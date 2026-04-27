"""
Unit tests for FastAPI application helpers.
"""

from __future__ import annotations

import asyncio
import logging

from starlette.background import BackgroundTasks
from starlette.responses import Response

from api.app import (
    _api_host_is_loopback,
    _attach_api_request_log,
    _cors_allow_credentials,
    _warn_if_api_host_is_exposed,
)
from config.settings import AppSettings


class _MonitoringRecorder:
    def __init__(self) -> None:
        self.requests = []

    def log_api_request(self, **kwargs) -> None:
        self.requests.append(kwargs)


def test_api_request_log_is_attached_to_response_background() -> None:
    recorder = _MonitoringRecorder()
    response = Response("ok")

    _attach_api_request_log(
        response,
        recorder,
        endpoint="/api",
        method="GET",
        status_code=200,
        response_time=0.01,
        user_id=None,
        ip_address="127.0.0.1",
    )

    assert response.background is not None
    asyncio.run(response.background())

    assert recorder.requests == [
        {
            "endpoint": "/api",
            "method": "GET",
            "status_code": 200,
            "response_time": 0.01,
            "user_id": None,
            "ip_address": "127.0.0.1",
        }
    ]


def test_api_request_log_preserves_existing_background_tasks() -> None:
    recorder = _MonitoringRecorder()
    completed = []

    async def mark_existing(value: str) -> None:
        completed.append(value)

    response = Response("ok")
    existing_background = BackgroundTasks()
    existing_background.add_task(mark_existing, "existing")
    response.background = existing_background

    _attach_api_request_log(
        response,
        recorder,
        endpoint="/health",
        method="GET",
        status_code=200,
        response_time=0.02,
        user_id=None,
        ip_address=None,
    )

    asyncio.run(response.background())

    assert completed == ["existing"]
    assert recorder.requests[0]["endpoint"] == "/health"


def test_cors_disables_credentials_for_wildcard_origins() -> None:
    assert _cors_allow_credentials(["*"]) is False
    assert _cors_allow_credentials(["https://devsynapse.example.com"]) is True


def test_default_cors_origins_are_localhost_only() -> None:
    assert AppSettings.model_fields["cors_allowed_origins"].default == (
        "http://127.0.0.1:5173,http://localhost:5173"
    )


def test_settings_parse_comma_separated_cors_origins() -> None:
    settings = AppSettings(
        cors_allowed_origins="https://app.example.com,http://127.0.0.1:5173"
    )

    assert settings.get_cors_allowed_origins() == [
        "https://app.example.com",
        "http://127.0.0.1:5173",
    ]


def test_api_host_loopback_detection() -> None:
    assert _api_host_is_loopback("127.0.0.1") is True
    assert _api_host_is_loopback("localhost") is True
    assert _api_host_is_loopback("::1") is True
    assert _api_host_is_loopback("0.0.0.0") is False
    assert _api_host_is_loopback("192.168.1.10") is False


def test_non_loopback_api_host_logs_local_first_warning(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="api.app")

    _warn_if_api_host_is_exposed("0.0.0.0")

    assert "local-first app can execute commands" in caplog.text
