"""Enhanced input widget with history and autocomplete for DevSynapse AI TUI."""
from __future__ import annotations

from textual.binding import Binding
from textual.widgets import Input, OptionList

from devsynapse.command_catalog import SLASH_COMMANDS, build_command_suggestions


class CommandSuggestionList(OptionList):
    """Suggestion menu that can be dismissed from keyboard focus."""

    BINDINGS = [
        Binding("escape", "dismiss", "Dismiss Menu", show=False, priority=True),
    ]

    def action_dismiss(self) -> None:
        app = self.app
        if hasattr(app, "_hide_command_suggestions"):
            app._hide_command_suggestions()
        if hasattr(app, "_input"):
            app._input().focus()


class EnhancedInput(Input):
    """Input widget with command history and autocomplete."""

    BINDINGS = [
        Binding("enter", "submit_or_accept", "Submit", show=False, priority=True),
        Binding("shift+enter", "insert_newline", "New Line", show=False, priority=True),
        Binding("up", "history_previous", "History Prev", show=False),
        Binding("down", "history_next", "History Next", show=False),
        Binding("ctrl+k", "history_previous", "History Prev", show=False, priority=True),
        Binding("ctrl+j", "history_next", "History Next", show=False, priority=True),
        Binding("tab", "autocomplete", "Autocomplete", show=False),
        Binding("escape", "dismiss_command_menu", "Dismiss Menu", show=False, priority=True),
        Binding("ctrl+space", "show_command_menu", "Commands", show=False),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._history: list[str] = []
        self._history_index: int = -1
        self._saved_value: str = ""

    def add_to_history(self, value: str) -> None:
        """Add a value to the command history."""
        if value and (not self._history or self._history[-1] != value):
            self._history.append(value)
            if len(self._history) > 100:
                self._history = self._history[-100:]
            self._history_index = len(self._history)

    def action_insert_newline(self) -> None:
        """Insert a newline character instead of submitting."""
        self.insert_text_at_cursor("\n")

    def action_history_previous(self) -> None:
        """Navigate to the previous command in history."""
        if self._command_menu_previous():
            return
        if not self._history:
            return
        if self._history_index == len(self._history):
            self._saved_value = self.value
        if self._history_index > 0:
            self._history_index -= 1
            self.value = self._history[self._history_index]
            self.cursor_position = len(self.value)

    def action_history_next(self) -> None:
        """Navigate to the next command in history."""
        if self._command_menu_next():
            return
        if not self._history:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.value = self._history[self._history_index]
        else:
            self._history_index = len(self._history)
            self.value = self._saved_value
        self.cursor_position = len(self.value)

    def action_autocomplete(self) -> None:
        """Autocomplete slash commands, paths, and bash commands."""
        if not self.value.strip():
            app = self.app
            if hasattr(app, "cycle_agent_mode"):
                app.cycle_agent_mode()
            return

        if self._command_menu_accept():
            return

        if self.value.startswith("/"):
            partial = self.value.lower()
            matches = [cmd for cmd in SLASH_COMMANDS if cmd.startswith(partial)]
            if len(matches) == 1:
                self.value = matches[0]
                self.cursor_position = len(self.value)
            elif len(matches) > 1:
                common_prefix = matches[0]
                for match in matches[1:]:
                    while not match.startswith(common_prefix):
                        common_prefix = common_prefix[:-1]
                if common_prefix != self.value:
                    self.value = common_prefix
                    self.cursor_position = len(self.value)
        elif self.value.startswith("!"):
            self._autocomplete_bash()

    def action_show_command_menu(self) -> None:
        """Open the contextual slash command menu."""
        if not self.value.startswith("/"):
            self.value = "/"
            self.cursor_position = 1
        app = self.app
        if hasattr(app, "refresh_command_suggestions"):
            app.refresh_command_suggestions(self.value, force=True)

    def action_dismiss_command_menu(self) -> None:
        """Close the contextual slash command menu."""
        app = self.app
        if hasattr(app, "_hide_command_suggestions"):
            app._hide_command_suggestions()

    async def action_submit_or_accept(self) -> None:
        """Accept the active menu suggestion before submitting the input."""
        if self._command_menu_accept():
            return
        await self.action_submit()

    def _command_menu_accept(self) -> bool:
        app = self.app
        if hasattr(app, "accept_command_suggestion"):
            return bool(app.accept_command_suggestion())
        return False

    def _command_menu_next(self) -> bool:
        app = self.app
        if hasattr(app, "move_command_suggestion"):
            return bool(app.move_command_suggestion(1))
        return False

    def _command_menu_previous(self) -> bool:
        app = self.app
        if hasattr(app, "move_command_suggestion"):
            return bool(app.move_command_suggestion(-1))
        return False

    def _autocomplete_bash(self) -> None:
        """Autocomplete common bash commands."""
        bash_commands = [
            "git", "ls", "cd", "pwd", "cat", "grep", "find",
            "npm", "node", "python", "python3", "make", "curl",
            "echo", "touch", "mkdir", "rm", "cp", "mv",
        ]
        partial = self.value[1:].strip().lower()
        if not partial:
            return
        matches = [cmd for cmd in bash_commands if cmd.startswith(partial)]
        if len(matches) == 1:
            self.value = f"!{matches[0]}"
            self.cursor_position = len(self.value)


def preview_autocomplete(value: str) -> str:
    """Return the first contextual completion for tests and non-Textual callers."""
    suggestions = build_command_suggestions(value, limit=1)
    return suggestions[0].value if suggestions else value
