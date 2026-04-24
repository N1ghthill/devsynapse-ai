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

from config.settings import DATA_DIR, MEMORY_DB_PATH
from core.migrations import apply_all_migrations, get_all_migration_status


def command_status() -> int:
    for item in get_all_migration_status(
        MEMORY_DB_PATH,
        DATA_DIR / "devsynapse_monitoring.db",
    ):
        print(
            f"{item['schema_name']}: current={item['current_version']} "
            f"latest={item['latest_version']} pending={item['pending']} "
            f"path={item['db_path']}"
        )
    return 0


def command_apply() -> int:
    results = apply_all_migrations(
        MEMORY_DB_PATH,
        DATA_DIR / "devsynapse_monitoring.db",
    )
    for schema_name, applied in results.items():
        print(f"{schema_name}: applied {applied} migration(s)")
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
