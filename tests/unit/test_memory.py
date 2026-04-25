"""
Unit tests for memory system
"""
import pytest
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def _create_memory(db_path):
    """Create MemorySystem with a specific DB path"""
    with patch('core.memory.MEMORY_DB_PATH', str(db_path)):
        from core.memory import MemorySystem
        memory = MemorySystem()
        memory.add_project("devsynapse-ai", "/home/irving/ruas/repos/devsynapse-ai",
                           "ai-assistant", "high")
        memory.add_project("botassist-whatsapp", "/home/irving/ruas/repos/botassist-whatsapp",
                           "electron-app", "high")
        return memory


class TestMemorySystem:

    def test_init_creates_db(self, tmp_path):
        db_path = tmp_path / "test_init.db"
        memory = _create_memory(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        conn.close()

        assert 'conversations' in tables
        assert 'user_preferences' in tables
        assert 'projects' in tables
        assert 'decisions' in tables

    def test_get_user_preferences(self, tmp_path):
        db_path = tmp_path / "test_prefs.db"
        memory = _create_memory(db_path)
        prefs = memory.get_user_preferences()
        assert isinstance(prefs, str)
        assert len(prefs) > 0

    def test_get_projects_context(self, tmp_path):
        db_path = tmp_path / "test_projects.db"
        memory = _create_memory(db_path)
        context = memory.get_projects_context()
        assert isinstance(context, str)
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_save_and_get_conversation_context(self, tmp_path):
        db_path = tmp_path / "test_conv.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="test_conv_1",
            user_message="Hello!",
            ai_response="Hi there!",
            llm_usage={
                "provider": "deepseek",
                "model": "deepseek-chat",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "prompt_cache_hit_tokens": 2,
                "prompt_cache_miss_tokens": 8,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.00000168,
            },
        )

        context = await memory.get_conversation_context("test_conv_1")
        assert "conversation_history" in context
        assert len(context["conversation_history"]) > 0
        assert context["project_name"] is None
        assert context["conversation_history"][0]["role"] == "user"
        assert context["conversation_history"][0]["content"] == "Hello!"
        assert context["conversation_messages"][1]["tokenUsage"]["total_tokens"] == 15
        assert context["conversation_messages"][1]["tokenUsage"]["estimated_cost_usd"] == pytest.approx(
            0.00000168
        )
        assert "projectName" not in context["conversation_messages"][1]

    def test_update_preference(self, tmp_path):
        db_path = tmp_path / "test_upref.db"
        memory = _create_memory(db_path)

        memory.update_preference("language", "Python", source="learned")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM user_preferences WHERE key = ?", ("language",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "Python"

    @pytest.mark.asyncio
    async def test_save_feedback_updates_confidence(self, tmp_path):
        db_path = tmp_path / "test_feedback.db"
        memory = _create_memory(db_path)

        memory.update_preference("editor", "vscode", source="learned")

        await memory.save_feedback(
            conversation_id="test_fb_1",
            feedback="Excelente resposta, muito útil!",
            score=5
        )

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT confidence FROM user_preferences WHERE key = ? AND value = ?",
            ("editor", "vscode")
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] > 0.7

    @pytest.mark.asyncio
    async def test_save_command_execution(self, tmp_path):
        db_path = tmp_path / "test_cmd.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="test_cmd_1",
            user_message="list files",
            ai_response="Running ls -la",
            opencode_command="ls -la"
        )

        await memory.save_command_execution(
            conversation_id="test_cmd_1",
            command="ls -la",
            success=True,
            result="Files listed successfully",
            output="file1\nfile2",
            status="success",
            reason_code=None,
            project_name="devsynapse-ai",
        )

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT command_executed, execution_result FROM conversations WHERE conversation_id = ?",
            ("test_cmd_1",)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 1
        assert "successfully" in row[1]

        context = await memory.get_conversation_context("test_cmd_1")
        assistant_message = context["conversation_messages"][1]
        assert assistant_message["command"] == "ls -la"
        assert assistant_message["commandStatus"] == "success"
        assert "file1" in assistant_message["commandResult"]
        assert assistant_message["projectName"] == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_save_interaction_infers_project_name(self, tmp_path):
        db_path = tmp_path / "test_project_infer.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="conv_project_infer",
            user_message="Analise o devsynapse-ai",
            ai_response='read "/home/irving/ruas/repos/devsynapse-ai/README.md"',
            opencode_command='read "/home/irving/ruas/repos/devsynapse-ai/README.md"',
        )

        context = await memory.get_conversation_context("conv_project_infer")
        assert context["project_name"] == "devsynapse-ai"
        assert context["conversation_messages"][0]["projectName"] == "devsynapse-ai"
        assistant_message = context["conversation_messages"][1]
        assert assistant_message["projectName"] == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_save_interaction_persists_explicit_project_name(self, tmp_path):
        db_path = tmp_path / "test_project_explicit.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="conv_project_explicit",
            user_message="Analise este repositório",
            ai_response="Resposta com contexto explícito",
            project_name="devsynapse-ai",
        )

        context = await memory.get_conversation_context("conv_project_explicit")
        conversations = memory.list_conversations()

        assert context["project_name"] == "devsynapse-ai"
        assert context["conversation_messages"][0]["projectName"] == "devsynapse-ai"
        assert context["conversation_messages"][1]["projectName"] == "devsynapse-ai"
        assert conversations[0]["project_name"] == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_list_conversations_returns_recent_summaries(self, tmp_path):
        db_path = tmp_path / "test_conversation_list.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="conv_a",
            user_message="Primeira conversa sobre repositorios",
            ai_response="Resposta A",
        )
        await memory.save_interaction(
            conversation_id="conv_b",
            user_message="Segunda conversa sobre docker",
            ai_response="Resposta B",
            llm_usage={
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 12,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.00000392,
            },
        )

        conversations = memory.list_conversations()

        assert len(conversations) >= 2
        assert conversations[0]["id"] == "conv_b"
        assert "Segunda conversa" in conversations[0]["title"]
        assert conversations[0]["total_tokens"] == 20
        assert conversations[0]["estimated_cost_usd"] == pytest.approx(0.00000392)

    def test_get_llm_usage_stats_and_csv_export(self, tmp_path):
        db_path = tmp_path / "test_usage_export.db"
        memory = _create_memory(db_path)

        import asyncio

        asyncio.run(
            memory.save_interaction(
                conversation_id="conv_usage",
                user_message="Mensagem com uso",
                ai_response="Resposta com uso",
                llm_usage={
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                    "prompt_tokens": 100,
                    "completion_tokens": 25,
                    "total_tokens": 125,
                    "prompt_cache_hit_tokens": 20,
                    "prompt_cache_miss_tokens": 80,
                    "reasoning_tokens": 0,
                    "estimated_cost_usd": 0.0000184,
                },
            )
        )

        stats = memory.get_llm_usage_stats(hours=24)
        assert stats["totals"]["request_count"] == 1
        assert stats["totals"]["total_tokens"] == 125
        assert stats["totals"]["estimated_cost_usd"] == pytest.approx(0.0000184)

        csv_data = memory.export_llm_usage_csv()
        assert "conversation_id,timestamp,provider,model" in csv_data
        assert "conv_usage" in csv_data
        assert "125" in csv_data

    def test_get_project_usage_breakdown(self, tmp_path):
        db_path = tmp_path / "test_project_usage.db"
        memory = _create_memory(db_path)

        import asyncio

        asyncio.run(
            memory.save_interaction(
                conversation_id="conv_project",
                user_message="Analise o projeto devsynapse-ai",
                ai_response='read "/home/irving/ruas/repos/devsynapse-ai/README.md"',
                opencode_command='read "/home/irving/ruas/repos/devsynapse-ai/README.md"',
                llm_usage={
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                    "prompt_tokens": 200,
                    "completion_tokens": 20,
                    "total_tokens": 220,
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 200,
                    "reasoning_tokens": 0,
                    "estimated_cost_usd": 0.0000336,
                },
            )
        )

        breakdown = memory.get_project_usage_breakdown(hours=24)
        assert breakdown[0]["project_name"] == "devsynapse-ai"
        assert breakdown[0]["total_tokens"] == 220
        assert breakdown[0]["estimated_cost_usd"] == pytest.approx(0.0000336)

    def test_get_llm_budget_status(self, tmp_path):
        db_path = tmp_path / "test_budget_status.db"
        memory = _create_memory(db_path)
        memory.update_app_settings(
            {
                "llm_daily_budget_usd": 0.01,
                "llm_monthly_budget_usd": 0.05,
                "llm_budget_warning_threshold_pct": 50,
                "llm_budget_critical_threshold_pct": 80,
            }
        )

        import asyncio

        asyncio.run(
            memory.save_interaction(
                conversation_id="conv_budget",
                user_message="Mensagem com custo de budget",
                ai_response="Resposta com custo",
                llm_usage={
                    "provider": "deepseek",
                    "model": "deepseek-v4-flash",
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 100,
                    "reasoning_tokens": 0,
                    "estimated_cost_usd": 0.0085,
                },
            )
        )

        budget = memory.get_llm_budget_status()
        assert budget["overall_status"] == "critical"
        assert budget["daily"]["level"] == "critical"
        assert budget["daily"]["usage_pct"] == pytest.approx(85.0)
        assert budget["monthly"]["level"] == "healthy"

    @pytest.mark.asyncio
    async def test_rename_and_delete_conversation(self, tmp_path):
        db_path = tmp_path / "test_conversation_mutations.db"
        memory = _create_memory(db_path)

        await memory.save_interaction(
            conversation_id="conv_mutation",
            user_message="Conversa para renomear",
            ai_response="Resposta inicial",
        )

        renamed = memory.rename_conversation("conv_mutation", "Título personalizado")
        assert renamed is True

        conversations = memory.list_conversations()
        assert conversations[0]["title"] == "Título personalizado"

        deleted = memory.delete_conversation("conv_mutation")
        assert deleted is True
        assert memory.list_conversations() == []

    def test_get_user_preferences_formatted(self, tmp_path):
        db_path = tmp_path / "test_prefs2.db"
        memory = _create_memory(db_path)

        memory.update_preference("theme", "dark", source="explicit")

        prefs_text = memory.get_user_preferences()
        assert "theme" in prefs_text
        assert "dark" in prefs_text

    def test_replace_and_get_project_permissions(self, tmp_path):
        db_path = tmp_path / "test_project_permissions.db"
        memory = _create_memory(db_path)

        memory.replace_project_permissions("irving", ["devsynapse-ai", "botassist-site"])

        user_permissions = memory.get_project_permissions("irving")
        all_permissions = memory.get_project_permissions()

        assert user_permissions == ["botassist-site", "devsynapse-ai"]
        assert all_permissions["irving"] == ["botassist-site", "devsynapse-ai"]

    def test_admin_audit_logs_are_persisted(self, tmp_path):
        db_path = tmp_path / "test_admin_audit.db"
        memory = _create_memory(db_path)

        memory.log_admin_action(
            actor_username="admin",
            action="update_project_permissions",
            target_username="irving",
            details={"project_mutation_allowlist": ["devsynapse-ai"]},
        )

        logs = memory.get_admin_audit_logs()

        assert len(logs) == 1
        assert logs[0]["actor_username"] == "admin"
        assert logs[0]["target_username"] == "irving"
        assert logs[0]["action"] == "update_project_permissions"
        assert logs[0]["details"]["project_mutation_allowlist"] == ["devsynapse-ai"]
