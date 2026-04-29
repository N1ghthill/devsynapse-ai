"""
Unit tests for memory system
"""
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from core.llm_optimization import build_task_profile

PROJECT_NAME = "devsynapse-ai"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOTASSIST_ROOT = PROJECT_ROOT.parent / "botassist-whatsapp"


def _create_memory(db_path):
    """Create MemorySystem with a specific DB path"""
    with patch('core.memory.MEMORY_DB_PATH', str(db_path)):
        from core.memory import MemorySystem
        memory = MemorySystem()
        memory.add_project(PROJECT_NAME, str(PROJECT_ROOT),
                           "ai-assistant", "high")
        memory.add_project("botassist-whatsapp", str(BOTASSIST_ROOT),
                           "electron-app", "high")
        return memory


class TestMemorySystem:

    def test_init_creates_db(self, tmp_path):
        db_path = tmp_path / "test_init.db"
        _create_memory(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        conn.close()

        assert 'conversations' in tables
        assert 'user_preferences' in tables
        assert 'projects' in tables
        assert 'decisions' in tables
        assert 'agent_learning' in tables
        assert 'agent_route_decisions' in tables
        assert 'project_memories' in tables
        assert 'skills' in tables
        assert 'skill_activations' in tables
        assert 'learning_nudge_events' in tables

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

    def test_list_projects_and_lookup_include_persisted_projects(self, tmp_path):
        db_path = tmp_path / "test_project_registry.db"
        memory = _create_memory(db_path)
        project_path = PROJECT_ROOT / "docs"

        memory.add_project("docs-project", str(project_path), "docs", "low")

        projects = memory.list_projects()
        lookup = memory.get_project_lookup()

        assert any(project["name"] == "docs-project" for project in projects)
        assert "docs-project" in memory.list_project_names()
        assert lookup["docs-project"]["path"] == str(project_path)
        assert lookup["docs-project"]["type"] == "docs"

    def test_project_lists_hide_missing_paths_but_admin_can_inspect_them(self, tmp_path):
        db_path = tmp_path / "test_missing_project_registry.db"
        memory = _create_memory(db_path)
        active_path = tmp_path / "active-project"
        missing_path = tmp_path / "deleted-project"
        active_path.mkdir()

        memory.add_project("active-project", str(active_path), "test", "medium")
        memory.add_project("deleted-project", str(missing_path), "test", "medium")

        public_projects = {project["name"]: project for project in memory.list_projects()}
        admin_projects = {
            project["name"]: project
            for project in memory.list_projects(include_missing=True)
        }
        lookup = memory.get_project_lookup()
        context = memory.get_projects_context()

        assert "active-project" in public_projects
        assert public_projects["active-project"]["path_exists"] is True
        assert "deleted-project" not in public_projects
        assert admin_projects["deleted-project"]["path_exists"] is False
        assert "deleted-project" not in lookup
        assert "deleted-project" not in context

    def test_delete_project_removes_registry_and_permissions(self, tmp_path):
        db_path = tmp_path / "test_delete_project_registry.db"
        memory = _create_memory(db_path)
        project_path = tmp_path / "removable-project"
        project_path.mkdir()
        memory.add_project("removable-project", str(project_path), "test", "medium")
        memory.replace_project_permissions("irving", ["removable-project", "devsynapse-ai"])

        assert memory.delete_project("removable-project") is True

        assert memory.get_project("removable-project", include_missing=True) is None
        assert "removable-project" not in memory.get_project_permissions("irving")

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
    async def test_negative_feedback_teaches_agent_to_prefer_pro(self, tmp_path):
        db_path = tmp_path / "test_agent_feedback.db"
        memory = _create_memory(db_path)
        message = "Debug erro complexo no cache"

        await memory.save_interaction(
            conversation_id="conv_agent_feedback",
            user_message=message,
            ai_response="Resposta incompleta",
            llm_usage={
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "prompt_cache_hit_tokens": 0,
                "prompt_cache_miss_tokens": 100,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.0000168,
            },
        )

        await memory.save_feedback(
            conversation_id="conv_agent_feedback",
            feedback="Resposta ruim, estava errado",
            score=1,
        )

        learning = memory.get_agent_learning(build_task_profile(message).signature)
        stats = memory.get_agent_learning_stats()

        assert learning is not None
        assert learning["preferred_model"] == "deepseek-v4-pro"
        assert learning["failure_count"] == 1
        assert stats["learned_patterns"] == 1

    def test_record_agent_route_decision_tracks_model(self, tmp_path):
        from core.llm_optimization import ModelRoute

        db_path = tmp_path / "test_agent_decision.db"
        memory = _create_memory(db_path)

        memory.record_agent_route_decision(
            conversation_id="conv_route",
            route=ModelRoute(
                model="deepseek-v4-flash",
                complexity="simple",
                reason="short_request",
                task_type="concept",
                task_signature="concept:abc",
            ),
            usage={
                "model": "deepseek-v4-flash",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "prompt_cache_hit_tokens": 8,
                "prompt_cache_miss_tokens": 2,
                "estimated_cost_usd": 0.00001,
            },
        )

        stats = memory.get_agent_learning_stats()
        assert stats["by_model"] == [{"selected_model": "deepseek-v4-flash", "count": 1}]

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

        inferred_project = await memory.save_interaction(
            conversation_id="conv_project_infer",
            user_message="Analise o devsynapse-ai",
            ai_response=f'read "{PROJECT_ROOT / "README.md"}"',
            opencode_command=f'read "{PROJECT_ROOT / "README.md"}"',
        )

        context = await memory.get_conversation_context("conv_project_infer")
        assert inferred_project == "devsynapse-ai"
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
                ai_response=f'read "{PROJECT_ROOT / "README.md"}"',
                opencode_command=f'read "{PROJECT_ROOT / "README.md"}"',
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

    def test_project_memory_confidence_decay_and_feedback(self, tmp_path):
        db_path = tmp_path / "test_project_memory.db"
        memory = _create_memory(db_path)

        saved = memory.upsert_project_memory(
            content="Use pytest -q for the fast local test loop.",
            project_name="devsynapse-ai",
            memory_type="procedure",
            confidence_score=0.7,
            memory_decay_score=0.01,
            tags=["pytest"],
        )
        reinforced = memory.upsert_project_memory(
            content="Use pytest -q for the fast local test loop.",
            project_name="devsynapse-ai",
            memory_type="procedure",
            confidence_score=0.7,
            memory_decay_score=0.01,
            tags=["tests"],
        )
        listed = memory.list_project_memories(
            project_name="devsynapse-ai",
            query="pytest tests",
        )
        adjusted = memory.adjust_project_memory_confidence(saved["id"], -0.1)

        assert reinforced["id"] == saved["id"]
        assert reinforced["evidence_count"] == 2
        assert listed[0]["effective_confidence"] > 0.0
        assert "tests" in reinforced["tags"]
        assert adjusted["confidence_score"] < reinforced["confidence_score"]

    @pytest.mark.asyncio
    async def test_command_success_nudge_creates_memory_and_skill(self, tmp_path):
        db_path = tmp_path / "test_learning_nudge.db"
        memory = _create_memory(db_path)
        command = 'bash "pytest -q"'

        await memory.save_interaction(
            conversation_id="conv_nudge",
            user_message="Rode os testes pytest e explique o resultado",
            ai_response=f"Vou executar {command}",
            opencode_command=command,
            project_name="devsynapse-ai",
        )
        await memory.save_command_execution(
            conversation_id="conv_nudge",
            command=command,
            success=True,
            result="Comando executado com sucesso",
            output="3 passed",
            status="success",
            project_name="devsynapse-ai",
        )

        memories = memory.list_project_memories(project_name="devsynapse-ai", query="pytest")
        skills = memory.list_skills()
        stats = memory.get_knowledge_stats()

        assert any(item["memory_type"] == "procedure" for item in memories)
        assert any(skill["slug"] == "test-pytest-workflow" for skill in skills)
        assert stats["nudges"]["total_events"] >= 1
        assert stats["skills"]["active_skills"] >= 1

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
