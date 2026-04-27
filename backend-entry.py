#!/usr/bin/env python3
"""
DevSynapse AI backend entry point for Tauri sidecar.

This script is compiled with PyInstaller into a self-contained executable
named `devsynapse-backend`.  Tauri spawns it as a sidecar process and
passes `--port` / `--data-dir` so the database and logs land in the
platform-correct application data directory.

Usage (from Tauri):
    devsynapse-backend --port 8765 --data-dir /path/to/app/data

Usage (standalone for debugging):
    python backend-entry.py --port 8000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `import api`, `import config`, etc.
# work both in development and inside the PyInstaller bundle.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _setup_data_dirs(data_dir: str | None) -> None:
    """Resolve per-platform data/log/config directories and export env vars.

    When Tauri provides ``--data-dir`` we use it directly.  Otherwise we
    fall back to the standard OS application-data location.
    """
    if data_dir:
        base = Path(data_dir)
    else:
        import platform

        system = platform.system()
        if system == "Linux":
            xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            base = Path(xdg) / "devsynapse-ai"
        elif system == "Darwin":
            base = Path.home() / "Library" / "Application Support" / "devsynapse-ai"
        else:  # Windows
            appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            base = Path(appdata) / "devsynapse-ai"

    data = base / "data"
    logs = base / "logs"
    config = base / "config"

    for d in (data, logs, config):
        d.mkdir(parents=True, exist_ok=True)

    os.environ["DEVSYNAPSE_DATA_DIR"] = str(data)
    os.environ["DEVSYNAPSE_LOGS_DIR"] = str(logs)
    os.environ["DEVSYNAPSE_CONFIG_DIR"] = str(config)


def main() -> None:
    parser = argparse.ArgumentParser(description="DevSynapse AI Backend")
    parser.add_argument("--port", type=int, default=8000, help="HTTP listen port")
    parser.add_argument("--data-dir", type=str, default=None, help="App data directory root")
    args = parser.parse_args()

    _setup_data_dirs(args.data_dir)

    # Override API host/port so uvicorn listens on the port Tauri chose.
    os.environ["API_HOST"] = "127.0.0.1"
    os.environ["API_PORT"] = str(args.port)

    # In Tauri mode we don't need the CORS dev-server origins.
    if "CORS_ALLOWED_ORIGINS" not in os.environ:
        os.environ["CORS_ALLOWED_ORIGINS"] = (
            "http://127.0.0.1:5173,"
            "http://localhost:5173,"
            "tauri://localhost,"
            "http://tauri.localhost,"
            "https://tauri.localhost"
        )

    import uvicorn

    from api.app import app

    print(f"DevSynapse AI backend starting on port {args.port}", flush=True)

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
