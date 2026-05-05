import json
from decimal import Decimal
from unittest.mock import patch

from core.deepseek import DeepSeekClient


class FakeStreamResponse:
    def __init__(self, events):
        self.events = events

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        assert decode_unicode is True
        for event in self.events:
            yield f"data: {json.dumps(event)}"
        yield "data: [DONE]"


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

    with patch("core.deepseek.requests.post", return_value=FakeStreamResponse(events)) as post:
        result = _client().stream_chat_completion(
            [{"role": "user", "content": "hi"}],
            on_token=tokens.append,
        )

    assert result.content == "Hello"
    assert tokens == ["Hel", "lo"]
    assert result.usage["total_tokens"] == 5
    assert post.call_args.kwargs["stream"] is True
    assert post.call_args.kwargs["json"]["stream_options"] == {"include_usage": True}


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
                            {"index": 0, "function": {"arguments": " -la\"}"}}
                        ]
                    }
                }
            ]
        },
    ]

    with patch("core.deepseek.requests.post", return_value=FakeStreamResponse(events)):
        result = _client().stream_chat_completion([{"role": "user", "content": "list"}])

    assert result.tool_calls == [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "bash", "arguments": "{\"command\":\"ls -la\"}"},
        }
    ]
