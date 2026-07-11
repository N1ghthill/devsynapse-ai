"""Private HTTP sidecar used by the packaged desktop shell."""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.operations import (
    operation_definitions,
    operation_risk_class,
    required_string,
    run_operation,
)

if TYPE_CHECKING:
    from core.desktop_conversation import DesktopConversationService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DevSynapse desktop backend sidecar")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--auth-token")
    return parser


class BackendState:
    def __init__(self, *, data_dir: Path, version: str, auth_token: str) -> None:
        self.data_dir = data_dir
        self.version = version
        self.auth_token = auth_token
        self.conversations: set[str] = set()
        self._conversation_service: "DesktopConversationService | None" = None
        self._conversation_service_lock = threading.Lock()

    def conversation_service(self) -> DesktopConversationService:
        from core.desktop_conversation import DesktopConversationService

        with self._conversation_service_lock:
            if self._conversation_service is None:
                self._conversation_service = DesktopConversationService()
            return self._conversation_service

    def reset_conversation_service(self) -> None:
        with self._conversation_service_lock:
            self._conversation_service = None


class SidecarHandler(BaseHTTPRequestHandler):
    server_version = "DevSynapseSidecar/1.0"

    @property
    def backend_state(self) -> BackendState:
        return self.server.backend_state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        del format, args

    def do_GET(self) -> None:
        if not self._authorized():
            self._json_response(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        if self.path == "/health":
            self._json_response(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "version": self.backend_state.version,
                    "pid": os.getpid(),
                    "dataDir": str(self.backend_state.data_dir),
                },
            )
            return

        if self.path == "/version":
            self._json_response(HTTPStatus.OK, {"version": self.backend_state.version})
            return

        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._json_response(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        if self.path == "/conversation/start":
            request_id = required_string(payload, "requestId")
            if request_id is None:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": "missing_request_id"})
                return
            conversation_id = f"conv-{uuid.uuid4().hex}"
            self.backend_state.conversations.add(conversation_id)
            self._json_response(
                HTTPStatus.OK,
                {
                    "conversationId": conversation_id,
                    "events": conversation_started_events(request_id, conversation_id),
                },
            )
            return

        if self.path == "/conversation/send":
            request_id = required_string(payload, "requestId")
            conversation_id = required_string(payload, "conversationId")
            message = required_string(payload, "message")
            if request_id is None or conversation_id is None or message is None:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": "missing_conversation_input"})
                return
            if conversation_id not in self.backend_state.conversations:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "conversation_not_found"})
                return
            try:
                result = self.backend_state.conversation_service().send_message(
                    conversation_id=conversation_id,
                    message=message,
                )
            except Exception:
                self._json_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "conversation_core_failed"},
                )
                return
            self._json_response(
                HTTPStatus.OK,
                {
                    "conversationId": conversation_id,
                    "events": conversation_send_events(
                        request_id,
                        conversation_id,
                        result.text,
                        command_pending=result.command_pending,
                    ),
                },
            )
            return

        if self.path == "/conversation/cancel":
            request_id = required_string(payload, "requestId")
            conversation_id = required_string(payload, "conversationId")
            if request_id is None or conversation_id is None:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": "missing_conversation_input"})
                return
            self._json_response(
                HTTPStatus.OK,
                {
                    "conversationId": conversation_id,
                    "events": conversation_cancel_events(request_id, conversation_id),
                },
            )
            return

        if self.path == "/operations/list":
            self._json_response(HTTPStatus.OK, {"operations": operation_definitions()})
            return

        if self.path == "/operations/run":
            request_id = required_string(payload, "requestId")
            operation_name = required_string(payload, "operationName")
            operation_input = payload.get("input", {})
            if request_id is None or operation_name is None or not isinstance(operation_input, dict):
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": "missing_operation_input"})
                return
            try:
                result = run_operation(operation_name, operation_input)
            except KeyError:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "operation_not_found"})
                return
            except ValueError as exc:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            if operation_name == "llm.provider.configure":
                self.backend_state.reset_conversation_service()
            self._json_response(
                HTTPStatus.OK,
                {
                    "requestId": request_id,
                    "operationName": operation_name,
                    "riskClass": operation_risk_class(operation_name),
                    "status": "completed",
                    "result": result,
                },
            )
            return

        self._json_response(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _authorized(self) -> bool:
        expected = f"Bearer {self.backend_state.auth_token}"
        return self.headers.get("authorization") == expected

    def _read_json_body(self) -> dict[str, Any]:
        length_header = self.headers.get("content-length")
        try:
            length = int(length_header or "0")
        except ValueError as exc:
            raise ValueError("invalid_content_length") from exc
        if length <= 0:
            return {}
        if length > 64 * 1024:
            raise ValueError("request_too_large")
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid_json") from exc
        if not isinstance(payload, dict):
            raise ValueError("invalid_json_object")
        return payload

    def _json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SidecarServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], state: BackendState) -> None:
        super().__init__(address, SidecarHandler)
        self.backend_state = state


def conversation_started_events(request_id: str, conversation_id: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "response.started",
            "requestId": request_id,
            "conversationId": conversation_id,
        },
        {
            "type": "response.completed",
            "requestId": request_id,
            "conversationId": conversation_id,
        },
    ]


def conversation_send_events(
    request_id: str,
    conversation_id: str,
    response_text: str,
    *,
    command_pending: bool = False,
) -> list[dict[str, Any]]:
    events = [
        {
            "type": "response.started",
            "requestId": request_id,
            "conversationId": conversation_id,
        },
        {
            "type": "response.delta",
            "requestId": request_id,
            "conversationId": conversation_id,
            "delta": response_text,
        },
    ]
    if command_pending:
        events.append(
            {
                "type": "operation.progress",
                "requestId": request_id,
                "conversationId": conversation_id,
                "delta": "A core command was proposed but not executed in the desktop shell.",
            }
        )
    events.append(
        {
            "type": "response.completed",
            "requestId": request_id,
            "conversationId": conversation_id,
        },
    )
    return events


def conversation_cancel_events(request_id: str, conversation_id: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "response.failed",
            "requestId": request_id,
            "conversationId": conversation_id,
            "error": "cancelled",
        }
    ]


def configure_runtime(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DEVSYNAPSE_HOME", str(data_dir))


def app_version() -> str:
    from config.settings import get_settings

    return get_settings().app_version


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_runtime(args.data_dir)
    auth_token = args.auth_token or os.getenv("DEVSYNAPSE_SIDECAR_TOKEN")
    if not auth_token:
        raise SystemExit("missing sidecar auth token")

    state = BackendState(
        data_dir=args.data_dir.expanduser().resolve(),
        version=app_version(),
        auth_token=auth_token,
    )
    server = SidecarServer((args.host, args.port), state)

    def stop(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()

    return 0
