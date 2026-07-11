#!/usr/bin/env python3
"""Create the Tauri release-only updater configuration from CI secrets."""

from __future__ import annotations

import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT = ROOT_DIR / "frontend" / "src-tauri" / "tauri.release.conf.json"


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required for production release builds")
    return value


def main() -> int:
    pubkey = required_env("TAURI_UPDATER_PUBKEY")
    endpoint = required_env("TAURI_UPDATER_ENDPOINT")
    config = {
        "bundle": {
            "createUpdaterArtifacts": True,
            "externalBin": ["binaries/devsynapse-backend"],
        },
        "plugins": {
            "updater": {
                "pubkey": pubkey,
                "endpoints": [endpoint],
                "windows": {
                    "installMode": "passive",
                },
            },
        },
    }
    OUTPUT.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Release updater config written: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
