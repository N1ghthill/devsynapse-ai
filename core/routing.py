"""LLM route selection — extracted from DevSynapseBrain to reduce coupling."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, Optional

import config.settings as app_settings
from core.llm_optimization import ModelRoute, ModelRouter, build_task_profile
from core.utils import coerce_bool

logger = logging.getLogger(__name__)


class RouteSelector:
    """Selects which LLM model/route to use for a given user message.

    Owns the routing policy, adaptive override, agent learning integration,
    and budget-aware model selection.  Needs access to memory and the
    DeepSeek client (or its relevant parts) at construction time.
    """

    def __init__(
        self,
        memory: Any,
        deepseek_model: str,
        provider_configs: Dict[str, Dict[str, Optional[str]]],
        deepseek_api_key: Optional[str],
    ):
        self._memory = memory
        self._deepseek_model = deepseek_model
        self._provider_configs = provider_configs
        self._deepseek_api_key = deepseek_api_key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_route(self, user_message: str, context: Dict) -> ModelRoute:
        persisted = self._get_persisted_app_settings()
        settings = app_settings.get_settings()
        profile = build_task_profile(user_message, context=context)
        learned_policy = self._get_agent_learning(profile.signature)
        router = ModelRouter(
            flash_model=str(
                persisted.get("deepseek_flash_model", settings.deepseek_flash_model)
            ),
            pro_model=str(persisted.get("deepseek_pro_model", settings.deepseek_pro_model)),
            default_model=str(persisted.get("deepseek_model", self._deepseek_model)),
        routing_enabled=coerce_bool(
            persisted.get("llm_model_routing_enabled", settings.llm_model_routing_enabled)
        ),
        auto_economy_enabled=coerce_bool(
            persisted.get("llm_auto_economy_enabled", settings.llm_auto_economy_enabled)
        ),
        )
        budget_status = None
        if router.auto_economy_enabled and hasattr(self._memory, "get_llm_budget_status"):
            try:
                budget_status = self._memory.get_llm_budget_status()
            except (sqlite3.OperationalError, ValueError):
                logger.debug("Could not read LLM budget status for routing", exc_info=True)

        route = router.select_model(
            user_message,
            context=context,
            budget_status=budget_status,
            learned_policy=learned_policy,
        )
        route = self._apply_adaptive_model_override(route, budget_status)
        logger.info(
            "LLM route selected: model=%s complexity=%s reason=%s budget=%s fallback=%s",
            route.model,
            route.complexity,
            route.reason,
            route.budget_mode,
            route.fallback_model,
        )
        return route

    def get_agent_learning_context(self) -> str:
        if not hasattr(self._memory, "get_agent_learning_context"):
            return "No agent learning patterns found yet."
        try:
            return self._memory.get_agent_learning_context()
        except (sqlite3.OperationalError, ValueError):
            logger.debug("Could not load agent learning context", exc_info=True)
            return "No agent learning patterns found yet."

    # ------------------------------------------------------------------
    # Adaptive override
    # ------------------------------------------------------------------

    def _apply_adaptive_model_override(
        self,
        route: ModelRoute,
        budget_status: Optional[Dict[str, Any]],
    ) -> ModelRoute:
        if not coerce_bool(
            self._get_persisted_app_settings().get("llm_adaptive_routing_enabled", True)
        ):
            return route
        catalog = getattr(self._memory, "list_llm_models", lambda **kwargs: [])()
        if not isinstance(catalog, list):
            return route
        candidates = [
            model for model in catalog
            if model.get("enabled")
            and model.get("input_cost_per_token") is not None
            and model.get("output_cost_per_token") is not None
            and self._provider_configured(model.get("provider"))
        ]
        if not candidates:
            return route

        budget_level = str((budget_status or {}).get("overall_status") or route.budget_mode)
        should_economize = route.complexity in {"simple", "economy"} or budget_level in {
            "warning",
            "critical",
        }
        if not should_economize:
            return route

        selected = min(
            candidates,
            key=lambda model: float(model["input_cost_per_token"])
            + float(model["output_cost_per_token"]),
        )
        selected_model = f"{selected['provider']}:{selected['model_id']}"
        if selected_model == route.model:
            return route
        return ModelRoute(
            model=selected_model,
            complexity=route.complexity,
            reason=f"adaptive_cheapest:{route.reason}",
            task_type=route.task_type,
            task_signature=route.task_signature,
            fallback_model=route.model,
            budget_mode=route.budget_mode,
            learned_preference=route.learned_preference,
            learned_confidence=route.learned_confidence,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _provider_configured(self, provider: Optional[str]) -> bool:
        if provider == "deepseek":
            return bool(self._deepseek_api_key)
        return bool((self._provider_configs.get(str(provider)) or {}).get("api_key"))

    def _get_agent_learning(self, task_signature: str) -> Optional[Dict]:
        if not hasattr(self._memory, "get_agent_learning"):
            return None
        try:
            return self._memory.get_agent_learning(task_signature)
        except (sqlite3.OperationalError, ValueError):
            logger.debug("Could not load agent learning for routing", exc_info=True)
            return None

    def _get_persisted_app_settings(self) -> Dict[str, str]:
        if not hasattr(self._memory, "get_app_settings"):
            return {}
        try:
            persisted = self._memory.get_app_settings()
            return persisted if isinstance(persisted, dict) else {}
        except (sqlite3.OperationalError, ValueError):
            logger.debug("Could not load persisted app settings", exc_info=True)
            return {}


