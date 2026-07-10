"""Packaged desktop backend sidecar entry point.

This process intentionally exposes only private lifecycle endpoints for the
desktop shell. Product Git/GitHub operations will be added through typed IPC
contracts, not through this HTTP surface.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
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
            request_id = _required_string(payload, "requestId")
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
            request_id = _required_string(payload, "requestId")
            conversation_id = _required_string(payload, "conversationId")
            message = _required_string(payload, "message")
            if request_id is None or conversation_id is None or message is None:
                self._json_response(HTTPStatus.BAD_REQUEST, {"error": "missing_conversation_input"})
                return
            if conversation_id not in self.backend_state.conversations:
                self._json_response(HTTPStatus.NOT_FOUND, {"error": "conversation_not_found"})
                return
            self._json_response(
                HTTPStatus.OK,
                {
                    "conversationId": conversation_id,
                    "events": conversation_send_events(request_id, conversation_id, message),
                },
            )
            return

        if self.path == "/conversation/cancel":
            request_id = _required_string(payload, "requestId")
            conversation_id = _required_string(payload, "conversationId")
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
            request_id = _required_string(payload, "requestId")
            operation_name = _required_string(payload, "operationName")
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
            self._json_response(
                HTTPStatus.OK,
                {
                    "requestId": request_id,
                    "operationName": operation_name,
                    "riskClass": "observe",
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


def _required_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


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
    message: str,
) -> list[dict[str, Any]]:
    del message
    return [
        {
            "type": "response.started",
            "requestId": request_id,
            "conversationId": conversation_id,
        },
        {
            "type": "response.delta",
            "requestId": request_id,
            "conversationId": conversation_id,
            "delta": (
                "Desktop IPC is connected. The next milestone will route this "
                "message through the conversation core and registered operations."
            ),
        },
        {
            "type": "response.completed",
            "requestId": request_id,
            "conversationId": conversation_id,
        },
    ]


def conversation_cancel_events(request_id: str, conversation_id: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "response.failed",
            "requestId": request_id,
            "conversationId": conversation_id,
            "error": "cancelled",
        }
    ]


def operation_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "project.list",
            "riskClass": "observe",
            "description": "List configured local projects and repository availability.",
        },
        {
            "name": "repository.snapshot",
            "riskClass": "observe",
            "description": "Return read-only identity and branch evidence for one project.",
        },
        {
            "name": "git.status",
            "riskClass": "observe",
            "description": "Return normalized read-only Git status counts for one project.",
        },
    ]


def _known_projects() -> dict[str, dict[str, str]]:
    from config.settings import get_settings

    return get_settings().build_known_projects()


def project_list(known_projects: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    projects = known_projects if known_projects is not None else _known_projects()
    output = []
    for name, info in sorted(projects.items()):
        path = Path(str(info.get("path", ""))).expanduser()
        output.append(
            {
                "name": name,
                "path": str(path),
                "type": info.get("type", "project"),
                "priority": info.get("priority", "medium"),
                "exists": path.exists(),
                "isGitRepository": (path / ".git").exists(),
            }
        )
    return {"projects": output}


def _project_path(project_name: str) -> Path:
    projects = _known_projects()
    info = projects.get(project_name)
    if not info:
        raise ValueError("project_not_found")
    path = Path(str(info.get("path", ""))).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError("project_path_unavailable")
    return path


def _git(project_path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_status_counts(porcelain: str) -> dict[str, int]:
    counts = {"staged": 0, "unstaged": 0, "untracked": 0}
    for line in porcelain.splitlines():
        if not line:
            continue
        if line.startswith("??"):
            counts["untracked"] += 1
            continue
        if len(line) >= 2:
            if line[0] != " ":
                counts["staged"] += 1
            if line[1] != " ":
                counts["unstaged"] += 1
    return counts


def repository_snapshot(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = _required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    path = _project_path(project_name)
    branch = _git(path, "branch", "--show-current")
    head = _git(path, "rev-parse", "--short", "HEAD")
    remote = _git(path, "remote", "get-url", "origin")
    porcelain = _git(path, "status", "--porcelain") or ""
    return {
        "projectName": project_name,
        "path": str(path),
        "isGitRepository": (path / ".git").exists(),
        "currentBranch": branch or None,
        "headCommit": head or None,
        "originUrl": remote or None,
        "hasLocalChanges": bool(porcelain),
    }


def git_status(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = _required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    path = _project_path(project_name)
    porcelain = _git(path, "status", "--porcelain") or ""
    branch = _git(path, "branch", "--show-current")
    return {
        "projectName": project_name,
        "path": str(path),
        "branch": branch or None,
        "counts": git_status_counts(porcelain),
        "isClean": not bool(porcelain),
    }


def run_operation(operation_name: str, operation_input: dict[str, Any]) -> dict[str, Any]:
    operations = {
        "project.list": lambda: project_list(),
        "repository.snapshot": lambda: repository_snapshot(operation_input),
        "git.status": lambda: git_status(operation_input),
    }
    if operation_name not in operations:
        raise KeyError(operation_name)
    return operations[operation_name]()


def _configure_runtime(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DEVSYNAPSE_HOME", str(data_dir))


def _app_version() -> str:
    from config.settings import get_settings

    return get_settings().app_version


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_runtime(args.data_dir)
    auth_token = args.auth_token or os.getenv("DEVSYNAPSE_SIDECAR_TOKEN")
    if not auth_token:
        raise SystemExit("missing sidecar auth token")

    state = BackendState(
        data_dir=args.data_dir.expanduser().resolve(),
        version=_app_version(),
        auth_token=auth_token,
    )
    server = SidecarServer((args.host, args.port), state)

    def stop(_signum: int, _frame: object) -> None:
        server.shutdown()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
