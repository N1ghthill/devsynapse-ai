"""Command palette modal for slash commands."""
from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from devsynapse.command_catalog import COMMAND_SPECS, CommandSpec


@dataclass(frozen=True)
class PaletteItem:
    """A command palette result."""

    spec: CommandSpec
    value: str
    label: str
    description: str
    category: str
    score: int


class CommandPaletteScreen(ModalScreen[str | None]):
    """Searchable command palette."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "choose_highlighted", "Choose"),
    ]

    def __init__(self, initial_query: str = "") -> None:
        super().__init__()
        self.initial_query = initial_query
        self._items: list[PaletteItem] = []

    def compose(self) -> ComposeResult:
        yield Static("Command Palette", id="palette-title")
        yield Input(
            value=self.initial_query,
            placeholder="Search commands, for example theme, project, budget...",
            id="palette-search",
        )
        yield OptionList(id="palette-results")
        yield Static("Enter choose  Esc close", id="palette-help")

    async def on_mount(self) -> None:
        self._refresh(self.initial_query)
        self.query_one("#palette-search", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "palette-search":
            self._refresh(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "palette-search":
            self.action_choose_highlighted()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "palette-results":
            return
        event.stop()
        self._choose(event.index)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_choose_highlighted(self) -> None:
        results = self.query_one("#palette-results", OptionList)
        highlighted = results.highlighted if isinstance(results.highlighted, int) else 0
        self._choose(highlighted)

    def _choose(self, index: int | None) -> None:
        if index is None or index < 0 or index >= len(self._items):
            return
        self.dismiss(self._items[index].value)

    def _refresh(self, query: str) -> None:
        self._items = _palette_items(query)
        results = self.query_one("#palette-results", OptionList)
        results.clear_options()
        if not self._items:
            results.add_option(Option("[dim]No command found[/]", disabled=True))
            return
        results.add_options(
            [
                Option(
                    (
                        f"[dim]{item.category:<7}[/] "
                        f"[bold]{item.label:<28}[/] "
                        f"[dim]{item.description}[/]"
                    ),
                    id=f"palette-{index}",
                )
                for index, item in enumerate(self._items)
            ]
        )
        results.highlighted = 0


def _palette_items(query: str, limit: int = 12) -> list[PaletteItem]:
    words = [word for word in query.strip().lower().split() if word]
    items: list[PaletteItem] = []
    for spec in COMMAND_SPECS:
        value = f"/{spec.name} " if spec.accepts_args else f"/{spec.name}"
        haystack = " ".join(
            (
                spec.name,
                spec.usage,
                spec.description,
                spec.category,
                " ".join(spec.aliases),
            )
        ).lower()
        score = _score(spec, haystack, words)
        if score is None:
            continue
        items.append(
            PaletteItem(
                spec=spec,
                value=value,
                label=spec.usage,
                description=spec.description,
                category=spec.category,
                score=score,
            )
        )
    items.sort(key=lambda item: (item.score, item.spec.menu_priority, item.spec.name))
    return items[:limit]


def _score(spec: CommandSpec, haystack: str, words: list[str]) -> int | None:
    if not words:
        return spec.menu_priority
    score = 0
    for word in words:
        if spec.name.startswith(word):
            score += 0
        elif word in haystack:
            score += 10
        elif _is_subsequence(word, haystack):
            score += 30
        else:
            return None
    return score


def _is_subsequence(needle: str, haystack: str) -> bool:
    iterator = iter(haystack)
    return all(char in iterator for char in needle)
