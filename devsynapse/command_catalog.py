"""Slash command catalog and completion helpers for the TUI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CommandSpec:
    """A command exposed in the canonical Textual TUI."""

    name: str
    usage: str
    description: str
    category: str
    menu_priority: int = 50
    aliases: tuple[str, ...] = ()
    accepts_args: bool = False


@dataclass(frozen=True)
class CommandSuggestion:
    """A concrete completion candidate for the input command menu."""

    value: str
    label: str
    description: str
    category: str


COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "connect", "/connect <provider>", "provider setup", "Setup", 10, accepts_args=True
    ),
    CommandSpec("providers", "/providers", "provider status", "Setup", 11),
    CommandSpec(
        "model", "/model <provider>", "choose active model", "Model", 20, accepts_args=True
    ),
    CommandSpec("models", "/models <provider>", "model catalog", "Model", 21, accepts_args=True),
    CommandSpec("discover", "/discover", "refresh catalog", "Model", 22),
    CommandSpec("status", "/status", "runtime status", "Session", 30),
    CommandSpec("projects", "/projects", "registered projects", "Project", 40),
    CommandSpec(
        "project", "/project <name>", "set active project", "Project", 41, accepts_args=True
    ),
    CommandSpec("usage", "/usage", "token and cost telemetry", "Ops", 50),
    CommandSpec(
        "budget", "/budget <target> <value>", "budget limits", "Ops", 51, accepts_args=True
    ),
    CommandSpec("router", "/router", "manual model status", "Ops", 52),
    CommandSpec("details", "/details", "toggle details", "View", 60),
    CommandSpec(
        "theme", "/theme <theme> <layout>", "TUI theme and density", "View", 61, accepts_args=True
    ),
    CommandSpec("copy", "/copy", "copy last answer", "Chat", 70),
    CommandSpec("new", "/new", "new conversation", "Chat", 71),
    CommandSpec("clear", "/clear", "clear conversation", "Chat", 72),
    CommandSpec("help", "/help", "command reference", "Help", 80, aliases=("h",)),
    CommandSpec("exit", "/exit", "close DevSynapse", "App", 90),
    CommandSpec("quit", "/quit", "close DevSynapse", "App", 91, aliases=("q",)),
)

CATEGORY_ORDER = {
    "Setup": 10,
    "Model": 20,
    "Session": 30,
    "Project": 40,
    "Ops": 50,
    "View": 60,
    "Chat": 70,
    "Help": 80,
    "App": 90,
}

PROVIDER_VALUES: tuple[tuple[str, str], ...] = (
    ("deepseek", "DeepSeek"),
    ("openrouter", "OpenRouter"),
    ("opencode-zen", "OpenCode Zen"),
    ("opencode-go", "OpenCode Go"),
)

PROVIDER_ALIASES: tuple[tuple[str, str], ...] = (
    ("zen", "OpenCode Zen"),
    ("go", "OpenCode Go"),
    ("opencode", "OpenCode Zen"),
)

BUDGET_TARGETS: tuple[tuple[str, str], ...] = (
    ("daily", "daily USD limit"),
    ("monthly", "monthly USD limit"),
    ("warning", "warning percentage threshold"),
    ("critical", "critical percentage threshold"),
)

THEME_VALUES: tuple[tuple[str, str], ...] = (
    ("dark", "GitHub-inspired dark theme"),
    ("light", "light theme"),
    ("dracula", "high-contrast Dracula-like theme"),
)

LAYOUT_VALUES: tuple[tuple[str, str], ...] = (
    ("default", "comfortable spacing"),
    ("dense", "compact terminal layout"),
)

SLASH_COMMANDS: tuple[str, ...] = tuple(f"/{spec.name}" for spec in COMMAND_SPECS)


def find_command_spec(command: str) -> CommandSpec | None:
    """Return the command spec matching a canonical command or alias."""
    normalized = command.strip().lower().removeprefix("/")
    for spec in COMMAND_SPECS:
        if normalized == spec.name or normalized in spec.aliases:
            return spec
    return None


def slash_command_help_lines() -> list[str]:
    """Return formatted help lines for the slash command catalog."""
    lines: list[str] = []
    current_category = ""
    for spec in sorted(
        COMMAND_SPECS,
        key=lambda item: (CATEGORY_ORDER.get(item.category, 999), item.menu_priority),
    ):
        if spec.category != current_category:
            current_category = spec.category
            lines.append(f"[bold]{current_category}[/]")
        lines.append(f"  {spec.usage:<28} {spec.description}")
    return lines


def build_command_suggestions(
    value: str,
    *,
    project_names: Iterable[str] = (),
    limit: int = 6,
) -> list[CommandSuggestion]:
    """Build contextual command completion suggestions for the TUI input."""
    if not value.startswith("/"):
        return []

    body = value[1:]
    has_trailing_space = value.endswith(" ")
    tokens = body.split()
    if not tokens:
        return _command_name_suggestions("", limit)

    command = tokens[0].lower()
    if len(tokens) == 1 and not has_trailing_space:
        return _command_name_suggestions(command, limit)

    spec = find_command_spec(command)
    if spec is None:
        return []

    arg_prefix = "" if has_trailing_space else tokens[-1].lower()
    arg_index = max(0, len(tokens) - 1)
    if has_trailing_space:
        arg_index += 1

    if spec.name in {"connect", "model", "models"} and arg_index <= 1:
        return _value_suggestions(
            f"/{spec.name}",
            arg_prefix,
            (*PROVIDER_VALUES, *PROVIDER_ALIASES),
            limit,
        )

    if spec.name == "budget" and arg_index <= 1:
        return _value_suggestions(f"/{spec.name}", arg_prefix, BUDGET_TARGETS, limit)

    if spec.name == "theme":
        if arg_index <= 1:
            return _value_suggestions(f"/{spec.name}", arg_prefix, THEME_VALUES, limit)
        if arg_index == 2:
            theme = tokens[1].lower() if len(tokens) > 1 else "dark"
            return _value_suggestions(f"/{spec.name} {theme}", arg_prefix, LAYOUT_VALUES, limit)

    if spec.name == "project" and arg_index <= 1:
        projects = tuple((name, "registered project") for name in sorted(project_names))
        clear = (("clear", "clear active project"),)
        return _value_suggestions(f"/{spec.name}", arg_prefix, (*clear, *projects), limit)

    return []


def _command_name_suggestions(prefix: str, limit: int) -> list[CommandSuggestion]:
    matches: list[tuple[int, int, CommandSuggestion]] = []
    for spec in COMMAND_SPECS:
        haystack = f"{spec.name} {spec.usage} {spec.description} {' '.join(spec.aliases)}"
        alias_starts = any(alias.startswith(prefix) for alias in spec.aliases)
        name_starts = spec.name.startswith(prefix)
        if prefix and prefix not in haystack.lower() and not name_starts and not alias_starts:
            continue
        value = f"/{spec.name} " if spec.accepts_args else f"/{spec.name}"
        score = 0 if not prefix or name_starts or alias_starts else 1
        matches.append(
            (
                score,
                spec.menu_priority,
                CommandSuggestion(
                    value=value,
                    label=spec.usage,
                    description=spec.description,
                    category=spec.category,
                ),
            )
        )
    matches.sort(key=lambda item: (item[0], item[1]))
    return [suggestion for _, _, suggestion in matches[:limit]]


def _value_suggestions(
    command: str,
    prefix: str,
    values: Iterable[tuple[str, str]],
    limit: int,
) -> list[CommandSuggestion]:
    suggestions: list[CommandSuggestion] = []
    for value, description in values:
        if prefix and not value.startswith(prefix):
            continue
        suggestions.append(
            CommandSuggestion(
                value=f"{command} {value} ",
                label=f"{command} {value}",
                description=description,
                category="Arg",
            )
        )
    return suggestions[:limit]
