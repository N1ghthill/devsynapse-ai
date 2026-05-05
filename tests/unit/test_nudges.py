"""Tests for core/memory/nudges.py."""

from core.db import connect_db
from core.memory.nudges import NudgeStore


def _store(tmp_path):
    db_path = str(tmp_path / "nudges_test.db")
    conn = connect_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_nudge_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            project_name TEXT,
            nudge_type TEXT,
            trigger_reason TEXT,
            status TEXT,
            details TEXT,
            created_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS project_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            project_name TEXT,
            memory_type TEXT DEFAULT 'fact',
            source TEXT DEFAULT 'manual',
            confidence_score REAL DEFAULT 0.6,
            memory_decay_score REAL DEFAULT 0.02,
            tags TEXT,
            metadata TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            description TEXT,
            body TEXT,
            category TEXT DEFAULT 'general',
            project_name TEXT,
            tags TEXT,
            source TEXT DEFAULT 'manual',
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return NudgeStore(
        db_path=db_path,
        memory_upserter=_fake_memory_upserter(db_path),
        skill_creator=_fake_skill_creator(db_path),
        skill_updater=_fake_skill_updater(db_path),
    )


def _fake_memory_upserter(db_path):
    def upserter(content, **kwargs):
        conn = connect_db(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO project_memories (content, project_name, memory_type, source, created_at, updated_at) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
            (content, kwargs.get("project_name"), kwargs.get("memory_type"), kwargs.get("source")),
        )
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {"id": row_id, "content": content}
    return upserter


def _fake_skill_creator(db_path):
    def creator(name, description, body, **kwargs):
        slug = name.lower().replace(" ", "-")
        conn = connect_db(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO skills (name, slug, description, body, category, project_name, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (name, slug, description, body, kwargs.get("category", "general"), kwargs.get("project_name"), kwargs.get("source", "nudge")),
        )
        conn.commit()
        conn.close()
        return {"slug": slug, "name": name}
    return creator


def _fake_skill_updater(db_path):
    def updater(name, **kwargs):
        return {"slug": name.lower().replace(" ", "-"), "name": name}
    return updater


class TestGetStats:
    def test_empty(self, tmp_path):
        store = _store(tmp_path)
        stats = store.get_stats()
        assert stats["total_events"] == 0
        assert stats["by_status"] == []

    def test_with_events(self, tmp_path):
        store = _store(tmp_path)
        store.record_event("c1", "p1", "learning", "command_success", "recorded")
        store.record_event("c2", "p1", "review", "not_complex", "skipped")
        store.record_event("c3", "p1", "learning", "command_success", "recorded")
        stats = store.get_stats()
        assert stats["total_events"] == 3
        assert len(stats["by_status"]) > 0


class TestRecordEvent:
    def test_inserts_row(self, tmp_path):
        store = _store(tmp_path)
        store.record_event("conv1", "proj1", "learning", "complex_task", "recorded", {"reason": "test"})
        conn = connect_db(store.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM learning_nudge_events")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1


class TestReviewCompletedTask:
    def test_command_success_creates_memory_and_skill(self, tmp_path):
        store = _store(tmp_path)
        result = store.review_completed_task(
            conversation_id="c1",
            user_message="Run pytest on the project",
            ai_response="I will run pytest",
            project_name="devsynapse-ai",
            opencode_command='bash "pytest -q"',
            command_success=True,
            command_result="success",
            command_output="3 passed",
            trigger_reason="command_success",
        )
        assert result["status"] == "recorded"
        assert len(result.get("memories", [])) > 0
        assert len(result.get("skills", [])) > 0

    def test_not_complex_skips(self, tmp_path):
        store = _store(tmp_path)
        result = store.review_completed_task(
            conversation_id="c1",
            user_message="What is Python?",
            ai_response="Python is a programming language.",
            project_name="devsynapse-ai",
            trigger_reason="not_complex",
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "not_complex"

    def test_complex_task_creates_insight(self, tmp_path):
        store = _store(tmp_path)
        route = type("Route", (), {"complexity": "complex"})()
        result = store.review_completed_task(
            conversation_id="c1",
            user_message="Refactor the entire auth module",
            ai_response="I will refactor the auth module...",
            project_name="devsynapse-ai",
            command_success=None,
            route=route,
            trigger_reason="complex_task",
        )
        assert result["status"] == "recorded"
        assert len(result.get("memories", [])) > 0


class TestLearningTriggerReason:
    def test_command_success_priority(self):
        reason = NudgeStore._learning_trigger_reason(
            route=None, opencode_command='bash "ls"', command_success=True, tool_iterations=0,
        )
        assert reason == "command_success"

    def test_command_failure_priority(self):
        reason = NudgeStore._learning_trigger_reason(
            route=None, opencode_command='bash "ls"', command_success=False, tool_iterations=0,
        )
        assert reason == "command_failure"

    def test_complex_task(self):
        route = type("Route", (), {"complexity": "complex"})()
        reason = NudgeStore._learning_trigger_reason(
            route=route, opencode_command=None, command_success=None, tool_iterations=0,
        )
        assert reason == "complex_task"

    def test_multi_tool_task(self):
        reason = NudgeStore._learning_trigger_reason(
            route=None, opencode_command=None, command_success=None, tool_iterations=3,
        )
        assert reason == "multi_tool_task"

    def test_command_proposed(self):
        reason = NudgeStore._learning_trigger_reason(
            route=None, opencode_command='bash "ls"', command_success=None, tool_iterations=0,
        )
        assert reason == "command_proposed"

    def test_not_complex(self):
        reason = NudgeStore._learning_trigger_reason(
            route=None, opencode_command=None, command_success=None, tool_iterations=0,
        )
        assert reason == "not_complex"
