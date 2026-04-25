#!/usr/bin/env bash
#
# DevSynapse AI — Uninstaller
#
# Remove os artefatos locais do DevSynapse, os aliases do shell,
# e opcionalmente os dados runtime e o diretório do projeto.
#
# Uso:
#   uninstall-devsynapse     # via alias (configurado pelo install.sh)
#   bash scripts/uninstall.sh

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

MEMORY_DB_FILE="$(get_config_value "MEMORY_DB_PATH" "$DATA_DIR/devsynapse_memory.db")"
LOG_FILE="$(get_config_value "LOG_FILE" "$LOGS_DIR/devsynapse.log")"
DATA_DIR="$(dirname "$MEMORY_DB_FILE")"
LOGS_DIR="$(dirname "$LOG_FILE")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
info() { echo -e "  ${CYAN}→${NC} $1"; }

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

    sed -e "/^${ALIAS_BLOCK_START}/,/^${ALIAS_BLOCK_END}/d" "$rc_file" > "$tmp_file"
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
    echo -e "  ${YELLOW}⚠  Isso inclui histórico de conversas e telemetria em:${NC}"
    echo -e "     ${CYAN}$DATA_DIR${NC}"
    echo -e "     ${CYAN}$LOGS_DIR${NC}"
    echo ""
    read -r -p "  Remover dados e logs runtime? [s/N]: " delete_data

    if [ "${delete_data,,}" = "s" ] || [ "${delete_data,,}" = "sim" ]; then
        remove_if_exists "$DATA_DIR" "runtime data/"
        remove_if_exists "$LOGS_DIR" "runtime logs/"
    else
        info "dados e logs runtime mantidos"
    fi

    # 5. Runtime config file
    echo ""
    echo -e "${BOLD}5. Arquivo de configuração runtime...${NC}"

    local delete_env="n"
    echo ""
    echo -e "  O arquivo ${CYAN}$CONFIG_FILE${NC} contém sua API key do DeepSeek."
    echo ""
    read -r -p "  Remover configuração runtime? [s/N]: " delete_env

    if [ "${delete_env,,}" = "s" ] || [ "${delete_env,,}" = "sim" ]; then
        remove_if_exists "$CONFIG_FILE" "configuração runtime"
    else
        info "configuração runtime mantida (contém sua API key)"
    fi

    # 6. Project directory
    echo ""
    echo -e "${BOLD}6. Diretório do projeto...${NC}"

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
