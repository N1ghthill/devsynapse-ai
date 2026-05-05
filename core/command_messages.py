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
    project_suffix = f" Project: {project_name}." if project_name else ""

    if status == "success":
        return f"Execution completed. The command result is available below.{project_suffix}"
    if status == "blocked":
        if reason_code == "project_scope_mismatch":
            return (
                "Execution was blocked because the command tried to exit the "
                f"project scope.{project_suffix}"
            )
        return (
            "Execution was blocked by a security rule or permission."
            f"{project_suffix}"
        )
    if reason_code == "interactive_sudo_required":
        return (
            "The command requires a password or interactive terminal for `sudo`. Run this "
            "step manually in the terminal, or configure dependencies outside "
            f"DevSynapse before continuing.{project_suffix}"
        )
    if reason_code == "privileged_setup_required":
        return (
            "This step requires privileged setup outside the chat. Run the necessary "
            "commands in the terminal and use Revalidate prerequisites before "
            f"continuing.{project_suffix}"
        )
    return f"Execution finished with failure and needs review.{project_suffix}"


def command_failure_message(
    command: str,
    message: str,
    reason_code: Optional[str],
    project_name: Optional[str],
) -> str:
    """Generate a failure message for a command that could not execute."""
    project_suffix = f" Project: {project_name}." if project_name else ""
    if reason_code == "interactive_sudo_required":
        return (
            f"The command `{command}` requires a password or interactive terminal for `sudo` "
            "and cannot be completed by the chat. Run this step manually in the "
            f"terminal, or configure dependencies outside DevSynapse.{project_suffix}"
        )
    if reason_code == "privileged_setup_required":
        return (
            f"The command `{command}` requires privileged setup and was blocked before "
            "running. Run this step manually in the terminal and use Revalidate "
            f"prerequisites to continue.{project_suffix}"
        )
    return f"The command `{command}` could not be executed: {message}{project_suffix}"


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
                "or command is unavailable; continue with any useful project-scoped "
                "work that is still possible and mention the missing prerequisite in "
                "the final answer. If the command was blocked by permission or project "
                "scope, choose an allowed action inside the active project or explain "
                "the exact permission/project selection required."
            ),
        },
    ]
