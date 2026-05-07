"""Tests for core/usage_tracker.py."""

from unittest.mock import Mock

from core.usage_tracker import UsageTracker


def _tracker(model_pricing=None):
    memory = Mock()
    pricing = model_pricing or {}
    memory.get_llm_model = Mock(side_effect=lambda p, m: pricing.get((p, m)))
    return UsageTracker(memory=memory, model_pricing_lookup=memory.get_llm_model)


class TestMergeUsage:
    def test_both_present(self):
        t = _tracker()
        base = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "estimated_cost_usd": 0.001}
        extra = {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300, "estimated_cost_usd": 0.002}
        result = t.merge_usage(base, extra)
        assert result["prompt_tokens"] == 300
        assert result["completion_tokens"] == 150
        assert result["total_tokens"] == 450
        assert result["estimated_cost_usd"] == 0.003

    def test_base_only(self):
        t = _tracker()
        base = {"prompt_tokens": 100}
        result = t.merge_usage(base, None)
        assert result == {"prompt_tokens": 100}

    def test_extra_only(self):
        t = _tracker()
        extra = {"completion_tokens": 50}
        result = t.merge_usage(None, extra)
        assert result == {"completion_tokens": 50}

    def test_both_none(self):
        t = _tracker()
        result = t.merge_usage(None, None)
        assert result is None

    def test_cost_none_handling(self):
        t = _tracker()
        base = {"prompt_tokens": 100, "estimated_cost_usd": None}
        extra = {"prompt_tokens": 50, "estimated_cost_usd": None}
        result = t.merge_usage(base, extra)
        assert result["estimated_cost_usd"] is None


class TestEnrichUsageCost:
    def test_with_catalog_entry(self):
        pricing = {
            ("openai", "gpt-4"): {
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
                "cache_read_cost_per_token": 0.000015,
            }
        }
        t = _tracker(model_pricing=pricing)
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
        }
        result = t.enrich_usage_cost("openai", "gpt-4", usage)
        assert result["estimated_cost_usd"] == round(1000 * 0.00003 + 500 * 0.00006, 8)

    def test_no_catalog(self):
        t = _tracker(model_pricing={})
        usage = {"prompt_tokens": 100, "completion_tokens": 50}
        result = t.enrich_usage_cost("unknown", "model", usage)
        # Now returns enriched dict with cost=0.0 instead of unchanged usage
        assert result is not usage
        assert result["estimated_cost_usd"] == 0.0
        assert result["pricing_source"] == "unknown"
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50

    def test_already_has_cost(self):
        t = _tracker()
        usage = {"prompt_tokens": 100, "estimated_cost_usd": 0.005}
        result = t.enrich_usage_cost("openai", "gpt-4", usage)
        assert result is usage

    def test_usage_is_none(self):
        t = _tracker()
        result = t.enrich_usage_cost("openai", "gpt-4", None)
        assert result is None

    def test_cache_tokens_used(self):
        pricing = {
            ("openai", "gpt-4"): {
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
                "cache_read_cost_per_token": 0.000015,
            }
        }
        t = _tracker(model_pricing=pricing)
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_cache_hit_tokens": 600,
            "prompt_cache_miss_tokens": 400,
        }
        result = t.enrich_usage_cost("openai", "gpt-4", usage)
        expected = 600 * 0.000015 + 400 * 0.00003 + 500 * 0.00006
        assert result["estimated_cost_usd"] == round(expected, 8)

    def test_no_provider_or_model(self):
        t = _tracker()
        usage = {"prompt_tokens": 100}
        result = t.enrich_usage_cost(None, "gpt-4", usage)
        assert result is usage
        result = t.enrich_usage_cost("openai", None, usage)
        assert result is usage


class TestRecordRouteDecision:
    def test_delegates_to_memory(self):
        memory = Mock()
        t = UsageTracker(memory=memory, model_pricing_lookup=Mock())
        route = Mock()
        t.record_route_decision("conv1", route, {"tokens": 100}, "proj1", "bash ls")
        memory.record_agent_route_decision.assert_called_once_with(
            conversation_id="conv1",
            route=route,
            usage={"tokens": 100},
            project_name="proj1",
            opencode_command="bash ls",
        )


class TestRecordLLMTelemetry:
    def test_delegates_to_memory(self):
        memory = Mock()
        t = UsageTracker(memory=memory, model_pricing_lookup=Mock())
        t.record_llm_telemetry(user_id="u1", conversation_id="c1", provider="openai", success=True)
        memory.record_llm_request_telemetry.assert_called_once_with(
            user_id="u1", conversation_id="c1", provider="openai", success=True,
        )
