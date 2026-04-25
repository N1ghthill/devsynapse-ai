"""
Bridge para comunicação com OpenCode
"""

import json
import logging
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.settings import (
    ADMIN_ONLY_BASH_COMMANDS,
    ADMIN_ONLY_COMMANDS,
    ALLOWED_BASH_COMMANDS,
    ALLOWED_COMMANDS,
    ALLOWED_DIRECTORIES,
    ALLOWED_FILE_EXTENSIONS,
    BLACKLISTED_PATTERNS,
    KNOWN_PROJECTS,
    MAX_EDIT_SIZE,
    OPENCODE_BACKUP_ENABLED,
    OPENCODE_BACKUP_SUFFIX,
    OPENCODE_MAX_OUTPUT,
    OPENCODE_TIMEOUT,
    READ_ONLY_COMMANDS,
    USER_BASH_COMMANDS,
    get_settings,
)
from core.monitoring import monitoring_system
from core.plugin_system import plugin_manager

logger = logging.getLogger(__name__)


CommandExecutionTuple = Tuple[bool, str, Optional[str], str, Optional[str], Optional[str]]


class OpenCodeBridge:
    """Gerencia comunicação segura com OpenCode"""
    
    def __init__(
        self,
        known_projects: Optional[Dict[str, Dict[str, str]]] = None,
        allowed_directories: Optional[List[str]] = None,
    ):
        self.allowed_commands = ALLOWED_COMMANDS
        self.allowed_bash_commands = ALLOWED_BASH_COMMANDS
        self.read_only_commands = READ_ONLY_COMMANDS
        self.user_bash_commands = USER_BASH_COMMANDS
        self.admin_only_commands = ADMIN_ONLY_COMMANDS
        self.admin_only_bash_commands = ADMIN_ONLY_BASH_COMMANDS
        self.blacklisted_patterns = BLACKLISTED_PATTERNS
        self.known_projects = known_projects if known_projects is not None else KNOWN_PROJECTS
        directory_source = allowed_directories if allowed_directories is not None else ALLOWED_DIRECTORIES
        self.allowed_directories = [Path(d) for d in directory_source]
        self.allowed_file_extensions = ALLOWED_FILE_EXTENSIONS
        self.backup_enabled = OPENCODE_BACKUP_ENABLED
        self.backup_suffix = OPENCODE_BACKUP_SUFFIX
        
    async def execute_command(
        self,
        command: str,
        user_id: Optional[str] = None,
        project_name: Optional[str] = None,
        user_role: str = "user",
        project_mutation_allowlist: Optional[List[str]] = None,
    ) -> CommandExecutionTuple:
        """
        Executa um comando OpenCode de forma segura
        
        Returns:
            Tuple[success, result_message, output]
        """
        
        start_time = time.time()
        
        before_event = await plugin_manager.emit_event(
            "command:before_execute",
            {
                "command": command,
                "user_id": user_id,
                "project_name": project_name,
            },
        )
        if before_event.cancelled:
            return False, "Execução cancelada por plugin.", None, "blocked", "plugin_cancelled", project_name

        command = before_event.data.get("command", command)

        # Validar e parsear comando
        validation_result = self._validate_command(command)
        if not validation_result[0]:
            error_msg = validation_result[1]
            execution_time = time.time() - start_time
            
            # Log de falha de validação
            monitoring_system.log_command_execution(
                command_type="validation_failed",
                command_text=command[:200],
                success=False,
                execution_time=execution_time,
                user_id=user_id,
                project_name=project_name,
                error_message=error_msg
            )
            
            return False, error_msg, None, "blocked", "validation_failed", project_name
        
        command_type, args = validation_result[2], validation_result[3]
        resolved_project_name = self._infer_project_name(command_type, args, project_name)
        effective_project_name = project_name or resolved_project_name

        authorized, auth_message = self._authorize_command(
            command_type,
            args,
            user_role,
            effective_project_name,
            project_mutation_allowlist or [],
        )
        if not authorized:
            execution_time = time.time() - start_time
            monitoring_system.log_command_execution(
                command_type="authorization_failed",
                command_text=command[:200],
                success=False,
                execution_time=execution_time,
                user_id=user_id,
                project_name=effective_project_name,
                error_message=auth_message,
            )
            return False, auth_message, None, "blocked", "authorization_failed", effective_project_name
        
        try:
            # Executar comando baseado no tipo
            if command_type == "bash":
                resolved_cwd = self._resolve_project_cwd(effective_project_name)
                result = await self._execute_bash(args, resolved_cwd)
            elif command_type == "read":
                result = await self._execute_read(args)
            elif command_type == "glob":
                result = await self._execute_glob(args)
            elif command_type == "grep":
                resolved_cwd = self._resolve_project_cwd(effective_project_name)
                result = await self._execute_grep(args, resolved_cwd)
            elif command_type == "edit":
                result = await self._execute_edit(args)
            elif command_type == "write":
                result = await self._execute_write(args)
            else:
                result = (False, f"Comando não implementado: {command_type}", None)
                
        except Exception as e:
            logger.error(f"Erro executando comando {command}: {e}")
            result = (False, f"Erro executando comando: {str(e)}", None)
        
        # Calcular tempo de execução
        execution_time = time.time() - start_time
        success, message, output = result
        status = "success" if success else "failed"
        reason_code = None if success else "execution_failed"
        
        # Log da execução
        monitoring_system.log_command_execution(
            command_type=command_type,
            command_text=command[:200],
            success=success,
            execution_time=execution_time,
            user_id=user_id,
            project_name=effective_project_name,
            error_message=message if not success else None
        )
        
        # Log métrica de tempo
        monitoring_system.log_system_metric(
            metric_name=f"command_{command_type}_execution_time",
            metric_value=execution_time,
            tags={"success": success, "user_id": user_id}
        )
        
        await plugin_manager.emit_event(
            "command:after_execute",
            {
                "command": command,
                "success": success,
                "message": message,
                "output": output,
                "user_id": user_id,
                "project_name": effective_project_name,
            },
        )

        return success, message, output, status, reason_code, effective_project_name
    
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

    def _authorize_command(
        self,
        command_type: Optional[str],
        args: Optional[List],
        user_role: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
    ) -> Tuple[bool, str]:
        """Authorize execution based on role and command sensitivity."""

        if command_type is None:
            return False, "Tipo de comando inválido para autorização"

        if user_role == "admin":
            return True, "Autorizado"

        if command_type in self.read_only_commands:
            return True, "Autorizado"

        if command_type in self.admin_only_commands:
            return self._authorize_project_mutation(
                command_type,
                project_name,
                project_mutation_allowlist,
            )

        if command_type == "bash":
            bash_command = args[0] if args else ""
            parts = shlex.split(bash_command)
            if not parts:
                return False, "Comando bash vazio"

            first_cmd = parts[0].lower()
            if first_cmd in self.user_bash_commands:
                return True, "Autorizado"
            if first_cmd in self.admin_only_bash_commands:
                return self._authorize_project_mutation(
                    f"bash:{first_cmd}",
                    project_name,
                    project_mutation_allowlist,
                )
            return False, f"Comando bash '{first_cmd}' não autorizado para o papel atual"

        return False, f"Comando '{command_type}' não autorizado para o papel atual"

    def _authorize_project_mutation(
        self,
        action_name: str,
        project_name: Optional[str],
        project_mutation_allowlist: List[str],
    ) -> Tuple[bool, str]:
        """Authorize mutation only for explicitly allowed projects."""

        if not project_name:
            return (
                False,
                (
                    f"Ação '{action_name}' exige contexto explícito de projeto "
                    "ou caminho resolvível para um projeto permitido"
                ),
            )

        if project_name in project_mutation_allowlist:
            return True, f"Autorizado para o projeto '{project_name}'"

        return (
            False,
            f"Ação '{action_name}' não autorizada para o projeto '{project_name}'",
        )

    def _infer_project_name(
        self,
        command_type: Optional[str],
        args: Optional[List],
        explicit_project_name: Optional[str],
    ) -> Optional[str]:
        """Infer project context from an explicit project name or command arguments."""

        if explicit_project_name and explicit_project_name in self.known_projects:
            return explicit_project_name

        if command_type is None or not args:
            return None

        candidates = []
        main_arg = args[0]
        extra_args = args[1] if len(args) > 1 else ""

        if command_type in {"read", "edit", "write"}:
            candidates.append(main_arg)
        elif command_type == "bash":
            try:
                candidates.extend(shlex.split(main_arg))
            except ValueError:
                candidates.append(main_arg)
        elif command_type in {"glob", "grep"}:
            candidates.extend([main_arg, extra_args])

        for candidate in candidates:
            resolved_project = self._resolve_project_from_text(candidate)
            if resolved_project:
                return resolved_project

        return None

    def _resolve_project_from_text(self, text: str) -> Optional[str]:
        """Resolve a project name from a path or textual command fragment."""

        if not text:
            return None

        best_match: Optional[str] = None
        best_score: int = -1

        text_lower = text.lower()

        for project_name, project_info in self.known_projects.items():
            project_path = str(Path(project_info["path"]).resolve())
            if project_name.lower() in text_lower or project_path.lower() in text_lower:
                score = len(project_name)
                if score > best_score:
                    best_score = score
                    best_match = project_name

        if best_match:
            return best_match

        try:
            path = Path(text).resolve()
        except Exception:
            return None

        for project_name, project_info in self.known_projects.items():
            project_path = Path(project_info["path"]).resolve()
            try:
                if path.is_relative_to(project_path):
                    score = len(project_name)
                    if score > best_score:
                        best_score = score
                        best_match = project_name
            except ValueError:
                continue

        return best_match
    
    def _resolve_project_cwd(self, project_name: Optional[str]) -> str:
        """Resolve the working directory for a project, falling back to default."""
        if project_name and project_name in self.known_projects:
            project_path = Path(self.known_projects[project_name]["path"])
            if project_path.is_dir():
                return str(project_path)
        return str(get_settings().default_execution_cwd)

    def _validate_bash_command(self, command: str) -> bool:
        """Valida um comando bash"""
        
        # Extrair primeiro comando
        parts = shlex.split(command)
        if not parts:
            return False
        
        first_cmd = parts[0].lower()
        
        # Verificar se está na lista permitida
        if first_cmd not in self.allowed_bash_commands:
            return False
        
        # Extrair primeiro comando
        parts = shlex.split(command)
        if not parts:
            return False
        
        first_cmd = parts[0].lower()
        
        # Verificar se está na lista permitida
        if first_cmd not in self.allowed_bash_commands:
            return False
        
        # Verificações adicionais de segurança
        dangerous_patterns = [
            "|", ">", ">>", "<", "&", ";", "`", "$(", ".."
        ]

        for pattern in dangerous_patterns:
            if pattern in command:
                return False

        return True
    
    def _validate_file_path(self, path: str, check_extension: bool = False) -> bool:
        """Valida um caminho de arquivo"""
        
        try:
            path_obj = Path(path).resolve()
            
            # Verificar se está dentro de diretórios permitidos
            for allowed_dir in self.allowed_directories:
                try:
                    if path_obj.is_relative_to(allowed_dir):
                        # Verificar extensão se necessário
                        if check_extension and path_obj.suffix:
                            if path_obj.suffix not in self.allowed_file_extensions:
                                logger.warning(f"Extensão não permitida: {path_obj.suffix}")
                                return False
                        return True
                except ValueError:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Erro validando caminho {path}: {e}")
            return False
    
    def _validate_file_size(self, path: Path, max_size: int) -> bool:
        """Valida tamanho de arquivo"""
        try:
            if path.exists() and path.is_file():
                file_size = path.stat().st_size
                return file_size <= max_size
            return True  # Arquivo não existe ainda
        except Exception:
            return False
    
    async def _execute_bash(self, args: List, cwd: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """Executa comando bash"""
        
        command = args[0]

        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Comando vazio", None

            if parts[0] == "cd":
                return False, "Comando bash não permitido para execução direta: cd", None

            exec_cwd = cwd or str(get_settings().default_execution_cwd)
            # Executar com timeout
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=OPENCODE_TIMEOUT,
                cwd=exec_cwd,
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
    
    async def _execute_grep(self, args: List, cwd: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
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
            
            base_dir = cwd or str(get_settings().dev_repos_root.resolve())
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
        """Executa comando edit do OpenCode com segurança"""
        
        filepath = args[0]
        extra_args = args[1]
        
        # Extrair old/new do extra_args (suporta múltiplas linhas)
        # Padrão: --old="texto" --new="texto" onde texto pode ter qualquer caractere exceto aspas não escapadas
        old_new_match = re.search(r'--old="((?:[^"\\\\]|\\\\.)*)"\s+--new="((?:[^"\\\\]|\\\\.)*)"', extra_args)
        if not old_new_match:
            return False, "Formato de edit inválido. Use: edit \"file\" --old=\"text\" --new=\"text\"", None
        
        old_text = old_new_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
        new_text = old_new_match.group(2).replace('\\"', '"').replace('\\\\', '\\')
        
        try:
            path = Path(filepath)
            
            # Verificar se arquivo existe
            if not path.exists():
                return False, f"Arquivo não encontrado: {filepath}", None
            
            if not path.is_file():
                return False, f"Caminho não é um arquivo: {filepath}", None
            
            # Validar tamanho do arquivo
            if not self._validate_file_size(path, MAX_EDIT_SIZE):
                return False, f"Arquivo muito grande para edição (limite: {MAX_EDIT_SIZE/1024/1024:.1f}MB)", None
            
            # Criar backup antes de editar (se habilitado)
            backup_path = None
            if self.backup_enabled:
                backup_path = path.with_suffix(path.suffix + self.backup_suffix)
                import shutil
                shutil.copy2(path, backup_path)
                logger.info(f"Backup criado: {backup_path}")
            
            # Ler conteúdo atual
            current_content = path.read_text(encoding='utf-8', errors='ignore')
            
            # Verificar se old_text existe no conteúdo
            if old_text not in current_content:
                # Tentar encontrar com diferentes encodings
                try:
                    current_content = path.read_text(encoding='utf-8')
                except:
                    try:
                        current_content = path.read_text(encoding='latin-1')
                    except:
                        current_content = path.read_text(errors='ignore')
                
                if old_text not in current_content:
                    backup_path.unlink(missing_ok=True)  # Remover backup
                    return False, f"Texto não encontrado no arquivo: '{old_text[:50]}...'", None
            
            # Fazer substituição
            new_content = current_content.replace(old_text, new_text)
            
            # Verificar se houve mudança
            if new_content == current_content:
                backup_path.unlink(missing_ok=True)
                return False, "Nenhuma alteração realizada (texto idêntico)", None
            
            # Escrever novo conteúdo
            path.write_text(new_content, encoding='utf-8')
            
            # Contar ocorrências substituídas
            occurrences = current_content.count(old_text)
            
            # Remover backup após sucesso
            backup_path.unlink(missing_ok=True)
            
            return True, f"Editado: {occurrences} ocorrência(s) substituída(s) em {filepath}", f"Backup: {backup_path.name}\nSubstituído: '{old_text[:100]}...'\nPor: '{new_text[:100]}...'"
            
        except Exception as e:
            # Manter backup em caso de erro
            logger.error(f"Erro editando arquivo {filepath}: {e}")
            return False, f"Erro editando arquivo: {str(e)}", None
    
    async def _execute_write(self, args: List) -> Tuple[bool, str, Optional[str]]:
        """Executa comando write do OpenCode com segurança"""
        
        filepath = args[0]
        extra_args = args[1]
        
        # Extrair conteúdo (suporta múltiplas linhas)
        # Padrão: --content="conteúdo" onde conteúdo pode ter qualquer caractere exceto aspas não escapadas
        content_match = re.search(r'--content="((?:[^"\\\\]|\\\\.)*)"', extra_args)
        if not content_match:
            return False, "Formato de write inválido. Use: write \"file\" --content=\"text\"", None
        
        content = content_match.group(1)
        # Processar escapes
        content = content.replace('\\"', '"').replace('\\\\', '\\')
        
        try:
            path = Path(filepath)
            
            # Verificar se diretório pai existe
            parent_dir = path.parent
            if not parent_dir.exists():
                # Criar diretórios se necessário (com permissões seguras)
                parent_dir.mkdir(parents=True, exist_ok=True)
                # Definir permissões seguras
                parent_dir.chmod(0o755)  # rwxr-xr-x
            
            # Verificar se arquivo já existe (para backup)
            file_exists = path.exists()
            backup_path = None
            
            if file_exists:
                # Criar backup
                backup_path = path.with_suffix(path.suffix + '.devsynapse_backup')
                import shutil
                shutil.copy2(path, backup_path)
            
            # Escrever conteúdo
            path.write_text(content, encoding='utf-8')
            
            # Definir permissões seguras
            path.chmod(0o644)  # rw-r--r--
            
            # Preparar mensagem de resultado
            if file_exists:
                # Ler conteúdo anterior para comparação
                old_content = backup_path.read_text(encoding='utf-8', errors='ignore') if backup_path else ""
                old_size = len(old_content)
                new_size = len(content)
                
                # Remover backup após sucesso
                if backup_path and backup_path.exists():
                    backup_path.unlink()
                
                return True, f"Arquivo sobrescrito: {filepath} ({old_size} → {new_size} chars)", f"Backup: {backup_path.name if backup_path else 'N/A'}\nTamanho anterior: {old_size} chars\nNovo tamanho: {new_size} chars"
            else:
                return True, f"Arquivo criado: {filepath} ({len(content)} chars)", f"Novo arquivo criado\nTamanho: {len(content)} chars"
            
        except Exception as e:
            logger.error(f"Erro escrevendo arquivo {filepath}: {e}")
            return False, f"Erro escrevendo arquivo: {str(e)}", None
    
    def get_project_context(self, project_name: str) -> Optional[Dict]:
        """Obtém contexto sobre um projeto específico"""
        
        if project_name in self.known_projects:
            return self.known_projects[project_name]
        
        # Tentar encontrar por nome similar
        for name, info in self.known_projects.items():
            if project_name.lower() in name.lower():
                return info
        
        return None
