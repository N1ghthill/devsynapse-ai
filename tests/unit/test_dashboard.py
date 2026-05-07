"""Tests for the dashboard screen."""
from __future__ import annotations

import pytest

from devsynapse.screens.dashboard import DashboardScreen


class TestDashboardScreen:
    def test_initial_state(self):
        screen = DashboardScreen()
        assert screen.usage_stats == {}
        assert screen.budget_status == {}
        assert screen.telemetry_stats == {}

    def test_css_is_defined(self):
        screen = DashboardScreen()
        assert screen.CSS is not None
        assert "#dashboard-container" in screen.CSS

    def test_bindings_defined(self):
        screen = DashboardScreen()
        binding_keys = [b[0] if isinstance(b, tuple) else b.key for b in screen.BINDINGS]
        assert "escape" in binding_keys

    def test_update_label_safe(self):
        screen = DashboardScreen()
        screen._update_label("nonexistent", "test")


class TestDashboardMetrics:
    def test_update_metrics_with_empty_data(self):
        screen = DashboardScreen()
        screen._update_metrics_display()

    def test_update_metrics_with_sample_data(self):
        screen = DashboardScreen()
        screen.usage_stats = {
            "totals": {
                "total_tokens": 10000,
                "estimated_cost_usd": 0.05,
                "cache_hit_rate_pct": 75.5,
                "request_count": 50,
            }
        }
        screen.budget_status = {
            "daily": {
                "actual_cost_usd": 0.05,
                "budget_usd": 1.0,
                "usage_pct": 5.0,
            },
            "monthly": {
                "actual_cost_usd": 1.5,
                "budget_usd": 20.0,
                "usage_pct": 7.5,
            },
        }
        screen._update_metrics_display()


class TestDashboardExport:
    def test_export_report(self):
        screen = DashboardScreen()
        screen.usage_stats = {"totals": {"total_tokens": 1000}}
        screen.budget_status = {"daily": {"actual_cost_usd": 0.05}}
        screen.telemetry_stats = {}

        screen._export_report()


class TestDashboardCommand:
    @pytest.mark.asyncio
    async def test_cmd_dashboard_opens_screen(self, tmp_path, monkeypatch):
        from devsynapse.commands import CommandDispatcher
        from devsynapse.tui import DevSynapseTUI

        monkeypatch.setenv("DEVSYNAPSE_HOME", str(tmp_path / "runtime"))
        monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(tmp_path / "runtime" / "config" / ".env"))
        monkeypatch.setenv("DEVSYNAPSE_DATA_DIR", str(tmp_path / "runtime" / "data"))
        monkeypatch.setenv("DEVSYNAPSE_LOGS_DIR", str(tmp_path / "runtime" / "logs"))

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_dashboard([])
            await pilot.pause()

            assert len(app.screen_stack) > 1
            from devsynapse.screens.dashboard import DashboardScreen
            assert isinstance(app.screen_stack[-1], DashboardScreen)

    @pytest.mark.asyncio
    async def test_cmd_export_without_args_shows_usage(self, tmp_path, monkeypatch):
        from unittest.mock import MagicMock

        from devsynapse.commands import CommandDispatcher
        from devsynapse.tui import DevSynapseTUI

        monkeypatch.setenv("DEVSYNAPSE_HOME", str(tmp_path / "runtime"))
        monkeypatch.setenv("DEVSYNAPSE_CONFIG_FILE", str(tmp_path / "runtime" / "config" / ".env"))
        monkeypatch.setenv("DEVSYNAPSE_DATA_DIR", str(tmp_path / "runtime" / "data"))
        monkeypatch.setenv("DEVSYNAPSE_LOGS_DIR", str(tmp_path / "runtime" / "logs"))

        import config.settings as app_settings
        app_settings.get_settings.cache_clear()

        app = DevSynapseTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            mock_chat = MagicMock()
            mock_chat.write = MagicMock()
            original_query_one = app.query_one

            def patched_query_one(selector, *args, **kwargs):
                if selector == "#chat" or (isinstance(selector, str) and selector.startswith("#chat")):
                    return mock_chat
                return original_query_one(selector, *args, **kwargs)

            app.query_one = patched_query_one
            dispatcher = CommandDispatcher(app)
            await dispatcher.cmd_export([])
            await pilot.pause()

            calls = [c[0][0] for c in mock_chat.write.call_args_list]
            text = " ".join(calls)
            assert "Export" in text
