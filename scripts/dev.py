#!/usr/bin/env python3
"""
Run the DevSynapse backend and frontend development servers together.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import CONFIG_FILE, MEMORY_DB_PATH, get_settings

FRONTEND_DIR = ROOT_DIR / "frontend"
API_HOST = "127.0.0.1"
API_PORT = 8000
FRONTEND_PORT = 5173


def _read_env(key: str, default: str = "") -> str:
    env_file = CONFIG_FILE
    if not env_file.is_file():
        return default
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return default


def format_admin_password_for_display(password: str) -> str:
    if password == "admin":
        return "admin"
    return "value from DEFAULT_ADMIN_PASSWORD in runtime config"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((API_HOST, port)) == 0


def check_ready() -> bool:
    missing = []
    if not CONFIG_FILE.exists():
        missing.append(str(CONFIG_FILE))
    if not (FRONTEND_DIR / "node_modules").exists():
        missing.append("frontend/node_modules")
    if not MEMORY_DB_PATH.exists():
        missing.append(str(MEMORY_DB_PATH))

    if missing:
        print("Missing setup artifacts: " + ", ".join(missing))
        print(f"Run `make setup`, then add your DEEPSEEK_API_KEY to `{CONFIG_FILE}`.")
        return False

    blocked_ports = [
        str(port)
        for port in (API_PORT, FRONTEND_PORT)
        if is_port_in_use(port)
    ]
    if blocked_ports:
        print("Port(s) already in use: " + ", ".join(blocked_ports))
        print("Stop the existing process or run the backend/frontend manually.")
        return False

    return True


def start_process(name: str, command: list[str], cwd: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("VITE_API_URL", f"http://{API_HOST}:{API_PORT}")
    env.setdefault("DEVSYNAPSE_CONFIG_FILE", str(CONFIG_FILE))
    print(f"Starting {name}: {' '.join(command)}")
    return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    deadline = time.monotonic() + 5
    for process in processes:
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def main() -> int:
    if not check_ready():
        return 1

    shutting_down = False
    processes = [
        start_process(
            "backend",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api.app:app",
                "--host",
                API_HOST,
                "--port",
                str(API_PORT),
                "--reload",
            ],
            ROOT_DIR,
        ),
        start_process(
            "frontend",
            ["npm", "run", "dev", "--", "--host", API_HOST],
            FRONTEND_DIR,
        ),
    ]

    def handle_shutdown(signum, _frame) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        print("\nStopping DevSynapse...")
        stop_processes(processes)
        raise SystemExit(0 if signum in {signal.SIGINT, signal.SIGTERM} else 1)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    print("")
    title = f"DevSynapse AI v{get_settings().app_version}"
    print("╔══════════════════════════════════════════════════╗")
    print(f"║{title.center(50)}║")
    print("╚══════════════════════════════════════════════════╝")
    print("")
    print(f"Frontend:  http://{API_HOST}:{FRONTEND_PORT}")
    print(f"API Docs:  http://{API_HOST}:{API_PORT}/docs")
    print(f"Health:    http://{API_HOST}:{API_PORT}/health")
    print("")
    admin_pw = _read_env("DEFAULT_ADMIN_PASSWORD", "admin")
    print(f"Login:     admin / {format_admin_password_for_display(admin_pw)}")
    print("")
    print("Press Ctrl+C to stop both servers.")
    print("")

    try:
        while True:
            for process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    stop_processes(processes)
                    return exit_code
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping DevSynapse...")
        stop_processes(processes)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
