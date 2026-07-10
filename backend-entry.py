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
import sys
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

    def _authorized(self) -> bool:
        expected = f"Bearer {self.backend_state.auth_token}"
        return self.headers.get("authorization") == expected

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
