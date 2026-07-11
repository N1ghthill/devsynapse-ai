"""Typed read-only operation kernel for the desktop sidecar."""

from __future__ import annotations

import subprocess
from hashlib import sha256
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
        {
            "name": "project.register",
            "riskClass": "local_mutation",
            "description": "Register one local folder as a desktop project without changing it.",
        },
        {
            "name": "commit.preview",
            "riskClass": "prepare",
            "description": "Build a read-only commit preview from the current project state.",
        },
    ]


def _known_projects() -> dict[str, dict[str, str]]:
    from config.settings import get_settings
    from core.memory import MemorySystem

    projects = get_settings().build_known_projects()
    try:
        projects.update(MemorySystem().get_project_lookup())
    except Exception:
        pass
    return projects


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


def git_status_entries(porcelain: str) -> list[dict[str, str]]:
    entries = []
    for line in porcelain.splitlines():
        if not line:
            continue
        if line.startswith("??"):
            entries.append(
                {
                    "path": line[3:],
                    "indexStatus": "untracked",
                    "worktreeStatus": "untracked",
                }
            )
            continue
        if len(line) < 4:
            continue
        index_status = line[0]
        worktree_status = line[1]
        entries.append(
            {
                "path": line[3:],
                "indexStatus": "clean" if index_status == " " else index_status,
                "worktreeStatus": "clean" if worktree_status == " " else worktree_status,
            }
        )
    return entries


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


def commit_preview(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    path = _project_path(project_name)
    porcelain = _git(path, "status", "--porcelain") or ""
    branch = _git(path, "branch", "--show-current")
    head = _git(path, "rev-parse", "--short", "HEAD")
    diff_stat = _git(path, "diff", "--stat") or ""
    staged_diff_stat = _git(path, "diff", "--cached", "--stat") or ""
    state_fingerprint = sha256(
        f"{project_name}\0{path}\0{branch}\0{head}\0{porcelain}".encode("utf-8")
    ).hexdigest()
    preview_id = state_fingerprint[:16]
    return {
        "previewId": preview_id,
        "projectName": project_name,
        "path": str(path),
        "riskClass": "prepare",
        "proposedOperation": "commit.create",
        "currentBranch": branch or None,
        "headCommit": head or None,
        "stateFingerprint": state_fingerprint,
        "isClean": not bool(porcelain),
        "counts": git_status_counts(porcelain),
        "files": git_status_entries(porcelain),
        "worktreeDiffStat": diff_stat,
        "stagedDiffStat": staged_diff_stat,
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


def project_register(operation_input: dict[str, Any]) -> dict[str, Any]:
    from core.memory import MemorySystem

    path_value = required_string(operation_input, "path")
    if path_value is None:
        raise ValueError("missing_project_path")
    path = Path(path_value).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError("project_path_unavailable")

    project_name = required_string(operation_input, "projectName") or path.name
    memory = MemorySystem()
    memory.add_project(project_name, str(path), "project", "medium")
    is_git_repository = (path / ".git").exists()
    return {
        "project": {
            "name": project_name,
            "path": str(path),
            "type": "project",
            "priority": "medium",
            "exists": True,
            "isGitRepository": is_git_repository,
        }
    }


def operation_risk_class(operation_name: str) -> str:
    for definition in operation_definitions():
        if definition["name"] == operation_name:
            return str(definition["riskClass"])
    raise KeyError(operation_name)


def run_operation(operation_name: str, operation_input: dict[str, Any]) -> dict[str, Any]:
    operations = {
        "project.list": lambda: project_list(),
        "repository.snapshot": lambda: repository_snapshot(operation_input),
        "git.status": lambda: git_status(operation_input),
        "project.register": lambda: project_register(operation_input),
        "commit.preview": lambda: commit_preview(operation_input),
    }
    if operation_name not in operations:
        raise KeyError(operation_name)
    return operations[operation_name]()
