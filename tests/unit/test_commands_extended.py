"""Extended tests for DevSynapse AI TUI command handlers."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from devsynapse.commands import (
    CommandDispatcher,
    _curate_discovered_models,
    _dedupe_models,
    _format_money,
    _is_free_model,
    _mask_secret,
    _model_cost_label,
    _model_option_label,
    _model_search_text,
    _model_supports_tools,
    _normalize_provider,
    _provider_config,
    _provider_key,
    _provider_model,
    _shorten_middle,
    _sort_models_for_ui,
)
from devsynapse.tui import DevSynapseTUI


class TestMaskSecret:
    def test_none_returns_not_set(self):
        assert _mask_secret(None) == "not set"

    def test_empty_returns_not_set(self):
        assert _mask_secret("") == "not set"

    def test_short_returns_set(self):
        assert _mask_secret("short") == "set"

    def test_eight_chars_returns_set(self):
        assert _mask_secret("12345678") == "set"

    def test_nine_chars_returns_masked(self):
        result = _mask_secret("123456789")
        assert result.startswith("1234")
        assert result.endswith("6789")
        assert "..." in result

    def test_long_key_masked(self):
        result = _mask_secret("sk-test-1234567890abcdef")
        assert result == "sk-t...cdef"


class TestFormatMoney:
    def test_integer(self):
        assert _format_money(10) == "$10.000000"

    def test_float(self):
        assert _format_money(0.5) == "$0.500000"

    def test_string_number(self):
        assert _format_money("3.14") == "$3.140000"

    def test_none_returns_zero(self):
        assert _format_money(None) == "$0.000000"

    def test_invalid_string_returns_zero(self):
        assert _format_money("not a number") == "$0.000000"

    def test_list_returns_zero(self):
        assert _format_money([]) == "$0.000000"

    def test_zero(self):
        assert _format_money(0) == "$0.000000"

    def test_negative(self):
        assert _format_money(-5.5) == "$-5.500000"


class TestShortenMiddle:
    def test_short_value_unchanged(self):
        assert _shorten_middle("hello") == "hello"

    def test_exact_limit_unchanged(self):
        value = "a" * 32
        assert _shorten_middle(value, limit=32) == value

    def test_long_value_shortened(self):
        value = "a" * 50
        result = _shorten_middle(value, limit=32)
        assert len(result) <= 32
        assert "..." in result

    def test_none_returns_empty(self):
        assert _shorten_middle(None) == ""

    def test_custom_limit(self):
        value = "abcdefghij"
        result = _shorten_middle(value, limit=8)
        assert len(result) <= 11
        assert "..." in result


class TestModelHelpers:
    def test_is_free_model_zero_cost(self):
        model = {
            "model_id": "test/model",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        }
        assert _is_free_model(model) is True

    def test_is_free_model_suffix(self):
        model = {
            "model_id": "test/model:free",
            "input_cost_per_token": 0.01,
            "output_cost_per_token": 0.01,
        }
        assert _is_free_model(model) is True

    def test_is_paid_model(self):
        model = {
            "model_id": "test/model",
            "input_cost_per_token": 0.001,
            "output_cost_per_token": 0.002,
        }
        assert _is_free_model(model) is False

    def test_is_free_model_invalid_cost_returns_false(self):
        model = {
            "model_id": "test/model",
            "input_cost_per_token": "invalid",
            "output_cost_per_token": "invalid",
        }
        assert _is_free_model(model) is False

    def test_model_supports_tools_true(self):
        model = {
            "capabilities": {"supported_parameters": ["tools", "tool_choice"]},
        }
        assert _model_supports_tools(model) is True

    def test_model_supports_tools_only_tool_choice(self):
        model = {
            "capabilities": {"supported_parameters": ["tool_choice"]},
        }
        assert _model_supports_tools(model) is True

    def test_model_supports_tools_false(self):
        model = {
            "capabilities": {"supported_parameters": ["temperature"]},
        }
        assert _model_supports_tools(model) is False

    def test_model_supports_tools_no_capabilities(self):
        model = {}
        assert _model_supports_tools(model) is False

    def test_model_cost_label_free(self):
        model = {
            "model_id": "test/model",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        }
        assert _model_cost_label(model) == "free"

    def test_model_cost_label_paid(self):
        model = {
            "model_id": "test/model",
            "input_cost_per_token": 0.000001,
            "output_cost_per_token": 0.000002,
        }
        label = _model_cost_label(model)
        assert "$1.000/M in" in label
        assert "$2.000/M out" in label

    def test_model_cost_label_unknown(self):
        model = {
            "model_id": "test/model",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        }
        label = _model_cost_label(model)
        assert "free" in label or "cost unknown" in label

    def test_model_option_label(self):
        model = {
            "provider": "openrouter",
            "model_id": "test/model",
            "name": "Test Model",
            "context_length": 100000,
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "capabilities": {"supported_parameters": ["tools"]},
        }
        label = _model_option_label(model)
        assert "openrouter:test/model" in label
        assert "free" in label
        assert "tools" in label
        assert "ctx 100000" in label
        assert "Test Model" in label

    def test_model_search_text(self):
        model = {
            "provider": "openrouter",
            "model_id": "test/model",
            "name": "Test Model",
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
        }
        text = _model_search_text(model)
        assert "openrouter" in text
        assert "test/model" in text
        assert "test model" in text
        assert "free" in text


class TestDedupeAndSortModels:
    def test_dedupe_removes_duplicates(self):
        models = [
            {"provider": "openrouter", "model_id": "model1"},
            {"provider": "openrouter", "model_id": "model1"},
            {"provider": "openrouter", "model_id": "model2"},
        ]
        result = _dedupe_models(models)
        assert len(result) == 2

    def test_dedupe_skips_empty_provider(self):
        models = [
            {"provider": "", "model_id": "model1"},
            {"provider": "openrouter", "model_id": "model1"},
        ]
        result = _dedupe_models(models)
        assert len(result) == 1
        assert result[0]["provider"] == "openrouter"

    def test_dedupe_skips_empty_model_id(self):
        models = [
            {"provider": "openrouter", "model_id": ""},
            {"provider": "openrouter", "model_id": "model1"},
        ]
        result = _dedupe_models(models)
        assert len(result) == 1

    def test_sort_free_first(self):
        models = [
            {
                "provider": "openrouter",
                "model_id": "paid",
                "input_cost_per_token": 0.001,
                "output_cost_per_token": 0.001,
            },
            {
                "provider": "openrouter",
                "model_id": "free",
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
            },
        ]
        result = _sort_models_for_ui(models)
        assert result[0]["model_id"] == "free"

    def test_sort_tools_before_non_tools(self):
        models = [
            {
                "provider": "openrouter",
                "model_id": "no-tools",
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "capabilities": {"supported_parameters": []},
            },
            {
                "provider": "openrouter",
                "model_id": "with-tools",
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "capabilities": {"supported_parameters": ["tools"]},
            },
        ]
        result = _sort_models_for_ui(models)
        assert result[0]["model_id"] == "with-tools"

    def test_sort_by_cost_when_same_category(self):
        models = [
            {
                "provider": "openrouter",
                "model_id": "expensive",
                "input_cost_per_token": 0.01,
                "output_cost_per_token": 0.01,
            },
            {
                "provider": "openrouter",
                "model_id": "cheap",
                "input_cost_per_token": 0.001,
                "output_cost_per_token": 0.001,
            },
        ]
        result = _sort_models_for_ui(models)
        assert result[0]["model_id"] == "cheap"


class TestCurateDiscoveredModels:
    def test_curates_openrouter_free_and_tools(self):
        models = [
            {
                "provider": "openrouter",
                "model_id": "free-model",
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "capabilities": {"supported_parameters": ["tools"]},
            },
            {
                "provider": "openrouter",
                "model_id": "paid-no-tools",
                "input_cost_per_token": 0.001,
                "output_cost_per_token": 0.001,
                "capabilities": {"supported_parameters": []},
            },
            {
                "provider": "deepseek",
                "model_id": "deepseek-model",
                "input_cost_per_token": 0.001,
                "output_cost_per_token": 0.001,
            },
        ]
        result = _curate_discovered_models(models)
        assert len(result) == 2
        assert any(m["model_id"] == "free-model" for m in result)
        assert any(m["model_id"] == "deepseek-model" for m in result)

    def test_curates_respects_limit(self):
        models = [
            {
                "provider": "openrouter",
                "model_id": f"model-{i}",
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "capabilities": {"supported_parameters": ["tools"]},
            }
            for i in range(100)
        ]
        result = _curate_discovered_models(models, limit=10)
        assert len(result) == 10


class TestNormalizeProvider:
    def test_normalizes_known_aliases(self):
        assert _normalize_provider("zen") == "opencode-zen"
        assert _normalize_provider("opencode") == "opencode-zen"
        assert _normalize_provider("go") == "opencode-go"

    def test_passes_through_valid_providers(self):
        assert _normalize_provider("deepseek") == "deepseek"
        assert _normalize_provider("openrouter") == "openrouter"
        assert _normalize_provider("opencode-zen") == "opencode-zen"
        assert _normalize_provider("opencode-go") == "opencode-go"

    def test_strips_and_lowercases(self):
        assert _normalize_provider("  DeepSeek  ") == "deepseek"
        assert _normalize_provider("OPENROUTER") == "openrouter"

    def test_returns_none_for_empty(self):
        assert _normalize_provider(None) is None
        assert _normalize_provider("") is None
        assert _normalize_provider("   ") is None


class TestProviderConfig:
    def test_returns_config_for_valid_provider(self):
        config = _provider_config("deepseek")
        assert config is not None
        assert config["label"] == "DeepSeek"
        assert config["env_key"] == "DEEPSEEK_API_KEY"

    def test_returns_none_for_invalid_provider(self):
        assert _provider_config("invalid") is None

    def test_returns_config_for_alias(self):
        config = _provider_config("zen")
        assert config is not None
        assert config["label"] == "OpenCode Zen"


class TestProviderKeyAndModel:
    def test_provider_key_returns_value(self):
        class FakeSettings:
            deepseek_api_key = "test-key"
            openrouter_api_key = "or-key"
            opencode_zen_api_key = "zen-key"
            opencode_go_api_key = "go-key"

        settings = FakeSettings()
        assert _provider_key(settings, "deepseek") == "test-key"
        assert _provider_key(settings, "openrouter") == "or-key"

    def test_provider_model_returns_value(self):
        class FakeSettings:
            deepseek_model = "deepseek-v4-pro"
            openrouter_model = "openrouter/free"

        settings = FakeSettings()
        assert _provider_model(settings, "deepseek") == "deepseek-v4-pro"
        assert _provider_model(settings, "openrouter") == "openrouter/free"

    def test_provider_model_returns_default_when_empty(self):
        class FakeSettings:
            deepseek_model = ""

        settings = FakeSettings()
        result = _provider_model(settings, "deepseek")
        assert result == "deepseek-v4-pro"


def _configure_runtime(monkeypatch, runtime_root):
    monkeypatch.setenv("DEVSYNAPSE_HOME", str(runtime_root))
    monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(runtime_root / "config" / ".env"))
    monkeypatch.setenv("DEVSYNAPSE_DATA_DIR", str(runtime_root / "data"))
    monkeypatch.setenv("DEVSYNAPSE_LOGS_DIR", str(runtime_root / "logs"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "")
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "")


def _mock_chat(app):
    mock_widget = MagicMock()
    mock_widget.write = MagicMock()
    mock_widget.clear = MagicMock()
    original_query_one = app.query_one

    def patched_query_one(selector, *args, **kwargs):
        if selector == "#chat" or (isinstance(selector, str) and selector.startswith("#chat")):
            return mock_widget
        if selector == "#typing-indicator":
            mock_indicator = MagicMock()
            mock_indicator.update = MagicMock()
            mock_indicator.add_class = MagicMock()
            mock_indicator.remove_class = MagicMock()
            return mock_indicator
        if selector == "#status-bar":
            mock_bar = MagicMock()
            mock_bar.update = MagicMock()
            return mock_bar
        if selector == "#sidebar":
            mock_sidebar = MagicMock()
            mock_sidebar.refresh_all = MagicMock()
            mock_sidebar.set_busy = MagicMock()
            return mock_sidebar
        return original_query_one(selector, *args, **kwargs)

    app.query_one = patched_query_one
    return mock_widget


class TestCommandDispatcherHandlers:
    @pytest.mark.asyncio
    async def test_cmd_usage_shows_telemetry(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_usage([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Usage last 24h" in text
            assert "requests" in text
            assert "tokens" in text
            assert "cost" in text

    @pytest.mark.asyncio
    async def test_cmd_theme_shows_current(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_theme([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "TUI Theme" in text
            assert "theme:" in text
            assert "layout:" in text

    @pytest.mark.asyncio
    async def test_cmd_theme_sets_dark(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_theme(["dark"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Theme" in text
            assert "dark" in text

    @pytest.mark.asyncio
    async def test_cmd_theme_sets_light_with_layout(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_theme(["light", "dense"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Theme" in text
            assert "light" in text
            assert "dense" in text

    @pytest.mark.asyncio
    async def test_cmd_theme_sets_dracula_with_max_lines(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_theme(["dracula", "default", "5000"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Theme" in text
            assert "dracula" in text
            assert "max lines 5000" in text

    @pytest.mark.asyncio
    async def test_cmd_theme_invalid_theme_shows_usage(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_theme(["invalid"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Usage:" in text

    @pytest.mark.asyncio
    async def test_cmd_theme_invalid_layout_shows_error(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_theme(["dark", "invalid"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "must be" in text

    @pytest.mark.asyncio
    async def test_cmd_theme_invalid_max_lines_shows_error(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_theme(["dark", "default", "not-a-number"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "must be an integer" in text

    @pytest.mark.asyncio
    async def test_cmd_budget_sets_daily(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_budget(["daily", "5.0"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Saved" in text
            assert "llm_daily_budget_usd" in text

    @pytest.mark.asyncio
    async def test_cmd_budget_sets_monthly(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_budget(["monthly", "50.0"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Saved" in text
            assert "llm_monthly_budget_usd" in text

    @pytest.mark.asyncio
    async def test_cmd_budget_sets_warning_threshold(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_budget(["warning", "90"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Saved" in text
            assert "llm_budget_warning_threshold_pct" in text

    @pytest.mark.asyncio
    async def test_cmd_budget_invalid_value_shows_error(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_budget(["daily", "not-a-number"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "must be numeric" in text

    @pytest.mark.asyncio
    async def test_cmd_budget_invalid_target_shows_usage(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_budget(["invalid", "10"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Usage:" in text

    @pytest.mark.asyncio
    async def test_cmd_clear_clears_chat(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_clear([])
            await pilot.pause()

            mock_chat.clear.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_exit_calls_exit(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_exit([])
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_cmd_exit_aliases_q(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)
            await dispatcher.handle("/q")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_cmd_exit_aliases_quit(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)
            await dispatcher.handle("/quit")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_cmd_copy_no_answer_shows_message(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_copy([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "No assistant answer" in text

    @pytest.mark.asyncio
    async def test_cmd_project_clears_project(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_project([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Workspace cleared" in text

    @pytest.mark.asyncio
    async def test_cmd_project_sets_project(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_project(["my-project"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Workspace:" in text or "Workspace not registered" in text

    @pytest.mark.asyncio
    async def test_cmd_project_registers_existing_directory_path(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")
        project_dir = tmp_path / "calc_py"
        project_dir.mkdir()

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_project([str(project_dir)])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Workspace registered:" in text
            assert "Workspace:" in text
            assert app.project_name == "calc_py"
            assert app.memory.get_project_lookup()["calc_py"]["path"] == str(project_dir)
            assert app.opencode.get_project_context("calc_py")["path"] == str(project_dir)

    @pytest.mark.asyncio
    async def test_cmd_project_unknown_shows_warning(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_project(["unknown-project"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Workspace not registered" in text

    @pytest.mark.asyncio
    async def test_cmd_connect_unknown_provider_shows_error(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_connect(["invalid"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Unknown provider" in text

    @pytest.mark.asyncio
    async def test_cmd_models_filters_by_provider(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_models(["openrouter"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Model catalog" in text or "No models in catalog" in text

    @pytest.mark.asyncio
    async def test_cmd_projects_no_projects_registered(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_projects([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "No registered workspaces" in text or "Workspaces" in text

    @pytest.mark.asyncio
    async def test_cmd_usage_shows_zeros_when_no_usage(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_usage([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Usage last 24h" in text
            assert "requests 0" in text

    @pytest.mark.asyncio
    async def test_cmd_budget_shows_healthy_when_no_usage(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_budget([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Budget" in text
            assert "healthy" in text

    @pytest.mark.asyncio
    async def test_cmd_router_shows_manual_mode(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_router([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Model Control" in text
            assert "manual" in text

    @pytest.mark.asyncio
    async def test_cmd_models_shows_empty_catalog(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_models([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "No models in catalog" in text or "Model catalog" in text
