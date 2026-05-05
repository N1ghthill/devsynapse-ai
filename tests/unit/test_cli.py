"""Unit tests for the terminal UI entry point."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _cli_env(runtime_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DEVSYNAPSE_HOME": str(runtime_root),
            "DEVSYNAPSE_CONFIG_FILE": str(runtime_root / "config" / ".env"),
            "DEVSYNAPSE_DATA_DIR": str(runtime_root / "data"),
            "DEVSYNAPSE_LOGS_DIR": str(runtime_root / "logs"),
            "DEEPSEEK_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "OPENCODE_ZEN_API_KEY": "",
            "OPENCODE_GO_API_KEY": "",
        }
    )
    return env


def test_tui_launcher_help_does_not_require_writable_runtime_config(tmp_path):
    runtime_root = tmp_path / "runtime"
    config_dir = runtime_root / "config"
    config_dir.mkdir(parents=True)
    config_file = config_dir / ".env"
    config_file.write_text("DEEPSEEK_API_KEY=\n", encoding="utf-8")
    config_file.chmod(stat.S_IRUSR)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "devsynapse.cli", "--help"],
            cwd=PROJECT_ROOT,
            env=_cli_env(runtime_root),
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        config_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    assert result.returncode == 0
    assert "terminal UI" in result.stdout
    assert "/connect" in result.stdout
    assert "providers" not in result.stdout.split("usage:", 1)[1].splitlines()[0]


def test_tui_launcher_version_does_not_create_runtime_state(tmp_path):
    runtime_root = tmp_path / "runtime"

    result = subprocess.run(
        [sys.executable, "-m", "devsynapse.cli", "--version"],
        cwd=PROJECT_ROOT,
        env=_cli_env(runtime_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("devsynapse ")
    assert not (runtime_root / "data" / "devsynapse_memory.db").exists()


@pytest.mark.parametrize(
    "command",
    [
        "ask",
        "chat",
        "connect",
        "providers",
        "status",
        "usage",
        "budget",
        "router",
        "models",
        "shell",
        "tui",
    ],
)
def test_tui_launcher_rejects_external_subcommands(tmp_path, command):
    runtime_root = tmp_path / "runtime"

    result = subprocess.run(
        [sys.executable, "-m", "devsynapse.cli", command],
        cwd=PROJECT_ROOT,
        env=_cli_env(runtime_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "opens the TUI directly" in result.stderr
    assert "/connect deepseek" in result.stderr
    assert not (runtime_root / "data" / "devsynapse_memory.db").exists()
