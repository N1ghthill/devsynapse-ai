#!/usr/bin/env bash
#
# DevSynapse AI - updater
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

step()  { echo -e "\n${BOLD}${CYAN}[$1]${NC} ${BOLD}$2${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }

usage() {
    cat <<'EOF'
DevSynapse updater

Usage:
  bash scripts/update.sh
  bash scripts/update.sh --version vX.Y.Z
  bash scripts/update.sh --branch main

Options:
  --version TAG   Update checkout to a published tag, for example v0.3.4.
  --branch NAME   Update checkout to a branch, defaulting to the current branch.
  --skip-git      Skip git fetch/checkout/pull and refresh local runtime only.
  --no-backup     Do not copy runtime config/database files before updating.
  -h, --help      Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            TARGET_VERSION="${2:-}"
            if [ -z "$TARGET_VERSION" ]; then
                fail "--version exige uma tag"
                exit 1
            fi
            shift 2
            ;;
        --branch)
            TARGET_BRANCH="${2:-}"
            if [ -z "$TARGET_BRANCH" ]; then
                fail "--branch exige um nome"
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
            fail "Opção desconhecida: $1"
            usage
            exit 1
            ;;
    esac
done

if [ -n "$TARGET_VERSION" ] && [ -n "$TARGET_BRANCH" ]; then
    fail "Use apenas uma opção: --version ou --branch"
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
    if ! command -v npm >/dev/null 2>&1; then
        missing+=("npm (nodejs)")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo ""
        echo -e "${RED}Dependências de sistema faltando:${NC}"
        for dep in "${missing[@]}"; do
            echo -e "  ${RED}✗${NC} $dep"
        done
        echo ""
        echo -e "Instale com:"
        echo -e "  ${BOLD}sudo apt update && sudo apt install -y git python3 python3-venv python3-pip nodejs npm${NC}"
        echo ""
        return 1
    fi

    ok "git, python3, venv e npm encontrados"
    return 0
}

backup_runtime_state() {
    if [ "$BACKUP_ENABLED" -eq 0 ]; then
        warn "Backup runtime desabilitado por --no-backup"
        return
    fi

    local memory_db
    local monitoring_db
    local log_file
    local timestamp
    local backup_dir
    local copied=0

    memory_db="$(get_config_value "MEMORY_DB_PATH" "$DATA_DIR/devsynapse_memory.db")"
    monitoring_db="$(get_config_value "MONITORING_DB_PATH" "$DATA_DIR/devsynapse_monitoring.db")"
    log_file="$(get_config_value "LOG_FILE" "$LOGS_DIR/devsynapse.log")"
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    backup_dir="$DATA_DIR/backups/update-$timestamp"

    mkdir -p "$backup_dir"

    for file in "$CONFIG_FILE" "$memory_db" "$monitoring_db" "$log_file"; do
        if [ -f "$file" ]; then
            cp -p "$file" "$backup_dir/$(basename "$file")"
            copied=$((copied + 1))
        fi
    done

    if [ "$copied" -gt 0 ]; then
        ok "Backup runtime criado em $backup_dir"
    else
        warn "Nenhum arquivo runtime existente para backup"
        rmdir "$backup_dir" 2>/dev/null || true
    fi
}

ensure_clean_worktree() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        fail "Este diretório não é um repositório Git"
        exit 1
    fi

    if [ -n "$(git status --porcelain)" ]; then
        fail "Há mudanças locais no repositório. Faça commit/stash antes de atualizar."
        git status --short
        exit 1
    fi
}

update_source_checkout() {
    if [ "$SKIP_GIT" -eq 1 ]; then
        warn "Atualização Git ignorada por --skip-git"
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
    ok "Código atualizado: $current_rev -> $new_rev"
}

install_python_requirements() {
    if [ -f "$ROOT_DIR/requirements.lock" ]; then
        pip install -r "$ROOT_DIR/requirements.txt" -c "$ROOT_DIR/requirements.lock"
    else
        pip install -r "$ROOT_DIR/requirements.txt"
    fi
}

refresh_runtime() {
    if [ ! -d "$ROOT_DIR/venv" ]; then
        python3 -m venv "$ROOT_DIR/venv"
        ok "venv criado em venv/"
    fi

    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv/bin/activate"

    install_python_requirements
    python3 "$ROOT_DIR/scripts/ensure_runtime_config.py"
    python3 "$ROOT_DIR/scripts/migrate.py" apply

    local admin_username
    local admin_password
    admin_username="$(get_config_value "DEFAULT_ADMIN_USERNAME" "admin")"
    admin_password="$(get_config_value "DEFAULT_ADMIN_PASSWORD" "admin")"

    python3 "$ROOT_DIR/scripts/manage_users.py" create \
        --username "$admin_username" \
        --password "$admin_password" \
        --role admin
    python3 "$ROOT_DIR/scripts/manage_users.py" seed-defaults

    ok "Runtime Python, config, migrações e usuários atualizados"
}

refresh_frontend() {
    (
        cd "$ROOT_DIR/frontend"
        npm install
        npm run build
    )
    ok "Frontend atualizado e rebuildado"
}

print_summary() {
    echo ""
    echo -e "${BOLD}${GREEN}Atualização concluída.${NC}"
    echo -e "Config: ${CYAN}$CONFIG_FILE${NC}"
    echo ""
    echo "Para iniciar:"
    echo -e "  ${CYAN}devsynapse${NC}"
}

main() {
    echo ""
    echo -e "${BOLD}${CYAN}DevSynapse AI updater${NC}"

    step "1/6" "Verificando dependências..."
    check_system_deps

    step "2/6" "Criando backup runtime..."
    backup_runtime_state

    step "3/6" "Atualizando código..."
    update_source_checkout

    step "4/6" "Atualizando backend e runtime..."
    refresh_runtime

    step "5/6" "Atualizando frontend..."
    refresh_frontend

    step "6/6" "Conferindo migrações..."
    python3 "$ROOT_DIR/scripts/migrate.py" status

    print_summary
}

main
