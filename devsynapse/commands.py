"""Slash command handlers for DevSynapse AI TUI."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import config.settings as app_settings
from core.llm_discovery import fetch_openai_compatible_models, fetch_openrouter_models
from devsynapse.tui_preferences import (
    ALLOWED_LAYOUTS,
    ALLOWED_THEMES,
    CHAT_MAX_LINES_MAX,
    CHAT_MAX_LINES_MIN,
)

if TYPE_CHECKING:
    from devsynapse.tui import DevSynapseTUI

logger = logging.getLogger(__name__)


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


class CommandDispatcher:
    """Dispatches slash commands for DevSynapseTUI."""

    def __init__(self, tui: DevSynapseTUI) -> None:
        self.tui = tui

    async def handle(self, raw: str) -> None:
        import shlex

        chat = self.tui._chat()
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
            "help": self.cmd_help,
            "h": self.cmd_help,
            "connect": self.cmd_connect,
            "providers": self.cmd_providers,
            "status": self.cmd_status,
            "projects": self.cmd_projects,
            "project": self.cmd_project,
            "model": self.cmd_model,
            "models": self.cmd_models,
            "discover": self.cmd_discover,
            "usage": self.cmd_usage,
            "budget": self.cmd_budget,
            "theme": self.cmd_theme,
            "copy": self.cmd_copy,
            "router": self.cmd_router,
            "details": self.cmd_details,
            "new": self.cmd_new,
            "clear": self.cmd_clear,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
            "q": self.cmd_exit,
        }
        handler = handlers.get(command)
        if handler is None:
            chat.write(f"[red]Unknown command:[/] /{command}. Type [bold]/help[/].")
            return
        await handler(args)

    async def cmd_help(self, _args: list[str]) -> None:
        from devsynapse.screens.help_screen import HelpScreen
        await self.tui.push_screen(HelpScreen())

    async def cmd_copy(self, _args: list[str]) -> None:
        chat = self.tui._chat()
        if not self.tui.last_response_text.strip():
            chat.write("[yellow]No assistant answer to copy yet.[/]")
            return
        try:
            self.tui.copy_to_clipboard(self.tui.last_response_text)
        except Exception as exc:
            chat.write(f"[red]Could not copy answer:[/] {exc}")
            logger.exception("Could not copy assistant answer")
            return
        chat.write("[green]Copied last assistant answer.[/]")

    async def cmd_status(self, _args: list[str]) -> None:
        chat = self.tui._chat()
        if self.tui.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        settings = app_settings.get_settings()
        budget = self.tui.memory.get_llm_budget_status()
        default_provider = _normalize_provider(settings.llm_default_provider) or "deepseek"
        chat.write("[bold]Status[/]")
        chat.write(f"  conversation: {self.tui.conversation_id}")
        chat.write(f"  project: {self.tui.project_name or 'none'}")
        chat.write(f"  providers: {'configured' if self.tui._has_provider_key(settings) else 'missing'}")
        chat.write(f"  default provider: {default_provider}")
        chat.write(f"  default model: {_provider_model(settings, default_provider)}")
        if self.tui.last_provider and self.tui.last_model:
            chat.write(f"  last response: {self.tui.last_provider}:{self.tui.last_model}")
        chat.write(f"  budget: {budget['overall_status']}")
        chat.write(f"  projects: {len(self.tui.memory.get_project_lookup())}")
        self.tui._update_status_bar()
        self.tui._refresh_sidebar()

    async def cmd_projects(self, _args: list[str]) -> None:
        chat = self.tui._chat()
        if self.tui.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        projects = self.tui.memory.get_project_lookup()
        if not projects:
            chat.write("[yellow]No registered projects.[/]")
            return
        chat.write("[bold]Projects[/]")
        for name, project in sorted(projects.items()):
            marker = "*" if name == self.tui.project_name else " "
            chat.write(f"{marker} {name}  {project.get('path', '')}")

    async def cmd_project(self, args: list[str]) -> None:
        chat = self.tui._chat()
        if not args:
            self.tui.project_name = None
            chat.write("[green]Project cleared.[/]")
            self.tui._update_status_bar()
            self.tui._refresh_sidebar()
            return
        project_name = args[0]
        if self.tui.memory is not None and project_name not in self.tui.memory.get_project_lookup():
            chat.write(f"[yellow]Project not registered:[/] {project_name}")
            chat.write("Use [bold]/projects[/] to list known projects.")
            return
        self.tui.project_name = project_name
        chat.write(f"[green]Project set:[/] {project_name}")
        self.tui._update_status_bar()
        self.tui._refresh_sidebar()

    async def cmd_connect(self, args: list[str]) -> None:
        chat = self.tui._chat()
        if not args:
            await self.tui._open_connect_screen()
            return
        if len(args) == 1:
            await self.tui._open_connect_screen(args[0])
            return

        provider = _normalize_provider(args[0])
        if provider not in PROVIDER_CONFIGS:
            chat.write(f"[red]Unknown provider:[/] {provider}")
            return

        api_key = args[1].strip()
        model = args[2].strip() if len(args) >= 3 else ""
        try:
            await self.tui._save_provider_credentials(provider, api_key, model)
        except Exception as exc:
            chat.write(f"[red]Could not save provider key:[/] {exc}")
            logger.exception("Could not save provider key")
            return

        env_key = PROVIDER_CONFIGS[provider]["env_key"]
        chat.write(f"[green]Saved[/] {env_key} = {_mask_secret(api_key)}")
        chat.write(f"[green]Default provider:[/] {provider}")
        chat.write("Use [bold]/discover[/] to refresh available model data.")

    async def cmd_providers(self, _args: list[str]) -> None:
        chat = self.tui._chat()
        settings = app_settings.get_settings()
        default_provider = _normalize_provider(settings.llm_default_provider) or "deepseek"
        chat.write("[bold]Providers[/]")
        for provider, config in PROVIDER_CONFIGS.items():
            marker = "*" if provider == default_provider else " "
            key_status = _mask_secret(_provider_key(settings, provider))
            model = _provider_model(settings, provider)
            chat.write(f"{marker} {provider:<12} {key_status:<12} model {model}")
        chat.write("Use [bold]/connect[/] to edit providers.")

    async def cmd_discover(self, _args: list[str]) -> None:
        chat = self.tui._chat()
        if self.tui.memory is None:
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
            count = self.tui.memory.upsert_llm_models(curated)
            chat.write(
                f"[green]Model catalog updated:[/] {count} principal models "
                f"({len(discovered)} discovered)"
            )
        else:
            chat.write("[yellow]No remote model catalog discovered.[/]")
            chat.write("Configure OpenRouter or OpenCode Go first with /connect.")

        for error in errors:
            chat.write(f"[red]{error}[/]")

    async def cmd_model(self, args: list[str]) -> None:
        provider = args[0] if args else None
        await self.tui._open_model_screen(provider)

    async def cmd_models(self, args: list[str]) -> None:
        chat = self.tui._chat()
        if self.tui.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return
        provider = args[0] if args else None
        models = _sort_models_for_ui(self.tui.memory.list_llm_models(provider=provider, limit=80))
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

    async def cmd_usage(self, _args: list[str]) -> None:
        chat = self.tui._chat()
        if self.tui.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return

        usage = self.tui.memory.get_llm_usage_stats(hours=24)
        totals = usage.get("totals", {})
        telemetry = self.tui.memory.get_llm_telemetry_stats(hours=24)
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

    async def cmd_budget(self, args: list[str]) -> None:
        chat = self.tui._chat()
        if self.tui.memory is None:
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
            self.tui.memory.update_app_settings({setting_key: value})
            chat.write(f"[green]Saved[/] {setting_key} = {value}")

        budget = self.tui.memory.get_llm_budget_status()
        chat.write(f"[bold]Budget[/] overall: {budget['overall_status']}")
        for window in ("daily", "monthly"):
            item = budget[window]
            chat.write(
                f"  {window}: {item['level']}  "
                f"{_format_money(item['actual_cost_usd'])}/{_format_money(item['budget_usd'])}  "
                f"{float(item['usage_pct']):.2f}%"
            )
        self.tui._update_status_bar()

    async def cmd_router(self, args: list[str]) -> None:
        chat = self.tui._chat()
        if self.tui.memory is None:
            chat.write("[red]Memory is not initialized.[/]")
            return

        if args:
            chat.write("[yellow]Automatic routing has been removed.[/]")
            chat.write("Use [bold]/model[/] to choose exactly which model DevSynapse uses.")

        settings = app_settings.get_settings()
        budget = self.tui.memory.get_llm_budget_status()
        models = self.tui.memory.list_llm_models(limit=200)
        default_provider = _normalize_provider(settings.llm_default_provider) or "deepseek"

        chat.write("[bold]Model Control[/]")
        chat.write("  mode: manual")
        chat.write("  automatic routing: removed")
        chat.write(f"  provider: {default_provider}")
        chat.write(f"  model: {_provider_model(settings, default_provider)}")
        chat.write(f"  budget status: {budget['overall_status']}")
        chat.write(f"  catalog models: {len(models)}")
        chat.write("Use [bold]/model[/] to search and change the active model.")

    async def cmd_details(self, _args: list[str]) -> None:
        self.tui.details_enabled = not self.tui.details_enabled
        chat = self.tui._chat()
        chat.write(f"[green]Details:[/] {'on' if self.tui.details_enabled else 'off'}")

    async def cmd_theme(self, args: list[str]) -> None:
        chat = self.tui._chat()
        current = self.tui.ui_preferences
        if not args:
            chat.write("[bold]TUI Theme[/]")
            chat.write(f"  theme: {current.theme}")
            chat.write(f"  layout: {current.layout}")
            chat.write(f"  chat max lines: {current.chat_max_lines}")
            chat.write("  usage: /theme dark|light|dracula [default|dense] [max-lines]")
            return

        theme = args[0].strip().lower()
        layout = args[1].strip().lower() if len(args) >= 2 else current.layout
        chat_max_lines = current.chat_max_lines
        if theme not in ALLOWED_THEMES:
            chat.write("[yellow]Usage:[/] /theme dark|light|dracula [default|dense] [max-lines]")
            return
        if layout not in ALLOWED_LAYOUTS:
            chat.write("[yellow]Layout must be:[/] default or dense")
            return
        if len(args) >= 3:
            try:
                chat_max_lines = int(args[2])
            except ValueError:
                chat.write("[yellow]Max lines must be an integer.[/]")
                return
            if not CHAT_MAX_LINES_MIN <= chat_max_lines <= CHAT_MAX_LINES_MAX:
                chat.write(
                    f"[yellow]Max lines must be between {CHAT_MAX_LINES_MIN} "
                    f"and {CHAT_MAX_LINES_MAX}.[/]"
                )
                return

        state = self.tui.apply_tui_preferences(
            theme=theme,
            layout=layout,
            chat_max_lines=chat_max_lines,
        )
        chat.write(f"[green]Theme {state}:[/] {theme}/{layout}  max lines {chat_max_lines}")
        chat.write(f"[dim]Config:[/] {self.tui.ui_preferences.config_file}")

    async def cmd_new(self, _args: list[str]) -> None:
        from core.correlation import generate_conversation_id

        self.tui.conversation_id = generate_conversation_id()
        chat = self.tui._chat()
        chat.clear()
        chat.write(f"[green]New conversation:[/] {self.tui.conversation_id}")
        self.tui._refresh_sidebar()

    async def cmd_clear(self, _args: list[str]) -> None:
        self.tui._chat().clear()
        self.tui._write_welcome()
        self.tui._refresh_sidebar()

    async def cmd_exit(self, _args: list[str]) -> None:
        self.tui.exit()
