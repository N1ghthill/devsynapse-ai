"""Smoke tests for the canonical Textual TUI surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input, Static


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
    from devsynapse.tui import DevSynapseTUI

    app_settings.get_settings.cache_clear()

    app = DevSynapseTUI()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        input_widget = app.query_one("#input", Input)
        session_panel = app.query_one("#session-panel", Static)
        providers_panel = app.query_one("#providers-panel", Static)

        assert app.memory is not None
        assert app.opencode is not None
        assert input_widget.has_focus
        assert "Session" in str(session_panel.content)
        assert "Providers" in str(providers_panel.content)

        await app._handle_slash_command("/status")
        await pilot.pause()

        status_bar = app.query_one("#bar", Static)
        assert "providers:0" in str(status_bar.content)
        assert "conversation:" in str(status_bar.content)
