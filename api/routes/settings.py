"""
Settings and project routes.
"""

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_brain, get_memory_system, require_admin, require_user
from api.models import (
    ProjectListResponse,
    ProjectSummaryResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from config.settings import get_settings
from core.brain import DevSynapseBrain
from core.memory import MemorySystem

router = APIRouter(tags=["settings"])
settings = get_settings()


def _bool_setting(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@router.get("/settings", response_model=SettingsResponse)
async def get_settings_route(
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
    brain: DevSynapseBrain = Depends(get_brain),
):
    persisted = memory_system.get_app_settings()
    if user.get("role") == "admin":
        user_allowlist = memory_system.list_project_names()
    else:
        user_allowlist = memory_system.get_project_permissions(user["username"])
    deepseek_configured = bool(brain.api_key)
    return SettingsResponse(
        deepseek_api_key=deepseek_configured,
        deepseek_model=persisted.get("deepseek_model", settings.deepseek_model),
        deepseek_flash_model=persisted.get(
            "deepseek_flash_model", settings.deepseek_flash_model
        ),
        deepseek_pro_model=persisted.get("deepseek_pro_model", settings.deepseek_pro_model),
        llm_model_routing_enabled=_bool_setting(
            persisted.get("llm_model_routing_enabled", settings.llm_model_routing_enabled)
        ),
        llm_auto_economy_enabled=_bool_setting(
            persisted.get("llm_auto_economy_enabled", settings.llm_auto_economy_enabled)
        ),
        llm_cache_hit_warning_threshold_pct=float(
            persisted.get(
                "llm_cache_hit_warning_threshold_pct",
                settings.llm_cache_hit_warning_threshold_pct,
            )
        ),
        temperature=float(persisted.get("temperature", settings.llm_temperature)),
        max_tokens=int(persisted.get("max_tokens", settings.llm_max_tokens)),
        conversation_history_limit=int(
            persisted.get("conversation_history_limit", settings.conversation_history_limit)
        ),
        llm_daily_budget_usd=float(
            persisted.get("llm_daily_budget_usd", settings.llm_daily_budget_usd)
        ),
        llm_monthly_budget_usd=float(
            persisted.get("llm_monthly_budget_usd", settings.llm_monthly_budget_usd)
        ),
        llm_budget_warning_threshold_pct=float(
            persisted.get(
                "llm_budget_warning_threshold_pct",
                settings.llm_budget_warning_threshold_pct,
            )
        ),
        llm_budget_critical_threshold_pct=float(
            persisted.get(
                "llm_budget_critical_threshold_pct",
                settings.llm_budget_critical_threshold_pct,
            )
        ),
        api_host=settings.api_host,
        api_port=settings.api_port,
        project_mutation_allowlist=user_allowlist,
    )


@router.put("/settings")
async def update_settings(
    settings_data: SettingsUpdateRequest,
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
    brain: DevSynapseBrain = Depends(get_brain),
):
    updates = settings_data.model_dump(exclude_none=True)
    warning_threshold = updates.get("llm_budget_warning_threshold_pct")
    critical_threshold = updates.get("llm_budget_critical_threshold_pct")
    if (
        warning_threshold is not None
        and critical_threshold is not None
        and critical_threshold < warning_threshold
    ):
        raise HTTPException(
            status_code=400,
            detail="Critical budget threshold must be greater than or equal to warning threshold",
        )

    if "deepseek_api_key" in updates and updates["deepseek_api_key"]:
        brain.api_key = updates["deepseek_api_key"]
    if "deepseek_model" in updates and updates["deepseek_model"]:
        brain.deepseek.model = updates["deepseek_model"]

    filtered_updates = {
        k: v
        for k, v in updates.items()
        if k != "deepseek_api_key"
    }
    if filtered_updates:
        memory_system.update_app_settings(filtered_updates)

    return await get_settings_route(admin, memory_system, brain)


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    projects = [
        ProjectSummaryResponse(
            name=project["name"],
            type=project["type"],
            priority=project["priority"],
            last_accessed=project["last_accessed"],
            access_count=int(project["access_count"] or 0),
        )
        for project in memory_system.list_projects()
    ]
    return ProjectListResponse(projects=projects, count=len(projects))
