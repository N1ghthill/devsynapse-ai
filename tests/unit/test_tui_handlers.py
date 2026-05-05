"""
Tests for TUI slash command handlers and pure helper functions.

Pure helpers are tested directly without Textual infrastructure.
Handler logic is tested via Textual's run_test() with a mocked chat widget.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devsynapse.tui import (
    DevSynapseTUI,
    _format_money,
    _mask_secret,
)


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


class TestRouterUpdatesFromArgs:
    """Tests for the pure argument parser used by /router."""

    def _make_tui(self):
        """Create a minimal TUI instance for calling the method."""
        return DevSynapseTUI()

    def test_router_on(self):
        tui = self._make_tui()
        result = tui._router_updates_from_args(["on"])
        assert result == {"llm_model_routing_enabled": True}

    def test_router_off(self):
        tui = self._make_tui()
        result = tui._router_updates_from_args(["off"])
        assert result == {"llm_model_routing_enabled": False}

    def test_router_economy_on(self):
        tui = self._make_tui()
        result = tui._router_updates_from_args(["economy", "on"])
        assert result == {"llm_auto_economy_enabled": True}

    def test_router_economy_off(self):
        tui = self._make_tui()
        result = tui._router_updates_from_args(["economy", "off"])
        assert result == {"llm_auto_economy_enabled": False}

    def test_router_adaptive_on(self):
        tui = self._make_tui()
        result = tui._router_updates_from_args(["adaptive", "on"])
        assert result == {"llm_adaptive_routing_enabled": True}

    def test_router_adaptive_off(self):
        tui = self._make_tui()
        result = tui._router_updates_from_args(["adaptive", "off"])
        assert result == {"llm_adaptive_routing_enabled": False}

    def test_router_invalid_args_returns_none(self):
        tui = self._make_tui()
        assert tui._router_updates_from_args([]) is None
        assert tui._router_updates_from_args(["invalid"]) is None
        assert tui._router_updates_from_args(["economy"]) is None
        assert tui._router_updates_from_args(["economy", "invalid"]) is None
        assert tui._router_updates_from_args(["on", "extra"]) is None


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
            await app._handle_slash_command("/unknown")
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
            await app._handle_slash_command('/connect "unclosed quote')
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
            await app._handle_slash_command("/")
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
            mock_chat = _mock_chat(app)
            await app._handle_slash_command("/help")
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "/connect" in text
            assert "/status" in text
            assert "/budget" in text
            assert "/router" in text

    @pytest.mark.asyncio
    async def test_status_shows_session_info(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            await app._handle_slash_command("/status")
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
            await app._handle_slash_command("/providers")
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
            await app._handle_slash_command("/new")
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
            await app._handle_slash_command("/details")
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "on" in text

            await app._handle_slash_command("/details")
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
            await app._handle_slash_command("/budget")
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
            await app._handle_slash_command("/router")
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Routing" in text or "routing" in text

    @pytest.mark.asyncio
    async def test_router_on_updates_setting(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            await app._handle_slash_command("/router on")
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Routing" in text or "routing" in text

    @pytest.mark.asyncio
    async def test_projects_shows_list(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            await app._handle_slash_command("/projects")
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Projects" in text or "projects" in text

    @pytest.mark.asyncio
    async def test_connect_without_args_shows_usage(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            await app._handle_slash_command("/connect")
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "connect" in text.lower()
