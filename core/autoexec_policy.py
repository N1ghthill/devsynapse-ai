"""Auto-execution policy for model-emitted tool commands."""

from __future__ import annotations

import re
import shlex
from typing import List, Optional

from config.settings import ALLOWED_COMMANDS, BLACKLISTED_PATTERNS

AUTOEXEC_READ_ONLY_BASH_COMMANDS = {"df", "du", "ls", "ps", "pwd"}
AUTOEXEC_READ_ONLY_GIT_SUBCOMMANDS = {
    "branch",
    "describe",
    "diff",
    "log",
    "ls-files",
    "remote",
    "rev-parse",
    "show",
    "status",
}
AUTOEXEC_BASH_OUTPUT_FLAGS = {"-o", "--output"}


def max_autoexec_rounds(auto_execute: bool, user_role: Optional[str]) -> int:
    """Allow trusted admin runs enough turns to build, test and fix without stopping early."""

    if auto_execute and user_role == "admin":
        return 20
    if auto_execute:
        return 8
    return 5


def should_replay_command_result(
    auto_execute: bool,
    user_role: Optional[str],
    status: str,
    reason_code: Optional[str],
    message: Optional[str] = None,
    output: Optional[str] = None,
) -> bool:
    """Let auto mode recover from normal failures and explain blocked actions."""

    del user_role

    if not auto_execute:
        return False

    if status == "failed" and reason_code == "execution_failed":
        if looks_like_interactive_sudo_failure(message, output):
            return False
        return True

    return status == "blocked" and reason_code in {
        "authorization_failed",
        "project_scope_mismatch",
        "validation_failed",
    }


def looks_like_interactive_sudo_failure(
    message: Optional[str],
    output: Optional[str],
) -> bool:
    text = f"{message or ''}\n{output or ''}".lower()
    sudo_markers = [
        "sudo:",
        "a terminal is required",
        "um terminal é necessário",
        "a password is required",
        "uma senha é necessária",
        "no tty present",
        "askpass",
    ]
    return "sudo" in text and any(marker in text for marker in sudo_markers)


def should_retry_missing_tool(
    auto_execute: bool,
    user_message: str,
    response_text: str,
    opencode_command: Optional[str],
) -> bool:
    """Recover when the model promises action but emits no executable tool call."""

    if not auto_execute or opencode_command:
        return False
    if response_text:
        return response_promises_pending_action(response_text)
    return user_request_expects_tool(user_message)


def user_request_expects_tool(user_message: str) -> bool:
    normalized = " ".join((user_message or "").strip().lower().split())
    if not normalized:
        return False

    explanatory_question_patterns = [
        r"^(como|how)\b",
        r"\b(o que|what|why|por que|porque)\b",
    ]
    if any(re.search(pattern, normalized) for pattern in explanatory_question_patterns):
        return False

    action_patterns = [
        r"\b(crie|criar|cria|implemente|implementar|gere|gerar|monte|montar|adicione|adicionar|edite|editar|salve|salvar|rode|rodar|execute|executar|leia|ler|liste|listar|inspecione|inspecionar)\b",
        r"\b(create|implement|generate|build|add|edit|save|run|execute|read|list|inspect)\b",
        r"\b(pode\s+continuar|continue|continuar)\b",
    ]
    return any(re.search(pattern, normalized) for pattern in action_patterns)


def response_promises_pending_action(response_text: str) -> bool:
    normalized = " ".join(response_text.strip().lower().split())
    if not normalized:
        return False

    pending_action_patterns = [
        r"\b(vou|irei|vamos)\s+(criar|escrever|gerar|montar|adicionar|editar|salvar|rodar|executar|ler|listar|inspecionar)\b",
        r"\b(agora|em seguida)\s+(vou|vamos)\s+(criar|escrever|gerar|montar|adicionar|editar|salvar|rodar|executar|ler|listar|inspecionar)\b",
        r"\b(agora|em seguida|pr[oó]ximo|next)\s+(?:o|a|os|as|the)?\s*[`'\"*_]*(arquivo|readme(?:\.md)?|teste|testes|c[oó]digo|pacote|m[oó]dulo|pyproject(?:\.toml)?|file|test|tests|code|package|module)\b[^.!?]*:?\s*$",
        r"\b(i'?ll|i will|let me|i am going to|i'm going to)\s+(create|write|generate|add|edit|save|run|execute|read|list|inspect)\b",
    ]
    return any(re.search(pattern, normalized) for pattern in pending_action_patterns)


def can_autoexecute_command(command: str, user_role: Optional[str] = None) -> bool:
    """Check whether a command may run without an explicit confirmation click."""
    if not command:
        return False

    lower = command.lower()
    for pattern in BLACKLISTED_PATTERNS:
        if pattern in lower:
            return False
    if requires_privileged_setup(command):
        return False

    parts = command.split(None, 1)
    cmd_type = parts[0].lower() if parts else ""

    if user_role == "admin":
        return cmd_type in set(ALLOWED_COMMANDS)

    if cmd_type == "bash":
        bash_command = parts[1].strip("\"' ") if len(parts) > 1 else ""
        if is_read_only_bash_command(bash_command):
            return True

    return False


def is_read_only_command(command: str) -> bool:
    """Compatibility helper for non-admin low-risk auto-execution checks."""
    return can_autoexecute_command(command, user_role="user")


def requires_privileged_setup(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return bool(re.search(r"(^|[;&|]\s*)sudo(\s|$)", command))
    if parts and parts[0].lower() == "bash" and len(parts) > 1:
        try:
            inner_parts = shlex.split(parts[1])
        except ValueError:
            return bool(re.search(r"(^|[;&|]\s*)sudo(\s|$)", parts[1]))
        return "sudo" in {part.lower() for part in inner_parts}
    return "sudo" in {part.lower() for part in parts}


def is_read_only_bash_command(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False

    if not parts:
        return False

    first_word = parts[0].lower()
    if first_word in AUTOEXEC_READ_ONLY_BASH_COMMANDS:
        return not has_output_redirect_flag(parts[1:])

    if first_word == "git":
        if len(parts) == 1:
            return True
        subcommand = parts[1].lower()
        if subcommand not in AUTOEXEC_READ_ONLY_GIT_SUBCOMMANDS:
            return False
        return not has_output_redirect_flag(parts[2:])

    return False


def has_output_redirect_flag(parts: List[str]) -> bool:
    return any(part in AUTOEXEC_BASH_OUTPUT_FLAGS or part.startswith("--output=") for part in parts)
