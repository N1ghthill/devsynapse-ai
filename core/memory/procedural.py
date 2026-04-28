"""
Project-scoped procedural memories with confidence and decay.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

DEFAULT_MEMORY_DECAY_SCORE = 0.02
MAX_MEMORY_CONTENT_CHARS = 2000


class ProjectMemoryStore:
    """Store reusable project knowledge with confidence decay."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_memory(
        self,
        content: str,
        project_name: Optional[str] = None,
        memory_type: str = "fact",
        source: str = "manual",
        confidence_score: float = 0.6,
        memory_decay_score: float = DEFAULT_MEMORY_DECAY_SCORE,
        tags: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create or reinforce a memory row."""

        normalized_content = self._normalize_content(content)
        now = datetime.now().isoformat()
        tag_list = sorted({tag.strip() for tag in tags or [] if tag.strip()})

        conn = self.get_db_connection()
        cursor = conn.cursor()
        existing = self._find_existing(cursor, project_name, memory_type, normalized_content)

        if existing is None:
            cursor.execute(
                """
                INSERT INTO project_memories (
                    project_name, memory_type, content, source, confidence_score,
                    memory_decay_score, evidence_count, access_count, created_at,
                    updated_at, tags, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?)
                """,
                (
                    project_name,
                    memory_type,
                    normalized_content,
                    source,
                    self._clamp(confidence_score),
                    max(0.0, float(memory_decay_score)),
                    now,
                    now,
                    json.dumps(tag_list, ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            memory_id = int(cursor.lastrowid)
        else:
            current = dict(existing)
            next_confidence = min(
                0.98,
                max(float(current["confidence_score"] or 0.0), confidence_score) + 0.05,
            )
            next_tags = sorted(set(self._json_list(current.get("tags"))) | set(tag_list))
            next_metadata = self._json_dict(current.get("metadata"))
            next_metadata.update(metadata or {})
            cursor.execute(
                """
                UPDATE project_memories
                SET source = ?,
                    confidence_score = ?,
                    memory_decay_score = ?,
                    evidence_count = evidence_count + 1,
                    updated_at = ?,
                    tags = ?,
                    metadata = ?
                WHERE id = ?
                """,
                (
                    source,
                    self._clamp(next_confidence),
                    max(
                        0.0,
                        min(
                            float(current["memory_decay_score"] or DEFAULT_MEMORY_DECAY_SCORE),
                            float(memory_decay_score),
                        ),
                    ),
                    now,
                    json.dumps(next_tags, ensure_ascii=False),
                    json.dumps(next_metadata, ensure_ascii=False),
                    current["id"],
                ),
            )
            memory_id = int(current["id"])

        conn.commit()
        row = self._get_by_id(cursor, memory_id)
        conn.close()
        return self._serialize(row) if row else {}

    def list_memories(
        self,
        project_name: Optional[str] = None,
        query: Optional[str] = None,
        include_global: bool = True,
        limit: int = 20,
        min_effective_confidence: float = 0.25,
        record_access: bool = True,
    ) -> list[Dict[str, Any]]:
        """Return relevant memories ordered by effective confidence and lexical match."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        if project_name and include_global:
            cursor.execute(
                """
                SELECT *
                FROM project_memories
                WHERE project_name = ? OR project_name IS NULL
                """,
                (project_name,),
            )
        elif project_name:
            cursor.execute(
                """
                SELECT *
                FROM project_memories
                WHERE project_name = ?
                """,
                (project_name,),
            )
        else:
            cursor.execute("SELECT * FROM project_memories")

        rows = [self._serialize(row) for row in cursor.fetchall()]
        scored = []
        for row in rows:
            effective = float(row["effective_confidence"])
            if effective < min_effective_confidence:
                continue
            query_score = self._query_score(query or "", row)
            scored.append((effective + query_score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [row for _, row in scored[: max(1, limit)]]

        if record_access and selected:
            now = datetime.now().isoformat()
            cursor.executemany(
                """
                UPDATE project_memories
                SET access_count = access_count + 1,
                    last_accessed_at = ?
                WHERE id = ?
                """,
                [(now, row["id"]) for row in selected],
            )
            conn.commit()
            ids = [row["id"] for row in selected]
            placeholders = ",".join("?" for _ in ids)
            cursor.execute(
                f"SELECT * FROM project_memories WHERE id IN ({placeholders})",
                ids,
            )
            refreshed = {int(row["id"]): self._serialize(row) for row in cursor.fetchall()}
            selected = [refreshed.get(row["id"], row) for row in selected]

        conn.close()
        return selected

    def adjust_confidence(
        self,
        memory_id: int,
        delta: float,
        source: str = "feedback",
    ) -> Optional[Dict[str, Any]]:
        """Apply explicit feedback to a memory confidence score."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        row = self._get_by_id(cursor, memory_id)
        if row is None:
            conn.close()
            return None

        current = float(row["confidence_score"] or 0.0)
        cursor.execute(
            """
            UPDATE project_memories
            SET confidence_score = ?,
                source = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                self._clamp(current + delta),
                source,
                datetime.now().isoformat(),
                memory_id,
            ),
        )
        conn.commit()
        updated = self._get_by_id(cursor, memory_id)
        conn.close()
        return self._serialize(updated) if updated else None

    def get_memory(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """Return a memory by id without changing access counters."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        row = self._get_by_id(cursor, memory_id)
        conn.close()
        return self._serialize(row) if row else None

    def format_context(
        self,
        project_name: Optional[str],
        query: str,
        limit: int = 6,
    ) -> str:
        """Build a compact prompt block from relevant memories."""

        memories = self.list_memories(
            project_name=project_name,
            query=query,
            include_global=True,
            limit=limit,
            min_effective_confidence=0.3,
        )
        if not memories:
            return "Nenhuma memória procedural relevante encontrada."

        lines = ["Memórias procedurais relevantes:"]
        for memory in memories:
            project = memory["project_name"] or "global"
            lines.append(
                "- "
                f"[{project}/{memory['memory_type']}] {memory['content']} "
                f"(confiança efetiva {float(memory['effective_confidence']):.0%})"
            )
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_memories,
                AVG(confidence_score) AS avg_confidence,
                SUM(evidence_count) AS evidence_count,
                SUM(access_count) AS access_count
            FROM project_memories
            """
        )
        totals = dict(cursor.fetchone())
        cursor.execute(
            """
            SELECT memory_type, COUNT(*) AS count
            FROM project_memories
            GROUP BY memory_type
            ORDER BY count DESC
            """
        )
        by_type = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {
            "total_memories": int(totals.get("total_memories") or 0),
            "avg_confidence": float(totals.get("avg_confidence") or 0.0),
            "evidence_count": int(totals.get("evidence_count") or 0),
            "access_count": int(totals.get("access_count") or 0),
            "by_type": by_type,
        }

    def _find_existing(
        self,
        cursor: sqlite3.Cursor,
        project_name: Optional[str],
        memory_type: str,
        content: str,
    ) -> Optional[sqlite3.Row]:
        if project_name is None:
            cursor.execute(
                """
                SELECT *
                FROM project_memories
                WHERE project_name IS NULL
                  AND memory_type = ?
                  AND content = ?
                """,
                (memory_type, content),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM project_memories
                WHERE project_name = ?
                  AND memory_type = ?
                  AND content = ?
                """,
                (project_name, memory_type, content),
            )
        return cursor.fetchone()

    @staticmethod
    def _get_by_id(cursor: sqlite3.Cursor, memory_id: int) -> Optional[sqlite3.Row]:
        cursor.execute("SELECT * FROM project_memories WHERE id = ?", (memory_id,))
        return cursor.fetchone()

    def _serialize(self, row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["tags"] = self._json_list(data.get("tags"))
        data["metadata"] = self._json_dict(data.get("metadata"))
        data["confidence_score"] = float(data.get("confidence_score") or 0.0)
        data["memory_decay_score"] = float(
            data.get("memory_decay_score") or DEFAULT_MEMORY_DECAY_SCORE
        )
        data["effective_confidence"] = self.effective_confidence(data)
        data["evidence_count"] = int(data.get("evidence_count") or 0)
        data["access_count"] = int(data.get("access_count") or 0)
        return data

    @classmethod
    def effective_confidence(cls, row: Dict[str, Any]) -> float:
        updated_at = cls._parse_datetime(row.get("updated_at")) or datetime.now()
        age_days = max((datetime.now() - updated_at).total_seconds() / 86400, 0.0)
        base = float(row.get("confidence_score") or 0.0)
        decay = max(0.0, float(row.get("memory_decay_score") or DEFAULT_MEMORY_DECAY_SCORE))
        decayed = base * math.exp(-decay * age_days)
        evidence_boost = min(0.1, math.log1p(int(row.get("evidence_count") or 0)) * 0.025)
        access_boost = min(0.12, math.log1p(int(row.get("access_count") or 0)) * 0.03)
        return round(cls._clamp(decayed + evidence_boost + access_boost), 4)

    @staticmethod
    def _query_score(query: str, row: Dict[str, Any]) -> float:
        if not query.strip():
            return 0.0
        query_terms = set(re.findall(r"[a-zA-Z0-9_áàâãéêíóôõúç-]{3,}", query.lower()))
        if not query_terms:
            return 0.0
        haystack = " ".join(
            [
                str(row.get("content") or ""),
                str(row.get("memory_type") or ""),
                " ".join(row.get("tags") or []),
            ]
        ).lower()
        matches = sum(1 for term in query_terms if term in haystack)
        return min(0.35, matches / max(len(query_terms), 1) * 0.35)

    @staticmethod
    def _normalize_content(content: str) -> str:
        normalized = " ".join((content or "").split()).strip()
        if not normalized:
            raise ValueError("Memory content is required")
        return normalized[:MAX_MEMORY_CONTENT_CHARS]

    @staticmethod
    def _clamp(value: float) -> float:
        return min(1.0, max(0.0, float(value)))

    @staticmethod
    def _json_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        try:
            parsed = json.loads(value or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item) for item in parsed]

    @staticmethod
    def _json_dict(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None
