"""
Shared pytest configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ["DEVSYNAPSE_HOME"] = str(
    Path(os.getenv("PYTEST_RUNTIME_ROOT", "/tmp")) / f"devsynapse-ai-pytest-{os.getpid()}"
)


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Return a temporary database path for isolated tests."""
    return str(tmp_path / "test_memory.db")


@pytest.fixture
def mock_settings(tmp_path: Path):
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.memory_db_path = tmp_path / "test_memory.db"
    settings.dev_workspace_root = tmp_path / "workspace"
    settings.dev_repos_root = tmp_path / "repos"
    settings.default_execution_cwd = tmp_path / "workspace"
    settings.build_default_preferences.return_value = {
        "coding_style": "clean_simple",
        "cost_preference": "low_cost_first",
        "communication_style": "direct_conversational",
        "risk_tolerance": "medium",
        "detail_level": "balanced",
    }
    settings.build_known_projects.return_value = {}
    settings.build_allowed_directories.return_value = [str(tmp_path)]
    settings.build_allowed_file_extensions.return_value = [".py", ".js", ".ts"]
    settings.opencode_timeout = 30
    settings.opencode_max_output = 10000
    settings.opencode_max_file_size = 10 * 1024 * 1024
    settings.max_edit_size = 1 * 1024 * 1024
    settings.max_write_size = 5 * 1024 * 1024
    settings.opencode_backup_enabled = True
    settings.opencode_backup_suffix = ".devsynapse_backup"
    settings.deepseek_api_key = None
    settings.deepseek_model = "deepseek-v4-pro"
    settings.deepseek_base_url = "https://api.deepseek.com/beta"
    settings.llm_temperature = 0.7
    settings.llm_max_tokens = 1500
    settings.llm_request_timeout = 12
    settings.llm_streaming_enabled = False
    settings.llm_default_provider = "deepseek"
    settings.assistant_user_name = "the user"
    return settings


@pytest.fixture
def memory_system(tmp_db_path: str, mock_settings):
    """Create a MemorySystem with temporary database."""
    with patch("core.memory.system.get_settings", return_value=mock_settings):
        from core.memory.system import MemorySystem
        return MemorySystem()


@pytest.fixture
def mock_bridge(mock_settings):
    """Create a mocked OpenCodeBridge for testing."""
    from core.opencode_bridge import OpenCodeBridge
    with patch("core.opencode_bridge.get_settings", return_value=mock_settings):
        bridge = OpenCodeBridge(
            known_projects={},
            allowed_directories=[str(mock_settings.dev_workspace_root)],
        )
        return bridge


@pytest.fixture
def mock_deepseek_client():
    """Create a mocked DeepSeekClient for testing."""
    from core.deepseek import DeepSeekClient
    client = MagicMock(spec=DeepSeekClient)
    client.configured = False
    client.model = "deepseek-v4-pro"
    client.api_key = None
    client.provider_configs = {}
    return client


@pytest.fixture
def mock_plugin_manager():
    """Create a mocked PluginManager for testing."""
    from core.plugin_system import PluginManager
    manager = MagicMock(spec=PluginManager)
    manager.emit_event = MagicMock()
    manager.emit_event.return_value = MagicMock(cancelled=False, data={})
    return manager
