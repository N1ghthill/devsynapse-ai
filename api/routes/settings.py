"""
Settings and project routes.
"""

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_brain, get_memory_system, require_admin, require_user
from api.models import (
    LlmModelCatalogEntry,
    LlmModelCatalogResponse,
    LlmModelDiscoveryResponse,
    ProjectListResponse,
    ProjectSummaryResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from config.settings import get_settings
from core.brain import DevSynapseBrain
from core.llm_discovery import fetch_openai_compatible_models, fetch_openrouter_models
from core.memory import MemorySystem
from core.runtime_config import set_runtime_config_values

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
    openrouter_configured = bool(
        (brain.deepseek.provider_configs.get("openrouter") or {}).get("api_key")
        or settings.openrouter_api_key
    )
    opencode_zen_configured = bool(
        (brain.deepseek.provider_configs.get("opencode-zen") or {}).get("api_key")
        or settings.opencode_zen_api_key
    )
    opencode_go_configured = bool(
        (brain.deepseek.provider_configs.get("opencode-go") or {}).get("api_key")
        or settings.opencode_go_api_key
    )
    return SettingsResponse(
        deepseek_api_key=deepseek_configured,
        openrouter_api_key=openrouter_configured,
        opencode_zen_api_key=opencode_zen_configured,
        opencode_go_api_key=opencode_go_configured,
        deepseek_model=persisted.get("deepseek_model", settings.deepseek_model),
        deepseek_flash_model=persisted.get(
            "deepseek_flash_model", settings.deepseek_flash_model
        ),
        deepseek_pro_model=persisted.get("deepseek_pro_model", settings.deepseek_pro_model),
        llm_model_routing_enabled=_bool_setting(
            persisted.get("llm_model_routing_enabled", settings.llm_model_routing_enabled)
        ),
        llm_adaptive_routing_enabled=_bool_setting(
            persisted.get("llm_adaptive_routing_enabled", True)
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


def _persisted_float_setting(persisted: dict, key: str, default: float) -> float:
    return float(persisted.get(key, default))


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    settings_data: SettingsUpdateRequest,
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
    brain: DevSynapseBrain = Depends(get_brain),
):
    updates = settings_data.model_dump(exclude_none=True)
    persisted = memory_system.get_app_settings()
    warning_threshold = float(
        updates.get(
            "llm_budget_warning_threshold_pct",
            _persisted_float_setting(
                persisted,
                "llm_budget_warning_threshold_pct",
                settings.llm_budget_warning_threshold_pct,
            ),
        )
    )
    critical_threshold = float(
        updates.get(
            "llm_budget_critical_threshold_pct",
            _persisted_float_setting(
                persisted,
                "llm_budget_critical_threshold_pct",
                settings.llm_budget_critical_threshold_pct,
            ),
        )
    )
    if critical_threshold < warning_threshold:
        raise HTTPException(
            status_code=400,
            detail="Critical budget threshold must be greater than or equal to warning threshold",
        )

    if "deepseek_api_key" in updates and updates["deepseek_api_key"]:
        brain.api_key = updates["deepseek_api_key"]
        set_runtime_config_values({"DEEPSEEK_API_KEY": updates["deepseek_api_key"]})
    if "openrouter_api_key" in updates and updates["openrouter_api_key"]:
        brain.set_provider_api_key("openrouter", updates["openrouter_api_key"])
        set_runtime_config_values({"OPENROUTER_API_KEY": updates["openrouter_api_key"]})
    if "opencode_zen_api_key" in updates and updates["opencode_zen_api_key"]:
        brain.set_provider_api_key("opencode-zen", updates["opencode_zen_api_key"])
        set_runtime_config_values({"OPENCODE_ZEN_API_KEY": updates["opencode_zen_api_key"]})
    if "opencode_go_api_key" in updates and updates["opencode_go_api_key"]:
        brain.set_provider_api_key("opencode-go", updates["opencode_go_api_key"])
        set_runtime_config_values({"OPENCODE_GO_API_KEY": updates["opencode_go_api_key"]})
    if "deepseek_model" in updates and updates["deepseek_model"]:
        brain.deepseek.model = updates["deepseek_model"]

    filtered_updates = {
        k: v
        for k, v in updates.items()
        if k not in {
            "deepseek_api_key",
            "openrouter_api_key",
            "opencode_zen_api_key",
            "opencode_go_api_key",
        }
    }
    if filtered_updates:
        memory_system.update_app_settings(filtered_updates)

    return await get_settings_route(admin, memory_system, brain)


@router.get("/settings/llm/models", response_model=LlmModelCatalogResponse)
async def list_llm_models(
    provider: str | None = None,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    models = memory_system.list_llm_models(provider=provider)
    return LlmModelCatalogResponse(
        models=[LlmModelCatalogEntry(**model) for model in models],
        count=len(models),
    )


@router.post("/settings/llm/discover", response_model=LlmModelDiscoveryResponse)
async def discover_llm_models(
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del admin
    persisted = memory_system.get_app_settings()
    discovered_models = []
    errors: dict[str, str] = {}
    providers: list[str] = []

    discovered_models.extend(
        [
            {
                "provider": "deepseek",
                "model_id": settings.deepseek_flash_model,
                "name": settings.deepseek_flash_model,
                "context_length": None,
                "input_cost_per_token": (
                    settings.deepseek_flash_input_cache_miss_price_usd_per_million / 1_000_000
                ),
                "output_cost_per_token": (
                    settings.deepseek_flash_output_price_usd_per_million / 1_000_000
                ),
                "cache_read_cost_per_token": (
                    settings.deepseek_flash_input_cache_hit_price_usd_per_million / 1_000_000
                ),
                "raw_pricing": {"source": "runtime_config"},
                "capabilities": {"direct_provider": True},
                "source_url": "runtime_config",
            },
            {
                "provider": "deepseek",
                "model_id": settings.deepseek_pro_model,
                "name": settings.deepseek_pro_model,
                "context_length": None,
                "input_cost_per_token": (
                    settings.deepseek_pro_input_cache_miss_price_usd_per_million / 1_000_000
                ),
                "output_cost_per_token": (
                    settings.deepseek_pro_output_price_usd_per_million / 1_000_000
                ),
                "cache_read_cost_per_token": (
                    settings.deepseek_pro_input_cache_hit_price_usd_per_million / 1_000_000
                ),
                "raw_pricing": {"source": "runtime_config"},
                "capabilities": {"direct_provider": True},
                "source_url": "runtime_config",
            },
        ]
    )
    providers.append("deepseek")

    try:
        models = fetch_openrouter_models(settings.openrouter_models_url)
        discovered_models.extend(models)
        providers.append("openrouter")
    except Exception as exc:
        errors["openrouter"] = str(exc)

    opencode_go_key = persisted.get("opencode_go_api_key") or settings.opencode_go_api_key
    try:
        models = fetch_openai_compatible_models(
            "opencode-go",
            settings.opencode_go_models_url,
            opencode_go_key,
        )
        discovered_models.extend(models)
        providers.append("opencode-go")
    except Exception as exc:
        errors["opencode-go"] = str(exc)

    count = memory_system.upsert_llm_models(discovered_models)
    return LlmModelDiscoveryResponse(discovered=count, providers=providers, errors=errors)


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
