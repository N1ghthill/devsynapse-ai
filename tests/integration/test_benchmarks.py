"""Benchmark suite for DevSynapse AI performance testing."""
from __future__ import annotations

import sqlite3
import time

import pytest

from core.skills import SkillStore


class TestSQLiteQueryBenchmarks:
    """Benchmarks for SQLite query performance."""

    @pytest.fixture
    def db_connection(self, tmp_path):
        db_path = tmp_path / "bench.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                user_message TEXT,
                ai_response TEXT,
                llm_provider TEXT,
                llm_model TEXT,
                total_tokens INTEGER,
                estimated_cost_usd REAL,
                conversation_project_name TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_id
            ON conversations(conversation_id)
        """)
        conn.commit()
        yield conn
        conn.close()

    def test_insert_conversation_performance(self, db_connection):
        """Benchmark: Insert 1000 conversations should be < 1 second."""
        start = time.time()

        for i in range(1000):
            db_connection.execute(
                """
                INSERT INTO conversations
                (conversation_id, timestamp, user_message, ai_response, llm_provider, llm_model, total_tokens, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"bench-{i}", time.time(), f"Message {i}", f"Response {i}", "openrouter", "test/model", 100, 0.001),
            )
        db_connection.commit()

        elapsed = time.time() - start
        assert elapsed < 1.0, f"Insert took {elapsed:.3f}s, expected < 1.0s"

    def test_query_recent_conversations_performance(self, db_connection):
        """Benchmark: Query recent conversations should be < 10ms."""
        for i in range(1000):
            db_connection.execute(
                """
                INSERT INTO conversations
                (conversation_id, timestamp, user_message, ai_response)
                VALUES (?, ?, ?, ?)
                """,
                (f"bench-{i}", time.time(), f"Message {i}", f"Response {i}"),
            )
        db_connection.commit()

        start = time.time()
        for _ in range(100):
            db_connection.execute(
                """
                SELECT * FROM conversations
                WHERE conversation_id = ?
                ORDER BY timestamp DESC
                LIMIT 5
                """,
                ("bench-500",),
            ).fetchall()

        elapsed = time.time() - start
        avg_time = elapsed / 100
        assert avg_time < 0.01, f"Query took {avg_time*1000:.2f}ms, expected < 10ms"

    def test_query_with_project_filter_performance(self, db_connection):
        """Benchmark: Query with project filter should be < 10ms."""
        for i in range(1000):
            db_connection.execute(
                """
                INSERT INTO conversations
                (conversation_id, timestamp, user_message, ai_response, conversation_project_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (f"bench-{i}", time.time(), f"Message {i}", f"Response {i}", "test-project" if i % 2 == 0 else "other-project"),
            )
        db_connection.commit()

        start = time.time()
        for _ in range(100):
            db_connection.execute(
                """
                SELECT conversation_project_name
                FROM conversations
                WHERE conversation_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                ("bench-500",),
            ).fetchone()

        elapsed = time.time() - start
        avg_time = elapsed / 100
        assert avg_time < 0.01, f"Query took {avg_time*1000:.2f}ms, expected < 10ms"


class TestSkillStoreBenchmarks:
    """Benchmarks for SkillStore operations."""

    @pytest.fixture
    def skill_store(self, tmp_path):
        db_path = tmp_path / "bench_skills.db"
        base_dir = tmp_path / "skills"
        base_dir.mkdir()

        store = SkillStore(str(db_path), base_dir)

        conn = store.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                description TEXT NOT NULL DEFAULT '',
                scope TEXT NOT NULL DEFAULT 'global',
                project_name TEXT,
                path TEXT NOT NULL,
                content_hash TEXT,
                metadata TEXT,
                use_count INTEGER DEFAULT 0,
                last_used_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skill_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_slug TEXT NOT NULL,
                project_name TEXT,
                conversation_id TEXT,
                reason TEXT,
                activated_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        return store

    def test_create_skill_performance(self, skill_store):
        """Benchmark: Create 100 skills should be < 1 second."""
        start = time.time()

        for i in range(100):
            skill_store.create_skill(
                name=f"Bench Skill {i}",
                description=f"Benchmark skill {i}",
                body=f"# Skill {i}\n\nContent",
            )

        elapsed = time.time() - start
        assert elapsed < 1.0, f"Create took {elapsed:.3f}s, expected < 1.0s"

    def test_list_skills_performance(self, skill_store):
        """Benchmark: List 100 skills should be < 200ms."""
        for i in range(100):
            skill_store.create_skill(
                name=f"List Skill {i}",
                description=f"List benchmark skill {i}",
                body=f"# Skill {i}",
            )

        start = time.time()
        for _ in range(100):
            skill_store.list_skills()

        elapsed = time.time() - start
        avg_time = elapsed / 100
        assert avg_time < 0.2, f"List took {avg_time*1000:.2f}ms, expected < 200ms"

    def test_get_skill_performance(self, skill_store):
        """Benchmark: Get skill by slug should be < 200ms."""
        for i in range(100):
            skill_store.create_skill(
                name=f"Get Skill {i}",
                description=f"Get benchmark skill {i}",
                body=f"# Skill {i}",
            )

        start = time.time()
        for _ in range(100):
            skill_store.get_skill("get-skill-50")

        elapsed = time.time() - start
        avg_time = elapsed / 100
        assert avg_time < 0.2, f"Get took {avg_time*1000:.2f}ms, expected < 200ms"


class TestModelHelpersBenchmarks:
    """Benchmarks for model helper functions."""

    def test_model_dedupe_performance(self):
        """Benchmark: Dedupe 1000 models should be < 100ms."""
        from devsynapse.commands import _dedupe_models

        models = [
            {"provider": "openrouter", "model_id": f"model-{i}"}
            for i in range(1000)
        ]
        models.extend(models)

        start = time.time()
        for _ in range(10):
            _dedupe_models(models)

        elapsed = time.time() - start
        avg_time = elapsed / 10
        assert avg_time < 0.1, f"Dedupe took {avg_time*1000:.2f}ms, expected < 100ms"

    def test_model_sort_performance(self):
        """Benchmark: Sort 1000 models should be < 100ms."""
        from devsynapse.commands import _sort_models_for_ui

        models = [
            {
                "provider": "openrouter",
                "model_id": f"model-{i}",
                "input_cost_per_token": 0.001 * (i % 10),
                "output_cost_per_token": 0.002 * (i % 10),
                "capabilities": {"supported_parameters": ["tools"]} if i % 2 == 0 else {},
            }
            for i in range(1000)
        ]

        start = time.time()
        for _ in range(10):
            _sort_models_for_ui(models)

        elapsed = time.time() - start
        avg_time = elapsed / 10
        assert avg_time < 0.1, f"Sort took {avg_time*1000:.2f}ms, expected < 100ms"
