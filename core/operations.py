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
            "name": "project.connect",
            "riskClass": "local_mutation",
            "description": "Associate one local project with a GitHub repository.",
        },
        {
            "name": "project.connection",
            "riskClass": "observe",
            "description": "Return the GitHub repository associated with one local project.",
        },
        {
            "name": "commit.preview",
            "riskClass": "prepare",
            "description": "Build a read-only commit preview from the current project state.",
        },
        {
            "name": "commit.preview.validate",
            "riskClass": "observe",
            "description": "Check whether a commit preview still matches current project state.",
        },
        {
            "name": "github.repository.list",
            "riskClass": "observe",
            "description": "List GitHub repositories available to the connected account.",
        },
        {
            "name": "github.auth.start",
            "riskClass": "prepare",
            "description": "Start GitHub OAuth device flow and return the browser verification code.",
        },
        {
            "name": "github.auth.poll",
            "riskClass": "local_mutation",
            "description": "Poll GitHub OAuth device flow and store the token in secure storage.",
        },
        {
            "name": "github.account.status",
            "riskClass": "observe",
            "description": "Return the active GitHub account without exposing credentials.",
        },
        {
            "name": "github.auth.disconnect",
            "riskClass": "local_mutation",
            "description": "Remove the stored GitHub token from secure storage.",
        },
        {
            "name": "llm.provider.status",
            "riskClass": "observe",
            "description": "Return configured LLM providers and selected model without secrets.",
        },
        {
            "name": "llm.provider.configure",
            "riskClass": "local_mutation",
            "description": "Store one provider API key and selected model in user runtime config.",
        },
        {
            "name": "llm.model.discover",
            "riskClass": "observe",
            "description": "Discover available provider models without exposing provider credentials.",
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
    links: dict[str, dict[str, Any]] = {}
    if known_projects is None:
        try:
            from core.memory import MemorySystem

            links = MemorySystem().get_project_repository_links()
        except Exception:
            links = {}
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
                "repository": links.get(name),
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
    return result.stdout.rstrip("\n")


def _untracked_content_fingerprint(project_path: Path, entries: list[dict[str, str]]) -> str:
    digest = sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        if entry["indexStatus"] != "untracked":
            continue
        relative_path = entry["path"]
        file_path = (project_path / relative_path).resolve()
        try:
            file_path.relative_to(project_path)
        except ValueError:
            continue
        if not file_path.is_file():
            continue
        digest.update(relative_path.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        try:
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            continue
        digest.update(b"\0")
    return digest.hexdigest()


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


def _repository_state(project_name: str) -> dict[str, Any]:
    path = _project_path(project_name)
    porcelain = _git(path, "status", "--porcelain", "-uall") or ""
    branch = _git(path, "branch", "--show-current")
    head = _git(path, "rev-parse", "--short", "HEAD")
    worktree_diff = _git(path, "diff", "--no-ext-diff") or ""
    staged_diff = _git(path, "diff", "--cached", "--no-ext-diff") or ""
    files = git_status_entries(porcelain)
    untracked_fingerprint = _untracked_content_fingerprint(path, files)
    state_fingerprint = sha256(
        (
            f"{project_name}\0{path}\0{branch}\0{head}\0{porcelain}\0"
            f"{worktree_diff}\0{staged_diff}\0{untracked_fingerprint}"
        ).encode("utf-8")
    ).hexdigest()
    return {
        "projectName": project_name,
        "path": path,
        "porcelain": porcelain,
        "worktreeDiff": worktree_diff,
        "stagedDiff": staged_diff,
        "currentBranch": branch or None,
        "headCommit": head or None,
        "stateFingerprint": state_fingerprint,
        "previewId": state_fingerprint[:16],
        "isClean": not bool(porcelain),
        "counts": git_status_counts(porcelain),
        "files": files,
    }


def repository_snapshot(operation_input: dict[str, Any]) -> dict[str, Any]:
    from core.memory import MemorySystem

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
        "repository": MemorySystem().get_project_repository_link(project_name),
        "hasLocalChanges": bool(porcelain),
    }


def commit_preview(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    state = _repository_state(project_name)
    path = state["path"]
    diff_stat = _git(path, "diff", "--stat") or ""
    staged_diff_stat = _git(path, "diff", "--cached", "--stat") or ""
    return {
        "previewId": state["previewId"],
        "projectName": project_name,
        "path": str(path),
        "riskClass": "prepare",
        "proposedOperation": "commit.create",
        "currentBranch": state["currentBranch"],
        "headCommit": state["headCommit"],
        "stateFingerprint": state["stateFingerprint"],
        "isStale": False,
        "isClean": state["isClean"],
        "counts": state["counts"],
        "files": state["files"],
        "worktreeDiffStat": diff_stat,
        "stagedDiffStat": staged_diff_stat,
    }


def commit_preview_validate(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = required_string(operation_input, "projectName")
    expected_fingerprint = required_string(operation_input, "stateFingerprint")
    if project_name is None:
        raise ValueError("missing_project_name")
    if expected_fingerprint is None:
        raise ValueError("missing_state_fingerprint")

    state = _repository_state(project_name)
    current_fingerprint = state["stateFingerprint"]
    valid = expected_fingerprint == current_fingerprint
    return {
        "projectName": project_name,
        "path": str(state["path"]),
        "valid": valid,
        "isStale": not valid,
        "expectedStateFingerprint": expected_fingerprint,
        "currentStateFingerprint": current_fingerprint,
        "expectedPreviewId": expected_fingerprint[:16],
        "currentPreviewId": state["previewId"],
        "currentBranch": state["currentBranch"],
        "headCommit": state["headCommit"],
        "isClean": state["isClean"],
        "counts": state["counts"],
        "files": state["files"],
    }


def git_status(operation_input: dict[str, Any]) -> dict[str, Any]:
    project_name = required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    state = _repository_state(project_name)
    return {
        "projectName": project_name,
        "path": str(state["path"]),
        "branch": state["currentBranch"],
        "headCommit": state["headCommit"],
        "stateFingerprint": state["stateFingerprint"],
        "counts": state["counts"],
        "files": state["files"],
        "isClean": state["isClean"],
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
            "repository": None,
        }
    }


def github_repository_list(operation_input: dict[str, Any]) -> dict[str, Any]:
    from core.github_client import GitHubApiClient

    query = required_string(operation_input, "query") or ""
    limit_value = operation_input.get("limit")
    limit = limit_value if isinstance(limit_value, int) and not isinstance(limit_value, bool) else 30
    return GitHubApiClient().list_repositories(query=query, limit=limit)


def _repository_identity(operation_input: dict[str, Any]) -> dict[str, Any]:
    repository = operation_input.get("repository")
    if isinstance(repository, dict):
        source = repository
    else:
        source = operation_input

    owner = required_string(source, "owner")
    name = required_string(source, "name") or required_string(source, "repositoryName")
    full_name = required_string(source, "fullName") or (
        f"{owner}/{name}" if owner is not None and name is not None else None
    )
    if owner is None or name is None:
        raise ValueError("missing_repository_identity")
    return {
        "owner": owner,
        "name": name,
        "fullName": full_name,
        "htmlUrl": required_string(source, "htmlUrl"),
        "cloneUrl": required_string(source, "cloneUrl"),
        "defaultBranch": required_string(source, "defaultBranch"),
        "private": bool(source.get("private")),
    }


def project_connect(operation_input: dict[str, Any]) -> dict[str, Any]:
    from core.github_auth import github_account_status
    from core.memory import MemorySystem

    project_name = required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")

    status = github_account_status({})
    if not status.get("connected"):
        raise ValueError("github_not_connected")
    account = status.get("account") if isinstance(status.get("account"), dict) else {}
    account_login = account.get("login") if isinstance(account, dict) else None
    repository = _repository_identity(operation_input)
    link = MemorySystem().connect_project_repository(
        project_name,
        repository,
        account_login=account_login if isinstance(account_login, str) else None,
    )
    return {
        "projectName": project_name,
        "repository": link,
    }


def project_connection(operation_input: dict[str, Any]) -> dict[str, Any]:
    from core.memory import MemorySystem

    project_name = required_string(operation_input, "projectName")
    if project_name is None:
        raise ValueError("missing_project_name")
    link = MemorySystem().get_project_repository_link(project_name)
    return {
        "projectName": project_name,
        "connected": link is not None,
        "repository": link,
    }


def operation_risk_class(operation_name: str) -> str:
    for definition in operation_definitions():
        if definition["name"] == operation_name:
            return str(definition["riskClass"])
    raise KeyError(operation_name)


def run_operation(operation_name: str, operation_input: dict[str, Any]) -> dict[str, Any]:
    from core.github_auth import (
        github_account_status,
        github_auth_disconnect,
        github_auth_poll,
        github_auth_start,
    )
    from core.llm_provider_config import configure_provider, discover_models, provider_status

    operations = {
        "project.list": lambda: project_list(),
        "repository.snapshot": lambda: repository_snapshot(operation_input),
        "git.status": lambda: git_status(operation_input),
        "project.register": lambda: project_register(operation_input),
        "project.connect": lambda: project_connect(operation_input),
        "project.connection": lambda: project_connection(operation_input),
        "commit.preview": lambda: commit_preview(operation_input),
        "commit.preview.validate": lambda: commit_preview_validate(operation_input),
        "github.repository.list": lambda: github_repository_list(operation_input),
        "github.auth.start": lambda: github_auth_start(operation_input),
        "github.auth.poll": lambda: github_auth_poll(operation_input),
        "github.account.status": lambda: github_account_status(operation_input),
        "github.auth.disconnect": lambda: github_auth_disconnect(operation_input),
        "llm.provider.status": lambda: provider_status(operation_input),
        "llm.provider.configure": lambda: configure_provider(operation_input),
        "llm.model.discover": lambda: discover_models(operation_input),
    }
    if operation_name not in operations:
        raise KeyError(operation_name)
    return operations[operation_name]()
