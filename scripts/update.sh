#!/usr/bin/env bash
#
# DevSynapse AI - TUI updater
#
# Usage:
#   bash scripts/update.sh
#   bash scripts/update.sh --version vX.Y.Z
#   bash scripts/update.sh --branch main

set -euo pipefail

if [ -n "${DEVSYNAPSE_UPDATE_ROOT_DIR:-}" ]; then
    ROOT_DIR="$DEVSYNAPSE_UPDATE_ROOT_DIR"
    SCRIPT_DIR="$ROOT_DIR/scripts"
else
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

if [ -z "${DEVSYNAPSE_UPDATE_RUNNING_FROM_TEMP:-}" ] && [ -f "$0" ]; then
    tmp_script="$(mktemp)"
    cp "$0" "$tmp_script"
    chmod +x "$tmp_script"
    export DEVSYNAPSE_UPDATE_RUNNING_FROM_TEMP=1
    export DEVSYNAPSE_UPDATE_ROOT_DIR="$ROOT_DIR"
    export DEVSYNAPSE_UPDATE_TEMP_SCRIPT="$tmp_script"
    exec bash "$tmp_script" "$@"
fi

if [ -n "${DEVSYNAPSE_UPDATE_TEMP_SCRIPT:-}" ]; then
    trap 'rm -f "$DEVSYNAPSE_UPDATE_TEMP_SCRIPT"' EXIT
fi

cd "$ROOT_DIR"
APP_ID="devsynapse-ai"

if [ -n "${DEVSYNAPSE_HOME:-}" ]; then
    RUNTIME_HOME="${DEVSYNAPSE_HOME/#\~/$HOME}"
    CONFIG_DIR="${DEVSYNAPSE_CONFIG_DIR:-$RUNTIME_HOME/config}"
    DATA_DIR="${DEVSYNAPSE_DATA_DIR:-$RUNTIME_HOME/data}"
    LOGS_DIR="${DEVSYNAPSE_LOGS_DIR:-$RUNTIME_HOME/logs}"
else
    CONFIG_DIR="${DEVSYNAPSE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/$APP_ID}"
    DATA_DIR="${DEVSYNAPSE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID/data}"
    LOGS_DIR="${DEVSYNAPSE_LOGS_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/$APP_ID/logs}"
fi

CONFIG_FILE="${DEVSYNAPSE_CONFIG_FILE:-$CONFIG_DIR/.env}"
BIN_DIR="${DEVSYNAPSE_BIN_DIR:-$HOME/.local/bin}"
export DEVSYNAPSE_CONFIG_FILE="$CONFIG_FILE"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

TARGET_VERSION=""
TARGET_BRANCH=""
SKIP_GIT=0
BACKUP_ENABLED=1

step() { echo -e "\n${BOLD}${CYAN}[$1]${NC} ${BOLD}$2${NC}"; }
ok() { echo -e "  ${GREEN}OK${NC} $1"; }
warn() { echo -e "  ${YELLOW}WARN${NC} $1"; }
fail() { echo -e "  ${RED}FAIL${NC} $1"; }

usage() {
    cat <<'EOF'
DevSynapse TUI updater

Usage:
  bash scripts/update.sh
  bash scripts/update.sh --version vX.Y.Z
  bash scripts/update.sh --branch main

Options:
  --version TAG   Update checkout to a published tag.
  --branch NAME   Update checkout to a branch, defaulting to the current branch.
  --skip-git      Skip git fetch/checkout/pull and refresh local runtime only.
  --no-backup     Do not copy runtime config/database/log files before updating.
  -h, --help      Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            TARGET_VERSION="${2:-}"
            if [ -z "$TARGET_VERSION" ]; then
                fail "--version requires a tag"
                exit 1
            fi
            shift 2
            ;;
        --branch)
            TARGET_BRANCH="${2:-}"
            if [ -z "$TARGET_BRANCH" ]; then
                fail "--branch requires a name"
                exit 1
            fi
            shift 2
            ;;
        --skip-git)
            SKIP_GIT=1
            shift
            ;;
        --no-backup)
            BACKUP_ENABLED=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [ -n "$TARGET_VERSION" ] && [ -n "$TARGET_BRANCH" ]; then
    fail "Use only one target: --version or --branch"
    exit 1
fi

get_config_value() {
    local key="$1"
    local default_value="${2:-}"

    if [ ! -f "$CONFIG_FILE" ]; then
        echo "$default_value"
        return
    fi

    awk -F= -v key="$key" -v default_value="$default_value" '
        $1 == key {
            sub("^[^=]*=", "")
            print
            found = 1
            exit
        }
        END {
            if (found != 1) {
                print default_value
            }
        }
    ' "$CONFIG_FILE"
}

set_env_value() {
    local key="$1"
    local value="$2"
    local tmp_file

    mkdir -p "$(dirname "$CONFIG_FILE")"
    tmp_file="$(mktemp)"
    if [ -f "$CONFIG_FILE" ]; then
        awk -v key="$key" -v value="$value" '
            BEGIN { updated = 0 }
            $0 ~ "^" key "=" {
                print key "=" value
                updated = 1
                next
            }
            { print }
            END {
                if (updated == 0) {
                    print key "=" value
                }
            }
        ' "$CONFIG_FILE" > "$tmp_file"
    else
        echo "$key=$value" > "$tmp_file"
    fi
    mv "$tmp_file" "$CONFIG_FILE"
}

check_system_deps() {
    local missing=()

    if [ "$SKIP_GIT" -eq 0 ] && ! command -v git >/dev/null 2>&1; then
        missing+=("git")
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        missing+=("python3")
    fi
    if ! python3 -m venv --help >/dev/null 2>&1; then
        missing+=("python3-venv")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo ""
        echo -e "${RED}Missing system dependencies:${NC}"
        for dep in "${missing[@]}"; do
            echo -e "  ${RED}FAIL${NC} $dep"
        done
        echo ""
        echo -e "Install with:"
        echo -e "  ${BOLD}sudo apt update && sudo apt install -y git python3 python3-venv python3-pip${NC}"
        echo ""
        return 1
    fi

    ok "required system dependencies found"
    return 0
}

backup_runtime_state() {
    if [ "$BACKUP_ENABLED" -eq 0 ]; then
        warn "Runtime backup disabled by --no-backup"
        return
    fi

    local memory_db
    local log_file
    local timestamp
    local backup_dir
    local copied=0

    memory_db="$(get_config_value "MEMORY_DB_PATH" "$DATA_DIR/devsynapse_memory.db")"
    log_file="$(get_config_value "LOG_FILE" "$LOGS_DIR/devsynapse.log")"
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup_dir="$DATA_DIR/backups/update-$timestamp"

    mkdir -p "$backup_dir"

    for file in "$CONFIG_FILE" "$memory_db" "$log_file"; do
        if [ -f "$file" ]; then
            cp -p "$file" "$backup_dir/$(basename "$file")"
            copied=$((copied + 1))
        fi
    done

    if [ "$copied" -gt 0 ]; then
        ok "Runtime backup created at $backup_dir"
    else
        warn "No existing runtime files to back up"
        rmdir "$backup_dir" 2>/dev/null || true
    fi
}

ensure_clean_worktree() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        fail "This directory is not a Git repository"
        exit 1
    fi

    if [ -n "$(git status --porcelain)" ]; then
        fail "Local changes found. Commit or stash before updating."
        git status --short
        exit 1
    fi
}

update_source_checkout() {
    if [ "$SKIP_GIT" -eq 1 ]; then
        warn "Git update skipped by --skip-git"
        return
    fi

    local current_rev
    local new_rev
    local branch

    ensure_clean_worktree
    current_rev="$(git rev-parse --short HEAD)"
    git fetch --tags origin

    if [ -n "$TARGET_VERSION" ]; then
        git checkout "$TARGET_VERSION"
    else
        branch="$TARGET_BRANCH"
        if [ -z "$branch" ]; then
            branch="$(git branch --show-current)"
        fi
        if [ -z "$branch" ]; then
            branch="main"
        fi
        git checkout "$branch"
        git pull --ff-only origin "$branch"
    fi

    new_rev="$(git rev-parse --short HEAD)"
    ok "Source updated: $current_rev -> $new_rev"
}

install_python_requirements() {
    if [ -f "$ROOT_DIR/requirements.lock" ]; then
        pip install -r "$ROOT_DIR/requirements.txt" -c "$ROOT_DIR/requirements.lock"
    else
        pip install -r "$ROOT_DIR/requirements.txt"
    fi
}

ensure_runtime_config() {
    mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$LOGS_DIR" "$(dirname "$CONFIG_FILE")"
    if [ ! -f "$CONFIG_FILE" ]; then
        cp "$ROOT_DIR/.env.example" "$CONFIG_FILE"
        ok "Runtime config created from .env.example"
    fi
    set_env_value "MEMORY_DB_PATH" "$(get_config_value "MEMORY_DB_PATH" "$DATA_DIR/devsynapse_memory.db")"
    set_env_value "LOG_FILE" "$(get_config_value "LOG_FILE" "$LOGS_DIR/devsynapse.log")"
}

write_command_wrappers() {
    mkdir -p "$BIN_DIR"

    cat > "$BIN_DIR/devsynapse" <<EOF
#!/usr/bin/env bash
export DEVSYNAPSE_CONFIG_FILE="$CONFIG_FILE"
exec "$ROOT_DIR/devsynapse.sh" "\$@"
EOF

    cat > "$BIN_DIR/update-devsynapse" <<EOF
#!/usr/bin/env bash
export DEVSYNAPSE_CONFIG_FILE="$CONFIG_FILE"
exec bash "$ROOT_DIR/scripts/update.sh" "\$@"
EOF

    cat > "$BIN_DIR/uninstall-devsynapse" <<EOF
#!/usr/bin/env bash
export DEVSYNAPSE_CONFIG_FILE="$CONFIG_FILE"
exec bash "$ROOT_DIR/scripts/uninstall.sh" "\$@"
EOF

    chmod +x "$BIN_DIR/devsynapse" "$BIN_DIR/update-devsynapse" "$BIN_DIR/uninstall-devsynapse"
    ok "Command wrappers refreshed in $BIN_DIR"
}

refresh_runtime() {
    if [ ! -d "$ROOT_DIR/venv" ]; then
        python3 -m venv "$ROOT_DIR/venv"
        ok "venv created"
    fi

    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv/bin/activate"

    install_python_requirements
    ensure_runtime_config
    python3 "$ROOT_DIR/scripts/migrate.py" apply
    write_command_wrappers

    ok "Python runtime and migrations refreshed"
}

print_summary() {
    echo ""
    echo -e "${BOLD}${GREEN}Update complete.${NC}"
    echo -e "Config: ${CYAN}$CONFIG_FILE${NC}"
    echo ""
    echo "Start with:"
    echo -e "  ${CYAN}devsynapse${NC}"
}

main() {
    echo ""
    echo -e "${BOLD}${CYAN}DevSynapse AI TUI updater${NC}"

    step "1/5" "Checking dependencies"
    check_system_deps

    step "2/5" "Backing up runtime state"
    backup_runtime_state

    step "3/5" "Updating source"
    update_source_checkout

    step "4/5" "Refreshing Python runtime"
    refresh_runtime

    step "5/5" "Checking migration status"
    python3 "$ROOT_DIR/scripts/migrate.py" status

    print_summary
}

main
