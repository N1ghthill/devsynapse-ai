"""Desktop-safe LLM provider configuration operations."""

from __future__ import annotations

from typing import Any

import config.settings as app_settings
from core.llm_discovery import fetch_openai_compatible_models, fetch_openrouter_models
from core.runtime_config import set_runtime_config_values

PROVIDER_CONFIGS = {
    "deepseek": {
        "label": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "model_key": "DEEPSEEK_MODEL",
        "model_attr": "deepseek_model",
        "key_attr": "deepseek_api_key",
        "default_model": "deepseek-v4-pro",
    },
    "openrouter": {
        "label": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "model_key": "OPENROUTER_MODEL",
        "model_attr": "openrouter_model",
        "key_attr": "openrouter_api_key",
        "default_model": "openrouter/free",
    },
    "opencode-zen": {
        "label": "OpenCode Zen",
        "env_key": "OPENCODE_ZEN_API_KEY",
        "model_key": "OPENCODE_ZEN_MODEL",
        "model_attr": "opencode_zen_model",
        "key_attr": "opencode_zen_api_key",
        "default_model": "qwen3-coder",
    },
    "opencode-go": {
        "label": "OpenCode Go",
        "env_key": "OPENCODE_GO_API_KEY",
        "model_key": "OPENCODE_GO_MODEL",
        "model_attr": "opencode_go_model",
        "key_attr": "opencode_go_api_key",
        "default_model": "deepseek-v4-pro",
    },
}


OPENROUTER_CURATED_FREE_MODELS = [
    {
        "provider": "openrouter",
        "modelId": "openrouter/free",
        "name": "Free Models Router",
        "contextLength": 200000,
        "free": True,
        "supportsTools": True,
    },
    {
        "provider": "openrouter",
        "modelId": "qwen/qwen3-coder:free",
        "name": "Qwen3 Coder 480B A35B (free)",
        "contextLength": 262000,
        "free": True,
        "supportsTools": True,
    },
    {
        "provider": "openrouter",
        "modelId": "minimax/minimax-m2.5:free",
        "name": "MiniMax M2.5 (free)",
        "contextLength": 196608,
        "free": True,
        "supportsTools": True,
    },
    {
        "provider": "openrouter",
        "modelId": "openai/gpt-oss-120b:free",
        "name": "OpenAI gpt-oss-120b (free)",
        "contextLength": 131072,
        "free": True,
        "supportsTools": True,
    },
]


def normalize_provider(value: str | None) -> str:
    normalized = (value or "openrouter").strip().lower()
    aliases = {
        "zen": "opencode-zen",
        "opencode": "opencode-zen",
        "go": "opencode-go",
    }
    return aliases.get(normalized, normalized)


def _provider_config(provider: str) -> dict[str, str]:
    normalized = normalize_provider(provider)
    config = PROVIDER_CONFIGS.get(normalized)
    if config is None:
        raise ValueError("unknown_provider")
    return config


def _provider_key(settings: Any, provider: str) -> str | None:
    config = _provider_config(provider)
    value = getattr(settings, config["key_attr"], None)
    return str(value) if value else None


def _provider_model(settings: Any, provider: str) -> str:
    config = _provider_config(provider)
    value = getattr(settings, config["model_attr"], "")
    return str(value or config["default_model"])


def _is_free_model(model: dict[str, Any]) -> bool:
    try:
        input_cost = float(model.get("input_cost_per_token") or model.get("inputCostPerToken") or 0)
        output_cost = float(
            model.get("output_cost_per_token") or model.get("outputCostPerToken") or 0
        )
    except (TypeError, ValueError):
        input_cost = output_cost = 1.0
    model_id = str(model.get("model_id") or model.get("modelId") or "")
    return (input_cost == 0.0 and output_cost == 0.0) or model_id.endswith(":free")


def _supports_tools(model: dict[str, Any]) -> bool:
    capabilities = model.get("capabilities") or {}
    params = capabilities.get("supported_parameters") or []
    return bool(model.get("supportsTools")) or "tools" in params or "tool_choice" in params


def _desktop_model(model: dict[str, Any]) -> dict[str, Any]:
    model_id = str(model.get("model_id") or model.get("modelId") or "")
    context_length = model.get("context_length") or model.get("contextLength")
    return {
        "provider": str(model.get("provider") or ""),
        "modelId": model_id,
        "name": str(model.get("name") or model_id),
        "contextLength": context_length if isinstance(context_length, int) else None,
        "free": _is_free_model(model),
        "supportsTools": _supports_tools(model),
    }


def _dedupe_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for model in models:
        provider = str(model.get("provider") or "")
        model_id = str(model.get("modelId") or model.get("model_id") or "")
        key = (provider, model_id)
        if not provider or not model_id or key in seen:
            continue
        seen.add(key)
        output.append(model)
    return output


def _sort_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        _dedupe_models(models),
        key=lambda model: (
            0 if model.get("free") else 1,
            0 if model.get("supportsTools") else 1,
            str(model.get("modelId") or ""),
        ),
    )


def model_candidates(provider: str | None = None, *, limit: int = 80) -> list[dict[str, Any]]:
    selected_provider = normalize_provider(provider)
    models: list[dict[str, Any]] = []
    if selected_provider == "openrouter":
        models.extend(OPENROUTER_CURATED_FREE_MODELS)
    try:
        from core.memory import MemorySystem

        models.extend(
            _desktop_model(model)
            for model in MemorySystem().list_llm_models(provider=selected_provider, limit=limit)
        )
    except Exception:
        pass
    return _sort_models(models)[:limit]


def provider_status(_operation_input: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = app_settings.get_settings()
    default_provider = normalize_provider(settings.llm_default_provider)
    providers = []
    for provider, config in PROVIDER_CONFIGS.items():
        providers.append(
            {
                "id": provider,
                "label": config["label"],
                "configured": bool(_provider_key(settings, provider)),
                "selected": provider == default_provider,
                "model": _provider_model(settings, provider),
                "defaultModel": config["default_model"],
            }
        )
    return {
        "defaultProvider": default_provider,
        "activeModel": _provider_model(settings, default_provider),
        "ready": any(provider["configured"] for provider in providers),
        "providers": providers,
        "models": model_candidates(default_provider),
    }


def configure_provider(operation_input: dict[str, Any]) -> dict[str, Any]:
    provider = normalize_provider(
        operation_input.get("provider") if isinstance(operation_input.get("provider"), str) else None
    )
    config = _provider_config(provider)
    api_key = operation_input.get("apiKey")
    model = operation_input.get("model")
    selected_model = str(model).strip() if isinstance(model, str) and model.strip() else config["default_model"]

    settings = app_settings.get_settings()
    existing_key = _provider_key(settings, provider)
    if not existing_key and not (isinstance(api_key, str) and api_key.strip()):
        raise ValueError("missing_provider_api_key")

    updates: dict[str, str] = {
        "LLM_DEFAULT_PROVIDER": provider,
        config["model_key"]: selected_model,
    }
    if isinstance(api_key, str) and api_key.strip():
        updates[config["env_key"]] = api_key.strip()

    set_runtime_config_values(updates)
    app_settings.get_settings.cache_clear()
    return provider_status({})


def discover_models(operation_input: dict[str, Any]) -> dict[str, Any]:
    provider = normalize_provider(
        operation_input.get("provider") if isinstance(operation_input.get("provider"), str) else None
    )
    settings = app_settings.get_settings()
    discovered: list[dict[str, Any]]

    if provider == "openrouter":
        discovered = fetch_openrouter_models(
            settings.openrouter_models_url,
            timeout=settings.llm_request_timeout,
        )
    elif provider == "opencode-go":
        discovered = fetch_openai_compatible_models(
            provider,
            settings.opencode_go_models_url,
            settings.opencode_go_api_key,
            timeout=settings.llm_request_timeout,
        )
    elif provider == "opencode-zen":
        discovered = fetch_openai_compatible_models(
            provider,
            settings.opencode_zen_models_url,
            settings.opencode_zen_api_key,
            timeout=settings.llm_request_timeout,
        )
    else:
        discovered = []

    desktop_models = _sort_models([_desktop_model(model) for model in discovered])
    curated = [
        model
        for model in desktop_models
        if provider != "openrouter" or model.get("free") or model.get("supportsTools")
    ][:80]

    if curated:
        try:
            from core.memory import MemorySystem

            MemorySystem().upsert_llm_models(
                [
                    {
                        "provider": model["provider"],
                        "model_id": model["modelId"],
                        "name": model["name"],
                        "context_length": model["contextLength"],
                        "input_cost_per_token": 0.0 if model["free"] else None,
                        "output_cost_per_token": 0.0 if model["free"] else None,
                        "capabilities": {
                            "supported_parameters": ["tools", "tool_choice"]
                            if model["supportsTools"]
                            else []
                        },
                    }
                    for model in curated
                ]
            )
        except Exception:
            pass

    models = _sort_models([*model_candidates(provider), *curated])[:80]
    return {
        "provider": provider,
        "discovered": len(discovered),
        "models": models,
    }
