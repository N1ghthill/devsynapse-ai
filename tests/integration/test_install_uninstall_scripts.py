"""
Smoke tests for install/uninstall shell scripts without network or real dependency installs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _create_script_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"

    (repo / "scripts").mkdir(parents=True)
    fake_bin.mkdir()
    home.mkdir()

    shutil.copy2(REPO_ROOT / "scripts" / "install.sh", repo / "scripts" / "install.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "uninstall.sh", repo / "scripts" / "uninstall.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "update.sh", repo / "scripts" / "update.sh")
    shutil.copy2(REPO_ROOT / ".env.example", repo / ".env.example")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "devsynapse-ai"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo / "devsynapse.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (repo / "devsynapse.sh").chmod(0o755)
    (repo / "config").mkdir()
    (repo / "config" / "settings.py").write_text(
        'class AppSettings:\n    app_version: str = "0.3.4"\n',
        encoding="utf-8",
    )
    (repo / "requirements.txt").write_text("textual>=8\n", encoding="utf-8")

    _write_executable(
        fake_bin / "python3",
        """
#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "-m" ] && [ "${2:-}" = "venv" ]; then
    if [ "${3:-}" = "--help" ]; then
        exit 0
    fi

    venv_dir="$3"
    mkdir -p "$venv_dir/bin"
    cat > "$venv_dir/bin/activate" <<ACTIVATE
export VIRTUAL_ENV="$venv_dir"
export PATH="\\$VIRTUAL_ENV/bin:\\$PATH"
ACTIVATE

    cat > "$venv_dir/bin/pip" <<'PIP'
#!/usr/bin/env bash
set -euo pipefail
echo "fake pip install complete"
PIP
    chmod +x "$venv_dir/bin/pip"

    cat > "$venv_dir/bin/python3" <<'PYTHON'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == *"migrate.py" ]]; then
    config_file="${DEVSYNAPSE_CONFIG_FILE:-}"
    memory_db="$(awk -F= '$1 == "MEMORY_DB_PATH" {sub("^[^=]*=", ""); print; exit}' "$config_file")"
    log_file="$(awk -F= '$1 == "LOG_FILE" {sub("^[^=]*=", ""); print; exit}' "$config_file")"
    mkdir -p "$(dirname "$memory_db")" "$(dirname "$log_file")"
    touch "$memory_db" "$log_file"
    echo "memory: applied 8 migration(s)"
else
    echo "fake python"
fi
PYTHON
    chmod +x "$venv_dir/bin/python3"
    exit 0
fi

echo "fake python"
""",
    )

    return repo, fake_bin, home


def _run_script(
    repo: Path,
    fake_bin: Path,
    home: Path,
    script: str,
    stdin: str,
    script_args: list[str] | None = None,
    interactive: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")
    env["XDG_STATE_HOME"] = str(home / ".local" / "state")
    for key in list(env):
        if key.startswith("DEVSYNAPSE_"):
            env.pop(key)
    if interactive:
        env["DEVSYNAPSE_INTERACTIVE"] = "1"
    return subprocess.run(
        ["bash", script, *(script_args or [])],
        cwd=repo,
        input=stdin,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
        check=False,
    )


def test_install_script_writes_env_and_command_wrappers_portably(tmp_path: Path) -> None:
    repo, fake_bin, home = _create_script_repo(tmp_path)
    repos_root = tmp_path / "repos&root"
    repos_root.mkdir()
    config_file = home / ".config" / "devsynapse-ai" / ".env"
    data_dir = home / ".local" / "share" / "devsynapse-ai" / "data"
    logs_dir = home / ".local" / "state" / "devsynapse-ai" / "logs"
    bin_dir = home / ".local" / "bin"

    first = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"sk-test&ci\n{repos_root}\n",
    )
    assert first.returncode == 0, first.stdout + first.stderr

    second = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"sk-test&ci-updated\n{repos_root}\n",
    )
    assert second.returncode == 0, second.stdout + second.stderr

    env_text = config_file.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-test&ci-updated" in env_text
    assert f"DEV_REPOS_ROOT={repos_root}" in env_text
    assert f"DEV_WORKSPACE_ROOT={home}" in env_text
    assert f"MEMORY_DB_PATH={data_dir / 'devsynapse_memory.db'}" in env_text
    assert f"LOG_FILE={logs_dir / 'devsynapse.log'}" in env_text

    assert (repo / "venv").is_dir()
    assert (data_dir / "devsynapse_memory.db").is_file()

    for command in ("devsynapse", "update-devsynapse", "uninstall-devsynapse"):
        command_path = bin_dir / command
        assert command_path.is_file()
        assert os.access(command_path, os.X_OK)

    assert "devsynapse.sh" in (bin_dir / "devsynapse").read_text(encoding="utf-8")
    assert "scripts/update.sh" in (bin_dir / "update-devsynapse").read_text(encoding="utf-8")
    assert "scripts/uninstall.sh" in (bin_dir / "uninstall-devsynapse").read_text(
        encoding="utf-8"
    )

    for rc_file in (home / ".bashrc", home / ".zshrc"):
        rc_text = rc_file.read_text(encoding="utf-8")
        assert "alias devsynapse=" not in rc_text
        assert "alias update-devsynapse=" not in rc_text
        assert "alias uninstall-devsynapse=" not in rc_text
        assert str(bin_dir) in rc_text
        assert rc_text.count("devsynapse path (managed by scripts/install.sh)") == 1


def test_install_script_preserves_existing_api_key_on_blank_input(tmp_path: Path) -> None:
    repo, fake_bin, home = _create_script_repo(tmp_path)
    repos_root = tmp_path / "repos"
    repos_root.mkdir()
    config_file = home / ".config" / "devsynapse-ai" / ".env"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("DEEPSEEK_API_KEY=sk-existing\n", encoding="utf-8")

    installed = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"\n{repos_root}\n",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    env_text = config_file.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-existing" in env_text
    assert "API key kept" in installed.stdout
    assert "No API key configured" not in installed.stdout


def test_install_script_uses_defaults_when_stdin_is_not_interactive(tmp_path: Path) -> None:
    repo, fake_bin, home = _create_script_repo(tmp_path)
    config_file = home / ".config" / "devsynapse-ai" / ".env"
    data_dir = home / ".local" / "share" / "devsynapse-ai" / "data"

    installed = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        "source ~/.bashrc\ndevsynapse\n",
        interactive=False,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    env_text = config_file.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=source ~/.bashrc" not in env_text
    assert f"DEV_REPOS_ROOT={home / 'repos'}" in env_text
    assert (data_dir / "devsynapse_memory.db").is_file()
    assert "No API key configured" in installed.stdout


def test_uninstall_script_removes_artifacts_and_respects_data_choices(tmp_path: Path) -> None:
    repo, fake_bin, home = _create_script_repo(tmp_path)
    repos_root = tmp_path / "repos"
    repos_root.mkdir()
    config_file = home / ".config" / "devsynapse-ai" / ".env"
    data_dir = home / ".local" / "share" / "devsynapse-ai" / "data"
    logs_dir = home / ".local" / "state" / "devsynapse-ai" / "logs"
    bin_dir = home / ".local" / "bin"

    installed = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"sk-test\n{repos_root}\n",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    keep_data = _run_script(repo, fake_bin, home, "scripts/uninstall.sh", "n\nn\n")
    assert keep_data.returncode == 0, keep_data.stdout + keep_data.stderr
    assert not (repo / "venv").exists()
    assert not (bin_dir / "devsynapse").exists()
    assert not (bin_dir / "update-devsynapse").exists()
    assert not (bin_dir / "uninstall-devsynapse").exists()
    assert data_dir.is_dir()
    assert logs_dir.is_dir()
    assert config_file.is_file()

    for rc_file in (home / ".bashrc", home / ".zshrc"):
        rc_text = rc_file.read_text(encoding="utf-8")
        assert "alias devsynapse=" not in rc_text
        assert "alias update-devsynapse=" not in rc_text
        assert "alias uninstall-devsynapse=" not in rc_text
        assert "devsynapse path" not in rc_text

    delete_data = _run_script(repo, fake_bin, home, "scripts/uninstall.sh", "s\ns\n")
    assert delete_data.returncode == 0, delete_data.stdout + delete_data.stderr
    assert not data_dir.exists()
    assert not logs_dir.exists()
    assert not config_file.exists()


def test_update_script_refreshes_existing_install_without_prompts(tmp_path: Path) -> None:
    repo, fake_bin, home = _create_script_repo(tmp_path)
    repos_root = tmp_path / "repos"
    repos_root.mkdir()
    config_file = home / ".config" / "devsynapse-ai" / ".env"
    data_dir = home / ".local" / "share" / "devsynapse-ai" / "data"
    bin_dir = home / ".local" / "bin"

    installed = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"sk-update-test\n{repos_root}\n",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    updated = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/update.sh",
        "",
        script_args=["--skip-git"],
    )
    assert updated.returncode == 0, updated.stdout + updated.stderr

    env_text = config_file.read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-update-test" in env_text
    assert "Update complete" in updated.stdout
    assert (bin_dir / "devsynapse").is_file()
    assert (bin_dir / "update-devsynapse").is_file()
    assert any((data_dir / "backups").glob("update-*"))
