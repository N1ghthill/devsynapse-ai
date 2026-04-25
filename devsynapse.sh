#!/usr/bin/env bash
#
# DevSynapse AI — CLI launcher
#
# Usage:
#   bash devsynapse.sh          # from the project directory
#   devsynapse                  # via the bash alias (set up by scripts/install.sh)
#
# Starts the backend and frontend, then prints connection info and credentials.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
    echo ""
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║              DevSynapse AI v0.3.0               ║${NC}"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_requirements() {
    local missing=()

    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}⚠  .env não encontrado. Execute 'bash scripts/install.sh' primeiro.${NC}"
        echo "   Ou copie .env.example para .env e configure DEEPSEEK_API_KEY."
        return 1
    fi

    if ! grep -q "DEEPSEEK_API_KEY=" .env 2>/dev/null || grep -q 'DEEPSEEK_API_KEY=$' .env 2>/dev/null; then
        echo -e "${YELLOW}⚠  DEEPSEEK_API_KEY não configurada no .env${NC}"
        echo "   Edite .env e adicione sua API key do DeepSeek."
        return 1
    fi

    if [ ! -d "venv" ]; then
        missing+=("venv")
    fi
    if [ ! -d "frontend/node_modules" ]; then
        missing+=("frontend/node_modules")
    fi
    if [ ! -f "data/devsynapse_memory.db" ]; then
        missing+=("data/")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠  Artefatos faltando: ${missing[*]}${NC}"
        echo "   Execute 'bash scripts/install.sh' para configurar."
        return 1
    fi

    return 0
}

source_venv() {
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    fi
}

get_admin_password() {
    local password=""
    if [ -f ".env" ]; then
        password=$(grep -E '^DEFAULT_ADMIN_PASSWORD=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
    fi
    if [ -z "$password" ]; then
        password="admin"
    fi
    echo "$password"
}

get_api_key_status() {
    if [ -f ".env" ]; then
        local key=""
        key=$(grep -E '^DEEPSEEK_API_KEY=' .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        if [ -n "$key" ] && [ "$key" != "your-key-here" ] && [ "$key" != "sk-" ]; then
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
    echo -e "   Senha     → ${GREEN}${admin_password}${NC}"
    echo ""
    echo -e "${BOLD}🔌 API Key DeepSeek:${NC} $(get_api_key_status)"
    echo ""
    echo -e "${BOLD}Pressione Ctrl+C para parar.${NC}"
    echo ""
}

cleanup() {
    echo ""
    echo -e "${YELLOW}Parando DevSynapse...${NC}"

    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi

    wait 2>/dev/null || true
    echo -e "${GREEN}DevSynapse parado.${NC}"
    exit 0
}

start() {
    banner

    if ! check_requirements; then
        exit 1
    fi

    source_venv

    echo -e "${GREEN}Iniciando servidores...${NC}"

    python -m uvicorn api.app:app \
        --host 127.0.0.1 \
        --port 8000 \
        --reload \
        --log-level warning \
        2>&1 | sed 's/^/[backend] /' &
    BACKEND_PID=$!

    sleep 1.5

    (cd frontend && npm run dev -- --host 127.0.0.1 2>&1) | sed 's/^/[frontend] /' &
    FRONTEND_PID=$!

    trap cleanup SIGINT SIGTERM

    sleep 2
    print_info

    wait
}

start
