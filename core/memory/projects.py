"""
Project registry extracted from memory system.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import KNOWN_PROJECTS

logger = logging.getLogger(__name__)


class ProjectRegistry:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_db_connection(self) -> sqlite3.Connection:
        """Return a SQLite connection for internal/service use."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_project(
        self,
        name: str,
        path: str,
        project_type: str = "project",
        priority: str = "medium",
        replace: bool = True,
    ):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        insert_clause = "INSERT OR REPLACE" if replace else "INSERT"
        cursor.execute(
            f"""
            {insert_clause} INTO projects
            (name, path, type, priority, last_accessed, access_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, path, project_type, priority, datetime.now().isoformat(), 0),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _project_path_exists(path: str | None) -> bool:
        if not path:
            return False
        return Path(path).expanduser().is_dir()

    def _project_from_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        project = dict(row)
        project["path_exists"] = self._project_path_exists(project.get("path"))
        return project

    def get_project(self, name: str, include_missing: bool = False) -> Optional[Dict[str, Any]]:
        """Return a registered project by exact name."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, path, type, priority, last_accessed, access_count
            FROM projects
            WHERE name = ?
            """,
            (name,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None

        project = self._project_from_row(row)
        if not include_missing and not project["path_exists"]:
            return None
        return project

    def list_projects(self, include_missing: bool = False) -> list[Dict[str, Any]]:
        """Return registered projects, hiding missing filesystem paths by default."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, path, type, priority, last_accessed, access_count
            FROM projects
            ORDER BY priority DESC, access_count DESC, name
            """
        )
        projects = [self._project_from_row(row) for row in cursor.fetchall()]
        conn.close()
        if not include_missing:
            projects = [project for project in projects if project["path_exists"]]
        return projects

    def list_project_names(self) -> list[str]:
        """Return active registered project names in stable order."""

        return [project["name"] for project in self.list_projects()]

    def delete_project(self, name: str) -> bool:
        """Delete a project registry row and related mutation permissions."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_permissions WHERE project_name = ?", (name,))
        cursor.execute("DELETE FROM projects WHERE name = ?", (name,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def get_project_lookup(self) -> Dict[str, Dict[str, str]]:
        """Return configured and persisted projects keyed by project name."""

        return self._get_project_lookup()

    def get_projects_context(self) -> str:
        """Retorna contexto sobre projetos"""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name, path, type, priority, last_accessed, access_count
            FROM projects
            ORDER BY priority DESC, access_count DESC
        """
        )

        rows = [self._project_from_row(row) for row in cursor.fetchall()]
        conn.close()
        rows = [row for row in rows if row["path_exists"]]

        if not rows:
            return "Nenhum projeto registrado."

        text = "Projetos conhecidos:\n"
        for row in rows:
            priority_emoji = (
                "🔥" if row["priority"] == "high" else "⚡" if row["priority"] == "medium" else "📁"
            )
            last_access = datetime.fromisoformat(row["last_accessed"]).strftime("%d/%m %H:%M")
            text += f"- {priority_emoji} **{row['name']}** ({row['type']}) "
            text += f"- acessado {row['access_count']}x, último: {last_access}\n"

        return text

    def _update_project_access(self, message: str, project_name: Optional[str] = None):
        """Atualiza contador de acesso para projetos mencionados"""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if project_name:
            projects = [project_name]
        else:
            cursor.execute("SELECT name, path FROM projects")
            projects = [
                row[0]
                for row in cursor.fetchall()
                if self._project_path_exists(row[1])
            ]

        for project in projects:
            if project_name or project.lower() in message.lower():
                cursor.execute(
                    """
                    UPDATE projects
                    SET access_count = access_count + 1,
                        last_accessed = ?
                    WHERE name = ?
                """,
                    (datetime.now().isoformat(), project),
                )
                logger.debug(f"Projeto acessado: {project}")

        conn.commit()
        conn.close()

    def _get_project_lookup(self) -> Dict[str, Dict[str, str]]:
        """Return configured projects plus projects persisted in this memory database."""

        projects = {
            name: dict(info)
            for name, info in KNOWN_PROJECTS.items()
            if self._project_path_exists(info.get("path"))
        }
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name, path, type, priority
                FROM projects
                """
            )
            for row in cursor.fetchall():
                if not self._project_path_exists(row["path"]):
                    continue
                projects[row["name"]] = {
                    "path": row["path"],
                    "type": row["type"],
                    "priority": row["priority"],
                }
        except sqlite3.Error as exc:
            logger.debug("Não foi possível carregar projetos persistidos: %s", exc)
        finally:
            if conn is not None:
                conn.close()

        return projects

    def get_project_permissions(self, username: Optional[str] = None) -> Dict[str, list[str]] | list[str]:
        """Return project mutation permissions for one user or for all users."""

        conn = self.get_db_connection()
        cursor = conn.cursor()

        if username is None:
            cursor.execute(
                """
                SELECT username, project_name
                FROM project_permissions
                WHERE permission = 'mutate'
                ORDER BY username, project_name
                """
            )
            rows = cursor.fetchall()
            conn.close()

            permissions: Dict[str, list[str]] = {}
            for row in rows:
                permissions.setdefault(row["username"], []).append(row["project_name"])
            return permissions

        cursor.execute(
            """
            SELECT project_name
            FROM project_permissions
            WHERE username = ? AND permission = 'mutate'
            ORDER BY project_name
            """,
            (username,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [row["project_name"] for row in rows]

    def replace_project_permissions(self, username: str, project_names: list[str], permission: str = "mutate"):
        """Replace a user's project permissions with an explicit list."""

        now = datetime.now().isoformat()
        unique_projects = sorted(set(project_names))
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM project_permissions
            WHERE username = ? AND permission = ?
            """,
            (username, permission),
        )
        for project_name in unique_projects:
            cursor.execute(
                """
                INSERT INTO project_permissions (username, project_name, permission, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, project_name, permission, now),
            )
        conn.commit()
        conn.close()
