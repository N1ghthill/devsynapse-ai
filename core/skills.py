"""
Markdown-backed procedural skills for DevSynapse.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

MAX_SKILL_BODY_CHARS = 20000
SKILL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9 _.-]{1,120}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,120}$")


class SkillError(ValueError):
    """Raised for invalid skill operations."""


class SkillStore:
    """Register, activate, and manage Markdown skills."""

    def __init__(
        self,
        db_path: str,
        base_dir: Path,
        project_lookup_fn: Optional[Callable[[], Dict[str, Dict[str, str]]]] = None,
    ):
        self.db_path = db_path
        self.base_dir = Path(base_dir)
        self.project_lookup_fn = project_lookup_fn or (lambda: {})

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_skill(
        self,
        name: str,
        description: str,
        body: str,
        category: str = "general",
        project_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        replace: bool = False,
        source: str = "manual",
    ) -> Dict[str, Any]:
        """Create a skill document and register it in SQLite."""

        skill_name = self._validate_name(name)
        slug = self.slugify(skill_name)
        category_slug = self._validate_category(category)
        skill_description = self._validate_description(description)
        skill_body = self._validate_body(body)
        scope = "project" if project_name else "global"
        skill_dir = self._skill_dir(scope, category_slug, slug, project_name)
        skill_path = skill_dir / "SKILL.md"

        if skill_path.exists() and not replace:
            raise SkillError(f"Skill already exists: {slug}")

        skill_dir.mkdir(parents=True, exist_ok=True)
        content = self._build_skill_document(
            name=skill_name,
            description=skill_description,
            category=category_slug,
            tags=tags or [],
            body=skill_body,
        )
        skill_path.write_text(content, encoding="utf-8")

        return self._upsert_skill_index(
            name=skill_name,
            slug=slug,
            category=category_slug,
            description=skill_description,
            project_name=project_name,
            scope=scope,
            path=skill_path,
            content=content,
            metadata={"source": source, "tags": tags or []},
        )

    def update_skill(
        self,
        slug_or_name: str,
        body: Optional[str] = None,
        description: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Patch a skill body or description."""

        skill = self.get_skill(slug_or_name, project_name=project_name)
        if skill is None:
            return None

        next_description = (
            self._validate_description(description)
            if description is not None
            else skill["description"]
        )
        next_body = self._validate_body(body) if body is not None else skill["body"]
        content = self._build_skill_document(
            name=skill["name"],
            description=next_description,
            category=skill["category"],
            tags=skill.get("tags") or [],
            body=next_body,
        )
        path = Path(skill["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return self._upsert_skill_index(
            name=skill["name"],
            slug=skill["slug"],
            category=skill["category"],
            description=next_description,
            project_name=skill["project_name"],
            scope=skill["scope"],
            path=path,
            content=content,
            metadata=skill.get("metadata") or {},
        )

    def delete_skill(
        self,
        slug_or_name: str,
        project_name: Optional[str] = None,
    ) -> bool:
        """Disable a skill and remove its SKILL.md file if it is local."""

        skill = self.get_skill(slug_or_name, project_name=project_name)
        if skill is None:
            return False

        path = Path(skill["path"])
        if path.exists():
            path.unlink()

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE skills
            SET is_active = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(), skill["id"]),
        )
        conn.commit()
        conn.close()
        return True

    def list_skills(
        self,
        project_name: Optional[str] = None,
        include_global: bool = True,
        include_inactive: bool = False,
    ) -> list[Dict[str, Any]]:
        """List known skills, including files created outside the API."""

        self.sync_from_disk(project_name=project_name)

        conn = self.get_db_connection()
        cursor = conn.cursor()
        where = []
        params: list[Any] = []
        if not include_inactive:
            where.append("is_active = 1")
        if project_name and include_global:
            where.append("(project_name = ? OR project_name IS NULL)")
            params.append(project_name)
        elif project_name:
            where.append("project_name = ?")
            params.append(project_name)

        query = "SELECT * FROM skills"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY scope DESC, category, name"
        cursor.execute(query, params)
        rows = [self._serialize(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_skill(
        self,
        slug_or_name: str,
        project_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        self.sync_from_disk(project_name=project_name)
        slug = self.slugify(slug_or_name)
        conn = self.get_db_connection()
        cursor = conn.cursor()
        if project_name:
            cursor.execute(
                """
                SELECT *
                FROM skills
                WHERE slug = ?
                  AND is_active = 1
                  AND (project_name = ? OR project_name IS NULL)
                ORDER BY CASE WHEN project_name = ? THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (slug, project_name, project_name),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM skills
                WHERE slug = ?
                  AND is_active = 1
                ORDER BY scope DESC
                LIMIT 1
                """,
                (slug,),
            )
        row = cursor.fetchone()
        conn.close()
        return self._hydrate(row) if row else None

    def activate_skill(
        self,
        slug_or_name: str,
        project_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
        reason: str = "manual",
    ) -> Optional[Dict[str, Any]]:
        """Record usage and return the full skill content."""

        skill = self.get_skill(slug_or_name, project_name=project_name)
        if skill is None:
            return None

        now = datetime.now().isoformat()
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE skills
            SET use_count = use_count + 1,
                last_used_at = ?,
                updated_at = updated_at
            WHERE id = ?
            """,
            (now, skill["id"]),
        )
        cursor.execute(
            """
            INSERT INTO skill_activations (
                skill_slug, project_name, conversation_id, reason, activated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill["slug"], project_name, conversation_id, reason, now),
        )
        conn.commit()
        conn.close()
        skill["use_count"] = int(skill.get("use_count") or 0) + 1
        skill["last_used_at"] = now
        return skill

    def select_relevant_skills(
        self,
        query: str,
        project_name: Optional[str] = None,
        limit: int = 3,
    ) -> list[Dict[str, Any]]:
        skills = self.list_skills(project_name=project_name, include_global=True)
        scored = []
        for skill in skills:
            score = self._query_score(query, skill)
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [self._hydrate_from_serialized(skill) for _, skill in scored[:limit]]

    def format_context(
        self,
        query: str,
        project_name: Optional[str] = None,
        limit: int = 3,
    ) -> str:
        selected = self.select_relevant_skills(query, project_name=project_name, limit=limit)
        if not selected:
            skills = self.list_skills(project_name=project_name, include_global=True)
            if not skills:
                return "Nenhuma skill registrada ainda."
            lines = ["Skills registradas:"]
            for skill in skills[:8]:
                scope = skill["project_name"] or "global"
                lines.append(f"- {skill['slug']} ({scope}): {skill['description']}")
            return "\n".join(lines)

        lines = ["Skills relevantes carregadas:"]
        for skill in selected:
            scope = skill["project_name"] or "global"
            content = skill["content"][:3500]
            lines.append(f"\n## {skill['name']} ({scope})\n{content}")
        return "\n".join(lines)

    def sync_from_disk(self, project_name: Optional[str] = None) -> None:
        roots = [(None, "global", self.base_dir)]
        if project_name:
            project_root = self._project_skill_root(project_name)
            if project_root is not None:
                roots.append((project_name, "project", project_root))

        for root_project, scope, root in roots:
            if not root.exists():
                continue
            for skill_path in root.glob("*/*/SKILL.md"):
                try:
                    content = skill_path.read_text(encoding="utf-8")
                    parsed = self.parse_skill_document(content)
                    name = parsed["frontmatter"].get("name") or skill_path.parent.name
                    description = parsed["frontmatter"].get("description") or "No description"
                    category = parsed["frontmatter"].get("category") or skill_path.parent.parent.name
                    tags = self._split_tags(parsed["frontmatter"].get("tags"))
                    self._upsert_skill_index(
                        name=name,
                        slug=skill_path.parent.name,
                        category=category,
                        description=description,
                        project_name=root_project,
                        scope=scope,
                        path=skill_path,
                        content=content,
                        metadata={"tags": tags, "source": "disk"},
                    )
                except Exception:
                    continue

    def get_stats(self) -> Dict[str, Any]:
        self.sync_from_disk()
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_skills,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_skills,
                SUM(use_count) AS use_count
            FROM skills
            """
        )
        totals = dict(cursor.fetchone())
        cursor.execute(
            """
            SELECT category, COUNT(*) AS count
            FROM skills
            WHERE is_active = 1
            GROUP BY category
            ORDER BY count DESC
            """
        )
        by_category = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {
            "total_skills": int(totals.get("total_skills") or 0),
            "active_skills": int(totals.get("active_skills") or 0),
            "use_count": int(totals.get("use_count") or 0),
            "by_category": by_category,
        }

    def _upsert_skill_index(
        self,
        name: str,
        slug: str,
        category: str,
        description: str,
        project_name: Optional[str],
        scope: str,
        path: Path,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, created_at
            FROM skills
            WHERE scope = ?
              AND slug = ?
              AND (project_name = ? OR (? IS NULL AND project_name IS NULL))
            LIMIT 1
            """,
            (scope, slug, project_name, project_name),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE skills
                SET name = ?,
                    category = ?,
                    description = ?,
                    project_name = ?,
                    path = ?,
                    content_hash = ?,
                    is_active = 1,
                    updated_at = ?,
                    metadata = ?
                WHERE id = ?
                """,
                (
                    name,
                    category,
                    description,
                    project_name,
                    str(path),
                    content_hash,
                    now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    existing["id"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO skills (
                    name, slug, category, description, project_name, scope, path,
                    content_hash, is_active, created_at, updated_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    name,
                    slug,
                    category,
                    description,
                    project_name,
                    scope,
                    str(path),
                    content_hash,
                    now,
                    now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
        conn.commit()
        cursor.execute(
            """
            SELECT *
            FROM skills
            WHERE scope = ?
              AND slug = ?
              AND (project_name = ? OR (? IS NULL AND project_name IS NULL))
            """,
            (scope, slug, project_name, project_name),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            raise SkillError("Skill index could not be loaded after write")
        return self._hydrate(row)

    def _skill_dir(
        self,
        scope: str,
        category: str,
        slug: str,
        project_name: Optional[str],
    ) -> Path:
        if scope == "project":
            root = self._project_skill_root(project_name)
            if root is None:
                raise SkillError(f"Unknown project for project skill: {project_name}")
        else:
            root = self.base_dir
        return root / category / slug

    def _project_skill_root(self, project_name: Optional[str]) -> Optional[Path]:
        if not project_name:
            return None
        project = self.project_lookup_fn().get(project_name)
        if not project:
            return None
        return Path(project["path"]).expanduser().resolve() / ".devsynapse" / "skills"

    @staticmethod
    def parse_skill_document(content: str) -> Dict[str, Any]:
        if not content.startswith("---\n"):
            return {"frontmatter": {}, "body": content}
        _, _, remainder = content.partition("---\n")
        frontmatter_text, separator, body = remainder.partition("\n---\n")
        if not separator:
            return {"frontmatter": {}, "body": content}

        frontmatter: Dict[str, str] = {}
        for line in frontmatter_text.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip().strip("\"'")
        return {"frontmatter": frontmatter, "body": body.lstrip()}

    @staticmethod
    def slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        if not slug:
            raise SkillError("Skill slug is required")
        if not SLUG_PATTERN.match(slug):
            raise SkillError(f"Invalid skill slug: {slug}")
        return slug[:120]

    @staticmethod
    def _validate_name(value: str) -> str:
        name = " ".join((value or "").split()).strip()
        if not SKILL_NAME_PATTERN.match(name):
            raise SkillError("Skill name must be 2-120 letters, numbers, spaces, . _ or -")
        return name

    @staticmethod
    def _validate_category(value: str) -> str:
        category = re.sub(r"[^a-z0-9-]+", "-", (value or "general").lower()).strip("-")
        if not category:
            return "general"
        if not SLUG_PATTERN.match(category):
            raise SkillError("Invalid skill category")
        return category[:80]

    @staticmethod
    def _validate_description(value: Optional[str]) -> str:
        description = " ".join((value or "").split()).strip()
        if not description:
            raise SkillError("Skill description is required")
        return description[:1024]

    @staticmethod
    def _validate_body(value: Optional[str]) -> str:
        body = (value or "").strip()
        if not body:
            raise SkillError("Skill body is required")
        if len(body) > MAX_SKILL_BODY_CHARS:
            raise SkillError("Skill body is too large")
        return body

    @staticmethod
    def _build_skill_document(
        name: str,
        description: str,
        category: str,
        tags: list[str],
        body: str,
    ) -> str:
        tag_line = ", ".join(sorted({tag.strip() for tag in tags if tag.strip()}))
        return (
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"category: {category}\n"
            f"tags: {tag_line}\n"
            "---\n\n"
            f"{body.strip()}\n"
        )

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["is_active"] = bool(data.get("is_active"))
        data["use_count"] = int(data.get("use_count") or 0)
        data["metadata"] = self._json_dict(data.get("metadata"))
        data["tags"] = self._split_tags(data["metadata"].get("tags"))
        return data

    def _hydrate(self, row: sqlite3.Row) -> Dict[str, Any]:
        return self._hydrate_from_serialized(self._serialize(row))

    def _hydrate_from_serialized(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(skill["path"])
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        parsed = self.parse_skill_document(content)
        hydrated = dict(skill)
        hydrated["content"] = content
        hydrated["body"] = parsed["body"]
        return hydrated

    @staticmethod
    def _query_score(query: str, skill: Dict[str, Any]) -> float:
        terms = set(re.findall(r"[a-zA-Z0-9_áàâãéêíóôõúç-]{3,}", query.lower()))
        if not terms:
            return 0.0
        haystack = " ".join(
            [
                skill.get("name") or "",
                skill.get("slug") or "",
                skill.get("description") or "",
                skill.get("category") or "",
                " ".join(skill.get("tags") or []),
            ]
        ).lower()
        matches = sum(1 for term in terms if term in haystack)
        return matches / max(len(terms), 1)

    @staticmethod
    def _split_tags(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if not value:
            return []
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _json_dict(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
