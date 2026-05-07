"""Dynamic sidebar for DevSynapse AI TUI - Reorganized for clarity."""
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
    """Dynamic sidebar with real-time updates.

    Panels:
    - Session: Chat ID, workspace, budget status
    - Model: Active model, last call details, session totals
    - Files: Git status, workspace
    - Telemetry: Usage by model, budget bars, health metrics
    - Actions: Quick commands reference
    """

    def __init__(
        self,
        *args,
        palette: dict[str, str] | None = None,
        collapsed_panels: dict[str, bool] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.palette = palette or {}
        self.session_id: str = "unknown"
        self.project_name: str | None = None
        self.last_provider: str | None = None
        self.last_model: str | None = None
        self.last_tokens: int = 0
        self.last_cost: float = 0.0
        self.is_busy: bool = False
        self.token_count: int = 0
        self.total_cost: float = 0.0
        self.request_count: int = 0
        self.usage_stats: dict[str, Any] = {}
        self.telemetry_stats: dict[str, Any] = {}
        self.budget_status: dict[str, Any] = {}
        self.file_changes: dict[str, Any] = {}
        self.project_count: int = 0
        self.catalog_count: int = 0
        self.intent_mode: str = "chat"  # chat, planning, build
        self._collapsed_panels: dict[str, bool] = {
            "telemetry": False,
            "model": False,
        }
        if collapsed_panels:
            for panel in self._collapsed_panels:
                self._collapsed_panels[panel] = bool(collapsed_panels.get(panel, False))

    def compose(self):
        yield Static(id="sidebar-session", classes="sidebar-panel")
        yield Static(id="sidebar-model", classes="sidebar-panel")
        yield Static(id="sidebar-files", classes="sidebar-panel")
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

    def collapsed_panels(self) -> dict[str, bool]:
        """Return persisted sidebar panel state."""
        return dict(self._collapsed_panels)

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
            workspace = _shorten_middle(self.project_name or "none", 20)
            budget_level = self._budget_level(
                budget_status if budget_status is not None else self.budget_status
            )

            status_text = "busy" if self.is_busy else "ready"
            status_color = self._color("executing" if self.is_busy else "success")

            # Mode indicator
            mode_icons = {
                "chat": "💬",
                "planning": "📋",
                "build": "🏗️",
            }
            mode_icon = mode_icons.get(self.intent_mode, "💬")

            panel = self.query_one("#sidebar-session", Static)
            panel.update(
                "\n".join(
                    [
                        f"{self._title('Session')} [{status_color}]{status_text}[/] {mode_icon}",
                        self._row("chat", _shorten_middle(short_id, 24)),
                        self._row("workspace", workspace),
                        self._row("scope", f"{provider_count} providers  {self.project_count} workspaces"),
                        self._row("budget", self._level_markup(budget_level)),
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
        last_tokens: int | None = None,
        last_cost: float | None = None,
    ) -> None:
        """Update model panel with clear separation of active vs last call."""
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
        if last_tokens is not None:
            self.last_tokens = last_tokens
        if last_cost is not None:
            self.last_cost = last_cost

        try:
            panel = self.query_one("#sidebar-model", Static)

            if self._collapsed_panels.get("model", True):
                settings = app_settings.get_settings()
                default_provider = (settings.llm_default_provider or "openrouter").strip().lower()
                active_model = _provider_model(settings, default_provider)
                panel.update(
                    f"{self._title('Model')} v {default_provider}:{_shorten_middle(active_model, 18)}  "
                    f"{self._muted('F2')}"
                )
                panel.add_class("collapsed")
                return

            panel.remove_class("collapsed")

            settings = app_settings.get_settings()
            default_provider = (settings.llm_default_provider or "openrouter").strip().lower()
            active_model = _provider_model(settings, default_provider)

            # Last call info
            last_used = (
                f"{_shorten_middle(self.last_model, 28)}"
                if self.last_model
                else "none"
            )
            last_tokens_str = f"{self.last_tokens:,}" if self.last_tokens else "0"
            last_cost_str = f"${self.last_cost:.4f}" if self.last_cost else "$0.0000"

            # Session totals
            token_str = f"{self.token_count:,}" if self.token_count else "0"
            cost_str = f"${self.total_cost:.4f}" if self.total_cost else "$0.0000"

            panel.update(
                "\n".join(
                    [
                        f"{self._title('Model')} {self._muted('manual')}",
                        self._row("active", default_provider),
                        f"[bold]{_shorten_middle(active_model, 32)}[/]",
                        "",
                        f"{self._title('Last Call')}",
                        self._row("model", last_used),
                        self._row("tokens", f"{self._metric(last_tokens_str)} tok"),
                        self._row("cost", self._metric(last_cost_str)),
                        "",
                        f"{self._title('Session')}",
                        self._row("calls", f"{self._metric(str(self.request_count))} req"),
                        self._row("tokens", f"{self._metric(token_str)} tok"),
                        self._row("cost", self._metric(cost_str)),
                        "",
                        self._row("catalog", f"{self.catalog_count} models  F2 /model"),
                    ]
                )
            )
        except Exception as e:
            logger.exception("Could not update model panel: %s", e)

    def update_files(self, file_changes: dict[str, Any] | None = None) -> None:
        """Update file changes panel."""
        if file_changes is not None:
            self.file_changes = file_changes
        try:
            panel = self.query_one("#sidebar-files", Static)
            state = str(self.file_changes.get("state") or "unknown")
            if state == "clean":
                panel.update(
                    "\n".join(
                        [
                            f"{self._title('Files')} [{self._color('success')}]clean[/]",
                            self._row("worktree", "no local changes"),
                            self._row("workspace", _shorten_middle(self.project_name or "none", 22)),
                        ]
                    )
                )
                return
            if state == "dirty":
                modified = int(self.file_changes.get("modified") or 0)
                added = int(self.file_changes.get("added") or 0)
                deleted = int(self.file_changes.get("deleted") or 0)
                untracked = int(self.file_changes.get("untracked") or 0)
                total = int(self.file_changes.get("total") or 0)
                panel.update(
                    "\n".join(
                        [
                            f"{self._title('Files')} [{self._color('warning')}]{total} changed[/]",
                            self._row("changed", f"M {modified}  A {added}  D {deleted}"),
                            self._row("untracked", str(untracked)),
                            self._row("hint", "!git diff"),
                        ]
                    )
                )
                return
            if state == "not_git":
                panel.update(
                    "\n".join(
                        [
                            f"{self._title('Files')} {self._muted('not a git repo')}",
                            self._row("workspace", _shorten_middle(self.project_name or "none", 22)),
                        ]
                    )
                )
                return
            panel.update(
                "\n".join(
                    [
                        f"{self._title('Files')} {self._muted('idle')}",
                        self._row("workspace", self.file_changes.get("message") or "select workspace"),
                    ]
                )
            )
        except Exception as e:
            logger.exception("Could not update file changes panel: %s", e)

    def update_telemetry(
        self,
        usage_stats: dict[str, Any] | None = None,
        telemetry_stats: dict[str, Any] | None = None,
        budget_status: dict[str, Any] | None = None,
    ) -> None:
        """Update telemetry panel with clear breakdown by model."""
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
                    f"{self._title('Telemetry')} v {self._muted('24h')} "
                    f"{self._metric(str(requests))} req  "
                    f"{self._metric(_compact_number(tokens))} tok  "
                    f"{self._metric(_money(cost))}  {self._muted('day')} {self._budget_bar(daily)}"
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

            # Build model breakdown section
            model_lines = []
            if rows:
                model_lines.append(f"{self._title('By Model')}")
                # Show top 3 models
                for row in rows[:3]:
                    provider = row.get("provider") or "?"
                    model = row.get("model") or "?"
                    label = f"{provider}:{_shorten_middle(model, 15)}"
                    count = int(row.get("request_count") or 0)
                    row_cost = float(row.get("estimated_cost_usd") or 0.0)
                    model_lines.append(
                        self._row(
                            "",
                            f"{label}  {self._metric(str(count))} req  {self._metric(_money(row_cost))}",
                        )
                    )
            else:
                model_lines.append(self._row("top model", "none yet"))

            panel.update(
                "\n".join(
                    [
                        f"{self._title('Telemetry')} {self._muted('24h')}",
                        "",
                        f"{self._title('Usage')}",
                        self._row(
                            "requests",
                            f"{self._metric(str(requests))} req  "
                            f"{self._metric(str(conversations))} chats  "
                            f"{self._metric(_compact_number(tokens))} tok",
                        ),
                        self._row("cost", f"{self._metric(_money(cost))}  cache {_pct(cache_hit)}"),
                        "",
                        f"{self._title('Health')}",
                        self._row("", f"{self._error_markup(error_pct)} errors  lat {_latency(latency_ms)}"),
                        "",
                        *model_lines,
                        "",
                        f"{self._title('Budget')}",
                        self._row("day", self._budget_bar(daily)),
                        self._row("month", self._budget_bar(monthly)),
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
                        self._title("Actions"),
                        f"{self._muted('^p')} palette  {self._muted('F2')} model",
                        f"{self._muted('F4')} model panel  {self._muted('F5')} telemetry",
                        f"{self._muted('F3')} copy     {self._muted('^r')} refresh",
                        f"{self._muted('^n')} new      {self._muted('^l')} clear",
                        "",
                        f"{self._muted('/')} menu  {self._muted('/theme')} theme",
                        f"{self._muted('/usage')} telemetry  {self._muted('!cmd')} shell",
                        "",
                        self._muted(f"updated {now}"),
                    ]
                )
            )
        except Exception as e:
            logger.exception("Could not update commands panel: %s", e)

    def set_busy(self, busy: bool) -> None:
        """Set busy status."""
        self.is_busy = busy
        self.update_session()

    def set_intent_mode(self, mode: str) -> None:
        """Set current intent mode (chat, planning, build)."""
        self.intent_mode = mode
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
        file_changes: dict[str, Any] | None = None,
        last_tokens: int | None = None,
        last_cost: float | None = None,
    ) -> None:
        """Refresh all panels."""
        self.update_session(session_id, project_name, project_count, budget_status)
        self.update_model(
            provider, model, tokens=tokens, cost=cost, catalog_count=catalog_count,
            last_tokens=last_tokens, last_cost=last_cost,
        )
        self.update_files(file_changes)
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

    def _level_markup(self, level: str) -> str:
        if level == "critical":
            return f"[{self._color('error')}]critical[/]"
        if level == "warning":
            return f"[{self._color('warning')}]warning[/]"
        if level == "healthy":
            return f"[{self._color('success')}]healthy[/]"
        if level == "disabled":
            return self._muted("disabled")
        return self._muted("unknown")

    def _error_markup(self, error_pct: float) -> str:
        if error_pct >= 10:
            return f"[{self._color('error')}]{error_pct:.1f}%[/]"
        if error_pct > 0:
            return f"[{self._color('warning')}]{error_pct:.1f}%[/]"
        return f"[{self._color('success')}]0.0%[/]"

    def _budget_bar(self, item: dict[str, Any]) -> str:
        pct = float(item.get("usage_pct") or 0.0)
        level = str(item.get("level") or "unknown")
        return f"{_bar(pct)} {self._level_markup(level)} {_money(item.get('actual_cost_usd'))}"

    def _top_model_line(self, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return self._row("top model", "none yet")
        row = rows[0]
        label = f"{row.get('provider') or '?'}:{row.get('model') or '?'}"
        count = int(row.get("request_count") or 0)
        return self._row("top", f"{_shorten_middle(label, 27)} {self._metric(str(count))} req")

    def _title(self, text: str) -> str:
        return f"[bold {self._color('title')}]{text}[/]"

    def _row(self, label: str, value: str) -> str:
        return f"{self._muted(label)} {value}"

    def _muted(self, text: str) -> str:
        return f"[{self._color('muted')}]{text}[/]"

    def _metric(self, text: str) -> str:
        return f"[{self._color('metric')}]{text}[/]"

    def _color(self, name: str) -> str:
        fallbacks = {
            "title": "thinking",
            "metric": "streaming",
            "muted": "muted",
        }
        key = name if name in self.palette else fallbacks.get(name, name)
        return self.palette.get(key, "#58a6ff")


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
