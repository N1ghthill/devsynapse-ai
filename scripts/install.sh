#!/usr/bin/env bash
#
# DevSynapse AI - TUI installer
#
# Usage:
#   bash scripts/install.sh
#
# Installs the Python runtime, creates user-scoped config/data/log directories,
# applies SQLite migrations and configures shell aliases for the canonical TUI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
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
CONFIG_FILE_DIR="$(dirname "$CONFIG_FILE")"
MEMORY_DB_FILE="$DATA_DIR/devsynapse_memory.db"
LOG_FILE="$LOGS_DIR/devsynapse.log"
export DEVSYNAPSE_CONFIG_FILE="$CONFIG_FILE"

APP_VERSION="$(awk -F\" '/app_version: str =/ {print $2; exit}' "$ROOT_DIR/config/settings.py" 2>/dev/null || true)"
APP_VERSION="${APP_VERSION:-unknown}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

step() { echo -e "\n${BOLD}${CYAN}[$1]${NC} ${BOLD}$2${NC}"; }
ok() { echo -e "  ${GREEN}OK${NC} $1"; }
warn() { echo -e "  ${YELLOW}WARN${NC} $1"; }
fail() { echo -e "  ${RED}FAIL${NC} $1"; }

set_env_value() {
    local key="$1"
    local value="$2"
    local tmp_file

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

ensure_env_value() {
    local key="$1"
    local value="$2"

    if ! grep -qE "^${key}=" "$CONFIG_FILE" 2>/dev/null; then
        set_env_value "$key" "$value"
    fi
}

get_env_value() {
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

install_python_requirements() {
    if [ -f "$ROOT_DIR/requirements.lock" ]; then
        pip install -r "$ROOT_DIR/requirements.txt" -c "$ROOT_DIR/requirements.lock"
    else
        pip install -r "$ROOT_DIR/requirements.txt"
    fi
}

check_system_deps() {
    local missing=()

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
        echo -e "  ${BOLD}sudo apt update && sudo apt install -y python3 python3-venv python3-pip${NC}"
        echo ""
        return 1
    fi

    ok "python3 and venv found"
    return 0
}

configure_runtime() {
    local api_key=""
    local current_api_key=""
    local repos_root=""
    local auto_repos=""

    mkdir -p "$CONFIG_DIR" "$CONFIG_FILE_DIR" "$DATA_DIR" "$LOGS_DIR"

    if [ ! -f "$CONFIG_FILE" ]; then
        cp "$ROOT_DIR/.env.example" "$CONFIG_FILE"
        ok "Runtime config created from .env.example"
    else
        ok "Runtime config already exists"
    fi

    set_env_value "MEMORY_DB_PATH" "$MEMORY_DB_FILE"
    set_env_value "LOG_FILE" "$LOG_FILE"
    ensure_env_value "DEV_WORKSPACE_ROOT" "$HOME"

    echo ""
    echo -e "  ${BOLD}Provider API key${NC}"
    echo -e "  Set one key now, or press Enter and use /connect inside the TUI later."
    echo ""
    read -r -p "  DeepSeek API key [optional]: " api_key
    echo ""

    if [ -n "$api_key" ]; then
        api_key=$(echo "$api_key" | xargs)
        set_env_value "DEEPSEEK_API_KEY" "$api_key"
        ok "DeepSeek API key saved"
    else
        current_api_key="$(get_env_value "DEEPSEEK_API_KEY" "")"
        if [ -n "$current_api_key" ]; then
            ok "API key kept from runtime config"
        else
            warn "No API key configured. Use /connect inside the TUI."
        fi
    fi

    echo ""
    echo -e "  ${BOLD}Repository directory${NC}"
    echo -e "  DevSynapse uses this root to resolve local projects and command scope."
    echo ""

    auto_repos="$HOME/repos"
    if [ -d "$HOME/ruas/repositorios" ]; then
        auto_repos="$HOME/ruas/repositorios"
    elif [ -d "$HOME/ruas/repos" ]; then
        auto_repos="$HOME/ruas/repos"
    elif [ -d "$HOME/projetos" ]; then
        auto_repos="$HOME/projetos"
    elif [ -d "$HOME/Projetos" ]; then
        auto_repos="$HOME/Projetos"
    elif [ -d "$HOME/Projects" ]; then
        auto_repos="$HOME/Projects"
    fi

    read -r -p "  Path [$auto_repos]: " repos_root
    repos_root="${repos_root:-$auto_repos}"
    echo ""

    if [ ! -d "$repos_root" ]; then
        warn "Directory '$repos_root' does not exist. Commands will fall back to HOME when needed."
    fi

    set_env_value "DEV_REPOS_ROOT" "$repos_root"
    ok "Repository root configured: $repos_root"
    ok "Config: $CONFIG_FILE"
    ok "Data: $DATA_DIR"
    ok "Logs: $LOGS_DIR"
}

configure_aliases() {
    local alias_marker="# >>> devsynapse alias (managed by scripts/install.sh) >>>"
    local alias_end="# <<< devsynapse alias <<<"
    local alias_line="alias devsynapse='cd \"$ROOT_DIR\" && DEVSYNAPSE_CONFIG_FILE=\"$CONFIG_FILE\" bash devsynapse.sh'"
    local update_line="alias update-devsynapse='cd \"$ROOT_DIR\" && DEVSYNAPSE_CONFIG_FILE=\"$CONFIG_FILE\" bash scripts/update.sh'"
    local uninstall_line="alias uninstall-devsynapse='cd \"$ROOT_DIR\" && DEVSYNAPSE_CONFIG_FILE=\"$CONFIG_FILE\" bash scripts/uninstall.sh'"

    setup_alias() {
        local rc_file="$1"
        local rc_name
        rc_name=$(basename "$rc_file")

        if [ ! -f "$rc_file" ]; then
            touch "$rc_file"
        fi

        if grep -qF "$alias_marker" "$rc_file" 2>/dev/null; then
            local tmp_file
            tmp_file="${rc_file}.devsynapse_tmp"
            awk -v start="$alias_marker" -v end="$alias_end" '
                $0 == start { skip = 1; next }
                $0 == end { skip = 0; next }
                skip != 1 { print }
            ' "$rc_file" > "$tmp_file"
            mv "$tmp_file" "$rc_file"
        fi

        {
            echo ""
            echo "$alias_marker"
            echo "$alias_line"
            echo "$update_line"
            echo "$uninstall_line"
            echo "$alias_end"
        } >> "$rc_file"

        ok "Aliases written to $rc_name"
    }

    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        setup_alias "$rc"
    done
}

install() {
    echo ""
    echo -e "${BOLD}${CYAN}DevSynapse AI TUI installer v$APP_VERSION${NC}"

    step "1/6" "Checking system dependencies"
    check_system_deps

    step "2/6" "Creating Python virtual environment"
    if [ ! -d "$ROOT_DIR/venv" ]; then
        python3 -m venv "$ROOT_DIR/venv" || {
            fail "Could not create venv"
            exit 1
        }
        ok "venv created"
    else
        ok "venv already exists"
    fi

    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv/bin/activate"

    step "3/6" "Installing Python dependencies"
    install_python_requirements 2>&1 | tail -3
    ok "Python dependencies installed"

    step "4/6" "Configuring runtime"
    configure_runtime

    step "5/6" "Applying SQLite migrations"
    python3 "$ROOT_DIR/scripts/migrate.py" apply || {
        fail "Migration failed"
        exit 1
    }
    ok "Migrations applied"

    step "6/6" "Configuring shell aliases"
    configure_aliases

    echo ""
    echo -e "${BOLD}${GREEN}DevSynapse AI installed.${NC}"
    echo ""
    echo -e "${BOLD}Start:${NC}"
    echo -e "  ${CYAN}source ~/.bashrc${NC}"
    echo -e "  ${CYAN}devsynapse${NC}"
    echo ""
    echo -e "${BOLD}Inside the TUI:${NC}"
    echo -e "  ${CYAN}/connect deepseek <api-key>${NC}"
    echo -e "  ${CYAN}/providers${NC}"
    echo -e "  ${CYAN}/status${NC}"
    echo -e "  ${CYAN}/usage${NC}"
    echo ""
    echo -e "${BOLD}Runtime files:${NC}"
    echo -e "  Config: ${CYAN}$CONFIG_FILE${NC}"
    echo -e "  Data:   ${CYAN}$DATA_DIR${NC}"
    echo -e "  Logs:   ${CYAN}$LOGS_DIR${NC}"
}

install
