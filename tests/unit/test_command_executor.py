"""Tests for core.command_executor."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.command_executor import CommandExecutor


@pytest.fixture
def executor(tmp_path: Path):
    """Create a CommandExecutor with permissive validators for testing."""
    def validate_file_path(path, check_ext=False):
        return True
    return CommandExecutor(
        validate_file_path=validate_file_path,
        validate_file_size=lambda path, max_size: True,
        decode_quoted_arg=lambda v: v.replace('\\"', '"'),
        backup_enabled=True,
        backup_suffix=".devsynapse_backup",
    )


@pytest.fixture
def executor_no_backup(tmp_path: Path):
    """Create a CommandExecutor with backups disabled."""
    def validate_file_path(path, check_ext=False):
        return True
    return CommandExecutor(
        validate_file_path=validate_file_path,
        validate_file_size=lambda path, max_size: True,
        decode_quoted_arg=lambda v: v.replace('\\"', '"'),
        backup_enabled=False,
        backup_suffix=".devsynapse_backup",
    )


class TestExecuteBash:
    async def test_successful_command(self, executor, tmp_path):
        success, message, output = await executor.execute_bash(
            ["echo hello"], cwd=str(tmp_path)
        )
        assert success is True
        assert "exit code: 0" in message
        assert "hello" in output

    async def test_failed_command(self, executor, tmp_path):
        success, message, output = await executor.execute_bash(
            ["false"], cwd=str(tmp_path)
        )
        assert success is False
        assert "exit code: 1" in message

    async def test_empty_command(self, executor, tmp_path):
        success, message, output = await executor.execute_bash([""], cwd=str(tmp_path))
        assert success is False
        assert "Empty command" in message

    async def test_cd_not_allowed(self, executor, tmp_path):
        success, message, output = await executor.execute_bash(
            ["cd /tmp"], cwd=str(tmp_path)
        )
        assert success is False
        assert "cd" in message
        assert "not allowed" in message

    async def test_stderr_captured(self, executor, tmp_path):
        success, message, output = await executor.execute_bash(
            ["bash -c 'echo stderr_msg >&2'"], cwd=str(tmp_path)
        )
        assert "STDERR" in output
        assert "stderr_msg" in output

    async def test_output_truncated_when_too_long(self, executor, tmp_path):
        long_output = "x" * 20000
        with patch("core.command_executor.get_settings") as mock_settings:
            mock_settings.return_value.opencode_timeout = 30
            mock_settings.return_value.opencode_max_output = 100
            mock_settings.return_value.default_execution_cwd = tmp_path

            success, message, output = await executor.execute_bash(
                [f"echo {long_output}"], cwd=str(tmp_path)
            )
            assert "truncated" in output
            assert len(output) < len(long_output)

    async def test_timeout_expired(self, executor, tmp_path):
        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("sleep 10", 1)
            with patch("core.command_executor.get_settings") as mock_settings:
                mock_settings.return_value.opencode_timeout = 1
                mock_settings.return_value.default_execution_cwd = tmp_path

                success, message, output = await executor.execute_bash(
                    ["sleep 10"], cwd=str(tmp_path)
                )
                assert success is False
                assert "timed out" in message

    async def test_os_error(self, executor, tmp_path):
        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("command not found")
            with patch("core.command_executor.get_settings") as mock_settings:
                mock_settings.return_value.opencode_timeout = 30
                mock_settings.return_value.default_execution_cwd = tmp_path

                success, message, output = await executor.execute_bash(
                    ["nonexistent_cmd"], cwd=str(tmp_path)
                )
                assert success is False
                assert "Error executing command" in message

    async def test_trusted_shell_does_not_enable_shell_true(self, executor, tmp_path):
        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            with patch("core.command_executor.get_settings") as mock_settings:
                mock_settings.return_value.opencode_timeout = 30
                mock_settings.return_value.opencode_max_output = 10000
                mock_settings.return_value.default_execution_cwd = tmp_path

                await executor.execute_bash(["echo test"], cwd=str(tmp_path), trusted_shell=True)
                call_kwargs = mock_run.call_args.kwargs
                assert call_kwargs["shell"] is False


class TestExecuteRead:
    async def test_read_existing_file(self, executor, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("hello world", encoding="utf-8")

        success, message, output = await executor.execute_read([str(file_path)])
        assert success is True
        assert "hello world" in output

    async def test_read_nonexistent_file(self, executor, tmp_path):
        success, message, output = await executor.execute_read(
            [str(tmp_path / "nonexistent.txt")]
        )
        assert success is False
        assert "File not found" in message

    async def test_read_directory_not_file(self, executor, tmp_path):
        success, message, output = await executor.execute_read([str(tmp_path)])
        assert success is False
        assert "not a file" in message

    async def test_read_truncates_long_content(self, executor, tmp_path):
        file_path = tmp_path / "long.txt"
        file_path.write_text("x" * 15000, encoding="utf-8")

        with patch("core.command_executor.get_settings") as mock_settings:
            mock_settings.return_value.opencode_max_output = 100

            success, message, output = await executor.execute_read([str(file_path)])
            assert success is True
            assert "truncated" in output

    async def test_read_os_error(self, executor, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("content", encoding="utf-8")

        with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
            success, message, output = await executor.execute_read([str(file_path)])
            assert success is False
            assert "Error reading file" in message


class TestExecuteGlob:
    async def test_glob_finds_files(self, executor, tmp_path):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()

        success, message, output = await executor.execute_glob(
            [str(tmp_path / "*.py")]
        )
        assert success is True
        parsed = json.loads(output)
        assert len(parsed) == 2

    async def test_glob_no_matches(self, executor, tmp_path):
        success, message, output = await executor.execute_glob(
            [str(tmp_path / "*.nonexistent")]
        )
        assert success is True
        assert "No files found" in message

    async def test_glob_respects_validator_when_not_trusted(self, executor, tmp_path):
        (tmp_path / "test.py").touch()
        def validate_file_path(path, check_ext=False):
            return False
        restrictive_executor = CommandExecutor(
            validate_file_path=validate_file_path,
            validate_file_size=lambda path, max_size: True,
            decode_quoted_arg=lambda v: v,
            backup_enabled=False,
            backup_suffix=".bak",
        )

        success, message, output = await restrictive_executor.execute_glob(
            [str(tmp_path / "*.py")], trusted_paths=False
        )
        assert success is True
        assert "No files found" in message

    async def test_glob_ignores_validator_when_trusted(self, executor, tmp_path):
        (tmp_path / "test.py").touch()
        def validate_file_path(path, check_ext=False):
            return False
        restrictive_executor = CommandExecutor(
            validate_file_path=validate_file_path,
            validate_file_size=lambda path, max_size: True,
            decode_quoted_arg=lambda v: v,
            backup_enabled=False,
            backup_suffix=".bak",
        )

        success, message, output = await restrictive_executor.execute_glob(
            [str(tmp_path / "*.py")], trusted_paths=True
        )
        assert success is True
        parsed = json.loads(output)
        assert len(parsed) == 1

    async def test_glob_limits_to_50_files(self, executor, tmp_path):
        for i in range(60):
            (tmp_path / f"file_{i}.py").touch()

        success, message, output = await executor.execute_glob(
            [str(tmp_path / "*.py")]
        )
        assert success is True
        assert "more files" in output
        # Extract JSON part before the "... and X more files" suffix
        json_end = output.rfind("]\n")
        if json_end != -1:
            json_part = output[:json_end + 1]
            parsed = json.loads(json_part)
            assert len(parsed) == 50

    async def test_glob_os_error(self, executor):
        with patch("glob.glob") as mock_glob:
            mock_glob.side_effect = OSError("invalid pattern")

            success, message, output = await executor.execute_glob(["[invalid"])
            assert success is False
            assert "Error searching" in message


class TestExecuteGrep:
    async def test_grep_finds_pattern(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("def hello():\n    pass\n", encoding="utf-8")

        with patch("core.command_executor.get_settings") as mock_settings:
            mock_settings.return_value.opencode_timeout = 30
            mock_settings.return_value.opencode_max_output = 10000
            mock_settings.return_value.dev_repos_root = tmp_path

            success, message, output = await executor.execute_grep(
                ["def hello", ""], cwd=str(tmp_path)
            )
            assert success is True
            assert "def hello" in output

    async def test_grep_pattern_not_found(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("def other():\n    pass\n", encoding="utf-8")

        with patch("core.command_executor.get_settings") as mock_settings:
            mock_settings.return_value.opencode_timeout = 30
            mock_settings.return_value.opencode_max_output = 10000
            mock_settings.return_value.dev_repos_root = tmp_path

            success, message, output = await executor.execute_grep(
                ["def nonexistent", ""], cwd=str(tmp_path)
            )
            assert success is True
            assert "Pattern not found" in message

    async def test_grep_with_include_filter(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("def hello():\n    pass\n", encoding="utf-8")

        with patch("core.command_executor.get_settings") as mock_settings:
            mock_settings.return_value.opencode_timeout = 30
            mock_settings.return_value.opencode_max_output = 10000
            mock_settings.return_value.dev_repos_root = tmp_path

            success, message, output = await executor.execute_grep(
                ["def hello", '--include="*.py"'], cwd=str(tmp_path)
            )
            assert success is True
            assert "def hello" in output

    async def test_grep_timeout(self, executor, tmp_path):
        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("grep", 1)
            with patch("core.command_executor.get_settings") as mock_settings:
                mock_settings.return_value.opencode_timeout = 1
                mock_settings.return_value.dev_repos_root = tmp_path

                success, message, output = await executor.execute_grep(
                    ["pattern", ""], cwd=str(tmp_path)
                )
                assert success is False
                assert "timed out" in message

    async def test_grep_truncates_long_output(self, executor, tmp_path):
        with patch("core.command_executor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="x" * 20000,
                stderr=""
            )
            with patch("core.command_executor.get_settings") as mock_settings:
                mock_settings.return_value.opencode_timeout = 30
                mock_settings.return_value.opencode_max_output = 100
                mock_settings.return_value.dev_repos_root = tmp_path

                success, message, output = await executor.execute_grep(
                    ["pattern", ""], cwd=str(tmp_path)
                )
                assert success is True
                assert "truncated" in output


class TestExecuteEdit:
    async def test_edit_replaces_text(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("old_text = 1\n", encoding="utf-8")

        success, message, output = await executor.execute_edit(
            [str(file_path), '--old="old_text" --new="new_text"']
        )
        assert success is True
        assert "1 occurrence" in message
        assert file_path.read_text() == "new_text = 1\n"

    async def test_edit_multiple_occurrences(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("foo bar foo\n", encoding="utf-8")

        success, message, output = await executor.execute_edit(
            [str(file_path), '--old="foo" --new="baz"']
        )
        assert success is True
        assert "2 occurrence" in message
        assert file_path.read_text() == "baz bar baz\n"

    async def test_edit_file_not_found(self, executor, tmp_path):
        success, message, output = await executor.execute_edit(
            [str(tmp_path / "nonexistent.py"), '--old="a" --new="b"']
        )
        assert success is False
        assert "File not found" in message

    async def test_edit_text_not_found(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("some content\n", encoding="utf-8")

        success, message, output = await executor.execute_edit(
            [str(file_path), '--old="nonexistent" --new="replacement"']
        )
        assert success is False
        assert "Text not found" in message

    async def test_edit_no_changes_when_identical(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("same\n", encoding="utf-8")

        success, message, output = await executor.execute_edit(
            [str(file_path), '--old="same" --new="same"']
        )
        assert success is False
        assert "No changes" in message

    async def test_edit_invalid_format(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("content\n", encoding="utf-8")

        success, message, output = await executor.execute_edit(
            [str(file_path), "invalid format"]
        )
        assert success is False
        assert "Invalid edit format" in message

    async def test_edit_creates_and_removes_backup(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("old\n", encoding="utf-8")

        await executor.execute_edit(
            [str(file_path), '--old="old" --new="new"']
        )
        backup_path = tmp_path / "test.devsynapse_backup"
        assert not backup_path.exists()

    async def test_edit_with_backup_disabled(self, executor_no_backup, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("old\n", encoding="utf-8")

        success, message, output = await executor_no_backup.execute_edit(
            [str(file_path), '--old="old" --new="new"']
        )
        assert success is True
        backup_path = tmp_path / "test.devsynapse_backup"
        assert not backup_path.exists()

    async def test_edit_directory_not_file(self, executor, tmp_path):
        success, message, output = await executor.execute_edit(
            [str(tmp_path), '--old="a" --new="b"']
        )
        assert success is False
        assert "not a file" in message

    async def test_edit_file_too_large(self, executor, tmp_path):
        file_path = tmp_path / "large.py"
        file_path.write_text("x" * 2_000_000, encoding="utf-8")

        restrictive_executor = CommandExecutor(
            validate_file_path=lambda path, check_ext: True,
            validate_file_size=lambda path, max_size: len(path.read_bytes()) < max_size,
            decode_quoted_arg=lambda v: v,
            backup_enabled=False,
            backup_suffix=".bak",
        )

        with patch("core.command_executor.get_settings") as mock_settings:
            mock_settings.return_value.max_edit_size = 1_000_000

            success, message, output = await restrictive_executor.execute_edit(
                [str(file_path), '--old="x" --new="y"']
            )
            assert success is False
            assert "too large" in message


class TestExecuteWrite:
    async def test_write_creates_new_file(self, executor, tmp_path):
        file_path = tmp_path / "new.py"

        success, message, output = await executor.execute_write(
            [str(file_path), '--content="print(1)"']
        )
        assert success is True
        assert "File created" in message
        assert file_path.read_text() == "print(1)"

    async def test_write_overwrites_existing_file(self, executor, tmp_path):
        file_path = tmp_path / "existing.py"
        file_path.write_text("old content", encoding="utf-8")

        success, message, output = await executor.execute_write(
            [str(file_path), '--content="new content"']
        )
        assert success is True
        assert "overwritten" in message
        assert file_path.read_text() == "new content"

    async def test_write_creates_parent_directories(self, executor, tmp_path):
        file_path = tmp_path / "a" / "b" / "c" / "new.py"

        success, message, output = await executor.execute_write(
            [str(file_path), '--content="hello"']
        )
        assert success is True
        assert file_path.exists()
        assert file_path.read_text() == "hello"

    async def test_write_invalid_format(self, executor, tmp_path):
        success, message, output = await executor.execute_write(
            [str(tmp_path / "test.py"), "invalid"]
        )
        assert success is False
        assert "Invalid write format" in message

    async def test_write_os_error(self, executor, tmp_path):
        with patch("pathlib.Path.write_text") as mock_write:
            mock_write.side_effect = OSError("permission denied")

            success, message, output = await executor.execute_write(
                [str(tmp_path / "test.py"), '--content="hello"']
            )
            assert success is False
            assert "Error writing file" in message

    async def test_write_removes_backup_after_success(self, executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("old", encoding="utf-8")

        await executor.execute_write(
            [str(file_path), '--content="new"']
        )
        backup_path = tmp_path / "test.devsynapse_backup"
        assert not backup_path.exists()


@pytest.fixture
def dry_run_executor(tmp_path: Path):
    """Create a CommandExecutor with dry-run enabled."""
    def validate_file_path(path, check_ext=False):
        return True
    return CommandExecutor(
        validate_file_path=validate_file_path,
        validate_file_size=lambda path, max_size: True,
        decode_quoted_arg=lambda v: v.replace('\\"', '"'),
        backup_enabled=True,
        backup_suffix=".devsynapse_backup",
        dry_run=True,
    )


class TestDryRunMode:
    async def test_bash_dry_run(self, dry_run_executor):
        success, message, output = await dry_run_executor.execute_bash(["echo hello"])
        assert success is True
        assert "[DRY RUN]" in message
        assert "echo hello" in message
        assert output is None

    async def test_edit_dry_run(self, dry_run_executor, tmp_path):
        file_path = tmp_path / "test.py"
        file_path.write_text("old_text = 1\n", encoding="utf-8")

        success, message, output = await dry_run_executor.execute_edit(
            [str(file_path), '--old="old_text = 1"\n--new="new_text = 2"']
        )
        assert success is True
        assert "[DRY RUN]" in message
        assert file_path.read_text() == "old_text = 1\n"

    async def test_write_dry_run_new_file(self, dry_run_executor, tmp_path):
        file_path = tmp_path / "new.py"

        success, message, output = await dry_run_executor.execute_write(
            [str(file_path), '--content="print(1)"']
        )
        assert success is True
        assert "[DRY RUN]" in message
        assert "create" in message.lower()
        assert not file_path.exists()

    async def test_write_dry_run_existing_file(self, dry_run_executor, tmp_path):
        file_path = tmp_path / "existing.py"
        file_path.write_text("old", encoding="utf-8")

        success, message, output = await dry_run_executor.execute_write(
            [str(file_path), '--content="new"']
        )
        assert success is True
        assert "[DRY RUN]" in message
        assert "overwrite" in message.lower()
        assert file_path.read_text() == "old"

    async def test_write_dry_run_creates_directory_preview(self, dry_run_executor, tmp_path):
        nested_path = tmp_path / "deep" / "nested" / "file.py"

        success, message, output = await dry_run_executor.execute_write(
            [str(nested_path), '--content="content"']
        )
        assert success is True
        assert "[DRY RUN]" in message
        assert "deep/nested" in message or "deep" in message
        assert not nested_path.exists()
