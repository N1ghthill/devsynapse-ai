"""Tests for core.correlation module."""

from datetime import datetime

from core.correlation import (
    generate_conversation_id,
    generate_request_id,
    generate_tool_run_id,
)


class TestGenerateConversationId:
    def test_format(self):
        cid = generate_conversation_id()
        assert cid.startswith("chat_")
        parts = cid.split("_")
        assert len(parts) == 3  # chat_YYYYMMDD_<6 hex chars>
        assert parts[0] == "chat"
        assert len(parts[2]) == 6  # 3 bytes = 6 hex chars

    def test_uses_provided_datetime(self):
        now = datetime(2024, 1, 15)
        cid = generate_conversation_id(now)
        assert "chat_20240115_" in cid

    def test_uses_current_datetime_when_none(self):
        cid = generate_conversation_id()
        today = datetime.now().strftime("%Y%m%d")
        assert f"chat_{today}_" in cid

    def test_uniqueness(self):
        ids = {generate_conversation_id() for _ in range(100)}
        assert len(ids) == 100


class TestGenerateRequestId:
    def test_format(self):
        rid = generate_request_id()
        assert rid.startswith("req_")
        assert len(rid) == 16  # req_ + 12 hex chars

    def test_uniqueness(self):
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100


class TestGenerateToolRunId:
    def test_format(self):
        tid = generate_tool_run_id()
        assert tid.startswith("tool_")
        assert len(tid) == 17  # tool_ + 12 hex chars

    def test_uniqueness(self):
        ids = {generate_tool_run_id() for _ in range(100)}
        assert len(ids) == 100
