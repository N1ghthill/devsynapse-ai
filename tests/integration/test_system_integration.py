"""
Integration tests for DevSynapse system
"""
import sqlite3
from pathlib import Path

import pytest

from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge

PROJECT_NAME = "devsynapse-ai"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _create_memory(db_path):
    """Create MemorySystem with a specific DB path"""
    from unittest.mock import patch as mock_patch
    with mock_patch('core.memory.MEMORY_DB_PATH', str(db_path)):
        memory = MemorySystem()
        memory.add_project(PROJECT_NAME, str(PROJECT_ROOT), "ai-assistant", "high")
        return memory


class TestSystemIntegration:

    @pytest.mark.asyncio
    async def test_memory_and_conversation_lifecycle(self, tmp_path):
        db_path = tmp_path / "lifecycle.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="lifecycle_test",
            user_message="What projects am I working on?",
            ai_response="You're working on DevSynapse AI"
        )

        context = await memory.get_conversation_context("lifecycle_test")
        assert "conversation_history" in context
        assert len(context["conversation_history"]) >= 2

        await memory.save_feedback(
            conversation_id="lifecycle_test",
            feedback="Great response!",
            score=5
        )

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_feedback, feedback_score FROM conversations WHERE conversation_id = ?",
            ("lifecycle_test",)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Great response!"
        assert row[1] == 5

    def test_security_integration(self):
        bridge = OpenCodeBridge()

        dangerous_cmds = [
            "rm -rf /",
            "sudo rm -rf /home",
        ]

        for cmd in dangerous_cmds:
            valid, msg, cmd_type, args = bridge._validate_command(cmd)
            assert valid is False

        dangerous_formatted = [
            'docker "ps"',
            'bash "dd if=/dev/zero of=/dev/sda"',
        ]

        for cmd in dangerous_formatted:
            valid, msg, cmd_type, args = bridge._validate_command(cmd)
            assert valid is False

        safe_cmds = [
            'bash "ls -la"',
            'bash "python --version"',
        ]
        for cmd in safe_cmds:
            valid, msg, cmd_type, args = bridge._validate_command(cmd)
            assert valid is True

    @pytest.mark.asyncio
    async def test_save_and_load_preferences(self, tmp_path):
        db_path = tmp_path / "prefs.db"
        memory = _create_memory(db_path)

        memory.update_preference("framework", "pytest", source="explicit")

        prefs = memory.get_user_preferences()
        assert "framework" in prefs
        assert "pytest" in prefs

    @pytest.mark.asyncio
    async def test_project_tracking(self, tmp_path):
        db_path = tmp_path / "projects.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="proj_test",
            user_message="Working on devsynapse-ai today",
            ai_response="Great! Let's continue"
        )

        context = memory.get_projects_context()
        assert "devsynapse-ai" in context

    @pytest.mark.asyncio
    async def test_learning_from_feedback(self, tmp_path):
        db_path = tmp_path / "learn.db"
        memory = _create_memory(db_path)

        memory.update_preference("database", "sqlite", source="learned")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT confidence FROM user_preferences WHERE key = ? AND value = ?",
            ("database", "sqlite")
        )
        initial = cursor.fetchone()[0]
        conn.close()

        await memory.save_feedback(
            conversation_id="learn_test",
            feedback="Excelente recomendação!",
            score=5
        )

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT confidence FROM user_preferences WHERE key = ? AND value = ?",
            ("database", "sqlite")
        )
        final = cursor.fetchone()[0]
        conn.close()

        assert final > initial
