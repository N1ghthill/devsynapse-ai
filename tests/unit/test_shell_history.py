"""Tests for shell command history."""
from __future__ import annotations

import pytest

from core.shell_history import ShellCommandHistory


@pytest.fixture
def shell_history(tmp_path):
    db_path = tmp_path / "shell_history.db"
    return ShellCommandHistory(str(db_path))


class TestShellCommandHistory:
    def test_save_and_retrieve(self, shell_history):
        shell_history.save_command("git status", output="On branch main", success=True)
        commands = shell_history.get_recent_commands()
        assert len(commands) == 1
        assert commands[0]["command"] == "git status"
        assert commands[0]["success"] == 1

    def test_get_recent_commands_limit(self, shell_history):
        for i in range(100):
            shell_history.save_command(f"cmd-{i}", success=True)
        commands = shell_history.get_recent_commands(limit=10)
        assert len(commands) == 10

    def test_search_history(self, shell_history):
        shell_history.save_command("git status", success=True)
        shell_history.save_command("git log", success=True)
        shell_history.save_command("ls -la", success=True)

        results = shell_history.search_history("git")
        assert len(results) == 2

    def test_clear_history(self, shell_history):
        shell_history.save_command("git status", success=True)
        shell_history.save_command("ls -la", success=True)
        shell_history.clear_history()
        commands = shell_history.get_recent_commands()
        assert len(commands) == 0

    def test_save_with_metadata(self, shell_history):
        shell_history.save_command(
            "git commit",
            output="Committed",
            success=True,
            conversation_id="conv-123",
            project_name="my-project",
        )
        commands = shell_history.get_recent_commands()
        assert len(commands) == 1
        assert commands[0]["conversation_id"] == "conv-123"
        assert commands[0]["project_name"] == "my-project"
