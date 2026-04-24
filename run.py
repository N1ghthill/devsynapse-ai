#!/usr/bin/env python3
"""
Script principal para executar o DevSynapse AI.
"""

import os
import sys
from pathlib import Path

# Adicionar diretório atual ao path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Função principal"""
    
    print("""
    DevSynapse AI - Assistente de Desenvolvimento Inteligente
    ========================================================
    
    Modos disponíveis:

    1. API Server    - Inicia servidor FastAPI
    2. Health Check  - Verifica configuração
    3. Install Deps  - Instala dependências

    Escolha um modo (1-3) ou 'q' para sair:
    """)
    
    choice = input("> ").strip()
    
    if choice == "1":
        from api.server import run_server
        run_server()
        
    elif choice == "2":
        from config.settings import validate_config
        errors = validate_config()
        if errors:
            print("❌ Problemas de configuração:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("✅ Configuração OK")
            
        # Verificar API key
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if api_key:
            print(f"✅ Deepseek API Key: Configurada ({len(api_key)} chars)")
        else:
            print("❌ Deepseek API Key: Não configurada")
            print("   Configure com: export DEEPSEEK_API_KEY='sua-chave'")
            
    elif choice == "3":
        print("Instalando dependências...")
        os.system("pip install -r requirements.txt")
        
    elif choice.lower() in ["q", "quit", "exit"]:
        print("Até logo! 👋")
        
    else:
        print("Opção inválida")

if __name__ == "__main__":
    main()
