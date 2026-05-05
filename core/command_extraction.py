"""OpenCode command extraction helpers."""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional


def tool_calls_to_opencode_command(tool_calls: Optional[List[Dict]]) -> Optional[str]:
    """Convert OpenAI-compatible tool calls into an OpenCode command string."""
    if not tool_calls:
        return None

    tc = tool_calls[0]
    func = tc.get("function", {})
    name = func.get("name", "")
    raw_args = func.get("arguments", "{}")

    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except Exception:
        return None

    if name == "bash":
        command = escape_opencode_arg(args.get("command", ""))
        if command:
            return f'bash "{command}"'
    elif name == "read":
        path = escape_opencode_arg(args.get("path", ""))
        if path:
            return f'read "{path}"'
    elif name == "glob":
        pattern = escape_opencode_arg(args.get("pattern", ""))
        if pattern:
            return f'glob "{pattern}"'
    elif name == "grep":
        pattern = escape_opencode_arg(args.get("pattern", ""))
        include = escape_opencode_arg(args.get("include", ""))
        if pattern:
            if include:
                return f'grep "{pattern}" --include="{include}"'
            return f'grep "{pattern}"'
    elif name == "edit":
        path = escape_opencode_arg(args.get("path", ""))
        old = escape_opencode_arg(args.get("old", ""))
        new = escape_opencode_arg(args.get("new", ""))
        if path:
            return f'edit "{path}" --old="{old}" --new="{new}"'
    elif name == "write":
        path = escape_opencode_arg(args.get("path", ""))
        content = escape_opencode_arg(args.get("content", ""))
        if path:
            return f'write "{path}" --content="{content}"'

    return None


def escape_opencode_arg(value: object) -> str:
    """Escape a JSON tool argument so it remains one quoted OpenCode argument."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def extract_opencode_command(response_text: str) -> Optional[str]:
    """Extract the last OpenCode command from model text."""

    patterns = {
        "bash": r'bash\s+"([^"]+)"',
        "read": r'read\s+"([^"]+)"',
        "glob": r'glob\s+"([^"]+)"',
        "grep": r'grep\s+"([^"]+)"(?:\s+--include="([^"]+)")?',
        "edit": r'edit\s+"([^"]+)"\s+--old="([^"]+)"\s+--new="([^"]+)"',
        "write": r'write\s+"([^"]+)"\s+--content="([^"]+)"',
    }

    matches = []
    for command_type, pattern in patterns.items():
        for match in re.finditer(pattern, response_text, re.IGNORECASE | re.DOTALL):
            matches.append((match.start(), command_type, match))

    if not matches:
        return extract_flexible_opencode_command(response_text)

    _, command_type, match = max(matches, key=lambda item: item[0])

    if command_type == "bash":
        return f'bash "{match.group(1)}"'
    if command_type == "read":
        return f'read "{match.group(1)}"'
    if command_type == "glob":
        return f'glob "{match.group(1)}"'
    if command_type == "grep":
        if match.group(2):
            return f'grep "{match.group(1)}" --include="{match.group(2)}"'
        return f'grep "{match.group(1)}"'
    if command_type == "edit":
        return (
            f'edit "{match.group(1)}" '
            f'--old="{match.group(2)}" --new="{match.group(3)}"'
        )
    if command_type == "write":
        return f'write "{match.group(1)}" --content="{match.group(2)}"'

    return extract_flexible_opencode_command(response_text)


def extract_flexible_opencode_command(response_text: str) -> Optional[str]:
    """Handle loosely formatted commands such as `bash ls -la` or bare `docker ps`."""

    lines = [line.strip() for line in response_text.splitlines() if line.strip()]

    for line in reversed(lines):
        normalized = line.strip().strip("`").strip()
        normalized = re.sub(r"^[-*]\s+", "", normalized)
        normalized = re.sub(r"^\d+\.\s+", "", normalized)

        if not normalized:
            continue

        explicit = normalize_explicit_command_line(normalized)
        if explicit:
            return explicit

        bare_shell = normalize_bare_shell_line(normalized)
        if bare_shell:
            return bare_shell

    return None


def normalize_explicit_command_line(line: str) -> Optional[str]:
    if any(operator in line for operator in ["&&", "||", ">", "|", ";"]):
        return None

    explicit_match = re.match(
        r'^(bash|read|glob|grep)\s+(?:"([^"]+)"|(.+))$',
        line,
        re.IGNORECASE,
    )
    if not explicit_match:
        return None

    command_type = explicit_match.group(1).lower()
    argument = (explicit_match.group(2) or explicit_match.group(3) or "").strip()
    if not argument:
        return None

    if command_type == "bash":
        return f'bash "{argument}"'
    if command_type == "read":
        return f'read "{argument}"'
    if command_type == "glob":
        return f'glob "{argument}"'
    if command_type == "grep":
        return f'grep "{argument}"'

    return None


def normalize_bare_shell_line(line: str) -> Optional[str]:
    if any(operator in line for operator in ["&&", "||", ">", "|", ";"]):
        return None

    bare_shell_match = re.match(r"^([a-zA-Z0-9_.-]+)(?:\s+.+)?$", line)
    if not bare_shell_match:
        return None

    if any(punct in line for punct in [":", "?", "!", "```"]):
        return None

    first_word = bare_shell_match.group(1).lower()
    if first_word not in {
        "ls",
        "pwd",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "git",
        "npm",
        "node",
        "python",
        "python3",
        "echo",
        "touch",
        "mkdir",
        "cp",
        "mv",
        "rm",
        "chmod",
        "df",
        "du",
        "ps",
        "top",
        "kill",
        "curl",
        "wget",
        "tar",
        "gzip",
        "gunzip",
        "zip",
        "unzip",
        "docker",
    }:
        return None

    return f'bash "{line}"'
