"""Modal screens for DevSynapse AI TUI."""
from __future__ import annotations

from typing import Any

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    Select,
    Static,
)

from devsynapse.commands import (
    PROVIDER_CONFIGS,
    _model_option_label,
    _model_search_text,
    _normalize_provider,
    _sort_models_for_ui,
)


class ProviderConnectionScreen(ModalScreen[dict[str, str] | None]):
    """Modal setup form for provider credentials."""

    CSS = """
    ProviderConnectionScreen {
        align: center middle;
    }

    #connect-dialog {
        width: 72;
        max-width: 90%;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $panel;
    }

    #connect-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #connect-help {
        color: $text-muted;
        margin-top: 1;
    }

    #connect-error {
        color: $error;
        height: 1;
    }

    #connect-actions {
        height: 3;
        align-horizontal: right;
        margin-top: 1;
    }

    #connect-actions Button {
        margin-left: 1;
    }
    """

    def __init__(self, provider: str = "deepseek", model: str | None = None) -> None:
        super().__init__()
        normalized = _normalize_provider(provider) or "deepseek"
        self.initial_provider = normalized if normalized in PROVIDER_CONFIGS else "deepseek"
        self.initial_model = model or PROVIDER_CONFIGS[self.initial_provider]["default_model"]

    def compose(self) -> Any:
        options = [
            (config["label"], provider)
            for provider, config in PROVIDER_CONFIGS.items()
        ]
        with Vertical(id="connect-dialog"):
            yield Label("Provider setup", id="connect-title")
            yield Select(
                options,
                value=self.initial_provider,
                allow_blank=False,
                id="provider-select",
            )
            yield Input(
                placeholder="API key",
                password=True,
                id="provider-api-key",
            )
            yield Input(
                value=self.initial_model,
                placeholder="Model",
                id="provider-model",
            )
            yield Static(
                "The selected provider becomes the default route for new requests.",
                id="connect-help",
            )
            yield Static("", id="connect-error")
            with Horizontal(id="connect-actions"):
                yield Button("Cancel", id="connect-cancel")
                yield Button("Save", variant="primary", id="connect-save")

    async def on_mount(self) -> None:
        self.query_one("#provider-api-key", Input).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "provider-select":
            return
        provider = str(event.value)
        model_input = self.query_one("#provider-model", Input)
        current_defaults = {config["default_model"] for config in PROVIDER_CONFIGS.values()}
        if not model_input.value.strip() or model_input.value.strip() in current_defaults:
            model_input.value = PROVIDER_CONFIGS[provider]["default_model"]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-cancel":
            self.dismiss(None)
            return
        if event.button.id != "connect-save":
            return

        provider = str(self.query_one("#provider-select", Select).value)
        api_key = self.query_one("#provider-api-key", Input).value.strip()
        model = self.query_one("#provider-model", Input).value.strip()
        if not api_key:
            self.query_one("#connect-error", Static).update("API key is required.")
            return
        self.dismiss({"provider": provider, "api_key": api_key, "model": model})


class ModelSelectionScreen(ModalScreen[dict[str, str] | None]):
    """Modal model picker with search over the configured catalog."""

    CSS = """
    ModelSelectionScreen {
        align: center middle;
    }

    #model-dialog {
        width: 104;
        max-width: 95%;
        height: auto;
        padding: 1 2 2 2;
        border: round $primary;
        background: $panel;
    }

    #model-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #model-help {
        color: $text-muted;
        margin-top: 1;
        margin-bottom: 1;
    }

    #model-actions {
        height: 3;
        align-horizontal: right;
        margin-top: 1;
    }

    #model-actions Button {
        margin-left: 1;
    }

    #model-search {
        margin-bottom: 1;
    }

    #model-select {
        height: 8;
    }
    """

    def __init__(
        self,
        models: list[dict[str, Any]],
        selected_provider: str,
        selected_model: str,
    ) -> None:
        super().__init__()
        self.models = _sort_models_for_ui(models)
        self.selected_provider = selected_provider
        self.selected_model = selected_model

    def compose(self) -> Any:
        with Vertical(id="model-dialog"):
            yield Label("Select Model", id="model-title")
            yield Input(
                placeholder="Search provider, model, free, tools...",
                id="model-search",
            )
            yield Select(
                self._options(""),
                allow_blank=False,
                id="model-select",
            )
            yield Static("", id="model-help")
            with Horizontal(id="model-actions"):
                yield Button("Cancel", id="model-cancel")
                yield Button("Use Model", variant="primary", id="model-save")

    async def on_mount(self) -> None:
        self._refresh_options("")
        self.query_one("#model-search", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "model-search":
            self._refresh_options(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "model-cancel":
            self.dismiss(None)
            return
        if event.button.id != "model-save":
            return
        selected = str(self.query_one("#model-select", Select).value)
        provider, _, model_id = selected.partition(":")
        if provider and model_id:
            self.dismiss({"provider": provider, "model": model_id})

    def _options(self, query: str) -> list[tuple[str, str]]:
        terms = [term for term in query.lower().split() if term]
        matches = [
            model for model in self.models
            if all(term in _model_search_text(model) for term in terms)
        ]
        if not matches:
            matches = self.models
        return [
            (
                _model_option_label(model),
                f"{model['provider']}:{model['model_id']}",
            )
            for model in matches[:30]
        ]

    def _refresh_options(self, query: str) -> None:
        options = self._options(query)
        select = self.query_one("#model-select", Select)
        select.set_options(options)
        selected_value = f"{self.selected_provider}:{self.selected_model}"
        values = {value for _, value in options}
        select.value = selected_value if selected_value in values else options[0][1]
        total = len(self.models)
        shown = len(options)
        self.query_one("#model-help", Static).update(
            f"{shown}/{total} shown. Enter selects, Esc cancels. F2 opens this screen."
        )
