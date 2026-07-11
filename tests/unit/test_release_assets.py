import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "prepare-release-assets.py"


def touch(path: Path, content: str = "asset") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_prepare_release_assets_uses_stable_platform_names(tmp_path: Path) -> None:
    input_dir = tmp_path / "release-assets"
    output_dir = tmp_path / "release-publish"

    touch(input_dir / "devsynapse-linux-x86_64" / "DevSynapse AI_1.2.1_amd64.AppImage")
    touch(input_dir / "devsynapse-linux-x86_64" / "DevSynapse AI_1.2.1_amd64.AppImage.sig", "linuxsig")
    touch(input_dir / "devsynapse-linux-x86_64" / "DevSynapse AI_1.2.1_amd64.deb")
    touch(input_dir / "devsynapse-windows-x86_64" / "DevSynapse AI_1.2.1_x64-setup.exe")
    touch(input_dir / "devsynapse-windows-x86_64" / "DevSynapse AI_1.2.1_x64-setup.exe.sig", "winsig")
    touch(input_dir / "devsynapse-windows-x86_64" / "DevSynapse AI_1.2.1_x64_en-US.msi")
    touch(input_dir / "devsynapse-windows-x86_64" / "DevSynapse AI_1.2.1_x64_en-US.msi.sig")
    touch(input_dir / "devsynapse-macos-x86_64" / "DevSynapse AI.app.tar.gz")
    touch(input_dir / "devsynapse-macos-x86_64" / "DevSynapse AI.app.tar.gz.sig", "macxsig")
    touch(input_dir / "devsynapse-macos-x86_64" / "DevSynapse AI_1.2.1_x64.dmg")
    touch(input_dir / "devsynapse-macos-aarch64" / "DevSynapse AI.app.tar.gz")
    touch(input_dir / "devsynapse-macos-aarch64" / "DevSynapse AI.app.tar.gz.sig", "macarmsig")
    touch(input_dir / "devsynapse-macos-aarch64" / "DevSynapse AI_1.2.1_aarch64.dmg")
    touch(input_dir / "devsynapse-apt-repository" / "devsynapse-apt-repository.tar.gz")

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(input_dir),
            str(output_dir),
            "--repository",
            "N1ghthill/devsynapse-ai",
            "--tag",
            "v1.2.1",
            "--notes",
            "Release notes",
        ],
        check=True,
    )

    expected_assets = {
        "DevSynapse-AI_1.2.1_linux-x86_64.AppImage",
        "DevSynapse-AI_1.2.1_linux-x86_64.AppImage.sig",
        "DevSynapse-AI_1.2.1_linux-x86_64.deb",
        "DevSynapse-AI_1.2.1_windows-x86_64-setup.exe",
        "DevSynapse-AI_1.2.1_windows-x86_64-setup.exe.sig",
        "DevSynapse-AI_1.2.1_windows-x86_64.msi",
        "DevSynapse-AI_1.2.1_windows-x86_64.msi.sig",
        "DevSynapse-AI_1.2.1_macos-x86_64.app.tar.gz",
        "DevSynapse-AI_1.2.1_macos-x86_64.app.tar.gz.sig",
        "DevSynapse-AI_1.2.1_macos-x86_64.dmg",
        "DevSynapse-AI_1.2.1_macos-aarch64.app.tar.gz",
        "DevSynapse-AI_1.2.1_macos-aarch64.app.tar.gz.sig",
        "DevSynapse-AI_1.2.1_macos-aarch64.dmg",
        "devsynapse-apt-repository_1.2.1.tar.gz",
        "latest.json",
    }
    assert {path.name for path in output_dir.iterdir()} == expected_assets

    latest = json.loads((output_dir / "latest.json").read_text(encoding="utf-8"))
    assert latest["version"] == "1.2.1"
    assert latest["platforms"]["linux-x86_64"]["signature"] == "linuxsig"
    assert latest["platforms"]["windows-x86_64"]["signature"] == "winsig"
    assert latest["platforms"]["darwin-x86_64"]["signature"] == "macxsig"
    assert latest["platforms"]["darwin-aarch64"]["signature"] == "macarmsig"
    assert latest["platforms"]["darwin-aarch64"]["url"].endswith(
        "/DevSynapse-AI_1.2.1_macos-aarch64.app.tar.gz"
    )
