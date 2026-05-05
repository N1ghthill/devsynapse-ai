"""Tests for devsynapse.cli entry point."""
from __future__ import annotations

from unittest.mock import patch

import pytest


class TestCliMain:
    def test_no_args_runs_tui(self):
        with patch("devsynapse.tui.run_tui") as mock_run_tui:
            from devsynapse import cli
            result = cli.main([])
            assert result == 0
            mock_run_tui.assert_called_once()

    def test_help_does_not_run_tui(self, capsys):
        from devsynapse import cli
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "terminal UI" in captured.out

    def test_rejects_unknown_command(self, capsys):
        from devsynapse import cli
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["ask"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "opens the TUI directly" in captured.err
        assert "/connect deepseek" in captured.err

    @pytest.mark.parametrize(
        "command",
        ["chat", "connect", "providers", "status", "usage", "budget", "router", "models", "shell", "tui"],
    )
    def test_rejects_all_external_subcommands(self, command, capsys):
        from devsynapse import cli
        with pytest.raises(SystemExit) as exc_info:
            cli.main([command])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "opens the TUI directly" in captured.err

    def test_rejects_command_with_args(self, capsys):
        from devsynapse import cli
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["connect", "deepseek", "my-key"])
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()

    def test_main_with_argv_none_uses_sys_argv(self):
        with patch("devsynapse.tui.run_tui") as mock_run_tui:
            with patch("sys.argv", ["devsynapse"]):
                from devsynapse import cli
                result = cli.main(None)
                assert result == 0
                mock_run_tui.assert_called_once()

    def test_main_with_custom_argv(self):
        with patch("devsynapse.tui.run_tui"):
            from devsynapse import cli
            result = cli.main([])
            assert result == 0
