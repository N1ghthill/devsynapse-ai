import subprocess
from pathlib import Path
from types import SimpleNamespace

from core.desktop_sidecar import (
    BackendState,
    SidecarHandler,
    conversation_cancel_events,
    conversation_send_events,
    conversation_started_events,
)
from core.operations import (
    git_status_counts,
    git_status_entries,
    operation_definitions,
    operation_risk_class,
    project_list,
    run_operation,
)


def _handler(token: str, header: str | None) -> SidecarHandler:
    handler = object.__new__(SidecarHandler)
    handler.server = SimpleNamespace(
        backend_state=BackendState(
            data_dir=Path("/tmp/devsynapse-test"),
            version="1.0.0",
            auth_token=token,
        )
    )
    handler.headers = {"authorization": header} if header else {}
    return handler


def test_sidecar_handler_requires_bearer_token():
    assert _handler("secret", None)._authorized() is False
    assert _handler("secret", "Bearer wrong")._authorized() is False
    assert _handler("secret", "Bearer secret")._authorized() is True


def test_conversation_start_events_are_typed():
    events = conversation_started_events("req-1", "conv-1")

    assert [event["type"] for event in events] == [
        "response.started",
        "response.completed",
    ]
    assert all(event["requestId"] == "req-1" for event in events)
    assert all(event["conversationId"] == "conv-1" for event in events)


def test_conversation_event_contract_has_required_identity_fields():
    events = [
        *conversation_started_events("req-start", "conv-1"),
        *conversation_send_events("req-send", "conv-1", "hello"),
        *conversation_cancel_events("req-cancel", "conv-1"),
    ]

    for event in events:
        assert isinstance(event["type"], str)
        assert event["requestId"].startswith("req-")
        assert event["conversationId"] == "conv-1"


def test_conversation_send_events_return_delta():
    events = conversation_send_events("req-2", "conv-1", "Core response")

    assert [event["type"] for event in events] == [
        "response.started",
        "response.delta",
        "response.completed",
    ]
    assert events[1]["delta"] == "Core response"


def test_conversation_send_events_disclose_pending_core_command():
    events = conversation_send_events(
        "req-2",
        "conv-1",
        "Core response",
        command_pending=True,
    )

    assert [event["type"] for event in events] == [
        "response.started",
        "response.delta",
        "operation.progress",
        "response.completed",
    ]
    assert "not executed" in events[2]["delta"]


def test_conversation_cancel_event_is_terminal_failure():
    events = conversation_cancel_events("req-3", "conv-1")

    assert events == [
        {
            "type": "response.failed",
            "requestId": "req-3",
            "conversationId": "conv-1",
            "error": "cancelled",
        }
    ]


def test_operation_definitions_are_read_only():
    definitions = operation_definitions()

    assert [definition["name"] for definition in definitions[:3]] == [
        "project.list",
        "repository.snapshot",
        "git.status",
    ]
    assert {definition["riskClass"] for definition in definitions[:3]} == {"observe"}


def test_project_register_operation_is_local_mutation():
    assert operation_risk_class("project.register") == "local_mutation"


def test_github_auth_poll_is_local_mutation():
    assert operation_risk_class("github.auth.poll") == "local_mutation"


def test_project_connect_is_local_mutation():
    assert operation_risk_class("project.connect") == "local_mutation"


def test_github_repository_list_is_observe():
    assert operation_risk_class("github.repository.list") == "observe"


def test_commit_preview_validate_is_observe():
    assert operation_risk_class("commit.preview.validate") == "observe"


def test_project_register_persists_local_project(monkeypatch, tmp_path):
    repo = tmp_path / "chosen"
    (repo / ".git").mkdir(parents=True)
    saved: dict[str, str] = {}

    class FakeMemory:
        def add_project(
            self,
            name: str,
            path: str,
            project_type: str,
            priority: str,
        ) -> None:
            saved.update(
                {
                    "name": name,
                    "path": path,
                    "project_type": project_type,
                    "priority": priority,
                }
            )

    monkeypatch.setattr("core.memory.MemorySystem", FakeMemory)

    result = run_operation("project.register", {"path": str(repo)})

    assert saved == {
        "name": "chosen",
        "path": str(repo.resolve()),
        "project_type": "project",
        "priority": "medium",
    }
    assert result["project"]["isGitRepository"] is True


def test_commit_preview_returns_prepare_contract(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    tracked.write_text("one\ntwo\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)

    monkeypatch.setattr(
        "core.operations._known_projects",
        lambda: {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "medium",
            }
        },
    )

    result = run_operation("commit.preview", {"projectName": "repo"})

    assert result["riskClass"] == "prepare"
    assert result["proposedOperation"] == "commit.create"
    assert result["isClean"] is False
    assert result["counts"] == {"staged": 1, "unstaged": 0, "untracked": 0}
    assert result["files"][0]["path"] == "tracked.txt"
    assert len(result["stateFingerprint"]) == 64
    assert result["isStale"] is False


def test_commit_preview_validate_detects_stale_state(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    tracked.write_text("one\ntwo\n", encoding="utf-8")

    monkeypatch.setattr(
        "core.operations._known_projects",
        lambda: {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "medium",
            }
        },
    )

    preview = run_operation("commit.preview", {"projectName": "repo"})
    valid = run_operation(
        "commit.preview.validate",
        {
            "projectName": "repo",
            "stateFingerprint": preview["stateFingerprint"],
        },
    )

    assert valid["valid"] is True
    assert valid["isStale"] is False
    assert valid["currentPreviewId"] == preview["previewId"]

    tracked.write_text("one\ntwo\nthree\n", encoding="utf-8")
    stale = run_operation(
        "commit.preview.validate",
        {
            "projectName": "repo",
            "stateFingerprint": preview["stateFingerprint"],
        },
    )

    assert stale["valid"] is False
    assert stale["isStale"] is True
    assert stale["expectedPreviewId"] == preview["previewId"]
    assert stale["currentPreviewId"] != preview["previewId"]
    assert stale["files"][0]["path"] == "tracked.txt"


def test_commit_preview_fingerprint_tracks_untracked_file_content(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "new.txt").write_text("draft one\n", encoding="utf-8")

    monkeypatch.setattr(
        "core.operations._known_projects",
        lambda: {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "medium",
            }
        },
    )

    preview = run_operation("commit.preview", {"projectName": "repo"})
    (repo / "new.txt").write_text("draft two\n", encoding="utf-8")
    validation = run_operation(
        "commit.preview.validate",
        {
            "projectName": "repo",
            "stateFingerprint": preview["stateFingerprint"],
        },
    )

    assert validation["isStale"] is True
    assert validation["currentStateFingerprint"] != preview["stateFingerprint"]


def test_commit_preview_validate_requires_fingerprint():
    try:
        run_operation("commit.preview.validate", {"projectName": "repo"})
    except ValueError as exc:
        assert str(exc) == "missing_state_fingerprint"
    else:
        raise AssertionError("commit.preview.validate should require stateFingerprint")


def test_project_list_operation_contract(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    monkeypatch.setattr(
        "core.operations._known_projects",
        lambda: {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "high",
            }
        },
    )

    result = run_operation("project.list", {})

    assert set(result) == {"projects"}
    assert result["projects"][0]["name"] == "repo"
    assert result["projects"][0]["isGitRepository"] is True
    assert result["projects"][0]["repository"] is None


def test_project_list_normalizes_known_projects(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    result = project_list(
        {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "high",
            }
        }
    )

    assert result["projects"] == [
        {
            "name": "repo",
            "path": str(repo),
            "type": "project",
            "priority": "high",
            "exists": True,
            "isGitRepository": True,
            "repository": None,
        }
    ]


def test_git_status_counts_parses_porcelain():
    assert git_status_counts(" M changed.py\nA  staged.py\n?? new.py\nMM both.py\n") == {
        "staged": 2,
        "unstaged": 2,
        "untracked": 1,
    }


def test_git_status_entries_normalize_porcelain():
    assert git_status_entries(" M changed.py\nA  staged.py\n?? new.py\n") == [
        {
            "path": "changed.py",
            "indexStatus": "clean",
            "worktreeStatus": "M",
        },
        {
            "path": "staged.py",
            "indexStatus": "A",
            "worktreeStatus": "clean",
        },
        {
            "path": "new.py",
            "indexStatus": "untracked",
            "worktreeStatus": "untracked",
        },
    ]


def test_git_status_returns_files_and_fingerprint(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "new.py").write_text("print('new')\n", encoding="utf-8")

    monkeypatch.setattr(
        "core.operations._known_projects",
        lambda: {
            "repo": {
                "path": str(repo),
                "type": "project",
                "priority": "medium",
            }
        },
    )

    result = run_operation("git.status", {"projectName": "repo"})

    assert result["counts"] == {"staged": 0, "unstaged": 0, "untracked": 1}
    assert result["files"] == [
        {
            "path": "new.py",
            "indexStatus": "untracked",
            "worktreeStatus": "untracked",
        }
    ]
    assert len(result["stateFingerprint"]) == 64
