"""
Monitoring and health routes.
"""

import sqlite3

from fastapi import APIRouter, Depends

from api.dependencies import (
    get_brain,
    get_current_user,
    get_memory_system,
    get_monitoring_system,
)
from api.models import DashboardStats, HealthResponse
from config.settings import get_settings
from core.brain import DevSynapseBrain
from core.memory import MemorySystem

router = APIRouter(tags=["monitoring"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    memory_system: MemorySystem = Depends(get_memory_system),
    brain: DevSynapseBrain = Depends(get_brain),
    monitoring_system=Depends(get_monitoring_system),
):
    conn = sqlite3.connect(memory_system.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM conversations")
    memory_count = cursor.fetchone()[0]
    conn.close()

    system_health = monitoring_system.get_system_health()
    return HealthResponse(
        status=system_health["overall_status"],
        version=settings.app_version,
        memory_entries=memory_count,
        deepseek_configured=brain.api_key is not None,
    )


@router.get("/monitoring/health", response_model=HealthResponse)
async def monitoring_health(
    memory_system: MemorySystem = Depends(get_memory_system),
    brain: DevSynapseBrain = Depends(get_brain),
    monitoring_system=Depends(get_monitoring_system),
):
    return await health_check(memory_system, brain, monitoring_system)


@router.get("/monitoring/stats", response_model=DashboardStats)
async def get_monitoring_stats(
    hours: int = 24,
    user=Depends(get_current_user),
    monitoring_system=Depends(get_monitoring_system),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    return DashboardStats(
        system_health=monitoring_system.get_system_health(),
        command_stats=monitoring_system.get_command_stats(hours),
        api_stats=monitoring_system.get_api_stats(hours),
        llm_usage={
            **memory_system.get_llm_usage_stats(hours=hours),
            "by_project": memory_system.get_project_usage_breakdown(hours=hours),
        },
        active_alerts=monitoring_system.get_active_alerts(),
    )


@router.get("/monitoring/alerts")
async def get_alerts(
    resolved: bool = False,
    user=Depends(get_current_user),
    monitoring_system=Depends(get_monitoring_system),
):
    if resolved:
        return {"alerts": [], "resolved": True}
    return {
        "alerts": monitoring_system.get_active_alerts(),
        "resolved": False,
    }


@router.post("/monitoring/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    user=Depends(get_current_user),
    monitoring_system=Depends(get_monitoring_system),
):
    monitoring_system.resolve_alert(alert_id)
    return {"success": True, "message": f"Alerta {alert_id} resolvido"}
