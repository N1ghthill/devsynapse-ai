"""Tests for core/tool_repair.py."""

from core.deepseek import LLMResult
from core.tool_repair import coerce_llm_result, sanitize_unconfirmed_execution_claims


class TestCoerceLLMResult:
    def test_llm_result_passthrough(self):
        original = LLMResult(content="hello", tool_calls=[{"id": "1"}])
        result = coerce_llm_result(original)
        assert result is original
        assert result.content == "hello"

    def test_string_to_llm_result(self):
        result = coerce_llm_result("plain text response")
        assert isinstance(result, LLMResult)
        assert result.content == "plain text response"
        assert result.tool_calls is None

    def test_empty_string_to_llm_result(self):
        result = coerce_llm_result("")
        assert isinstance(result, LLMResult)
        assert result.content == ""


class TestSanitizeUnconfirmedExecutionClaims:
    def test_command_present_skips_sanitization(self):
        text = "I created the file and it's done!"
        result = sanitize_unconfirmed_execution_claims(text, 'write "file.py"')
        assert result == text

    def test_shell_like_claim_sanitized(self):
        text = "I ran the command:\n  echo hello > file.txt\n  Done!"
        result = sanitize_unconfirmed_execution_claims(text, None)
        assert "haven't executed" in result
        assert "single executable command" in result

    def test_success_claim_sanitized(self):
        text = "I completed the task and file created successfully."
        result = sanitize_unconfirmed_execution_claims(text, None)
        assert "haven't executed" in result

    def test_normal_text_passthrough(self):
        text = "I can help you with that. Let me analyze the code structure."
        result = sanitize_unconfirmed_execution_claims(text, None)
        assert result == text

    def test_empty_text_passthrough(self):
        result = sanitize_unconfirmed_execution_claims("", None)
        assert result == ""

    def test_mkdir_redirect_sanitized(self):
        text = "mkdir project && cd project\n  Finished!"
        result = sanitize_unconfirmed_execution_claims(text, None)
        assert "haven't executed" in result

    def test_ready_created_sanitized(self):
        text = "Ready! Created the configuration file."
        result = sanitize_unconfirmed_execution_claims(text, None)
        assert "haven't executed" in result
