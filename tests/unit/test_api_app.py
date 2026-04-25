"""
Unit tests for FastAPI application helpers.
"""

from __future__ import annotations

import asyncio

from starlette.background import BackgroundTasks
from starlette.responses import Response

from api.app import _attach_api_request_log, _cors_allow_credentials
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
    response = Response("ok")
    existing_background = BackgroundTasks()
    existing_background.add_task(completed.append, "existing")
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


def test_settings_parse_comma_separated_cors_origins() -> None:
    settings = AppSettings(
        cors_allowed_origins="https://app.example.com,http://127.0.0.1:5173"
    )

    assert settings.get_cors_allowed_origins() == [
        "https://app.example.com",
        "http://127.0.0.1:5173",
    ]
