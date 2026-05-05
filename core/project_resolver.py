"""Project resolution and registration logic."""

import shlex
from pathlib import Path
from typing import Callable, Dict, List, Optional


class ProjectResolver:
    """Resolves project context from paths, text, and current working directory."""

    def __init__(
        self,
        known_projects: Dict[str, Dict],
        get_settings: Callable,
    ) -> None:
        self.known_projects = known_projects
        self._get_settings = get_settings

    @property
    def _repos_root(self) -> Path:
        return self._get_settings().dev_repos_root

    @property
    def _default_execution_cwd(self) -> Path:
        return self._get_settings().default_execution_cwd

    def resolve_from_repos_path(self, text: str) -> Optional[str]:
        """Resolve a project name from a repos root path reference."""
        if not text or not self._looks_like_path_reference(text):
            return None

        try:
            path = Path(text).expanduser().resolve()
        except (OSError, ValueError):
            return None

        repos_root = self._repos_root.expanduser().resolve()
        try:
            relative_path = path.relative_to(repos_root)
        except ValueError:
            return None

        if not relative_path.parts:
            return None
        project_name = relative_path.parts[0]
        return project_name if project_name and not project_name.startswith(".") else None

    @staticmethod
    def _looks_like_path_reference(text: str) -> bool:
        stripped = str(text).strip()
        if not stripped:
            return False
        return (
            stripped.startswith(("/", "~", ".", "$HOME"))
            or "/" in stripped
            or "\\" in stripped
        )

    def register_repos_project_if_needed(
        self,
        project_name: Optional[str],
        register_callback: Callable,
    ) -> None:
        """Register a repos project if it doesn't exist yet.

        Uses a callback to avoid tight coupling with OpenCodeBridge.register_project.
        """
        if not project_name or project_name in self.known_projects:
            return

        repos_root = self._repos_root.expanduser().resolve()
        project_root = repos_root / project_name
        try:
            project_root.relative_to(repos_root)
        except ValueError:
            return

        register_callback(project_name, str(project_root), "project", "medium")

    def resolve_from_text(self, text: str) -> Optional[str]:
        """Resolve a project name from a path or textual command fragment."""
        if not text:
            return None

        best_match: Optional[str] = None
        best_score: int = -1

        text_lower = text.lower()
        looks_like_path = self._looks_like_path_reference(text)

        if looks_like_path:
            try:
                path = Path(text).resolve()
            except (OSError, ValueError):
                path = None

            if path is not None:
                for project_name, project_info in self.known_projects.items():
                    project_path = Path(project_info["path"]).resolve()
                    try:
                        if path.is_relative_to(project_path):
                            score = len(str(project_path))
                            if score > best_score:
                                best_score = score
                                best_match = project_name
                    except ValueError:
                        continue

            if best_match:
                return best_match

        for project_name, project_info in self.known_projects.items():
            project_path = str(Path(project_info["path"]).resolve())
            if project_name.lower() in text_lower or project_path.lower() in text_lower:
                score = len(project_name)
                if score > best_score:
                    best_score = score
                    best_match = project_name

        return best_match

    def resolve_cwd(self, project_name: Optional[str]) -> str:
        """Resolve the working directory for a project, falling back to default."""
        if project_name and project_name in self.known_projects:
            project_path = Path(self.known_projects[project_name]["path"])
            if project_path.is_dir():
                return str(project_path)
        return str(self._default_execution_cwd)

    def infer_project_name(
        self,
        command_type: Optional[str],
        args: Optional[List],
        explicit_project_name: Optional[str],
    ) -> Optional[str]:
        """Infer project context from an explicit project name or command arguments."""
        if command_type is None or not args:
            return explicit_project_name if explicit_project_name in self.known_projects else None

        candidates = []
        main_arg = args[0]
        extra_args = args[1] if len(args) > 1 else ""

        if command_type in {"read", "edit", "write"}:
            candidates.append(main_arg)
        elif command_type == "bash":
            try:
                candidates.extend(shlex.split(main_arg))
            except ValueError:
                candidates.append(main_arg)
        elif command_type in {"glob", "grep"}:
            candidates.extend([main_arg, extra_args])

        for candidate in candidates:
            resolved_project = self.resolve_from_text(candidate)
            if resolved_project:
                return resolved_project
            repos_project = self.resolve_from_repos_path(candidate)
            if repos_project:
                return repos_project

        if explicit_project_name and explicit_project_name in self.known_projects:
            return explicit_project_name

        return None
