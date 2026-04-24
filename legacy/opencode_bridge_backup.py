"""
Bridge para comunicação com OpenCode
"""

import subprocess
import json
import logging
import re
import shlex
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from config.settings import (
    OPENCODE_TIMEOUT, OPENCODE_MAX_OUTPUT,
    ALLOWED_COMMANDS, BLACKLISTED_PATTERNS,
    KNOWN_PROJECTS
)

logger = logging.getLogger(__name__)


class OpenCodeBridge:
    """Gerencia comunicação segura com OpenCode"""
    
    def __init__(self):
        self.allowed_commands = ALLOWED_COMMANDS
        self.blacklisted_patterns = BLACKLISTED_PATTERNS
        
    async def execute_command(self, command: str) -> Tuple[bool, str, Optional[str]]:
        """
        Executa um comando OpenCode de forma segura
        
        Returns:
            Tuple[success, result_message, output]
        """
        
        # Validar e parsear comando
        validation_result = self._validate_command(command)
        if not validation_result[0]:
            return False, validation_result[1], None
        
        command_type, args = validation_result[2], validation_result[3]
        
        try:
            # Executar comando baseado no tipo
            if command_type == "bash":
                return await self._execute_bash(args)
            elif command_type == "read":
                return await self._execute_read(args)
            elif command_type == "glob":
                return await self._execute_glob(args)
            elif command_type == "grep":
                return await self._execute_grep(args)
            elif command_type == "edit":
                return await self._execute_edit(args)
            elif command_type == "write":
                return await self._execute_write(args)
            else:
                return False, f"Comando não implementado: {command_type}", None
                
        except Exception as e:
            logger.error(f"Erro executando comando {command}: {e}")
            return False, f"Erro executando comando: {str(e)}", None
    
    def _validate_command(self, command: str) -> Tuple[bool, str, Optional[str], Optional[List]]:
        """Valida e parseia um comando OpenCode"""
        
        # Padrão: comando "argumento"
        pattern = r'^(\w+)\s+"([^"]+)"(?:\s+(.+))?$'
        match = re.match(pattern, command)
        
        if not match:
            return False, f"Formato de comando inválido: {command}", None, None
        
        command_type = match.group(1).lower()
        main_arg = match.group(2)
        extra_args = match.group(3) if match.group(3) else ""
        
        # Verificar se comando é permitido
        if command_type not in self.allowed_commands:
            return False, f"Comando não permitido: {command_type}", None, None
        
        # Verificar padrões blacklistados
        full_command = f"{command_type} {main_arg} {extra_args}".lower()
        for pattern in self.blacklisted_patterns:
            if pattern in full_command:
                return False, f"Comando contém padrão não permitido: {pattern}", None, None
        
        # Validar argumentos específicos por tipo de comando
        if command_type == "bash":
            # Validar comando bash
            if not self._validate_bash_command(main_arg):
                return False, f"Comando bash não permitido: {main_arg}", None, None
        
        elif command_type in ["read", "edit", "write"]:
            # Validar caminho de arquivo
            if not self._validate_file_path(main_arg):
                return False, f"Caminho de arquivo não permitido: {main_arg}", None, None
        
        return True, "Comando válido", command_type, [main_arg, extra_args]
    
    def _validate_bash_command(self, command: str) -> bool:
        """Valida um comando bash"""
        
        # Lista de comandos bash permitidos
        allowed_bash_commands = [
            "ls", "pwd", "cd", "cat", "head", "tail", "grep", "find",
            "git", "npm", "node", "python", "python3", "echo",
            "mkdir", "cp", "mv", "rm", "chmod", "chown",
            "df", "du", "ps", "top", "kill", "curl", "wget"
        ]
        
        # Extrair primeiro comando
        parts = shlex.split(command)
        if not parts:
            return False
        
        first_cmd = parts[0].lower()
        
        # Verificar se está na lista permitida
        if first_cmd not in allowed_bash_commands:
            return False
        
        # Verificações adicionais de segurança
        dangerous_patterns = [
            "|", ">", ">>", "<", "&", ";", "`", "$(", ".."
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command:
                # Alguns são permitidos em contextos controlados
                if pattern == "|" and "grep" in command:
                    continue  # grep com pipe é ok
                if pattern == ">" and ">" not in command[:10]:  # Não no início
                    continue
                return False
        
        return True
    
    def _validate_file_path(self, path: str) -> bool:
        """Valida um caminho de arquivo"""
        
        try:
            path_obj = Path(path).resolve()
            
            # Verificar se está dentro de diretórios permitidos
            allowed_prefixes = [
                Path("/home/irving/ruas/repos"),
                Path("/home/irving"),
                Path("/tmp"),
                Path("/var/tmp")
            ]
            
            # Verificar se o caminho começa com algum prefixo permitido
            for prefix in allowed_prefixes:
                try:
                    if path_obj.is_relative_to(prefix):
                        return True
                except ValueError:
                    continue
            
            return False
            
        except Exception:
            return False
    
    async def _execute_bash(self, args: List) -> Tuple[bool, str, Optional[str]]:
        """Executa comando bash"""
        
        command = args[0]
        
        try:
            # Executar com timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=OPENCODE_TIMEOUT,
                cwd="/home/irving"  # Diretório seguro
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            # Limitar tamanho da saída
            if len(output) > OPENCODE_MAX_OUTPUT:
                output = output[:OPENCODE_MAX_OUTPUT] + f"\n... (truncado, total: {len(output)} chars)"
            
            if result.returncode == 0:
                return True, f"Comando executado com sucesso (exit code: {result.returncode})", output
            else:
                return False, f"Comando falhou (exit code: {result.returncode})", output
                
        except subprocess.TimeoutExpired:
            return False, f"Comando expirou após {OPENCODE_TIMEOUT} segundos", None
        except Exception as e:
            return False, f"Erro executando comando: {str(e)}", None
    
    async def _execute_read(self, args: List) -> Tuple[bool, str, Optional[str]]:
        """Simula comando read do OpenCode"""
        
        filepath = args[0]
        
        try:
            path = Path(filepath)
            if not path.exists():
                return False, f"Arquivo não encontrado: {filepath}", None
            
            if not path.is_file():
                return False, f"Caminho não é um arquivo: {filepath}", None
            
            # Ler arquivo
            content = path.read_text(encoding='utf-8', errors='ignore')
            
            # Limitar tamanho
            if len(content) > OPENCODE_MAX_OUTPUT:
                content = content[:OPENCODE_MAX_OUTPUT] + f"\n... (truncado, total: {len(content)} chars)"
            
            return True, f"Arquivo lido: {filepath} ({len(content)} chars)", content
            
        except Exception as e:
            return False, f"Erro lendo arquivo: {str(e)}", None
    
    async def _execute_glob(self, args: List) -> Tuple[bool, str, Optional[str]]:
        """Simula comando glob do OpenCode"""
        
        pattern = args[0]
        
        try:
            # Encontrar arquivos que correspondem ao padrão
            import glob
            
            files = glob.glob(pattern, recursive=True)
            
            # Limitar a diretórios permitidos
            allowed_files = []
            for file in files:
                if self._validate_file_path(file):
                    allowed_files.append(file)
            
            if not allowed_files:
                return True, f"Nenhum arquivo encontrado para padrão: {pattern}", "[]"
            
            output = json.dumps(allowed_files[:50], indent=2)  # Limitar a 50 arquivos
            if len(allowed_files) > 50:
                output += f"\n... e mais {len(allowed_files) - 50} arquivos"
            
            return True, f"Encontrados {len(allowed_files)} arquivos para padrão: {pattern}", output
            
        except Exception as e:
            return False, f"Erro buscando arquivos: {str(e)}", None
    
    async def _execute_grep(self, args: List) -> Tuple[bool, str, Optional[str]]:
        """Simula comando grep do OpenCode"""
        
        pattern = args[0]
        extra_args = args[1]
        
        try:
            # Parsear argumentos extras
            include_pattern = None
            if extra_args and "--include=" in extra_args:
                include_match = re.search(r'--include="([^"]+)"', extra_args)
                if include_match:
                    include_pattern = include_match.group(1)
            
            # Usar subprocess para grep real (mais seguro que implementação própria)
            cmd = ["grep", "-r", "-n", "--color=never", pattern]
            
            if include_pattern:
                cmd.extend(["--include", include_pattern])
            
            # Diretório base seguro
            base_dir = "/home/irving/ruas/repos"
            cmd.append(base_dir)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=OPENCODE_TIMEOUT
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            # Limitar tamanho
            if len(output) > OPENCODE_MAX_OUTPUT:
                output = output[:OPENCODE_MAX_OUTPUT] + f"\n... (truncado, total: {len(output)} chars)"
            
            if result.returncode in [0, 1]:  # 0 = encontrou, 1 = não encontrou
                msg = "Busca completada" if result.returncode == 0 else "Padrão não encontrado"
                return True, msg, output
            else:
                return False, f"grep falhou (exit code: {result.returncode})", output
                
        except subprocess.TimeoutExpired:
            return False, f"Busca expirou após {OPENCODE_TIMEOUT} segundos", None
        except Exception as e:
            return False, f"Erro na busca: {str(e)}", None
    
    async def _execute_edit(self, args: List) -> Tuple[bool, str, Optional[str]]:
        """Simula comando edit do OpenCode (apenas simulação por segurança)"""
        
        filepath = args[0]
        extra_args = args[1]
        
        # Por segurança, não implementar edição real no POC
        # Em produção, isso seria implementado com verificação de backup, etc.
        
        # Extrair old/new do extra_args
        old_new_match = re.search(r'--old="([^"]+)"\s+--new="([^"]+)"', extra_args)
        if not old_new_match:
            return False, "Formato de edit inválido. Use: edit \"file\" --old=\"text\" --new=\"text\"", None
        
        old_text = old_new_match.group(1)
        new_text = old_new_match.group(2)
        
        return True, f"Simulação: Substituir '{old_text[:50]}...' por '{new_text[:50]}...' em {filepath}", None
    
    async def _execute_write(self, args: List) -> Tuple[bool, str, Optional[str]]:
        """Simula comando write do OpenCode (apenas simulação por segurança)"""
        
        filepath = args[0]
        extra_args = args[1]
        
        # Extrair conteúdo
        content_match = re.search(r'--content="([^"]+)"', extra_args)
        if not content_match:
            return False, "Formato de write inválido. Use: write \"file\" --content=\"text\"", None
        
        content = content_match.group(1)
        
        # Por segurança, não escrever arquivos reais no POC
        return True, f"Simulação: Escrever {len(content)} chars em {filepath}", None
    
    def get_project_context(self, project_name: str) -> Optional[Dict]:
        """Obtém contexto sobre um projeto específico"""
        
        if project_name in KNOWN_PROJECTS:
            return KNOWN_PROJECTS[project_name]
        
        # Tentar encontrar por nome similar
        for name, info in KNOWN_PROJECTS.items():
            if project_name.lower() in name.lower():
                return info
        
        return None