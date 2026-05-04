"""LLM model discovery adapters."""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_openrouter_model(raw: Dict[str, Any], source_url: str) -> Dict[str, Any]:
    pricing = raw.get("pricing") or {}
    architecture = raw.get("architecture") or {}
    top_provider = raw.get("top_provider") or {}
    return {
        "provider": "openrouter",
        "model_id": raw.get("id") or raw.get("slug"),
        "name": raw.get("name") or raw.get("id"),
        "context_length": raw.get("context_length"),
        "input_cost_per_token": _float_or_none(pricing.get("prompt")),
        "output_cost_per_token": _float_or_none(pricing.get("completion")),
        "cache_read_cost_per_token": _float_or_none(pricing.get("input_cache_read")),
        "raw_pricing": pricing,
        "capabilities": {
            "architecture": architecture,
            "top_provider": top_provider,
            "supported_parameters": raw.get("supported_parameters") or [],
        },
        "source_url": source_url,
    }


def _normalize_openai_compatible_model(
    raw: Dict[str, Any],
    provider: str,
    source_url: str,
) -> Dict[str, Any]:
    model_id = raw.get("id") or raw.get("model") or raw.get("name")
    return {
        "provider": provider,
        "model_id": model_id,
        "name": raw.get("name") or model_id,
        "context_length": raw.get("context_length") or raw.get("contextLength"),
        "input_cost_per_token": _float_or_none(
            (raw.get("pricing") or {}).get("prompt")
            or raw.get("input_cost_per_token")
        ),
        "output_cost_per_token": _float_or_none(
            (raw.get("pricing") or {}).get("completion")
            or raw.get("output_cost_per_token")
        ),
        "cache_read_cost_per_token": _float_or_none(
            (raw.get("pricing") or {}).get("input_cache_read")
        ),
        "raw_pricing": raw.get("pricing") or {},
        "capabilities": {
            "owned_by": raw.get("owned_by"),
            "object": raw.get("object"),
        },
        "source_url": source_url,
    }


def fetch_openrouter_models(models_url: str, timeout: int = 12) -> list[Dict[str, Any]]:
    response = requests.get(models_url, timeout=(5, timeout))
    response.raise_for_status()
    payload = response.json()
    return [
        normalized
        for item in payload.get("data", [])
        if (normalized := _normalize_openrouter_model(item, models_url)).get("model_id")
    ]


def fetch_openai_compatible_models(
    provider: str,
    models_url: str,
    api_key: Optional[str],
    timeout: int = 12,
) -> list[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    response = requests.get(models_url, headers=headers, timeout=(5, timeout))
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    return [
        normalized
        for item in items
        if isinstance(item, dict)
        if (
            normalized := _normalize_openai_compatible_model(item, provider, models_url)
        ).get("model_id")
    ]
