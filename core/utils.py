"""Shared utility functions for DevSynapse AI core modules."""

from __future__ import annotations

from typing import Any


def coerce_bool(value: Any) -> bool:
    """Coerce a value to boolean, handling common string representations."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_whitespace(text: str, lower: bool = False) -> str:
    """Collapse consecutive whitespace into single spaces, optionally lowercasing."""
    result = " ".join(text.split())
    if lower:
        result = result.lower()
    return result
