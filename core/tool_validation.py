"""Schema validation for LLM tool calls before execution."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ALLOWED_TOOL_NAMES = {"bash", "read", "glob", "grep", "edit", "write"}

REQUIRED_ARGS: Dict[str, List[str]] = {
    "bash": ["command"],
    "read": ["path"],
    "glob": ["pattern"],
    "grep": ["pattern"],
    "edit": ["path", "old", "new"],
    "write": ["path", "content"],
}

MAX_ARG_LENGTH = 50_000


def validate_tool_calls(
    tool_calls: Optional[List[Dict[str, Any]]],
) -> Tuple[bool, str]:
    """Validate tool calls before execution.

    Returns (is_valid, reason).
    """
    if not tool_calls:
        return False, "No tool calls provided"

    if len(tool_calls) > 5:
        return False, f"Too many tool calls: {len(tool_calls)} (max 5)"

    for i, tc in enumerate(tool_calls):
        valid, reason = _validate_single_tool_call(tc, i)
        if not valid:
            return False, reason

    return True, "OK"


def _validate_single_tool_call(
    tc: Dict[str, Any],
    index: int,
) -> Tuple[bool, str]:
    func = tc.get("function")
    if not isinstance(func, dict):
        return False, f"Tool call {index}: missing function object"

    name = func.get("name", "")
    if not name:
        return False, f"Tool call {index}: missing function name"

    if name not in ALLOWED_TOOL_NAMES:
        return False, f"Tool call {index}: unknown tool '{name}'"

    raw_args = func.get("arguments", "{}")
    if not isinstance(raw_args, (str, dict)):
        return False, f"Tool call {index}: arguments must be string or object"

    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return False, f"Tool call {index}: invalid JSON arguments: {exc}"

    if not isinstance(args, dict):
        return False, f"Tool call {index}: arguments must be a JSON object"

    required = REQUIRED_ARGS.get(name, [])
    for key in required:
        if key not in args or args[key] is None:
            return False, f"Tool call {index}: missing required argument '{key}' for '{name}'"

    for key, value in args.items():
        if isinstance(value, str) and len(value) > MAX_ARG_LENGTH:
            return False, f"Tool call {index}: argument '{key}' too long ({len(value)} chars)"

    if name == "bash":
        command = str(args.get("command", ""))
        if not command.strip():
            return False, f"Tool call {index}: empty bash command"

    if name in ("edit", "write"):
        path = str(args.get("path", ""))
        if not path.strip():
            return False, f"Tool call {index}: empty file path"

    return True, "OK"
