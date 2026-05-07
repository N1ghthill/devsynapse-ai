"""LLM execution with model fallback and degraded mode."""

import logging
import random
import time
from typing import Callable, Dict, List, Optional

import requests

from config.settings import AppSettings
from core.async_utils import run_blocking
from core.deepseek import DeepSeekClient, LLMResult
from core.llm_optimization import ModelRoute
from core.tools.openai_tool_defs import OPENCODE_TOOLS
from core.usage_tracker import UsageTracker

logger = logging.getLogger(__name__)

# Operational errors that should trigger fallback mode
OPERATIONAL_ERRORS = (
    requests.ConnectionError,
    requests.Timeout,
    requests.HTTPError,
    TimeoutError,
    OSError,
    RuntimeError,
)


class LLMExecutor:
    """Orchestrate LLM API calls with fallback and telemetry recording."""

    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        usage_tracker: UsageTracker,
        get_settings: Callable[[], AppSettings],
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
            return LLMResult(content=self._get_fallback_response("not_configured"))

        model = route.model if route else self._client.model
        start_time = time.perf_counter()
        try:
            return await self._complete_and_record(
                messages, model, tool_choice, route, user_id, conversation_id, start_time,
                on_token,
            )
        except OPERATIONAL_ERRORS as e:
            fallback_model = route.fallback_model if route else None
            if fallback_model and fallback_model != model:
                try:
                    logger.warning(
                        "LLM model %s call failed (%s); retrying with %s",
                        model, e, fallback_model,
                    )
                    return await self._complete_and_record(
                        messages, fallback_model, tool_choice, route, user_id,
                        conversation_id, start_time, on_token,
                    )
                except OPERATIONAL_ERRORS as fallback_error:
                    logger.warning(
                        "LLM fallback model %s failed: %s (original error: %s)",
                        fallback_model, fallback_error, e,
                    )
                    self._usage.record_llm_telemetry(
                        user_id=user_id, conversation_id=conversation_id,
                        provider=None, model=model, route=route, success=False,
                        usage=None,
                        total_latency_ms=(time.perf_counter() - start_time) * 1000,
                        error_message=f"Primary: {e}; Fallback: {fallback_error}",
                    )
                    logger.warning("LLM provider failed: %s. Using degraded response.", e)
                    return LLMResult(content=self._get_fallback_response("unavailable"))

            self._usage.record_llm_telemetry(
                user_id=user_id, conversation_id=conversation_id,
                provider=None, model=model, route=route, success=False,
                usage=None,
                total_latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )
            logger.warning("LLM provider failed: %s. Using degraded response.", e)
            return LLMResult(content=self._get_fallback_response("unavailable"))

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
        raw_usage = result.usage
        if raw_usage is None and (result.provider or result.model):
            raw_usage = {"provider": result.provider, "model": result.model}
        usage = self._usage.enrich_usage_cost(result.provider, result.model, raw_usage)
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
    def _get_fallback_response(reason: str = "unavailable") -> str:
        """Return a random degraded-mode response when the API is unavailable."""
        if reason == "not_configured":
            return (
                "No LLM provider is configured yet. Use /connect to add a provider key, "
                "or ask me to run specific local commands like 'bash ls' or 'read file'."
            )
        fallback_responses = [
            "The selected LLM provider timed out and I switched to degraded mode. "
            "I can still help with basic local tasks if you specify what you need.",
            "The selected LLM provider is temporarily unavailable. "
            "You can ask me to run specific commands like 'bash ls' or 'read file'.",
            "The active model is not responding right now. "
            "I can still help with tasks that do not require remote model analysis.",
        ]
        return random.choice(fallback_responses)
