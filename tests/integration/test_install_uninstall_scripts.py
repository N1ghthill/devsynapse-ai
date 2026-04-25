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
    (repo / "frontend").mkdir()
    fake_bin.mkdir()
    home.mkdir()

    shutil.copy2(REPO_ROOT / "scripts" / "install.sh", repo / "scripts" / "install.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "uninstall.sh", repo / "scripts" / "uninstall.sh")
    shutil.copy2(REPO_ROOT / ".env.example", repo / ".env.example")
    (repo / "requirements.txt").write_text("fastapi>=0\n", encoding="utf-8")

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
            mkdir -p data logs
            touch data/devsynapse_memory.db data/devsynapse_monitoring.db
            echo "memory: applied 8 migration(s)"
            echo "monitoring: applied 1 migration(s)"
        elif [[ "${1:-}" == *"manage_users.py" ]]; then
            echo "Default users ensured in SQLite."
        else
            echo "fake python3"
        fi
        PYTHON
            chmod +x "$venv_dir/bin/python3"
            exit 0
        fi

        echo "fake python3"
        """,
    )

    _write_executable(
        fake_bin / "npm",
        """
        #!/usr/bin/env bash
        set -euo pipefail

        if [ "${1:-}" = "install" ]; then
            mkdir -p node_modules
            echo "fake npm install complete"
        elif [ "${1:-}" = "run" ] && [ "${2:-}" = "build" ]; then
            mkdir -p dist
            echo "fake npm build complete"
        else
            echo "fake npm"
        fi
        """,
    )

    return repo, fake_bin, home


def _run_script(repo: Path, fake_bin: Path, home: Path, script: str, stdin: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", script],
        cwd=repo,
        input=stdin,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
        check=False,
    )


def test_install_script_writes_env_and_aliases_portably(tmp_path: Path) -> None:
    repo, fake_bin, home = _create_script_repo(tmp_path)
    repos_root = tmp_path / "repos&root"
    repos_root.mkdir()

    first = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"sk-test&ci\n{repos_root}\nfirst-pass\nfirst-pass\n",
    )
    assert first.returncode == 0, first.stdout + first.stderr

    second = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"sk-test&ci-updated\n{repos_root}\nsecond-pass\nsecond-pass\n",
    )
    assert second.returncode == 0, second.stdout + second.stderr

    env_text = (repo / ".env").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=sk-test&ci-updated" in env_text
    assert f"DEV_REPOS_ROOT={repos_root}" in env_text
    assert f"DEV_WORKSPACE_ROOT={home}" in env_text
    assert "DEFAULT_ADMIN_PASSWORD=second-pass" in env_text

    assert (repo / "venv").is_dir()
    assert (repo / "frontend" / "node_modules").is_dir()
    assert (repo / "frontend" / "dist").is_dir()
    assert (repo / "data" / "devsynapse_memory.db").is_file()
    assert (repo / "data" / "devsynapse_monitoring.db").is_file()

    for rc_file in (home / ".bashrc", home / ".zshrc"):
        rc_text = rc_file.read_text(encoding="utf-8")
        assert rc_text.count("alias devsynapse=") == 1
        assert rc_text.count("alias uninstall-devsynapse=") == 1


def test_uninstall_script_removes_artifacts_and_respects_data_choices(tmp_path: Path) -> None:
    repo, fake_bin, home = _create_script_repo(tmp_path)
    repos_root = tmp_path / "repos"
    repos_root.mkdir()

    installed = _run_script(
        repo,
        fake_bin,
        home,
        "scripts/install.sh",
        f"sk-test\n{repos_root}\nadmin-pass\nadmin-pass\n",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr

    keep_data = _run_script(repo, fake_bin, home, "scripts/uninstall.sh", "n\nn\n")
    assert keep_data.returncode == 0, keep_data.stdout + keep_data.stderr
    assert not (repo / "venv").exists()
    assert not (repo / "frontend" / "node_modules").exists()
    assert not (repo / "frontend" / "dist").exists()
    assert (repo / "data").is_dir()
    assert (repo / "logs").is_dir()
    assert (repo / ".env").is_file()

    for rc_file in (home / ".bashrc", home / ".zshrc"):
        rc_text = rc_file.read_text(encoding="utf-8")
        assert "alias devsynapse=" not in rc_text
        assert "alias uninstall-devsynapse=" not in rc_text

    delete_data = _run_script(repo, fake_bin, home, "scripts/uninstall.sh", "s\ns\n")
    assert delete_data.returncode == 0, delete_data.stdout + delete_data.stderr
    assert not (repo / "data").exists()
    assert not (repo / "logs").exists()
    assert not (repo / ".env").exists()
