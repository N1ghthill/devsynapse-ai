"""End-to-end tests for DevSynapse AI main user flows."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from devsynapse.commands import CommandDispatcher
from devsynapse.tui import DevSynapseTUI


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


class TestE2EFirstTimeSetup:
    """E2E test: First-time user setup flow."""

    @pytest.mark.asyncio
    async def test_first_time_user_can_check_status(self, tmp_path, monkeypatch):
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
            assert "Status" in text
            assert "conversation:" in text

    @pytest.mark.asyncio
    async def test_first_time_user_can_check_providers(self, tmp_path, monkeypatch):
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
            assert "Providers" in text
            assert "not set" in text

    @pytest.mark.asyncio
    async def test_first_time_user_can_set_provider(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)

            await dispatcher.cmd_connect(["openrouter", "sk-test-key-12345"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Saved" in text
            assert "OPENROUTER_API_KEY" in text


class TestE2EDevelopmentSession:
    """E2E test: Typical development session flow."""

    @pytest.mark.asyncio
    async def test_user_can_create_new_conversation(self, tmp_path, monkeypatch):
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

    @pytest.mark.asyncio
    async def test_user_can_clear_chat(self, tmp_path, monkeypatch):
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
    async def test_user_can_toggle_details(self, tmp_path, monkeypatch):
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
            assert "Details:" in text
            assert "on" in text


class TestE2EBudgetMonitoring:
    """E2E test: Budget monitoring flow."""

    @pytest.mark.asyncio
    async def test_user_can_check_budget(self, tmp_path, monkeypatch):
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
    async def test_user_can_set_daily_budget(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)

            await dispatcher.cmd_budget(["daily", "10.0"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Saved" in text
            assert "llm_daily_budget_usd" in text

    @pytest.mark.asyncio
    async def test_user_can_set_monthly_budget(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)

            await dispatcher.cmd_budget(["monthly", "100.0"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Saved" in text
            assert "llm_monthly_budget_usd" in text


class TestE2EThemeConfiguration:
    """E2E test: Theme configuration flow."""

    @pytest.mark.asyncio
    async def test_user_can_change_theme(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)

            await dispatcher.cmd_theme(["dracula"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Theme" in text
            assert "dracula" in text

    @pytest.mark.asyncio
    async def test_user_can_change_layout(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = _mock_chat(app)
            dispatcher = CommandDispatcher(app)

            await dispatcher.cmd_theme(["dark", "dense"])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Theme" in text
            assert "dense" in text


class TestE2EHelpAndNavigation:
    """E2E test: Help and navigation flow."""

    @pytest.mark.asyncio
    async def test_user_can_access_help(self, tmp_path, monkeypatch):
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
    async def test_user_can_exit_application(self, tmp_path, monkeypatch):
        _configure_runtime(monkeypatch, tmp_path / "runtime")

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)

            await dispatcher.cmd_exit([])
            await pilot.pause()
