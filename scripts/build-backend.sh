#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON="${PYTHON:-./venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    BASE_PYTHON="${BASE_PYTHON:-python3}"
    "$BASE_PYTHON" -m venv venv
    PYTHON="./venv/bin/python"
fi

"$PYTHON" -m pip install -r requirements.txt -q
"$PYTHON" -m pip install pyinstaller -q

CLEAN_FLAG=""
if [ "${1:-}" = "--clean" ]; then
    CLEAN_FLAG="--clean"
fi

"$PYTHON" -m PyInstaller $CLEAN_FLAG --noconfirm backend.spec

TARGET_TRIPLE="${TAURI_TARGET_TRIPLE:-${CARGO_BUILD_TARGET:-}}"
if [ -z "$TARGET_TRIPLE" ]; then
    TARGET_TRIPLE="$(rustc -vV | awk '/^host:/ {print $2}')"
fi

if [ -z "$TARGET_TRIPLE" ]; then
    echo "Could not determine Rust target triple" >&2
    exit 1
fi

EXE_SUFFIX=""
if [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
    EXE_SUFFIX=".exe"
fi

SRC="dist/devsynapse-backend${EXE_SUFFIX}"
if [ ! -f "$SRC" ] && [ -f "dist/devsynapse-backend" ]; then
    SRC="dist/devsynapse-backend"
fi

if [ ! -f "$SRC" ]; then
    echo "PyInstaller output not found at $SRC" >&2
    exit 1
fi

DEST_DIR="frontend/src-tauri/binaries"
DEST="$DEST_DIR/devsynapse-backend-$TARGET_TRIPLE$EXE_SUFFIX"
mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"
if [[ "$EXE_SUFFIX" != ".exe" ]]; then
    chmod +x "$DEST"
fi

echo "Backend sidecar built: $DEST"
