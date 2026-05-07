"""Bookmarks for DevSynapse AI commands."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional

from core.db import connect_db


class BookmarkStore:
    """Gerencia favoritos de comandos do usuário."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                command TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                use_count INTEGER DEFAULT 0,
                last_used_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def add_bookmark(
        self,
        name: str,
        command: str,
        description: str = "",
    ) -> dict[str, Any]:
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO bookmarks (name, command, description, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, command, description, now),
        )
        conn.commit()
        bookmark_id = cursor.lastrowid
        conn.close()
        return {
            "id": bookmark_id,
            "name": name,
            "command": command,
            "description": description,
            "created_at": now,
            "use_count": 0,
            "last_used_at": None,
        }

    def get_bookmark(self, name: str) -> Optional[dict[str, Any]]:
        conn = connect_db(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM bookmarks WHERE name = ?",
            (name,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_bookmarks(self) -> list[dict[str, Any]]:
        conn = connect_db(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM bookmarks ORDER BY name",
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def delete_bookmark(self, name: str) -> bool:
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM bookmarks WHERE name = ?",
            (name,),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def increment_use_count(self, name: str) -> None:
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE bookmarks
            SET use_count = use_count + 1,
                last_used_at = ?
            WHERE name = ?
            """,
            (datetime.now().isoformat(), name),
        )
        conn.commit()
        conn.close()
