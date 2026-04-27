"""
DeepSeek API client — transport, payload, pricing.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, AsyncIterator, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


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

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: List[Dict],
        tools: List[Dict],
        stream: bool,
        model: Optional[str] = None,
    ) -> Dict:
        thinking_config = {"type": "enabled" if self.thinking_enabled else "disabled"}
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": stream,
            "tools": tools,
            "tool_choice": "auto",
            "reasoning_effort": self.reasoning_effort,
            "thinking": thinking_config,
        }
        if not self.thinking_enabled:
            payload["temperature"] = self.temperature
        return payload

    def chat_completion(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        max_tokens: Optional[int] = None,
        thinking: Optional[Dict] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Non-streaming chat completion call."""
        url = f"{self.base_url}/chat/completions"
        request_model = model or self.model
        payload = self._build_payload(messages, tools or [], stream=False, model=request_model)

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if thinking is not None:
            payload["thinking"] = thinking
            payload.pop("tools", None)
            payload.pop("tool_choice", None)

        response = requests.post(
            url,
            headers=self._build_headers(),
            json=payload,
            timeout=(5, self.request_timeout),
        )
        response.raise_for_status()

        result = response.json()
        choice = result["choices"][0]
        message = choice.get("message", {})
        usage = self._build_usage_snapshot(
            provider="deepseek",
            model=result.get("model") or request_model,
            usage=result.get("usage") or {},
        )
        return {
            "content": message.get("content") or "",
            "provider": "deepseek",
            "model": result.get("model") or request_model,
            "usage": usage,
            "tool_calls": message.get("tool_calls"),
            "reasoning_content": message.get("reasoning_content"),
        }

    async def chat_completion_streaming(
        self, messages: List[Dict], tools: List[Dict], model: Optional[str] = None
    ) -> AsyncIterator[Dict]:
        """Streaming chat completion, yielding delta chunks."""
        import httpx

        url = f"{self.base_url}/chat/completions"
        request_model = model or self.model
        payload = self._build_payload(messages, tools, stream=True, model=request_model)

        collected_content = ""
        collected_reasoning = ""
        collected_usage: Optional[Dict] = None
        tool_call_buffers: Dict[int, Dict] = {}

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=self._build_headers(),
                json=payload,
                timeout=httpx.Timeout(5.0, read=self.request_timeout),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json

                        chunk = json.loads(data_str)
                    except Exception:
                        continue

                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        reasoning = delta.get("reasoning_content", "")
                        if reasoning:
                            collected_reasoning += reasoning
                            yield {"type": "reasoning", "content": reasoning}

                        content = delta.get("content", "")
                        if content:
                            collected_content += content
                            yield {"type": "text", "content": content}

                        tc_deltas = delta.get("tool_calls")
                        if tc_deltas:
                            for tc in tc_deltas:
                                idx = tc.get("index", 0)
                                buf = tool_call_buffers.setdefault(
                                    idx,
                                    {
                                        "id": None,
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    },
                                )
                                if "id" in tc and tc["id"]:
                                    buf["id"] = tc["id"]
                                if tc.get("function") and tc["function"].get("name"):
                                    buf["function"]["name"] = tc["function"]["name"]
                                if tc.get("function") and "arguments" in tc["function"]:
                                    buf["function"]["arguments"] += tc["function"]["arguments"]

                    usage_chunk = chunk.get("usage")
                    if usage_chunk:
                        collected_usage = usage_chunk

        collected_tool_calls = (
            [tool_call_buffers[idx] for idx in sorted(tool_call_buffers)] or None
        )

        usage = self._build_usage_snapshot(
            provider="deepseek",
            model=request_model,
            usage=collected_usage or {},
        )
        yield {
            "type": "done",
            "content": collected_content,
            "usage": usage,
            "tool_calls": collected_tool_calls,
            "reasoning_content": collected_reasoning or None,
        }

    def _build_usage_snapshot(
        self, provider: str, model: str, usage: Dict
    ) -> Dict[str, int | float | str | None]:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        prompt_cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
        prompt_cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
        reasoning_tokens = int(
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        )

        if prompt_tokens and not prompt_cache_hit_tokens and not prompt_cache_miss_tokens:
            prompt_cache_miss_tokens = prompt_tokens

        estimated_cost_usd = self._calculate_usage_cost(
            provider=provider,
            model=model,
            prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            prompt_cache_miss_tokens=prompt_cache_miss_tokens,
            completion_tokens=completion_tokens,
        )

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
