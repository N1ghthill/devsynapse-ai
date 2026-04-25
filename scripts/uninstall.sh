#!/usr/bin/env bash
#
# DevSynapse AI — Uninstaller
#
# Remove os artefatos locais do DevSynapse, os aliases do shell,
# e opcionalmente os dados e o diretório do projeto.
#
# Uso:
#   uninstall-devsynapse     # via alias (configurado pelo install.sh)
#   bash scripts/uninstall.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

ALIAS_MARKER="# >>> devsynapse alias (managed by scripts/install.sh) >>>"
ALIAS_UNINSTALL_MARKER="# >>> uninstall-devsynapse alias (managed by scripts/install.sh) >>>"

ALIAS_BLOCK_START="# >>> devsynapse"
ALIAS_BLOCK_END="# <<< devsynapse"

REMOVED_ANYTHING=0

remove_if_exists() {
    local target="$1"
    local label="${2:-$target}"
    if [ -e "$target" ]; then
        rm -rf "$target"
        ok "$label removido"
        REMOVED_ANYTHING=1
    else
        info "$label não encontrado, pulando"
    fi
}

remove_alias_block() {
    local rc_file="$1"
    local rc_name
    rc_name=$(basename "$rc_file")

    if [ ! -f "$rc_file" ]; then
        return
    fi

    if ! grep -qF "$ALIAS_BLOCK_START" "$rc_file" 2>/dev/null; then
        return
    fi

    local tmp_file
    tmp_file="${rc_file}.devsynapse_tmp"

    sed -e "/^# >>> devsynapse/,/^# <<< devsynapse/d" "$rc_file" > "$tmp_file"
    mv "$tmp_file" "$rc_file"

    ok "Aliases removidos de $rc_name"
    REMOVED_ANYTHING=1
}

main() {
    echo ""
    echo -e "${BOLD}${RED}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${RED}║         DevSynapse AI — Desinstalação           ║${NC}"
    echo -e "${BOLD}${RED}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Este script remove artefatos locais do DevSynapse."
    echo "Seus arquivos de projeto e repositórios NÃO serão afetados."
    echo ""

    # 1. Shell aliases
    echo -e "${BOLD}1. Removendo aliases do shell...${NC}"
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.bash_aliases"; do
        remove_alias_block "$rc"
    done

    # 2. Python venv
    echo ""
    echo -e "${BOLD}2. Removendo ambiente virtual Python...${NC}"
    remove_if_exists "$ROOT_DIR/venv" "venv/"

    # 3. Frontend artifacts
    echo ""
    echo -e "${BOLD}3. Removendo artefatos do frontend...${NC}"
    remove_if_exists "$ROOT_DIR/frontend/node_modules" "frontend/node_modules/"
    remove_if_exists "$ROOT_DIR/frontend/dist" "frontend/dist/"

    # 4. Database and logs
    echo ""
    echo -e "${BOLD}4. Removendo dados e logs locais...${NC}"

    local delete_data="n"
    echo ""
    echo -e "  ${YELLOW}⚠  Isso inclui histórico de conversas e telemetria.${NC}"
    echo ""
    read -r -p "  Remover diretório data/ e logs/? [s/N]: " delete_data

    if [ "${delete_data,,}" = "s" ] || [ "${delete_data,,}" = "sim" ]; then
        remove_if_exists "$ROOT_DIR/data" "data/"
        remove_if_exists "$ROOT_DIR/logs" "logs/"
    else
        info "data/ e logs/ mantidos"
    fi

    # 5. .env file
    echo ""
    echo -e "${BOLD}5. Arquivo .env...${NC}"

    local delete_env="n"
    echo ""
    echo -e "  O arquivo ${CYAN}.env${NC} contém sua API key do DeepSeek."
    echo ""
    read -r -p "  Remover .env? [s/N]: " delete_env

    if [ "${delete_env,,}" = "s" ] || [ "${delete_env,,}" = "sim" ]; then
        remove_if_exists "$ROOT_DIR/.env" ".env"
    else
        info ".env mantido (contém sua API key)"
    fi

    # 6. Project directory
    echo ""
    echo -e "${BOLD}6. Diretório do projeto...${NC}"

    local delete_project="n"
    echo ""
    echo -e "  Para remover completamente, delete o diretório:"
    echo -e "  ${CYAN}rm -rf $ROOT_DIR${NC}"
    echo ""

    # Conclusão
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║       DevSynapse AI desinstalado com sucesso!    ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    if [ "$REMOVED_ANYTHING" -eq 0 ]; then
        echo "Nenhum artefato encontrado para remover."
    fi

    echo "Execute 'source ~/.bashrc' para recarregar o shell."
    echo ""
}

main
