"""
Command result message builders for DevSynapse Brain.

Extracted from DevSynapseBrain as pure static functions with zero coupling
to the orchestrator class.
"""
from typing import Dict, List, Optional


def command_completion_fallback(executed_command: Dict) -> str:
    """Generate a fallback message for a completed command execution."""
    status = executed_command.get("status")
    reason_code = executed_command.get("reason_code")
    project_name = executed_command.get("project_name")
    command = executed_command.get("command")
    result = executed_command.get("result")
    workspace_suffix = f" Workspace: {project_name}." if project_name else ""

    if status == "success":
        return f"Execution completed. The command result is available below.{workspace_suffix}"
    if status == "blocked":
        if reason_code == "project_scope_mismatch":
            return (
                "Execution was blocked because the command tried to exit the "
                f"workspace scope.{workspace_suffix}"
            )
        return (
            "Execution was blocked by the current mode or workspace safety rules."
            f"{workspace_suffix}"
        )
    if reason_code == "interactive_sudo_required":
        return (
            "The command requires a password or interactive terminal for `sudo`. Run this "
            "step manually in the terminal, or configure dependencies outside "
            f"DevSynapse before continuing.{workspace_suffix}"
        )
    if reason_code == "privileged_setup_required":
        return (
            "This step requires privileged setup outside the chat. Run the necessary "
            "commands in the terminal and use Revalidate prerequisites before "
            f"continuing.{workspace_suffix}"
        )
    command_part = f" `{command}`" if command else ""
    result_part = f": {result}" if result else "."
    return (
        f"I could not complete the local check{command_part}{result_part} "
        "Continue from the available context instead of treating this as a completed plan."
        f"{workspace_suffix}"
    )


def command_failure_message(
    command: str,
    message: str,
    reason_code: Optional[str],
    project_name: Optional[str],
) -> str:
    """Generate a failure message for a command that could not execute."""
    workspace_suffix = f" Workspace: {project_name}." if project_name else ""
    if reason_code == "interactive_sudo_required":
        return (
            f"The command `{command}` requires a password or interactive terminal for `sudo` "
            "and cannot be completed by the chat. Run this step manually in the "
            f"terminal, or configure dependencies outside DevSynapse.{workspace_suffix}"
        )
    if reason_code == "privileged_setup_required":
        return (
            f"The command `{command}` requires privileged setup and was blocked before "
            "running. Run this step manually in the terminal and use Revalidate "
            f"prerequisites to continue.{workspace_suffix}"
        )
    return f"The command `{command}` could not be executed: {message}{workspace_suffix}"


def build_command_result_replay_messages(
    assistant_text: str,
    command: str,
    success: bool,
    message: str,
    output: Optional[str],
) -> List[Dict[str, str]]:
    """Replay tool output in a provider-compatible text form."""
    result_text = output or message or "(no output)"
    status = "success" if success else "failed"
    return [
        {"role": "assistant", "content": assistant_text or f"Executed `{command}`."},
        {
            "role": "user",
            "content": (
                f"Command `{command}` finished with status `{status}`.\n"
                f"Result: {message}\n\n"
                f"Output:\n```\n{result_text[:3000]}\n```\n\n"
                "Never report success for a command whose status is `failed` or "
                "`blocked`, even if part of a shell pipeline produced output. "
                "Continue the original task. If more filesystem or command work is "
                "needed, emit exactly one next tool call. If the task is complete, "
                "give the final concise result. Do not stop only because a dependency "
                "or command is unavailable; continue with any useful workspace-scoped "
                "work that is still possible and mention the missing prerequisite in "
                "the final answer. If the command was blocked by mode or workspace "
                "scope, choose an allowed action inside the target workspace or explain "
                "the exact target path or mode change required."
            ),
        },
    ]
