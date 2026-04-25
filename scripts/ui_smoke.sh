#!/usr/bin/env bash
#
# Run a browser smoke test against a temporary local DevSynapse runtime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    if [ -x "$ROOT_DIR/venv/bin/python" ]; then
        PYTHON="$ROOT_DIR/venv/bin/python"
    else
        PYTHON="python3"
    fi
fi

HOST="${DEVSYNAPSE_SMOKE_HOST:-127.0.0.1}"
PORT="${DEVSYNAPSE_SMOKE_PORT:-18080}"
BASE_URL="http://${HOST}:${PORT}"
TMP_DIR="$(mktemp -d)"
API_PID=""

cleanup() {
    if [ -n "$API_PID" ] && kill -0 "$API_PID" >/dev/null 2>&1; then
        kill "$API_PID" >/dev/null 2>&1 || true
        wait "$API_PID" >/dev/null 2>&1 || true
    fi
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

export MEMORY_DB_PATH="${MEMORY_DB_PATH:-$TMP_DIR/devsynapse_memory.db}"
export MONITORING_DB_PATH="${MONITORING_DB_PATH:-$TMP_DIR/devsynapse_monitoring.db}"
export LOG_FILE="${LOG_FILE:-$TMP_DIR/devsynapse.log}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-devsynapse-ui-smoke-secret}"
export DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-SmokePass123}"
export DEFAULT_USER_USERNAME="${DEFAULT_USER_USERNAME:-smoke-user}"
export DEFAULT_USER_PASSWORD="${DEFAULT_USER_PASSWORD:-SmokeUser123}"
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-sk-ui-smoke}"
export DEV_WORKSPACE_ROOT="${DEV_WORKSPACE_ROOT:-$TMP_DIR/workspace}"
export DEV_REPOS_ROOT="${DEV_REPOS_ROOT:-$TMP_DIR/repos}"

mkdir -p "$DEV_WORKSPACE_ROOT" "$DEV_REPOS_ROOT"

echo "Applying smoke-test migrations..."
"$PYTHON" "$ROOT_DIR/scripts/migrate.py" apply

echo "Building frontend for ${BASE_URL}..."
(
    cd "$ROOT_DIR/frontend"
    VITE_API_URL="$BASE_URL" npm run build
)

echo "Starting temporary API on ${BASE_URL}..."
(
    cd "$ROOT_DIR"
    "$PYTHON" -m uvicorn api.app:app --host "$HOST" --port "$PORT"
) > "$TMP_DIR/api.log" 2>&1 &
API_PID="$!"

for _ in $(seq 1 40); do
    if "$PYTHON" - "$BASE_URL/api" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=1) as response:
    if response.status == 200:
        raise SystemExit(0)
raise SystemExit(1)
PY
    then
        break
    fi

    if ! kill -0 "$API_PID" >/dev/null 2>&1; then
        echo "API process exited before becoming ready."
        cat "$TMP_DIR/api.log"
        exit 1
    fi

    sleep 0.5
done

if ! "$PYTHON" - "$BASE_URL/api" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=1) as response:
    if response.status == 200:
        raise SystemExit(0)
raise SystemExit(1)
PY
then
    echo "API did not become ready."
    cat "$TMP_DIR/api.log"
    exit 1
fi

echo "Running Playwright UI smoke..."
(
    cd "$ROOT_DIR/frontend"
    DEVSYNAPSE_SMOKE_BASE_URL="$BASE_URL" \
    DEVSYNAPSE_SMOKE_USERNAME="${DEVSYNAPSE_SMOKE_USERNAME:-admin}" \
    DEVSYNAPSE_SMOKE_PASSWORD="${DEVSYNAPSE_SMOKE_PASSWORD:-$DEFAULT_ADMIN_PASSWORD}" \
    DEVSYNAPSE_SMOKE_SCREENSHOT="$TMP_DIR/smoke-ui-failure.png" \
    npm run smoke:ui
)
