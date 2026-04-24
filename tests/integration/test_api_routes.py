"""
Route-level integration tests for chat and conversation APIs.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from fastapi import HTTPException


class _MonitoringStub:
    def log_api_request(self, *args, **kwargs):
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


@pytest.fixture
def route_services(tmp_path, monkeypatch):
    import core.memory as memory_module
    from core.brain import DevSynapseBrain
    from core.memory import MemorySystem
    from core.opencode_bridge import OpenCodeBridge

    db_path = tmp_path / "route_contract.db"
    monkeypatch.setattr(memory_module, "MEMORY_DB_PATH", db_path)

    memory = MemorySystem()
    bridge = OpenCodeBridge()
    brain = DevSynapseBrain(memory, bridge)
    monitoring = _MonitoringStub()
    user = {"username": "irving", "role": "user"}

    return SimpleNamespace(
        memory=memory,
        bridge=bridge,
        brain=brain,
        monitoring=monitoring,
        user=user,
    )


@pytest.mark.asyncio
async def test_conversation_list_rename_and_delete_flow(route_services):
    from api.models import ConversationRenameRequest
    from api.routes.chat import delete_conversation, list_conversations, rename_conversation

    await route_services.memory.save_interaction(
        conversation_id="conv_http",
        user_message="Conversa criada pela rota",
        ai_response="Resposta inicial",
    )

    list_response = await list_conversations(memory_system=route_services.memory)
    assert list_response["conversations"][0]["id"] == "conv_http"

    rename_response = await rename_conversation(
        conversation_id="conv_http",
        payload=ConversationRenameRequest(title="Título via rota"),
        memory_system=route_services.memory,
    )
    assert rename_response == {"success": True, "conversation_id": "conv_http"}

    renamed_list = await list_conversations(memory_system=route_services.memory)
    assert renamed_list["conversations"][0]["title"] == "Título via rota"

    delete_response = await delete_conversation(
        conversation_id="conv_http",
        memory_system=route_services.memory,
    )
    assert delete_response == {"success": True, "conversation_id": "conv_http"}

    deleted_list = await list_conversations(memory_system=route_services.memory)
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

    response = await execute_command(
        request=CommandExecutionRequest(
            conversation_id="conv_exec_blocked",
            command='bash "docker ps"',
            confirm=True,
        ),
        background_tasks=BackgroundTasks(),
        user=route_services.user,
        bridge=route_services.bridge,
        memory_system=route_services.memory,
        monitoring_system=route_services.monitoring,
    )

    assert response.success is False
    assert response.status == "blocked"
    assert response.reason_code == "validation_failed"
    assert response.project_name is None


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
async def test_delete_conversation_returns_404_for_unknown_id(route_services):
    from api.routes.chat import delete_conversation

    with pytest.raises(HTTPException) as exc_info:
        await delete_conversation(
            conversation_id="missing",
            memory_system=route_services.memory,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_conversations_and_stats_include_llm_usage(route_services):
    from api.routes.chat import list_conversations
    from api.routes.monitoring import get_monitoring_stats

    await route_services.memory.save_interaction(
        conversation_id="conv_usage_stats",
        user_message="Mensagem com custo sobre devsynapse-ai",
        ai_response='Resposta com custo read "/home/irving/ruas/repos/devsynapse-ai/README.md"',
        opencode_command='read "/home/irving/ruas/repos/devsynapse-ai/README.md"',
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

    conversations = await list_conversations(memory_system=route_services.memory)
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
