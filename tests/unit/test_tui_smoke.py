"""Smoke tests for the canonical Textual TUI surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import OptionList, RichLog, Static

from devsynapse.tui_input import EnhancedInput
from devsynapse.tui_sidebar import DynamicSidebar


def _configure_runtime(monkeypatch: pytest.MonkeyPatch, runtime_root: Path) -> None:
    monkeypatch.setenv("DEVSYNAPSE_HOME", str(runtime_root))
    monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(runtime_root / "config" / ".env"))
    monkeypatch.setenv("DEVSYNAPSE_DATA_DIR", str(runtime_root / "data"))
    monkeypatch.setenv("DEVSYNAPSE_LOGS_DIR", str(runtime_root / "logs"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "")
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "")


@pytest.mark.asyncio
async def test_tui_mounts_and_handles_status_command(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.commands import CommandDispatcher
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        input_widget = app.query_one("#input", EnhancedInput)
        app.query_one("#chat", RichLog)
        sidebar = app.query_one("#sidebar", DynamicSidebar)

        assert app.memory is not None
        assert app.opencode is not None
        assert input_widget.has_focus
        assert "Telemetry" in str(sidebar.query_one("#sidebar-telemetry", Static).content)

        dispatcher = CommandDispatcher(app)
        await dispatcher.cmd_status([])
        await pilot.pause()

        status_bar = app.query_one("#status-bar", Static)
        content = str(status_bar.content)
        assert "DevSynapse AI" in content
        assert "ready" in content
        assert "budget:" in content


@pytest.mark.asyncio
async def test_tui_sidebar_renders_telemetry_snapshot(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(110, 34)) as pilot:
        await pilot.pause()

        sidebar = app.query_one("#sidebar", DynamicSidebar)
        sidebar.refresh_all(
            session_id="chat_test",
            project_name="devsynapse-ai",
            project_count=1,
            budget_status={
                "overall_status": "healthy",
                "daily": {
                    "level": "healthy",
                    "usage_pct": 25.0,
                    "actual_cost_usd": 0.0025,
                },
                "monthly": {
                    "level": "warning",
                    "usage_pct": 75.0,
                    "actual_cost_usd": 0.075,
                },
            },
            provider="openrouter",
            model="test/model",
            tokens=1200,
            cost=0.004,
            usage_stats={
                "totals": {
                    "request_count": 3,
                    "conversation_count": 2,
                    "total_tokens": 1200,
                    "cache_hit_rate_pct": 40.0,
                    "estimated_cost_usd": 0.004,
                }
            },
            telemetry_stats={
                "by_user_model": [
                    {
                        "provider": "openrouter",
                        "model": "test/model",
                        "request_count": 3,
                        "error_count": 1,
                        "avg_total_latency_ms": 850.0,
                    }
                ]
            },
            catalog_count=12,
        )
        await pilot.pause()

        text = str(sidebar.query_one("#sidebar-telemetry", Static).content)
        assert "Telemetry" in text
        assert "3" in text
        assert "1.2k" in text or "1200" in text


@pytest.mark.asyncio
async def test_tui_help_shortcut_works_before_slash_command(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.screens.help_screen import HelpScreen
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        assert app._dispatcher is None
        await pilot.press("ctrl+h")
        await pilot.pause()

        assert isinstance(app.screen_stack[-1], HelpScreen)
        assert app._dispatcher is not None


@pytest.mark.asyncio
async def test_tui_command_suggestions_complete_commands_and_arguments(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        input_widget = app.query_one("#input", EnhancedInput)
        menu = app.query_one("#command-suggestions", OptionList)

        input_widget.value = "/co"
        app.refresh_command_suggestions(input_widget.value)
        await pilot.pause()

        assert not menu.has_class("hidden")
        assert app.accept_command_suggestion()
        assert input_widget.value == "/connect "

        input_widget.value = "/connect o"
        app.refresh_command_suggestions(input_widget.value)
        assert app.accept_command_suggestion()
        assert input_widget.value == "/connect openrouter "

        input_widget.value = "/status"
        app.refresh_command_suggestions(input_widget.value)
        assert not app.accept_command_suggestion()
        assert menu.has_class("hidden")


@pytest.mark.asyncio
async def test_tui_enter_submits_chat_message(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        input_widget = app.query_one("#input", EnhancedInput)
        input_widget.value = "hello from enter"
        await pilot.press("enter")
        await pilot.pause()

        assert input_widget.value == ""
        assert input_widget._history[-1] == "hello from enter"


@pytest.mark.asyncio
async def test_tui_enter_submits_exact_slash_command_when_menu_is_open(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        input_widget = app.query_one("#input", EnhancedInput)
        menu = app.query_one("#command-suggestions", OptionList)
        input_widget.value = "/status"
        app.refresh_command_suggestions(input_widget.value)

        assert not menu.has_class("hidden")
        await pilot.press("enter")
        await pilot.pause()

        status_bar = app.query_one("#status-bar", Static)
        assert input_widget.value == ""
        assert menu.has_class("hidden")
        content = str(status_bar.content)
        assert "DevSynapse AI" in content or "ready" in content
