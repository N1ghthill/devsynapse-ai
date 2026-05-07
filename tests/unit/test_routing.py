"""Tests for provider-aware route selection."""

from core.routing import RouteSelector


class FakeMemory:
    def __init__(self, models=None):
        self.models = models or []

    def get_app_settings(self):
        return {}

    def get_llm_budget_status(self):
        return {"overall_status": "healthy"}

    def get_agent_learning(self, _task_signature):
        return None

    def list_llm_models(self, provider=None, limit=200):
        items = self.models
        if provider:
            items = [model for model in items if model["provider"] == provider]
        return items[:limit]


def test_select_route_uses_default_provider_when_deepseek_is_not_configured():
    selector = RouteSelector(
        memory=FakeMemory(),
        deepseek_model="deepseek-v4-pro",
        provider_configs={"openrouter": {"api_key": "sk-test"}},
        deepseek_api_key=None,
        default_provider="openrouter",
        provider_model_defaults={"openrouter": "openrouter/free"},
    )

    route = selector.select_route("Explique rapidamente este erro", {})

    assert route.model == "openrouter:openrouter/free"
    assert route.reason == "manual_model_selection"
    assert route.complexity == "manual"


def test_select_route_respects_selected_paid_model_for_simple_chat():
    selector = RouteSelector(
        memory=FakeMemory(
            [
                {
                    "provider": "openrouter",
                    "model_id": "paid/model",
                    "enabled": True,
                    "input_cost_per_token": 0.000001,
                    "output_cost_per_token": 0.000002,
                },
                {
                    "provider": "openrouter",
                    "model_id": "qwen/qwen3-coder:free",
                    "enabled": True,
                    "input_cost_per_token": 0.0,
                    "output_cost_per_token": 0.0,
                },
            ]
        ),
        deepseek_model="deepseek-v4-pro",
        provider_configs={"openrouter": {"api_key": "sk-test"}},
        deepseek_api_key=None,
        default_provider="openrouter",
        provider_model_defaults={"openrouter": "paid/model"},
    )

    route = selector.select_route("Oi", {})

    assert route.model == "openrouter:paid/model"


def test_select_route_respects_selected_free_openrouter_model_for_chat():
    selector = RouteSelector(
        memory=FakeMemory(
            [
                {
                    "provider": "openrouter",
                    "model_id": "google/gemini-2.5-flash-lite",
                    "enabled": True,
                    "input_cost_per_token": 0.0,
                    "output_cost_per_token": 0.0,
                }
            ]
        ),
        deepseek_model="deepseek-v4-pro",
        provider_configs={"openrouter": {"api_key": "sk-test"}},
        deepseek_api_key=None,
        default_provider="openrouter",
        provider_model_defaults={"openrouter": "google/gemma-4-26b-a4b-it:free"},
    )

    route = selector.select_route("Oi", {})

    assert route.model == "openrouter:google/gemma-4-26b-a4b-it:free"


def test_select_route_falls_back_to_configured_provider_catalog():
    selector = RouteSelector(
        memory=FakeMemory(
            [
                {
                    "provider": "opencode-go",
                    "model_id": "deepseek-v4-flash",
                    "enabled": True,
                    "input_cost_per_token": 0.000001,
                    "output_cost_per_token": 0.000002,
                }
            ]
        ),
        deepseek_model="deepseek-v4-pro",
        provider_configs={"opencode-go": {"api_key": "sk-test"}},
        deepseek_api_key=None,
        default_provider="deepseek",
        provider_model_defaults={},
    )

    route = selector.select_route("Explique este trecho", {})

    assert route.model == "opencode-go:deepseek-v4-flash"
    assert route.reason == "manual_model_selection"


def test_select_route_sets_cross_provider_fallback_model():
    selector = RouteSelector(
        memory=FakeMemory(),
        deepseek_model="deepseek-v4-pro",
        provider_configs={"openrouter": {"api_key": "sk-test"}},
        deepseek_api_key="sk-deepseek",
        default_provider="deepseek",
        provider_model_defaults={
            "deepseek": "deepseek-v4-pro",
            "openrouter": "openrouter/free",
        },
    )

    route = selector.select_route("Explique este trecho", {})

    assert route.model == "deepseek-v4-pro"
    assert route.fallback_model == "openrouter:openrouter/free"


def test_select_route_does_not_prefer_deepseek_when_default_is_unconfigured():
    selector = RouteSelector(
        memory=FakeMemory(),
        deepseek_model="deepseek-v4-pro",
        provider_configs={"openrouter": {"api_key": "sk-test"}},
        deepseek_api_key="sk-deepseek",
        default_provider="opencode-go",
        provider_model_defaults={
            "deepseek": "deepseek-v4-pro",
            "openrouter": "openrouter/free",
            "opencode-go": "deepseek-v4-pro",
        },
    )

    route = selector.select_route("Explique este trecho", {})

    assert route.model == "openrouter:openrouter/free"
    assert route.fallback_model == "deepseek-v4-pro"
