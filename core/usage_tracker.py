"""Usage tracking, cost calculation, and LLM telemetry recording."""

from typing import Any, Callable, Dict, Optional


class UsageTracker:
    """Track LLM usage, compute costs, and persist telemetry."""

    def __init__(
        self,
        memory: Any,
        model_pricing_lookup: Callable,
    ) -> None:
        self._memory = memory
        self._pricing = model_pricing_lookup

    def merge_usage(
        self,
        base: Optional[Dict],
        extra: Optional[Dict],
    ) -> Optional[Dict]:
        """Combine two usage dicts from consecutive LLM calls."""
        if not base and not extra:
            return None
        if not base:
            return dict(extra)
        if not extra:
            return dict(base)

        merged = {
            "provider": extra.get("provider") or base.get("provider"),
            "model": extra.get("model") or base.get("model"),
            "prompt_tokens": int(base.get("prompt_tokens") or 0)
            + int(extra.get("prompt_tokens") or 0),
            "completion_tokens": int(base.get("completion_tokens") or 0)
            + int(extra.get("completion_tokens") or 0),
            "total_tokens": int(base.get("total_tokens") or 0)
            + int(extra.get("total_tokens") or 0),
            "prompt_cache_hit_tokens": int(base.get("prompt_cache_hit_tokens") or 0)
            + int(extra.get("prompt_cache_hit_tokens") or 0),
            "prompt_cache_miss_tokens": int(base.get("prompt_cache_miss_tokens") or 0)
            + int(extra.get("prompt_cache_miss_tokens") or 0),
            "reasoning_tokens": int(base.get("reasoning_tokens") or 0)
            + int(extra.get("reasoning_tokens") or 0),
            "estimated_cost_usd": None,
        }

        base_cost = base.get("estimated_cost_usd")
        extra_cost = extra.get("estimated_cost_usd")
        if base_cost is not None or extra_cost is not None:
            merged["estimated_cost_usd"] = round(
                float(base_cost or 0.0) + float(extra_cost or 0.0),
                8,
            )

        return merged

    def enrich_usage_cost(
        self,
        provider: Optional[str],
        model: Optional[str],
        usage: Optional[Dict],
    ) -> Optional[Dict]:
        """Add estimated_cost_usd to raw token usage using catalog pricing."""
        if not usage:
            return usage
        if usage.get("estimated_cost_usd") is not None:
            return usage
        if not provider or not model:
            return usage
        catalog = self._pricing(provider, model)
        if not isinstance(catalog, dict):
            return usage
        input_cost = catalog.get("input_cost_per_token")
        output_cost = catalog.get("output_cost_per_token")
        cache_cost = catalog.get("cache_read_cost_per_token")
        if input_cost is None or output_cost is None:
            return usage
        cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
        cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        if prompt_tokens and not cache_hit_tokens and not cache_miss_tokens:
            cache_miss_tokens = prompt_tokens
        cost = (
            cache_hit_tokens * float(cache_cost if cache_cost is not None else input_cost)
            + cache_miss_tokens * float(input_cost)
            + completion_tokens * float(output_cost)
        )
        enriched = dict(usage)
        enriched["estimated_cost_usd"] = round(cost, 8)
        return enriched

    def record_route_decision(
        self,
        conversation_id: Optional[str],
        route: Any,
        usage: Optional[Dict],
        project_name: Optional[str],
        opencode_command: Optional[str],
    ) -> None:
        """Persist the route selection decision for later analysis."""
        self._memory.record_agent_route_decision(
            conversation_id=conversation_id,
            route=route,
            usage=usage,
            project_name=project_name,
            opencode_command=opencode_command,
        )

    def record_llm_telemetry(self, **kwargs) -> None:
        """Record per-request LLM telemetry."""
        self._memory.record_llm_request_telemetry(**kwargs)
