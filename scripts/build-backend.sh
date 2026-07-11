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

"$PYTHON" scripts/build_backend.py "$@"
