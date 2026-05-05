"""
DevSynapse AI — Textual TUI (terminal chat interface).
"""

import asyncio
import importlib
import logging
import shlex
import sys
from pathlib import Path
from typing import Any

from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static

import config.settings as app_settings
from core.brain import DevSynapseBrain
from core.correlation import generate_conversation_id
from core.llm_discovery import fetch_openai_compatible_models, fetch_openrouter_models
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge
from core.plugin_system import plugin_manager
from core.runtime_config import ensure_runtime_config_file, set_runtime_config_values

logger = logging.getLogger(__name__)


PROVIDER_CONFIGS = {
    "deepseek": {
        "label": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "model_key": "DEEPSEEK_MODEL",
        "model_attr": "deepseek_model",
        "key_attr": "deepseek_api_key",
        "default_model": "deepseek-v4-pro",
    },
    "openrouter": {
        "label": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "model_key": "OPENROUTER_MODEL",
        "model_attr": "openrouter_model",
        "key_attr": "openrouter_api_key",
        "default_model": "openrouter/free",
    },
    "opencode-zen": {
        "label": "OpenCode Zen",
        "env_key": "OPENCODE_ZEN_API_KEY",
        "model_key": "OPENCODE_ZEN_MODEL",
        "model_attr": "opencode_zen_model",
        "key_attr": "opencode_zen_api_key",
        "default_model": "qwen3-coder",
    },
    "opencode-go": {
        "label": "OpenCode Go",
        "env_key": "OPENCODE_GO_API_KEY",
        "model_key": "OPENCODE_GO_MODEL",
        "model_attr": "opencode_go_model",
        "key_attr": "opencode_go_api_key",
        "default_model": "deepseek-v4-pro",
    },
}

OPENROUTER_CURATED_FREE_MODELS = [
    {
        "provider": "openrouter",
        "model_id": "openrouter/free",
        "name": "Free Models Router",
        "context_length": 200000,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "capabilities": {"supported_parameters": ["tools", "tool_choice"]},
    },
    {
        "provider": "openrouter",
        "model_id": "qwen/qwen3-coder:free",
        "name": "Qwen3 Coder 480B A35B (free)",
        "context_length": 262000,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "capabilities": {"supported_parameters": ["tools", "tool_choice"]},
    },
    {
        "provider": "openrouter",
        "model_id": "minimax/minimax-m2.5:free",
        "name": "MiniMax M2.5 (free)",
        "context_length": 196608,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "capabilities": {"supported_parameters": ["tools"]},
    },
    {
        "provider": "openrouter",
        "model_id": "openai/gpt-oss-120b:free",
        "name": "OpenAI gpt-oss-120b (free)",
        "context_length": 131072,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "capabilities": {"supported_parameters": ["tools", "tool_choice"]},
    },
    {
        "provider": "openrouter",
        "model_id": "nvidia/nemotron-3-super-120b-a12b:free",
        "name": "NVIDIA Nemotron 3 Super (free)",
        "context_length": 262144,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "capabilities": {"supported_parameters": ["tools", "tool_choice"]},
    },
    {
        "provider": "openrouter",
        "model_id": "z-ai/glm-4.5-air:free",
        "name": "Z.ai GLM 4.5 Air (free)",
        "context_length": 131072,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "capabilities": {"supported_parameters": ["tools", "tool_choice"]},
    },
]

PROVIDER_ALIASES = {
    "zen": "opencode-zen",
    "opencode": "opencode-zen",
    "go": "opencode-go",
}


def _normalize_provider(value: str | None) -> str | None:
    provider = (value or "").strip().lower()
    return PROVIDER_ALIASES.get(provider, provider) if provider else None


def _provider_config(provider: str | None) -> dict[str, str] | None:
    normalized = _normalize_provider(provider)
    return PROVIDER_CONFIGS.get(normalized or "")


def _provider_key(settings: Any, provider: str) -> str | None:
    config = PROVIDER_CONFIGS[provider]
    return getattr(settings, config["key_attr"])


def _provider_model(settings: Any, provider: str) -> str:
    config = PROVIDER_CONFIGS[provider]
    value = getattr(settings, config["model_attr"], "")
    return str(value or config["default_model"])


def _mask_secret(value: str | None) -> str:
    if not value:
        return "not set"
    if len(value) <= 8:
        return "set"
    return f"{value[:4]}...{value[-4:]}"


def _format_money(value: object) -> str:
    try:
        return f"${float(value):.6f}"
    except (TypeError, ValueError):
        return "$0.000000"


def _shorten_middle(value: str | None, limit: int = 32) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    side = max(4, (limit - 3) // 2)
    return f"{text[:side]}...{text[-side:]}"


def _is_free_model(model: dict[str, Any]) -> bool:
    try:
        input_cost = float(model.get("input_cost_per_token") or 0.0)
        output_cost = float(model.get("output_cost_per_token") or 0.0)
    except (TypeError, ValueError):
        input_cost = output_cost = 1.0
    model_id = str(model.get("model_id") or "")
    return (input_cost == 0.0 and output_cost == 0.0) or model_id.endswith(":free")


def _model_supports_tools(model: dict[str, Any]) -> bool:
    capabilities = model.get("capabilities") or {}
    params = capabilities.get("supported_parameters") or []
    return "tools" in params or "tool_choice" in params


def _model_cost_label(model: dict[str, Any]) -> str:
    if _is_free_model(model):
        return "free"
    input_cost = model.get("input_cost_per_token")
    output_cost = model.get("output_cost_per_token")
    if input_cost is None or output_cost is None:
        return "cost unknown"
    return f"${float(input_cost) * 1_000_000:.3f}/M in ${float(output_cost) * 1_000_000:.3f}/M out"


def _model_option_label(model: dict[str, Any]) -> str:
    provider = model.get("provider") or "?"
    model_id = model.get("model_id") or "?"
    name = model.get("name") or model_id
    tools = " tools" if _model_supports_tools(model) else ""
    context = model.get("context_length") or "?"
    return f"{provider}:{model_id}  {_model_cost_label(model)}{tools}  ctx {context}  {name}"


def _model_search_text(model: dict[str, Any]) -> str:
    return " ".join(
        str(value or "")
        for value in (
            model.get("provider"),
            model.get("model_id"),
            model.get("name"),
            _model_cost_label(model),
        )
    ).lower()


def _dedupe_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped = []
    for model in models:
        key = (str(model.get("provider") or ""), str(model.get("model_id") or ""))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        deduped.append(model)
    return deduped


def _sort_models_for_ui(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def score(model: dict[str, Any]) -> tuple[int, int, float, str]:
        cost = float(model.get("input_cost_per_token") or 0.0) + float(
            model.get("output_cost_per_token") or 0.0
        )
        return (
            0 if _is_free_model(model) else 1,
            0 if _model_supports_tools(model) else 1,
            cost,
            str(model.get("model_id") or ""),
        )

    return sorted(_dedupe_models(models), key=score)


def _curate_discovered_models(models: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    openrouter = [model for model in models if model.get("provider") == "openrouter"]
    other = [model for model in models if model.get("provider") != "openrouter"]
    curated_openrouter = [
        model for model in _sort_models_for_ui(openrouter)
        if _is_free_model(model) or _model_supports_tools(model)
    ][:limit]
    return _dedupe_models([*curated_openrouter, *other])


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

    def compose(self) -> ComposeResult:
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

    def compose(self) -> ComposeResult:
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


class DevSynapseTUI(App):
    """Textual TUI for DevSynapse AI."""

    TITLE = "DevSynapse AI"
    SUB_TITLE = "terminal coding agent"
    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #workspace {
        height: 1fr;
        min-height: 0;
    }

    #main-pane {
        width: 1fr;
        min-width: 0;
    }

    #side-pane {
        width: 36;
        min-width: 32;
        background: $panel;
        border-left: solid $border;
        padding: 1;
        overflow: hidden;
    }

    #chat {
        height: 1fr;
        border: none;
        padding: 1 2 0 2;
        background: $surface;
    }

    #input {
        height: 3;
        background: $surface;
        border: solid $border;
        padding: 0 1 0 1;
    }

    #input:focus {
        border: solid $primary;
    }

    .panel {
        width: 100%;
        margin-bottom: 1;
        padding: 1;
        border: tall $border;
        background: $boost;
    }

    #session-panel {
        height: 7;
    }

    #providers-panel {
        height: 10;
    }

    #commands-panel {
        height: 1fr;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
    }

    #bar {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 2;
    }

    RichLog {
        scrollbar-color: $primary;
        scrollbar-background: $panel;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+h", "show_help", "Help"),
        Binding("f2", "open_model_picker", "Model"),
        Binding("f3", "copy_last_response", "Copy"),
        Binding("ctrl+n", "new_session", "New"),
        Binding("ctrl+p", "open_connect", "Providers"),
        Binding("ctrl+r", "refresh_status", "Refresh"),
    ]

    def __init__(self):
        super().__init__()
        self.brain = None
        self.opencode = None
        self.memory = None
        self.conversation_id = generate_conversation_id()
        self.project_name = None
        self.details_enabled = False
        self.last_provider = None
        self.last_model = None
        self.last_response_text = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="workspace"):
            with Vertical(id="main-pane"):
                yield RichLog(id="chat", highlight=True, markup=True, wrap=True)
                yield Input(
                    id="input",
                    placeholder="Message DevSynapse, /help, /status, or !<shell command>",
                )
            with Vertical(id="side-pane"):
                yield Static(id="session-panel", classes="panel")
                yield Static(id="providers-panel", classes="panel")
                yield Static(id="commands-panel", classes="panel")
        yield Static(id="bar")
        yield Footer()

    async def on_mount(self):
        input_w = self.query_one("#input", Input)
        input_w.focus()
        await self._init_engine()
        self._refresh_sidebar()

    def _chat(self) -> RichLog:
        return self.query_one("#chat", RichLog)

    def _input(self) -> Input:
        return self.query_one("#input", Input)

    def _write_panel(
        self,
        title: str,
        content: object,
        border_style: str = "blue",
        subtitle: str | None = None,
    ) -> None:
        self._chat().write(
            Panel(
                content,
                title=title,
                subtitle=subtitle,
                border_style=border_style,
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def _write_user_message(self, text: str) -> None:
        self._write_panel("you", Text(text), border_style="cyan")

    def _write_assistant_message(self, text: str) -> None:
        self.last_response_text = text
        self._write_panel(
            "DevSynapse",
            Markdown(text),
            border_style="green",
            subtitle="F3 copy",
        )

    def _write_command_message(self, command: str) -> None:
        self._write_panel("command", Text(command), border_style="yellow")

    def _write_model_message(self, provider: str, model: str) -> None:
        self._write_panel(
            "model",
            Text(f"{provider}:{model}", style="dim"),
            border_style="bright_black",
        )

    async def _init_engine(self):
        chat = self._chat()

        try:
            ensure_runtime_config_file()
            settings = app_settings.get_settings()
            self.memory = MemorySystem()
            self.opencode = OpenCodeBridge(
                known_projects=self.memory.get_project_lookup(),
            )
            if self._has_provider_key(settings):
                self.brain = DevSynapseBrain(self.memory, self.opencode)
            else:
                self.brain = None
            await plugin_manager.load_all()
            await plugin_manager.emit_event("server:startup", {})

            if not self._has_provider_key(settings):
                self._write_welcome()
                chat.write("[yellow]No provider key configured.[/]")
                chat.write(
                    "Use [bold]/connect[/] to open provider setup, or "
                    "[bold]/connect deepseek <api-key>[/]."
                )
                self._update_status_bar()
            else:
                self._write_welcome()
                chat.write(
                    "[green]Ready.[/] Type a task, [bold]/help[/], [bold]/model[/], "
                    "[bold]/copy[/], [bold]/budget[/], [bold]/router[/] or [bold]/usage[/]."
                )
                self._update_status_bar()
            chat.write("")
            self._refresh_sidebar()

        except Exception as e:
            chat.write(f"[red]Init error: {e}[/]")
            logger.exception("Init failed")
            self._refresh_sidebar()

    def _write_welcome(self) -> None:
        chat = self.query_one("#chat", RichLog)
        chat.write("[bold]DevSynapse AI[/]  local terminal agent")
        chat.write("Chat is ready. Model choice is manual.")
        chat.write(
            "Use [bold]F2[/] or [bold]/model[/] to choose a model; "
            "[bold]F3[/] or [bold]/copy[/] copies the last answer."
        )
        chat.write("")

    async def _rebuild_engine(self):
        app_settings.get_settings.cache_clear()
        importlib.reload(app_settings)
        if self.memory is None:
            self.memory = MemorySystem()
        self.opencode = OpenCodeBridge(
            known_projects=self.memory.get_project_lookup(),
        )
        settings = app_settings.get_settings()
        self.brain = (
            DevSynapseBrain(self.memory, self.opencode)
            if self._has_provider_key(settings)
            else None
        )
        self._update_status_bar()
        self._refresh_sidebar()

    @staticmethod
    def _has_provider_key(settings) -> bool:
        return any(_provider_key(settings, provider) for provider in PROVIDER_CONFIGS)

    def _refresh_sidebar(self) -> None:
        try:
            settings = app_settings.get_settings()
            project_count = len(self.memory.get_project_lookup()) if self.memory else 0
            budget = self.memory.get_llm_budget_status() if self.memory else {}
            budget_status = budget.get("overall_status", "unknown")
            provider_count = sum(
                bool(_provider_key(settings, provider))
                for provider in PROVIDER_CONFIGS
            )
            default_provider = _normalize_provider(settings.llm_default_provider) or "deepseek"
            active_model = _provider_model(settings, default_provider)
            short_conversation_id = self.conversation_id.removeprefix("chat_")

            self.query_one("#session-panel", Static).update(
                "\n".join(
                    [
                        "[bold accent]Session[/]",
                        f"chat: {short_conversation_id}",
                        f"project: {self.project_name or 'none'}",
                        f"projects: {project_count}",
                        f"budget: {budget_status}",
                    ]
                )
            )
            self.query_one("#providers-panel", Static).update(
                "\n".join(
                    [
                        "[bold accent]Model[/]",
                        f"provider: {default_provider}",
                        f"model: {_shorten_middle(active_model, 30)}",
                        f"configured keys: {provider_count}",
                        f"last: {_shorten_middle(self.last_model, 28) if self.last_model else 'none'}",
                        "[dim]F2 or /model[/]",
                    ]
                )
            )
            self.query_one("#commands-panel", Static).update(
                "\n".join(
                    [
                        "[bold accent]Commands[/]",
                        "F2  model picker",
                        "^p  providers",
                        "F3  copy answer",
                        "^r  refresh",
                        "^n  new chat",
                        "",
                        "/connect  provider setup",
                        "/model    choose model",
                        "/models   catalog",
                        "/usage    telemetry",
                        "!cmd      shell tool",
                    ]
                )
            )
        except Exception:
            logger.debug("Could not refresh TUI sidebar", exc_info=True)

    async def action_clear_chat(self):
        self._chat().clear()

    async def action_show_help(self):
        self._show_help()

    async def action_new_session(self):
        await self._cmd_new([])

    async def action_refresh_status(self):
        await self._cmd_status([])

    async def action_open_connect(self):
        await self._open_connect_screen()

    async def action_open_model_picker(self):
        await self._open_model_screen()

    async def action_copy_last_response(self):
        await self._cmd_copy([])

    async def on_input_submitted(self, event):
        task = event.value.strip()
        if not task:
            return

        input_w = self._input()
        chat = self._chat()

        input_w.clear()
        input_w.disabled = True
        self._update_status_bar(message="busy")

        self._write_user_message(task)

        if task.startswith("/"):
            await self._handle_slash_command(task)
            input_w.disabled = False
            input_w.focus()
            self._update_status_bar()
            return

        if task.startswith("!"):
            await self._handle_shell_message(task[1:].strip())
            input_w.disabled = False
            input_w.focus()
            self._update_status_bar()
            return

        if not self.brain or not self.brain.deepseek.configured:
            chat.write("[red]No provider key configured.[/]")
            chat.write(
                "Use [bold]/connect[/] to open provider setup, or "
                "[bold]/connect deepseek <api-key>[/].\n"
            )
            input_w.disabled = False
            input_w.focus()
            self._update_status_bar()
            return

        await self._process(task, chat, input_w)

    async def _process(self, task, chat, input_w):
        streamed_chunks: list[str] = []

        def on_token(chunk: str) -> None:
            streamed_chunks.append(chunk)

        try:
            response_text, command, usage = await self.brain.process_message(
                user_message=task,
                conversation_id=self.conversation_id,
                project_name=self.project_name,
                user_id="tui",
                user_role="admin",
                auto_execute=True,
                on_token=on_token,
            )

            rendered_response = response_text or "".join(streamed_chunks)
            if rendered_response:
                self._write_assistant_message(rendered_response)
                chat.write("")

            if command:
                self._write_command_message(command)

            if usage:
                self.last_provider = usage.get("provider") or self.last_provider
                self.last_model = usage.get("model") or self.last_model
                if self.last_provider and self.last_model:
                    self._write_model_message(self.last_provider, self.last_model)
                self._update_status_bar(usage)

            chat.write("")

        except Exception as e:
            chat.write(f"[red]Error: {e}[/]\n")
            logger.exception("process failed")
        finally:
            input_w.disabled = False
            input_w.focus()
            self._update_status_bar()
            self._refresh_sidebar()

    async def _handle_slash_command(self, raw: str) -> None:
        chat = self.query_one("#chat", RichLog)
        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            chat.write(f"[red]Invalid command:[/] {exc}")
            return
        if not parts:
            return

        command = parts[0][1:].lower()
        args = parts[1:]
        handlers = {
            "help": self._cmd_help,
            "h": self._cmd_help,
            "connect": self._cmd_connect,
            "providers": self._cmd_providers,
            "status": self._cmd_status,
            "projects": self._cmd_projects,
            "project": self._cmd_project,
            "model": self._cmd_model,
            "models": self._cmd_models,
            "discover": self._cmd_discover,
            "usage": self._cmd_usage,
            "budget": self._cmd_budget,
            "copy": self._cmd_copy,
            "router": self._cmd_router,
            "details": self._cmd_details,
            "new": self._cmd_new,
            "clear": self._cmd_new,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
            "q": self._cmd_exit,
        }
        handler = handlers.get(command)
        if handler is None:
            chat.write(f"[red]Unknown command:[/] /{command}. Type [bold]/help[/].")
            return
        await handler(args)

    async def _handle_shell_message(self, command: str) -> None:
        chat = self._chat()
        if not command:
            chat.write("[yellow]Usage:[/] !<shell command>")
            return
        if self.opencode is None:
            chat.write("[red]Command bridge is not initialized.[/]")
            return
        escaped_command = command.replace("\\", "\\\\").replace('"', '\\"')
        result = await self.opencode.execute_command(
            f'bash "{escaped_command}"',
            user_id="tui",
            user_role="admin",
            project_name=self.project_name,
            conversation_id=self.conversation_id,
        )
        color = "green" if result.success else "red"
        body = result.message
        if result.reason_code:
            body += f"\nreason: {result.reason_code}"
        if result.output:
            body += f"\n\n{result.output}"
        self._write_panel(
            f"shell {result.status}",
            Text(body),
            border_style=color,
        )
        self._refresh_sidebar()

    async def _cmd_help(self, _args: list[str]) -> None:
        self._show_help()

    def _show_help(self) -> None:
        chat = self._chat()
        chat.write("[bold]DevSynapse commands[/]")
        chat.write("  /connect                         open provider setup")
        chat.write("  /connect <provider>              open setup with provider selected")
        chat.write("  /connect <provider> <api-key>    save provider key")
        chat.write("  /providers                       show provider key status")
        chat.write("  /status                          show runtime status")
        chat.write("  /projects                        list registered projects")
        chat.write("  /project <name>                  set active project")
        chat.write("  /project                         clear active project")
        chat.write("  /discover                        refresh model catalog")
        chat.write("  /model                           search and select active model")
        chat.write("  /models [provider]               list model catalog")
        chat.write("  /copy                            copy last assistant answer")
        chat.write("  /budget                          show usage plan and limits")
        chat.write("  /budget daily|monthly <usd>      set budget limit")
        chat.write("  /budget warning|critical <pct>   set thresholds")
        chat.write("  /router                          show manual model status")
        chat.write("  /usage                           show recent provider/model telemetry")
        chat.write("  /details                         toggle route/tool detail display")
        chat.write("  /new                             start a new conversation")
        chat.write("  !<command>                       run shell command as a tool result")

    async def _cmd_copy(self, _args: list[str]) -> None:
        chat = self._chat()
        if not self.last_response_text.strip():
            chat.write("[yellow]No assistant answer to copy yet.[/]")
            return
        try:
            self.copy_to_clipboard(self.last_response_text)
        except Exception as exc:
            chat.write(f"[red]Could not copy answer:[/] {exc}")
            logger.exception("Could not copy assistant answer")
            return
        chat.write("[green]Copied last assistant answer.[/]")

    async def _cmd_status(self, _args: list[str]) -> None:
        chat = self._chat()
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        settings = app_settings.get_settings()
        budget = self.memory.get_llm_budget_status()
        default_provider = _normalize_provider(settings.llm_default_provider) or "deepseek"
        chat.write("[bold]Status[/]")
        chat.write(f"  conversation: {self.conversation_id}")
        chat.write(f"  project: {self.project_name or 'none'}")
        chat.write(f"  providers: {'configured' if self._has_provider_key(settings) else 'missing'}")
        chat.write(f"  default provider: {default_provider}")
        chat.write(f"  default model: {_provider_model(settings, default_provider)}")
        if self.last_provider and self.last_model:
            chat.write(f"  last response: {self.last_provider}:{self.last_model}")
        chat.write(f"  budget: {budget['overall_status']}")
        chat.write(f"  projects: {len(self.memory.get_project_lookup())}")
        self._update_status_bar()
        self._refresh_sidebar()

    async def _cmd_projects(self, _args: list[str]) -> None:
        chat = self._chat()
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        projects = self.memory.get_project_lookup()
        if not projects:
            chat.write("[yellow]No registered projects.[/]")
            return
        chat.write("[bold]Projects[/]")
        for name, project in sorted(projects.items()):
            marker = "*" if name == self.project_name else " "
            chat.write(f"{marker} {name}  {project.get('path', '')}")

    async def _cmd_project(self, args: list[str]) -> None:
        chat = self._chat()
        if not args:
            self.project_name = None
            chat.write("[green]Project cleared.[/]")
            self._update_status_bar()
            self._refresh_sidebar()
            return
        project_name = args[0]
        if self.memory is not None and project_name not in self.memory.get_project_lookup():
            chat.write(f"[yellow]Project not registered:[/] {project_name}")
            chat.write("Use [bold]/projects[/] to list known projects.")
            return
        self.project_name = project_name
        chat.write(f"[green]Project set:[/] {project_name}")
        self._update_status_bar()
        self._refresh_sidebar()

    async def _cmd_connect(self, args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        if not args:
            await self._open_connect_screen()
            return
        if len(args) == 1:
            await self._open_connect_screen(args[0])
            return

        provider = _normalize_provider(args[0])
        if provider not in PROVIDER_CONFIGS:
            chat.write(f"[red]Unknown provider:[/] {provider}")
            return

        api_key = args[1].strip()
        model = args[2].strip() if len(args) >= 3 else ""
        try:
            await self._save_provider_credentials(provider, api_key, model)
        except Exception as exc:
            chat.write(f"[red]Could not save provider key:[/] {exc}")
            logger.exception("Could not save provider key")
            return

        env_key = PROVIDER_CONFIGS[provider]["env_key"]
        chat.write(f"[green]Saved[/] {env_key} = {_mask_secret(api_key)}")
        chat.write(f"[green]Default provider:[/] {provider}")
        chat.write("Use [bold]/discover[/] to refresh available model data.")

    async def _open_connect_screen(self, provider: str | None = None) -> None:
        chat = self.query_one("#chat", RichLog)
        settings = app_settings.get_settings()
        selected_provider = (
            _normalize_provider(provider)
            or _normalize_provider(settings.llm_default_provider)
            or "deepseek"
        )
        if selected_provider not in PROVIDER_CONFIGS:
            chat.write(f"[red]Unknown provider:[/] {provider}")
            return
        await self.push_screen(
            ProviderConnectionScreen(
                provider=selected_provider,
                model=_provider_model(settings, selected_provider),
            ),
            callback=self._connect_screen_callback,
        )

    def _connect_screen_callback(self, result: dict[str, str] | None) -> None:
        asyncio.create_task(self._handle_connect_screen_result(result))

    async def _handle_connect_screen_result(self, result: dict[str, str] | None) -> None:
        chat = self.query_one("#chat", RichLog)
        if not result:
            chat.write("[yellow]Provider setup cancelled.[/]")
            return
        try:
            await self._save_provider_credentials(
                result["provider"],
                result["api_key"],
                result.get("model", ""),
            )
        except Exception as exc:
            chat.write(f"[red]Could not save provider key:[/] {exc}")
            logger.exception("Could not save provider key")
            return
        chat.write(f"[green]Provider ready:[/] {result['provider']}")
        chat.write("Use [bold]/discover[/] to refresh available model data.")

    async def _save_provider_credentials(
        self,
        provider: str,
        api_key: str,
        model: str | None = None,
    ) -> None:
        config = _provider_config(provider)
        if config is None:
            raise ValueError(f"Unknown provider: {provider}")
        normalized_provider = _normalize_provider(provider) or "deepseek"
        selected_model = (model or "").strip() or config["default_model"]
        set_runtime_config_values(
            {
                config["env_key"]: api_key.strip(),
                "LLM_DEFAULT_PROVIDER": normalized_provider,
                config["model_key"]: selected_model,
            }
        )
        await self._rebuild_engine()

    async def _cmd_providers(self, _args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        settings = app_settings.get_settings()
        default_provider = _normalize_provider(settings.llm_default_provider) or "deepseek"
        chat.write("[bold]Providers[/]")
        for provider, config in PROVIDER_CONFIGS.items():
            marker = "*" if provider == default_provider else " "
            key_status = _mask_secret(_provider_key(settings, provider))
            model = _provider_model(settings, provider)
            chat.write(f"{marker} {provider:<12} {key_status:<12} model {model}")
        chat.write("Use [bold]/connect[/] to edit providers.")

    async def _cmd_discover(self, _args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return

        settings = app_settings.get_settings()
        discovered = []
        errors = []

        if settings.openrouter_api_key:
            try:
                discovered.extend(
                    fetch_openrouter_models(
                        settings.openrouter_models_url,
                        timeout=settings.llm_request_timeout,
                    )
                )
            except Exception as exc:
                errors.append(f"openrouter: {exc}")

        if settings.opencode_go_api_key:
            try:
                discovered.extend(
                    fetch_openai_compatible_models(
                        "opencode-go",
                        settings.opencode_go_models_url,
                        settings.opencode_go_api_key,
                        timeout=settings.llm_request_timeout,
                    )
                )
            except Exception as exc:
                errors.append(f"opencode-go: {exc}")

        if settings.opencode_zen_api_key:
            try:
                discovered.extend(
                    fetch_openai_compatible_models(
                        "opencode-zen",
                        settings.opencode_zen_models_url,
                        settings.opencode_zen_api_key,
                        timeout=settings.llm_request_timeout,
                    )
                )
            except Exception as exc:
                errors.append(f"opencode-zen: {exc}")

        if discovered:
            curated = _curate_discovered_models(discovered)
            count = self.memory.upsert_llm_models(curated)
            chat.write(
                f"[green]Model catalog updated:[/] {count} principal models "
                f"({len(discovered)} discovered)"
            )
        else:
            chat.write("[yellow]No remote model catalog discovered.[/]")
            chat.write("Configure OpenRouter or OpenCode Go first with /connect.")

        for error in errors:
            chat.write(f"[red]{error}[/]")

    async def _cmd_model(self, args: list[str]) -> None:
        provider = args[0] if args else None
        await self._open_model_screen(provider)

    async def _open_model_screen(self, provider: str | None = None) -> None:
        chat = self.query_one("#chat", RichLog)
        settings = app_settings.get_settings()
        selected_provider = (
            _normalize_provider(provider)
            or _normalize_provider(settings.llm_default_provider)
            or "openrouter"
        )
        if selected_provider not in PROVIDER_CONFIGS:
            chat.write(f"[red]Unknown provider:[/] {provider}")
            return
        models = self._model_picker_catalog(selected_provider)
        if not models:
            chat.write("[yellow]No model candidates available.[/]")
            chat.write("Use [bold]/discover[/] after connecting a provider.")
            return
        await self.push_screen(
            ModelSelectionScreen(
                models=models,
                selected_provider=selected_provider,
                selected_model=_provider_model(settings, selected_provider),
            ),
            callback=self._model_screen_callback,
        )

    def _model_screen_callback(self, result: dict[str, str] | None) -> None:
        asyncio.create_task(self._handle_model_screen_result(result))

    async def _handle_model_screen_result(self, result: dict[str, str] | None) -> None:
        chat = self.query_one("#chat", RichLog)
        if not result:
            chat.write("[yellow]Model selection cancelled.[/]")
            return
        provider = result["provider"]
        model = result["model"]
        config = _provider_config(provider)
        if config is None:
            chat.write(f"[red]Unknown provider:[/] {provider}")
            return
        set_runtime_config_values(
            {
                "LLM_DEFAULT_PROVIDER": provider,
                config["model_key"]: model,
            }
        )
        await self._rebuild_engine()
        chat.write(f"[green]Model selected:[/] {provider}:{model}")

    def _model_picker_catalog(self, selected_provider: str) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        if self.memory is not None:
            models.extend(self.memory.list_llm_models(limit=200))
        models.extend(OPENROUTER_CURATED_FREE_MODELS)
        settings = app_settings.get_settings()
        for provider, config in PROVIDER_CONFIGS.items():
            models.append(
                {
                    "provider": provider,
                    "model_id": _provider_model(settings, provider),
                    "name": f"{config['label']} configured default",
                    "context_length": None,
                    "input_cost_per_token": None,
                    "output_cost_per_token": None,
                    "capabilities": {},
                }
            )
        configured = [
            model for model in _sort_models_for_ui(models)
            if model.get("provider") == selected_provider
            or (
                str(model.get("provider") or "") in PROVIDER_CONFIGS
                and _provider_key(settings, str(model.get("provider") or ""))
            )
        ]
        return configured or _sort_models_for_ui(models)

    async def _cmd_models(self, args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        provider = args[0] if args else None
        models = _sort_models_for_ui(self.memory.list_llm_models(provider=provider, limit=80))
        if not models:
            chat.write(
                "[yellow]No models in catalog.[/] "
                "Use /discover after connecting a provider."
            )
            return

        chat.write("[bold]Model catalog[/]")
        for model in models[:40]:
            chat.write(f"  {_model_option_label(model)}")
        chat.write("Use [bold]/model[/] for searchable selection.")

    async def _cmd_usage(self, _args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return

        usage = self.memory.get_llm_usage_stats(hours=24)
        totals = usage.get("totals", {})
        telemetry = self.memory.get_llm_telemetry_stats(hours=24)
        chat.write("[bold]Usage last 24h[/]")
        chat.write(
            (
                "  requests {requests}  conversations {conversations}  "
                "tokens {tokens}  cache {cache:.2f}%  cost {cost}"
            ).format(
                requests=totals.get("request_count", 0),
                conversations=totals.get("conversation_count", 0),
                tokens=totals.get("total_tokens", 0),
                cache=float(totals.get("cache_hit_rate_pct") or 0.0),
                cost=_format_money(totals.get("estimated_cost_usd")),
            )
        )
        rows = telemetry.get("by_user_model", [])
        if rows:
            chat.write("[bold]By model[/]")
            for row in rows[:10]:
                chat.write(
                    f"  {row['provider']}:{row['model']}  req {row['request_count']}  "
                    f"errors {row['error_count']}  cost {_format_money(row['estimated_cost_usd'])}"
                )

    async def _cmd_budget(self, args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return

        if len(args) >= 2:
            target = args[0].lower()
            key_map = {
                "daily": "llm_daily_budget_usd",
                "monthly": "llm_monthly_budget_usd",
                "warning": "llm_budget_warning_threshold_pct",
                "critical": "llm_budget_critical_threshold_pct",
            }
            setting_key = key_map.get(target)
            if setting_key is None:
                chat.write(
                    "[yellow]Usage:[/] /budget daily|monthly <usd> "
                    "or /budget warning|critical <pct>"
                )
                return
            try:
                value = float(args[1])
            except ValueError:
                chat.write("[red]Budget value must be numeric.[/]")
                return
            self.memory.update_app_settings({setting_key: value})
            chat.write(f"[green]Saved[/] {setting_key} = {value}")

        budget = self.memory.get_llm_budget_status()
        chat.write(f"[bold]Budget[/] overall: {budget['overall_status']}")
        for window in ("daily", "monthly"):
            item = budget[window]
            chat.write(
                f"  {window}: {item['level']}  "
                f"{_format_money(item['actual_cost_usd'])}/{_format_money(item['budget_usd'])}  "
                f"{float(item['usage_pct']):.2f}%"
            )
        self._update_status_bar()

    async def _cmd_router(self, args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return

        if args:
            chat.write("[yellow]Automatic routing has been removed.[/]")
            chat.write("Use [bold]/model[/] to choose exactly which model DevSynapse uses.")

        settings = app_settings.get_settings()
        budget = self.memory.get_llm_budget_status()
        models = self.memory.list_llm_models(limit=200)
        default_provider = _normalize_provider(settings.llm_default_provider) or "deepseek"

        chat.write("[bold]Model Control[/]")
        chat.write("  mode: manual")
        chat.write("  automatic routing: removed")
        chat.write(f"  provider: {default_provider}")
        chat.write(f"  model: {_provider_model(settings, default_provider)}")
        chat.write(f"  budget status: {budget['overall_status']}")
        chat.write(f"  catalog models: {len(models)}")
        chat.write("Use [bold]/model[/] to search and change the active model.")

    def _router_updates_from_args(self, args: list[str]) -> dict[str, object] | None:
        _ = args
        return None

    async def _cmd_details(self, _args: list[str]) -> None:
        self.details_enabled = not self.details_enabled
        chat = self.query_one("#chat", RichLog)
        chat.write(f"[green]Details:[/] {'on' if self.details_enabled else 'off'}")

    async def _cmd_new(self, _args: list[str]) -> None:
        self.conversation_id = generate_conversation_id()
        chat = self.query_one("#chat", RichLog)
        chat.clear()
        chat.write(f"[green]New conversation:[/] {self.conversation_id}")

    async def _cmd_exit(self, _args: list[str]) -> None:
        self.exit()

    def _update_status_bar(self, usage: dict | None = None, message: str | None = None) -> None:
        if self.memory is None:
            return
        bar = self.query_one("#bar", Static)
        settings = app_settings.get_settings()
        provider_count = sum(
            bool(_provider_key(settings, provider))
            for provider in PROVIDER_CONFIGS
        )
        budget = self.memory.get_llm_budget_status()
        project = self.project_name or "-"
        if message:
            bar.update(
                f" providers:{provider_count}  budget:{budget['overall_status']}  "
                f"project:{project}  {message}"
            )
            return
        if usage:
            provider = usage.get("provider", "?")
            model = usage.get("model", "?")
            tokens = usage.get("total_tokens") or 0
            cost = _format_money(usage.get("estimated_cost_usd"))
            bar.update(
                f" providers:{provider_count}  budget:{budget['overall_status']}  "
                f"project:{project}  {provider}/{model}  tokens:{tokens}  cost:{cost}"
            )
        else:
            model_status = (
                f" {self.last_provider}/{self.last_model}"
                if self.last_provider and self.last_model
                else ""
            )
            bar.update(
                f" providers:{provider_count}  budget:{budget['overall_status']}  "
                f"project:{project}{model_status}  conversation:{self.conversation_id}"
            )


def run_tui():
    app = DevSynapseTUI()
    app.run()
