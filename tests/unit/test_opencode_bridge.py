"""
Unit tests for OpenCode bridge
"""
import pytest
import os
import json
import subprocess
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from core.opencode_bridge import OpenCodeBridge
from config.settings import ALLOWED_COMMANDS, ALLOWED_BASH_COMMANDS, BLACKLISTED_PATTERNS, ALLOWED_DIRECTORIES


class TestOpenCodeBridge:
    """Test OpenCodeBridge class"""

    def test_init(self):
        bridge = OpenCodeBridge()
        assert bridge.allowed_commands == ALLOWED_COMMANDS
        assert bridge.allowed_bash_commands == ALLOWED_BASH_COMMANDS
        assert bridge.blacklisted_patterns == BLACKLISTED_PATTERNS

    def test_validate_bash_command_allowed(self):
        bridge = OpenCodeBridge()

        allowed = ["ls", "pwd", "cat", "python", "git status", "echo hello"]
        for cmd in allowed:
            assert bridge._validate_bash_command(cmd) is True

    def test_validate_bash_command_disallowed(self):
        bridge = OpenCodeBridge()

        disallowed = ["sudo rm", "dd if=/dev/zero"]
        for cmd in disallowed:
            assert bridge._validate_bash_command(cmd) is False

    def test_validate_bash_command_dangerous_patterns(self):
        bridge = OpenCodeBridge()

        dangerous = ["ls; rm -rf /", "echo `whoami`", "cat /etc/passwd &"]
        for cmd in dangerous:
            assert bridge._validate_bash_command(cmd) is False

    def test_validate_file_path_allowed(self):
        bridge = OpenCodeBridge()

        allowed = [
            "/home/irving/ruas/repos/devsynapse-ai/test.py",
            "/home/irving/test.txt",
            "/tmp/test_file.log",
            "/var/tmp/data.csv",
        ]

        for path in allowed:
            assert bridge._validate_file_path(path) is True

    def test_validate_file_path_restricted(self):
        bridge = OpenCodeBridge()

        restricted = [
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "/usr/bin/sudo",
            "/home/otheruser/foo.py",
        ]

        for path in restricted:
            assert bridge._validate_file_path(path) is False

    def test_validate_file_size(self, tmp_path):
        bridge = OpenCodeBridge()

        small_file = tmp_path / "small.txt"
        small_file.write_text("hello")

        assert bridge._validate_file_size(small_file, 1000) is True
        assert bridge._validate_file_size(small_file, 1) is False

    @pytest.mark.asyncio
    async def test_execute_bash_success(self):
        bridge = OpenCodeBridge()

        with patch('core.opencode_bridge.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "file1.txt\nfile2.py\n"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            success, message, output = await bridge._execute_bash(["echo hello"])
            assert success is True
            assert "sucesso" in message

    @pytest.mark.asyncio
    async def test_execute_bash_failure(self):
        bridge = OpenCodeBridge()

        with patch('core.opencode_bridge.subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "command not found"
            mock_run.return_value = mock_result

            success, message, output = await bridge._execute_bash(["nonexistent"])
            assert success is False
            assert "falhou" in message

    @pytest.mark.asyncio
    async def test_execute_bash_timeout(self):
        bridge = OpenCodeBridge()

        with patch('core.opencode_bridge.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 10", timeout=30)

            success, message, output = await bridge._execute_bash(["sleep 10"])
            assert success is False
            assert "expirou" in message

    def test_validate_command_valid_bash(self):
        bridge = OpenCodeBridge()

        valid, msg, cmd_type, args = bridge._validate_command('bash "ls -la"')
        assert valid is True
        assert cmd_type == "bash"
        assert args[0] == "ls -la"

    def test_validate_command_valid_read(self):
        bridge = OpenCodeBridge()

        valid, msg, cmd_type, args = bridge._validate_command('read "/home/irving/ruas/repos/devsynapse-ai/test.py"')
        assert valid is True
        assert cmd_type == "read"

    def test_validate_command_invalid_format(self):
        bridge = OpenCodeBridge()

        valid, msg, cmd_type, args = bridge._validate_command("invalid command")
        assert valid is False
        assert "Formato" in msg

    def test_validate_command_disallowed_type(self):
        bridge = OpenCodeBridge()

        valid, msg, cmd_type, args = bridge._validate_command('docker "ps"')
        assert valid is False
        assert "não permitido" in msg

    def test_validate_command_blacklisted_pattern(self):
        bridge = OpenCodeBridge()

        valid, msg, cmd_type, args = bridge._validate_command('bash "rm -rf /"')
        assert valid is False
        assert "não permitido" in msg

    @pytest.mark.asyncio
    async def test_execute_command_successful_flow(self):
        bridge = OpenCodeBridge()

        with patch.object(bridge, '_execute_bash', new_callable=AsyncMock) as mock_bash:
            mock_bash.return_value = (True, "Command executed", "output")

            result = await bridge.execute_command('bash "echo hello"')
            success, message, output, status, reason_code, project_name = result

            assert success is True
            assert message == "Command executed"
            assert output == "output"
            assert status == "success"
            assert reason_code is None

    @pytest.mark.asyncio
    async def test_execute_command_returns_structured_blocked_status_for_validation(self):
        bridge = OpenCodeBridge()

        success, message, output, status, reason_code, project_name = await bridge.execute_command('docker "ps"')

        assert success is False
        assert output is None
        assert status == "blocked"
        assert reason_code == "validation_failed"
        assert project_name is None

    def test_authorize_read_for_user(self):
        bridge = OpenCodeBridge()

        authorized, message = bridge._authorize_command(
            "read",
            ["/tmp/file.txt", ""],
            "user",
            None,
            [],
        )

        assert authorized is True
        assert "Autorizado" in message

    def test_authorize_edit_requires_admin(self):
        bridge = OpenCodeBridge()

        authorized, message = bridge._authorize_command(
            "edit",
            ["/tmp/file.txt", '--old="a" --new="b"'],
            "user",
            None,
            [],
        )

        assert authorized is False
        assert "exige contexto explícito de projeto" in message

    def test_authorize_safe_bash_for_user(self):
        bridge = OpenCodeBridge()

        authorized, message = bridge._authorize_command(
            "bash",
            ["git status", ""],
            "user",
            None,
            [],
        )

        assert authorized is True
        assert "Autorizado" in message

    def test_authorize_mutating_bash_requires_admin(self):
        bridge = OpenCodeBridge()

        authorized, message = bridge._authorize_command(
            "bash",
            ["rm file.txt", ""],
            "user",
            None,
            [],
        )

        assert authorized is False
        assert "exige contexto explícito de projeto" in message

    def test_authorize_touch_requires_project_context(self):
        bridge = OpenCodeBridge()

        authorized, message = bridge._authorize_command(
            "bash",
            ["touch /home/irving/Documentos/TESTE_ESCRITA.md", ""],
            "user",
            None,
            [],
        )

        assert authorized is False
        assert "exige contexto explícito de projeto" in message

    def test_authorize_project_mutation_for_allowlisted_project(self):
        bridge = OpenCodeBridge()

        authorized, message = bridge._authorize_command(
            "edit",
            ["/home/irving/ruas/repos/devsynapse-ai/README.md", '--old="a" --new="b"'],
            "user",
            "devsynapse-ai",
            ["devsynapse-ai"],
        )

        assert authorized is True
        assert "devsynapse-ai" in message

    def test_authorize_project_mutation_denied_when_project_not_allowlisted(self):
        bridge = OpenCodeBridge()

        authorized, message = bridge._authorize_command(
            "write",
            ["/home/irving/ruas/repos/devsynapse-ai/test.txt", '--content="hello"'],
            "user",
            "devsynapse-ai",
            [],
        )

        assert authorized is False
        assert "não autorizada" in message

    def test_infer_project_name_from_file_path(self):
        bridge = OpenCodeBridge()

        project_name = bridge._infer_project_name(
            "read",
            ["/home/irving/ruas/repos/devsynapse-ai/README.md", ""],
            None,
        )

        assert project_name == "devsynapse-ai"

    def test_infer_project_name_from_bash_command(self):
        bridge = OpenCodeBridge()

        project_name = bridge._infer_project_name(
            "bash",
            ['ls /home/irving/ruas/repos/devsynapse-ai', ""],
            None,
        )

        assert project_name == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_execute_command_authorization_failure(self):
        bridge = OpenCodeBridge()

        result = await bridge.execute_command(
            'write "/tmp/test.txt" --content="hello"',
            user_role="user",
        )
        success, message, output, status, reason_code, project_name = result

        assert success is False
        assert "exige contexto explícito de projeto" in message
        assert output is None
        assert status == "blocked"
        assert reason_code == "authorization_failed"
        assert project_name is None

    @pytest.mark.asyncio
    async def test_execute_command_project_mutation_allowed_for_allowlisted_project(self):
        bridge = OpenCodeBridge()

        with patch.object(bridge, "_execute_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = (True, "created", "ok")

            success, message, output, status, reason_code, project_name = await bridge.execute_command(
                'write "/home/irving/ruas/repos/devsynapse-ai/test.txt" --content="hello"',
                user_role="user",
                project_mutation_allowlist=["devsynapse-ai"],
            )

        assert success is True
        assert message == "created"
        assert output == "ok"
        assert status == "success"
        assert reason_code is None
        assert project_name == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_execute_command_validation_failure(self):
        bridge = OpenCodeBridge()

        result = await bridge.execute_command('docker "ps"')
        success, message, output, status, reason_code, project_name = result

        assert success is False
        assert "não permitido" in message
        assert status == "blocked"
        assert reason_code == "validation_failed"
        assert project_name is None

    def test_get_project_context_found(self):
        bridge = OpenCodeBridge()

        context = bridge.get_project_context("devsynapse-ai")
        assert context is not None
        assert "path" in context

    def test_get_project_context_not_found(self):
        bridge = OpenCodeBridge()

        context = bridge.get_project_context("nonexistent-project")
        assert context is None

    @pytest.mark.asyncio
    async def test_execute_read(self, tmp_path):
        bridge = OpenCodeBridge()

        test_file = tmp_path / "test_read.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        # Copy to an allowed directory
        import shutil
        dest = Path("/tmp/test_read_opencode.txt")
        shutil.copy(test_file, dest)

        try:
            success, message, output = await bridge._execute_read([str(dest)])
            assert success is True
            assert "Line 1" in output
        finally:
            if dest.exists():
                dest.unlink()

    @pytest.mark.asyncio
    async def test_execute_read_not_found(self):
        bridge = OpenCodeBridge()

        success, message, output = await bridge._execute_read(["/tmp/nonexistent_file_xyz.txt"])
        assert success is False
        assert "não encontrado" in message
