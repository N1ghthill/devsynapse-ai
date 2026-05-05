#!/usr/bin/env python3
"""
Apply or inspect SQLite schema migrations.
"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import MEMORY_DB_PATH
from core.migrations import build_memory_migration_manager


def command_status() -> int:
    manager = build_memory_migration_manager(MEMORY_DB_PATH)
    status = manager.status()
    print(
        f"memory: current={status['current_version']} "
        f"latest={status['latest_version']} pending={status['pending']} "
        f"path={status['db_path']}"
    )
    return 0


def command_apply() -> int:
    manager = build_memory_migration_manager(MEMORY_DB_PATH)
    applied = manager.apply_migrations()
    print(f"memory: applied {applied} migration(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage DevSynapse SQLite migrations")
    parser.add_argument("command", choices=["status", "apply"])
    args = parser.parse_args()

    if args.command == "status":
        return command_status()
    return command_apply()


if __name__ == "__main__":
    raise SystemExit(main())
