"""
SQLite schema versioning utilities.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    statements: Sequence[str]


class MigrationManager:
    """Apply ordered schema migrations to a SQLite database."""

    def __init__(self, db_path: Path | str, schema_name: str, migrations: Iterable[Migration]):
        self.db_path = Path(db_path)
        self.schema_name = schema_name
        self.migrations = tuple(sorted(migrations, key=lambda migration: migration.version))

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)

    def ensure_schema_table(self, conn: sqlite3.Connection):
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                schema_name TEXT NOT NULL,
                version INTEGER NOT NULL,
                description TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                PRIMARY KEY (schema_name, version)
            )
            """
        )
        conn.commit()

    def get_current_version(self, conn: sqlite3.Connection | None = None) -> int:
        owns_connection = conn is None
        if conn is None:
            conn = self.connect()

        self.ensure_schema_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(MAX(version), 0)
            FROM schema_migrations
            WHERE schema_name = ?
            """,
            (self.schema_name,),
        )
        version = int(cursor.fetchone()[0])

        if owns_connection:
            conn.close()

        return version

    def apply_migrations(self) -> int:
        conn = self.connect()
        self.ensure_schema_table(conn)
        current_version = self.get_current_version(conn)
        applied = 0

        for migration in self.migrations:
            if migration.version <= current_version:
                continue

            logger.info(
                "Applying migration %s:%s - %s",
                self.schema_name,
                migration.version,
                migration.description,
            )
            cursor = conn.cursor()
            for statement in migration.statements:
                cursor.execute(statement)
            cursor.execute(
                """
                INSERT INTO schema_migrations (schema_name, version, description, applied_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.schema_name,
                    migration.version,
                    migration.description,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            applied += 1

        conn.close()
        return applied

    def status(self) -> dict:
        current_version = self.get_current_version()
        latest_version = self.migrations[-1].version if self.migrations else 0
        return {
            "schema_name": self.schema_name,
            "db_path": str(self.db_path),
            "current_version": current_version,
            "latest_version": latest_version,
            "pending": max(latest_version - current_version, 0),
        }
