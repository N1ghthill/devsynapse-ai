"""
Route-level integration tests for chat and conversation APIs.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

PROJECT_NAME = "devsynapse-ai"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _MonitoringStub:
    def __init__(self):
        self.api_requests = []

    def log_api_request(self, *args, **kwargs):
        self.api_requests.append(kwargs)
        return None

    def log_command_execution(self, *args, **kwargs):
        return None

    def log_system_metric(self, *args, **kwargs):
        return None

    def get_system_health(self):
        return {
            "overall_status": "healthy",
            "command_error_rate": 0.0,
            "api_error_rate": 0.0,
            "active_alerts": 0,
        }

    def get_command_stats(self, hours=24):
        return {
            "totals": {"total": 0, "successful": 0, "failed": 0},
            "by_type": [],
            "recent": [],
            "timeframe_hours": hours,
        }

    def get_api_stats(self, hours=24):
        return {
            "totals": {"total_requests": 0, "avg_response_time": 0.0, "unique_endpoints": 0},
            "by_endpoint": [],
            "status_codes": [],
            "timeframe_hours": hours,
        }

    def get_active_alerts(self):
        return []

    def sync_llm_budget_alerts(self, budget_status):
        self.budget_status = budget_status


@pytest.fixture
def route_services(tmp_path, monkeypatch):
    import core.memory as memory_module
    from core.brain import DevSynapseBrain
    from core.memory import MemorySystem
    from core.opencode_bridge import OpenCodeBridge

    db_path = tmp_path / "route_contract.db"
    monkeypatch.setattr(memory_module, "MEMORY_DB_PATH", db_path)

    memory = MemorySystem()
    memory.add_project(PROJECT_NAME, str(PROJECT_ROOT), "ai-assistant", "high")
    monitoring = _MonitoringStub()
    bridge = OpenCodeBridge(monitoring_system=monitoring)
    brain = DevSynapseBrain(memory, bridge)
    user = {"username": "irving", "role": "user"}
    admin = {"username": "admin", "role": "admin"}

    return SimpleNamespace(
        memory=memory,
        bridge=bridge,
        brain=brain,
        monitoring=monitoring,
        user=user,
        admin=admin,
    )


@pytest.mark.asyncio
async def test_chat_route_forwards_and_returns_explicit_project_name(route_services):
    from api.models import ChatRequest
    from api.routes.chat import chat_endpoint

    route_services.brain.process_message = AsyncMock(
        return_value=("Resposta do projeto", None, None)
    )

    response = await chat_endpoint(
        request=ChatRequest(
            message="Analise o repositório",
            conversation_id="conv_chat_project",
            project_name="devsynapse-ai",
        ),
        user=route_services.user,
        brain=route_services.brain,
        memory_system=route_services.memory,
        monitoring_system=route_services.monitoring,
    )

    route_services.brain.process_message.assert_awaited_once_with(
        user_message="Analise o repositório",
        conversation_id="conv_chat_project",
        project_name="devsynapse-ai",
        user_id="irving",
        user_role="user",
        project_mutation_allowlist=[],
    )
    assert response.project_name == "devsynapse-ai"


@pytest.mark.asyncio
async def test_chat_route_returns_persisted_project_name(route_services):
    from api.models import ChatRequest
    from api.routes.chat import chat_endpoint

    await route_services.memory.save_interaction(
        conversation_id="conv_chat_existing_project",
        user_message="Contexto inicial",
        ai_response="Resposta inicial",
        project_name="devsynapse-ai",
    )
    route_services.brain.process_message = AsyncMock(
        return_value=("Resposta de continuidade", None, None)
    )

    response = await chat_endpoint(
        request=ChatRequest(
            message="Continue",
            conversation_id="conv_chat_existing_project",
        ),
        user=route_services.user,
        brain=route_services.brain,
        memory_system=route_services.memory,
        monitoring_system=route_services.monitoring,
    )

    assert response.project_name == "devsynapse-ai"


@pytest.mark.asyncio
async def test_conversation_list_rename_and_delete_flow(route_services):
    from api.models import ConversationRenameRequest
    from api.routes.chat import delete_conversation, list_conversations, rename_conversation

    await route_services.memory.save_interaction(
        conversation_id="conv_http",
        user_message="Conversa criada pela rota",
        ai_response="Resposta inicial",
    )

    list_response = await list_conversations(
        user=route_services.user,
        memory_system=route_services.memory,
    )
    assert list_response["conversations"][0]["id"] == "conv_http"

    rename_response = await rename_conversation(
        conversation_id="conv_http",
        payload=ConversationRenameRequest(title="Título via rota"),
        user=route_services.user,
        memory_system=route_services.memory,
    )
    assert rename_response == {"success": True, "conversation_id": "conv_http"}

    renamed_list = await list_conversations(
        user=route_services.user,
        memory_system=route_services.memory,
    )
    assert renamed_list["conversations"][0]["title"] == "Título via rota"

    delete_response = await delete_conversation(
        conversation_id="conv_http",
        user=route_services.user,
        memory_system=route_services.memory,
    )
    assert delete_response == {"success": True, "conversation_id": "conv_http"}

    deleted_list = await list_conversations(
        user=route_services.user,
        memory_system=route_services.memory,
    )
    assert deleted_list["conversations"] == []


@pytest.mark.asyncio
async def test_execute_returns_structured_blocked_status(route_services):
    from api.models import CommandExecutionRequest
    from api.routes.chat import execute_command

    await route_services.memory.save_interaction(
        conversation_id="conv_exec_blocked",
        user_message="Rode docker ps",
        ai_response='bash "docker ps"',
        opencode_command='bash "docker ps"',
    )

    background_tasks = BackgroundTasks()
    response = await execute_command(
        request=CommandExecutionRequest(
            conversation_id="conv_exec_blocked",
            command='bash "docker ps"',
            confirm=True,
        ),
        background_tasks=background_tasks,
        user=route_services.user,
        bridge=route_services.bridge,
        memory_system=route_services.memory,
        monitoring_system=route_services.monitoring,
    )
    await background_tasks()

    assert response.success is False
    assert response.status == "blocked"
    assert response.reason_code == "validation_failed"
    assert response.project_name is None
    assert route_services.monitoring.api_requests[-1]["endpoint"] == "/execute"
    assert route_services.monitoring.api_requests[-1]["status_code"] == 200


@pytest.mark.asyncio
async def test_execute_returns_structured_success_status(route_services, tmp_path):
    from api.models import CommandExecutionRequest
    from api.routes.chat import execute_command

    allowed_file = tmp_path / "api_execute_read.txt"
    allowed_file.write_text("linha 1\nlinha 2\n", encoding="utf-8")

    command = f'read "{allowed_file}"'
    await route_services.memory.save_interaction(
        conversation_id="conv_exec_success",
        user_message="Leia o arquivo temporário",
        ai_response=command,
        opencode_command=command,
    )

    response = await execute_command(
        request=CommandExecutionRequest(
            conversation_id="conv_exec_success",
            command=command,
            confirm=True,
        ),
        background_tasks=BackgroundTasks(),
        user=route_services.user,
        bridge=route_services.bridge,
        memory_system=route_services.memory,
        monitoring_system=route_services.monitoring,
    )

    assert response.success is True
    assert response.status == "success"
    assert response.reason_code is None
    assert "linha 1" in (response.output or "")
    assert response.project_name is None


@pytest.mark.asyncio
async def test_execute_returns_resolved_project_name(route_services):
    from api.models import CommandExecutionRequest
    from api.routes.chat import execute_command

    route_services.bridge.execute_command = AsyncMock(
        return_value=(
            True,
            "Arquivo lido",
            "conteúdo",
            "success",
            None,
            "devsynapse-ai",
        )
    )

    response = await execute_command(
        request=CommandExecutionRequest(
            conversation_id="conv_exec_project",
            command=f'read "{PROJECT_ROOT / "README.md"}"',
            confirm=True,
        ),
        background_tasks=BackgroundTasks(),
        user=route_services.user,
        bridge=route_services.bridge,
        memory_system=route_services.memory,
        monitoring_system=route_services.monitoring,
    )

    assert response.success is True
    assert response.project_name == "devsynapse-ai"


@pytest.mark.asyncio
async def test_delete_conversation_returns_404_for_unknown_id(route_services):
    from api.routes.chat import delete_conversation

    with pytest.raises(HTTPException) as exc_info:
        await delete_conversation(
            conversation_id="missing",
            user=route_services.user,
            memory_system=route_services.memory,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_conversations_and_stats_include_llm_usage(route_services):
    from api.routes.chat import list_conversations
    from api.routes.monitoring import get_monitoring_stats

    route_services.memory.update_app_settings(
        {
            "llm_daily_budget_usd": 0.00004,
            "llm_monthly_budget_usd": 0.001,
            "llm_budget_warning_threshold_pct": 80,
            "llm_budget_critical_threshold_pct": 100,
        }
    )

    await route_services.memory.save_interaction(
        conversation_id="conv_usage_stats",
        user_message="Mensagem com custo sobre devsynapse-ai",
        ai_response=f'Resposta com custo read "{PROJECT_ROOT / "README.md"}"',
        opencode_command=f'read "{PROJECT_ROOT / "README.md"}"',
        llm_usage={
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "prompt_tokens": 300,
            "completion_tokens": 40,
            "total_tokens": 340,
            "prompt_cache_hit_tokens": 50,
            "prompt_cache_miss_tokens": 250,
            "reasoning_tokens": 0,
            "estimated_cost_usd": 0.0000462,
        },
    )

    conversations = await list_conversations(
        user=route_services.user,
        memory_system=route_services.memory,
    )
    assert conversations["conversations"][0]["total_tokens"] == 340
    assert conversations["conversations"][0]["estimated_cost_usd"] == pytest.approx(0.0000462)

    stats = await get_monitoring_stats(
        hours=24,
        user=route_services.user,
        monitoring_system=route_services.monitoring,
        memory_system=route_services.memory,
    )
    assert stats.llm_usage["totals"]["total_tokens"] == 340
    assert stats.llm_usage["totals"]["estimated_cost_usd"] == pytest.approx(0.0000462)
    assert stats.llm_usage["by_project"][0]["project_name"] == "devsynapse-ai"
    assert stats.llm_usage["budget"]["daily"]["level"] == "critical"
    assert stats.llm_usage["budget"]["monthly"]["level"] == "healthy"


@pytest.mark.asyncio
async def test_get_settings_includes_budget_fields(route_services):
    from api.routes.settings import get_settings_route

    route_services.memory.update_app_settings(
        {
            "llm_daily_budget_usd": 12.5,
            "llm_monthly_budget_usd": 150.0,
            "llm_budget_warning_threshold_pct": 70,
            "llm_budget_critical_threshold_pct": 95,
        }
    )

    response = await get_settings_route(
        user=route_services.user,
        memory_system=route_services.memory,
    )

    assert response.llm_daily_budget_usd == pytest.approx(12.5)
    assert response.llm_monthly_budget_usd == pytest.approx(150.0)
    assert response.llm_budget_warning_threshold_pct == pytest.approx(70)
    assert response.llm_budget_critical_threshold_pct == pytest.approx(95)


@pytest.mark.asyncio
async def test_get_settings_admin_includes_all_project_names(route_services):
    from api.routes.settings import get_settings_route

    response = await get_settings_route(
        user=route_services.admin,
        memory_system=route_services.memory,
    )

    assert "devsynapse-ai" in response.project_mutation_allowlist


@pytest.mark.asyncio
async def test_list_projects_requires_user_context_and_hides_paths(route_services):
    from api.routes.settings import list_projects

    response = await list_projects(
        user=route_services.user,
        memory_system=route_services.memory,
    )

    project = next(item for item in response.projects if item.name == "devsynapse-ai")
    assert not hasattr(project, "path")
    assert response.count >= 1


@pytest.mark.asyncio
async def test_admin_list_projects_includes_paths(route_services):
    from api.routes.admin import list_admin_projects

    response = await list_admin_projects(
        admin=route_services.admin,
        memory_system=route_services.memory,
    )

    project = next(item for item in response.projects if item.name == "devsynapse-ai")
    assert project.path == str(PROJECT_ROOT)
    assert response.count >= 1


@pytest.mark.asyncio
async def test_update_settings_rejects_critical_threshold_below_warning(route_services):
    from api.models import SettingsUpdateRequest
    from api.routes.settings import update_settings

    with pytest.raises(HTTPException) as exc_info:
        await update_settings(
            settings_data=SettingsUpdateRequest(
                llm_budget_warning_threshold_pct=90,
                llm_budget_critical_threshold_pct=80,
            ),
            user=route_services.user,
            memory_system=route_services.memory,
            brain=route_services.brain,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_admin_user_summary_shows_global_scope_for_admin(route_services):
    from api.routes.admin import list_users

    route_services.memory.upsert_user("admin", "hash", role="admin")
    route_services.memory.upsert_user("irving", "hash", role="user")
    route_services.memory.replace_project_permissions("irving", ["devsynapse-ai"])

    response = await list_users(
        admin=route_services.admin,
        memory_system=route_services.memory,
    )

    users = {user.username: user for user in response.users}
    assert "devsynapse-ai" in users["admin"].project_mutation_allowlist
    assert users["irving"].project_mutation_allowlist == ["devsynapse-ai"]


@pytest.mark.asyncio
async def test_admin_cannot_update_admin_project_allowlist(route_services):
    from api.models import AdminUserPermissionsUpdateRequest
    from api.routes.admin import update_user_permissions

    route_services.memory.upsert_user("admin", "hash", role="admin")

    with pytest.raises(HTTPException) as exc_info:
        await update_user_permissions(
            username="admin",
            payload=AdminUserPermissionsUpdateRequest(project_mutation_allowlist=[]),
            admin=route_services.admin,
            memory_system=route_services.memory,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_admin_can_create_project(route_services, tmp_path):
    from api.models import ProjectCreateRequest
    from api.routes.admin import create_project

    project_dir = tmp_path / "new-project"
    project_dir.mkdir()

    response = await create_project(
        payload=ProjectCreateRequest(
            name="new-project",
            path=str(project_dir),
            type="test",
            priority="high",
        ),
        admin=route_services.admin,
        memory_system=route_services.memory,
        bridge=route_services.bridge,
    )

    assert response.name == "new-project"
    assert response.path == str(project_dir.resolve())
    assert route_services.bridge.get_project_context("new-project")["path"] == str(
        project_dir.resolve()
    )
    assert "new-project" in route_services.memory.list_project_names()


@pytest.mark.asyncio
async def test_admin_create_project_rejects_duplicate_names(route_services):
    from api.models import ProjectCreateRequest
    from api.routes.admin import create_project

    with pytest.raises(HTTPException) as exc_info:
        await create_project(
            payload=ProjectCreateRequest(
                name="devsynapse-ai",
                path=str(PROJECT_ROOT),
                type="test",
                priority="high",
            ),
            admin=route_services.admin,
            memory_system=route_services.memory,
            bridge=route_services.bridge,
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_admin_create_project_uses_defaults_for_optional_fields(route_services, tmp_path):
    from api.models import ProjectCreateRequest
    from api.routes.admin import create_project

    project_dir = tmp_path / "defaulted-project"
    project_dir.mkdir()

    response = await create_project(
        payload=ProjectCreateRequest(
            name="defaulted-project",
            path=str(project_dir),
            type="",
            priority="",
        ),
        admin=route_services.admin,
        memory_system=route_services.memory,
        bridge=route_services.bridge,
    )

    assert response.type == "project"
    assert response.priority == "medium"


@pytest.mark.asyncio
async def test_export_usage_csv_route(route_services):
    from api.routes.chat import export_conversation_usage_csv

    await route_services.memory.save_interaction(
        conversation_id="conv_csv",
        user_message="Exporte isso",
        ai_response="Linha exportável",
        llm_usage={
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "prompt_tokens": 50,
            "completion_tokens": 10,
            "total_tokens": 60,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 50,
            "reasoning_tokens": 0,
            "estimated_cost_usd": 0.0000098,
        },
    )

    response = await export_conversation_usage_csv(
        user=route_services.user,
        memory_system=route_services.memory,
    )

    assert response.media_type == "text/csv"
    assert "conv_csv" in response.body.decode()
