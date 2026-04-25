#!/usr/bin/env bash
#
# Regenerate Python dependency lock constraints from the current manifests.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="${PYTHON:-python3}"
TMP_DIR="$(mktemp -d)"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

generate_lock() {
    local requirements_file="$1"
    local output_file="$2"
    local venv_dir="$3"

    "$PYTHON" -m venv "$venv_dir"
    "$venv_dir/bin/python" -m pip install --upgrade pip
    "$venv_dir/bin/pip" install -r "$ROOT_DIR/$requirements_file"
    "$venv_dir/bin/pip" freeze --local | sort > "$ROOT_DIR/$output_file"
}

generate_lock "requirements.txt" "requirements.lock" "$TMP_DIR/runtime-venv"
generate_lock "requirements-dev.txt" "requirements-dev.lock" "$TMP_DIR/dev-venv"

echo "Updated requirements.lock and requirements-dev.lock"
