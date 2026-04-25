#!/usr/bin/env bash
#
# DevSynapse AI — Installer
#
# Compatibilidade: Debian / Ubuntu (requer bash, python3, npm).
#
# Uso:
#   bash scripts/install.sh
#
# O que faz:
#   1. Verifica dependências de sistema (python3, python3-venv, npm)
#   2. Cria venv e instala dependências Python
#   3. Instala dependências do frontend (npm)
#   4. Cria .env a partir de .env.example se não existir
#   5. Executa migrações do banco
#   6. Cria usuário admin padrão (admin / admin)
#   7. Build do frontend para produção
#   8. Adiciona alias `devsynapse` ao ~/.bashrc e ~/.zshrc

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${BOLD}${CYAN}[$1]${NC} ${BOLD}$2${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }

# ---- System dependency check ----

check_system_deps() {
    local missing=()

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
        echo -e "  ${BOLD}sudo apt update && sudo apt install -y python3 python3-venv python3-pip nodejs npm${NC}"
        echo ""
        return 1
    fi

    ok "python3, venv e npm encontrados"
    return 0
}

# ---- Instalação ----

install() {
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║        DevSynapse AI Installer v0.3.0           ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"

    step "1/8" "Verificando dependências de sistema..."
    if ! check_system_deps; then
        exit 1
    fi

    step "2/8" "Criando ambiente virtual Python..."
    if [ ! -d "$ROOT_DIR/venv" ]; then
        python3 -m venv "$ROOT_DIR/venv" || {
            fail "Falha ao criar venv"
            exit 1
        }
        ok "venv criado em venv/"
    else
        ok "venv já existe"
    fi

    # shellcheck disable=SC1091
    source "$ROOT_DIR/venv/bin/activate"

    step "3/8" "Instalando dependências Python..."
    pip install -r "$ROOT_DIR/requirements.txt" 2>&1 | tail -3
    ok "Dependências Python instaladas"

    step "4/8" "Instalando dependências do frontend..."
    cd "$ROOT_DIR/frontend"
    npm install 2>&1 | tail -3
    ok "Dependências frontend instaladas"
    cd "$ROOT_DIR"

    step "5/8" "Configurando .env..."
    local api_key=""

    if [ ! -f "$ROOT_DIR/.env" ]; then
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
        ok ".env criado a partir de .env.example"
    else
        ok ".env já existe"
    fi

    echo ""
    echo -e "  ${BOLD}DeepSeek API Key${NC}"
    echo -e "  Necessária para o chat funcionar. Obtenha em ${CYAN}https://platform.deepseek.com/api_keys${NC}"
    echo ""
    read -r -p "  Cole sua API key (ou Enter para pular): " api_key
    echo ""

    if [ -n "$api_key" ]; then
        api_key=$(echo "$api_key" | xargs)
        if [ "${api_key:0:3}" != "sk-" ]; then
            warn "A chave não começa com 'sk-'. Será salva mesmo assim, mas pode não funcionar."
        fi
        if grep -qE '^DEEPSEEK_API_KEY=' "$ROOT_DIR/.env" 2>/dev/null; then
            sed -i "s|^DEEPSEEK_API_KEY=.*|DEEPSEEK_API_KEY=$api_key|" "$ROOT_DIR/.env"
        else
            echo "DEEPSEEK_API_KEY=$api_key" >> "$ROOT_DIR/.env"
        fi
        ok "API key configurada"
    else
        echo -e "  ${YELLOW}⚠  API key não configurada. Edite .env manualmente antes de iniciar:${NC}"
        echo -e "     ${CYAN}DEEPSEEK_API_KEY=sk-sua-chave-aqui${NC}"
        echo ""
    fi

    step "6/8" "Executando migrações do banco..."
    python3 "$ROOT_DIR/scripts/migrate.py" apply || {
        fail "Falha nas migrações"
        exit 1
    }
    ok "Migrações aplicadas"

    step "7/8" "Criando usuário admin padrão..."
    python3 "$ROOT_DIR/scripts/manage_users.py" seed-defaults || {
        fail "Falha ao criar usuário"
        exit 1
    }
    ok "Usuário admin padrão criado (admin / admin)"

    step "8/8" "Build do frontend para produção..."
    cd "$ROOT_DIR/frontend"
    npm run build 2>&1 | tail -3
    ok "Frontend build concluído"
    cd "$ROOT_DIR"

    # ---- Alias ----

    ALIAS_LINE="alias devsynapse='cd \"$ROOT_DIR\" && bash devsynapse.sh'"
    ALIAS_MARKER="# >>> devsynapse alias (managed by scripts/install.sh) >>>"
    ALIAS_END="# <<< devsynapse alias <<<"

    setup_alias() {
        local rc_file="$1"
        local rc_name
        rc_name=$(basename "$rc_file")

        if [ ! -f "$rc_file" ]; then
            touch "$rc_file"
        fi

        if grep -qF "$ALIAS_MARKER" "$rc_file" 2>/dev/null; then
            warn "Alias já configurado em $rc_name"
            return
        fi

        {
            echo ""
            echo "$ALIAS_MARKER"
            echo "$ALIAS_LINE"
            echo "$ALIAS_END"
        } >> "$rc_file"

        ok "Alias adicionado a $rc_name"
    }

    echo ""
    echo -e "${BOLD}${CYAN}Configurando alias...${NC}"

    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        setup_alias "$rc"
    done

    # ---- Conclusão ----

    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║       DevSynapse AI instalado com sucesso!       ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    local has_key=0
    if grep -qE '^DEEPSEEK_API_KEY=sk-' "$ROOT_DIR/.env" 2>/dev/null; then
        has_key=1
    fi

    if [ "$has_key" -eq 0 ]; then
        echo -e "${YELLOW}⚠  Configure sua API key do DeepSeek antes de iniciar:${NC}"
        echo -e "   Edite ${CYAN}.env${NC} e defina:"
        echo -e "   ${YELLOW}DEEPSEEK_API_KEY=sk-sua-chave-aqui${NC}"
        echo ""
    fi

    echo -e "${BOLD}Para começar:${NC}"
    echo ""
    echo -e "  1. Reinicie o terminal ou execute:"
    echo -e "     ${CYAN}source ~/.bashrc${NC}"
    echo ""
    echo -e "  2. Inicie o DevSynapse:"
    echo -e "     ${CYAN}devsynapse${NC}"
    echo ""
    echo -e "${BOLD}Credenciais padrão:${NC}"
    echo -e "   Login: ${GREEN}admin${NC}"
    echo -e "   Senha: ${GREEN}admin${NC}"
    echo ""
    echo -e "${BOLD}Links (após iniciar):${NC}"
    echo -e "   Frontend: ${CYAN}http://127.0.0.1:5173${NC}"
    echo -e "   API Docs: ${CYAN}http://127.0.0.1:8000/docs${NC}"
    echo ""
}

install
