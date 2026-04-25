"""
Tests for the local development process launcher.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from scripts import dev


def test_stop_processes_terminates_child_process_group(tmp_path: Path) -> None:
    child_pid_file = tmp_path / "child.pid"
    process = subprocess.Popen(
        ["bash", "-c", f"sleep 60 & echo $! > {child_pid_file}; wait"],
        start_new_session=True,
    )

    deadline = time.monotonic() + 5
    while not child_pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)

    assert child_pid_file.exists()
    child_pid = int(child_pid_file.read_text(encoding="utf-8").strip())

    try:
        dev.stop_processes([process])
        process.wait(timeout=5)
        time.sleep(0.1)
        assert process.poll() is not None
        assert not Path(f"/proc/{child_pid}").exists()
    finally:
        if process.poll() is None:
            process.kill()
        if Path(f"/proc/{child_pid}").exists():
            try:
                os.kill(child_pid, 9)
            except ProcessLookupError:
                pass


def test_format_admin_password_for_display_hides_custom_password() -> None:
    assert dev.format_admin_password_for_display("admin") == "admin"
    assert (
        dev.format_admin_password_for_display("custom-secret")
        == "value from DEFAULT_ADMIN_PASSWORD in .env"
    )
