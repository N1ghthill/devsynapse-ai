import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("backend_entry", ROOT_DIR / "backend-entry.py")
assert SPEC is not None
backend_entry = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(backend_entry)

BackendState = backend_entry.BackendState
SidecarHandler = backend_entry.SidecarHandler
conversation_cancel_events = backend_entry.conversation_cancel_events
conversation_send_events = backend_entry.conversation_send_events
conversation_started_events = backend_entry.conversation_started_events
git_status_counts = backend_entry.git_status_counts
operation_definitions = backend_entry.operation_definitions
project_list = backend_entry.project_list


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


def test_conversation_send_events_return_delta():
    events = conversation_send_events("req-2", "conv-1", "hello")

    assert [event["type"] for event in events] == [
        "response.started",
        "response.delta",
        "response.completed",
    ]
    assert "Desktop IPC is connected" in events[1]["delta"]


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

    assert [definition["name"] for definition in definitions] == [
        "project.list",
        "repository.snapshot",
        "git.status",
    ]
    assert {definition["riskClass"] for definition in definitions} == {"observe"}


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
