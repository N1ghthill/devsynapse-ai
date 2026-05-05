#!/bin/bash
# DevSynapse AI launcher
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT_DIR/venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "DevSynapse venv not found. Run: cd \"$ROOT_DIR\" && python3 -m venv venv && source venv/bin/activate && make install-dev" >&2
    exit 1
fi

cd "$ROOT_DIR"
exec "$PYTHON" -m devsynapse.cli "$@"
