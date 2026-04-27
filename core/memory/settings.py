"""
Persistent settings storage for DevSynapse.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SettingsStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_user_preferences(self) -> str:
        """Retorna preferências do usuário como texto formatado"""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT key, value, confidence, source
            FROM user_preferences
            ORDER BY confidence DESC, evidence_count DESC
        """
        )

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "Nenhuma preferência aprendida ainda."

        text = "Preferências conhecidas do Irving:\n"
        for row in rows:
            source_emoji = "🎯" if row["source"] == "explicit" else "📚" if row["source"] == "learned" else "⚙️"
            text += f"- {source_emoji} **{row['key']}**: {row['value']} "
            text += f"(confiança: {row['confidence']:.0%})\n"

        return text

    def update_preference(self, key: str, value: str, source: str = "learned"):
        """Atualiza ou cria uma preferência do usuário"""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT value, confidence, evidence_count
            FROM user_preferences
            WHERE key = ?
        """,
            (key,),
        )

        row = cursor.fetchone()

        if row:
            # Já existe - atualizar
            old_value, old_confidence, old_count = row
            if old_value == value:
                # Mesmo valor - aumentar confiança
                new_confidence = min(old_confidence * 1.05, 1.0)
                new_count = old_count + 1
                cursor.execute(
                    """
                    UPDATE user_preferences
                    SET confidence = ?, evidence_count = ?, last_updated = ?
                    WHERE key = ? AND value = ?
                    """,
                    (new_confidence, new_count, datetime.now().isoformat(), key, old_value),
                )
            else:
                # Valor diferente - diminuir confiança no antigo, criar novo
                new_confidence = max(old_confidence * 0.7, 0.1)
                cursor.execute(
                    """
                    UPDATE user_preferences
                    SET confidence = ?, last_updated = ?
                    WHERE key = ? AND value = ?
                """,
                    (new_confidence, datetime.now().isoformat(), key, old_value),
                )

                # Inserir novo valor
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO user_preferences
                    (key, value, source, confidence, last_updated, evidence_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                """,
                    (key, value, source, 0.5, datetime.now().isoformat()),
                )
        else:
            # Nova preferência
            cursor.execute(
                """
                INSERT INTO user_preferences
                (key, value, source, confidence, last_updated, evidence_count)
                VALUES (?, ?, ?, ?, ?, 1)
            """,
                (key, value, source, 0.7, datetime.now().isoformat()),
            )

        conn.commit()
        conn.close()

        logger.info(f"Preferência atualizada: {key} = {value} ({source})")

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Return a stored user by username."""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, password_hash, role, is_active, created_at, last_login
            FROM users
            WHERE username = ?
            """,
            (username,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "last_login": row["last_login"],
        }

    def upsert_user(self, username: str, password_hash: str, role: str = "user", is_active: bool = True):
        """Create or update a user record."""

        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role, is_active, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, NULL)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                role = excluded.role,
                is_active = excluded.is_active
            """,
            (username, password_hash, role, int(is_active), now),
        )
        conn.commit()
        conn.close()

    def touch_user_login(self, username: str):
        """Update the user's last successful login timestamp."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET last_login = ?
            WHERE username = ?
            """,
            (datetime.now().isoformat(), username),
        )
        conn.commit()
        conn.close()

    def get_app_settings(self) -> Dict[str, Any]:
        """Return persisted application settings."""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT key, value
            FROM app_settings
            """
        )
        rows = cursor.fetchall()
        conn.close()
        return {row["key"]: row["value"] for row in rows}

    def update_app_settings(self, settings_data: Dict[str, Any]):
        """Persist runtime-adjustable settings."""

        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for key, value in settings_data.items():
            cursor.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, str(value), now),
            )
        conn.commit()
        conn.close()

    def log_admin_action(
        self,
        actor_username: str,
        action: str,
        target_username: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Persist an administrative audit event."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO admin_audit_logs (
                actor_username,
                target_username,
                action,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                actor_username,
                target_username,
                action,
                json.dumps(details or {}),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def get_admin_audit_logs(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Return recent administrative audit events."""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, actor_username, target_username, action, details, created_at
            FROM admin_audit_logs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row["id"],
                "actor_username": row["actor_username"],
                "target_username": row["target_username"],
                "action": row["action"],
                "details": json.loads(row["details"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
