#!/usr/bin/env python3
"""Stage release assets and generate Tauri's static latest.json manifest."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

UPDATER_PLATFORMS = {
    "devsynapse-linux-x86_64": ("linux-x86_64", ".AppImage"),
    "devsynapse-windows-x86_64": ("windows-x86_64", ".exe"),
    "devsynapse-macos-x86_64": ("darwin-x86_64", ".app.tar.gz"),
    "devsynapse-macos-aarch64": ("darwin-aarch64", ".app.tar.gz"),
}

ASSET_PLATFORMS = {
    "devsynapse-linux-x86_64": "linux-x86_64",
    "devsynapse-windows-x86_64": "windows-x86_64",
    "devsynapse-macos-x86_64": "macos-x86_64",
    "devsynapse-macos-aarch64": "macos-aarch64",
}

PRODUCT_ASSET_PREFIX = "DevSynapse-AI"


def release_url(repository: str, tag: str, asset_name: str) -> str:
    return f"https://github.com/{repository}/releases/download/{tag}/{asset_name}"


def artifact_name(source: Path, input_dir: Path) -> str | None:
    try:
        return source.relative_to(input_dir).parts[0]
    except ValueError:
        return None


def package_suffix(source_name: str) -> str | None:
    suffixes = (
        ".app.tar.gz.sig",
        ".app.tar.gz",
        ".AppImage.sig",
        ".AppImage",
        "-setup.exe.sig",
        "-setup.exe",
        ".msi.sig",
        ".msi",
        ".dmg",
        ".deb",
    )
    for suffix in suffixes:
        if source_name.endswith(suffix):
            return suffix
    return None


def staged_asset_name(source: Path, input_dir: Path, version: str) -> str:
    artifact = artifact_name(source, input_dir)
    if artifact == "devsynapse-apt-repository" and source.name == "devsynapse-apt-repository.tar.gz":
        return f"devsynapse-apt-repository_{version}.tar.gz"

    platform = ASSET_PLATFORMS.get(artifact or "")
    suffix = package_suffix(source.name)
    if platform and suffix:
        if suffix in {".app.tar.gz", ".app.tar.gz.sig"}:
            return f"{PRODUCT_ASSET_PREFIX}_{version}_{platform}.app.tar.gz{'.sig' if source.name.endswith('.sig') else ''}"
        if suffix in {"-setup.exe", "-setup.exe.sig"}:
            return f"{PRODUCT_ASSET_PREFIX}_{version}_{platform}-setup.exe{'.sig' if source.name.endswith('.sig') else ''}"
        return f"{PRODUCT_ASSET_PREFIX}_{version}_{platform}{suffix}"

    return source.name.replace(" ", ".")


def copy_named_asset(source: Path, output_dir: Path, name: str, used_names: set[str]) -> Path:
    if name in used_names:
        candidate = f"{source.parent.name}-{name}"
        counter = 2
        while candidate in used_names:
            candidate = f"{source.parent.name}-{counter}-{name}"
            counter += 1
        name = candidate
    used_names.add(name)
    destination = output_dir / name
    shutil.copy2(source, destination)
    return destination


def find_update_asset(artifact_dir: Path, extension: str) -> Path | None:
    candidates = sorted(
        path
        for path in artifact_dir.rglob(f"*{extension}")
        if path.is_file() and not path.name.endswith(".sig")
    )
    if not candidates:
        return None
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    copied_by_source: dict[Path, Path] = {}
    version = args.tag.removeprefix("v")

    for source in sorted(path for path in args.input_dir.rglob("*") if path.is_file()):
        staged = copy_named_asset(
            source,
            args.output_dir,
            staged_asset_name(source, args.input_dir, version),
            used_names,
        )
        copied_by_source[source.resolve()] = staged

    platforms: dict[str, dict[str, str]] = {}
    for artifact_name, (platform_key, extension) in UPDATER_PLATFORMS.items():
        artifact_dir = args.input_dir / artifact_name
        if not artifact_dir.exists():
            continue
        update_source = find_update_asset(artifact_dir, extension)
        if update_source is None:
            continue
        signature_source = Path(f"{update_source}.sig")
        if not signature_source.exists():
            raise SystemExit(f"Missing updater signature for {update_source}")
        staged_update = copied_by_source[update_source.resolve()]
        platforms[platform_key] = {
            "signature": signature_source.read_text(encoding="utf-8").strip(),
            "url": release_url(args.repository, args.tag, staged_update.name),
        }

    if not platforms:
        raise SystemExit("No updater platforms were discovered")

    latest = {
        "version": version,
        "notes": args.notes,
        "pub_date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "platforms": platforms,
    }
    (args.output_dir / "latest.json").write_text(
        json.dumps(latest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Release assets staged in {args.output_dir}")
    print(f"Updater platforms: {', '.join(sorted(platforms))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
