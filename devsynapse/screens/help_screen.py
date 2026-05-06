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
        ("/new", "start new conversation"),
        ("/clear", "clear current chat"),
    ],
    "Project": [
        ("/projects", "list registered projects"),
        ("/project <name>", "set active project"),
        ("/project", "clear active project"),
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
    ("Tab", "autocomplete"),
    ("Esc", "close menu/modal"),
]


class HelpScreen(ModalScreen[None]):
    """Help overlay screen with categorized commands."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #help-container {
        width: 80;
        height: 80%;
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
    }

    #help-header {
        height: 3;
        background: #0d1117;
        border-bottom: solid #30363d;
        padding: 1 0;
    }

    #help-title {
        text-style: bold;
        color: #58a6ff;
    }

    #help-content {
        height: 1fr;
        layout: horizontal;
    }

    #help-categories {
        width: 30;
        border-right: solid #30363d;
        padding-right: 1;
    }

    .category-button {
        width: 100%;
        height: 3;
        background: #21262d;
        border: none;
        margin-bottom: 1;
        text-align: left;
    }

    .category-button:focus {
        background: #30363d;
    }

    .category-button.active {
        background: #58a6ff;
    }

    #help-commands {
        width: 1fr;
        padding-left: 1;
    }

    #help-shortcuts {
        height: 8;
        border-top: solid #30363d;
        background: #0d1117;
        padding: 1;
    }

    .shortcut-key {
        color: #58a6ff;
        text-style: bold;
    }

    .shortcut-desc {
        color: #8b949e;
    }

    #help-footer {
        height: 2;
        background: #0d1117;
        border-top: solid #30363d;
        padding: 0 1;
    }

    #help-footer Button {
        margin-left: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_category = "Setup"

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            with Horizontal(id="help-header"):
                yield Label("[bold #58a6ff]DevSynapse AI Help[/]", id="help-title")
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

        lines = [f"[bold #58a6ff]{category}[/]", ""]
        for cmd, desc in commands:
            lines.append(f"[cyan]{cmd:<25}[/] [dim]{desc}[/]")

        commands_panel = self.query_one("#commands-content", Static)
        commands_panel.update("\n".join(lines))

    async def _update_shortcuts(self) -> None:
        lines = ["[bold #58a6ff]Keyboard Shortcuts[/]  "]
        for key, desc in SHORTCUTS:
            lines.append(f"[#58a6ff]{key:<10}[/] [#8b949e]{desc}[/]  ")

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
