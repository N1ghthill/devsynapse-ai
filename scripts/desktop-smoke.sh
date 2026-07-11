#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TIMEOUT_SECONDS="${DEVSYNAPSE_DESKTOP_SMOKE_TIMEOUT:-120}"
REQUIRED="${DEVSYNAPSE_DESKTOP_SMOKE_REQUIRED:-0}"

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ] && ! command -v xvfb-run >/dev/null 2>&1; then
    if [ "$REQUIRED" = "1" ]; then
        echo "desktop smoke requires DISPLAY, WAYLAND_DISPLAY or xvfb-run" >&2
        exit 1
    fi
    echo "desktop smoke skipped: no graphical display or xvfb-run available"
    exit 0
fi

LOG_FILE="$(mktemp -t devsynapse-desktop-smoke.XXXXXX.log)"
# shellcheck disable=SC2317
cleanup() {
    rm -f "$LOG_FILE"
}
trap cleanup EXIT

RUNNER=()
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ] && command -v xvfb-run >/dev/null 2>&1; then
    RUNNER=(xvfb-run -a)
fi

set +e
(
    cd "$ROOT_DIR/frontend"
    NO_COLOR=1 "${RUNNER[@]}" timeout "${TIMEOUT_SECONDS}s" \
        npm run tauri:dev -- --no-watch --exit-on-panic
) >"$LOG_FILE" 2>&1
STATUS=$?
set -e

if ! grep -Eq 'Running.*target/debug/devsynapse-ai' "$LOG_FILE"; then
    echo "desktop smoke failed: Tauri runtime did not start before timeout" >&2
    tail -80 "$LOG_FILE" >&2
    exit 1
fi

if [ "$STATUS" -eq 124 ]; then
    echo "desktop smoke passed: Tauri window process stayed alive for ${TIMEOUT_SECONDS}s"
    exit 0
fi

if [ "$STATUS" -eq 0 ]; then
    echo "desktop smoke passed: Tauri window process exited cleanly"
    exit 0
fi

echo "desktop smoke failed: Tauri command exited with status $STATUS" >&2
tail -80 "$LOG_FILE" >&2
exit "$STATUS"
