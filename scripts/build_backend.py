#!/usr/bin/env python3
"""Build the packaged Python sidecar for the active Tauri target."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def run(command: list[str], *, cwd: Path = ROOT_DIR) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def rust_host_triple() -> str:
    result = subprocess.run(
        ["rustc", "-vV"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Could not determine Rust host target triple")


def target_triple() -> str:
    for key in ("TAURI_TARGET_TRIPLE", "CARGO_BUILD_TARGET"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return rust_host_triple()


def install_dependencies(python: Path) -> None:
    constraints = ROOT_DIR / "requirements.lock"
    requirements = ROOT_DIR / "requirements.txt"
    command = [str(python), "-m", "pip", "install", "-r", str(requirements)]
    if constraints.exists():
        command.extend(["-c", str(constraints)])
    run(command)
    run([str(python), "-m", "pip", "install", "pyinstaller"])


def pyinstaller_args(clean: bool) -> list[str]:
    command = [sys.executable, "-m", "PyInstaller"]
    if clean:
        command.append("--clean")
    command.extend(["--noconfirm", "backend.spec"])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="Pass --clean to PyInstaller")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Assume Python dependencies and PyInstaller are already installed",
    )
    args = parser.parse_args()

    if not args.skip_install:
        install_dependencies(Path(sys.executable))

    run(pyinstaller_args(args.clean))

    triple = target_triple()
    exe_suffix = ".exe" if "windows" in triple else ""
    source = ROOT_DIR / "dist" / f"devsynapse-backend{exe_suffix}"
    if not source.exists() and exe_suffix:
        source = ROOT_DIR / "dist" / "devsynapse-backend"
    if not source.exists():
        raise SystemExit(f"PyInstaller output not found: {source}")

    destination_dir = ROOT_DIR / "frontend" / "src-tauri" / "binaries"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"devsynapse-backend-{triple}{exe_suffix}"
    shutil.copy2(source, destination)
    if exe_suffix != ".exe":
        destination.chmod(destination.stat().st_mode | 0o111)

    print(f"Backend sidecar built: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
