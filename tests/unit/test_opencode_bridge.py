"""
Unit tests for OpenCode bridge
"""
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.settings import ALLOWED_BASH_COMMANDS, ALLOWED_COMMANDS, BLACKLISTED_PATTERNS
from core.opencode_bridge import OpenCodeBridge

PROJECT_NAME = "devsynapse-ai"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECTS = {
    PROJECT_NAME: {
        "path": str(PROJECT_ROOT),
        "type": "ai-assistant",
        "priority": "high",
    }
}
ALLOWED_TEST_DIRECTORIES = [str(PROJECT_ROOT.parent), "/tmp", "/var/tmp"]


class _MonitoringStub:
    def log_command_execution(self, *args, **kwargs):
        return None

    def log_system_metric(self, *args, **kwargs):
        return None


@pytest.fixture(autouse=True)
def isolate_bridge_monitoring(monkeypatch):
    monkeypatch.setattr("core.opencode_bridge.default_monitoring_system", _MonitoringStub())


def _bridge():
    return OpenCodeBridge(
        known_projects=PROJECTS,
        allowed_directories=ALLOWED_TEST_DIRECTORIES,
    )


class TestOpenCodeBridge:
    """Test OpenCodeBridge class"""

    def test_init(self):
        bridge = _bridge()
        assert bridge.allowed_commands == ALLOWED_COMMANDS
        assert bridge.allowed_bash_commands == ALLOWED_BASH_COMMANDS
        assert bridge.blacklisted_patterns == BLACKLISTED_PATTERNS

    def test_validate_bash_command_allowed(self):
        bridge = _bridge()

        allowed = ["ls", "pwd", "cat", "python", "git status", "echo hello"]
        for cmd in allowed:
            assert bridge._validate_bash_command(cmd) is True

    def test_validate_bash_command_disallowed(self):
        bridge = _bridge()

        disallowed = ["sudo rm", "dd if=/dev/zero"]
        for cmd in disallowed:
            assert bridge._validate_bash_command(cmd) is False

    def test_validate_bash_command_dangerous_patterns(self):
        bridge = _bridge()

        dangerous = ["ls; rm -rf /", "echo `whoami`", "cat /etc/passwd &"]
        for cmd in dangerous:
            assert bridge._validate_bash_command(cmd) is False

    def test_validate_file_path_allowed(self):
        bridge = _bridge()

        allowed = [
            str(PROJECT_ROOT / "test.py"),
            str(PROJECT_ROOT.parent / "scratch.txt"),
            "/tmp/test_file.log",
            "/var/tmp/data.csv",
        ]

        for path in allowed:
            assert bridge._validate_file_path(path) is True

    def test_validate_file_path_restricted(self):
        bridge = _bridge()

        restricted = [
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "/usr/bin/sudo",
            "/home/otheruser/foo.py",
        ]

        for path in restricted:
            assert bridge._validate_file_path(path) is False

    def test_validate_file_size(self, tmp_path):
        bridge = _bridge()

        small_file = tmp_path / "small.txt"
        small_file.write_text("hello")

        assert bridge._validate_file_size(small_file, 1000) is True
        assert bridge._validate_file_size(small_file, 1) is False

    @pytest.mark.asyncio
    async def test_execute_bash_success(self):
        bridge = _bridge()

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
        bridge = _bridge()

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
        bridge = _bridge()

        with patch('core.opencode_bridge.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="sleep 10", timeout=30)

            success, message, output = await bridge._execute_bash(["sleep 10"])
            assert success is False
            assert "expirou" in message

    def test_validate_command_valid_bash(self):
        bridge = _bridge()

        valid, msg, cmd_type, args = bridge._validate_command('bash "ls -la"')
        assert valid is True
        assert cmd_type == "bash"
        assert args[0] == "ls -la"

    def test_validate_command_valid_read(self):
        bridge = _bridge()

        valid, msg, cmd_type, args = bridge._validate_command(
            f'read "{PROJECT_ROOT / "test.py"}"'
        )
        assert valid is True
        assert cmd_type == "read"

    def test_validate_command_invalid_format(self):
        bridge = _bridge()

        valid, msg, cmd_type, args = bridge._validate_command("invalid command")
        assert valid is False
        assert "Formato" in msg

    def test_validate_command_disallowed_type(self):
        bridge = _bridge()

        valid, msg, cmd_type, args = bridge._validate_command('docker "ps"')
        assert valid is False
        assert "não permitido" in msg

    def test_validate_command_blacklisted_pattern(self):
        bridge = _bridge()

        valid, msg, cmd_type, args = bridge._validate_command('bash "rm -rf /"')
        assert valid is False
        assert "não permitido" in msg

    @pytest.mark.asyncio
    async def test_execute_command_successful_flow(self):
        bridge = _bridge()

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
        bridge = _bridge()

        success, message, output, status, reason_code, project_name = await bridge.execute_command('docker "ps"')

        assert success is False
        assert output is None
        assert status == "blocked"
        assert reason_code == "validation_failed"
        assert project_name is None

    def test_authorize_read_for_user(self):
        bridge = _bridge()

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
        bridge = _bridge()

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
        bridge = _bridge()

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
        bridge = _bridge()

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
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "bash",
            ["touch /tmp/TESTE_ESCRITA.md", ""],
            "user",
            None,
            [],
        )

        assert authorized is False
        assert "exige contexto explícito de projeto" in message

    def test_authorize_project_mutation_for_allowlisted_project(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "edit",
            [str(PROJECT_ROOT / "README.md"), '--old="a" --new="b"'],
            "user",
            "devsynapse-ai",
            ["devsynapse-ai"],
        )

        assert authorized is True
        assert "devsynapse-ai" in message

    def test_authorize_project_mutation_denied_when_project_not_allowlisted(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "write",
            [str(PROJECT_ROOT / "test.txt"), '--content="hello"'],
            "user",
            "devsynapse-ai",
            [],
        )

        assert authorized is False
        assert "não autorizada" in message

    def test_authorize_admin_has_global_mutation_access_for_registered_project(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "write",
            [str(PROJECT_ROOT / "test.txt"), '--content="hello"'],
            "admin",
            "devsynapse-ai",
            [],
        )

        assert authorized is True
        assert "Autorizado" in message

    def test_authorize_project_mutation_denies_paths_outside_project(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "write",
            [str(PROJECT_ROOT.parent / "outside.txt"), '--content="hello"'],
            "user",
            "devsynapse-ai",
            ["devsynapse-ai"],
        )

        assert authorized is False
        assert "fora do projeto" in message

    def test_authorize_admin_mutation_denies_paths_outside_registered_project(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "write",
            [str(PROJECT_ROOT.parent / "outside.txt"), '--content="hello"'],
            "admin",
            "devsynapse-ai",
            [],
        )

        assert authorized is False
        assert "fora do projeto" in message

    def test_authorize_mutating_bash_denies_paths_outside_project(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "bash",
            [f"touch {PROJECT_ROOT.parent / 'outside.txt'}", ""],
            "user",
            "devsynapse-ai",
            ["devsynapse-ai"],
        )

        assert authorized is False
        assert "fora do projeto" in message

    def test_authorize_project_mutation_denies_relative_path_traversal(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "write",
            ["../outside.txt", '--content="hello"'],
            "user",
            "devsynapse-ai",
            ["devsynapse-ai"],
        )

        assert authorized is False
        assert "fora do projeto" in message

    def test_authorize_project_mutation_denies_symlink_escape(self, tmp_path):
        project_root = tmp_path / "project"
        outside_root = tmp_path / "outside"
        project_root.mkdir()
        outside_root.mkdir()
        link_path = project_root / "linked-outside"
        link_path.symlink_to(outside_root, target_is_directory=True)
        bridge = OpenCodeBridge(
            known_projects={
                "tmp-project": {
                    "path": str(project_root),
                    "type": "test",
                    "priority": "medium",
                }
            },
            allowed_directories=[str(tmp_path)],
        )

        authorized, message = bridge._authorize_command(
            "write",
            ["linked-outside/escape.txt", '--content="hello"'],
            "user",
            "tmp-project",
            ["tmp-project"],
        )

        assert authorized is False
        assert "fora do projeto" in message

    def test_authorize_mutating_bash_checks_target_directory_option(self):
        bridge = _bridge()

        authorized, message = bridge._authorize_command(
            "bash",
            [f"cp -t {PROJECT_ROOT.parent} {PROJECT_ROOT / 'README.md'}", ""],
            "user",
            "devsynapse-ai",
            ["devsynapse-ai"],
        )

        assert authorized is False
        assert "fora do projeto" in message

    def test_register_project_updates_bridge_lookup(self):
        bridge = _bridge()
        docs_path = PROJECT_ROOT / "docs"

        bridge.register_project("docs-project", str(docs_path), "docs", "low")

        assert bridge.get_project_context("docs-project")["path"] == str(docs_path)
        assert bridge._resolve_project_cwd("docs-project") == str(docs_path)

    def test_infer_project_name_from_file_path(self):
        bridge = _bridge()

        project_name = bridge._infer_project_name(
            "read",
            [str(PROJECT_ROOT / "README.md"), ""],
            None,
        )

        assert project_name == "devsynapse-ai"

    def test_infer_project_name_from_bash_command(self):
        bridge = _bridge()

        project_name = bridge._infer_project_name(
            "bash",
            [f"ls {PROJECT_ROOT}", ""],
            None,
        )

        assert project_name == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_execute_command_authorization_failure(self):
        bridge = _bridge()

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
        bridge = _bridge()

        with patch.object(bridge, "_execute_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = (True, "created", "ok")

            success, message, output, status, reason_code, project_name = await bridge.execute_command(
                f'write "{PROJECT_ROOT / "test.txt"}" --content="hello"',
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
    async def test_execute_command_normalizes_relative_read_path_against_project(self):
        bridge = _bridge()

        with patch.object(bridge, "_execute_read", new_callable=AsyncMock) as mock_read:
            mock_read.return_value = (True, "read", "content")

            success, message, output, status, reason_code, project_name = await bridge.execute_command(
                'read "README.md"',
                project_name="devsynapse-ai",
                user_role="user",
            )

        mock_read.assert_awaited_once_with([str(PROJECT_ROOT / "README.md"), ""])
        assert success is True
        assert message == "read"
        assert output == "content"
        assert status == "success"
        assert reason_code is None
        assert project_name == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_execute_command_normalizes_relative_mutation_path_against_project(self):
        bridge = _bridge()

        with patch.object(bridge, "_execute_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = (True, "created", "ok")

            success, message, output, status, reason_code, project_name = await bridge.execute_command(
                'write "notes/devsynapse.txt" --content="hello"',
                project_name="devsynapse-ai",
                user_role="user",
                project_mutation_allowlist=["devsynapse-ai"],
            )

        mock_write.assert_awaited_once_with(
            [str(PROJECT_ROOT / "notes" / "devsynapse.txt"), '--content="hello"']
        )
        assert success is True
        assert message == "created"
        assert output == "ok"
        assert status == "success"
        assert reason_code is None
        assert project_name == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_execute_command_validation_failure(self):
        bridge = _bridge()

        result = await bridge.execute_command('docker "ps"')
        success, message, output, status, reason_code, project_name = result

        assert success is False
        assert "não permitido" in message
        assert status == "blocked"
        assert reason_code == "validation_failed"
        assert project_name is None

    def test_get_project_context_found(self):
        bridge = _bridge()

        context = bridge.get_project_context("devsynapse-ai")
        assert context is not None
        assert "path" in context

    def test_get_project_context_not_found(self):
        bridge = _bridge()

        context = bridge.get_project_context("nonexistent-project")
        assert context is None

    @pytest.mark.asyncio
    async def test_execute_read(self, tmp_path):
        bridge = _bridge()

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
        bridge = _bridge()

        success, message, output = await bridge._execute_read(["/tmp/nonexistent_file_xyz.txt"])
        assert success is False
        assert "não encontrado" in message

    @pytest.mark.asyncio
    async def test_execute_edit_without_backup_enabled(self, tmp_path):
        bridge = _bridge()
        bridge.backup_enabled = False
        target = tmp_path / "edit.txt"
        target.write_text("alpha beta", encoding="utf-8")

        success, message, output = await bridge._execute_edit(
            [str(target), '--old="alpha" --new="omega"']
        )

        assert success is True
        assert "Editado" in message
        assert "Backup: desabilitado" in output
        assert target.read_text(encoding="utf-8") == "omega beta"

    @pytest.mark.asyncio
    async def test_execute_edit_decodes_escaped_quotes_and_newlines(self, tmp_path):
        bridge = _bridge()
        bridge.backup_enabled = False
        target = tmp_path / "edit_escaped.txt"
        target.write_text('print("hi")\n', encoding="utf-8")

        success, message, output = await bridge._execute_edit(
            [str(target), '--old="print(\\"hi\\")\\n" --new="print(\\"bye\\")\\n"']
        )

        assert success is True
        assert "Editado" in message
        assert "Substituído" in output
        assert target.read_text(encoding="utf-8") == 'print("bye")\n'

    @pytest.mark.asyncio
    async def test_execute_write_decodes_escaped_quotes_and_newlines(self, tmp_path):
        bridge = _bridge()
        target = tmp_path / "write_escaped.txt"

        success, message, output = await bridge._execute_write(
            [str(target), '--content="print(\\"hi\\")\\npath = \\"C:\\\\tmp\\""']
        )

        assert success is True
        assert "Arquivo criado" in message
        assert "Novo arquivo criado" in output
        assert target.read_text(encoding="utf-8") == 'print("hi")\npath = "C:\\tmp"'
