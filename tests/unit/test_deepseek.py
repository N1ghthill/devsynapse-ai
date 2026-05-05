import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from core.deepseek import DeepSeekClient


class FakeStreamResponse:
    def __init__(self, events):
        self.events = events
        self.status_code = 200

    def raise_for_status(self):
        return None

    def iter_lines(self):
        for event in self.events:
            yield f"data: {json.dumps(event)}"
        yield "data: [DONE]"

    def close(self):
        pass


class FakeNonStreamResponse:
    def __init__(self, json_data):
        self._json_data = json_data
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_data


def _client() -> DeepSeekClient:
    return DeepSeekClient(
        api_key="key",
        model="deepseek-chat",
        base_url="https://example.test",
        reasoning_effort="high",
        thinking_enabled=True,
        temperature=0.7,
        max_tokens=100,
        request_timeout=5,
        flash_pricing={
            "cache_hit": Decimal("0.1"),
            "cache_miss": Decimal("0.2"),
            "output": Decimal("0.3"),
        },
    )


def test_stream_chat_completion_accumulates_content_and_usage():
    events = [
        {"model": "deepseek-chat", "choices": [{"delta": {"content": "Hel"}}]},
        {"model": "deepseek-chat", "choices": [{"delta": {"content": "lo"}}]},
        {
            "model": "deepseek-chat",
            "choices": [],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        },
    ]
    tokens = []

    fake_client = MagicMock()
    fake_client.post.return_value = FakeStreamResponse(events)

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = _client().stream_chat_completion(
            [{"role": "user", "content": "hi"}],
            on_token=tokens.append,
        )

    assert result.content == "Hello"
    assert tokens == ["Hel", "lo"]
    assert result.usage["total_tokens"] == 5
    call_kwargs = fake_client.post.call_args.kwargs
    assert call_kwargs["json"]["stream"] is True
    assert call_kwargs["json"]["stream_options"] == {"include_usage": True}


def test_stream_chat_completion_accumulates_tool_call_deltas():
    events = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-1",
                                "type": "function",
                                "function": {"name": "bash", "arguments": "{\"command\":\"ls"},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": "\"}"},
                            }
                        ]
                    }
                }
            ]
        },
    ]

    fake_client = MagicMock()
    fake_client.post.return_value = FakeStreamResponse(events)

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = _client().stream_chat_completion(
            [{"role": "user", "content": "run ls"}],
        )

    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["function"]["name"] == "bash"
    assert result.tool_calls[0]["function"]["arguments"] == '{"command":"ls"}'


def test_chat_completion_requires_deepseek_api_key():
    client = _client()
    client.api_key = None

    with pytest.raises(RuntimeError, match="LLM provider not configured: deepseek"):
        client.chat_completion([{"role": "user", "content": "hi"}])


def test_chat_completion_returns_content_and_usage():
    response_data = {
        "model": "deepseek-chat",
        "choices": [
            {
                "message": {
                    "content": "Hello, world!",
                    "reasoning_content": "thinking...",
                }
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }

    fake_client = MagicMock()
    fake_client.post.return_value = FakeNonStreamResponse(response_data)

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = _client().chat_completion([{"role": "user", "content": "hi"}])

    assert result.content == "Hello, world!"
    assert result.model == "deepseek-chat"
    assert result.provider == "deepseek"
    assert result.usage["total_tokens"] == 15
    assert result.reasoning_content == "thinking..."


def test_chat_completion_returns_tool_calls():
    response_data = {
        "model": "deepseek-chat",
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "bash", "arguments": "{\"command\":\"ls\"}"},
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    }

    fake_client = MagicMock()
    fake_client.post.return_value = FakeNonStreamResponse(response_data)

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = _client().chat_completion(
            [{"role": "user", "content": "list files"}],
            tools=[{"type": "function", "function": {"name": "bash"}}],
        )

    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["function"]["name"] == "bash"


def test_stream_chat_completion_with_thinking_mode():
    events = [
        {"choices": [{"delta": {"reasoning_content": "thinking..."}}]},
        {"choices": [{"delta": {"content": "answer"}}]},
    ]

    fake_client = MagicMock()
    fake_client.post.return_value = FakeStreamResponse(events)

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = _client().stream_chat_completion(
            [{"role": "user", "content": "hi"}],
        )

    assert result.reasoning_content == "thinking..."
    assert result.content == "answer"


def test_chat_completion_with_openrouter_provider():
    response_data = {
        "model": "anthropic/claude-2",
        "choices": [{"message": {"content": "Hello from OpenRouter"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    }

    fake_client = MagicMock()
    fake_client.post.return_value = FakeNonStreamResponse(response_data)

    client = _client()
    client.provider_configs = {
        "openrouter": {
            "base_url": "https://openrouter.test",
            "api_key": "or-key",
        }
    }
    client.model = "openrouter:anthropic/claude-2"

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = client.chat_completion([{"role": "user", "content": "hi"}])

    assert result.content == "Hello from OpenRouter"
    assert result.provider == "openrouter"
    assert result.model == "anthropic/claude-2"


def test_retry_on_500_status_code():
    """Verify that 500 errors trigger retry logic."""
    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            resp = MagicMock()
            resp.status_code = 500
            resp.close = MagicMock()
            return resp
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "model": "deepseek-chat",
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        return resp

    fake_client = MagicMock()
    fake_client.post.side_effect = mock_post

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = _client().chat_completion([{"role": "user", "content": "hi"}])

    assert call_count == 3
    assert result.content == "ok"


def test_retry_on_connection_error():
    """Verify that connection errors trigger retry logic."""
    import httpx

    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.ConnectError("connection failed")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "model": "deepseek-chat",
            "choices": [{"message": {"content": "recovered"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        return resp

    fake_client = MagicMock()
    fake_client.post.side_effect = mock_post

    with patch("core.deepseek.httpx.Client", return_value=fake_client):
        result = _client().chat_completion([{"role": "user", "content": "hi"}])

    assert call_count == 2
    assert result.content == "recovered"
