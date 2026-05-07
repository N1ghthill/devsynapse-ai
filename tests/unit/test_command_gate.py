"""
Property-based tests for CommandGate authorization facade.

Properties under test:
1. Gate never crashes for any valid input combination.
2. Gate always returns an explicit decision (allowed is bool, reason_code is non-empty str).
3. Gate is deterministic — same inputs yield the same result.
4. Admin read commands targeting known project paths are never blocked.
5. Commands targeting an unregistered project are always denied.
"""
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from core.opencode_bridge import CommandGate, GateResult, OpenCodeBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_NAME = "devsynapse-ai"

SAFE_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po"),
        blacklist_characters=("\x00", "'", '"', "`"),
    ),
    max_size=200,
).filter(lambda s: s not in {"/", ".", ".."} and s.strip())


def _bridge():
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


class TestCommandGateProperties:
    """Property-based tests for CommandGate."""

    @given(
        command_type=st.sampled_from(["bash", "read", "glob", "grep", "edit", "write"]),
        args=st.lists(SAFE_TEXT, max_size=3),
        user_role=st.sampled_from(["admin", "user"]),
        project_name=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        effective_project=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=200)
    def test_gate_never_crashes(
        self, command_type, args, user_role, project_name, effective_project
    ):
        """Property: Gate.check never raises for any valid input combination."""
        bridge = _bridge()
        gate = CommandGate(bridge)

        result = gate.check(
            command_type=command_type,
            args=args,
            user_role=user_role,
            project_name=project_name,
            project_mutation_allowlist=[],
            effective_project=effective_project,
        )

        assert isinstance(result, GateResult)

    @given(
        command_type=st.sampled_from(["bash", "read", "glob", "grep", "edit", "write"]),
        args=st.lists(SAFE_TEXT, max_size=3),
        user_role=st.sampled_from(["admin", "user"]),
        project_name=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        effective_project=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=200)
    def test_gate_always_returns_explicit_decision(
        self, command_type, args, user_role, project_name, effective_project
    ):
        """Property: Gate always returns an explicit, unambiguous decision."""
        bridge = _bridge()
        gate = CommandGate(bridge)

        result = gate.check(
            command_type=command_type,
            args=args,
            user_role=user_role,
            project_name=project_name,
            project_mutation_allowlist=[],
            effective_project=effective_project,
        )

        assert isinstance(result.allowed, bool)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0
        assert isinstance(result.reason_code, str)
        assert len(result.reason_code) > 0

    @given(
        command_type=st.sampled_from(["bash", "read", "glob", "grep", "edit", "write"]),
        args=st.lists(SAFE_TEXT, max_size=3),
        user_role=st.sampled_from(["admin", "user"]),
        project_name=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
        effective_project=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    )
    @settings(max_examples=200)
    def test_gate_is_deterministic(
        self, command_type, args, user_role, project_name, effective_project
    ):
        """Property: Same inputs always produce the same result."""
        bridge = _bridge()
        gate = CommandGate(bridge)

        result_a = gate.check(
            command_type=command_type,
            args=args,
            user_role=user_role,
            project_name=project_name,
            project_mutation_allowlist=[],
            effective_project=effective_project,
        )
        result_b = gate.check(
            command_type=command_type,
            args=args,
            user_role=user_role,
            project_name=project_name,
            project_mutation_allowlist=[],
            effective_project=effective_project,
        )

        assert result_a.allowed == result_b.allowed
        assert result_a.reason == result_b.reason
        assert result_a.reason_code == result_b.reason_code
        assert result_a.effective_project == result_b.effective_project

    @given(
        file_path=st.text(min_size=1, max_size=200).filter(
            lambda p: p not in {"", ".", ".."} and "\x00" not in p
        ),
    )
    @settings(max_examples=100)
    def test_admin_read_never_blocked(self, file_path):
        """Property: Admin read commands are never blocked by the gate."""
        bridge = _bridge()
        gate = CommandGate(bridge)

        result = gate.check(
            command_type="read",
            args=[file_path, ""],
            user_role="admin",
            project_name=None,
            project_mutation_allowlist=[],
            effective_project=None,
        )

        assert result.allowed is True

    @given(
        command_type=st.sampled_from(["bash", "read", "glob", "grep", "edit", "write"]),
        args=st.lists(SAFE_TEXT, min_size=1, max_size=3),
        user_role=st.sampled_from(["admin", "user"]),
    )
    @settings(max_examples=200)
    def test_unregistered_project_always_denies(self, command_type, args, user_role):
        """Property: Commands targeting an unregistered project are always denied."""
        bridge = _bridge()
        gate = CommandGate(bridge)

        result = gate.check(
            command_type=command_type,
            args=args,
            user_role=user_role,
            project_name="nonexistent-project-xyz",
            project_mutation_allowlist=[],
            effective_project="nonexistent-project-xyz",
        )

        assert result.allowed is False
        assert result.reason_code in {
            "project_scope_mismatch",
            "authorization_failed",
        }

    @given(
        command_type=st.sampled_from(["edit", "write"]),
        args=st.lists(SAFE_TEXT, min_size=1, max_size=3),
        user_role=st.just("user"),
    )
    @settings(max_examples=100)
    def test_user_mutation_without_project_denied(self, command_type, args, user_role):
        """Property: User mutations without project context are always denied."""
        bridge = _bridge()
        gate = CommandGate(bridge)

        result = gate.check(
            command_type=command_type,
            args=args,
            user_role=user_role,
            project_name=None,
            project_mutation_allowlist=[],
            effective_project=None,
        )

        assert result.allowed is False
        assert result.reason_code in {"authorization_failed", "validation_failed"}

    @given(command_type=st.sampled_from(["bash", "read", "glob", "grep", "edit", "write"]))
    @settings(max_examples=100)
    def test_admin_allows_valid_project_scoped_commands(self, command_type):
        """Property: Admin role allows valid commands inside the active project."""
        bridge = _bridge()
        gate = CommandGate(bridge)
        args_by_type = {
            "bash": ["python3 --version", ""],
            "read": ["README.md", ""],
            "glob": ["*.py", ""],
            "grep": ["DevSynapse", ""],
            "edit": ["README.md", '--old="DevSynapse" --new="DevSynapse"'],
            "write": ["notes.txt", '--content="hello"'],
        }

        result = gate.check(
            command_type=command_type,
            args=args_by_type[command_type],
            user_role="admin",
            project_name=PROJECT_NAME,
            project_mutation_allowlist=[],
            effective_project=PROJECT_NAME,
        )

        assert result.allowed is True
