"""Tests for core/command_validator.py."""

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from core.command_validator import CommandValidator

PROJECT_NAME = "devsynapse-ai"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

SAFE_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po"),
        blacklist_characters=("\x00", "'", '"', "`"),
    ),
    max_size=200,
).filter(lambda s: s not in {"/", ".", ".."} and s.strip())


def _validator(**overrides):
    known_projects = {
        PROJECT_NAME: {"path": str(PROJECT_ROOT), "type": "project", "priority": "medium"},
    }
    defaults = {
        "known_projects": known_projects,
        "allowed_bash_commands": {"ls", "cat", "echo", "git", "find", "grep"},
        "read_only_commands": {"read", "glob", "grep"},
        "admin_only_commands": {"edit", "write"},
        "user_bash_commands": {"ls", "cat", "echo", "git", "find", "grep"},
        "admin_only_bash_commands": {"rm", "mv", "cp", "mkdir", "chmod"},
        "allowed_directories": [PROJECT_ROOT],
        "allowed_file_extensions": {".py", ".txt", ".md"},
    }
    defaults.update(overrides)
    return CommandValidator(**defaults)


class TestAuthorizeCommand:
    def test_admin_always_allowed(self):
        v = _validator()
        allowed, _ = v.authorize_command("edit", ["file.py"], "admin", PROJECT_NAME, [])
        assert allowed is True

    def test_admin_write_without_project_denied(self):
        v = _validator()
        allowed, message = v.authorize_command("write", ["file.py"], "admin", None, [])
        assert allowed is False
        assert "requires explicit project context" in message

    def test_admin_mutating_bash_without_project_denied(self):
        v = _validator()
        allowed, message = v.authorize_command("bash", ["mkdir scratch"], "admin", None, [])
        assert allowed is False
        assert "requires explicit project context" in message

    def test_admin_read_only_bash_without_project_allowed(self):
        v = _validator()
        allowed, _ = v.authorize_command("bash", ["python3 --version"], "admin", None, [])
        assert allowed is True

    def test_user_read_allowed(self):
        v = _validator()
        allowed, _ = v.authorize_command("read", ["file.py"], "user", PROJECT_NAME, [])
        assert allowed is True

    def test_user_edit_denied(self):
        v = _validator()
        allowed, _ = v.authorize_command("edit", ["file.py"], "user", None, [])
        assert allowed is False

    def test_valid_bash_for_user(self):
        v = _validator()
        allowed, _ = v.authorize_command("bash", ["echo hello"], "user", None, [])
        assert allowed is True

    def test_admin_bash_without_project_denied(self):
        v = _validator()
        allowed, _ = v.authorize_command("bash", ["rm file.txt"], "user", None, [])
        assert allowed is False

    def test_unknown_command_denied(self):
        v = _validator()
        allowed, _ = v.authorize_command("unknown", [], "user", PROJECT_NAME, [])
        assert allowed is False

    def test_none_command_type_denied(self):
        v = _validator()
        allowed, _ = v.authorize_command(None, [], "user", PROJECT_NAME, [])
        assert allowed is False


class TestValidateBashCommand:
    def test_allowed_command(self):
        v = _validator()
        assert v.validate_bash_command("echo hello") is True

    def test_disallowed_command(self):
        v = _validator()
        assert v.validate_bash_command("sudo rm -rf /") is False

    def test_dangerous_pattern_pipe(self):
        v = _validator()
        assert v.validate_bash_command("ls | grep foo") is False

    def test_dangerous_pattern_redirect(self):
        v = _validator()
        assert v.validate_bash_command("echo foo > file.txt") is False


class TestValidateFilePath:
    def test_inside_allowed_dir(self, tmp_path):
        v = _validator(allowed_directories=[tmp_path])
        target = tmp_path / "file.txt"
        assert v.validate_file_path(str(target)) is True

    def test_outside_allowed_dir(self, tmp_path):
        v = _validator(allowed_directories=[tmp_path])
        assert v.validate_file_path("/etc/passwd") is False


class TestValidateFileSize:
    def test_within_limit(self, tmp_path):
        v = _validator()
        f = tmp_path / "small.txt"
        f.write_text("hello")
        assert v.validate_file_size(f, 1024) is True

    def test_exceeds_limit(self, tmp_path):
        v = _validator()
        f = tmp_path / "large.txt"
        f.write_text("x" * 2000)
        assert v.validate_file_size(f, 100) is False


class TestDecodeQuotedArg:
    def test_newline(self):
        assert CommandValidator.decode_quoted_arg("hello\\nworld") == "hello\nworld"

    def test_tab(self):
        assert CommandValidator.decode_quoted_arg("hello\\tworld") == "hello\tworld"

    def test_carriage_return(self):
        assert CommandValidator.decode_quoted_arg("hello\\rworld") == "hello\rworld"

    def test_escaped_quote(self):
        assert CommandValidator.decode_quoted_arg('say \\"hi\\"') == 'say "hi"'

    def test_escaped_backslash(self):
        assert CommandValidator.decode_quoted_arg("path\\\\to") == "path\\to"

    def test_no_escapes_passthrough(self):
        assert CommandValidator.decode_quoted_arg("plain text") == "plain text"


class TestHypothesisNeverCrashes:
    @given(
        command_type=st.one_of(st.none(), st.sampled_from(["read", "edit", "write", "bash", "glob", "grep"])),
        args=st.lists(SAFE_TEXT, max_size=3),
        user_role=st.sampled_from(["admin", "user"]),
        project_name=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=100)
    def test_authorize_never_crashes(self, command_type, args, user_role, project_name):
        v = _validator()
        allowed, reason = v.authorize_command(command_type, args, user_role, project_name, [])
        assert isinstance(allowed, bool)
        assert isinstance(reason, str)
        assert len(reason) > 0
