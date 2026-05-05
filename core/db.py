"""
SQLite schema versioning utilities.
"""

import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_TIMEOUT_SECONDS = 30.0
DEFAULT_SQLITE_BUSY_TIMEOUT_MS = 30000
_WAL_CONFIGURED_PATHS: set[Path] = set()
_WAL_CONFIG_LOCK = threading.Lock()


def connect_db(
    db_path: Path | str,
    *,
    row_factory: bool = True,
    timeout: float = DEFAULT_SQLITE_TIMEOUT_SECONDS,
) -> sqlite3.Connection:
    """Open a SQLite connection with the repository's runtime defaults."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=timeout, check_same_thread=False)
    if row_factory:
        conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute(f"PRAGMA busy_timeout = {DEFAULT_SQLITE_BUSY_TIMEOUT_MS}")
    if path.name != ":memory:" and _should_configure_wal(path):
        try:
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.OperationalError as exc:
            logger.debug("Could not enable SQLite WAL mode for %s: %s", path, exc)

    return conn


@contextmanager
def db_session(db_path: Path | str):
    """Context manager that yields a SQLite connection and ensures it is closed."""
    conn = connect_db(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _should_configure_wal(path: Path) -> bool:
    resolved = path.resolve()
    with _WAL_CONFIG_LOCK:
        if resolved in _WAL_CONFIGURED_PATHS:
            return False
        _WAL_CONFIGURED_PATHS.add(resolved)
        return True


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
        return connect_db(self.db_path)

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
