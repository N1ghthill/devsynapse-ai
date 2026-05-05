"""Structured JSON logging formatter for DevSynapse AI."""
from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for structured log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        exc_info = record.exc_info
        if exc_info is True:
            exc_info = sys.exc_info()

        if exc_info and exc_info[0] is not None:
            log_entry["exception"] = {
                "type": exc_info[0].__name__,
                "message": str(exc_info[1]),
                "traceback": traceback.format_exception(*exc_info),
            }

        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        return json.dumps(log_entry, default=str)


def setup_structured_logging(level: str = "INFO") -> None:
    """Configure root logger to use JSON formatting.

    Only activates if DEVSYNAPSE_JSON_LOGS=1 is set in the environment.
    """
    import os

    if os.getenv("DEVSYNAPSE_JSON_LOGS") != "1":
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    for existing in root.handlers[:]:
        root.removeHandler(existing)

    root.addHandler(handler)
