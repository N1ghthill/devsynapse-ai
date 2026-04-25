#!/usr/bin/env python3
"""
Create the per-user DevSynapse runtime config when it does not exist.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import BASE_DIR, CONFIG_FILE, DATA_DIR, LOGS_DIR


def _read_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _set_config_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    output: list[str] = []

    for line in lines:
        if line.startswith(f"{key}="):
            output.append(f"{key}={value}")
            updated = True
        else:
            output.append(line)

    if not updated:
        output.append(f"{key}={value}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        source_env = BASE_DIR / ".env"
        template = source_env if source_env.exists() else BASE_DIR / ".env.example"
        CONFIG_FILE.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Created runtime config: {CONFIG_FILE}")
    else:
        print(f"Runtime config already exists: {CONFIG_FILE}")

    values = _read_config(CONFIG_FILE)
    current_secret = values.get("JWT_SECRET_KEY", "")
    if (
        not current_secret
        or current_secret == "change-this-in-production"
        or len(current_secret) < 32
    ):
        _set_config_value(CONFIG_FILE, "JWT_SECRET_KEY", secrets.token_urlsafe(48))

    _set_config_value(CONFIG_FILE, "MEMORY_DB_PATH", str(DATA_DIR / "devsynapse_memory.db"))
    _set_config_value(
        CONFIG_FILE,
        "MONITORING_DB_PATH",
        str(DATA_DIR / "devsynapse_monitoring.db"),
    )
    _set_config_value(CONFIG_FILE, "LOG_FILE", str(LOGS_DIR / "devsynapse.log"))

    print(f"Runtime data: {DATA_DIR}")
    print(f"Runtime logs: {LOGS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
