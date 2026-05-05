"""Tests for core.json_logger."""
from __future__ import annotations

import json
import logging
import os
from unittest.mock import patch

from core.json_logger import JsonFormatter, setup_structured_logging


class TestJsonFormatter:
    def test_formats_basic_record(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["message"] == "hello world"
        assert parsed["module"] == "test"
        assert parsed["function"] is None
        assert parsed["line"] == 10
        assert "timestamp" in parsed

    def test_formats_exception(self):
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = True
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="something failed",
                args=(),
                exc_info=exc_info,
            )
            result = formatter.format(record)
            parsed = json.loads(result)

            assert parsed["level"] == "ERROR"
            assert "exception" in parsed
            assert parsed["exception"]["type"] == "ValueError"
            assert parsed["exception"]["message"] == "test error"
            assert isinstance(parsed["exception"]["traceback"], list)

    def test_includes_extra_data(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="with data",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"user": "admin", "action": "login"}
        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["data"] == {"user": "admin", "action": "login"}


class TestSetupStructuredLogging:
    def test_does_not_activate_without_env_var(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEVSYNAPSE_JSON_LOGS", None)
            root = logging.getLogger()
            old_handlers = root.handlers[:]

            setup_structured_logging()

            assert root.handlers == old_handlers

    def test_activates_with_env_var(self):
        with patch.dict(os.environ, {"DEVSYNAPSE_JSON_LOGS": "1"}):
            root = logging.getLogger()
            setup_structured_logging()

            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0].formatter, JsonFormatter)

            for handler in root.handlers[:]:
                root.removeHandler(handler)
