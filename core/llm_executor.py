"""LLM execution with model fallback and degraded mode."""

import logging
import random
import time
from typing import Callable, Dict, List, Optional

from core.async_utils import run_blocking
from core.deepseek import DeepSeekClient, LLMResult
from core.llm_optimization import ModelRoute
from core.tools.openai_tool_defs import OPENCODE_TOOLS

logger = logging.getLogger(__name__)


class LLMExecutor:
    """Orchestrate LLM API calls with fallback and telemetry recording."""

    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        usage_tracker,
        get_settings: Callable,
    ) -> None:
        self._client = deepseek_client
        self._usage = usage_tracker
        self._get_settings = get_settings

    async def call_api(
        self,
        messages: List[Dict],
        route: Optional[ModelRoute] = None,
        tool_choice: object = "auto",
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResult:
        """Call the LLM API with model fallback and degraded mode."""
        if not self._client.configured:
            return LLMResult(content=self._get_fallback_response())

        model = route.model if route else self._client.model
        start_time = time.perf_counter()
        try:
            return await self._complete_and_record(
                messages, model, tool_choice, route, user_id, conversation_id, start_time,
                on_token,
            )
        except Exception as e:
            fallback_model = route.fallback_model if route else None
            if fallback_model and fallback_model != model:
                try:
                    logger.warning(
                        "DeepSeek %s call failed (%s); retrying with %s",
                        model, e, fallback_model,
                    )
                    return await self._complete_and_record(
                        messages, fallback_model, tool_choice, route, user_id,
                        conversation_id, start_time, on_token,
                    )
                except Exception as fallback_error:
                    logger.warning(
                        "DeepSeek fallback model %s failed: %s",
                        fallback_model, fallback_error,
                    )

            self._usage.record_llm_telemetry(
                user_id=user_id, conversation_id=conversation_id,
                provider=None, model=model, route=route, success=False,
                usage=None,
                total_latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )
            logger.warning("DeepSeek API falhou: %s. Usando resposta degradada.", e)
            return LLMResult(content=self._get_fallback_response())

    async def _complete_and_record(
        self,
        messages: List[Dict],
        model: str,
        tool_choice: object,
        route: Optional[ModelRoute],
        user_id: Optional[str],
        conversation_id: Optional[str],
        start_time: float,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResult:
        settings = self._get_settings()
        if settings.llm_streaming_enabled:
            result = await run_blocking(
                self._client.stream_chat_completion,
                messages,
                OPENCODE_TOOLS,
                model=model,
                tool_choice=tool_choice,
                on_token=on_token,
            )
        else:
            result = await run_blocking(
                self._client.chat_completion,
                messages,
                OPENCODE_TOOLS,
                model=model,
                tool_choice=tool_choice,
            )
        usage = self._usage.enrich_usage_cost(result.provider, result.model, result.usage)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._usage.record_llm_telemetry(
            user_id=user_id, conversation_id=conversation_id,
            provider=result.provider, model=result.model,
            route=route, success=True, usage=usage,
            first_token_latency_ms=elapsed_ms, total_latency_ms=elapsed_ms,
        )
        return LLMResult(
            content=result.content,
            provider=result.provider,
            model=result.model,
            usage=usage,
            tool_calls=result.tool_calls,
            reasoning_content=result.reasoning_content,
        )

    @staticmethod
    def _get_fallback_response() -> str:
        """Return a random degraded-mode response when the API is unavailable."""
        fallback_responses = [
            "The DeepSeek API timed out and I switched to degraded mode. "
            "I can still help with basic tasks if you specify what you need.",
            "DeepSeek is temporarily unavailable. "
            "You can ask me to run specific commands like 'bash ls' or 'read file'.",
            "Sorry, I'm having technical difficulties. "
            "In the meantime, I can help with tasks that don't require complex AI analysis."
        ]
        return random.choice(fallback_responses)
