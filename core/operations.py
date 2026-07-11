"""Typed read-only operation kernel for the desktop sidecar."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def required_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def operation_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "project.list",
            "riskClass": "observe",
            "description": "List configured local projects and repository availability.",
        },
        {
            "name": "repository.snapshot",
            "riskClass": "observe",
            "description": "Return read-only identity and branch evidence for one project.",
        },
        {
            "name": "git.status",
            "riskClass": "observe",
            "description": "Return normalized read-only Git status counts for one project.",
        },
    ]


def _known_projects() -> dict[str, dict[str, str]]:
    from config.settings import get_settings

    return get_settings().build_known_projects()


def project_list(known_projects: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    projects = known_projects if known_projects is not None else _known_projects()
    output = []
    for name, info in sorted(projects.items()):
        path = Path(str(info.get("path", ""))).expanduser()
        output.append(
            {
                "name": name,
                "path": str(path),
                "type": info.get("type", "project"),
                "priority": info.get("priority", "medium"),
                "exists": path.exists(),
                "isGitRepository": (path / ".git").exists(),
            }
        )
    return {"projects": output}


def _project_path(project_name: str) -> Path:
    projects = _known_projects()
    info = projects.get(project_name)
    if not info:
        raise ValueError("project_not_found")
    path = Path(str(info.get("path", ""))).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError("project_path_unavailable")
    return path


def _git(project_path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_status_counts(porcelain: str) -> dict[str, int]:
    counts = {"staged": 0, "unstaged": 0, "untracked": 0}
    for line in porcelain.splitlines():
        if not line:
            continue
        if line.startswith("??"):
            counts["untracked"] += 1
            continue
        if len(line) >= 2:
            if line[0] != " ":
                counts["staged"] += 1
            if line[1] != " ":
                counts["unstaged"] += 1
    return counts


def repository_snapshot(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    path = _project_path(project_name)
    branch = _git(path, "branch", "--show-current")
    head = _git(path, "rev-parse", "--short", "HEAD")
    remote = _git(path, "remote", "get-url", "origin")
    porcelain = _git(path, "status", "--porcelain") or ""
    return {
        "projectName": project_name,
        "path": str(path),
        "isGitRepository": (path / ".git").exists(),
        "currentBranch": branch or None,
        "headCommit": head or None,
        "originUrl": remote or None,
        "hasLocalChanges": bool(porcelain),
    }


def git_status(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    path = _project_path(project_name)
    porcelain = _git(path, "status", "--porcelain") or ""
    branch = _git(path, "branch", "--show-current")
    return {
        "projectName": project_name,
        "path": str(path),
        "branch": branch or None,
        "counts": git_status_counts(porcelain),
        "isClean": not bool(porcelain),
    }


def run_operation(operation_name: str, operation_input: dict[str, Any]) -> dict[str, Any]:
    operations = {
        "project.list": lambda: project_list(),
        "repository.snapshot": lambda: repository_snapshot(operation_input),
        "git.status": lambda: git_status(operation_input),
    }
    if operation_name not in operations:
        raise KeyError(operation_name)
    return operations[operation_name]()
