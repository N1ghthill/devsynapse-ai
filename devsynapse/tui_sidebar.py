"""Dynamic sidebar for DevSynapse AI TUI."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from textual.containers import Vertical
from textual.widgets import Static

import config.settings as app_settings
from devsynapse.commands import (
    PROVIDER_CONFIGS,
    _provider_key,
    _provider_model,
    _shorten_middle,
)

logger = logging.getLogger(__name__)


class DynamicSidebar(Vertical):
    """Dynamic sidebar with real-time updates."""

    DEFAULT_CSS = """
    DynamicSidebar {
        width: 40;
        min-width: 36;
        background: #0d1117;
        border-left: solid #30363d;
        padding: 1;
        overflow: hidden;
    }

    DynamicSidebar .sidebar-panel {
        width: 100%;
        margin-bottom: 1;
        padding: 1;
        border: tall #30363d;
        background: #161b22;
    }

    DynamicSidebar .sidebar-panel.collapsed {
        height: auto !important;
    }

    DynamicSidebar .sidebar-panel.collapsed > Static {
        display: none;
    }

    DynamicSidebar .sidebar-toggle {
        color: #8b949e;
        text-style: italic;
    }

    DynamicSidebar .sidebar-title {
        text-style: bold;
        color: #58a6ff;
    }

    DynamicSidebar #sidebar-session {
        height: 6;
    }

    DynamicSidebar #sidebar-model {
        height: 7;
    }

    DynamicSidebar #sidebar-telemetry {
        height: 10;
    }

    DynamicSidebar #sidebar-commands {
        height: auto;
    }

    DynamicSidebar .metric {
        color: #8b949e;
    }

    DynamicSidebar .metric-value {
        color: #58a6ff;
        text-style: bold;
    }

    DynamicSidebar .status-indicator {
        width: 1;
        text-align: center;
    }

    DynamicSidebar .status-ready {
        color: #3fb950;
    }

    DynamicSidebar .status-busy {
        color: #d29922;
    }

    DynamicSidebar .status-error {
        color: #f85149;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.session_id: str = "unknown"
        self.project_name: str | None = None
        self.last_provider: str | None = None
        self.last_model: str | None = None
        self.is_busy: bool = False
        self.token_count: int = 0
        self.total_cost: float = 0.0
        self.request_count: int = 0
        self.usage_stats: dict[str, Any] = {}
        self.telemetry_stats: dict[str, Any] = {}
        self.budget_status: dict[str, Any] = {}
        self.project_count: int = 0
        self.catalog_count: int = 0
        self._collapsed_panels: dict[str, bool] = {
            "telemetry": False,
            "model": False,
        }

    def compose(self):
        yield Static(id="sidebar-session", classes="sidebar-panel")
        yield Static(id="sidebar-model", classes="sidebar-panel")
        yield Static(id="sidebar-telemetry", classes="sidebar-panel")
        yield Static(id="sidebar-commands", classes="sidebar-panel")

    def toggle_panel(self, panel_name: str) -> None:
        """Toggle collapsed state of a panel."""
        if panel_name in self._collapsed_panels:
            self._collapsed_panels[panel_name] = not self._collapsed_panels[panel_name]
            panel_id = f"sidebar-{panel_name}"
            try:
                panel = self.query_one(f"#{panel_id}", Static)
                if self._collapsed_panels[panel_name]:
                    panel.add_class("collapsed")
                else:
                    panel.remove_class("collapsed")
            except Exception:
                pass

    def update_session(
        self,
        session_id: str | None = None,
        project_name: str | None = None,
        project_count: int | None = None,
        budget_status: dict[str, Any] | str | None = None,
    ) -> None:
        """Update session panel."""
        if session_id:
            self.session_id = session_id
        if project_name is not None:
            self.project_name = project_name
        if project_count is not None:
            self.project_count = project_count
        if isinstance(budget_status, dict):
            self.budget_status = budget_status

        try:
            settings = app_settings.get_settings()
            provider_count = sum(
                bool(_provider_key(settings, provider))
                for provider in PROVIDER_CONFIGS
            )

            short_id = self.session_id.removeprefix("chat_")
            project = _shorten_middle(self.project_name or "none", 20)
            budget_level = self._budget_level(
                budget_status if budget_status is not None else self.budget_status
            )

            status_text = "busy" if self.is_busy else "ready"
            status_class = "status-busy" if self.is_busy else "status-ready"

            panel = self.query_one("#sidebar-session", Static)
            panel.update(
                "\n".join(
                    [
                        "[bold #58a6ff]Session[/] "
                        f"[{status_class}]{status_text}[/]",
                        f"[dim]chat[/] {_shorten_middle(short_id, 24)}",
                        f"[dim]project[/] {project}",
                        f"[dim]providers[/] {provider_count}  "
                        f"[dim]projects[/] {self.project_count}",
                        f"[dim]budget[/] {self._level_markup(budget_level)}",
                    ]
                )
            )
        except Exception as e:
            logger.exception("Could not update session panel: %s", e)

    def update_model(
        self,
        provider: str | None = None,
        model: str | None = None,
        tokens: int | None = None,
        cost: float | None = None,
        catalog_count: int | None = None,
    ) -> None:
        """Update model panel."""
        if provider:
            self.last_provider = provider
        if model:
            self.last_model = model
        if tokens is not None:
            self.token_count = tokens
        if cost is not None:
            self.total_cost = cost
        if catalog_count is not None:
            self.catalog_count = catalog_count

        try:
            panel = self.query_one("#sidebar-model", Static)

            if self._collapsed_panels.get("model", True):
                settings = app_settings.get_settings()
                default_provider = (settings.llm_default_provider or "deepseek").strip().lower()
                active_model = _provider_model(settings, default_provider)
                panel.update(
                    f"[bold #58a6ff]Model[/] ▼ {default_provider}:{_shorten_middle(active_model, 18)}  [dim]F2[/]"
                )
                panel.add_class("collapsed")
                return

            panel.remove_class("collapsed")

            settings = app_settings.get_settings()
            default_provider = (settings.llm_default_provider or "deepseek").strip().lower()
            active_model = _provider_model(settings, default_provider)

            last_used = (
                f"{_shorten_middle(self.last_model, 28)}"
                if self.last_model
                else "none"
            )

            token_str = f"{self.token_count:,}" if self.token_count else "0"
            cost_str = f"${self.total_cost:.4f}" if self.total_cost else "$0.0000"

            panel.update(
                "\n".join(
                    [
                        "[bold #58a6ff]Model[/] [dim]manual[/]",
                        f"[dim]active[/] {default_provider}",
                        f"[bold]{_shorten_middle(active_model, 32)}[/]",
                        f"[dim]last[/] {last_used}",
                        f"[dim]session[/] [metric-value]{token_str}[/] tok  "
                        f"[metric-value]{cost_str}[/]",
                        f"[dim]catalog[/] {self.catalog_count}  [dim]F2 /model[/]",
                    ]
                )
            )
        except Exception as e:
            logger.exception("Could not update model panel: %s", e)

    def update_telemetry(
        self,
        usage_stats: dict[str, Any] | None = None,
        telemetry_stats: dict[str, Any] | None = None,
        budget_status: dict[str, Any] | None = None,
    ) -> None:
        """Update telemetry and budget panel."""
        if usage_stats is not None:
            self.usage_stats = usage_stats
        if telemetry_stats is not None:
            self.telemetry_stats = telemetry_stats
        if budget_status is not None:
            self.budget_status = budget_status

        try:
            panel = self.query_one("#sidebar-telemetry", Static)

            if self._collapsed_panels.get("telemetry", True):
                totals = self.usage_stats.get("totals", {})
                requests = int(totals.get("request_count") or 0)
                tokens = int(totals.get("total_tokens") or 0)
                cost = float(totals.get("estimated_cost_usd") or 0.0)
                daily = self.budget_status.get("daily", {})
                panel.update(
                    f"[bold #58a6ff]Telemetry[/] ▼ [dim]24h:[/] [metric-value]{requests}[/] req  "
                    f"[metric-value]{_compact_number(tokens)}[/] tok  "
                    f"[metric-value]{_money(cost)}[/]  [dim]day:[/] {self._budget_bar(daily)}"
                )
                panel.add_class("collapsed")
                return

            panel.remove_class("collapsed")

            totals = self.usage_stats.get("totals", {})
            rows = self.telemetry_stats.get("by_user_model", [])
            requests = int(totals.get("request_count") or 0)
            conversations = int(totals.get("conversation_count") or 0)
            tokens = int(totals.get("total_tokens") or 0)
            cache_hit = float(totals.get("cache_hit_rate_pct") or 0.0)
            cost = float(totals.get("estimated_cost_usd") or 0.0)

            total_requests = sum(int(row.get("request_count") or 0) for row in rows)
            total_errors = sum(int(row.get("error_count") or 0) for row in rows)
            error_pct = (total_errors / total_requests * 100.0) if total_requests else 0.0
            latency_ms = _weighted_average(rows, "avg_total_latency_ms", "request_count")

            daily = self.budget_status.get("daily", {})
            monthly = self.budget_status.get("monthly", {})

            panel.update(
                "\n".join(
                    [
                        "[bold #58a6ff]Telemetry[/] [dim]24h[/]",
                        f"[metric-value]{requests}[/] req  "
                        f"[metric-value]{conversations}[/] chats  "
                        f"[metric-value]{_compact_number(tokens)}[/] tok",
                        f"[dim]cost[/] [metric-value]{_money(cost)}[/]  "
                        f"[dim]cache[/] {_pct(cache_hit)}",
                        f"[dim]errors[/] {self._error_markup(error_pct)}  "
                        f"[dim]lat[/] {_latency(latency_ms)}",
                        f"[dim]day[/]   {self._budget_bar(daily)}",
                        f"[dim]month[/] {self._budget_bar(monthly)}",
                        self._top_model_line(rows),
                    ]
                )
            )
        except Exception as e:
            logger.exception("Could not update telemetry panel: %s", e)

    def update_commands(self) -> None:
        """Update commands panel."""
        try:
            panel = self.query_one("#sidebar-commands", Static)
            now = datetime.now().strftime("%H:%M:%S")
            panel.update(
                "\n".join(
                    [
                        "[bold #58a6ff]Actions[/]",
                        "[dim]F2[/] model    [dim]^p[/] providers",
                        "[dim]F3[/] copy     [dim]^r[/] refresh",
                        "[dim]^n[/] new      [dim]^l[/] clear",
                        "",
                        "[dim]/[/] menu  [dim]/usage[/] telemetry",
                        "[dim]/budget[/] limits  [dim]!cmd[/] shell",
                        "",
                        f"[dim]updated {now}[/]",
                    ]
                )
            )
        except Exception as e:
            logger.exception("Could not update commands panel: %s", e)

    def set_busy(self, busy: bool) -> None:
        """Set busy status."""
        self.is_busy = busy
        self.update_session()

    def refresh_all(
        self,
        session_id: str | None = None,
        project_name: str | None = None,
        project_count: int | None = None,
        budget_status: dict[str, Any] | str | None = None,
        provider: str | None = None,
        model: str | None = None,
        tokens: int | None = None,
        cost: float | None = None,
        usage_stats: dict[str, Any] | None = None,
        telemetry_stats: dict[str, Any] | None = None,
        catalog_count: int | None = None,
    ) -> None:
        """Refresh all panels."""
        self.update_session(session_id, project_name, project_count, budget_status)
        self.update_model(provider, model, tokens=tokens, cost=cost, catalog_count=catalog_count)
        self.update_telemetry(
            usage_stats=usage_stats,
            telemetry_stats=telemetry_stats,
            budget_status=budget_status if isinstance(budget_status, dict) else None,
        )
        self.update_commands()

    @staticmethod
    def _budget_level(budget_status: dict[str, Any] | str | None) -> str:
        if isinstance(budget_status, dict):
            return str(budget_status.get("overall_status") or "unknown")
        return str(budget_status or "unknown")

    @staticmethod
    def _level_markup(level: str) -> str:
        if level == "critical":
            return "[#f85149]critical[/]"
        if level == "warning":
            return "[#d29922]warning[/]"
        if level == "healthy":
            return "[#3fb950]healthy[/]"
        if level == "disabled":
            return "[dim]disabled[/]"
        return "[dim]unknown[/]"

    @staticmethod
    def _error_markup(error_pct: float) -> str:
        if error_pct >= 10:
            return f"[#f85149]{error_pct:.1f}%[/]"
        if error_pct > 0:
            return f"[#d29922]{error_pct:.1f}%[/]"
        return "[#3fb950]0.0%[/]"

    def _budget_bar(self, item: dict[str, Any]) -> str:
        pct = float(item.get("usage_pct") or 0.0)
        level = str(item.get("level") or "unknown")
        return f"{_bar(pct)} {self._level_markup(level)} {_money(item.get('actual_cost_usd'))}"

    @staticmethod
    def _top_model_line(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "[dim]top model[/] none yet"
        row = rows[0]
        label = f"{row.get('provider') or '?'}:{row.get('model') or '?'}"
        count = int(row.get("request_count") or 0)
        return f"[dim]top[/] {_shorten_middle(label, 27)} [metric-value]{count}[/] req"


def _compact_number(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def _money(value: object) -> str:
    try:
        amount = float(value or 0.0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"${amount:.4f}" if amount >= 0.01 else f"${amount:.6f}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _latency(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value >= 1000:
        return f"{value / 1000:.1f}s"
    return f"{value:.0f}ms"


def _bar(percent: float, width: int = 8) -> str:
    bounded = max(0.0, min(percent, 100.0))
    filled = int(round(width * bounded / 100.0))
    return "[" + ("#" * filled).ljust(width, "-") + f"] {bounded:5.1f}%"


def _weighted_average(
    rows: list[dict[str, Any]],
    value_key: str,
    weight_key: str,
) -> float | None:
    total_weight = 0
    weighted = 0.0
    for row in rows:
        value = row.get(value_key)
        if value is None:
            continue
        weight = int(row.get(weight_key) or 0)
        if weight <= 0:
            continue
        total_weight += weight
        weighted += float(value) * weight
    if total_weight <= 0:
        return None
    return weighted / total_weight
