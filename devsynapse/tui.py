"""
DevSynapse AI — Textual TUI (terminal chat interface).
"""

import importlib
import logging
import shlex
import sys
from pathlib import Path

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
from core.llm_discovery import fetch_openai_compatible_models, fetch_openrouter_models
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge
from core.plugin_system import plugin_manager
from core.runtime_config import ensure_runtime_config_file, set_runtime_config_values

logger = logging.getLogger(__name__)


PROVIDER_ENV_KEYS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "opencode-zen": "OPENCODE_ZEN_API_KEY",
    "zen": "OPENCODE_ZEN_API_KEY",
    "opencode-go": "OPENCODE_GO_API_KEY",
    "go": "OPENCODE_GO_API_KEY",
}


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
        width: 32;
        min-width: 28;
        background: $panel;
        border-left: solid $border;
        padding: 1;
        overflow: hidden;
    }

    #chat {
        height: 1fr;
        border: none;
        padding: 1 2;
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
        border: round $border;
        background: $boost;
    }

    #session-panel {
        height: 7;
    }

    #providers-panel {
        height: 7;
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
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_chat", "Clear"),
        Binding("ctrl+h", "show_help", "Help"),
        Binding("ctrl+n", "new_session", "New"),
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
                    "Use [bold]/connect deepseek <api-key>[/] or "
                    "[bold]/connect openrouter <api-key>[/]."
                )
                self._update_status_bar()
            else:
                self._write_welcome()
                chat.write(
                    "[green]Ready.[/] Type a task, [bold]/help[/], [bold]/models[/], "
                    "[bold]/budget[/], [bold]/router[/] or [bold]/usage[/]."
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
        chat.write("Chat is ready. Use commands from the input line below.")
        chat.write(
            "Try [bold]/help[/], [bold]/connect[/], [bold]/budget[/], "
            "[bold]/router[/] or [bold]/usage[/]."
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
        return any(
            [
                settings.deepseek_api_key,
                settings.openrouter_api_key,
                settings.opencode_zen_api_key,
                settings.opencode_go_api_key,
            ]
        )

    def _refresh_sidebar(self) -> None:
        try:
            settings = app_settings.get_settings()
            project_count = len(self.memory.get_project_lookup()) if self.memory else 0
            budget = self.memory.get_llm_budget_status() if self.memory else {}
            budget_status = budget.get("overall_status", "unknown")
            provider_count = sum(
                bool(value)
                for value in (
                    settings.deepseek_api_key,
                    settings.openrouter_api_key,
                    settings.opencode_zen_api_key,
                    settings.opencode_go_api_key,
                )
            )
            short_conversation_id = self.conversation_id.removeprefix("chat_")

            self.query_one("#session-panel", Static).update(
                "\n".join(
                    [
                        "[bold accent]Session[/]",
                        f"chat: {short_conversation_id}",
                        f"project: {self.project_name or 'none'}",
                        f"projects: {project_count}  budget: {budget_status}",
                        f"details: {'on' if self.details_enabled else 'off'}",
                    ]
                )
            )
            self.query_one("#providers-panel", Static).update(
                "\n".join(
                    [
                        "[bold accent]Providers[/]",
                        f"configured: {provider_count}",
                        f"deep: {_mask_secret(settings.deepseek_api_key)}",
                        f"open: {_mask_secret(settings.openrouter_api_key)}",
                        f"zen:  {_mask_secret(settings.opencode_zen_api_key)}",
                        f"go:   {_mask_secret(settings.opencode_go_api_key)}",
                    ]
                )
            )
            self.query_one("#commands-panel", Static).update(
                "\n".join(
                    [
                        "[bold accent]Commands[/]",
                        "/help     list commands",
                        "/status   runtime",
                        "/project  active project",
                        "/usage    telemetry",
                        "/budget   budget",
                        "/router   routing",
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

    async def on_input_submitted(self, event):
        task = event.value.strip()
        if not task:
            return

        input_w = self._input()
        chat = self._chat()

        input_w.clear()
        input_w.disabled = True
        self._update_status_bar(message="busy")

        chat.write(f"\n[bold]# you:[/] {task}")

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
                "Use [bold]/connect deepseek <api-key>[/] or "
                "[bold]/connect openrouter <api-key>[/].\n"
            )
            input_w.disabled = False
            input_w.focus()
            self._update_status_bar()
            return

        await self._process(task, chat, input_w)

    async def _process(self, task, chat, input_w):
        try:
            response_text, command, usage = await self.brain.process_message(
                user_message=task,
                conversation_id=self.conversation_id,
                project_name=self.project_name,
                user_id="tui",
                user_role="admin",
                auto_execute=True,
            )

            if response_text:
                chat.write(response_text)
                chat.write("")

            if command:
                chat.write(f"[yellow]command: {command}[/]")

            if usage:
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
            "models": self._cmd_models,
            "discover": self._cmd_discover,
            "usage": self._cmd_usage,
            "budget": self._cmd_budget,
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
        success, message, output, status, reason_code, _project_name = result
        color = "green" if success else "red"
        chat.write(f"[{color}]! {status}[/] {message}")
        if reason_code:
            chat.write(f"[yellow]reason:[/] {reason_code}")
        if output:
            chat.write(output)
        self._refresh_sidebar()

    async def _cmd_help(self, _args: list[str]) -> None:
        self._show_help()

    def _show_help(self) -> None:
        chat = self._chat()
        chat.write("[bold]DevSynapse commands[/]")
        chat.write("  /connect                         show configured providers")
        chat.write("  /connect <provider> <api-key>    save provider key")
        chat.write("  /providers                       show provider key status")
        chat.write("  /status                          show runtime status")
        chat.write("  /projects                        list registered projects")
        chat.write("  /project <name>                  set active project")
        chat.write("  /project                         clear active project")
        chat.write("  /discover                        refresh model catalog")
        chat.write("  /models [provider]               list model catalog")
        chat.write("  /budget                          show usage plan and limits")
        chat.write("  /budget daily|monthly <usd>      set budget limit")
        chat.write("  /budget warning|critical <pct>   set thresholds")
        chat.write("  /router                          show routing policy")
        chat.write("  /router on|off                   enable or disable model routing")
        chat.write("  /router economy on|off           enable or disable automatic economy")
        chat.write("  /router adaptive on|off          enable or disable cheapest-model override")
        chat.write("  /usage                           show recent provider/model telemetry")
        chat.write("  /details                         toggle route/tool detail display")
        chat.write("  /new                             start a new conversation")
        chat.write("  !<command>                       run shell command as a tool result")

    async def _cmd_status(self, _args: list[str]) -> None:
        chat = self._chat()
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        settings = app_settings.get_settings()
        budget = self.memory.get_llm_budget_status()
        chat.write("[bold]Status[/]")
        chat.write(f"  conversation: {self.conversation_id}")
        chat.write(f"  project: {self.project_name or 'none'}")
        chat.write(f"  providers: {'configured' if self._has_provider_key(settings) else 'missing'}")
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
        if len(args) < 2:
            await self._cmd_providers([])
            chat.write("[yellow]Usage:[/] /connect deepseek <api-key>")
            chat.write("Providers: deepseek, openrouter, opencode-zen, opencode-go")
            return

        provider = args[0].lower()
        env_key = PROVIDER_ENV_KEYS.get(provider)
        if env_key is None:
            chat.write(f"[red]Unknown provider:[/] {provider}")
            return

        api_key = args[1].strip()
        try:
            set_runtime_config_values({env_key: api_key})
            await self._rebuild_engine()
        except Exception as exc:
            chat.write(f"[red]Could not save provider key:[/] {exc}")
            logger.exception("Could not save provider key")
            return

        chat.write(f"[green]Saved[/] {env_key} = {_mask_secret(api_key)}")
        chat.write("Use [bold]/discover[/] to refresh available model data.")

    async def _cmd_providers(self, _args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        settings = app_settings.get_settings()
        chat.write("[bold]Providers[/]")
        chat.write(f"  deepseek      {_mask_secret(settings.deepseek_api_key)}")
        chat.write(f"  openrouter    {_mask_secret(settings.openrouter_api_key)}")
        chat.write(f"  opencode-zen  {_mask_secret(settings.opencode_zen_api_key)}")
        chat.write(f"  opencode-go   {_mask_secret(settings.opencode_go_api_key)}")

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

        if discovered:
            count = self.memory.upsert_llm_models(discovered)
            chat.write(f"[green]Model catalog updated:[/] {count} models")
        else:
            chat.write("[yellow]No remote model catalog discovered.[/]")
            chat.write("Configure OpenRouter or OpenCode Go first with /connect.")

        for error in errors:
            chat.write(f"[red]{error}[/]")

    async def _cmd_models(self, args: list[str]) -> None:
        chat = self.query_one("#chat", RichLog)
        if self.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        provider = args[0] if args else None
        models = self.memory.list_llm_models(provider=provider, limit=25)
        if not models:
            chat.write(
                "[yellow]No models in catalog.[/] "
                "Use /discover after connecting a provider."
            )
            return

        chat.write("[bold]Model catalog[/]")
        for model in models:
            input_cost = model.get("input_cost_per_token")
            output_cost = model.get("output_cost_per_token")
            cost = "unknown"
            if input_cost is not None and output_cost is not None:
                input_per_million = float(input_cost) * 1_000_000
                output_per_million = float(output_cost) * 1_000_000
                cost = f"in ${input_per_million:.4f}/M out ${output_per_million:.4f}/M"
            context = model.get("context_length") or "?"
            name = model.get("name") or model["model_id"]
            chat.write(
                f"  {model['provider']}:{model['model_id']}  ctx {context}  {cost}  {name}"
            )

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
            updates = self._router_updates_from_args(args)
            if updates is None:
                chat.write(
                    "[yellow]Usage:[/] /router on|off | /router economy on|off | "
                    "/router adaptive on|off"
                )
                return
            self.memory.update_app_settings(updates)
            chat.write("[green]Router settings saved.[/]")

        settings = app_settings.get_settings()
        persisted = self.memory.get_app_settings()
        routing_enabled = self._setting_bool(
            persisted,
            "llm_model_routing_enabled",
            settings.llm_model_routing_enabled,
        )
        economy_enabled = self._setting_bool(
            persisted,
            "llm_auto_economy_enabled",
            settings.llm_auto_economy_enabled,
        )
        adaptive_enabled = self._setting_bool(persisted, "llm_adaptive_routing_enabled", True)
        budget = self.memory.get_llm_budget_status()
        learning = self.memory.get_agent_learning_stats()
        models = self.memory.list_llm_models(limit=200)
        priced_models = [
            model for model in models
            if model.get("enabled")
            and model.get("input_cost_per_token") is not None
            and model.get("output_cost_per_token") is not None
        ]

        chat.write("[bold]Router[/]")
        chat.write(f"  routing: {'on' if routing_enabled else 'off'}")
        chat.write(f"  auto economy: {'on' if economy_enabled else 'off'}")
        chat.write(f"  adaptive cheapest: {'on' if adaptive_enabled else 'off'}")
        chat.write(f"  budget status: {budget['overall_status']}")
        chat.write(
            f"  flash: {persisted.get('deepseek_flash_model', settings.deepseek_flash_model)}"
        )
        chat.write(f"  pro: {persisted.get('deepseek_pro_model', settings.deepseek_pro_model)}")
        chat.write(f"  learned task patterns: {learning.get('total_patterns', 0)}")
        chat.write(f"  priced catalog models: {len(priced_models)}")
        if priced_models:
            cheapest = min(
                priced_models,
                key=lambda model: float(model["input_cost_per_token"])
                + float(model["output_cost_per_token"]),
            )
            chat.write(f"  cheapest known: {cheapest['provider']}:{cheapest['model_id']}")

    def _router_updates_from_args(self, args: list[str]) -> dict[str, object] | None:
        if len(args) == 1 and args[0].lower() in {"on", "off"}:
            return {"llm_model_routing_enabled": args[0].lower() == "on"}
        if (
            len(args) == 2
            and args[0].lower() in {"economy", "adaptive"}
            and args[1].lower() in {"on", "off"}
        ):
            key = (
                "llm_auto_economy_enabled"
                if args[0].lower() == "economy"
                else "llm_adaptive_routing_enabled"
            )
            return {key: args[1].lower() == "on"}
        return None

    @staticmethod
    def _setting_bool(persisted: dict, key: str, default: bool) -> bool:
        value = persisted.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

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
            bool(value)
            for value in (
                settings.deepseek_api_key,
                settings.openrouter_api_key,
                settings.opencode_zen_api_key,
                settings.opencode_go_api_key,
            )
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
            bar.update(
                f" providers:{provider_count}  budget:{budget['overall_status']}  "
                f"project:{project}  conversation:{self.conversation_id}"
            )


def run_tui():
    app = DevSynapseTUI()
    app.run()
