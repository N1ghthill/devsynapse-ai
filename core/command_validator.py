"""Command validation and authorization logic."""

import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CommandValidator:
    """Validates and authorizes command execution based on role, project, and path rules."""

    def __init__(
        self,
        known_projects: Dict[str, Dict],
        allowed_bash_commands: set,
        read_only_commands: set,
        admin_only_commands: set,
        user_bash_commands: set,
        admin_only_bash_commands: set,
        allowed_directories: List[Path],
        allowed_file_extensions: set,
    ) -> None:
        self.known_projects = known_projects
        self.allowed_bash_commands = allowed_bash_commands
        self.read_only_commands = read_only_commands
        self.admin_only_commands = admin_only_commands
        self.user_bash_commands = user_bash_commands
        self.admin_only_bash_commands = admin_only_bash_commands
        self.allowed_directories = allowed_directories
        self.allowed_file_extensions = allowed_file_extensions

    def authorize_command(
        self,
        command_type: Optional[str],
        args: Optional[List],
        user_role: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
    ) -> Tuple[bool, str]:
        """Authorize execution based on role and command sensitivity."""
        if command_type is None:
            return False, "Invalid command type for authorization"

        if user_role == "admin":
            return True, "Authorized as trusted administrator"

        if command_type in self.read_only_commands:
            return True, "Authorized"

        if command_type in self.admin_only_commands:
            return self._authorize_project_mutation(
                command_type,
                args,
                user_role,
                project_name,
                project_mutation_allowlist,
            )

        if command_type == "bash":
            return self._authorize_bash_command(
                args,
                user_role,
                project_name,
                project_mutation_allowlist,
            )

        return False, f"Command '{command_type}' not authorized for current role"

    def _authorize_bash_command(
        self,
        args: Optional[List],
        user_role: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
    ) -> Tuple[bool, str]:
        bash_command = args[0] if args else ""
        try:
            parts = shlex.split(bash_command)
        except ValueError:
            return False, "Invalid bash command syntax"
        if not parts:
            return False, "Empty bash command"

        first_cmd = parts[0].lower()
        if first_cmd in self.user_bash_commands:
            return True, "Authorized"
        if first_cmd == "kill":
            if user_role == "admin":
                return True, "Authorized"
            return False, "Bash command 'kill' requires admin role"
        if first_cmd in self.admin_only_bash_commands:
            return self._authorize_project_mutation(
                f"bash:{first_cmd}",
                args,
                user_role,
                project_name,
                project_mutation_allowlist,
            )
        return False, f"Bash command '{first_cmd}' not authorized for current role"

    def _authorize_project_mutation(
        self,
        action_name: str,
        args: Optional[List],
        user_role: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
    ) -> Tuple[bool, str]:
        """Authorize mutation only for explicitly allowed projects."""
        if not project_name:
            return (
                False,
                (
                    f"Action '{action_name}' requires explicit project context "
                    "or a resolvable path to an allowed project"
                ),
            )

        if project_name not in self.known_projects:
            return False, f"Project '{project_name}' is not registered"

        if user_role != "admin" and project_name not in project_mutation_allowlist:
            return (
                False,
                f"Action '{action_name}' not authorized for project '{project_name}'",
            )

        paths_authorized, path_message = self._authorize_mutation_paths(
            action_name,
            args,
            project_name,
        )
        if not paths_authorized:
            return False, path_message

        if user_role == "admin" or project_name in project_mutation_allowlist:
            return True, f"Authorized for project '{project_name}'"

        return (
            False,
            f"Action '{action_name}' not authorized for project '{project_name}'",
        )

    def _authorize_mutation_paths(
        self,
        action_name: str,
        args: Optional[List],
        project_name: str,
    ) -> Tuple[bool, str]:
        """Ensure mutating commands only target paths inside the resolved project."""
        project_root = Path(self.known_projects[project_name]["path"]).expanduser().resolve()
        raw_paths = self._mutation_path_operands(action_name, args)
        if not raw_paths:
            return (
                False,
                (
                    f"Action '{action_name}' requires a file or directory path "
                    f"inside project '{project_name}'"
                ),
            )

        for raw_path in raw_paths:
            resolved_path = self._resolve_command_path(raw_path, project_root)
            try:
                if not resolved_path.is_relative_to(project_root):
                    return (
                        False,
                        (
                            f"Action '{action_name}' cannot modify path outside "
                            f"project '{project_name}': {resolved_path}"
                        ),
                    )
            except ValueError:
                return (
                    False,
                    (
                        f"Action '{action_name}' cannot modify path outside "
                        f"project '{project_name}': {resolved_path}"
                    ),
                )

        return True, "Autorizado"

    def _mutation_path_operands(self, action_name: str, args: Optional[List]) -> List[str]:
        """Extract path operands from mutating commands."""
        if not args:
            return []

        if action_name in {"edit", "write"}:
            return [args[0]] if args[0] else []

        if not action_name.startswith("bash:"):
            return []

        bash_command = args[0] if args else ""
        try:
            parts = shlex.split(bash_command)
        except ValueError:
            return []

        if len(parts) < 2:
            return []

        command_name = action_name.split(":", 1)[1]
        operands = self._non_option_operands(parts[1:])

        if command_name == "chmod":
            return operands[1:] if len(operands) > 1 else []

        if command_name in {"touch", "mkdir", "cp", "mv", "rm"}:
            return operands

        return []

    def _non_option_operands(self, parts: List[str]) -> List[str]:
        """Return simple non-option operands from a shell argument list."""
        operands: List[str] = []
        option_takes_value = {"-t", "--target-directory", "--reference"}
        skip_next = False
        after_option_marker = False
        for index, part in enumerate(parts):
            if skip_next:
                skip_next = False
                continue
            if after_option_marker:
                operands.append(part)
                continue
            if part == "--":
                after_option_marker = True
                continue
            if part in option_takes_value:
                next_index = index + 1
                if next_index < len(parts):
                    operands.append(parts[next_index])
                skip_next = True
                continue
            if part.startswith("--target-directory=") or part.startswith("--reference="):
                operands.append(part.split("=", 1)[1])
                continue
            if part.startswith("-"):
                continue
            operands.append(part)
        return operands

    def _resolve_command_path(self, raw_path: str, project_root: Path) -> Path:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = project_root / path
        return path.resolve()

    def validate_command_paths_inside_project(
        self,
        command_type: Optional[str],
        args: Optional[List],
        project_name: str,
    ) -> Tuple[bool, str]:
        """Keep mutating actions inside the explicitly selected chat project."""
        if project_name not in self.known_projects:
            return False, f"Selected project is not registered: {project_name}"

        project_root = Path(self.known_projects[project_name]["path"]).expanduser().resolve()
        for raw_path in self._project_scope_path_operands(command_type, args):
            resolved_path = self._resolve_command_path(raw_path, project_root)
            try:
                if resolved_path.is_relative_to(project_root):
                    continue
            except ValueError:
                pass

            return (
                False,
                (
                    f"Command cannot access path outside project '{project_name}': "
                    f"{resolved_path}"
                ),
            )

        return True, "Project scope respected"

    def _project_scope_path_operands(
        self,
        command_type: Optional[str],
        args: Optional[List],
    ) -> List[str]:
        if not args:
            return []

        if command_type in {"edit", "write"}:
            return [str(args[0])] if args[0] else []

        if command_type != "bash":
            return []

        try:
            parts = shlex.split(str(args[0]))
        except ValueError:
            return []

        if not parts:
            return []

        first_cmd = parts[0].lower()
        if first_cmd not in self.admin_only_bash_commands:
            return []

        return self._mutation_path_operands(f"bash:{first_cmd}", args)

    def normalize_file_command_args(
        self,
        command_type: Optional[str],
        args: Optional[List],
        project_name: Optional[str],
    ) -> Optional[List]:
        """Resolve relative file-command paths against the selected project."""
        if command_type not in {"read", "edit", "write"} or not args:
            return args
        if not project_name or project_name not in self.known_projects:
            return args

        project_root = Path(self.known_projects[project_name]["path"]).expanduser().resolve()
        normalized_args = list(args)
        normalized_args[0] = str(self._resolve_command_path(str(args[0]), project_root))
        return normalized_args

    def validate_bash_command(self, command: str) -> bool:
        """Validate a bash command."""
        parts = shlex.split(command)
        if not parts:
            return False

        first_cmd = parts[0].lower()
        if first_cmd not in self.allowed_bash_commands:
            return False

        dangerous_patterns = ["|", ">", ">>", "<", "&", ";", "`", "$(", ".."]
        for pattern in dangerous_patterns:
            if pattern in command:
                return False

        return True

    def validate_file_path(self, path: str, check_extension: bool = False) -> bool:
        """Validate a file path."""
        try:
            path_obj = Path(path).resolve()
            for allowed_dir in self.allowed_directories:
                try:
                    if path_obj.is_relative_to(allowed_dir.resolve()):
                        if check_extension and path_obj.suffix:
                            if path_obj.suffix not in self.allowed_file_extensions:
                                return False
                        return True
                except ValueError:
                    continue
            return False
        except OSError:
            return False

    def validate_file_size(self, path: Path, max_size: int) -> bool:
        """Validate file size."""
        try:
            if path.exists() and path.is_file():
                file_size = path.stat().st_size
                return file_size <= max_size
            return True
        except OSError:
            return False

    @staticmethod
    def decode_quoted_arg(value: str) -> str:
        """Decode the small escape set used inside OpenCode quoted arguments."""
        decoded = []
        index = 0
        while index < len(value):
            char = value[index]
            if char != "\\" or index + 1 >= len(value):
                decoded.append(char)
                index += 1
                continue

            next_char = value[index + 1]
            if next_char == "n":
                decoded.append("\n")
            elif next_char == "r":
                decoded.append("\r")
            elif next_char == "t":
                decoded.append("\t")
            elif next_char in {'"', "\\"}:
                decoded.append(next_char)
            else:
                decoded.append(char)
                decoded.append(next_char)
            index += 2

        return "".join(decoded)
