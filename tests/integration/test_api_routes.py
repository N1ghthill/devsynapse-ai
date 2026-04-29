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


def _isolate_bootstrap_runtime(monkeypatch, tmp_path):
    import core.bootstrap as bootstrap_module
    import core.runtime_config as runtime_config_module

    config_file = tmp_path / "runtime" / "config" / ".env"
    data_dir = tmp_path / "runtime" / "data"
    logs_dir = tmp_path / "runtime" / "logs"

    monkeypatch.setattr(bootstrap_module, "CONFIG_FILE", config_file)
    monkeypatch.setattr(bootstrap_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(bootstrap_module, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(runtime_config_module, "CONFIG_FILE", config_file)
    monkeypatch.setattr(runtime_config_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(runtime_config_module, "LOGS_DIR", logs_dir)

    return config_file


@pytest.mark.asyncio
async def test_bootstrap_complete_configures_first_run_runtime(route_services, tmp_path, monkeypatch):
    from api.models import BootstrapAdminRequest
    from api.routes.bootstrap import bootstrap_status, complete_bootstrap
    from core.auth import AuthService

    config_file = _isolate_bootstrap_runtime(monkeypatch, tmp_path)
    repos_root = tmp_path / "repos"
    project_dir = repos_root / "example-project"
    (project_dir / ".git").mkdir(parents=True)

    auth = AuthService(route_services.memory)
    auth.ensure_default_users()

    initial_status = await bootstrap_status(auth_service=auth)
    assert initial_status.requires_setup is True
    assert initial_status.admin_password_required is True
    assert initial_status.default_admin_username == "admin"

    response = await complete_bootstrap(
        request=BootstrapAdminRequest(
            admin_password="local-admin-pass",
            deepseek_api_key="sk-bootstrap-test",
            workspace_root=str(tmp_path),
            repos_root=str(repos_root),
        ),
        user=None,
        auth_service=auth,
        memory_system=route_services.memory,
        bridge=route_services.bridge,
        brain=route_services.brain,
    )

    assert response.user == {"username": "admin", "role": "admin"}
    assert response.access_token
    assert response.status.requires_setup is False
    assert response.registered_projects[0].name == "example-project"
    assert auth.authenticate_user("admin", "admin") is None
    assert auth.authenticate_user("admin", "local-admin-pass") == {
        "username": "admin",
        "role": "admin",
    }
    assert route_services.brain.api_key == "sk-bootstrap-test"
    assert route_services.bridge.known_projects["example-project"]["path"] == str(
        project_dir.resolve()
    )

    env_text = config_file.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-bootstrap-test" in env_text
    assert f"DEV_WORKSPACE_ROOT={tmp_path.resolve()}" in env_text
    assert f"DEV_REPOS_ROOT={repos_root.resolve()}" in env_text


@pytest.mark.asyncio
async def test_bootstrap_requires_admin_after_admin_password_is_configured(
    route_services, tmp_path, monkeypatch
):
    from api.models import BootstrapAdminRequest
    from api.routes.bootstrap import bootstrap_status, complete_bootstrap
    from core.auth import AuthService

    _isolate_bootstrap_runtime(monkeypatch, tmp_path)
    repos_root = tmp_path / "repos"
    repos_root.mkdir()

    auth = AuthService(route_services.memory)
    auth.bootstrap_admin_password("already-configured")

    status_response = await bootstrap_status(auth_service=auth)
    assert status_response.admin_password_required is False

    with pytest.raises(HTTPException) as exc_info:
        await complete_bootstrap(
            request=BootstrapAdminRequest(
                deepseek_api_key="sk-auth-required",
                repos_root=str(repos_root),
            ),
            user=None,
            auth_service=auth,
            memory_system=route_services.memory,
            bridge=route_services.bridge,
            brain=route_services.brain,
        )

    assert exc_info.value.status_code == 403

    response = await complete_bootstrap(
        request=BootstrapAdminRequest(
            deepseek_api_key="sk-auth-required",
            repos_root=str(repos_root),
        ),
        user=route_services.admin,
        auth_service=auth,
        memory_system=route_services.memory,
        bridge=route_services.bridge,
        brain=route_services.brain,
    )

    assert response.access_token is None
    assert response.status.requires_setup is False
    assert auth.authenticate_user("admin", "already-configured") == {
        "username": "admin",
        "role": "admin",
    }


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
        auto_execute=False,
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

    route_services.brain.process_message.assert_awaited_once_with(
        user_message="Continue",
        conversation_id="conv_chat_existing_project",
        project_name="devsynapse-ai",
        user_id="irving",
        user_role="user",
        project_mutation_allowlist=[],
        auto_execute=False,
    )
    assert response.project_name == "devsynapse-ai"


@pytest.mark.asyncio
async def test_chat_route_rejects_project_switch_inside_existing_conversation(route_services, tmp_path):
    from api.models import ChatRequest
    from api.routes.chat import chat_endpoint

    other_project = tmp_path / "other-project"
    other_project.mkdir()
    route_services.memory.add_project("other-project", str(other_project), "project", "medium")
    await route_services.memory.save_interaction(
        conversation_id="conv_locked_project",
        user_message="Contexto inicial",
        ai_response="Resposta inicial",
        project_name="devsynapse-ai",
    )
    route_services.brain.process_message = AsyncMock(
        return_value=("Resposta indevida", None, None)
    )

    with pytest.raises(HTTPException) as exc_info:
        await chat_endpoint(
            request=ChatRequest(
                message="Troque de projeto",
                conversation_id="conv_locked_project",
                project_name="other-project",
            ),
            user=route_services.user,
            brain=route_services.brain,
            memory_system=route_services.memory,
            monitoring_system=route_services.monitoring,
        )

    assert exc_info.value.status_code == 409
    route_services.brain.process_message.assert_not_awaited()


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
    assert stats.llm_usage["totals"]["cache_hit_rate_pct"] == pytest.approx(16.67)
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
            "llm_model_routing_enabled": "False",
            "llm_auto_economy_enabled": "True",
            "llm_cache_hit_warning_threshold_pct": 75,
        }
    )

    response = await get_settings_route(
        user=route_services.user,
        memory_system=route_services.memory,
        brain=route_services.brain,
    )

    assert response.llm_daily_budget_usd == pytest.approx(12.5)
    assert response.llm_monthly_budget_usd == pytest.approx(150.0)
    assert response.llm_budget_warning_threshold_pct == pytest.approx(70)
    assert response.llm_budget_critical_threshold_pct == pytest.approx(95)
    assert response.llm_model_routing_enabled is False
    assert response.llm_auto_economy_enabled is True
    assert response.llm_cache_hit_warning_threshold_pct == pytest.approx(75)


@pytest.mark.asyncio
async def test_get_settings_admin_includes_all_project_names(route_services):
    from api.routes.settings import get_settings_route

    response = await get_settings_route(
        user=route_services.admin,
        memory_system=route_services.memory,
        brain=route_services.brain,
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
            admin=route_services.admin,
            memory_system=route_services.memory,
            brain=route_services.brain,
        )

    assert exc_info.value.status_code == 400


def test_update_settings_route_requires_admin_dependency():
    from fastapi.routing import APIRoute

    from api.dependencies import require_admin
    from api.routes.settings import router

    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path == "/settings" and "PUT" in route.methods
    )

    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
    assert require_admin in dependency_calls


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
async def test_admin_can_create_project_directory_from_name(
    route_services, tmp_path, monkeypatch
):
    from api.models import ProjectCreateRequest
    from api.routes import admin as admin_routes

    repos_root = tmp_path / "repos"
    repos_root.mkdir()
    route_services.bridge.allowed_directories = [repos_root]
    monkeypatch.setattr(
        admin_routes,
        "get_settings",
        lambda: SimpleNamespace(dev_repos_root=repos_root),
    )

    response = await admin_routes.create_project(
        payload=ProjectCreateRequest(
            name="Meu Projeto Novo",
            create_directory=True,
        ),
        admin=route_services.admin,
        memory_system=route_services.memory,
        bridge=route_services.bridge,
    )

    assert response.name == "Meu Projeto Novo"
    assert response.path == str((repos_root / "meu-projeto-novo").resolve())
    assert (repos_root / "meu-projeto-novo").is_dir()
    assert route_services.bridge.get_project_context("Meu Projeto Novo")["path"] == response.path


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


@pytest.mark.asyncio
async def test_knowledge_routes_manage_memories_and_skills(route_services):
    from api.models import (
        ProjectMemoryCreateRequest,
        ProjectMemoryFeedbackRequest,
        SkillActivateRequest,
        SkillCreateRequest,
    )
    from api.routes.knowledge import (
        activate_skill,
        adjust_memory_confidence,
        create_memory,
        create_skill,
        knowledge_stats,
        list_memories,
        list_skills,
    )

    route_services.memory.replace_project_permissions("irving", ["devsynapse-ai"])

    memory_response = await create_memory(
        payload=ProjectMemoryCreateRequest(
            content="Prefer pytest -q before broader integration checks.",
            project_name="devsynapse-ai",
            memory_type="procedure",
            confidence_score=0.75,
        ),
        user=route_services.user,
        memory_system=route_services.memory,
    )
    memories = await list_memories(
        project_name="devsynapse-ai",
        query="pytest",
        user=route_services.user,
        memory_system=route_services.memory,
    )
    adjusted_memory = await adjust_memory_confidence(
        memory_id=memory_response.id,
        payload=ProjectMemoryFeedbackRequest(delta=0.1),
        user=route_services.user,
        memory_system=route_services.memory,
    )
    skill_response = await create_skill(
        payload=SkillCreateRequest(
            name="pytest triage",
            description="Debug pytest failures with the local project test loop.",
            category="test",
            body="## Steps\nRun `pytest -q`, inspect the first failure, then patch narrowly.",
            project_name=None,
        ),
        admin=route_services.admin,
        memory_system=route_services.memory,
    )
    activated = await activate_skill(
        skill_name="pytest-triage",
        payload=SkillActivateRequest(project_name=None, reason="test"),
        user=route_services.user,
        memory_system=route_services.memory,
    )
    skills = await list_skills(
        user=route_services.user,
        memory_system=route_services.memory,
    )
    stats = await knowledge_stats(
        user=route_services.user,
        memory_system=route_services.memory,
    )

    assert memory_response.project_name == "devsynapse-ai"
    assert adjusted_memory.confidence_score > memory_response.confidence_score
    assert memories.memories[0].effective_confidence > 0
    assert skill_response.slug == "pytest-triage"
    assert activated.use_count == 1
    assert skills.skills[0].slug == "pytest-triage"
    assert stats.memories["total_memories"] == 1
    assert stats.skills["active_skills"] == 1


@pytest.mark.asyncio
async def test_knowledge_memory_global_write_requires_admin(route_services):
    from api.models import ProjectMemoryCreateRequest
    from api.routes.knowledge import create_memory

    with pytest.raises(HTTPException) as exc_info:
        await create_memory(
            payload=ProjectMemoryCreateRequest(
                content="Global memory should be admin controlled.",
                project_name=None,
            ),
            user=route_services.user,
            memory_system=route_services.memory,
        )

    assert exc_info.value.status_code == 403

    response = await create_memory(
        payload=ProjectMemoryCreateRequest(
            content="Global memory should be admin controlled.",
            project_name=None,
        ),
        user=route_services.admin,
        memory_system=route_services.memory,
    )

    assert response.project_name is None
