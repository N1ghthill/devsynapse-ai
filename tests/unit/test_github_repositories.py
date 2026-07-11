from unittest.mock import patch

import pytest

from config.settings import AppSettings
from core import github_auth
from core.github_client import GitHubApiClient
from core.memory import MemorySystem
from core.operations import run_operation


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("request failed")


class FakeTokenStore:
    token: str | None = "gho_secret"

    def get(self):
        return self.token

    def delete(self):
        self.__class__.token = None


def test_github_client_lists_repositories_without_exposing_token(monkeypatch):
    captured_headers = {}

    def fake_get(_url, *, headers, params, timeout):
        captured_headers.update(headers)
        assert params["per_page"] == 30
        assert timeout == 12
        return FakeResponse(
            [
                {
                    "id": 1,
                    "name": "devsynapse-ai",
                    "full_name": "N1ghthill/devsynapse-ai",
                    "private": False,
                    "fork": False,
                    "archived": False,
                    "default_branch": "main",
                    "html_url": "https://github.com/N1ghthill/devsynapse-ai",
                    "clone_url": "https://github.com/N1ghthill/devsynapse-ai.git",
                    "owner": {"login": "N1ghthill"},
                    "permissions": {"pull": True, "push": True, "admin": True},
                    "updated_at": "2026-07-11T00:00:00Z",
                }
            ]
        )

    monkeypatch.setattr("core.github_client.requests.get", fake_get)

    result = GitHubApiClient(token_store=FakeTokenStore()).list_repositories()

    assert result["repositories"][0]["fullName"] == "N1ghthill/devsynapse-ai"
    assert result["repositories"][0]["permissions"]["push"] is True
    assert "gho_secret" not in str(result)
    assert captured_headers["Authorization"] == "Bearer gho_secret"


def test_github_client_filters_repositories_locally(monkeypatch):
    monkeypatch.setattr(
        "core.github_client.requests.get",
        lambda *args, **kwargs: FakeResponse(
            [
                {
                    "name": "alpha",
                    "full_name": "N1ghthill/alpha",
                    "owner": {"login": "N1ghthill"},
                },
                {
                    "name": "beta",
                    "full_name": "N1ghthill/beta",
                    "owner": {"login": "N1ghthill"},
                },
            ]
        ),
    )

    result = GitHubApiClient(token_store=FakeTokenStore()).list_repositories(query="bet")

    assert [repository["name"] for repository in result["repositories"]] == ["beta"]


def test_project_repository_link_persists_and_is_deleted_with_project(tmp_path):
    settings = AppSettings()
    settings.memory_db_path = tmp_path / "memory.db"
    project_path = tmp_path / "repo"
    project_path.mkdir()

    with patch("core.memory.system.get_settings", return_value=settings), patch(
        "core.memory.projects.get_settings",
        return_value=settings,
    ):
        memory = MemorySystem()
        memory.add_project("repo", str(project_path), "project", "medium")
        link = memory.connect_project_repository(
            "repo",
            {
                "owner": "N1ghthill",
                "name": "devsynapse-ai",
                "fullName": "N1ghthill/devsynapse-ai",
                "htmlUrl": "https://github.com/N1ghthill/devsynapse-ai",
                "cloneUrl": "https://github.com/N1ghthill/devsynapse-ai.git",
                "defaultBranch": "main",
                "private": False,
            },
            account_login="N1ghthill",
        )

        assert link["fullName"] == "N1ghthill/devsynapse-ai"
        assert memory.get_project_repository_link("repo")["accountLogin"] == "N1ghthill"
        assert memory.get_project_repository_links()["repo"]["name"] == "devsynapse-ai"
        assert memory.delete_project("repo") is True
        assert memory.get_project_repository_link("repo") is None


def test_project_connect_operation_requires_github_account(monkeypatch):
    monkeypatch.setattr(
        github_auth,
        "github_account_status",
        lambda _input: {"connected": False, "secureStorageAvailable": True},
    )

    with pytest.raises(ValueError, match="github_not_connected"):
        run_operation(
            "project.connect",
            {
                "projectName": "repo",
                "repository": {"owner": "N1ghthill", "name": "devsynapse-ai"},
            },
        )


def test_project_connect_operation_stores_repository(monkeypatch):
    saved = {}

    class FakeMemory:
        def connect_project_repository(self, project_name, repository, *, account_login=None):
            saved.update(
                {
                    "project_name": project_name,
                    "repository": repository,
                    "account_login": account_login,
                }
            )
            return {
                "provider": "github",
                "owner": repository["owner"],
                "name": repository["name"],
                "fullName": repository["fullName"],
                "accountLogin": account_login,
            }

    monkeypatch.setattr(
        github_auth,
        "github_account_status",
        lambda _input: {"connected": True, "account": {"login": "N1ghthill"}},
    )
    monkeypatch.setattr("core.memory.MemorySystem", FakeMemory)

    result = run_operation(
        "project.connect",
        {
            "projectName": "repo",
            "repository": {
                "owner": "N1ghthill",
                "name": "devsynapse-ai",
                "fullName": "N1ghthill/devsynapse-ai",
            },
        },
    )

    assert saved["project_name"] == "repo"
    assert saved["account_login"] == "N1ghthill"
    assert result["repository"]["fullName"] == "N1ghthill/devsynapse-ai"
