#!/usr/bin/env python3
"""
Administrative utilities for local DevSynapse users.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.auth import AuthService
from core.memory import MemorySystem


def build_services() -> tuple[MemorySystem, AuthService]:
    memory = MemorySystem()
    auth = AuthService(memory)
    return memory, auth


def command_seed_defaults() -> int:
    _, auth = build_services()
    auth.ensure_default_users()
    print("Default users ensured in SQLite.")
    return 0


def command_list_users() -> int:
    memory, _ = build_services()
    conn = memory.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT username, role, is_active, created_at, last_login
        FROM users
        ORDER BY username
        """
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No users found.")
        return 0

    for row in rows:
        print(
            f"{row['username']} role={row['role']} active={bool(row['is_active'])} "
            f"created_at={row['created_at']} last_login={row['last_login']}"
        )
    return 0


def command_create_user(username: str, password: str, role: str) -> int:
    memory, auth = build_services()
    memory.upsert_user(
        username=username,
        password_hash=auth.hash_password(password),
        role=role,
        is_active=True,
    )
    print(f"User '{username}' created/updated with role '{role}'.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage DevSynapse local users")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("seed-defaults", help="Ensure default users exist")
    subparsers.add_parser("list", help="List persisted users")

    create_parser = subparsers.add_parser("create", help="Create or update a user")
    create_parser.add_argument("--username", required=True)
    create_parser.add_argument("--password", required=True)
    create_parser.add_argument("--role", default="user", choices=["user", "admin"])

    args = parser.parse_args()

    if args.command == "seed-defaults":
        return command_seed_defaults()
    if args.command == "list":
        return command_list_users()
    if args.command == "create":
        return command_create_user(args.username, args.password, args.role)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
