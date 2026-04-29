#!/bin/sh
set -eu

# Tauri desktop builds can remain alive in the system tray after the last window
# is closed. Stop the UI and sidecar before dpkg/rpm removes their files.
stop_processes() {
    signal="$1"

    for name in "devsynapse-ai" "DevSynapse AI" "devsynapse-backend"; do
        if command -v pkill >/dev/null 2>&1; then
            pkill "-$signal" -x "$name" >/dev/null 2>&1 || true
        fi
    done

    if command -v pkill >/dev/null 2>&1; then
        pkill "-$signal" -f "/devsynapse-backend" >/dev/null 2>&1 || true
    fi
}

has_running_processes() {
    for name in "devsynapse-ai" "DevSynapse AI" "devsynapse-backend"; do
        if command -v pgrep >/dev/null 2>&1 && pgrep -x "$name" >/dev/null 2>&1; then
            return 0
        fi
    done

    if command -v pgrep >/dev/null 2>&1 && pgrep -f "/devsynapse-backend" >/dev/null 2>&1; then
        return 0
    fi

    return 1
}

stop_processes TERM

count=0
while has_running_processes && [ "$count" -lt 20 ]; do
    count=$((count + 1))
    sleep 0.1
done

if has_running_processes; then
    stop_processes KILL
fi

exit 0
