from types import SimpleNamespace

from core import github_auth


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("request failed")


class FakeTokenStore:
    token: str | None = None

    def get(self):
        return self.token

    def set(self, token: str):
        self.__class__.token = token

    def delete(self):
        self.__class__.token = None


def _settings():
    return SimpleNamespace(
        github_client_id="client-123",
        github_oauth_scopes="read:user read:org",
    )


def test_github_auth_start_returns_user_code_without_device_code(monkeypatch):
    monkeypatch.setattr(github_auth, "get_settings", _settings)
    monkeypatch.setattr(
        github_auth.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "device_code": "device-secret",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }
        ),
    )

    result = github_auth.github_auth_start({})

    assert result["verificationUri"] == "https://github.com/login/device"
    assert result["userCode"] == "ABCD-1234"
    assert result["authSessionId"].startswith("github-auth-")
    assert "deviceCode" not in result
    assert "device_code" not in result


def test_github_auth_poll_pending_does_not_store_token(monkeypatch):
    monkeypatch.setattr(github_auth, "get_settings", _settings)
    monkeypatch.setattr(
        github_auth.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "device_code": "device-secret",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }
        ),
    )
    started = github_auth.github_auth_start({})
    monkeypatch.setattr(
        github_auth.requests,
        "post",
        lambda *args, **kwargs: FakeResponse({"error": "authorization_pending"}),
    )

    result = github_auth.github_auth_poll({"authSessionId": started["authSessionId"]})

    assert result == {"status": "pending", "authenticated": False, "interval": 5}


def test_github_auth_poll_success_stores_token_without_returning_it(monkeypatch):
    FakeTokenStore.token = None
    monkeypatch.setattr(github_auth, "get_settings", _settings)
    monkeypatch.setattr(github_auth, "SecureTokenStore", FakeTokenStore)
    monkeypatch.setattr(
        github_auth.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "device_code": "device-secret",
                "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device",
                "expires_in": 900,
                "interval": 5,
            }
        ),
    )
    started = github_auth.github_auth_start({})
    monkeypatch.setattr(
        github_auth.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "access_token": "gho_secret",
                "scope": "read:user",
                "token_type": "bearer",
            }
        ),
    )
    monkeypatch.setattr(
        github_auth.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            {
                "login": "octocat",
                "id": 1,
                "name": "The Octocat",
                "avatar_url": "https://avatars.githubusercontent.com/u/1",
                "html_url": "https://github.com/octocat",
            }
        ),
    )

    result = github_auth.github_auth_poll({"authSessionId": started["authSessionId"]})

    assert FakeTokenStore.token == "gho_secret"
    assert result["authenticated"] is True
    assert result["account"]["login"] == "octocat"
    assert "access_token" not in result
    assert "gho_secret" not in str(result)


def test_github_status_reports_secure_storage_unavailable(monkeypatch):
    class BrokenTokenStore:
        def get(self):
            raise RuntimeError("secure_storage_unavailable")

    monkeypatch.setattr(github_auth, "SecureTokenStore", BrokenTokenStore)

    result = github_auth.github_account_status({})

    assert result == {
        "connected": False,
        "secureStorageAvailable": False,
        "error": "secure_storage_unavailable",
    }
