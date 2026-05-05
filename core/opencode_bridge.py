"""
Bridge for OpenCode communication
"""

import logging
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.settings import (
    ADMIN_ONLY_BASH_COMMANDS,
    ADMIN_ONLY_COMMANDS,
    ALLOWED_BASH_COMMANDS,
    ALLOWED_COMMANDS,
    BLACKLISTED_PATTERNS,
    READ_ONLY_COMMANDS,
    USER_BASH_COMMANDS,
    get_settings,
)
from core.autoexec_policy import looks_like_interactive_sudo_failure
from core.command_executor import CommandExecutor
from core.command_validator import CommandValidator
from core.plugin_system import plugin_manager
from core.project_resolver import ProjectResolver

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool
    message: str
    output: Optional[str] = None
    status: str = "failed"
    reason_code: Optional[str] = None
    project_name: Optional[str] = None

    def to_tuple(self) -> Tuple[bool, str, Optional[str], str, Optional[str], Optional[str]]:
        """Convert to legacy tuple format for backward compatibility."""
        return (self.success, self.message, self.output, self.status, self.reason_code, self.project_name)


@dataclass
class GateResult:
    """Result of a command authorization gate check."""
    allowed: bool
    reason: str
    reason_code: str
    effective_project: Optional[str] = None


class CommandGate:
    """Facade for command authorization checks.

    Delegates to the bridge's existing validation methods without merging
    their internal logic. Provides a single entry point for authorization.
    """

    def __init__(self, bridge: "OpenCodeBridge") -> None:
        self._bridge = bridge

    def check(
        self,
        command_type: str,
        args: List[str],
        user_role: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
        effective_project: Optional[str] = None,
    ) -> GateResult:
        """Run all authorization phases in sequence.

        Phase 1 — Project scope: mutating commands must stay inside the project.
        Phase 2 — File path: non-admin read/edit/write must target allowed paths.
        Phase 3 — Role: role-based authorization with project mutation checks.
        """
        resolved_project = effective_project or project_name

        if project_name:
            scoped, scope_message = self._bridge._validate_command_paths_inside_project(
                command_type,
                args,
                project_name,
            )
            if not scoped:
                return GateResult(False, scope_message, "project_scope_mismatch", project_name)

        trusted_admin = user_role == "admin"
        if command_type in {"read", "edit", "write"} and not trusted_admin and args:
            if not self._bridge._validate_file_path(args[0]):
                return GateResult(
                    False,
                    f"File path not allowed: {args[0]}",
                    "validation_failed",
                    resolved_project,
                )

        authorized, auth_message = self._bridge._authorize_command(
            command_type,
            args,
            user_role,
            resolved_project,
            project_mutation_allowlist,
        )
        if not authorized:
            return GateResult(False, auth_message, "authorization_failed", resolved_project)

        return GateResult(True, "Authorized", "ok", resolved_project)


class OpenCodeBridge:
    """Manages secure communication with OpenCode."""
    
    def __init__(
        self,
        known_projects: Optional[Dict[str, Dict[str, str]]] = None,
        allowed_directories: Optional[List[str]] = None,
    ) -> None:
        settings = get_settings()
        self.allowed_commands = ALLOWED_COMMANDS
        self.allowed_bash_commands = ALLOWED_BASH_COMMANDS
        self.read_only_commands = READ_ONLY_COMMANDS
        self.user_bash_commands = USER_BASH_COMMANDS
        self.admin_only_commands = ADMIN_ONLY_COMMANDS
        self.admin_only_bash_commands = ADMIN_ONLY_BASH_COMMANDS
        self.blacklisted_patterns = BLACKLISTED_PATTERNS
        self.known_projects = known_projects if known_projects is not None else settings.build_known_projects()
        directory_source = allowed_directories if allowed_directories is not None else settings.build_allowed_directories()
        self.allowed_directories = [Path(d) for d in directory_source]
        self.allowed_file_extensions = settings.build_allowed_file_extensions()
        self.backup_enabled = settings.opencode_backup_enabled
        self.backup_suffix = settings.opencode_backup_suffix

        self._validator = CommandValidator(
            known_projects=self.known_projects,
            allowed_bash_commands=set(self.allowed_bash_commands),
            read_only_commands=set(self.read_only_commands),
            admin_only_commands=set(self.admin_only_commands),
            user_bash_commands=set(self.user_bash_commands),
            admin_only_bash_commands=set(self.admin_only_bash_commands),
            allowed_directories=self.allowed_directories,
            allowed_file_extensions=set(self.allowed_file_extensions),
        )
        self._resolver = ProjectResolver(
            known_projects=self.known_projects,
            get_settings=lambda: get_settings(),
        )

        self._executor = CommandExecutor(
            validate_file_path=self._validator.validate_file_path,
            validate_file_size=self._validator.validate_file_size,
            decode_quoted_arg=self._validator.decode_quoted_arg,
            backup_enabled=self.backup_enabled,
            backup_suffix=self.backup_suffix,
        )

    def register_project(
        self,
        name: str,
        path: str,
        project_type: str = "project",
        priority: str = "medium",
    ) -> None:
        """Register or refresh a project for command attribution and cwd resolution."""

        self.known_projects[name] = {
            "path": path,
            "type": project_type,
            "priority": priority,
        }
        
    async def execute_command(
        self,
        command: str,
        user_id: Optional[str] = None,
        project_name: Optional[str] = None,
        user_role: str = "user",
        project_mutation_allowlist: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        tool_run_id: Optional[str] = None,
    ) -> CommandResult:
        """Execute an OpenCode command securely.

        Returns a CommandResult dataclass with execution details.
        """

        before_event = await plugin_manager.emit_event(
            "command:before_execute",
            {
                "command": command,
                "user_id": user_id,
                "project_name": project_name,
            },
        )
        if before_event.cancelled:
            return CommandResult(False, "Execution cancelled by plugin.", status="blocked", reason_code="plugin_cancelled", project_name=project_name)

        command = before_event.data.get("command", command)

        trusted_admin = user_role == "admin"
        validation_result = self._validate_command(command, user_role=user_role)
        if not validation_result[0]:
            return CommandResult(False, validation_result[1], status="blocked", reason_code="validation_failed", project_name=project_name)
        
        command_type, args = validation_result[2], validation_result[3]
        if project_name and project_name not in self.known_projects:
            return CommandResult(False, f"Selected project not registered: {project_name}", status="blocked", reason_code="authorization_failed", project_name=project_name)

        args = self._normalize_placeholder_command_args(command_type, args)
        if command_type == "bash" and self._requires_privileged_setup(args[0] if args else ""):
            return CommandResult(
                False,
                "Sudo commands are not executed via chat. Run privileged steps manually in the terminal and revalidate prerequisites.",
                status="blocked",
                reason_code="privileged_setup_required",
                project_name=project_name,
            )

        resolved_project_name = self._infer_project_name(command_type, args, project_name)
        self._register_repos_project_if_needed(resolved_project_name)
        if (
            project_name
            and resolved_project_name
            and resolved_project_name != project_name
            and self._project_scope_path_operands(command_type, args)
        ):
            return CommandResult(
                False,
                f"Command targets project '{resolved_project_name}', but this conversation is locked to project '{project_name}'",
                status="blocked",
                reason_code="project_scope_mismatch",
                project_name=project_name,
            )

        effective_project_name = project_name or resolved_project_name
        args = self._normalize_file_command_args(command_type, args, effective_project_name)

        gate_result = CommandGate(self).check(
            command_type,
            args,
            user_role,
            project_name,
            project_mutation_allowlist or [],
            effective_project=effective_project_name,
        )
        if not gate_result.allowed:
            return CommandResult(
                False,
                gate_result.reason,
                status="blocked",
                reason_code=gate_result.reason_code,
                project_name=gate_result.effective_project,
            )
        
        try:
            if command_type == "bash":
                resolved_cwd = self._resolve_project_cwd(effective_project_name)
                result = await self._executor.execute_bash(
                    args,
                    resolved_cwd,
                    trusted_shell=trusted_admin,
                )
            elif command_type == "read":
                result = await self._executor.execute_read(args)
            elif command_type == "glob":
                result = await self._executor.execute_glob(args, trusted_paths=trusted_admin)
            elif command_type == "grep":
                resolved_cwd = self._resolve_project_cwd(effective_project_name)
                result = await self._executor.execute_grep(args, resolved_cwd)
            elif command_type == "edit":
                result = await self._executor.execute_edit(args)
            elif command_type == "write":
                result = await self._executor.execute_write(args)
            else:
                result = (False, f"Command not implemented: {command_type}", None)
                
        except (OSError, subprocess.SubprocessError) as e:
            logger.error("Error executing command %s: %s", command, e)
            result = (False, f"Error executing command: {str(e)}", None)
        
        success, message, output = result
        status = "success" if success else "failed"
        reason_code = None if success else "execution_failed"
        if not success and looks_like_interactive_sudo_failure(message, output):
            reason_code = "interactive_sudo_required"
        
        await plugin_manager.emit_event(
            "command:after_execute",
            {
                "command": command,
                "success": success,
                "message": message,
                "output": output,
                "user_id": user_id,
                "project_name": effective_project_name,
            },
        )

        return CommandResult(success, message, output, status, reason_code, effective_project_name)

    @staticmethod
    def _requires_privileged_setup(command: str) -> bool:
        try:
            parts = shlex.split(command)
        except ValueError:
            return bool(re.search(r"(^|[;&|]\s*)sudo(\s|$)", command))
        return "sudo" in {part.lower() for part in parts}

    def _normalize_placeholder_command_args(
        self,
        command_type: Optional[str],
        args: Optional[List[str]],
    ) -> Optional[List[str]]:
        """Map common LLM placeholder paths to this machine configured roots."""

        if not args:
            return args

        normalized = list(args)
        if command_type in {"read", "edit", "write", "glob"} and normalized[0]:
            normalized[0] = self._normalize_placeholder_path_text(str(normalized[0]))
        elif command_type == "bash" and normalized[0]:
            normalized[0] = self._normalize_placeholder_path_text(str(normalized[0]))

        return normalized

    @staticmethod
    def _normalize_placeholder_path_text(text: str) -> str:
        settings = get_settings()
        repos_root = str(settings.dev_repos_root.expanduser().resolve())
        workspace_root = str(settings.dev_workspace_root.expanduser().resolve())

        replacements = [
            (r"(?<![\w/])(?:/home/user|/home/coder|/Users/user)/projects(?P<rest>/[^\s\"']*)?", repos_root),
            (r"(?<![\w/])(?:~|\$HOME)/projects(?P<rest>/[^\s\"']*)?", repos_root),
            (r"(?<![\w/])/workspace/projects(?P<rest>/[^\s\"']*)?", repos_root),
            (r"(?<![\w/])/workspace(?P<rest>/[^\s\"']*)?", repos_root),
            (r"(?<![\w/])(?:/home/user|/home/coder|/Users/user)(?P<rest>/[^\s\"']*)?", workspace_root),
        ]

        normalized = text
        for pattern, root in replacements:
            normalized = re.sub(
                pattern,
                lambda match, target=root: str(Path(target) / (match.group("rest") or "").lstrip("/")),
                normalized,
            )
        return normalized
    
    def _validate_command(
        self,
        command: str,
        user_role: str = "user",
    ) -> Tuple[bool, str, Optional[str], Optional[List[str]]]:
        """Validate and parse an OpenCode command."""

        # Pattern: command "argument"
        pattern = r'^(\w+)\s+"((?:[^"\\]|\\.)*)"(?:\s+(.+))?$'
        match = re.match(pattern, command, re.DOTALL)
        
        if not match:
            return False, f"Invalid command format: {command}", None, None
        
        command_type = match.group(1).lower()
        main_arg = self._decode_quoted_arg(match.group(2))
        extra_args = match.group(3) if match.group(3) else ""
        
        # Check if command is allowed
        if command_type not in self.allowed_commands:
            return False, f"Command not allowed: {command_type}", None, None
        
        # Check for blacklisted patterns
        full_command = f"{command_type} {main_arg} {extra_args}".lower()
        for pattern in self.blacklisted_patterns:
            if pattern in full_command:
                return False, f"Command contains disallowed pattern: {pattern}", None, None
        
        # Validate arguments by command type
        if command_type == "bash":
            if user_role == "admin":
                if not main_arg.strip():
                    return False, "Empty bash command", None, None
            else:
                if not self._validate_bash_command(main_arg):
                    return False, f"Bash command not allowed: {main_arg}", None, None

        return True, "Command valid", command_type, [main_arg, extra_args]

    def _authorize_command(
        self,
        command_type: Optional[str],
        args: Optional[List[str]],
        user_role: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
    ) -> Tuple[bool, str]:
        return self._validator.authorize_command(
            command_type, args, user_role, project_name, project_mutation_allowlist,
        )

    def _authorize_project_mutation(
        self,
        action_name: str,
        args: Optional[List[str]],
        user_role: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
    ) -> Tuple[bool, str]:
        return self._validator._authorize_project_mutation(
            action_name, args, user_role, project_name, project_mutation_allowlist,
        )

    def _authorize_mutation_paths(
        self,
        action_name: str,
        args: Optional[List[str]],
        project_name: str,
    ) -> Tuple[bool, str]:
        return self._validator._authorize_mutation_paths(action_name, args, project_name)

    def _mutation_path_operands(self, action_name: str, args: Optional[List[str]]) -> List[str]:
        return self._validator._mutation_path_operands(action_name, args)

    def _non_option_operands(self, parts: List[str]) -> List[str]:
        return self._validator._non_option_operands(parts)

    def _resolve_command_path(self, raw_path: str, project_root: Path) -> Path:
        return self._validator._resolve_command_path(raw_path, project_root)

    def _validate_command_paths_inside_project(
        self,
        command_type: Optional[str],
        args: Optional[List[str]],
        project_name: str,
    ) -> Tuple[bool, str]:
        return self._validator.validate_command_paths_inside_project(
            command_type, args, project_name,
        )

    def _project_scope_path_operands(
        self,
        command_type: Optional[str],
        args: Optional[List[str]],
    ) -> List[str]:
        return self._validator._project_scope_path_operands(command_type, args)

    def _normalize_file_command_args(
        self,
        command_type: Optional[str],
        args: Optional[List[str]],
        project_name: Optional[str],
    ) -> Optional[List[str]]:
        return self._validator.normalize_file_command_args(command_type, args, project_name)

    def _infer_project_name(
        self,
        command_type: Optional[str],
        args: Optional[List[str]],
        explicit_project_name: Optional[str],
    ) -> Optional[str]:
        return self._resolver.infer_project_name(command_type, args, explicit_project_name)

    def _resolve_project_from_repos_path(self, text: str) -> Optional[str]:
        return self._resolver.resolve_from_repos_path(text)

    @staticmethod
    def _looks_like_path_reference(text: str) -> bool:
        return ProjectResolver._looks_like_path_reference(text)

    def _register_repos_project_if_needed(self, project_name: Optional[str]) -> None:
        self._resolver.register_repos_project_if_needed(project_name, self.register_project)

    def _resolve_project_from_text(self, text: str) -> Optional[str]:
        return self._resolver.resolve_from_text(text)

    def _resolve_project_cwd(self, project_name: Optional[str]) -> str:
        return self._resolver.resolve_cwd(project_name)

    def _validate_bash_command(self, command: str) -> bool:
        return self._validator.validate_bash_command(command)

    def _validate_file_path(self, path: str, check_extension: bool = False) -> bool:
        return self._validator.validate_file_path(path, check_extension)

    def _validate_file_size(self, path: Path, max_size: int) -> bool:
        return self._validator.validate_file_size(path, max_size)

    @staticmethod
    def _decode_quoted_arg(value: str) -> str:
        return CommandValidator.decode_quoted_arg(value)

    def get_project_context(self, project_name: str) -> Optional[Dict]:
        """Get context about a specific project."""
        
        if project_name in self.known_projects:
            return self.known_projects[project_name]
        
        # Try to find by similar name
        for name, info in self.known_projects.items():
            if project_name.lower() in name.lower():
                return info
        
        return None
