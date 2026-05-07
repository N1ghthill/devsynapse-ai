"""LLM route selection — extracted from DevSynapseBrain to reduce coupling."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, Optional

from core.llm_optimization import ModelRoute, build_task_profile

logger = logging.getLogger(__name__)


class RouteSelector:
    """Select the user-chosen LLM provider/model.

    DevSynapse intentionally uses manual model control. The selected provider
    and model come from runtime config and are changed from the TUI `/model`
    and `/connect` flows. This class only validates that the selected provider
    is configured and falls back to another configured provider if needed.
    """

    def __init__(
        self,
        memory: Any,
        deepseek_model: str,
        provider_configs: Dict[str, Dict[str, Optional[str]]],
        deepseek_api_key: Optional[str],
        default_provider: str = "openrouter",
        provider_model_defaults: Optional[Dict[str, Optional[str]]] = None,
    ):
        self._memory = memory
        self._deepseek_model = deepseek_model
        self._provider_configs = provider_configs
        self._deepseek_api_key = deepseek_api_key
        self._default_provider = self._normalize_provider(default_provider)
        self._provider_model_defaults = provider_model_defaults or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_route(self, user_message: str, context: Dict) -> ModelRoute:
        profile = build_task_profile(user_message, context=context)
        providers = self._configured_providers_in_order()
        provider = providers[0] if providers else None
        model = self._selected_model(provider) if provider else self._deepseek_model
        fallback_model = self._selected_model(providers[1]) if len(providers) > 1 else None
        route = ModelRoute(
            model=model,
            complexity="manual",
            reason="manual_model_selection",
            task_type=profile.task_type,
            task_signature=profile.signature,
            fallback_model=fallback_model,
            budget_mode="manual",
        )
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
    # Helpers
    # ------------------------------------------------------------------

    def _provider_configured(self, provider: Optional[str]) -> bool:
        if provider == "deepseek":
            return bool(self._deepseek_api_key)
        return bool((self._provider_configs.get(str(provider)) or {}).get("api_key"))

    def _selected_model(self, provider: str) -> str:
        configured_model = (self._provider_model_defaults.get(provider) or "").strip()
        if configured_model:
            return self._qualify_model(provider, configured_model)
        if provider == "deepseek":
            return self._deepseek_model
        catalog_model = self._first_catalog_model(provider)
        if catalog_model:
            return self._qualify_model(provider, catalog_model)
        return self._qualify_model(provider, "")

    def _configured_providers_in_order(self) -> list[str]:
        providers: list[str] = []

        def add(provider: Optional[str]) -> None:
            normalized = self._normalize_provider(provider)
            if self._provider_configured(normalized):
                providers.append(normalized)

        add(self._default_provider)
        for provider in [*self._provider_configs.keys(), "deepseek", *self._provider_model_defaults.keys()]:
            add(provider)

        deduplicated: list[str] = []
        seen: set[str] = set()
        for provider in providers:
            if provider in seen:
                continue
            seen.add(provider)
            deduplicated.append(provider)
        return deduplicated

    def _first_catalog_model(self, provider: str) -> Optional[str]:
        catalog = getattr(self._memory, "list_llm_models", lambda **kwargs: [])(
            provider=provider,
            limit=1,
        )
        if not isinstance(catalog, list):
            return None
        for model in catalog:
            if model.get("enabled", True) and model.get("model_id"):
                return str(model["model_id"])
        return None

    @staticmethod
    def _qualify_model(provider: str, model: str) -> str:
        if provider == "deepseek":
            return model.split(":", 1)[1] if model.startswith("deepseek:") else model
        return model if model.startswith(f"{provider}:") else f"{provider}:{model}"

    @staticmethod
    def _normalize_provider(provider: Optional[str]) -> str:
        normalized = (provider or "openrouter").strip().lower()
        aliases = {
            "zen": "opencode-zen",
            "opencode": "opencode-zen",
            "go": "opencode-go",
        }
        return aliases.get(normalized, normalized)

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
