"""Shell command history for DevSynapse AI."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional

from core.db import connect_db


class ShellCommandHistory:
    """Gerencia histórico de comandos shell executados."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shell_command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                output TEXT,
                success INTEGER DEFAULT 0,
                executed_at TEXT NOT NULL,
                conversation_id TEXT,
                project_name TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_command(
        self,
        command: str,
        output: str = "",
        success: bool = False,
        conversation_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> None:
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO shell_command_history
            (command, output, success, executed_at, conversation_id, project_name)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (command, output, int(success), datetime.now().isoformat(), conversation_id, project_name),
        )
        conn.commit()
        conn.close()

    def get_recent_commands(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = connect_db(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM shell_command_history
            ORDER BY executed_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def search_history(self, pattern: str, limit: int = 20) -> list[dict[str, Any]]:
        conn = connect_db(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM shell_command_history
            WHERE command LIKE ?
            ORDER BY executed_at DESC
            LIMIT ?
            """,
            (f"%{pattern}%", limit),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def clear_history(self) -> None:
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shell_command_history")
        conn.commit()
        conn.close()
