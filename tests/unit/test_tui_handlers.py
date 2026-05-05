"""
Tests for TUI slash command handlers and pure helper functions.

Pure helpers are tested directly without Textual infrastructure.
Handler logic is tested via Textual's run_test() with a mocked chat widget.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devsynapse.command_catalog import build_command_suggestions, slash_command_help_lines
from devsynapse.commands import (
    OPENROUTER_CURATED_FREE_MODELS,
    CommandDispatcher,
    _format_money,
    _is_free_model,
    _mask_secret,
    _model_option_label,
)
from devsynapse.screens import ModelSelectionScreen, ProviderConnectionScreen
from devsynapse.tui import DevSynapseTUI


class TestPureHelpers:
    """Tests for pure helper functions that have no Textual dependency."""

    def test_mask_secret_none(self):
        assert _mask_secret(None) == "not set"

    def test_mask_secret_empty(self):
        assert _mask_secret("") == "not set"

    def test_mask_secret_short(self):
        assert _mask_secret("short") == "set"

    def test_mask_secret_long(self):
        result = _mask_secret("abcdefghij1234567890")
        assert result.startswith("abcd")
        assert result.endswith("7890")
        assert "..." in result

    def test_format_money_valid(self):
        assert _format_money(10) == "$10.000000"
        assert _format_money(0.5) == "$0.500000"
        assert _format_money("3.14") == "$3.140000"

    def test_format_money_invalid(self):
        assert _format_money(None) == "$0.000000"
        assert _format_money("not a number") == "$0.000000"
        assert _format_money([]) == "$0.000000"

    def test_f2_binding_opens_model_picker(self):
        tui = DevSynapseTUI()
        bindings = {binding.key: binding.action for binding in tui.BINDINGS}
        assert bindings["f2"] == "open_model_picker"

    def test_free_model_helpers(self):
        model = OPENROUTER_CURATED_FREE_MODELS[0]
        assert _is_free_model(model)
        assert "free" in _model_option_label(model)
        assert "tools" in _model_option_label(model)

    def test_command_catalog_suggests_provider_arguments(self):
        suggestions = build_command_suggestions("/connect o")
        values = [suggestion.value for suggestion in suggestions]
        assert "/connect openrouter " in values
        assert "/connect opencode-go " in values

    def test_command_help_uses_catalog(self):
        lines = slash_command_help_lines()
        text = " ".join(lines)
        assert "/connect <provider>" in text
        assert "/providers" in text
        assert "/details" in text


def _configure_runtime(monkeypatch: pytest.MonkeyPatch, runtime_root: Path) -> None:
    """Set up isolated runtime environment for TUI tests."""
    monkeypatch.setenv("DEVSYNAPSE_HOME", str(runtime_root))
    monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(runtime_root / "config" / ".env"))
    monkeypatch.setenv("DEVSYNAPSE_DATA_DIR", str(runtime_root / "data"))
    monkeypatch.setenv("DEVSYNAPSE_LOGS_DIR", str(runtime_root / "logs"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "")
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "")


def _mock_chat(app):
    """Patch query_one to return a mock chat widget for the given app."""
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


class TestSlashCommandParsing:
    """Tests for slash command parsing and routing."""

    @pytest.mark.asyncio
    async def test_unknown_command_shows_error(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.handle("/unknown")
            await pilot.pause()

            mock_chat.write.assert_called()
            call_arg = mock_chat.write.call_args[0][0]
            assert "Unknown command" in call_arg

    @pytest.mark.asyncio
    async def test_invalid_shlex_shows_error(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.handle('/connect "unclosed quote')
            await pilot.pause()

            mock_chat.write.assert_called()
            call_arg = mock_chat.write.call_args[0][0]
            assert "Invalid command" in call_arg

    @pytest.mark.asyncio
    async def test_empty_command_shows_unknown(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.handle("/")
            await pilot.pause()

            mock_chat.write.assert_called()
            call_arg = mock_chat.write.call_args[0][0]
            assert "Unknown command" in call_arg


class TestSlashCommandHandlers:
    """Tests for individual slash command handlers."""

    @pytest.mark.asyncio
    async def test_help_shows_commands(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_help([])
            await pilot.pause()

            assert len(app.screen_stack) > 1
            from devsynapse.screens.help_screen import HelpScreen
            top_screen = app.screen_stack[-1]
            assert isinstance(top_screen, HelpScreen)

    @pytest.mark.asyncio
    async def test_status_shows_session_info(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_status([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "conversation:" in text

    @pytest.mark.asyncio
    async def test_providers_shows_key_status(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_providers([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "not set" in text or "set" in text

    @pytest.mark.asyncio
    async def test_new_clears_chat(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_new([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "New conversation" in text
            mock_chat.clear.assert_called()

    @pytest.mark.asyncio
    async def test_details_toggles(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_details([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "on" in text

            await dispatcher.cmd_details([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "off" in text

    @pytest.mark.asyncio
    async def test_budget_shows_usage(self, tmp_path, monkeypatch):
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
            assert "Budget" in text or "budget" in text

    @pytest.mark.asyncio
    async def test_router_shows_status(self, tmp_path, monkeypatch):
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
    async def test_router_args_explain_manual_control(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_router(["on"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Automatic routing has been removed" in text
            assert "/model" in text

    @pytest.mark.asyncio
    async def test_projects_shows_list(self, tmp_path, monkeypatch):
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
            assert "Projects" in text or "projects" in text

    @pytest.mark.asyncio
    async def test_connect_without_args_opens_provider_setup(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_connect([])
            await pilot.pause()

            assert isinstance(app.screen, ProviderConnectionScreen)
            app.screen.dismiss(None)
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_connect_with_args_saves_provider_and_default(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_connect(["openrouter", "sk-test", "openrouter/auto"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Saved" in text
            assert os.environ["OPENROUTER_API_KEY"] == "sk-test"
            assert os.environ["LLM_DEFAULT_PROVIDER"] == "openrouter"
            assert os.environ["OPENROUTER_MODEL"] == "openrouter/auto"

    @pytest.mark.asyncio
    async def test_model_command_opens_searchable_model_picker(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(120, 35)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_model(["openrouter"])
            await pilot.pause()

            assert isinstance(app.screen, ModelSelectionScreen)
            assert app.screen.query_one("#model-search") is not None
            app.screen.dismiss(None)
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_process_renders_streamed_response_once(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            input_widget = MagicMock()

            async def fake_process_message(**kwargs):
                on_token = kwargs["on_token"]
                for chunk in ["O", "lá", "\\n", "mundo"]:
                    on_token(chunk)
                return "Olá\nmundo", None, {"provider": "openrouter", "model": "test/model"}

            app.brain = MagicMock()
            app.brain.process_message = fake_process_message

            await app._process("oi", mock_chat, input_widget)
            await pilot.pause()

            writes = [call.args[0] for call in mock_chat.write.call_args_list]
            assert "O" not in writes
            assert "lá" not in writes
            assert app.last_response_text == "Olá\nmundo"
            assert any(getattr(write, "title", None) == "DevSynapse" for write in writes)

    @pytest.mark.asyncio
    async def test_copy_copies_last_response(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            copied = []
            app.copy_to_clipboard = copied.append
            app.last_response_text = "resposta final"

            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_copy([])
            await pilot.pause()

            assert copied == ["resposta final"]
            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            assert any("Copied" in str(call) for call in calls)
