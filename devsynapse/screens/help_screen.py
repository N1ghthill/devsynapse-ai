"""Help overlay screen for DevSynapse AI TUI."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

CATEGORIES = {
    "Setup": [
        ("/connect", "provider setup"),
        ("/connect <provider>", "setup specific provider"),
        ("/connect <provider> <key>", "quick setup with API key"),
        ("/providers", "show configured provider status"),
    ],
    "Model": [
        ("/model", "choose active model"),
        ("/model <provider>", "choose model from provider"),
        ("/models", "list all known models"),
        ("/models <provider>", "list models from provider"),
        ("/discover", "refresh model catalog"),
    ],
    "Session": [
        ("/status", "show runtime status"),
        ("/mode build|plan", "switch agent mode"),
        ("/new", "start new conversation"),
        ("/clear", "clear current chat"),
    ],
    "Workspace": [
        ("/projects", "list registered workspaces"),
        ("/project <path|name>", "set workspace"),
        ("/project", "clear workspace"),
    ],
    "Ops": [
        ("/usage", "token and cost telemetry"),
        ("/budget", "daily/monthly budget status"),
        ("/budget daily <usd>", "set daily budget"),
        ("/budget monthly <usd>", "set monthly budget"),
        ("/router", "manual model routing status"),
    ],
    "Chat": [
        ("/copy", "copy last assistant answer"),
        ("/details", "toggle detailed tool output"),
    ],
    "View": [
        ("/theme", "show current theme/layout"),
        ("/theme dracula dense", "switch TUI theme and density"),
        ("/theme dracula dense 5000", "set rendered chat history"),
    ],
    "Shell": [
        ("!<command>", "run shell command"),
        ("/help", "show this help"),
        ("/exit", "close DevSynapse"),
    ],
    "Mouse": [
        ("Wheel", "scroll chat, sidebars and lists"),
        ("Click suggestion", "select command suggestions"),
        ("Click palette row", "select command palette results"),
        ("Click input", "return focus to message input"),
    ],
}

SHORTCUTS = [
    ("F2", "open model picker"),
    ("F3", "copy last response"),
    ("F4", "toggle model sidebar panel"),
    ("F5", "toggle telemetry sidebar panel"),
    ("Ctrl+N", "new conversation"),
    ("Ctrl+L", "clear chat"),
    ("Ctrl+P", "open command palette"),
    ("Ctrl+R", "refresh status"),
    ("Ctrl+H", "show help"),
    ("Ctrl+Space", "command menu"),
    ("PageUp/Down", "scroll chat"),
    ("Ctrl+Home/End", "chat top/bottom"),
    ("Up/Down", "history or menu"),
    ("Ctrl+K/J", "history or menu"),
    ("Tab", "mode on empty input, autocomplete otherwise"),
    ("Esc", "close menu/modal"),
]


class HelpScreen(ModalScreen[None]):
    """Help overlay screen with categorized commands."""

    def __init__(self) -> None:
        super().__init__()
        self._current_category = "Setup"

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            with Horizontal(id="help-header"):
                yield Label("DevSynapse AI Help", id="help-title")
            with Horizontal(id="help-content"):
                with Vertical(id="help-categories"):
                    for category in CATEGORIES.keys():
                        yield Button(
                            category,
                            id=f"cat-{category}",
                            classes="category-button",
                        )
                with Vertical(id="help-commands"):
                    yield Static("", id="commands-content")
            with Vertical(id="help-shortcuts"):
                yield Static("", id="shortcuts-content")
            with Horizontal(id="help-footer"):
                yield Button("Close", id="help-close", variant="primary")

    async def on_mount(self) -> None:
        await self._show_category(self._current_category)
        await self._update_shortcuts()
        self.query_one(f"#cat-{self._current_category}", Button).has_focus = True

    async def _show_category(self, category: str) -> None:
        self._current_category = category
        commands = CATEGORIES.get(category, [])

        for btn in self.query(".category-button"):
            btn.remove_class("active")
            if btn.id == f"cat-{category}":
                btn.add_class("active")

        title = self._color("title")
        accent = self._color("streaming")
        muted = self._color("muted")
        lines = [f"[bold {title}]{category}[/]", ""]
        for cmd, desc in commands:
            lines.append(f"[{accent}]{cmd:<25}[/] [{muted}]{desc}[/]")

        commands_panel = self.query_one("#commands-content", Static)
        commands_panel.update("\n".join(lines))

    async def _update_shortcuts(self) -> None:
        title = self._color("title")
        accent = self._color("streaming")
        muted = self._color("muted")
        lines = [f"[bold {title}]Keyboard Shortcuts[/]  "]
        for key, desc in SHORTCUTS:
            lines.append(f"[{accent}]{key:<10}[/] [{muted}]{desc}[/]  ")

        shortcuts_panel = self.query_one("#shortcuts-content", Static)
        shortcuts_panel.update("  ".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss()
            return

        if event.button.id and event.button.id.startswith("cat-"):
            category = event.button.id[4:]
            self.run_task(self._show_category(category))

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss()
        elif event.key == "tab":
            categories = list(CATEGORIES.keys())
            current_idx = categories.index(self._current_category)
            next_idx = (current_idx + 1) % len(categories)
            self.run_task(self._show_category(categories[next_idx]))
        elif event.key == "shift+tab":
            categories = list(CATEGORIES.keys())
            current_idx = categories.index(self._current_category)
            prev_idx = (current_idx - 1) % len(categories)
            self.run_task(self._show_category(categories[prev_idx]))

    def _color(self, name: str) -> str:
        app = self.app
        preferences = getattr(app, "ui_preferences", None)
        palette = getattr(preferences, "palette", {}) or {}
        fallbacks = {
            "title": "thinking",
            "streaming": "streaming",
            "muted": "muted",
        }
        key = name if name in palette else fallbacks.get(name, name)
        return palette.get(key, "cyan")
