import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-apt-repository.sh"


def require_debian_packaging_tools() -> None:
    missing = [
        command
        for command in ("dpkg-deb", "dpkg-scanpackages")
        if shutil.which(command) is None
    ]
    if missing:
        pytest.skip(f"missing Debian packaging tools: {', '.join(missing)}")


def build_minimal_deb(output: Path, version: str = "9.8.7") -> Path:
    package_root = output.parent / "package-root"
    debian_dir = package_root / "DEBIAN"
    bin_dir = package_root / "usr" / "bin"
    debian_dir.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    package_root.chmod(0o755)
    debian_dir.chmod(0o755)

    (debian_dir / "control").write_text(
        "\n".join(
            [
                "Package: dev-synapse-ai",
                f"Version: {version}",
                "Section: devel",
                "Priority: optional",
                "Architecture: amd64",
                "Maintainer: DevSynapse <dev@example.invalid>",
                "Description: Test package",
                "",
            ]
        ),
        encoding="utf-8",
    )
    executable = bin_dir / "devsynapse-ai"
    executable.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    subprocess.run(["dpkg-deb", "--build", str(package_root), str(output)], check=True)
    return output


def test_build_apt_repository_normalizes_deb_filename(tmp_path: Path) -> None:
    require_debian_packaging_tools()
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    build_minimal_deb(input_dir / "DevSynapse AI_9.8.7_amd64.deb")

    subprocess.run([str(SCRIPT), str(input_dir), str(output_dir)], check=True)

    package_filename = "dev-synapse-ai_9.8.7_amd64.deb"
    assert (output_dir / "repository" / "pool" / "main" / package_filename).is_file()
    packages = (
        output_dir
        / "repository"
        / "dists"
        / "stable"
        / "main"
        / "binary-amd64"
        / "Packages"
    ).read_text(encoding="utf-8")
    assert f"Filename: pool/main/{package_filename}" in packages
    assert "DevSynapse AI_9.8.7_amd64.deb" not in packages

    with tarfile.open(output_dir / "devsynapse-apt-repository.tar.gz") as archive:
        assert f"repository/pool/main/{package_filename}" in archive.getnames()
