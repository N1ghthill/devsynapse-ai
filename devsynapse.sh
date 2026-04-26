#!/usr/bin/env bash
#
# DevSynapse AI — CLI launcher
#
# Usage:
#   bash devsynapse.sh          # from the project directory
#   devsynapse                  # via the bash alias (set up by scripts/install.sh)
#   devsynapse update           # update code, dependencies, migrations and frontend build
#
# Compatibility: Debian / Ubuntu and close apt-based Linux distributions.
# Starts the backend and frontend, then prints connection info and credentials.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
APP_ID="devsynapse-ai"

if [ -n "${DEVSYNAPSE_HOME:-}" ]; then
    RUNTIME_HOME="${DEVSYNAPSE_HOME/#\~/$HOME}"
    CONFIG_DIR="${DEVSYNAPSE_CONFIG_DIR:-$RUNTIME_HOME/config}"
    DEFAULT_DATA_DIR="${DEVSYNAPSE_DATA_DIR:-$RUNTIME_HOME/data}"
else
    CONFIG_DIR="${DEVSYNAPSE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/$APP_ID}"
    DEFAULT_DATA_DIR="${DEVSYNAPSE_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID/data}"
fi
CONFIG_FILE="${DEVSYNAPSE_CONFIG_FILE:-$CONFIG_DIR/.env}"
export DEVSYNAPSE_CONFIG_FILE="$CONFIG_FILE"
APP_VERSION="$(awk -F\" '/app_version: str =/ {print $2; exit}' "$SCRIPT_DIR/config/settings.py" 2>/dev/null || true)"
APP_VERSION="${APP_VERSION:-unknown}"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
    local text="DevSynapse AI v$APP_VERSION"
    local width=50
    local left
    local right
    left=$(( (width - ${#text}) / 2 ))
    right=$(( width - ${#text} - left ))

    echo ""
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    printf "%b║%*s%s%*s║%b\n" "$CYAN$BOLD" "$left" "" "$text" "$right" "" "$NC"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

usage() {
    cat <<'EOF'
DevSynapse AI

Usage:
  devsynapse
  devsynapse start
  devsynapse update [--version vX.Y.Z]
  devsynapse uninstall
  devsynapse help
EOF
}

check_cli_tools() {
    local missing=()

    if ! command -v python3 >/dev/null 2>&1; then
        missing+=("python3")
    fi
    if ! command -v npm >/dev/null 2>&1; then
        missing+=("npm")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${RED}✗ Ferramentas não encontradas: ${missing[*]}${NC}"
        echo "  Instale com: sudo apt install python3 python3-venv python3-pip nodejs npm"
        return 1
    fi
    return 0
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

check_requirements() {
    if ! check_cli_tools; then
        return 1
    fi

    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${YELLOW}⚠  Configuração runtime não encontrada. Execute 'bash scripts/install.sh' primeiro.${NC}"
        echo -e "   Esperado: ${CYAN}$CONFIG_FILE${NC}"
        return 1
    fi

    local has_key=0
    local key_value=""
    if grep -qE '^DEEPSEEK_API_KEY=' "$CONFIG_FILE" 2>/dev/null; then
        key_value=$(grep -E '^DEEPSEEK_API_KEY=' "$CONFIG_FILE" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
        if [ -n "$key_value" ] \
           && [ "$key_value" != "your-key-here" ] \
           && [ "$key_value" != "sk-your-key-here" ] \
           && [ "${key_value:0:3}" = "sk-" ]; then
            has_key=1
        fi
    fi

    if [ "$has_key" -eq 0 ]; then
        echo -e "${YELLOW}⚠  DEEPSEEK_API_KEY inválida ou não configurada no runtime${NC}"
        echo "   Edite $CONFIG_FILE:  DEEPSEEK_API_KEY=sk-sua-chave-aqui"
        return 1
    fi

    local memory_db_path
    memory_db_path=$(get_env_value "MEMORY_DB_PATH" "$DEFAULT_DATA_DIR/devsynapse_memory.db")
    if [ ! -d "venv" ] || [ ! -d "frontend/node_modules" ] || [ ! -f "$memory_db_path" ]; then
        echo -e "${YELLOW}⚠  Setup incompleto. Execute 'bash scripts/install.sh'.${NC}"
        return 1
    fi

    return 0
}

source_venv() {
    if [ -f "venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        source venv/bin/activate
    fi
}

get_admin_password() {
    local password=""
    if [ -f "$CONFIG_FILE" ]; then
        password=$(grep -E '^DEFAULT_ADMIN_PASSWORD=' "$CONFIG_FILE" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
    fi
    echo "${password:-admin}"
}

get_api_key_status() {
    if [ -f "$CONFIG_FILE" ]; then
        local key=""
        key=$(grep -E '^DEEPSEEK_API_KEY=' "$CONFIG_FILE" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
        if [ -n "$key" ] && [ "${key:0:3}" = "sk-" ]; then
            echo -e "${GREEN}configurada${NC}"
            return
        fi
    fi
    echo -e "${RED}não configurada${NC}"
}

print_info() {
    local admin_password
    admin_password=$(get_admin_password)

    echo ""
    echo -e "${BOLD}🔗 URLs de acesso:${NC}"
    echo -e "   Frontend  → ${CYAN}http://127.0.0.1:5173${NC}"
    echo -e "   API Docs  → ${CYAN}http://127.0.0.1:8000/docs${NC}"
    echo -e "   Health    → ${CYAN}http://127.0.0.1:8000/health${NC}"
    echo ""
    echo -e "${BOLD}🔑 Credenciais padrão:${NC}"
    echo -e "   Usuário   → ${GREEN}admin${NC}"
    if [ "$admin_password" = "admin" ]; then
        echo -e "   Senha     → ${GREEN}admin${NC}"
    else
        echo -e "   Senha     → ${GREEN}valor atual de DEFAULT_ADMIN_PASSWORD no runtime${NC}"
    fi
    echo ""
    echo -e "${BOLD}🔌 API Key DeepSeek:${NC} $(get_api_key_status)"
    echo -e "${BOLD}⚙️  Config:${NC} ${CYAN}$CONFIG_FILE${NC}"
    echo ""
    echo -e "${BOLD}Pressione Ctrl+C para parar.${NC}"
    echo ""
}

cleanup() {
    echo ""
    echo -e "${YELLOW}Parando DevSynapse...${NC}"

    if [ -n "${BACKEND_PID:-}" ]; then
        stop_process_group "$BACKEND_PID"
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        stop_process_group "$FRONTEND_PID"
    fi

    wait 2>/dev/null || true
    echo -e "${GREEN}DevSynapse parado.${NC}"
    exit 0
}

stop_process_group() {
    local pid="$1"
    local attempts=0

    if ! kill -0 "$pid" 2>/dev/null; then
        return
    fi

    kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true

    while kill -0 "$pid" 2>/dev/null && [ "$attempts" -lt 50 ]; do
        sleep 0.1
        attempts=$((attempts + 1))
    done

    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    fi
}

start() {
    banner

    if ! check_requirements; then
        exit 1
    fi

    source_venv

    echo -e "${GREEN}Iniciando servidores...${NC}"

    setsid bash -c 'set -o pipefail; python3 -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload --log-level warning 2>&1 | sed "s/^/[backend] /"' &
    BACKEND_PID=$!

    sleep 1.5

    setsid bash -c 'set -o pipefail; cd frontend && npm run dev -- --host 127.0.0.1 2>&1 | sed "s/^/[frontend] /"' &
    FRONTEND_PID=$!

    trap cleanup SIGINT SIGTERM

    sleep 2
    print_info

    wait 2>/dev/null || true
}

main() {
    local command="${1:-start}"
    if [ "$#" -gt 0 ]; then
        shift
    fi

    case "$command" in
        start|run)
            start "$@"
            ;;
        update)
            exec bash "$SCRIPT_DIR/scripts/update.sh" "$@"
            ;;
        uninstall)
            exec bash "$SCRIPT_DIR/scripts/uninstall.sh" "$@"
            ;;
        help|-h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Comando desconhecido: $command${NC}"
            usage
            exit 1
            ;;
    esac
}

main "$@"
