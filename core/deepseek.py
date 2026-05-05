"""
DeepSeek API client — transport, payload, pricing.
"""

import json
import logging
import time
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, Dict, Iterator, List, Optional

import httpx

from core.metrics import metrics

logger = logging.getLogger(__name__)
KNOWN_PROVIDER_PREFIXES = {"deepseek", "openrouter", "opencode-zen", "opencode-go"}

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class LLMResult:
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, int | float | str | None]] = None
    tool_calls: Optional[List[Dict]] = None
    reasoning_content: Optional[str] = None


class DeepSeekClient:
    """Encapsulates DeepSeek API calls, payload construction and cost calculation."""

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        base_url: str,
        reasoning_effort: str,
        thinking_enabled: bool,
        temperature: float,
        max_tokens: int,
        request_timeout: int,
        flash_pricing: Optional[Dict[str, Decimal]] = None,
        pro_pricing: Optional[Dict[str, Decimal]] = None,
        provider_configs: Optional[Dict[str, Dict[str, Optional[str]]]] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.reasoning_effort = reasoning_effort
        self.thinking_enabled = thinking_enabled
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.request_timeout = request_timeout
        self.flash_pricing = flash_pricing or {}
        self.pro_pricing = pro_pricing or {}
        self.provider_configs = provider_configs or {}

    @property
    def configured(self) -> bool:
        return bool(self.api_key or any(cfg.get("api_key") for cfg in self.provider_configs.values()))

    def _resolve_provider_model(self, model: Optional[str]) -> tuple[str, str, str, Optional[str]]:
        selected = model or self.model
        provider, provider_model = "deepseek", selected
        if ":" in selected:
            candidate_provider, candidate_model = selected.split(":", 1)
            if candidate_provider in KNOWN_PROVIDER_PREFIXES or candidate_provider in self.provider_configs:
                provider, provider_model = candidate_provider, candidate_model

        if provider == "deepseek":
            return provider, provider_model, self.base_url, self.api_key

        config = self.provider_configs.get(provider) or {}
        return (
            provider,
            provider_model,
            str(config.get("base_url") or ""),
            config.get("api_key"),
        )

    def _build_headers(self, provider: str, api_key: Optional[str]) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "http://127.0.0.1"
            headers["X-Title"] = "DevSynapse AI"
        return headers

    def _post_with_retry(
        self,
        url: str,
        headers: Dict[str, str],
        json: Dict,
        stream: bool = False,
    ) -> httpx.Response:
        """POST with exponential backoff retry for transient failures."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                client = httpx.Client(timeout=httpx.Timeout(self.request_timeout, connect=5.0))
                response = client.post(
                    url,
                    headers=headers,
                    json=json,
                    stream=stream,
                )
                if response.status_code in RETRYABLE_STATUS_CODES:
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Retrying after %s (attempt %d/%d, wait %.1fs)",
                        response.status_code,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                    )
                    response.close()
                    client.close()
                    time.sleep(wait)
                    continue
                response._client = client
                return response
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Retrying after %s (attempt %d/%d, wait %.1fs)",
                        type(exc).__name__,
                        attempt + 1,
                        MAX_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                continue
        if last_error:
            raise last_error
        raise RuntimeError("All retries exhausted without a response")

    def _build_payload(
        self,
        messages: List[Dict],
        tools: List[Dict],
        stream: bool,
        model: Optional[str] = None,
        tool_choice: Any = "auto",
        provider: str = "deepseek",
    ) -> Dict:
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": stream,
            "tools": tools,
        }
        if provider == "deepseek":
            thinking_config = {"type": "enabled" if self.thinking_enabled else "disabled"}
            payload["reasoning_effort"] = self.reasoning_effort
            payload["thinking"] = thinking_config
            if not self.thinking_enabled:
                payload["temperature"] = self.temperature
        else:
            payload["temperature"] = self.temperature
        if tools:
            payload["tool_choice"] = tool_choice
        return payload

    def chat_completion(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        max_tokens: Optional[int] = None,
        thinking: Optional[Dict] = None,
        model: Optional[str] = None,
        tool_choice: Any = "auto",
    ) -> LLMResult:
        """Non-streaming chat completion call."""
        start = time.monotonic()
        try:
            provider, provider_model, base_url, api_key = self._resolve_provider_model(model)
            if not api_key or not base_url:
                raise RuntimeError(f"LLM provider not configured: {provider}")
            url = f"{base_url}/chat/completions"
            payload = self._build_payload(
                messages,
                tools or [],
                stream=False,
                model=provider_model,
                tool_choice=tool_choice,
                provider=provider,
            )

            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if thinking is not None:
                payload["thinking"] = thinking
                payload.pop("tools", None)
                payload.pop("tool_choice", None)

            response = self._post_with_retry(
                url,
                self._build_headers(provider, api_key),
                payload,
                stream=False,
            )
            response.raise_for_status()

            result = response.json()
            choice = result["choices"][0]
            message = choice.get("message", {})
            usage = self._build_usage_snapshot(
                provider=provider,
                model=result.get("model") or provider_model,
                usage=result.get("usage") or {},
            )
            duration = time.monotonic() - start
            metrics.record_timing("llm.latency", duration, {"provider": provider, "stream": "false"})
            metrics.increment("llm.success")
            if usage and usage.get("total_tokens"):
                metrics.record_gauge("llm.tokens", usage["total_tokens"], {"provider": provider})

            return LLMResult(
                content=message.get("content") or "",
                provider=provider,
                model=result.get("model") or provider_model,
                usage=usage,
                tool_calls=message.get("tool_calls"),
                reasoning_content=message.get("reasoning_content"),
            )
        except Exception:
            metrics.increment("llm.failure")
            raise

    def stream_chat_completion(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        max_tokens: Optional[int] = None,
        thinking: Optional[Dict] = None,
        model: Optional[str] = None,
        tool_choice: Any = "auto",
        on_token: Optional[Callable[[str], None]] = None,
    ) -> LLMResult:
        """Streaming chat completion call that returns the accumulated final result."""
        start = time.monotonic()
        try:
            provider, provider_model, base_url, api_key = self._resolve_provider_model(model)
            if not api_key or not base_url:
                raise RuntimeError(f"LLM provider not configured: {provider}")
            url = f"{base_url}/chat/completions"
            payload = self._build_payload(
                messages,
                tools or [],
                stream=True,
                model=provider_model,
                tool_choice=tool_choice,
                provider=provider,
            )
            payload["stream_options"] = {"include_usage": True}

            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if thinking is not None:
                payload["thinking"] = thinking
                payload.pop("tools", None)
                payload.pop("tool_choice", None)

            response = self._post_with_retry(
                url,
                self._build_headers(provider, api_key),
                payload,
                stream=True,
            )
            response.raise_for_status()

            content_parts: list[str] = []
            reasoning_parts: list[str] = []
            tool_call_parts: dict[int, Dict[str, Any]] = {}
            usage_payload: Dict[str, Any] = {}
            response_model = provider_model

            for event in self._iter_sse_events(response):
                if event.get("model"):
                    response_model = event["model"]
                if event.get("usage"):
                    usage_payload = event["usage"]

                choices = event.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    content_parts.append(content)
                    if on_token is not None:
                        on_token(content)

                reasoning_content = delta.get("reasoning_content")
                if reasoning_content:
                    reasoning_parts.append(reasoning_content)

                for tool_call_delta in delta.get("tool_calls") or []:
                    self._merge_tool_call_delta(tool_call_parts, tool_call_delta)

            usage = (
                self._build_usage_snapshot(provider=provider, model=response_model, usage=usage_payload)
                if usage_payload
                else None
            )
            tool_calls = [
                tool_call_parts[index]
                for index in sorted(tool_call_parts)
                if tool_call_parts[index].get("function", {}).get("name")
            ]

            duration = time.monotonic() - start
            metrics.record_timing("llm.latency", duration, {"provider": provider, "stream": "true"})
            metrics.increment("llm.success")
            if usage and usage.get("total_tokens"):
                metrics.record_gauge("llm.tokens", usage["total_tokens"], {"provider": provider})

            return LLMResult(
                content="".join(content_parts),
                provider=provider,
                model=response_model,
                usage=usage,
                tool_calls=tool_calls or None,
                reasoning_content="".join(reasoning_parts) or None,
            )
        except Exception:
            metrics.increment("llm.failure")
            raise

    @staticmethod
    def _iter_sse_events(response) -> Iterator[Dict[str, Any]]:
        try:
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    logger.debug("Ignoring malformed SSE payload: %s", data)
        finally:
            client = getattr(response, "_client", None)
            if client is not None:
                client.close()

    @staticmethod
    def _merge_tool_call_delta(
        tool_call_parts: dict[int, Dict[str, Any]],
        delta: Dict[str, Any],
    ) -> None:
        index = int(delta.get("index") or 0)
        entry = tool_call_parts.setdefault(
            index,
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if delta.get("id"):
            entry["id"] = delta["id"]
        if delta.get("type"):
            entry["type"] = delta["type"]

        function_delta = delta.get("function") or {}
        function = entry.setdefault("function", {"name": "", "arguments": ""})
        if function_delta.get("name"):
            function["name"] += function_delta["name"]
        if function_delta.get("arguments"):
            function["arguments"] += function_delta["arguments"]

    def _build_usage_snapshot(
        self, provider: str, model: str, usage: Dict
    ) -> Dict[str, int | float | str | None]:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        prompt_cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
        prompt_cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
        prompt_details = usage.get("prompt_tokens_details") or {}
        if not prompt_cache_hit_tokens:
            prompt_cache_hit_tokens = int(prompt_details.get("cached_tokens") or 0)
        reasoning_tokens = int(
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        )

        if prompt_tokens and not prompt_cache_hit_tokens and not prompt_cache_miss_tokens:
            prompt_cache_miss_tokens = prompt_tokens

        estimated_cost_usd = usage.get("cost")
        if estimated_cost_usd is None:
            estimated_cost_usd = self._calculate_usage_cost(
                provider=provider,
                model=model,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=prompt_cache_miss_tokens,
                completion_tokens=completion_tokens,
            )
        elif estimated_cost_usd is not None:
            estimated_cost_usd = float(estimated_cost_usd)

        return {
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_cache_hit_tokens": prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": prompt_cache_miss_tokens,
            "reasoning_tokens": reasoning_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        }

    def _calculate_usage_cost(
        self,
        provider: str,
        model: str,
        prompt_cache_hit_tokens: int,
        prompt_cache_miss_tokens: int,
        completion_tokens: int,
    ) -> Optional[float]:
        if provider != "deepseek":
            return None

        pricing = self._get_model_pricing(model)
        if pricing is None:
            return None

        per_million = Decimal("1000000")
        total = (
            Decimal(prompt_cache_hit_tokens) * pricing["cache_hit"] / per_million
            + Decimal(prompt_cache_miss_tokens) * pricing["cache_miss"] / per_million
            + Decimal(completion_tokens) * pricing["output"] / per_million
        )
        return float(total.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

    def _get_model_pricing(self, model: str) -> Optional[Dict[str, Decimal]]:
        normalized = model.lower()
        if normalized in {"deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash"}:
            return self.flash_pricing
        if normalized == "deepseek-v4-pro":
            return self.pro_pricing
        return None
