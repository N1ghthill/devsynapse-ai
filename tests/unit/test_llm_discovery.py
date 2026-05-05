"""Tests for core.llm_discovery."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.llm_discovery import (
    _float_or_none,
    _normalize_openai_compatible_model,
    _normalize_openrouter_model,
    fetch_openai_compatible_models,
    fetch_openrouter_models,
)


class TestFloatOrNone:
    def test_valid_float(self):
        assert _float_or_none("1.5") == 1.5
        assert _float_or_none(2.0) == 2.0
        assert _float_or_none(0) == 0.0

    def test_none_returns_none(self):
        assert _float_or_none(None) is None

    def test_empty_string_returns_none(self):
        assert _float_or_none("") is None

    def test_invalid_string_returns_none(self):
        assert _float_or_none("not_a_number") is None


class TestNormalizeOpenrouterModel:
    def test_basic_normalization(self):
        raw = {
            "id": "openai/gpt-4",
            "name": "GPT-4",
            "context_length": 8192,
            "pricing": {"prompt": "0.00003", "completion": "0.00006"},
            "architecture": {"modality": "text+image->text"},
            "top_provider": {"is_moderated": False},
            "supported_parameters": ["tools", "tool_choice"],
        }
        result = _normalize_openrouter_model(raw, "https://openrouter.ai/api/v1/models")
        assert result["provider"] == "openrouter"
        assert result["model_id"] == "openai/gpt-4"
        assert result["name"] == "GPT-4"
        assert result["context_length"] == 8192
        assert result["input_cost_per_token"] == 0.00003
        assert result["output_cost_per_token"] == 0.00006
        assert "tools" in result["capabilities"]["supported_parameters"]

    def test_fallback_to_slug_when_no_id(self):
        raw = {"slug": "meta/llama-3"}
        result = _normalize_openrouter_model(raw, "https://example.com")
        assert result["model_id"] == "meta/llama-3"

    def test_fallback_name_to_id(self):
        raw = {"id": "some/model"}
        result = _normalize_openrouter_model(raw, "https://example.com")
        assert result["name"] == "some/model"

    def test_missing_pricing_returns_none_costs(self):
        raw = {"id": "test/model"}
        result = _normalize_openrouter_model(raw, "https://example.com")
        assert result["input_cost_per_token"] is None
        assert result["output_cost_per_token"] is None

    def test_cache_read_cost(self):
        raw = {
            "id": "test/model",
            "pricing": {"input_cache_read": "0.00001"},
        }
        result = _normalize_openrouter_model(raw, "https://example.com")
        assert result["cache_read_cost_per_token"] == 0.00001

    def test_source_url_preserved(self):
        raw = {"id": "test/model"}
        result = _normalize_openrouter_model(raw, "https://example.com/models")
        assert result["source_url"] == "https://example.com/models"


class TestNormalizeOpenaiCompatibleModel:
    def test_basic_normalization(self):
        raw = {
            "id": "gpt-3.5-turbo",
            "name": "GPT-3.5 Turbo",
            "owned_by": "openai",
            "object": "model",
        }
        result = _normalize_openai_compatible_model(
            raw, "opencode-go", "https://example.com/models"
        )
        assert result["provider"] == "opencode-go"
        assert result["model_id"] == "gpt-3.5-turbo"
        assert result["name"] == "GPT-3.5 Turbo"
        assert result["capabilities"]["owned_by"] == "openai"

    def test_fallback_to_model_field(self):
        raw = {"model": "fallback-model"}
        result = _normalize_openai_compatible_model(raw, "test", "https://example.com")
        assert result["model_id"] == "fallback-model"

    def test_fallback_to_name_field(self):
        raw = {"name": "name-only-model"}
        result = _normalize_openai_compatible_model(raw, "test", "https://example.com")
        assert result["model_id"] == "name-only-model"

    def test_context_length_variants(self):
        raw = {"id": "test", "contextLength": 4096}
        result = _normalize_openai_compatible_model(raw, "test", "https://example.com")
        assert result["context_length"] == 4096

        raw2 = {"id": "test2", "context_length": 8192}
        result2 = _normalize_openai_compatible_model(raw2, "test", "https://example.com")
        assert result2["context_length"] == 8192

    def test_pricing_from_nested_pricing_object(self):
        raw = {
            "id": "test",
            "pricing": {"prompt": "0.001", "completion": "0.002", "input_cache_read": "0.0005"},
        }
        result = _normalize_openai_compatible_model(raw, "test", "https://example.com")
        assert result["input_cost_per_token"] == 0.001
        assert result["output_cost_per_token"] == 0.002
        assert result["cache_read_cost_per_token"] == 0.0005

    def test_pricing_from_top_level_fields(self):
        raw = {
            "id": "test",
            "input_cost_per_token": 0.01,
            "output_cost_per_token": 0.02,
        }
        result = _normalize_openai_compatible_model(raw, "test", "https://example.com")
        assert result["input_cost_per_token"] == 0.01
        assert result["output_cost_per_token"] == 0.02


class TestFetchOpenrouterModels:
    def test_fetches_and_normalizes(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "openai/gpt-4",
                    "name": "GPT-4",
                    "context_length": 8192,
                    "pricing": {"prompt": "0.03", "completion": "0.06"},
                    "architecture": {},
                    "top_provider": {},
                    "supported_parameters": ["tools"],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openrouter_models("https://openrouter.ai/api/v1/models")

        assert len(models) == 1
        assert models[0]["model_id"] == "openai/gpt-4"

    def test_filters_items_without_model_id(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "valid-model"},
                {},  # no id
                {"id": ""},  # empty id
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openrouter_models("https://openrouter.ai/api/v1/models")

        assert len(models) == 1
        assert models[0]["model_id"] == "valid-model"

    def test_empty_data_returns_empty_list(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openrouter_models("https://openrouter.ai/api/v1/models")

        assert models == []

    def test_raises_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            with pytest.raises(Exception, match="404"):
                fetch_openrouter_models("https://openrouter.ai/api/v1/models")


class TestFetchOpenaiCompatibleModels:
    def test_fetches_and_normalizes(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5", "owned_by": "openai"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openai_compatible_models(
                "opencode-go",
                "https://example.com/models",
                "test-api-key",
            )

        assert len(models) == 1
        assert models[0]["model_id"] == "gpt-3.5-turbo"
        assert models[0]["provider"] == "opencode-go"

    def test_sends_auth_header_when_api_key_provided(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response) as mock_get:
            fetch_openai_compatible_models(
                "test-provider",
                "https://example.com/models",
                "secret-key",
            )
            call_headers = mock_get.call_args.kwargs.get("headers", {})
            assert call_headers["Authorization"] == "Bearer secret-key"

    def test_no_auth_header_when_api_key_missing(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response) as mock_get:
            fetch_openai_compatible_models(
                "test-provider",
                "https://example.com/models",
                None,
            )
            call_headers = mock_get.call_args.kwargs.get("headers", {})
            assert "Authorization" not in call_headers

    def test_handles_list_payload(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "model-1"},
            {"id": "model-2"},
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openai_compatible_models(
                "test", "https://example.com/models", None
            )

        assert len(models) == 2

    def test_returns_empty_for_non_list_non_dict_payload(self):
        mock_response = MagicMock()
        mock_response.json.return_value = "invalid"
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openai_compatible_models(
                "test", "https://example.com/models", None
            )

        assert models == []

    def test_filters_non_dict_items(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "valid"},
                "not_a_dict",
                123,
                None,
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openai_compatible_models(
                "test", "https://example.com/models", None
            )

        assert len(models) == 1
        assert models[0]["model_id"] == "valid"

    def test_filters_items_without_model_id(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "valid"},
                {},
                {"other_field": "no-id-field"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("core.llm_discovery.requests.get", return_value=mock_response):
            models = fetch_openai_compatible_models(
                "test", "https://example.com/models", None
            )

        assert len(models) == 1
