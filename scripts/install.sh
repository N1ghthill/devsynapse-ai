#!/usr/bin/env bash
#
# DevSynapse AI - TUI installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/N1ghthill/devsynapse-ai/main/scripts/install.sh | bash
#   bash scripts/install.sh
#
# Installs the Python runtime, creates user-scoped config/data/log directories,
# applies SQLite migrations and installs canonical shell commands.

set -euo pipefail

APP_ID="devsynapse-ai"
REPO_URL="${DEVSYNAPSE_REPO_URL:-https://github.com/N1ghthill/devsynapse-ai.git}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -n "${DEVSYNAPSE_INSTALL_DIR:-}" ]; then
    INSTALL_DIR="${DEVSYNAPSE_INSTALL_DIR/#\~/$HOME}"
else
    INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID/source"
fi

if [ ! -f "$ROOT_DIR/pyproject.toml" ] || [ ! -f "$ROOT_DIR/.env.example" ]; then
    echo "DevSynapse source checkout not found; bootstrapping from $REPO_URL"
    if ! command -v git >/dev/null 2>&1; then
        echo "Missing dependency: git" >&2
        echo "Install with: sudo apt update && sudo apt install -y git python3 python3-venv python3-pip" >&2
        exit 1
    fi
    if [ -d "$INSTALL_DIR/.git" ]; then
        git -C "$INSTALL_DIR" fetch --tags origin
        git -C "$INSTALL_DIR" pull --ff-only
    else
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
    exec bash "$INSTALL_DIR/scripts/install.sh" "$@"
fi

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
BIN_DIR="${DEVSYNAPSE_BIN_DIR:-$HOME/.local/bin}"
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

prompt_value() {
    local prompt="$1"
    local default_value="${2:-}"
    local value=""

    if [ -n "${DEVSYNAPSE_ASSUME_DEFAULTS:-}" ]; then
        echo "$default_value"
        return
    fi

    if [ ! -t 0 ] && [ -z "${DEVSYNAPSE_INTERACTIVE:-}" ]; then
        echo "$default_value"
        return
    fi

    if [ -t 0 ]; then
        read -r -p "$prompt" value || value="$default_value"
    elif [ -t 1 ] && [ -r /dev/tty ]; then
        read -r -p "$prompt" value < /dev/tty || value="$default_value"
    else
        read -r -p "$prompt" value || value="$default_value"
    fi

    echo "${value:-$default_value}"
}

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
    api_key="$(prompt_value "  DeepSeek API key [optional]: " "")"
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

    repos_root="$(prompt_value "  Path [$auto_repos]: " "$auto_repos")"
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

remove_legacy_aliases() {
    local rc_file="$1"
    local tmp_file

    if [ ! -f "$rc_file" ]; then
        return
    fi

    tmp_file="${rc_file}.devsynapse_tmp"
    sed \
        -e '/^# >>> devsynapse alias /,/^# <<< devsynapse alias <<</d' \
        -e '/^# >>> devsynapse$/,/^# <<< devsynapse$/d' \
        -e '/^alias devsynapse=/d' \
        -e '/^alias update-devsynapse=/d' \
        -e '/^alias uninstall-devsynapse=/d' \
        "$rc_file" > "$tmp_file"
    mv "$tmp_file" "$rc_file"
}

configure_shell_path() {
    local rc_file="$1"
    local marker="# >>> devsynapse path (managed by scripts/install.sh) >>>"
    local marker_end="# <<< devsynapse path <<<"
    local rc_name
    local tmp_file

    rc_name="$(basename "$rc_file")"
    mkdir -p "$(dirname "$rc_file")"
    touch "$rc_file"
    remove_legacy_aliases "$rc_file"

    if grep -qF "$marker" "$rc_file" 2>/dev/null; then
        tmp_file="${rc_file}.devsynapse_tmp"
        awk -v start="$marker" -v end="$marker_end" '
            $0 == start { skip = 1; next }
            $0 == end { skip = 0; next }
            skip != 1 { print }
        ' "$rc_file" > "$tmp_file"
        mv "$tmp_file" "$rc_file"
    fi

    {
        echo ""
        echo "$marker"
        echo "export PATH=\"$BIN_DIR:\$PATH\""
        echo "$marker_end"
    } >> "$rc_file"

    ok "PATH configured in $rc_name"
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
    ok "Commands installed in $BIN_DIR"
}

configure_commands() {
    write_command_wrappers
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        configure_shell_path "$rc"
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

    step "6/6" "Installing commands"
    configure_commands

    echo ""
    echo -e "${BOLD}${GREEN}DevSynapse AI installed.${NC}"
    echo ""
    echo -e "${BOLD}Start:${NC}"
    echo -e "  ${CYAN}source ~/.bashrc${NC}  # if ~/.local/bin was not already in PATH"
    echo -e "  ${CYAN}devsynapse${NC}"
    echo ""
    echo -e "${BOLD}Inside the TUI:${NC}"
    echo -e "  ${CYAN}/connect deepseek <api-key>${NC}"
    echo -e "  ${CYAN}/providers${NC}"
    echo -e "  ${CYAN}/status${NC}"
    echo -e "  ${CYAN}/usage${NC}"
    echo ""
    echo -e "${BOLD}Notes:${NC}"
    echo -e "  Piped installs use default setup values; configure provider keys with ${CYAN}/connect${NC}."
    echo -e "  Scripted local installs can set ${CYAN}DEVSYNAPSE_ASSUME_DEFAULTS=1${NC} to skip prompts."
    echo ""
    echo -e "${BOLD}Runtime files:${NC}"
    echo -e "  Config: ${CYAN}$CONFIG_FILE${NC}"
    echo -e "  Data:   ${CYAN}$DATA_DIR${NC}"
    echo -e "  Logs:   ${CYAN}$LOGS_DIR${NC}"
}

install
