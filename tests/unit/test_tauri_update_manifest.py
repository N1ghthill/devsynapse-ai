"""
Tests for the Tauri updater manifest generator.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_manifest_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / (
        "generate-tauri-update-manifest.py"
    )
    spec = importlib.util.spec_from_file_location("generate_tauri_update_manifest", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_manifest_supports_multiple_platforms(tmp_path: Path) -> None:
    module = _load_manifest_module()
    linux_sig = tmp_path / "linux.sig"
    windows_sig = tmp_path / "windows.sig"
    linux_sig.write_text("linux-signature\n", encoding="utf-8")
    windows_sig.write_text("windows-signature\n", encoding="utf-8")

    manifest = module.build_manifest(
        version="0.5.2",
        notes="Release notes",
        platforms=["linux-x86_64", "windows-x86_64"],
        urls=[
            "https://example.com/DevSynapse_AI_0.5.2_amd64.deb",
            "https://example.com/DevSynapse_AI_0.5.2_x64-setup.exe",
        ],
        signature_files=[linux_sig, windows_sig],
    )

    assert manifest["version"] == "0.5.2"
    assert manifest["notes"] == "Release notes"
    assert manifest["platforms"] == {
        "linux-x86_64": {
            "signature": "linux-signature",
            "url": "https://example.com/DevSynapse_AI_0.5.2_amd64.deb",
        },
        "windows-x86_64": {
            "signature": "windows-signature",
            "url": "https://example.com/DevSynapse_AI_0.5.2_x64-setup.exe",
        },
    }
    assert manifest["pub_date"].endswith("Z")


def test_build_manifest_rejects_mismatched_platform_arguments(tmp_path: Path) -> None:
    module = _load_manifest_module()
    signature = tmp_path / "linux.sig"
    signature.write_text("linux-signature\n", encoding="utf-8")

    try:
        module.build_manifest(
            version="0.5.2",
            notes="Release notes",
            platforms=["linux-x86_64", "windows-x86_64"],
            urls=["https://example.com/linux.deb"],
            signature_files=[signature],
        )
    except ValueError as exc:
        assert "same number of times" in str(exc)
    else:
        raise AssertionError("Expected mismatched updater manifest arguments to fail")

