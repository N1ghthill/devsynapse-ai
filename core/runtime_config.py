"""Helpers for the per-user runtime environment file."""

from __future__ import annotations

import os
from pathlib import Path

from config.settings import (
    BASE_DIR,
    CONFIG_FILE,
    DATA_DIR,
    DEFAULT_RUNTIME_CONFIG_TEMPLATE,
    LOGS_DIR,
)


def read_runtime_config(path: Path | None = None) -> dict[str, str]:
    path = path or CONFIG_FILE
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


def _serialize_value(value: str | Path) -> str:
    text = str(value).strip()
    if "\n" in text or "\r" in text:
        raise ValueError("Runtime config values cannot contain newlines")
    return text


def _chmod_private(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        path.chmod(0o600)
    except OSError:
        pass


def set_runtime_config_values(
    updates: dict[str, str | Path],
    path: Path | None = None,
) -> None:
    path = path or CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    serialized_updates = {key: _serialize_value(value) for key, value in updates.items()}
    pending = dict(serialized_updates)
    output: list[str] = []

    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            output.append(line)
            continue

        key, _, _ = line.partition("=")
        stripped_key = key.strip()
        if stripped_key in pending:
            output.append(f"{stripped_key}={pending.pop(stripped_key)}")
        else:
            output.append(line)

    for key, value in pending.items():
        output.append(f"{key}={value}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    _chmod_private(path)
    os.environ.update(serialized_updates)


def ensure_runtime_config_file(path: Path | None = None) -> None:
    path = path or CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        source_env = BASE_DIR / ".env"
        template = source_env if source_env.exists() else BASE_DIR / ".env.example"
        template_text = (
            template.read_text(encoding="utf-8")
            if template.exists()
            else DEFAULT_RUNTIME_CONFIG_TEMPLATE
        )
        path.write_text(template_text, encoding="utf-8")
        _chmod_private(path)

    updates: dict[str, str | Path] = {
        "MEMORY_DB_PATH": DATA_DIR / "devsynapse_memory.db",
        "LOG_FILE": LOGS_DIR / "devsynapse.log",
    }

    set_runtime_config_values(updates, path)
