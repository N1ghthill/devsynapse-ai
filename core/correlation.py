"""Correlation ID helpers shared by API and UI-facing contracts."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime


def generate_conversation_id(now: datetime | None = None) -> str:
    """Return a human-readable conversation ID suitable for support/debugging."""

    timestamp = (now or datetime.now()).strftime("%Y%m%d")
    return f"chat_{timestamp}_{secrets.token_hex(3)}"


def generate_request_id() -> str:
    """Return a compact per-request correlation ID."""

    return f"req_{uuid.uuid4().hex[:12]}"


def generate_tool_run_id() -> str:
    """Return a compact command/tool execution correlation ID."""

    return f"tool_{uuid.uuid4().hex[:12]}"
