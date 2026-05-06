"""Smoke tests for the canonical Textual TUI surface."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from textual.widgets import OptionList, RichLog, Static

from devsynapse.tui_input import EnhancedInput
from devsynapse.tui_preferences import load_tui_preferences
from devsynapse.tui_rendering import (
    diff_stats,
    is_unified_diff,
    progress_summary,
    render_command_result,
    render_progress_bar,
    render_structured_tree,
    structured_output_lexer,
    tabular_output_rows,
)
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
    assert preferences.chat_max_lines == 2000
    assert preferences.sidebar_collapsed == {"model": False, "telemetry": False}
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
    monkeypatch.setenv("DEVSYNAPSE_TUI_MAX_LINES", "500")

    preferences = load_tui_preferences()

    assert preferences.theme == "dracula"
    assert preferences.layout == "dense"
    assert preferences.chat_max_lines == 500
    assert preferences.palette["thinking"] == "#8be9fd"


def test_tui_themes_define_high_contrast_focus_states():
    theme_dir = Path("devsynapse/styles/themes")

    for theme_name in ("dark", "light", "dracula"):
        content = (theme_dir / f"{theme_name}.tcss").read_text(encoding="utf-8")
        assert "#chat:focus" in content
        assert "#command-suggestions:focus" in content
        assert "#palette-results:focus" in content


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


def test_tui_renderer_detects_json_and_yaml_outputs():
    json_result = structured_output_lexer('{"ok": true, "items": [1, 2]}')
    yaml_result = structured_output_lexer("name: devsynapse\nstatus: ready\n")

    assert json_result is not None
    assert json_result[0] == "json"
    assert '"ok": true' in json_result[1]
    assert yaml_result == ("yaml", "name: devsynapse\nstatus: ready")
    assert render_command_result(message="ok", output='{"status": "ready"}') is not None


def test_tui_renderer_builds_tree_for_json_objects_and_arrays():
    tree = render_structured_tree(
        '{"project": {"name": "devsynapse", "checks": ["lint", "test"]}, "ok": true}'
    )

    assert tree is not None
    assert "JSON" in str(tree.label)
    assert render_structured_tree('"plain scalar"') is None
    assert render_command_result(message="ok", output='{"items": [{"name": "api"}]}') is not None


def test_tui_renderer_detects_explicit_progress_output():
    progress = progress_summary("starting\nprogress: 3/10 files\n")

    assert progress is not None
    assert progress.percent == 30.0
    assert progress_summary("copying\nprogress: 42%\n").percent == 42.0
    assert progress_summary("loaded 3/10 files\n") is None
    assert render_progress_bar(progress) is not None
    assert render_command_result(message="ok", output="progress: 3/10 files\n") is not None


def test_tui_renderer_detects_csv_and_tsv_table_outputs():
    csv_output = "name,status\napi,ready\nworker,queued\n"
    tsv_output = "name\tstatus\napi\tready\nworker\tqueued\n"

    assert tabular_output_rows(csv_output) == [
        ["name", "status"],
        ["api", "ready"],
        ["worker", "queued"],
    ]
    assert tabular_output_rows(tsv_output) == [
        ["name", "status"],
        ["api", "ready"],
        ["worker", "queued"],
    ]
    assert tabular_output_rows("hello, world\n") is None
    assert render_command_result(message="ok", output=csv_output) is not None


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
        chat = app.query_one("#chat", RichLog)
        assert chat.max_lines == 2000
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
        assert "approval:trusted-auto" in content
        assert "tok:0" in content
        assert "cost:$0.0000" in content
        assert "cwd:" in content
        assert "session:" in content
        assert "DevSynapse AI" in str(header.content)
        assert "/theme" in str(footer.content)
        assert "^k/^j" in str(footer.content)
        assert "PgUp/PgDn" in str(footer.content)


@pytest.mark.asyncio
async def test_tui_mounts_with_configured_theme_and_dense_layout(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    _configure_runtime(monkeypatch, runtime_root)
    config_file = runtime_root / "config" / "ui.json"
    monkeypatch.setenv("DEVSYNAPSE_TUI_CONFIG_FILE", str(config_file))
    config_file.parent.mkdir(parents=True)
    config_file.write_text(
        (
            '{"theme": "dracula", "layout": "dense", '
            '"sidebar": {"collapsed_panels": {"model": true}}}\n'
        ),
        encoding="utf-8",
    )

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(90, 26)) as pilot:
        await pilot.pause()

        assert app.ui_preferences.theme == "dracula"
        assert app.ui_preferences.layout == "dense"
        assert app.ui_preferences.sidebar_collapsed["model"] is True
        assert any(str(path).endswith("dracula.tcss") for path in app.CSS_PATH)
        assert any(str(path).endswith("dense.tcss") for path in app.CSS_PATH)
        sidebar = app.query_one("#sidebar", DynamicSidebar)
        assert sidebar.query_one("#sidebar-model", Static).has_class("collapsed")


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
        assert saved["chat"]["max_lines"] == 2000
        assert app.ui_preferences.theme == "light"
        assert app.ui_preferences.layout == "dense"
        assert "light/dense" in str(app.query_one("#app-header", Static).content)
        await dispatcher.cmd_theme(["dracula", "default", "5000"])
        await pilot.pause()

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["theme"] == "dracula"
        assert saved["layout"] == "default"
        assert saved["chat"]["max_lines"] == 5000
        assert app.ui_preferences.chat_max_lines == 5000
        assert app.query_one("#chat", RichLog).max_lines == 5000


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
            file_changes={
                "state": "dirty",
                "total": 3,
                "modified": 1,
                "added": 1,
                "deleted": 0,
                "untracked": 1,
            },
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
        files_text = str(sidebar.query_one("#sidebar-files", Static).content)
        assert "Telemetry" in text
        assert "3" in text
        assert "1.2k" in text or "1200" in text
        assert "Files" in files_text
        assert "3 changed" in files_text


def test_tui_project_file_changes_reads_git_status(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    from devsynapse.tui import DevSynapseTUI

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("print('ready')\n", encoding="utf-8")

    app = DevSynapseTUI()
    app.project_name = "sample"
    changes = app._project_file_changes({"sample": {"path": str(repo)}})

    assert changes["state"] == "dirty"
    assert changes["untracked"] == 1


@pytest.mark.asyncio
async def test_tui_sidebar_panels_toggle_with_shortcuts(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    _configure_runtime(monkeypatch, runtime_root)
    config_file = runtime_root / "config" / "ui.json"
    monkeypatch.setenv("DEVSYNAPSE_TUI_CONFIG_FILE", str(config_file))

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(110, 34)) as pilot:
        await pilot.pause()

        sidebar = app.query_one("#sidebar", DynamicSidebar)
        model_panel = sidebar.query_one("#sidebar-model", Static)
        telemetry_panel = sidebar.query_one("#sidebar-telemetry", Static)

        assert not model_panel.has_class("collapsed")
        assert not telemetry_panel.has_class("collapsed")

        await pilot.press("f4")
        await pilot.press("f5")
        await pilot.pause()

        assert model_panel.has_class("collapsed")
        assert telemetry_panel.has_class("collapsed")
        assert "F4" in str(app.query_one("#app-footer", Static).content)
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["sidebar"]["collapsed_panels"] == {
            "model": True,
            "telemetry": True,
        }


@pytest.mark.asyncio
async def test_tui_busy_indicator_animates(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        indicator = app.query_one("#typing-indicator", Static)
        app._set_busy(True, "Executing shell command")
        app._busy_started_at = app._busy_started_at - 2 if app._busy_started_at else None
        first = str(indicator.content)
        app._update_busy_indicator()
        second = str(indicator.content)
        status_bar = app.query_one("#status-bar", Static)
        status_content = str(status_bar.content)
        app._set_busy(False)

        assert "Executing shell command" in first
        assert "|" in second
        assert "s" in second
        assert "Executing shell command" in status_content
        assert first != second
        assert str(indicator.content) == ""


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
        shortcuts = app.screen_stack[-1].query_one("#shortcuts-content", Static)
        assert "Ctrl+K/J" in str(shortcuts.content)
        assert "PageUp/Down" in str(shortcuts.content)
        assert "close menu/modal" in str(shortcuts.content)
        await app.screen_stack[-1]._show_category("Mouse")
        commands = app.screen_stack[-1].query_one("#commands-content", Static)
        assert "Wheel" in str(commands.content)
        assert "Click input" in str(commands.content)


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

        input_widget.value = "/theme dracula dense 5"
        app.refresh_command_suggestions(input_widget.value)
        assert app.accept_command_suggestion()
        assert input_widget.value == "/theme dracula dense 5000 "

        input_widget.value = "/"
        app.refresh_command_suggestions(input_widget.value, force=True)
        assert not menu.has_class("hidden")
        app.action_dismiss_command_menu()
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
async def test_tui_input_supports_vim_style_history_shortcuts(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        input_widget = app.query_one("#input", EnhancedInput)
        input_widget.add_to_history("first task")
        input_widget.add_to_history("second task")

        await pilot.press("ctrl+k")
        await pilot.pause()
        assert input_widget.value == "second task"

        await pilot.press("ctrl+k")
        await pilot.pause()
        assert input_widget.value == "first task"

        await pilot.press("ctrl+j")
        await pilot.pause()
        assert input_widget.value == "second task"


@pytest.mark.asyncio
async def test_tui_chat_scroll_actions_are_available(tmp_path, monkeypatch):
    _configure_runtime(monkeypatch, tmp_path / "runtime")

    import config.settings as app_settings
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 18)) as pilot:
        await pilot.pause()

        chat = app.query_one("#chat", RichLog)
        for index in range(80):
            chat.write(f"line {index}")
        await pilot.pause()

        app.action_scroll_chat_top()
        app.action_scroll_chat_page_down()
        app.action_scroll_chat_page_up()
        app.action_scroll_chat_bottom()
        await pilot.pause()

        assert chat.max_scroll_y >= 0


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
