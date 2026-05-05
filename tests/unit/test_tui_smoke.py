"""Smoke tests for the canonical Textual TUI surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import OptionList, RichLog, Static

from devsynapse.tui_input import EnhancedInput
from devsynapse.tui_preferences import load_tui_preferences
from devsynapse.tui_rendering import diff_stats, is_unified_diff, render_command_result
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
    monkeypatch.delenv("DEVSYNAPSE_TUI_CONFIG_FILE", raising=False)
    monkeypatch.delenv("DEVSYNAPSE_TUI_THEME", raising=False)
    monkeypatch.delenv("DEVSYNAPSE_TUI_LAYOUT", raising=False)


def test_tui_preferences_create_json_config_and_resolve_css_paths(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")
    config_file = tmp_path / "runtime" / "config" / "ui.json"
    monkeypatch.setenv("DEVSYNAPSE_TUI_CONFIG_FILE", str(config_file))

    preferences = load_tui_preferences()

    assert preferences.theme == "dark"
    assert preferences.layout == "default"
    assert config_file.is_file()
    assert json.loads(config_file.read_text(encoding="utf-8"))["theme"] == "dark"
    assert all(path.is_file() for path in preferences.css_paths)


def test_tui_preferences_accept_theme_and_layout_overrides(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")
    config_file = tmp_path / "runtime" / "config" / "ui.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text('{"theme": "light", "layout": "default"}\n', encoding="utf-8")
    monkeypatch.setenv("DEVSYNAPSE_TUI_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DEVSYNAPSE_TUI_THEME", "dracula")
    monkeypatch.setenv("DEVSYNAPSE_TUI_LAYOUT", "dense")

    preferences = load_tui_preferences()

    assert preferences.theme == "dracula"
    assert preferences.layout == "dense"
    assert preferences.palette["thinking"] == "#8be9fd"


def test_tui_diff_renderer_detects_and_summarizes_unified_diff():
    diff = "\n".join(
        [
            "diff --git a/app.py b/app.py",
            "index 1111111..2222222 100644",
            "--- a/app.py",
            "+++ b/app.py",
            "@@ -1,2 +1,3 @@",
            " import os",
            "-print('old')",
            "+print('new')",
            "+print('done')",
        ]
    )

    assert is_unified_diff(diff)
    stats = diff_stats(diff)
    assert stats.files == 1
    assert stats.hunks == 1
    assert stats.additions == 2
    assert stats.deletions == 1
    assert render_command_result(message="ok", output=diff) is not None


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
        header = app.query_one("#app-header", Static)
        footer = app.query_one("#app-footer", Static)
        content = str(status_bar.content)
        assert "DevSynapse AI" in content
        assert "ready" in content
        assert "budget:" in content
        assert "DevSynapse AI" in str(header.content)
        assert "/theme" in str(footer.content)


@pytest.mark.asyncio
async def test_tui_mounts_with_configured_theme_and_dense_layout(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    _configure_runtime(monkeypatch, runtime_root)
    config_file = runtime_root / "config" / "ui.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text('{"theme": "dracula", "layout": "dense"}\n', encoding="utf-8")
    monkeypatch.setenv("DEVSYNAPSE_TUI_CONFIG_FILE", str(config_file))

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(90, 26)) as pilot:
        await pilot.pause()

        assert app.ui_preferences.theme == "dracula"
        assert app.ui_preferences.layout == "dense"
        assert any(str(path).endswith("dracula.tcss") for path in app.CSS_PATH)
        assert any(str(path).endswith("dense.tcss") for path in app.CSS_PATH)
        app.query_one("#sidebar", DynamicSidebar)


@pytest.mark.asyncio
async def test_tui_theme_command_persists_preferences(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    _configure_runtime(monkeypatch, runtime_root)
    config_file = runtime_root / "config" / "ui.json"
    monkeypatch.setenv("DEVSYNAPSE_TUI_CONFIG_FILE", str(config_file))

    import config.settings as app_settings
    from devsynapse.commands import CommandDispatcher
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        dispatcher = CommandDispatcher(app)
        await dispatcher.cmd_theme(["light", "dense"])
        await pilot.pause()

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["theme"] == "light"
        assert saved["layout"] == "dense"
        assert app.ui_preferences.theme == "light"
        assert app.ui_preferences.layout == "dense"
        assert "light/dense" in str(app.query_one("#app-header", Static).content)


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
async def test_tui_command_palette_fills_selected_command(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.screens.command_palette import CommandPaletteScreen
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        await pilot.press("ctrl+p")
        await pilot.pause()

        palette = app.screen_stack[-1]
        assert isinstance(palette, CommandPaletteScreen)
        palette.query_one("#palette-search").value = "theme"
        palette._refresh("theme")
        palette.action_choose_highlighted()
        await pilot.pause()

        input_widget = app.query_one("#input", EnhancedInput)
        assert input_widget.value == "/theme "
        assert input_widget.has_focus


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

        input_widget.value = "/theme dr"
        app.refresh_command_suggestions(input_widget.value)
        assert app.accept_command_suggestion()
        assert input_widget.value == "/theme dracula "

        input_widget.value = "/theme dracula den"
        app.refresh_command_suggestions(input_widget.value)
        assert app.accept_command_suggestion()
        assert input_widget.value == "/theme dracula dense "


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
