"""First-run runtime bootstrap for desktop and shell flows."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config.settings import CONFIG_FILE, DATA_DIR, LOGS_DIR, get_settings
from core.auth import AuthService
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge
from core.runtime_config import (
    ensure_runtime_config_file,
    read_runtime_config,
    set_runtime_config_values,
)


def _expand_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _discover_git_projects(repos_root: Path, limit: int = 200) -> list[dict[str, str]]:
    if not repos_root.is_dir():
        return []

    projects: list[dict[str, str]] = []
    for entry in sorted(repos_root.iterdir(), key=lambda item: item.name.lower()):
        if len(projects) >= limit:
            break
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if not (entry / ".git").is_dir():
            continue
        projects.append(
            {
                "name": entry.name,
                "path": str(entry.resolve()),
                "type": "project",
                "priority": "medium",
            }
        )
    return projects


def build_allowed_directories(workspace_root: Path, repos_root: Path) -> list[Path]:
    roots = {workspace_root.resolve(), repos_root.resolve(), Path("/tmp"), Path("/var/tmp")}
    return sorted(roots, key=str)


def refresh_bridge_runtime_scope(
    bridge: OpenCodeBridge,
    memory_system: MemorySystem,
    workspace_root: Path,
    repos_root: Path,
) -> None:
    bridge.allowed_directories = build_allowed_directories(workspace_root, repos_root)
    bridge.known_projects = memory_system.get_project_lookup()


def get_bootstrap_status(auth_service: AuthService) -> dict[str, Any]:
    ensure_runtime_config_file()
    settings = get_settings()
    values = read_runtime_config()
    explicit_repos_root = values.get("DEV_REPOS_ROOT") or os.getenv("DEV_REPOS_ROOT")
    explicit_workspace_root = values.get("DEV_WORKSPACE_ROOT") or os.getenv("DEV_WORKSPACE_ROOT")
    configured_repos_root = _expand_path(explicit_repos_root) if explicit_repos_root else None
    suggested_workspace = (
        _expand_path(explicit_workspace_root)
        if explicit_workspace_root
        else _expand_path(settings.dev_workspace_root)
    )
    suggested_repos = configured_repos_root or _expand_path(settings.dev_repos_root)
    api_key = values.get("DEEPSEEK_API_KEY") or settings.deepseek_api_key or ""
    admin_password_required = auth_service.admin_requires_password_setup()
    workspace_configured = configured_repos_root is not None and configured_repos_root.is_dir()

    reasons: list[str] = []
    if admin_password_required:
        reasons.append("admin_password")
    if not str(api_key).strip():
        reasons.append("deepseek_api_key")
    if not workspace_configured:
        reasons.append("workspace")

    return {
        "requires_setup": bool(reasons),
        "reasons": reasons,
        "admin_password_required": admin_password_required,
        "deepseek_api_key_configured": bool(str(api_key).strip()),
        "workspace_configured": workspace_configured,
        "default_admin_username": settings.default_admin_username,
        "suggested_workspace_root": str(suggested_workspace),
        "suggested_repos_root": str(suggested_repos),
        "workspace_root": explicit_workspace_root,
        "repos_root": explicit_repos_root,
        "config_path": str(CONFIG_FILE),
        "data_dir": str(DATA_DIR),
        "logs_dir": str(LOGS_DIR),
        "discovered_project_count": len(_discover_git_projects(suggested_repos)),
    }


def apply_bootstrap(
    *,
    auth_service: AuthService,
    memory_system: MemorySystem,
    bridge: OpenCodeBridge,
    deepseek_api_key: str | None,
    repos_root: str,
    workspace_root: str | None = None,
    admin_password: str | None = None,
    register_discovered_projects: bool = True,
) -> dict[str, Any]:
    ensure_runtime_config_file()
    settings = get_settings()
    values = read_runtime_config()

    resolved_repos_root = _expand_path(repos_root)
    if not resolved_repos_root.is_dir():
        raise ValueError("Repository root must be an existing directory")

    resolved_workspace_root = (
        _expand_path(workspace_root)
        if workspace_root
        else resolved_repos_root.parent
    )
    if not resolved_workspace_root.is_dir():
        raise ValueError("Workspace root must be an existing directory")

    effective_api_key = (
        deepseek_api_key.strip()
        if deepseek_api_key
        else (values.get("DEEPSEEK_API_KEY") or settings.deepseek_api_key or "").strip()
    )
    if not effective_api_key:
        raise ValueError("DeepSeek API key is required")

    user = None
    if admin_password:
        user = auth_service.bootstrap_admin_password(admin_password)

    set_runtime_config_values(
        {
            "DEVSYNAPSE_BOOTSTRAP_COMPLETED": "true",
            "DEEPSEEK_API_KEY": effective_api_key,
            "DEV_WORKSPACE_ROOT": resolved_workspace_root,
            "DEV_REPOS_ROOT": resolved_repos_root,
            "MEMORY_DB_PATH": DATA_DIR / "devsynapse_memory.db",
            "MONITORING_DB_PATH": DATA_DIR / "devsynapse_monitoring.db",
            "LOG_FILE": LOGS_DIR / "devsynapse.log",
        }
    )
    get_settings.cache_clear()
    settings = get_settings()

    discovered_projects = _discover_git_projects(resolved_repos_root)
    registered_projects: list[dict[str, str]] = []
    if register_discovered_projects:
        for project in discovered_projects:
            existing_project = memory_system.get_project(project["name"], include_missing=True)
            if existing_project is None or not existing_project["path_exists"]:
                memory_system.add_project(
                    project["name"],
                    project["path"],
                    project["type"],
                    project["priority"],
                    replace=existing_project is not None,
                )
            registered_projects.append(project)

    refresh_bridge_runtime_scope(
        bridge,
        memory_system,
        resolved_workspace_root,
        resolved_repos_root,
    )

    if user is None:
        user = {
            "username": settings.default_admin_username,
            "role": "admin",
        }

    return {
        "user": user,
        "deepseek_api_key": effective_api_key,
        "registered_projects": registered_projects,
        "status": get_bootstrap_status(auth_service),
    }
