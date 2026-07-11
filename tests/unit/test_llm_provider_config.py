from types import SimpleNamespace

import pytest

from core import llm_provider_config


def _settings(**overrides):
    values = {
        "llm_default_provider": "openrouter",
        "deepseek_api_key": None,
        "openrouter_api_key": None,
        "opencode_zen_api_key": None,
        "opencode_go_api_key": None,
        "deepseek_model": "deepseek-v4-pro",
        "openrouter_model": "openrouter/free",
        "opencode_zen_model": "qwen3-coder",
        "opencode_go_model": "deepseek-v4-pro",
        "openrouter_models_url": "https://openrouter.ai/api/v1/models",
        "opencode_go_models_url": "https://opencode.ai/zen/go/v1/models",
        "opencode_zen_models_url": "https://opencode.ai/zen/v1/models",
        "llm_request_timeout": 12,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeGetSettings:
    def __init__(self, settings):
        self.settings = settings
        self.cleared = False

    def __call__(self):
        return self.settings

    def cache_clear(self):
        self.cleared = True


def test_provider_status_reports_openrouter_without_secret(monkeypatch):
    settings = _settings(openrouter_api_key="sk-openrouter-secret")
    monkeypatch.setattr(llm_provider_config.app_settings, "get_settings", FakeGetSettings(settings))

    result = llm_provider_config.provider_status({})

    assert result["ready"] is True
    openrouter = next(provider for provider in result["providers"] if provider["id"] == "openrouter")
    assert openrouter["configured"] is True
    assert openrouter["model"] == "openrouter/free"
    assert "sk-openrouter-secret" not in str(result)


def test_configure_provider_persists_default_provider_and_model(monkeypatch):
    settings = _settings()
    fake_get_settings = FakeGetSettings(settings)
    captured = {}

    def fake_set_runtime_config_values(updates):
        captured.update(updates)
        settings.llm_default_provider = updates["LLM_DEFAULT_PROVIDER"]
        settings.openrouter_api_key = updates["OPENROUTER_API_KEY"]
        settings.openrouter_model = updates["OPENROUTER_MODEL"]

    monkeypatch.setattr(llm_provider_config.app_settings, "get_settings", fake_get_settings)
    monkeypatch.setattr(
        llm_provider_config,
        "set_runtime_config_values",
        fake_set_runtime_config_values,
    )

    result = llm_provider_config.configure_provider(
        {
            "provider": "openrouter",
            "apiKey": "sk-openrouter-secret",
            "model": "qwen/qwen3-coder:free",
        }
    )

    assert captured == {
        "LLM_DEFAULT_PROVIDER": "openrouter",
        "OPENROUTER_MODEL": "qwen/qwen3-coder:free",
        "OPENROUTER_API_KEY": "sk-openrouter-secret",
    }
    assert fake_get_settings.cleared is True
    assert result["activeModel"] == "qwen/qwen3-coder:free"
    assert "sk-openrouter-secret" not in str(result)


def test_configure_provider_requires_key_when_provider_is_not_configured(monkeypatch):
    monkeypatch.setattr(
        llm_provider_config.app_settings,
        "get_settings",
        FakeGetSettings(_settings()),
    )

    with pytest.raises(ValueError, match="missing_provider_api_key"):
        llm_provider_config.configure_provider(
            {"provider": "openrouter", "apiKey": "", "model": "openrouter/free"}
        )
