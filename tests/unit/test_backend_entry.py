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
