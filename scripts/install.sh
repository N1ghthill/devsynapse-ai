#!/usr/bin/env bash
#
# DevSynapse AI — Installer
#
# Configura o ambiente completo e adiciona o alias `devsynapse` ao shell.
#
# Uso:
#   bash scripts/install.sh
#
# O que faz:
#   1. Cria venv e instala dependências Python
#   2. Instala dependências do frontend (npm)
#   3. Cria .env a partir de .env.example se não existir
#   4. Executa migrações do banco
#   5. Cria usuário admin padrão
#   6. Build do frontend
#   7. Adiciona alias `devsynapse` ao ~/.bashrc

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${BOLD}${CYAN}[$1]${NC} ${BOLD}$2${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }

step "1/7" "Criando ambiente virtual Python..."
if [ ! -d "$ROOT_DIR/venv" ]; then
    python3 -m venv "$ROOT_DIR/venv"
    ok "venv criado em $ROOT_DIR/venv"
else
    ok "venv já existe"
fi

source "$ROOT_DIR/venv/bin/activate"

step "2/7" "Instalando dependências Python..."
pip install -r "$ROOT_DIR/requirements.txt" -q
ok "Dependências Python instaladas"

step "3/7" "Instalando dependências do frontend..."
cd "$ROOT_DIR/frontend"
npm install --silent 2>/dev/null
ok "Dependências frontend instaladas"
cd "$ROOT_DIR"

step "4/7" "Configurando .env..."
if [ ! -f "$ROOT_DIR/.env" ]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    ok ".env criado a partir de .env.example"
    warn "Edite .env e configure DEEPSEEK_API_KEY"
else
    ok ".env já existe"
fi

step "5/7" "Executando migrações do banco..."
python "$ROOT_DIR/scripts/migrate.py" apply
ok "Migrações aplicadas"

step "6/7" "Criando usuário admin padrão..."
python "$ROOT_DIR/scripts/manage_users.py" seed-defaults
ok "Usuário admin padrão criado"

step "7/7" "Build do frontend..."
cd "$ROOT_DIR/frontend"
npm run build --silent 2>/dev/null
ok "Frontend build concluído"
cd "$ROOT_DIR"

# ---- Alias ----

ALIAS_LINE="alias devsynapse='cd \"$ROOT_DIR\" && bash devsynapse.sh'"
ALIAS_MARKER="# >>> devsynapse alias (managed by scripts/install.sh) >>>"
ALIAS_END="# <<< devsynapse alias <<<"

setup_alias() {
    local rc_file="$1"
    if [ ! -f "$rc_file" ]; then
        touch "$rc_file"
    fi

    if grep -qF "$ALIAS_MARKER" "$rc_file" 2>/dev/null; then
        warn "Alias já configurado em $(basename "$rc_file")"
        return
    fi

    {
        echo ""
        echo "$ALIAS_MARKER"
        echo "$ALIAS_LINE"
        echo "$ALIAS_END"
    } >> "$rc_file"

    ok "Alias adicionado a $(basename "$rc_file")"
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
echo -e "${BOLD}Próximos passos:${NC}"
echo ""
echo -e "  1. Configure sua API key do DeepSeek em ${CYAN}.env${NC}:"
echo -e "     ${YELLOW}DEEPSEEK_API_KEY=sk-sua-chave-aqui${NC}"
echo ""
echo -e "  2. Reinicie o terminal ou execute:"
echo -e "     ${CYAN}source ~/.bashrc${NC}"
echo ""
echo -e "  3. Inicie o DevSynapse:"
echo -e "     ${CYAN}devsynapse${NC}"
echo ""
echo -e "${BOLD}Credenciais padrão:${NC}"
echo -e "   Login: ${GREEN}admin${NC}"
echo -e "   Senha: ${GREEN}admin${NC}"
echo ""
echo -e "${BOLD}Links rápidos:${NC}"
echo -e "   Frontend: ${CYAN}http://127.0.0.1:5173${NC}"
echo -e "   API Docs: ${CYAN}http://127.0.0.1:8000/docs${NC}"
echo ""
