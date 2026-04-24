#!/usr/bin/env python3
"""
DevSynapse Proof of Concept - Bridge OpenCode + Deepseek

Este script demonstra:
1. Conversação com Deepseek API
2. Tradução para comandos OpenCode
3. Execução de comandos reais
4. Memória básica da conversa
"""

import os
import json
import sqlite3
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Configurações
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MEMORY_DB = "devsynapse_memory.db"

class DevSynapsePOC:
    def __init__(self):
        """Inicializa DevSynapse com memória e conexão Deepseek"""
        self.api_key = DEEPSEEK_API_KEY
        self.conversation_history = []
        self.init_memory()
        self.init_opencode_context()
        
    def init_memory(self):
        """Inicializa banco de dados SQLite para memória"""
        self.conn = sqlite3.connect(MEMORY_DB)
        cursor = self.conn.cursor()
        
        # Tabela de conversas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                user_message TEXT,
                ai_response TEXT,
                opencode_command TEXT,
                success INTEGER
            )
        ''')
        
        # Tabela de preferências do Irving
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT,
                learned_from TEXT,
                confidence REAL
            )
        ''')
        
        # Inserir preferências iniciais (baseado no que sabemos)
        initial_prefs = [
            ("coding_style", "clean_simple", "observed", 0.8),
            ("cost_preference", "low_cost_first", "observed", 0.9),
            ("project_priority", "botassist_high", "assumed", 0.7),
            ("communication_style", "direct_conversational", "observed", 0.85)
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO preferences (key, value, learned_from, confidence)
            VALUES (?, ?, ?, ?)
        ''', initial_prefs)
        
        self.conn.commit()
        
    def init_opencode_context(self):
        """Coleta contexto sobre o ambiente OpenCode/projetos"""
        self.projects = {}
        repos_path = "/home/irving/ruas/repos"
        
        try:
            projects = os.listdir(repos_path)
            for project in projects:
                project_path = os.path.join(repos_path, project)
                if os.path.isdir(project_path):
                    # Verifica se é repositório git
                    git_path = os.path.join(project_path, ".git")
                    if os.path.exists(git_path):
                        self.projects[project] = {
                            "path": project_path,
                            "is_git": True
                        }
                    else:
                        self.projects[project] = {
                            "path": project_path,
                            "is_git": False
                        }
        except Exception as e:
            print(f"⚠️  Erro ao escanear projetos: {e}")
            self.projects = {}
    
    def get_user_preferences(self) -> str:
        """Retorna preferências do Irving como contexto"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value, confidence FROM preferences ORDER BY confidence DESC")
        prefs = cursor.fetchall()
        
        preferences_text = "Preferências conhecidas do Irving:\n"
        for key, value, confidence in prefs:
            preferences_text += f"- {key}: {value} (confiança: {confidence:.0%})\n"
        
        return preferences_text
    
    def call_deepseek(self, user_message: str) -> str:
        """Chama API do Deepseek com contexto personalizado"""
        if not self.api_key:
            return "❌ Erro: DEEPSEEK_API_KEY não configurada. Configure com: export DEEPSEEK_API_KEY='sua-chave-aqui'"
        
        # Construir contexto personalizado
        system_prompt = f"""Você é DevSynapse, assistente de desenvolvimento inteligente do Irving Ruas (N1ghthill).

{self.get_user_preferences()}

PROJETOS DISPONÍVEIS:
{json.dumps(list(self.projects.keys()), indent=2)}

SUAS HABILIDADES:
1. Conversar naturalmente com Irving
2. Analisar problemas técnicos
3. Sugerir comandos OpenCode apropriados
4. Aprender com feedback do Irving

FORMATO DE RESPOSTA:
- Seja conversacional mas técnico
- Sugira comandos OpenCode quando relevante
- Considere as preferências do Irving
- Seja honesto sobre limitações

COMANDOS OPENCODE DISPONÍVEIS:
- bash: Executar comandos shell
- read: Ler arquivos
- glob: Buscar arquivos por padrão
- grep: Buscar conteúdo
- edit: Editar arquivos
- write: Escrever arquivos

Exemplo: "Para listar arquivos no BotAssist, use: bash 'ls /home/irving/ruas/repos/botassist-whatsapp'"
"""
        
        # Preparar mensagens
        messages = [
            {"role": "system", "content": system_prompt},
            *self.conversation_history[-6:],  # Últimas 6 mensagens como contexto
            {"role": "user", "content": user_message}
        ]
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"]
            
            # Extrair possível comando OpenCode da resposta
            opencode_command = self.extract_opencode_command(ai_response)
            
            # Salvar na memória
            self.save_to_memory(user_message, ai_response, opencode_command)
            
            return ai_response
            
        except requests.exceptions.RequestException as e:
            return f"❌ Erro na API Deepseek: {e}"
        except Exception as e:
            return f"❌ Erro inesperado: {e}"
    
    def extract_opencode_command(self, response: str) -> Optional[str]:
        """Tenta extrair comando OpenCode da resposta do AI"""
        # Padrões simples para detectar comandos
        patterns = [
            "bash '", "bash \"", "read '", "read \"",
            "glob '", "glob \"", "grep '", "grep \"",
            "edit '", "edit \"", "write '", "write \""
        ]
        
        for pattern in patterns:
            if pattern in response.lower():
                # Encontra o comando (simplificado)
                start = response.lower().find(pattern)
                # Tenta extrair até o próximo quote
                quote_char = response[start + len(pattern) - 1]
                end = response.find(quote_char, start + len(pattern))
                
                if end != -1:
                    command = response[start:end+1]
                    return command
        
        return None
    
    def execute_opencode_command(self, command: str) -> str:
        """Executa um comando OpenCode (simulado por enquanto)"""
        if not command:
            return "Nenhum comando para executar"
        
        # Simulação - em produção, integraria com OpenCode real
        print(f"🔧 Executando comando OpenCode: {command}")
        
        # Para prova de conceito, só mostra o que faria
        if command.startswith("bash "):
            cmd = command[5:].strip("'\"")
            return f"📟 Executaria no bash: {cmd}\n(Em produção, executaria realmente)"
        elif command.startswith("read "):
            filepath = command[5:].strip("'\"")
            return f"📖 Leria arquivo: {filepath}"
        elif command.startswith("glob "):
            pattern = command[5:].strip("'\"")
            return f"🔍 Buscaria padrão: {pattern}"
        
        return f"Comando reconhecido: {command}"
    
    def save_to_memory(self, user_msg: str, ai_resp: str, command: Optional[str]):
        """Salva interação na memória"""
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO conversations (timestamp, user_message, ai_response, opencode_command, success)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, user_msg, ai_resp, command, 1))
        
        self.conn.commit()
        
        # Manter histórico em memória também
        self.conversation_history.extend([
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": ai_resp}
        ])
    
    def learn_from_feedback(self, feedback: str):
        """Aprende com feedback explícito do usuário"""
        # Implementação simplificada
        print(f"📚 Aprendendo com feedback: {feedback}")
        # Em versão completa, atualizaria preferências
    
    def chat_loop(self):
        """Loop principal de chat"""
        print("=" * 60)
        print("🤖 DevSynapse Proof of Concept - OpenCode + Deepseek")
        print("=" * 60)
        print(f"📁 Projetos detectados: {len(self.projects)}")
        print("💬 Digite 'sair' para encerrar")
        print("💡 Exemplo: 'Mostre os arquivos do BotAssist'")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n👤 Irving: ").strip()
                
                if user_input.lower() in ['sair', 'exit', 'quit']:
                    print("\n👋 Até logo, Irving!")
                    break
                
                if not user_input:
                    continue
                
                # Chamar Deepseek
                print("\n🤖 DevSynapse pensando...")
                response = self.call_deepseek(user_input)
                
                print(f"\n🤖 DevSynapse: {response}")
                
                # Verificar se há comando para executar
                command = self.extract_opencode_command(response)
                if command:
                    execute = input(f"\n⚡ Executar comando '{command}'? (s/n): ").strip().lower()
                    if execute == 's':
                        result = self.execute_opencode_command(command)
                        print(f"\n🔧 Resultado: {result}")
                
                # Feedback opcional
                feedback = input("\n💭 Feedback (enter para pular): ").strip()
                if feedback:
                    self.learn_from_feedback(feedback)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Interrompido pelo usuário")
                break
            except Exception as e:
                print(f"\n❌ Erro: {e}")
    
    def __del__(self):
        """Limpeza"""
        if hasattr(self, 'conn'):
            self.conn.close()

def main():
    """Função principal"""
    print("🚀 Inicializando DevSynapse POC...")
    
    # Verificar API key
    if not DEEPSEEK_API_KEY:
        print("⚠️  AVISO: DEEPSEEK_API_KEY não configurada")
        print("Configure com:")
        print("  export DEEPSEEK_API_KEY='sua-chave-aqui'")
        print("Ou adicione ao ~/.bashrc")
        print("\nContinuando em modo simulado...")
    
    devsynapse = DevSynapsePOC()
    devsynapse.chat_loop()

if __name__ == "__main__":
    main()