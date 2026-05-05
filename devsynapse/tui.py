"""
DevSynapse AI - Textual TUI (terminal chat interface).
Enhanced with a command menu, help overlay, notifications and dynamic sidebar.
"""

import asyncio
import importlib
import logging
import sys
from datetime import datetime
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
from textual.widgets import OptionList, RichLog, Static
from textual.widgets.option_list import Option

import config.settings as app_settings
from core.brain import DevSynapseBrain
from core.correlation import generate_conversation_id
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge
from core.plugin_system import plugin_manager
from core.runtime_config import ensure_runtime_config_file, set_runtime_config_values
from devsynapse.command_catalog import CommandSuggestion, build_command_suggestions
from devsynapse.commands import (
    OPENROUTER_CURATED_FREE_MODELS,
    PROVIDER_CONFIGS,
    CommandDispatcher,
    _format_money,
    _provider_config,
    _provider_key,
    _provider_model,
    _sort_models_for_ui,
)
from devsynapse.screens import ModelSelectionScreen, ProviderConnectionScreen
from devsynapse.screens.command_palette import CommandPaletteScreen
from devsynapse.tui_input import EnhancedInput
from devsynapse.tui_notifications import NotificationManager
from devsynapse.tui_preferences import TUIPreferences, load_tui_preferences, save_tui_preferences
from devsynapse.tui_rendering import render_command_result, strip_ansi
from devsynapse.tui_sidebar import DynamicSidebar

logger = logging.getLogger(__name__)


class DevSynapseTUI(App):
    """Enhanced Textual TUI for DevSynapse AI."""

    TITLE = "DevSynapse AI"
    SUB_TITLE = "terminal coding agent"
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+h", "show_help", "Help"),
        Binding("f2", "open_model_picker", "Model"),
        Binding("f3", "copy_last_response", "Copy"),
        Binding("f4", "toggle_model_panel", "Model Panel"),
        Binding("f5", "toggle_telemetry_panel", "Telemetry Panel"),
        Binding("ctrl+n", "new_session", "New"),
        Binding("ctrl+p", "open_command_palette", "Palette"),
        Binding("ctrl+r", "refresh_status", "Refresh"),
    ]

    def __init__(self):
        self.ui_preferences: TUIPreferences = load_tui_preferences()
        self.CSS_PATH = self.ui_preferences.css_paths
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
        self._is_busy = False
        self._streaming_panel_id = None
        self._total_tokens = 0
        self._total_cost = 0.0
        self._command_suggestions: list[CommandSuggestion] = []
        self._header_widget: Static | None = None
        self._footer_widget: Static | None = None
        self._typing_widget: Static | None = None
        self._busy_message = ""
        self._busy_frame = 0

    def compose(self) -> ComposeResult:
        yield Static(id="app-header")
        yield NotificationManager(id="notifications")
        with Horizontal(id="workspace"):
            with Vertical(id="main-pane"):
                yield RichLog(id="chat", highlight=True, markup=True, wrap=True)
                yield Static("", id="typing-indicator")
                with Vertical(id="input-container"):
                    yield OptionList(id="command-suggestions", classes="hidden")
                    yield EnhancedInput(
                        id="input",
                        placeholder="Message /help or !cmd (Shift+Enter for new line)",
                    )
            yield DynamicSidebar(id="sidebar", palette=self.ui_preferences.palette)
        yield Static(id="status-bar")
        yield Static(id="app-footer")

    async def on_mount(self):
        self._header_widget = self.query_one("#app-header", Static)
        self._footer_widget = self.query_one("#app-footer", Static)
        self._typing_widget = self.query_one("#typing-indicator", Static)
        self._update_chrome()
        self.set_interval(1.0, self._update_header)
        self.set_interval(0.4, self._update_busy_indicator)
        input_w = self._input()
        input_w.focus()
        self._sidebar().refresh_all(
            session_id=self.conversation_id,
            project_name=self.project_name,
        )
        await self._init_engine()

    def _chat(self) -> RichLog:
        return self.query_one("#chat", RichLog)

    def _input(self) -> EnhancedInput:
        return self.query_one("#input", EnhancedInput)

    def _sidebar(self) -> DynamicSidebar:
        return self.query_one("#sidebar", DynamicSidebar)

    def _header(self) -> Static:
        if self._header_widget is not None:
            return self._header_widget
        return self.query_one("#app-header", Static)

    def _footer(self) -> Static:
        if self._footer_widget is not None:
            return self._footer_widget
        return self.query_one("#app-footer", Static)

    def _notification_manager(self) -> NotificationManager:
        return self.query_one("#notifications", NotificationManager)

    def _typing_indicator(self) -> Static:
        if self._typing_widget is not None:
            return self._typing_widget
        return self.query_one("#typing-indicator", Static)

    def _command_dispatcher(self) -> CommandDispatcher:
        if self._dispatcher is None:
            self._dispatcher = CommandDispatcher(self)
        return self._dispatcher

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
        self._write_panel("you", Text(text), border_style=self._state_color("user"))

    def _write_assistant_message(self, text: str) -> None:
        self.last_response_text = text
        self._write_panel(
            "DevSynapse",
            Markdown(text),
            border_style=self._state_color("assistant"),
            subtitle="F3 copy",
        )

    def _write_command_message(self, command: str) -> None:
        self._write_panel("command", Text(command), border_style=self._state_color("executing"))

    def _write_model_message(self, provider: str, model: str) -> None:
        self._write_panel(
            "model",
            Text(f"{provider}:{model}", style="dim"),
            border_style=self._state_color("muted"),
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
            else:
                self._write_welcome()
                chat.write(
                    "[green]Ready.[/] Type a task, [bold]/help[/], [bold]/model[/], "
                    "[bold]/copy[/], [bold]/budget[/], [bold]/router[/] or [bold]/usage[/]."
                )
            chat.write("")
            self._refresh_sidebar()

        except Exception as e:
            chat.write(f"[red]Init error: {e}[/]")
            logger.exception("Init failed")
            self._notification_manager().show(f"Init failed: {e}", "error")

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
            project_count = len(self.memory.get_project_lookup()) if self.memory else 0
            budget = self.memory.get_llm_budget_status() if self.memory else {}
            usage_stats = self.memory.get_llm_usage_stats(hours=24) if self.memory else {}
            telemetry_stats = (
                self.memory.get_llm_telemetry_stats(hours=24) if self.memory else {}
            )
            catalog_count = (
                len(self.memory.list_llm_models(limit=500)) if self.memory else 0
            )

            self._sidebar().refresh_all(
                session_id=self.conversation_id,
                project_name=self.project_name,
                project_count=project_count,
                budget_status=budget,
                provider=self.last_provider,
                model=self.last_model,
                tokens=self._total_tokens,
                cost=self._total_cost,
                usage_stats=usage_stats,
                telemetry_stats=telemetry_stats,
                catalog_count=catalog_count,
            )
        except Exception as e:
            logger.exception("Could not refresh TUI sidebar: %s", e)

    async def action_clear_chat(self):
        self._chat().clear()
        self._notification_manager().show("Chat cleared", "info")

    async def action_show_help(self):
        await self._command_dispatcher().cmd_help([])

    async def action_new_session(self):
        if self._dispatcher:
            await self._dispatcher.cmd_new([])
        else:
            self.conversation_id = generate_conversation_id()
            self._chat().clear()
            self._write_welcome()
            self._refresh_sidebar()
            self._notification_manager().show("New session started", "success")

    async def action_refresh_status(self):
        await self._command_dispatcher().cmd_status([])
        self._refresh_sidebar()
        self._notification_manager().show("Status refreshed", "info")

    async def action_open_connect(self):
        await self._open_connect_screen()

    async def action_open_command_palette(self):
        await self.push_screen(CommandPaletteScreen(), callback=self._command_palette_callback)

    def _command_palette_callback(self, value: str | None) -> None:
        if not value:
            self._input().focus()
            return
        input_w = self._input()
        input_w.value = value
        input_w.cursor_position = len(value)
        input_w.focus()
        self.refresh_command_suggestions(value, force=True)

    async def action_open_model_picker(self):
        await self._open_model_screen()

    async def action_copy_last_response(self):
        await self._command_dispatcher().cmd_copy([])

    def action_toggle_model_panel(self) -> None:
        self._sidebar().toggle_panel("model")
        self._sidebar().update_model()
        self._notification_manager().show("Model panel toggled", "info")

    def action_toggle_telemetry_panel(self) -> None:
        self._sidebar().toggle_panel("telemetry")
        self._sidebar().update_telemetry()
        self._notification_manager().show("Telemetry panel toggled", "info")

    async def on_input_submitted(self, event):
        task = event.value.strip()
        if not task:
            return

        input_w = self._input()
        chat = self._chat()

        self._hide_command_suggestions()
        input_w.add_to_history(task)
        input_w.clear()
        input_w.disabled = True
        self._write_user_message(task)

        if task.startswith("/"):
            self._set_busy(True, "Running slash command...")
            await self._command_dispatcher().handle(task)
            self._set_busy(False)
            input_w.disabled = False
            input_w.focus()
            return

        if task.startswith("!"):
            self._set_busy(True, "Executing shell command...")
            await self._handle_shell_message(task[1:].strip())
            self._set_busy(False)
            input_w.disabled = False
            input_w.focus()
            return

        self._set_busy(True, "DevSynapse is thinking...")

        if not self.brain or not self.brain.deepseek.configured:
            chat.write("[red]No provider key configured.[/]")
            chat.write(
                "Use [bold]/connect[/] to open provider setup, or "
                "[bold]/connect deepseek <api-key>[/].\n"
            )
            self._set_busy(False)
            input_w.disabled = False
            input_w.focus()
            return

        await self._process(task, chat, input_w)

    def _state_color(self, state: str) -> str:
        """Return a semantic color from the active TUI theme."""
        return self.ui_preferences.palette.get(state, self.ui_preferences.palette["thinking"])

    def _update_chrome(self) -> None:
        self._update_header()
        self._update_footer()

    def _update_header(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        theme = self.ui_preferences.theme
        layout = self.ui_preferences.layout
        self._header().update(
            f"[bold {self._state_color('title')}]DevSynapse AI[/] "
            f"[{self._state_color('muted')}]terminal coding agent[/] "
            f"[{self._state_color('streaming')}]{theme}/{layout}[/] "
            f"[{self._state_color('muted')}]{now}[/]"
        )

    def _update_footer(self) -> None:
        muted = self._state_color("muted")
        accent = self._state_color("streaming")
        self._footer().update(
            f"[{accent}]^l[/] Clear   [{accent}]^h[/] Help   "
            f"[{accent}]F2[/] Model   [{accent}]F3[/] Copy   "
            f"[{accent}]F4[/] Model panel   [{accent}]F5[/] Telemetry   "
            f"[{accent}]^n[/] New   [{accent}]^p[/] Palette   "
            f"[{accent}]^r[/] Refresh   [{accent}]/[/] Commands   "
            f"[{accent}]/theme[/] Theme   [{muted}]Esc quits dialogs[/]"
        )

    def apply_tui_preferences(
        self,
        *,
        theme: str | None = None,
        layout: str | None = None,
    ) -> str:
        """Persist and apply TUI appearance preferences."""
        self.ui_preferences = save_tui_preferences(
            theme=theme,
            layout=layout,
            config_file=self.ui_preferences.config_file,
        )
        self.CSS_PATH = self.ui_preferences.css_paths
        self._sidebar().palette = self.ui_preferences.palette
        self._update_chrome()
        self._update_status_bar()
        self._refresh_sidebar()
        try:
            self.refresh_css(animate=False)
            return "applied"
        except Exception:
            logger.exception("Could not refresh TUI CSS after preference change")
            return "saved"

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        """Set busy state with visual indicators."""
        self._is_busy = busy
        typing = self._typing_indicator()
        if busy:
            self._busy_message = message or "DevSynapse is thinking"
            self._busy_frame = 0
            self._update_busy_indicator()
            typing.add_class("pulse")
        else:
            self._busy_message = ""
            typing.update("")
            typing.remove_class("pulse")
        self._sidebar().set_busy(busy)
        self._update_status_bar(message=message or "busy" if busy else None)

    def _update_busy_indicator(self) -> None:
        if not self._is_busy or not self._busy_message:
            return
        dots = "." * (self._busy_frame % 4)
        padding = " " * (3 - len(dots))
        self._typing_indicator().update(
            f"[bold {self._state_color('thinking')}]{self._busy_message}{dots}{padding}[/]"
        )
        self._busy_frame += 1

    async def _process(self, task, chat, input_w):
        streamed_chunks: list[str] = []
        typing_shown = False

        def on_token(chunk: str) -> None:
            nonlocal typing_shown
            streamed_chunks.append(chunk)
            if not typing_shown:
                typing_shown = True

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
                tokens = usage.get("total_tokens") or 0
                cost = usage.get("estimated_cost_usd") or 0.0
                self._total_tokens += tokens
                self._total_cost += cost
                self._update_status_bar(usage)

            chat.write("")

        except Exception as e:
            chat.write(f"[red]Error: {e}[/]\n")
            logger.exception("process failed")
            self._notification_manager().show(f"Error: {e}", "error")
        finally:
            self._set_busy(False)
            input_w.disabled = False
            input_w.focus()
            self._update_status_bar()
            self._refresh_sidebar()

    def on_input_changed(self, event) -> None:
        if event.input.id == "input":
            self.refresh_command_suggestions(event.value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "command-suggestions":
            return
        event.stop()
        self.accept_command_suggestion(event.index)
        self._input().focus()

    def refresh_command_suggestions(self, value: str | None = None, *, force: bool = False) -> None:
        """Refresh the slash command suggestion menu for the current input."""
        text = self._input().value if value is None else value
        if self._is_busy and not force:
            self._hide_command_suggestions()
            return

        project_names = self.memory.get_project_lookup().keys() if self.memory else ()
        suggestions = build_command_suggestions(text, project_names=project_names)
        if force and not suggestions:
            suggestions = build_command_suggestions("/", project_names=project_names)
        self._command_suggestions = suggestions

        menu = self.query_one("#command-suggestions", OptionList)
        menu.clear_options()
        if not suggestions:
            self._hide_command_suggestions()
            return

        menu.add_options(
            [
                Option(
                    (
                        f"[dim]{suggestion.category:<7}[/] "
                        f"[bold]{suggestion.label:<26}[/] "
                        f"[dim]{suggestion.description}[/]"
                    ),
                    id=f"command-suggestion-{index}",
                )
                for index, suggestion in enumerate(suggestions)
            ]
        )
        menu.highlighted = 0
        menu.remove_class("hidden")

    def move_command_suggestion(self, direction: int) -> bool:
        """Move the active command suggestion while the input keeps focus."""
        menu = self.query_one("#command-suggestions", OptionList)
        if not self._command_suggestions or menu.has_class("hidden"):
            return False
        current = menu.highlighted if isinstance(menu.highlighted, int) else 0
        next_index = max(0, min(menu.option_count - 1, current + direction))
        menu.highlighted = next_index
        menu.scroll_to_highlight()
        return True

    def accept_command_suggestion(self, index: int | None = None) -> bool:
        """Apply the highlighted command suggestion to the input."""
        menu = self.query_one("#command-suggestions", OptionList)
        if not self._command_suggestions or menu.has_class("hidden"):
            return False
        selected_index = index
        if selected_index is None:
            selected_index = menu.highlighted if isinstance(menu.highlighted, int) else 0
        if selected_index is None or selected_index >= len(self._command_suggestions):
            return False

        suggestion = self._command_suggestions[selected_index]
        input_w = self._input()
        if input_w.value == suggestion.value:
            self._hide_command_suggestions()
            return False
        input_w.value = suggestion.value
        input_w.cursor_position = len(input_w.value)
        self.refresh_command_suggestions(input_w.value)
        return True

    def _hide_command_suggestions(self) -> None:
        self._command_suggestions = []
        try:
            menu = self.query_one("#command-suggestions", OptionList)
        except Exception:
            return
        menu.clear_options()
        menu.add_class("hidden")

    async def _handle_shell_message(self, command: str) -> None:
        chat = self._chat()
        if not command:
            chat.write("[yellow]Usage:[/] !<shell command>")
            return
        if self.opencode is None:
            chat.write("[red]Command bridge is not initialized.[/]")
            return
        self._update_status_bar(message=f"executing: {command[:60]}")
        escaped_command = command.replace("\\", "\\\\").replace('"', '\\"')
        result = await self.opencode.execute_command(
            f'bash "{escaped_command}"',
            user_id="tui",
            user_role="admin",
            project_name=self.project_name,
            conversation_id=self.conversation_id,
        )
        color = self._state_color("success" if result.success else "error")
        self._write_panel(
            f"shell {result.status}",
            render_command_result(
                message=result.message,
                output=strip_ansi(result.output or ""),
                reason_code=result.reason_code,
            ),
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
            self._notification_manager().show("Provider setup cancelled", "warning")
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
            self._notification_manager().show(f"Save failed: {exc}", "error")
            return
        chat.write(f"[green]Provider ready:[/] {result['provider']}")
        chat.write("Use [bold]/discover[/] to refresh available model data.")
        self._notification_manager().show(f"Provider {result['provider']} ready", "success")

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
            self._notification_manager().show("Model selection cancelled", "warning")
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
        self._notification_manager().show(f"Model set to {model}", "success")

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
        bar = self.query_one("#status-bar", Static)
        budget = self.memory.get_llm_budget_status()
        budget_str = budget.get("overall_status", "unknown")
        budget_color = (
            self._state_color("success")
            if budget_str == "healthy"
            else (
                self._state_color("warning")
                if budget_str == "warning"
                else self._state_color("error")
            )
        )

        if message:
            project = self.project_name or "no project"
            bar.update(
                f"[bold {self._state_color('thinking')}]*[/] {message}  "
                f"[dim]{project}[/]"
            )
            return

        if usage:
            provider = usage.get("provider", "?")
            model = (usage.get("model", "?") or "")[:20]
            tokens = usage.get("total_tokens") or 0
            cost = _format_money(usage.get("estimated_cost_usd"))
            bar.update(
                f"[dim]{provider}[/] [bold]{model}[/] [dim]{tokens} tok[/] "
                f"[{budget_color}]{cost}[/]"
            )
        else:
            short_id = self.conversation_id.removeprefix("chat_")[-12:]
            project = self.project_name or "no project"
            bar.update(
                f"[dim]DevSynapse AI[/] [bold {self._state_color('success')}]ready[/]  "
                f"budget:[{budget_color}]{budget_str}[/]  "
                f"[dim]project:{project} session:{short_id}[/]"
            )


def run_tui():
    app = DevSynapseTUI()
    app.run()
