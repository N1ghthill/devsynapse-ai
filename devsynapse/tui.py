"""
DevSynapse AI — Textual TUI (terminal chat interface).
"""

import asyncio
import importlib
import logging
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
from textual.widgets import Footer, Header, Input, RichLog, Static

import config.settings as app_settings
from core.brain import DevSynapseBrain
from core.correlation import generate_conversation_id
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge
from core.plugin_system import plugin_manager
from core.runtime_config import ensure_runtime_config_file, set_runtime_config_values
from devsynapse.commands import (
    OPENROUTER_CURATED_FREE_MODELS,
    PROVIDER_CONFIGS,
    CommandDispatcher,
    _format_money,
    _provider_config,
    _provider_key,
    _provider_model,
    _shorten_middle,
    _sort_models_for_ui,
)
from devsynapse.screens import ModelSelectionScreen, ProviderConnectionScreen

logger = logging.getLogger(__name__)


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
        self._dispatcher: CommandDispatcher | None = None

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
        input_w = self._input()
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
            default_provider = (settings.llm_default_provider or "deepseek").strip().lower()
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
        except Exception as e:
            logger.exception("Could not refresh TUI sidebar: %s", e)

    async def action_clear_chat(self):
        self._chat().clear()

    async def action_show_help(self):
        if self._dispatcher:
            await self._dispatcher.cmd_help([])

    async def action_new_session(self):
        if self._dispatcher:
            await self._dispatcher.cmd_new([])

    async def action_refresh_status(self):
        if self._dispatcher:
            await self._dispatcher.cmd_status([])

    async def action_open_connect(self):
        await self._open_connect_screen()

    async def action_open_model_picker(self):
        await self._open_model_screen()

    async def action_copy_last_response(self):
        if self._dispatcher:
            await self._dispatcher.cmd_copy([])

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
            if self._dispatcher is None:
                self._dispatcher = CommandDispatcher(self)
            await self._dispatcher.handle(task)
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

    async def _open_connect_screen(self, provider: str | None = None) -> None:
        chat = self.query_one("#chat", RichLog)
        settings = app_settings.get_settings()
        selected_provider = (
            (provider or settings.llm_default_provider or "deepseek").strip().lower()
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
        normalized_provider = (provider or "deepseek").strip().lower()
        selected_model = (model or "").strip() or config["default_model"]
        set_runtime_config_values(
            {
                config["env_key"]: api_key.strip(),
                "LLM_DEFAULT_PROVIDER": normalized_provider,
                config["model_key"]: selected_model,
            }
        )
        await self._rebuild_engine()

    async def _open_model_screen(self, provider: str | None = None) -> None:
        chat = self.query_one("#chat", RichLog)
        settings = app_settings.get_settings()
        selected_provider = (
            (provider or settings.llm_default_provider or "openrouter").strip().lower()
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
