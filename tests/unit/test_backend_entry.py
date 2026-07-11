from pathlib import Path
from types import SimpleNamespace

from core.desktop_sidecar import (
    BackendState,
    SidecarHandler,
    conversation_cancel_events,
    conversation_send_events,
    conversation_started_events,
)
from core.operations import (
    git_status_counts,
    operation_definitions,
    operation_risk_class,
    project_list,
    run_operation,
)


def _handler(token: str, header: str | None) -> SidecarHandler:
    handler = object.__new__(SidecarHandler)
    handler.server = SimpleNamespace(
        backend_state=BackendState(
            data_dir=Path("/tmp/devsynapse-test"),
            version="1.0.0",
            auth_token=token,
        )
    )
    handler.headers = {"authorization": header} if header else {}
    return handler


def test_sidecar_handler_requires_bearer_token():
    assert _handler("secret", None)._authorized() is False
    assert _handler("secret", "Bearer wrong")._authorized() is False
    assert _handler("secret", "Bearer secret")._authorized() is True


def test_conversation_start_events_are_typed():
    events = conversation_started_events("req-1", "conv-1")

    assert [event["type"] for event in events] == [
        "response.started",
        "response.completed",
    ]
    assert all(event["requestId"] == "req-1" for event in events)
    assert all(event["conversationId"] == "conv-1" for event in events)


def test_conversation_event_contract_has_required_identity_fields():
    events = [
        *conversation_started_events("req-start", "conv-1"),
        *conversation_send_events("req-send", "conv-1", "hello"),
        *conversation_cancel_events("req-cancel", "conv-1"),
    ]

    for event in events:
        assert isinstance(event["type"], str)
        assert event["requestId"].startswith("req-")
        assert event["conversationId"] == "conv-1"


def test_conversation_send_events_return_delta():
    events = conversation_send_events("req-2", "conv-1", "Core response")

    assert [event["type"] for event in events] == [
        "response.started",
        "response.delta",
        "response.completed",
    ]
    assert events[1]["delta"] == "Core response"


def test_conversation_send_events_disclose_pending_core_command():
    events = conversation_send_events(
        "req-2",
        "conv-1",
        "Core response",
        command_pending=True,
    )

    assert [event["type"] for event in events] == [
        "response.started",
        "response.delta",
        "operation.progress",
        "response.completed",
    ]
    assert "not executed" in events[2]["delta"]


def test_conversation_cancel_event_is_terminal_failure():
    events = conversation_cancel_events("req-3", "conv-1")

    assert events == [
        {
            "type": "response.failed",
            "requestId": "req-3",
            "conversationId": "conv-1",
            "error": "cancelled",
        }
    ]


def test_operation_definitions_are_read_only():
    definitions = operation_definitions()

    assert [definition["name"] for definition in definitions[:3]] == [
        "project.list",
        "repository.snapshot",
        "git.status",
    ]
    assert {definition["riskClass"] for definition in definitions[:3]} == {"observe"}


def test_project_register_operation_is_local_mutation():
    assert operation_risk_class("project.register") == "local_mutation"


def test_project_register_persists_local_project(monkeypatch, tmp_path):
    repo = tmp_path / "chosen"
    (repo / ".git").mkdir(parents=True)
    saved: dict[str, str] = {}

    class FakeMemory:
        def add_project(
            self,
            name: str,
            path: str,
            project_type: str,
            priority: str,
        ) -> None:
            saved.update(
                {
                    "name": name,
                    "path": path,
                    "project_type": project_type,
                    "priority": priority,
                }
            )

    monkeypatch.setattr("core.memory.MemorySystem", FakeMemory)

    result = run_operation("project.register", {"path": str(repo)})

    assert saved == {
        "name": "chosen",
        "path": str(repo.resolve()),
        "project_type": "project",
        "priority": "medium",
    }
    assert result["project"]["isGitRepository"] is True


def test_project_list_operation_contract(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    monkeypatch.setattr(
        "core.operations._known_projects",
        lambda: {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "high",
            }
        },
    )

    result = run_operation("project.list", {})

    assert set(result) == {"projects"}
    assert result["projects"][0]["name"] == "repo"
    assert result["projects"][0]["isGitRepository"] is True


def test_project_list_normalizes_known_projects(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    result = project_list(
        {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "high",
            }
        }
    )

    assert result["projects"] == [
        {
            "name": "repo",
            "path": str(repo),
            "type": "project",
            "priority": "high",
            "exists": True,
            "isGitRepository": True,
        }
    ]


def test_git_status_counts_parses_porcelain():
    assert git_status_counts(" M changed.py\nA  staged.py\n?? new.py\nMM both.py\n") == {
        "staged": 2,
        "unstaged": 2,
        "untracked": 1,
    }
