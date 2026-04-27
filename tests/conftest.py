"""
Shared pytest configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ["DEVSYNAPSE_HOME"] = str(
    Path(os.getenv("PYTEST_RUNTIME_ROOT", "/tmp")) / f"devsynapse-ai-pytest-{os.getpid()}"
)
