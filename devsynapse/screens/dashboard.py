"""Dashboard screen for DevSynapse AI metrics and analytics."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DashboardScreen(Screen):
    """Dashboard de métricas e analytics do DevSynapse AI."""

    CSS = """
    DashboardScreen {
        align: center middle;
    }

    #dashboard-container {
        width: 100;
        height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #dashboard-title {
        text-style: bold;
        color: $primary;
        content-align: center top;
        width: 100%;
        height: 3;
    }

    #metrics-grid {
        width: 100%;
        height: 1fr;
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        padding: 1 0;
    }

    .metric-card {
        border: round $primary;
        padding: 1;
    }

    .metric-title {
        text-style: bold;
        color: $primary;
    }

    .metric-value {
        text-style: bold;
        color: $success;
    }

    #button-row {
        width: 100%;
        height: 5;
        align: center middle;
    }

    #button-row Button {
        margin: 0 1;
        min-width: 15;
    }
    """

    BINDINGS = [
        ("escape", "close_dashboard", "Fechar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.usage_stats = {}
        self.budget_status = {}
        self.telemetry_stats = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="dashboard-container"):
            yield Label("📊 Dashboard de Métricas", id="dashboard-title")
            with Container(id="metrics-grid"):
                with Vertical(classes="metric-card"):
                    yield Label("Uso de Tokens (24h)", classes="metric-title")
                    yield Label("Carregando...", id="metric-tokens")
                with Vertical(classes="metric-card"):
                    yield Label("Custo Estimado (24h)", classes="metric-title")
                    yield Label("Carregando...", id="metric-custo")
                with Vertical(classes="metric-card"):
                    yield Label("Taxa de Cache", classes="metric-title")
                    yield Label("Carregando...", id="metric-cache")
                with Vertical(classes="metric-card"):
                    yield Label("Requisições (24h)", classes="metric-title")
                    yield Label("Carregando...", id="metric-requests")
                with Vertical(classes="metric-card"):
                    yield Label("Orçamento Diário", classes="metric-title")
                    yield Label("Carregando...", id="metric-budget-daily")
                with Vertical(classes="metric-card"):
                    yield Label("Orçamento Mensal", classes="metric-title")
                    yield Label("Carregando...", id="metric-budget-monthly")
            with Horizontal(id="button-row"):
                yield Button("Exportar Relatório", id="btn-export", variant="primary")
                yield Button("Fechar", id="btn-close", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._load_metrics()

    def _load_metrics(self) -> None:
        """Carrega métricas do sistema."""
        try:
            app = self.app
            if hasattr(app, "memory") and app.memory:
                self.usage_stats = app.memory.get_llm_usage_stats(hours=24)
                self.budget_status = app.memory.get_llm_budget_status()
                self.telemetry_stats = app.memory.get_llm_telemetry_stats(hours=24)

            self._update_metrics_display()
        except Exception as exc:
            logger.error(f"Erro ao carregar métricas: {exc}")

    def _update_metrics_display(self) -> None:
        """Atualiza a exibição das métricas."""
        try:
            totals = self.usage_stats.get("totals", {})

            tokens = totals.get("total_tokens", 0)
            self._update_label("metric-tokens", f"{tokens:,} tokens")

            cost = totals.get("estimated_cost_usd", 0.0)
            self._update_label("metric-custo", f"${cost:.4f}")

            cache_rate = totals.get("cache_hit_rate_pct", 0.0)
            self._update_label("metric-cache", f"{cache_rate:.1f}%")

            requests = totals.get("request_count", 0)
            self._update_label("metric-requests", f"{requests}")

            daily = self.budget_status.get("daily", {})
            daily_cost = daily.get("actual_cost_usd", 0.0)
            daily_budget = daily.get("budget_usd", 0.0)
            daily_pct = daily.get("usage_pct", 0.0)
            self._update_label(
                "metric-budget-daily",
                f"${daily_cost:.2f} / ${daily_budget:.2f} ({daily_pct:.0f}%)",
            )

            monthly = self.budget_status.get("monthly", {})
            monthly_cost = monthly.get("actual_cost_usd", 0.0)
            monthly_budget = monthly.get("budget_usd", 0.0)
            monthly_pct = monthly.get("usage_pct", 0.0)
            self._update_label(
                "metric-budget-monthly",
                f"${monthly_cost:.2f} / ${monthly_budget:.2f} ({monthly_pct:.0f}%)",
            )
        except Exception as exc:
            logger.error(f"Erro ao atualizar métricas: {exc}")

    def _update_label(self, label_id: str, value: str) -> None:
        """Atualiza um label com segurança."""
        try:
            label = self.query_one(f"#{label_id}", Label)
            label.update(value)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-close":
            self.dismiss()
        elif button_id == "btn-export":
            self._export_report()

    def _export_report(self) -> None:
        """Exporta relatório de métricas."""
        try:
            import json
            from datetime import datetime

            report = {
                "timestamp": datetime.now().isoformat(),
                "usage_stats": self.usage_stats,
                "budget_status": self.budget_status,
                "telemetry_stats": self.telemetry_stats,
            }

            report_json = json.dumps(report, indent=2, default=str)
            logger.info("Relatório exportado com sucesso")

            app = self.app
            if hasattr(app, "copy_to_clipboard"):
                app.copy_to_clipboard(report_json)

        except Exception as exc:
            logger.error(f"Erro ao exportar relatório: {exc}")

    def action_close_dashboard(self) -> None:
        self.dismiss()
