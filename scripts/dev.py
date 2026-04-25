#!/usr/bin/env python3
"""
Run the DevSynapse backend and frontend development servers together.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
API_HOST = "127.0.0.1"
API_PORT = 8000
FRONTEND_PORT = 5173


def _read_env(key: str, default: str = "") -> str:
    env_file = ROOT_DIR / ".env"
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


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((API_HOST, port)) == 0


def check_ready() -> bool:
    missing = []
    if not (ROOT_DIR / ".env").exists():
        missing.append(".env")
    if not (FRONTEND_DIR / "node_modules").exists():
        missing.append("frontend/node_modules")

    if missing:
        print("Missing setup artifacts: " + ", ".join(missing))
        print("Run `make setup`, then add your DEEPSEEK_API_KEY to `.env`.")
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
    print(f"Starting {name}: {' '.join(command)}")
    return subprocess.Popen(command, cwd=cwd, env=env)


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + 5
    for process in processes:
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if process.poll() is None:
            process.kill()


def main() -> int:
    if not check_ready():
        return 1

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

    print("")
    print("╔══════════════════════════════════════════════════╗")
    print("║              DevSynapse AI v0.3.0               ║")
    print("╚══════════════════════════════════════════════════╝")
    print("")
    print(f"Frontend:  http://{API_HOST}:{FRONTEND_PORT}")
    print(f"API Docs:  http://{API_HOST}:{API_PORT}/docs")
    print(f"Health:    http://{API_HOST}:{API_PORT}/health")
    print("")
    admin_pw = _read_env("DEFAULT_ADMIN_PASSWORD", "admin")
    print(f"Login:     admin / {admin_pw}")
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
