"""Read-only GitHub API client for desktop repository operations."""

from __future__ import annotations

from typing import Any

import requests

from core.github_auth import SecureTokenStore

API_BASE_URL = "https://api.github.com"
DEFAULT_REPOSITORY_LIMIT = 30
MAX_REPOSITORY_LIMIT = 100


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def normalize_repository(payload: dict[str, Any]) -> dict[str, Any]:
    owner = payload.get("owner") if isinstance(payload.get("owner"), dict) else {}
    owner_login = owner.get("login") if isinstance(owner, dict) else None
    name = payload.get("name")
    full_name = payload.get("full_name")
    html_url = payload.get("html_url")
    clone_url = payload.get("clone_url")
    ssh_url = payload.get("ssh_url")

    if not isinstance(name, str) or not name.strip():
        raise ValueError("github_invalid_response")
    if not isinstance(owner_login, str) or not owner_login.strip():
        raise ValueError("github_invalid_response")

    return {
        "id": _integer(payload.get("id")),
        "owner": owner_login,
        "name": name,
        "fullName": full_name if isinstance(full_name, str) else f"{owner_login}/{name}",
        "private": bool(payload.get("private")),
        "fork": bool(payload.get("fork")),
        "archived": bool(payload.get("archived")),
        "defaultBranch": payload.get("default_branch")
        if isinstance(payload.get("default_branch"), str)
        else None,
        "description": payload.get("description")
        if isinstance(payload.get("description"), str)
        else None,
        "htmlUrl": html_url if isinstance(html_url, str) else None,
        "cloneUrl": clone_url if isinstance(clone_url, str) else None,
        "sshUrl": ssh_url if isinstance(ssh_url, str) else None,
        "permissions": payload.get("permissions") if isinstance(payload.get("permissions"), dict) else {},
        "updatedAt": payload.get("updated_at") if isinstance(payload.get("updated_at"), str) else None,
        "pushedAt": payload.get("pushed_at") if isinstance(payload.get("pushed_at"), str) else None,
    }


class GitHubApiClient:
    """Backend-only GitHub client that never returns credentials."""

    def __init__(self, token_store: SecureTokenStore | None = None) -> None:
        self.token_store = token_store or SecureTokenStore()

    def _token(self) -> str:
        try:
            token = self.token_store.get()
        except RuntimeError as exc:
            raise ValueError("secure_storage_unavailable") from exc
        if not token:
            raise ValueError("github_not_connected")
        return token

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        token = self._token()
        try:
            response = requests.get(
                f"{API_BASE_URL}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params=params or {},
                timeout=12,
            )
        except requests.RequestException as exc:
            raise ValueError("github_api_unavailable") from exc
        if response.status_code == 401:
            self.token_store.delete()
            raise ValueError("github_token_invalid")
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise ValueError("github_api_unavailable") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise ValueError("github_invalid_response") from exc

    @staticmethod
    def _limit(value: Any) -> int:
        if isinstance(value, int) and not isinstance(value, bool):
            return min(max(value, 1), MAX_REPOSITORY_LIMIT)
        return DEFAULT_REPOSITORY_LIMIT

    def list_repositories(
        self,
        *,
        query: str = "",
        limit: int = DEFAULT_REPOSITORY_LIMIT,
    ) -> dict[str, Any]:
        per_page = self._limit(limit)
        payload = self._get(
            "/user/repos",
            {
                "visibility": "all",
                "affiliation": "owner,collaborator,organization_member",
                "sort": "updated",
                "direction": "desc",
                "per_page": per_page,
                "page": 1,
            },
        )
        if not isinstance(payload, list):
            raise ValueError("github_invalid_response")

        repositories = [normalize_repository(item) for item in payload if isinstance(item, dict)]
        normalized_query = query.strip().lower()
        if normalized_query:
            repositories = [
                repository
                for repository in repositories
                if normalized_query in repository["fullName"].lower()
                or normalized_query in repository["name"].lower()
                or (
                    isinstance(repository.get("description"), str)
                    and normalized_query in repository["description"].lower()
                )
            ]

        return {
            "repositories": repositories,
            "query": query.strip(),
            "limit": per_page,
            "totalReturned": len(repositories),
        }
