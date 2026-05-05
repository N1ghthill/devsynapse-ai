"""
Integration tests for the full command execution flow.

Tests the complete path: parse → validate → authorize → execute (mocked) → result.
Uses temporary SQLite databases for memory persistence and mocks subprocess
to avoid executing real commands in CI.
"""
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge

PROJECT_NAME = "devsynapse-ai"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _create_memory(db_path):
    """Create MemorySystem with a specific DB path."""
    from unittest.mock import patch as mock_patch

    from config.settings import AppSettings, get_settings

    get_settings.cache_clear()
    settings = AppSettings()
    settings.memory_db_path = db_path

    with mock_patch("core.memory.system.get_settings", return_value=settings):
        memory = MemorySystem()
        memory.add_project(PROJECT_NAME, str(PROJECT_ROOT), "ai-assistant", "high")
        return memory


def _bridge():
    """Create OpenCodeBridge with the test project registered."""
    return OpenCodeBridge(
        known_projects={
            PROJECT_NAME: {
                "name": PROJECT_NAME,
                "path": str(PROJECT_ROOT),
                "type": "project",
                "complexity": "medium",
            }
        },
        allowed_directories=[str(PROJECT_ROOT)],
    )


class TestCommandFlowIntegration:
    """Full command execution flow with real validation + mocked subprocess."""

    @pytest.mark.asyncio
    async def test_admin_bash_executes_via_trusted_shell(self, tmp_path):
        """Admin bash commands use trusted shell (bash -o pipefail -c)."""
        bridge = _bridge()

        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="output", stderr="")

            result = await bridge.execute_command(
                'bash "echo hello | cat"',
                user_role="admin",
                project_name=PROJECT_NAME,
            )

            assert result.success is True
            assert result.status == "success"
            mock_run.assert_called_once()
            call_args = mock_run.call_args.args[0]
            assert call_args[:3] == ["/bin/bash", "-o", "pipefail"]

    @pytest.mark.asyncio
    async def test_user_bash_executes_via_direct_args(self, tmp_path):
        """User bash commands use direct argument list (no shell)."""
        bridge = _bridge()

        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")

            result = await bridge.execute_command(
                'bash "git status"',
                user_role="user",
                project_name=PROJECT_NAME,
            )

            assert result.success is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args.args[0]
            assert call_args == ["git", "status"]
            assert mock_run.call_args.kwargs.get("shell") is False

    @pytest.mark.asyncio
    async def test_user_blocked_from_admin_only_bash(self):
        """User role is blocked from admin-only bash commands like rm."""
        bridge = _bridge()

        result = await bridge.execute_command(
            'bash "rm file.txt"',
            user_role="user",
            project_name=PROJECT_NAME,
        )

        assert result.success is False
        assert result.status == "blocked"
        assert result.reason_code == "authorization_failed"

    @pytest.mark.asyncio
    async def test_blocks_sudo_before_execution(self):
        """Sudo commands are blocked before any execution attempt."""
        bridge = _bridge()

        with patch("core.command_executor.subprocess.run") as mock_run:
            result = await bridge.execute_command(
                'bash "sudo apt-get update"',
                user_role="admin",
                project_name=PROJECT_NAME,
            )

            assert result.success is False
            assert result.status == "blocked"
            assert result.reason_code == "privileged_setup_required"
            mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocks_disallowed_command_type(self):
        """Commands not in the allowlist are blocked."""
        bridge = _bridge()

        result = await bridge.execute_command('docker "ps"')

        assert result.success is False
        assert result.status == "blocked"
        assert result.reason_code == "validation_failed"

    @pytest.mark.asyncio
    async def test_blocks_blacklisted_pattern(self):
        """Commands containing blacklisted patterns are blocked."""
        bridge = _bridge()

        result = await bridge.execute_command('bash "rm -rf /"')

        assert result.success is False
        assert result.status == "blocked"
        assert result.reason_code == "validation_failed"
        assert "disallowed pattern" in result.message

    @pytest.mark.asyncio
    async def test_user_write_inside_project_with_allowlist(self, tmp_path):
        """User can write inside project when project is in mutation allowlist."""
        bridge = _bridge()

        with patch.object(bridge._executor, "execute_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = (True, "created", "ok")

            result = await bridge.execute_command(
                f'write "{PROJECT_ROOT / "test.txt"}" --content="hello"',
                user_role="user",
                project_mutation_allowlist=[PROJECT_NAME],
            )

            assert result.success is True
            assert result.status == "success"
            mock_write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_write_outside_project_blocked(self, tmp_path):
        """User cannot write to paths outside the project."""
        bridge = _bridge()

        with patch.object(bridge._executor, "execute_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = (True, "created", "ok")

            result = await bridge.execute_command(
                'write "/tmp/outside.txt" --content="hello"',
                user_role="user",
                project_name=PROJECT_NAME,
                project_mutation_allowlist=[PROJECT_NAME],
            )

            assert result.success is False
            assert result.status == "blocked"
            assert result.reason_code == "project_scope_mismatch"
            mock_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_command_timeout_returns_failed_status(self):
        """Subprocess timeout is captured and returns a failed status."""
        bridge = _bridge()

        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 10", timeout=30)

            result = await bridge.execute_command(
                'bash "sleep 10"',
                user_role="admin",
                project_name=PROJECT_NAME,
            )

            assert result.success is False
            assert result.status == "failed"
            assert result.reason_code == "execution_failed"
            assert "timed out" in result.message

    @pytest.mark.asyncio
    async def test_command_subprocess_error_returns_failed_status(self):
        """Subprocess errors are captured and return a failed status."""
        bridge = _bridge()

        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("command not found")

            result = await bridge.execute_command(
                'bash "nonexistent"',
                user_role="admin",
                project_name=PROJECT_NAME,
            )

            assert result.success is False
            assert result.status == "failed"
            assert result.reason_code == "execution_failed"

    @pytest.mark.asyncio
    async def test_plugin_cancel_blocks_execution(self):
        """Plugin event cancellation blocks command execution."""
        bridge = _bridge()

        with patch("core.opencode_bridge.plugin_manager") as mock_plugins:
            mock_plugins.emit_event = AsyncMock(
                return_value=Mock(cancelled=True, data={})
            )

            result = await bridge.execute_command(
                'bash "echo hello"',
                user_role="admin",
            )

            assert result.success is False
            assert result.status == "blocked"
            assert result.reason_code == "plugin_cancelled"

    @pytest.mark.asyncio
    async def test_project_scope_mismatch_blocks_cross_project_mutation(self):
        """Mutation targeting a different project is blocked when conversation is locked."""
        bridge = _bridge()
        other_project = PROJECT_ROOT.parent / "other-project"
        bridge.register_project("other-project", str(other_project), "project", "medium")

        with patch.object(bridge._executor, "execute_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = (True, "created", "ok")

            result = await bridge.execute_command(
                f'write "{other_project / "file.txt"}" --content="hello"',
                user_role="admin",
                project_name=PROJECT_NAME,
            )

            assert result.success is False
            assert result.status == "blocked"
            assert result.reason_code == "project_scope_mismatch"
            mock_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_read_command_succeeds_for_user(self, tmp_path):
        """User can read files inside allowed directories."""
        bridge = _bridge()
        test_file = tmp_path / "readable.txt"
        test_file.write_text("hello world", encoding="utf-8")

        bridge = OpenCodeBridge(
            known_projects={
                PROJECT_NAME: {
                    "name": PROJECT_NAME,
                    "path": str(PROJECT_ROOT),
                    "type": "project",
                    "complexity": "medium",
                }
            },
            allowed_directories=[str(tmp_path), str(PROJECT_ROOT)],
        )

        result = await bridge.execute_command(
            f'read "{test_file}"',
            user_role="user",
        )

        assert result.success is True
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_glob_command_succeeds_for_admin(self):
        """Admin can glob anywhere (trusted_paths=True)."""
        bridge = _bridge()

        with patch.object(bridge._executor, "execute_glob", new_callable=AsyncMock) as mock_glob:
            mock_glob.return_value = (True, "found 3 files", '["a.py", "b.py", "c.py"]')

            result = await bridge.execute_command(
                'glob "/etc/*.conf"',
                user_role="admin",
            )

            assert result.success is True
            mock_glob.assert_awaited_once()
            call_kwargs = mock_glob.await_args.kwargs
            assert call_kwargs.get("trusted_paths") is True

    @pytest.mark.asyncio
    async def test_edit_command_succeeds_for_admin_inside_project(self, tmp_path):
        """Admin can edit files inside the project."""
        bridge = _bridge()
        test_file = PROJECT_ROOT / "test_edit_integration.tmp"
        test_file.write_text("old content", encoding="utf-8")

        try:
            with patch.object(bridge._executor, "execute_edit", new_callable=AsyncMock) as mock_edit:
                mock_edit.return_value = (True, "Edited: 1 occurrence(s)", "Replaced: ...")

                result = await bridge.execute_command(
                    f'edit "{test_file}" --old="old" --new="new"',
                    user_role="admin",
                    project_name=PROJECT_NAME,
                )

                assert result.success is True
                assert result.status == "success"
                mock_edit.assert_awaited_once()
        finally:
            test_file.unlink(missing_ok=True)


class TestCommandFlowWithMemory:
    """Command execution flow integrated with MemorySystem."""

    @pytest.mark.asyncio
    async def test_full_flow_persists_command_result(self, tmp_path):
        """execute_command flow with MemorySystem records the command result."""
        db_path = tmp_path / "flow_test.db"
        memory = _create_memory(db_path)
        bridge = _bridge()

        with patch.object(bridge._executor, "execute_bash", new_callable=AsyncMock) as mock_bash:
            mock_bash.return_value = (True, "ok", "output")

            result = await bridge.execute_command(
                'bash "git status"',
                user_role="admin",
                project_name=PROJECT_NAME,
            )

            assert result.success is True
            assert result.status == "success"
            mock_bash.assert_awaited_once()

        # Verify memory recorded the interaction
        context = await memory.get_conversation_context("test_session")
        assert context is not None

    @pytest.mark.asyncio
    async def test_memory_persists_across_commands(self, tmp_path):
        """Multiple commands in the same conversation share memory context."""
        db_path = tmp_path / "multi_command.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="multi_test",
            user_message="First message",
            ai_response="First response",
        )

        context = await memory.get_conversation_context("multi_test")
        assert len(context["conversation_history"]) >= 2

        await memory.save_interaction(
            conversation_id="multi_test",
            user_message="Second message",
            ai_response="Second response",
        )

        context = await memory.get_conversation_context("multi_test")
        assert len(context["conversation_history"]) >= 4
