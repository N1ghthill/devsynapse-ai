"""Extended tests for DevSynapse AI TUI input widget."""
from __future__ import annotations

from devsynapse.tui_input import (
    EnhancedInput,
    preview_autocomplete,
)


class TestEnhancedInputBindings:
    def test_has_submit_binding(self):
        bindings = {b.key: b.action for b in EnhancedInput.BINDINGS}
        assert "enter" in bindings
        assert bindings["enter"] == "submit_or_accept"

    def test_has_shift_enter_binding(self):
        bindings = {b.key: b.action for b in EnhancedInput.BINDINGS}
        assert "shift+enter" in bindings
        assert bindings["shift+enter"] == "insert_newline"

    def test_has_history_bindings(self):
        bindings = {b.key: b.action for b in EnhancedInput.BINDINGS}
        assert "up" in bindings
        assert "down" in bindings
        assert "ctrl+k" in bindings
        assert "ctrl+j" in bindings

    def test_has_tab_binding(self):
        bindings = {b.key: b.action for b in EnhancedInput.BINDINGS}
        assert "tab" in bindings
        assert bindings["tab"] == "autocomplete"

    def test_has_escape_binding(self):
        bindings = {b.key: b.action for b in EnhancedInput.BINDINGS}
        assert "escape" in bindings
        assert bindings["escape"] == "dismiss_command_menu"

    def test_has_ctrl_space_binding(self):
        bindings = {b.key: b.action for b in EnhancedInput.BINDINGS}
        assert "ctrl+space" in bindings
        assert bindings["ctrl+space"] == "show_command_menu"


class TestEnhancedInputHistory:
    def test_add_to_history_adds_new_item(self):
        input_widget = EnhancedInput()
        input_widget.add_to_history("test command")
        assert input_widget._history == ["test command"]
        assert input_widget._history_index == 1

    def test_add_to_history_ignores_empty(self):
        input_widget = EnhancedInput()
        input_widget.add_to_history("")
        assert input_widget._history == []

    def test_add_to_history_ignores_duplicate(self):
        input_widget = EnhancedInput()
        input_widget.add_to_history("test")
        input_widget.add_to_history("test")
        assert input_widget._history == ["test"]

    def test_add_to_history_limits_to_100(self):
        input_widget = EnhancedInput()
        for i in range(150):
            input_widget.add_to_history(f"command-{i}")
        assert len(input_widget._history) == 100
        assert input_widget._history[0] == "command-50"

    def test_history_initial_state(self):
        input_widget = EnhancedInput()
        assert input_widget._history == []
        assert input_widget._history_index == -1
        assert input_widget._saved_value == ""


class TestPreviewAutocomplete:
    def test_preview_autocomplete_returns_match(self):
        result = preview_autocomplete("/help")
        assert result == "/help"

    def test_preview_autocomplete_returns_partial(self):
        result = preview_autocomplete("/con")
        assert result.startswith("/con")

    def test_preview_autocomplete_returns_original_when_no_match(self):
        result = preview_autocomplete("/xyz123")
        assert result == "/xyz123"

    def test_preview_autocomplete_non_slash_returns_original(self):
        result = preview_autocomplete("test")
        assert result == "test"

    def test_preview_autocomplete_empty_returns_empty(self):
        result = preview_autocomplete("")
        assert result == ""

    def test_preview_autocomplete_with_args(self):
        result = preview_autocomplete("/connect ")
        assert result.startswith("/connect ")
