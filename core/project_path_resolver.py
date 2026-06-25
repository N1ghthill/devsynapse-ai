"""Project path resolution with exact path support.

Ensures projects are created in the EXACT location specified by the user.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PathResolution:
    """Result of path resolution."""

    absolute_path: Path
    display_path: str
    is_valid: bool
    error_message: Optional[str] = None
    requires_confirmation: bool = False
    project_name: Optional[str] = None
    source: str = "unknown"


class ProjectPathResolver:
    """Resolves and validates project paths from user messages.

    Supports:
    - Full paths: ~/ruas/repositorios/calc_py
    - Relative paths: ./calc_py, ../projects/calc_py
    - Project names: calc_py (resolved to repos_root/calc_py)
    - Path extraction from messages: "crie em ~/path/to/project"
    """

    def __init__(
        self,
        repos_root: Path,
        workspace_root: Path,
        allowed_directories: Optional[List[Path]] = None,
        default_cwd: Optional[Path] = None,
    ) -> None:
        self.repos_root = repos_root.expanduser().resolve()
        self.workspace_root = workspace_root.expanduser().resolve()
        self.default_cwd = (default_cwd or Path.cwd()).expanduser().resolve()
        self.allowed_directories = allowed_directories or [
            self.repos_root,
            self.workspace_root,
        ]

    def resolve_from_message(self, message: str) -> PathResolution:
        """Extract and resolve path from user message.

        Examples:
        - "Crie uma calculadora em ~/ruas/repositorios/calc_py"
        - "Quero criar um projeto em ./meu-app"
        - "Crie o projeto my-api"
        """
        # 1. Try to extract explicit path from message
        extracted_path = self._extract_path_from_message(message)
        if extracted_path:
            return self._resolve_path(extracted_path)

        # 2. Try to extract project name and build path
        project_name = self._extract_project_name(message)
        if project_name:
            path = self.repos_root / project_name
            return self._resolve_path(str(path), source="repos_root_fallback")

        # 3. No path found
        return PathResolution(
            absolute_path=self.repos_root,
            display_path=str(self.repos_root),
            is_valid=False,
            error_message="Não foi possível determinar o local do projeto. Por favor, especifique o caminho.",
        )

    def resolve_current_git_project(self) -> PathResolution:
        """Resolve the current Git repository root when the app is launched inside one."""
        git_root = self._find_git_root(self.default_cwd)
        if git_root is None:
            return PathResolution(
                absolute_path=self.default_cwd,
                display_path=self._format_display_path(self.default_cwd),
                is_valid=False,
                error_message="Diretório atual não está dentro de um repositório Git.",
                source="current_cwd",
            )
        return self._valid_resolution(git_root, source="current_git")

    def resolve_path(self, path_str: str) -> PathResolution:
        """Resolve a specific path string.

        Args:
            path_str: Path string (can be relative, absolute, or with ~)

        Returns:
            PathResolution with validated path
        """
        return self._resolve_path(path_str)

    def _resolve_path(self, path_str: str, source: str = "explicit_path") -> PathResolution:
        """Internal path resolution logic."""
        if not path_str or not path_str.strip():
            return PathResolution(
                absolute_path=self.repos_root,
                display_path=str(self.repos_root),
                is_valid=False,
                error_message="Path vazio",
            )

        # Parse path
        try:
            path = Path(path_str.strip())
        except (ValueError, TypeError) as e:
            return PathResolution(
                absolute_path=self.repos_root,
                display_path=str(self.repos_root),
                is_valid=False,
                error_message=f"Path inválido: {e}",
            )

        # Handle relative paths
        if not path.is_absolute():
            if path_str.startswith("~/") or path_str.startswith("~\\"):
                # Expand ~
                path = path.expanduser()
            elif path_str.startswith("./") or path_str.startswith("../"):
                # Relative to the configured execution cwd, not necessarily
                # the Python process cwd used by tests or CI.
                path = self.default_cwd / path
                path = path.resolve()
            else:
                # Relative to repos root
                path = self.repos_root / path
                path = path.resolve()
        else:
            # Absolute path - expand ~ if present
            path = path.expanduser().resolve()

        if path.exists():
            git_root = self._find_git_root(path)
            if git_root is not None and self._git_root_applies_to_path(path, git_root):
                return self._valid_resolution(git_root, source="git_discovery")

        # Validate path is in allowed directory. This is the fallback for new
        # project directories that do not exist yet and therefore cannot expose
        # a Git root.
        if not self._is_in_allowed_directory(path):
            return PathResolution(
                absolute_path=path,
                display_path=self._format_display_path(path),
                is_valid=False,
                error_message=(
                    "Path fora dos diretórios permitidos e sem repositório Git detectado. "
                    f"Use um caminho explícito em um repositório Git existente, "
                    f"{self.repos_root} ou {self.workspace_root}."
                ),
                project_name=self._extract_project_name_from_path(path),
                source=source,
            )

        return self._valid_resolution(path, source=source)

    def _valid_resolution(self, path: Path, source: str) -> PathResolution:
        """Build a successful path resolution."""
        return PathResolution(
            absolute_path=path,
            display_path=self._format_display_path(path),
            is_valid=True,
            requires_confirmation=True,
            project_name=self._extract_project_name_from_path(path),
            source=source,
        )

    def _find_git_root(self, path: Path) -> Optional[Path]:
        """Return the nearest Git repository root for an existing path or parent."""
        try:
            candidate = path.expanduser()
            if not candidate.exists():
                existing_parent = next(
                    (parent for parent in [candidate.parent, *candidate.parents] if parent.exists()),
                    None,
                )
                if existing_parent is None:
                    return None
                candidate = existing_parent
            candidate = candidate.resolve()
            if candidate.is_file():
                candidate = candidate.parent
        except OSError:
            return None

        for current in [candidate, *candidate.parents]:
            if (current / ".git").exists():
                return current
        return None

    def _git_root_applies_to_path(self, path: Path, git_root: Path) -> bool:
        """Avoid treating an ambient parent Git repo as the project for nested paths."""
        try:
            resolved_path = path.resolve()
            resolved_git_root = git_root.resolve()
        except OSError:
            return False

        if resolved_path == resolved_git_root:
            return True

        for allowed in self.allowed_directories:
            try:
                allowed_root = allowed.expanduser().resolve()
                resolved_path.relative_to(allowed_root)
            except (OSError, ValueError):
                continue
            try:
                resolved_git_root.relative_to(allowed_root)
                return True
            except ValueError:
                return False

        return resolved_git_root != self.workspace_root

    def _extract_path_from_message(self, message: str) -> Optional[str]:
        """Extract path from user message.

        Supports ANY path the user specifies:
        - "~/any/path/to/project"
        - "/home/user/any/project"
        - "./relative/path"
        - "../parent/project"
        """
        # Path extraction patterns (Portuguese and English)
        patterns = [
            # "em ~/path" or "no ~/path" or "na ~/path"
            r'(?:em|no|na|para|em\s+que|para\s+(?:o\s+)?)\s*([~\.]?/[\w\-./]+)',
            # "at ~/path" or "in ~/path" or "to ~/path"
            r'(?:at|in|to|into)\s+([~\.]?/[\w\-./]+)',
            # Absolute path (ANY absolute path, not just home/Users/ruas)
            r'(/[\w\-./]+)',
            # Relative path
            r'(\.{1,2}/[\w\-./]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                path = match.group(1)
                # Filter out very short paths that are probably not real paths
                if len(path) > 2 and path not in ['/', '/tmp', '/var', '/etc', '/usr']:
                    return path

        return None

    def _extract_project_name(self, message: str) -> Optional[str]:
        """Extract project name from message.

        Patterns:
        - "projeto myapp"
        - "app myapp"
        - "aplicação myapp"
        """
        # Only extract project names that look like actual project names
        # Filter out common Portuguese/English words
        common_words = {
            "um", "uma", "o", "a", "meu", "minha", "este", "esta", "esse", "essa",
            "a", "an", "the", "my", "this", "that",
            "projeto", "project", "app", "aplicação", "application",
            "crie", "criar", "fazer", "create", "make",
        }

        patterns = [
            r'(?:projeto|projecto?|app|aplicação?)\s+([a-zA-Z0-9][\w\-]{2,})',
            r'(?:crie|criar|cirar)\s+(?:um\s+)?(?:projeto|projecto?|app|aplicação?)\s+([a-zA-Z0-9][\w\-]{2,})',
            r'([a-zA-Z0-9][\w\-]{2,})\s+(?:projeto|projecto?|app|aplicação?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1)
                # Filter out common words
                if name.lower() not in common_words:
                    return name

        return None

    def _extract_project_name_from_path(self, path: Path) -> str:
        """Extract project name from path.

        For ~/ruas/repositorios/calc_py, returns "calc_py"
        Uses the LAST directory name, not the first.
        """
        # Use the last directory name as project name
        # This handles cases like ~/ruas/repositorios/calc_py -> calc_py
        return path.name

    def _is_in_allowed_directory(self, path: Path) -> bool:
        """Check if path is within allowed directories using whitelist approach.

        Security: Only allows paths that resolve to be within one of the
        configured allowed_directories. This prevents path traversal attacks,
        symlink escapes, and access to unauthorized directories.
        """
        # Resolve the path to follow symlinks and get absolute path
        resolved = path.resolve()

        # Check against each allowed directory
        for allowed in self.allowed_directories:
            allowed_resolved = allowed.resolve()
            try:
                # is_relative_to() checks if resolved path is under allowed_resolved
                resolved.relative_to(allowed_resolved)
                return True
            except ValueError:
                # Path is not under this allowed directory, try next
                continue

        # Path is not within any allowed directory
        return False

    def _format_display_path(self, path: Path) -> str:
        """Format path for display (shorten with ~ if possible)."""
        home = Path.home()
        try:
            relative = path.relative_to(home)
            return f"~/{relative}"
        except ValueError:
            pass

        try:
            relative = path.relative_to(self.repos_root)
            return f"repos/{relative}"
        except ValueError:
            pass

        try:
            relative = path.relative_to(self.workspace_root)
            return f"workspace/{relative}"
        except ValueError:
            pass

        return str(path)
