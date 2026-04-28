#!/usr/bin/env python3
"""
Create the per-user DevSynapse runtime config when it does not exist.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import BASE_DIR, CONFIG_FILE, DATA_DIR, LOGS_DIR
from core.runtime_config import ensure_runtime_config_file


def main() -> int:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        source_env = BASE_DIR / ".env"
        template = source_env if source_env.exists() else BASE_DIR / ".env.example"
        CONFIG_FILE.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Created runtime config: {CONFIG_FILE}")
    else:
        print(f"Runtime config already exists: {CONFIG_FILE}")

    ensure_runtime_config_file()

    print(f"Runtime data: {DATA_DIR}")
    print(f"Runtime logs: {LOGS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
