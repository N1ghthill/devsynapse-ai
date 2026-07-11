"""GitHub OAuth device flow and secure token storage."""

from __future__ import annotations

import importlib
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests

from config.settings import get_settings

DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
API_USER_URL = "https://api.github.com/user"
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
KEYRING_SERVICE = "devsynapse-ai.github"
KEYRING_USERNAME = "github.com"


@dataclass
class PendingGitHubAuth:
    client_id: str
    device_code: str
    expires_at: float
    interval: int
    scopes: str


_PENDING_AUTH: dict[str, PendingGitHubAuth] = {}
_PENDING_AUTH_LOCK = threading.Lock()


class SecureTokenStore:
    """Small keyring wrapper that fails closed when secure storage is unavailable."""

    def __init__(self, service: str = KEYRING_SERVICE, username: str = KEYRING_USERNAME) -> None:
        self.service = service
        self.username = username

    def _keyring(self) -> Any:
        try:
            return importlib.import_module("keyring")
        except ImportError as exc:
            raise RuntimeError("secure_storage_unavailable") from exc

    def get(self) -> str | None:
        try:
            token = self._keyring().get_password(self.service, self.username)
        except Exception as exc:
            raise RuntimeError("secure_storage_unavailable") from exc
        return token if isinstance(token, str) and token.strip() else None

    def set(self, token: str) -> None:
        try:
            self._keyring().set_password(self.service, self.username, token)
        except Exception as exc:
            raise RuntimeError("secure_storage_unavailable") from exc

    def delete(self) -> None:
        try:
            self._keyring().delete_password(self.service, self.username)
        except Exception:
            # Deleting an absent token should be idempotent.
            pass


def _client_id() -> str:
    client_id = (get_settings().github_client_id or "").strip()
    if not client_id:
        raise ValueError("github_client_id_missing")
    return client_id


def _oauth_scopes(operation_input: dict[str, Any] | None = None) -> str:
    requested = ""
    if operation_input is not None:
        requested = str(operation_input.get("scopes") or "").strip()
    return requested or get_settings().github_oauth_scopes.strip() or "read:user read:org"


def _post_json(url: str, data: dict[str, str]) -> dict[str, Any]:
    try:
        response = requests.post(
            url,
            data=data,
            headers={"Accept": "application/json"},
            timeout=12,
        )
    except requests.RequestException as exc:
        raise ValueError("github_api_unavailable") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("github_invalid_response") from exc
    if response.status_code >= 400:
        error = payload.get("error") if isinstance(payload, dict) else None
        raise ValueError(f"github_{error or 'request_failed'}")
    if not isinstance(payload, dict):
        raise ValueError("github_invalid_response")
    return payload


def _github_account(token: str) -> dict[str, Any]:
    try:
        response = requests.get(
            API_USER_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=12,
        )
    except requests.RequestException as exc:
        raise ValueError("github_api_unavailable") from exc
    if response.status_code == 401:
        SecureTokenStore().delete()
        raise ValueError("github_token_invalid")
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ValueError("github_api_unavailable") from exc
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("github_invalid_response")
    return {
        "login": payload.get("login"),
        "id": payload.get("id"),
        "name": payload.get("name"),
        "avatarUrl": payload.get("avatar_url"),
        "htmlUrl": payload.get("html_url"),
    }


def github_auth_start(operation_input: dict[str, Any]) -> dict[str, Any]:
    client_id = _client_id()
    scopes = _oauth_scopes(operation_input)
    payload = _post_json(
        DEVICE_CODE_URL,
        {
            "client_id": client_id,
            "scope": scopes,
        },
    )
    if payload.get("error"):
        raise ValueError(f"github_{payload['error']}")

    device_code = str(payload.get("device_code") or "")
    user_code = str(payload.get("user_code") or "")
    verification_uri = str(payload.get("verification_uri") or "")
    if not device_code or not user_code or not verification_uri:
        raise ValueError("github_invalid_response")

    expires_in = int(payload.get("expires_in") or 900)
    interval = int(payload.get("interval") or 5)
    auth_session_id = f"github-auth-{uuid.uuid4().hex}"
    with _PENDING_AUTH_LOCK:
        _PENDING_AUTH[auth_session_id] = PendingGitHubAuth(
            client_id=client_id,
            device_code=device_code,
            expires_at=time.time() + expires_in,
            interval=interval,
            scopes=scopes,
        )

    return {
        "authSessionId": auth_session_id,
        "verificationUri": verification_uri,
        "userCode": user_code,
        "expiresIn": expires_in,
        "interval": interval,
        "scopes": scopes,
    }


def github_auth_poll(operation_input: dict[str, Any]) -> dict[str, Any]:
    auth_session_id = str(operation_input.get("authSessionId") or "").strip()
    if not auth_session_id:
        raise ValueError("missing_auth_session_id")
    with _PENDING_AUTH_LOCK:
        pending = _PENDING_AUTH.get(auth_session_id)
    if pending is None:
        raise ValueError("github_auth_session_not_found")
    if time.time() >= pending.expires_at:
        with _PENDING_AUTH_LOCK:
            _PENDING_AUTH.pop(auth_session_id, None)
        return {"status": "expired", "authenticated": False}

    payload = _post_json(
        ACCESS_TOKEN_URL,
        {
            "client_id": pending.client_id,
            "device_code": pending.device_code,
            "grant_type": DEVICE_GRANT_TYPE,
        },
    )
    error = payload.get("error")
    if error == "authorization_pending":
        return {
            "status": "pending",
            "authenticated": False,
            "interval": pending.interval,
        }
    if error == "slow_down":
        pending.interval += 5
        return {
            "status": "slow_down",
            "authenticated": False,
            "interval": pending.interval,
        }
    if error in {"expired_token", "token_expired"}:
        with _PENDING_AUTH_LOCK:
            _PENDING_AUTH.pop(auth_session_id, None)
        return {"status": "expired", "authenticated": False}
    if error:
        raise ValueError(f"github_{error}")

    token = str(payload.get("access_token") or "")
    if not token:
        raise ValueError("github_invalid_response")
    try:
        SecureTokenStore().set(token)
    except RuntimeError as exc:
        raise ValueError("secure_storage_unavailable") from exc
    with _PENDING_AUTH_LOCK:
        _PENDING_AUTH.pop(auth_session_id, None)
    return {
        "status": "authenticated",
        "authenticated": True,
        "account": _github_account(token),
        "scopes": payload.get("scope") or pending.scopes,
    }


def github_account_status(_operation_input: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        token = SecureTokenStore().get()
    except RuntimeError:
        return {
            "connected": False,
            "secureStorageAvailable": False,
            "error": "secure_storage_unavailable",
        }
    if not token:
        return {"connected": False, "secureStorageAvailable": True}
    return {
        "connected": True,
        "secureStorageAvailable": True,
        "account": _github_account(token),
    }


def github_auth_disconnect(_operation_input: dict[str, Any] | None = None) -> dict[str, Any]:
    SecureTokenStore().delete()
    return {"connected": False}
