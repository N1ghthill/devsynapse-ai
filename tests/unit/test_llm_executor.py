"""Tests for core/llm_executor.py."""

from unittest.mock import Mock

import pytest

from core.deepseek import LLMResult
from core.llm_executor import LLMExecutor


def _mock_settings(streaming=False):
    settings = Mock()
    settings.llm_streaming_enabled = streaming
    return settings


def _mock_deepseek(configured=True, model="gpt-4"):
    client = Mock()
    client.configured = configured
    client.model = model
    client.stream_chat_completion = Mock()
    client.chat_completion = Mock()
    return client


def _mock_usage_tracker():
    usage = Mock()
    usage.enrich_usage_cost = Mock(side_effect=lambda p, m, u: u)
    usage.record_llm_telemetry = Mock()
    return usage


def _executor(deepseek=None, usage=None, streaming=False):
    return LLMExecutor(
        deepseek_client=deepseek or _mock_deepseek(),
        usage_tracker=usage or _mock_usage_tracker(),
        get_settings=lambda: _mock_settings(streaming=streaming),
    )


class TestCallAPI:
    @pytest.mark.asyncio
    async def test_not_configured_returns_fallback(self):
        client = _mock_deepseek(configured=False)
        exec = _executor(deepseek=client)
        result = await exec.call_api([{"role": "user", "content": "hello"}])
        assert isinstance(result, LLMResult)
        assert len(result.content) > 0

    @pytest.mark.asyncio
    async def test_success_path(self):
        client = _mock_deepseek()
        client.chat_completion.return_value = LLMResult(
            content="response", provider="openai", model="gpt-4",
        )
        usage = _mock_usage_tracker()
        exec = _executor(deepseek=client, usage=usage, streaming=False)
        result = await exec.call_api([{"role": "user", "content": "hello"}])
        assert result.content == "response"
        client.chat_completion.assert_called_once()
        assert usage.record_llm_telemetry.called

    @pytest.mark.asyncio
    async def test_primary_fails_fallback_succeeds(self):
        client = _mock_deepseek()
        route = Mock()
        route.model = "gpt-4"
        route.fallback_model = "gpt-3.5"
        client.chat_completion.side_effect = [
            RuntimeError("primary failed"),
            LLMResult(content="fallback response", provider="openai", model="gpt-3.5"),
        ]
        exec = _executor(deepseek=client, streaming=False)
        result = await exec.call_api([{"role": "user", "content": "hello"}], route=route)
        assert result.content == "fallback response"
        assert client.chat_completion.call_count == 2

    @pytest.mark.asyncio
    async def test_both_fails_returns_fallback(self):
        client = _mock_deepseek()
        route = Mock()
        route.model = "gpt-4"
        route.fallback_model = "gpt-3.5"
        client.chat_completion.side_effect = [
            RuntimeError("primary failed"),
            RuntimeError("fallback also failed"),
        ]
        usage = _mock_usage_tracker()
        exec = _executor(deepseek=client, usage=usage, streaming=False)
        result = await exec.call_api([{"role": "user", "content": "hello"}], route=route)
        assert isinstance(result, LLMResult)
        assert usage.record_llm_telemetry.called
        call_kwargs = usage.record_llm_telemetry.call_args[1]
        assert call_kwargs["success"] is False


class TestCompleteAndRecord:
    @pytest.mark.asyncio
    async def test_streaming_mode(self):
        client = _mock_deepseek()
        client.stream_chat_completion.return_value = LLMResult(
            content="streamed", provider="openai", model="gpt-4",
        )
        usage = _mock_usage_tracker()
        exec = _executor(deepseek=client, usage=usage, streaming=True)
        result = await exec._complete_and_record(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4", tool_choice="auto", route=None,
            user_id="u1", conversation_id="c1", start_time=0.0,
        )
        assert result.content == "streamed"
        client.stream_chat_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_mode(self):
        client = _mock_deepseek()
        client.chat_completion.return_value = LLMResult(
            content="batched", provider="openai", model="gpt-4",
        )
        usage = _mock_usage_tracker()
        exec = _executor(deepseek=client, usage=usage, streaming=False)
        result = await exec._complete_and_record(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4", tool_choice="auto", route=None,
            user_id="u1", conversation_id="c1", start_time=0.0,
        )
        assert result.content == "batched"
        client.chat_completion.assert_called_once()
        assert result.usage["provider"] == "openai"
        assert result.usage["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_enriches_usage(self):
        client = _mock_deepseek()
        client.chat_completion.return_value = LLMResult(
            content="ok", provider="openai", model="gpt-4",
            usage={"prompt_tokens": 100},
        )
        usage = _mock_usage_tracker()
        usage.enrich_usage_cost = Mock(return_value={"prompt_tokens": 100, "estimated_cost_usd": 0.003})
        exec = _executor(deepseek=client, usage=usage, streaming=False)
        result = await exec._complete_and_record(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4", tool_choice="auto", route=None,
            user_id="u1", conversation_id="c1", start_time=0.0,
        )
        usage.enrich_usage_cost.assert_called_once()
        assert result.usage["estimated_cost_usd"] == 0.003


class TestGetFallbackResponse:
    def test_returns_string(self):
        response = LLMExecutor._get_fallback_response()
        assert isinstance(response, str)
        assert len(response) > 0

    def test_returns_one_of_known_responses(self):
        known = [
            "The selected LLM provider timed out",
            "The selected LLM provider is temporarily unavailable",
            "The active model is not responding",
        ]
        response = LLMExecutor._get_fallback_response()
        assert any(phrase in response for phrase in known)
        assert "DeepSeek" not in response

    def test_not_configured_response_is_provider_neutral(self):
        response = LLMExecutor._get_fallback_response("not_configured")
        assert "No LLM provider is configured" in response
        assert "DeepSeek" not in response
