#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Build the DevSynapse AI backend sidecar with PyInstaller.
#
# Usage:
#   bash scripts/build-backend.sh   [--clean]
#
# Output:
#   dist/devsynapse-backend
#   frontend/src-tauri/binaries/devsynapse-backend-{target-triple}
#
# After this, run `npm run tauri build` to bundle the desktop app.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── Python venv ──────────────────────────────────────────────────────────────
PYTHON="${PYTHON:-./venv/bin/python}"
if [ ! -f "$PYTHON" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    "$PYTHON" -m pip install --upgrade pip
fi

# ── Install dependencies ─────────────────────────────────────────────────────
echo "Installing Python dependencies..."
"$PYTHON" -m pip install -r requirements.txt -q

# ── PyInstaller ──────────────────────────────────────────────────────────────
echo "Installing PyInstaller..."
"$PYTHON" -m pip install pyinstaller -q

CLEAN_FLAG=""
if [ "${1:-}" = "--clean" ]; then
    CLEAN_FLAG="--clean"
    echo "Clean build requested."
fi

echo "Building backend executable with PyInstaller..."
"$PYTHON" -m PyInstaller $CLEAN_FLAG --noconfirm backend.spec

# ── Copy to Tauri sidecar directory ──────────────────────────────────────────
# Tauri expects the binary at frontend/src-tauri/binaries/{name}-{target-triple}
# for the current Rust target. Cross-OS builds should run this script on the
# target OS, because PyInstaller does not produce portable binaries.

TARGET_TRIPLE="${TAURI_TARGET_TRIPLE:-${CARGO_BUILD_TARGET:-}}"
if [ -z "$TARGET_TRIPLE" ]; then
    TARGET_TRIPLE="$(rustc -vV | awk '/^host:/ {print $2}')"
fi

if [ -z "$TARGET_TRIPLE" ]; then
    echo "ERROR: could not determine Rust target triple"
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
    echo "ERROR: PyInstaller output not found at $SRC"
    echo "Contents of dist/:"
    find dist/ -type f 2>/dev/null | head -20
    exit 1
fi

DEST_DIR="frontend/src-tauri/binaries"
DEST="$DEST_DIR/devsynapse-backend-$TARGET_TRIPLE$EXE_SUFFIX"
mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"
if [[ "$EXE_SUFFIX" != ".exe" ]]; then
    chmod +x "$DEST"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Backend built successfully: $SRC"
echo "  Size: $(du -h "$SRC" | cut -f1)"
echo "  Tauri sidecar: $DEST"
echo ""
echo "  Next step:"
echo "    npm run tauri build       # from frontend/"
echo ""
echo "  For development:"
echo "    npm run tauri:dev          # from frontend/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
