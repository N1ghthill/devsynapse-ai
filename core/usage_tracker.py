"""Usage tracking, cost calculation, and LLM telemetry recording."""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Fallback pricing for common models when catalog is unavailable
# These are approximate prices as of 2024-01
FALLBACK_PRICING = {
    # OpenAI
    "gpt-4o": {"input_cost_per_token": 0.0000025, "output_cost_per_token": 0.000010},
    "gpt-4o-mini": {"input_cost_per_token": 0.00000015, "output_cost_per_token": 0.0000006},
    "gpt-4-turbo": {"input_cost_per_token": 0.00001, "output_cost_per_token": 0.00003},
    # Anthropic
    "claude-3-5-sonnet": {"input_cost_per_token": 0.000003, "output_cost_per_token": 0.000015},
    "claude-3-opus": {"input_cost_per_token": 0.000015, "output_cost_per_token": 0.000075},
    "claude-3-haiku": {"input_cost_per_token": 0.00000025, "output_cost_per_token": 0.00000125},
    # DeepSeek
    "deepseek-chat": {"input_cost_per_token": 0.00000027, "output_cost_per_token": 0.0000011},
    "deepseek-reasoner": {"input_cost_per_token": 0.00000055, "output_cost_per_token": 0.00000219},
    # Moonshot (Kimi)
    "kimi-k2": {"input_cost_per_token": 0.0000002, "output_cost_per_token": 0.0000008},
    # Qwen
    "qwen-max": {"input_cost_per_token": 0.0000004, "output_cost_per_token": 0.0000012},
}


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
        """Add estimated_cost_usd to raw token usage using catalog pricing.

        Supports both pay-per-use and plan-based billing:
        - pay-per-use: calculates cost based on token prices
        - plan: tracks tokens used vs limit, calculates overage if any
        """
        if not usage:
            return usage
        if usage.get("estimated_cost_usd") is not None:
            return usage
        if not provider or not model:
            return usage

        # Try catalog pricing first
        catalog = self._pricing(provider, model)
        pricing = None

        if isinstance(catalog, dict):
            # Check if this is a plan-based model
            billing_type = catalog.get("billing_type", "pay_per_use")

            if billing_type == "plan":
                return self._calculate_plan_usage(catalog, usage)

            # Pay-per-use: get prices from catalog
            input_cost = catalog.get("input_cost_per_token")
            output_cost = catalog.get("output_cost_per_token")
            cache_cost = catalog.get("cache_read_cost_per_token")

            if input_cost is not None and output_cost is not None:
                pricing = {
                    "input_cost_per_token": input_cost,
                    "output_cost_per_token": output_cost,
                    "cache_read_cost_per_token": cache_cost,
                }

        # Fallback to hardcoded pricing if catalog doesn't have prices
        if pricing is None:
            pricing = self._get_fallback_pricing(model)
            if pricing:
                logger.debug(
                    "Using fallback pricing for %s:%s", provider, model
                )

        # If still no pricing, return usage with cost=0 (don't block)
        if pricing is None:
            enriched = dict(usage)
            enriched["estimated_cost_usd"] = 0.0
            enriched["pricing_source"] = "unknown"
            logger.warning(
                "No pricing available for %s:%s, cost will be $0.00",
                provider,
                model,
            )
            return enriched

        # Calculate cost
        input_cost = pricing["input_cost_per_token"]
        output_cost = pricing["output_cost_per_token"]
        cache_cost = pricing.get("cache_read_cost_per_token")

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
        enriched["pricing_source"] = "catalog" if catalog else "fallback"
        return enriched

    def _calculate_plan_usage(
        self,
        catalog: Dict,
        usage: Dict,
    ) -> Dict:
        """Calculate usage for plan-based billing.

        Returns usage dict with plan-specific fields:
        - tokens_used: tokens consumed this period
        - tokens_limit: tokens included in plan
        - tokens_remaining: tokens left in plan
        - pct_used: percentage of plan consumed
        - days_remaining: days until plan resets
        - overage_cost: cost if exceeded plan limit
        """
        tokens_used = int(usage.get("total_tokens") or 0)
        tokens_limit = int(catalog.get("plan_tokens_limit") or 0)
        tokens_remaining = max(0, tokens_limit - tokens_used)
        pct_used = (tokens_used / tokens_limit * 100.0) if tokens_limit > 0 else 0.0

        # Calculate days remaining in plan cycle
        days_remaining = self._calculate_plan_days_remaining(catalog)

        # Calculate overage cost if exceeded
        overage_cost = 0.0
        if tokens_used > tokens_limit:
            overage = tokens_used - tokens_limit
            overage_rate = float(catalog.get("overage_cost_per_1k") or 0.0) / 1000.0
            overage_cost = overage * overage_rate

        enriched = dict(usage)
        enriched["estimated_cost_usd"] = 0.0  # Base plan cost is fixed
        enriched["billing_type"] = "plan"
        enriched["plan_tokens_used"] = tokens_used
        enriched["plan_tokens_limit"] = tokens_limit
        enriched["plan_tokens_remaining"] = tokens_remaining
        enriched["plan_pct_used"] = round(pct_used, 2)
        enriched["plan_days_remaining"] = days_remaining
        enriched["plan_overage_cost"] = round(overage_cost, 8)
        enriched["pricing_source"] = "plan"
        return enriched

    def _calculate_plan_days_remaining(self, catalog: Dict) -> int:
        """Calculate days remaining in current plan cycle."""
        from datetime import datetime, timedelta

        start_date_str = catalog.get("plan_start_date")
        reset_cycle = catalog.get("plan_reset_cycle", "monthly")

        if not start_date_str:
            return 30  # Default

        try:
            start_date = datetime.fromisoformat(start_date_str)
            now = datetime.now()

            if reset_cycle == "daily":
                next_reset = start_date + timedelta(days=1)
                while next_reset < now:
                    next_reset += timedelta(days=1)
                return (next_reset - now).days

            elif reset_cycle == "weekly":
                next_reset = start_date + timedelta(weeks=1)
                while next_reset < now:
                    next_reset += timedelta(weeks=1)
                return (next_reset - now).days

            else:  # monthly
                # Add months until we're past now
                months = 0
                next_reset = start_date
                while next_reset < now:
                    months += 1
                    # Handle month addition properly
                    month = start_date.month + months
                    year = start_date.year + (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                    day = min(start_date.day, 28)  # Safe day
                    next_reset = datetime(year, month, day)

                return (next_reset - now).days

        except (ValueError, TypeError):
            return 30  # Default fallback

    def _get_fallback_pricing(self, model: str) -> Optional[Dict]:
        """Get pricing from fallback table for common models."""
        # Try exact match first
        model_lower = model.lower()
        if model_lower in FALLBACK_PRICING:
            return FALLBACK_PRICING[model_lower]

        # Try partial match (e.g., "gpt-4o-2024-05-13" -> "gpt-4o")
        for key, pricing in FALLBACK_PRICING.items():
            if key in model_lower or model_lower.startswith(key):
                return pricing

        return None

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
