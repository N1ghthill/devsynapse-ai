"""Tests for core.tool_validation."""
from __future__ import annotations

from core.tool_validation import validate_tool_calls


class TestValidateToolCalls:
    def test_none_tool_calls_invalid(self):
        valid, reason = validate_tool_calls(None)
        assert not valid
        assert "No tool calls" in reason

    def test_empty_list_invalid(self):
        valid, reason = validate_tool_calls([])
        assert not valid
        assert "No tool calls" in reason

    def test_valid_bash_call(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": '{"command": "ls -la"}',
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert valid
        assert reason == "OK"

    def test_valid_read_call(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "read",
                    "arguments": '{"path": "/tmp/test.py"}',
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert valid

    def test_valid_write_call(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "write",
                    "arguments": '{"path": "/tmp/test.py", "content": "hello"}',
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert valid

    def test_valid_edit_call(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "edit",
                    "arguments": '{"path": "/tmp/test.py", "old": "a", "new": "b"}',
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert valid

    def test_unknown_tool_name_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "unknown_tool",
                    "arguments": "{}",
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "unknown tool" in reason

    def test_missing_function_name_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "arguments": "{}",
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "missing function name" in reason

    def test_missing_function_object_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "missing function object" in reason

    def test_invalid_json_arguments_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": "{invalid json",
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "invalid JSON" in reason

    def test_missing_required_argument_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": "{}",
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "missing required argument" in reason

    def test_empty_bash_command_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": '{"command": ""}',
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "empty bash command" in reason

    def test_empty_file_path_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "write",
                    "arguments": '{"path": "", "content": "hello"}',
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "empty file path" in reason

    def test_too_many_tool_calls_invalid(self):
        tool_calls = [
            {
                "id": f"call-{i}",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": '{"command": "ls"}',
                },
            }
            for i in range(6)
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "Too many tool calls" in reason

    def test_argument_too_long_invalid(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": '{"command": "' + "x" * 60000 + '"}',
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "too long" in reason

    def test_dict_arguments_accepted(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": {"command": "ls -la"},
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert valid

    def test_arguments_must_be_object(self):
        tool_calls = [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": "[]",
                },
            }
        ]
        valid, reason = validate_tool_calls(tool_calls)
        assert not valid
        assert "must be a JSON object" in reason
