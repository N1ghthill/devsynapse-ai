"""Tests for core.command_messages."""
from __future__ import annotations

from core.command_messages import (
    build_command_result_replay_messages,
    command_completion_fallback,
    command_failure_message,
)


class TestCommandCompletionFallback:
    def test_success_status(self):
        executed_command = {
            "status": "success",
            "reason_code": None,
            "project_name": None,
        }
        result = command_completion_fallback(executed_command)
        assert "Execution completed" in result
        assert "command result is available" in result

    def test_success_with_project(self):
        executed_command = {
            "status": "success",
            "reason_code": None,
            "project_name": "my-project",
        }
        result = command_completion_fallback(executed_command)
        assert "Execution completed" in result
        assert "Project: my-project" in result

    def test_blocked_project_scope(self):
        executed_command = {
            "status": "blocked",
            "reason_code": "project_scope_mismatch",
            "project_name": None,
        }
        result = command_completion_fallback(executed_command)
        assert "blocked" in result
        assert "project scope" in result

    def test_blocked_security_rule(self):
        executed_command = {
            "status": "blocked",
            "reason_code": "authorization_failed",
            "project_name": None,
        }
        result = command_completion_fallback(executed_command)
        assert "blocked" in result
        assert "security rule" in result

    def test_interactive_sudo_required(self):
        executed_command = {
            "status": "failed",
            "reason_code": "interactive_sudo_required",
            "project_name": None,
        }
        result = command_completion_fallback(executed_command)
        assert "password or interactive terminal" in result
        assert "sudo" in result

    def test_privileged_setup_required(self):
        executed_command = {
            "status": "failed",
            "reason_code": "privileged_setup_required",
            "project_name": None,
        }
        result = command_completion_fallback(executed_command)
        assert "privileged setup" in result
        assert "Revalidate prerequisites" in result

    def test_generic_failure(self):
        executed_command = {
            "status": "failed",
            "reason_code": "execution_failed",
            "project_name": None,
        }
        result = command_completion_fallback(executed_command)
        assert "failure" in result
        assert "needs review" in result

    def test_unknown_status_defaults_to_failure(self):
        executed_command = {
            "status": "unknown",
            "reason_code": None,
            "project_name": None,
        }
        result = command_completion_fallback(executed_command)
        assert "failure" in result

    def test_blocked_with_project(self):
        executed_command = {
            "status": "blocked",
            "reason_code": "project_scope_mismatch",
            "project_name": "test-project",
        }
        result = command_completion_fallback(executed_command)
        assert "Project: test-project" in result


class TestCommandFailureMessage:
    def test_interactive_sudo_required(self):
        result = command_failure_message(
            "sudo apt update", "blocked", "interactive_sudo_required", None
        )
        assert "sudo apt update" in result
        assert "password or interactive terminal" in result

    def test_privileged_setup_required(self):
        result = command_failure_message(
            "sudo systemctl start nginx", "blocked", "privileged_setup_required", None
        )
        assert "sudo systemctl start nginx" in result
        assert "privileged setup" in result
        assert "Revalidate prerequisites" in result

    def test_generic_failure(self):
        result = command_failure_message(
            "ls /root", "permission denied", None, None
        )
        assert "ls /root" in result
        assert "permission denied" in result

    def test_with_project_name(self):
        result = command_failure_message(
            "rm file.txt", "not allowed", "validation_failed", "my-project"
        )
        assert "rm file.txt" in result
        assert "Project: my-project" in result


class TestBuildCommandResultReplayMessages:
    def test_successful_command(self):
        messages = build_command_result_replay_messages(
            assistant_text="I will list files.",
            command="bash \"ls -la\"",
            success=True,
            message="Command executed successfully",
            output="file1.txt\nfile2.txt",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        assert "I will list files" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "status `success`" in messages[1]["content"]
        assert "file1.txt" in messages[1]["content"]

    def test_failed_command(self):
        messages = build_command_result_replay_messages(
            assistant_text="Running command...",
            command="bash \"false\"",
            success=False,
            message="Command failed",
            output="error output",
        )
        assert len(messages) == 2
        assert messages[1]["role"] == "user"
        assert "status `failed`" in messages[1]["content"]

    def test_no_output_uses_message(self):
        messages = build_command_result_replay_messages(
            assistant_text="",
            command="bash \"echo hi\"",
            success=True,
            message="ok",
            output=None,
        )
        assert "ok" in messages[1]["content"]

    def test_assistant_text_defaults_to_command(self):
        messages = build_command_result_replay_messages(
            assistant_text="",
            command="bash \"test\"",
            success=True,
            message="ok",
            output="result",
        )
        assert "Executed `bash \"test\"`" in messages[0]["content"]

    def test_output_truncated_to_3000_chars(self):
        long_output = "x" * 5000
        messages = build_command_result_replay_messages(
            assistant_text="",
            command="bash \"long\"",
            success=True,
            message="ok",
            output=long_output,
        )
        assert len(messages[1]["content"]) < len(long_output)

    def test_messages_include_continuation_instructions(self):
        messages = build_command_result_replay_messages(
            assistant_text="",
            command="bash \"test\"",
            success=False,
            message="failed",
            output="error",
        )
        user_content = messages[1]["content"]
        assert "Continue the original task" in user_content
        assert "exactly one next tool call" in user_content
        assert "Do not stop only because" in user_content
