"""
Núcleo do DevSynapse - Integração com DeepSeek API
"""

import asyncio
import logging
import re
import shlex
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import config.settings as app_settings
from config.settings import ALLOWED_COMMANDS, BLACKLISTED_PATTERNS
from core.correlation import generate_tool_run_id
from core.deepseek import DeepSeekClient, LLMResult
from core.llm_optimization import ModelRoute
from core.plugin_system import plugin_manager
from core.prompts import build_system_prompt
from core.routing import RouteSelector

logger = logging.getLogger(__name__)


@dataclass
class TaskChecklist:
    expected_files: set[str]
    completed_files: set[str]
    requires_pytest: bool = False
    pytest_passed: bool = False


OPENCODE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "strict": True,
            "description": (
                "Execute a shell command on the system. "
                "Use to list files, check git status, run tests, install project dependencies, etc. "
                "Do not use sudo or privileged OS package installation from chat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The full shell command to execute (e.g. 'ls -la', 'git status')",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "strict": True,
            "description": "Read the contents of a file from the filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to read",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob",
            "strict": True,
            "description": "Find files matching a glob pattern (e.g. '**/*.py', 'src/**/*.ts').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to search for files",
                    }
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "strict": True,
            "description": "Search for a regex pattern in file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression to search for",
                    },
                    "include": {
                        "type": "string",
                        "description": "File extension filter (e.g. '*.js', '*.py'). Use empty string to search all files.",
                    },
                },
                "required": ["pattern", "include"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "strict": True,
            "description": "Edit a file by replacing one piece of text with another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to edit",
                    },
                    "old": {
                        "type": "string",
                        "description": "Exact text to replace (must match precisely)",
                    },
                    "new": {
                        "type": "string",
                        "description": "New text that will replace the old text",
                    },
                },
                "required": ["path", "old", "new"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "strict": True,
            "description": (
                "Write content to a file (overwrites if it exists). "
                "Parent directories are created automatically; use this as the first action "
                "when creating a small new project instead of running mkdir separately."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
]

AUTOEXEC_READ_ONLY_BASH_COMMANDS = {"df", "du", "ls", "ps", "pwd"}
AUTOEXEC_READ_ONLY_GIT_SUBCOMMANDS = {
    "branch",
    "describe",
    "diff",
    "log",
    "ls-files",
    "remote",
    "rev-parse",
    "show",
    "status",
}
AUTOEXEC_BASH_OUTPUT_FLAGS = {"-o", "--output"}


class DevSynapseBrain:
    """Gerencia a inteligência do DevSynapse via API DeepSeek."""

    def __init__(self, memory_system, opencode_bridge):
        self.memory = memory_system
        self.opencode = opencode_bridge
        settings = app_settings.get_settings()
        flash_pricing = {
            "cache_hit": Decimal(
                str(settings.deepseek_flash_input_cache_hit_price_usd_per_million)
            ),
            "cache_miss": Decimal(
                str(settings.deepseek_flash_input_cache_miss_price_usd_per_million)
            ),
            "output": Decimal(str(settings.deepseek_flash_output_price_usd_per_million)),
        }
        pro_pricing = {
            "cache_hit": Decimal(
                str(settings.deepseek_pro_input_cache_hit_price_usd_per_million)
            ),
            "cache_miss": Decimal(
                str(settings.deepseek_pro_input_cache_miss_price_usd_per_million)
            ),
            "output": Decimal(str(settings.deepseek_pro_output_price_usd_per_million)),
        }
        self.deepseek = DeepSeekClient(
            api_key=app_settings.DEEPSEEK_API_KEY,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            reasoning_effort=settings.deepseek_reasoning_effort,
            thinking_enabled=settings.deepseek_thinking_enabled,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            request_timeout=settings.llm_request_timeout,
            flash_pricing=flash_pricing,
            pro_pricing=pro_pricing,
            provider_configs={
                "openrouter": {
                    "api_key": app_settings.OPENROUTER_API_KEY,
                    "base_url": settings.openrouter_base_url,
                },
                "opencode-zen": {
                    "api_key": app_settings.OPENCODE_ZEN_API_KEY,
                    "base_url": settings.opencode_zen_base_url,
                },
                "opencode-go": {
                    "api_key": app_settings.OPENCODE_GO_API_KEY,
                    "base_url": settings.opencode_go_base_url,
                },
            },
        )

        self.router = RouteSelector(
            memory=self.memory,
            deepseek_model=self.deepseek.model,
            provider_configs=self.deepseek.provider_configs,
            deepseek_api_key=self.deepseek.api_key,
        )

        if not self.deepseek.configured:
            logger.warning("DeepSeek API key não configurada")

    @property
    def api_key(self) -> Optional[str]:
        return self.deepseek.api_key

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self.deepseek.api_key = value

    def set_provider_api_key(self, provider: str, value: Optional[str]) -> None:
        config = self.deepseek.provider_configs.setdefault(provider, {})
        config["api_key"] = value
        
    def generate_system_prompt(self, context: Dict) -> str:
        user_prefs = self.memory.get_user_preferences()
        projects_info = self.memory.get_projects_context()
        agent_learning = self._get_agent_learning_context()
        active_project_name = context.get("project_name")
        current_request = context.get("current_user_message") or ""
        procedural_memory = self._get_project_memory_context(active_project_name, current_request)
        skills_context = self._get_skills_context(current_request, active_project_name)
        agent_run_context = context.get("agent_run_context") or "Nenhuma tarefa de agente ativa."
        stuck_context = self._detect_stuck_context(context)
        settings = app_settings.get_settings()
        active_project_path = None
        if active_project_name and hasattr(self.memory, "get_project"):
            try:
                active_project = self.memory.get_project(active_project_name)
                active_project_path = active_project.get("path") if active_project else None
            except Exception:
                active_project_path = None

        return build_system_prompt(
            user_prefs=user_prefs,
            projects_info=projects_info,
            agent_learning=agent_learning,
            procedural_memory=procedural_memory,
            skills_context=skills_context,
            agent_run_context=agent_run_context,
            stuck_context=stuck_context,
            active_project_name=active_project_name,
            active_project_path=active_project_path,
            workspace_root=str(settings.dev_workspace_root),
            repos_root=str(settings.dev_repos_root),
            default_cwd=str(settings.default_execution_cwd),
        )

    async def process_message(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        project_name: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        project_mutation_allowlist: Optional[List[str]] = None,
        auto_execute: bool = False,
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        """
        Processa uma mensagem do usuário e retorna resposta + comando OpenCode.

        When user_id and user_role are provided, read-only commands are auto-executed
        and the result is fed back to the LLM in a loop until a final answer is reached.
        Mutating commands require explicit confirmation unless automatic execution is enabled
        for a trusted admin session.
        """
        
        event_data = {
            "user_message": user_message,
            "conversation_id": conversation_id,
            "project_name": project_name,
        }

        bp_event = await plugin_manager.emit_event("brain:before_process", event_data)
        if bp_event.cancelled:
            return "Processamento cancelado por plugin.", None, None
        user_message = bp_event.data.get("user_message", user_message)
        conversation_id = bp_event.data.get("conversation_id", conversation_id)
        project_name = bp_event.data.get("project_name", project_name)

        # Obter contexto da conversa
        context = await self.memory.get_conversation_context(conversation_id)
        effective_project_name = project_name or context.get("project_name")
        if effective_project_name:
            context["project_name"] = effective_project_name
        agent_run = self._start_agent_run_if_needed(
            conversation_id,
            user_message,
            effective_project_name,
            context,
        )

        mem_before = {
            "user_message": user_message,
            "conversation_id": conversation_id,
            "project_name": effective_project_name,
        }
        await plugin_manager.emit_event("memory:before_save", mem_before)

        # Preparar mensagens para o DeepSeek
        messages = self._prepare_messages(user_message, context)

        llm_event = await plugin_manager.emit_event("brain:before_llm_call", {"messages": messages})
        if not llm_event.cancelled:
            messages = llm_event.data.get("messages", messages)

        route = self._select_llm_route(user_message, context)

        # Chamar API com loop de auto-execução para comandos read-only
        max_autoexec_rounds = self._max_autoexec_rounds(auto_execute, user_role)
        round_count = 0
        aggregated_usage = None
        opencode_command = None
        response_text = ""
        autoexecuted_command = None

        while round_count < max_autoexec_rounds:
            round_count += 1
            llm_result = self._coerce_llm_result(
                await self._call_llm_api(
                    messages,
                    route=route,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )
            )
            response_text = llm_result.content
            opencode_command = self._tool_calls_to_opencode_command(llm_result.tool_calls)
            if opencode_command is None:
                opencode_command = self._extract_opencode_command(response_text)
            aggregated_usage = self._merge_usage(aggregated_usage, llm_result.usage)

            if self._should_retry_missing_tool(
                auto_execute=auto_execute,
                user_message=user_message,
                response_text=response_text,
                opencode_command=opencode_command,
            ):
                messages = self._build_tool_repair_messages(user_message, context, response_text)
                continue

            autoexec_enabled = bool(self.api_key and user_id and user_role)
            if not (
                autoexec_enabled
                and opencode_command
                and self._can_autoexecute_command(opencode_command, user_role)
            ):
                break

            tool_run_id = generate_tool_run_id()
            success, msg, output, status, reason, proj = await self.opencode.execute_command(
                opencode_command,
                user_id=user_id,
                project_name=effective_project_name,
                user_role=user_role,
                project_mutation_allowlist=project_mutation_allowlist or [],
                conversation_id=conversation_id,
                tool_run_id=tool_run_id,
            )
            self._record_agent_command_result(
                conversation_id=conversation_id,
                goal=user_message,
                command=opencode_command,
                success=success,
                result=msg,
                output=output,
                status=status,
                reason_code=reason,
                project_name=proj,
            )
            autoexecuted_command = {
                "command": opencode_command,
                "success": success,
                "result": msg,
                "output": output,
                "status": status,
                "reason_code": reason,
                "project_name": proj,
                "tool_run_id": tool_run_id,
            }

            if not success:
                if self._should_replay_command_result(
                    auto_execute,
                    user_role,
                    status,
                    reason,
                    msg,
                    output,
                ):
                    messages.extend(
                        self._build_command_result_replay_messages(
                            response_text,
                            opencode_command,
                            success,
                            msg,
                            output,
                        )
                    )
                    opencode_command = None
                    continue
                response_text = (
                    f"{response_text}\n\n"
                    f"{self._command_failure_message(opencode_command, msg, reason, proj)}"
                )
                opencode_command = None
                break

            messages.extend(
                self._build_command_result_replay_messages(
                    response_text,
                    opencode_command,
                    success,
                    msg,
                    output,
                )
            )

        await plugin_manager.emit_event("brain:after_llm_call", {"response": response_text})

        response_text = self._sanitize_unconfirmed_execution_claims(
            response_text,
            opencode_command,
        )
        if autoexecuted_command is not None and (
            not response_text.strip() or self._response_promises_pending_action(response_text)
        ):
            response_text = self._command_completion_fallback(autoexecuted_command)

        persisted_command = opencode_command
        if persisted_command is None and autoexecuted_command is not None:
            persisted_command = autoexecuted_command["command"]

        # Salvar na memória
        persisted_project_name = await self.memory.save_interaction(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=response_text,
            opencode_command=persisted_command,
            llm_usage=aggregated_usage,
            project_name=effective_project_name,
        )
        if isinstance(persisted_project_name, str) or persisted_project_name is None:
            effective_project_name = persisted_project_name or effective_project_name

        if autoexecuted_command is not None and persisted_command == autoexecuted_command["command"]:
            await self.memory.save_command_execution(
                conversation_id=conversation_id,
                command=autoexecuted_command["command"],
                success=autoexecuted_command["success"],
                result=autoexecuted_command["result"],
                output=autoexecuted_command["output"],
                status=autoexecuted_command["status"],
                reason_code=autoexecuted_command["reason_code"],
                project_name=autoexecuted_command["project_name"],
                record_agent_event=False,
            )
            if autoexecuted_command["success"]:
                self._persist_repos_project_if_needed(autoexecuted_command["project_name"])

        self._record_agent_route_decision(
            conversation_id=conversation_id,
            route=route,
            usage=aggregated_usage,
            project_name=effective_project_name,
            opencode_command=persisted_command,
        )
        self._review_completed_task(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=response_text,
            project_name=effective_project_name,
            opencode_command=persisted_command,
            route=route,
            tool_iterations=max(0, round_count - 1) + (1 if persisted_command else 0),
        )
        self._record_agent_final_response(
            agent_run,
            conversation_id,
            response_text,
            has_pending_command=opencode_command is not None,
            project_name=effective_project_name,
        )

        await plugin_manager.emit_event("memory:after_save", {
            "conversation_id": conversation_id,
            "user_message": user_message,
            "response": response_text,
            "project_name": effective_project_name,
        })

        ap_event = await plugin_manager.emit_event("brain:after_process", {
            "response": response_text,
            "opencode_command": opencode_command,
        })
        if not ap_event.cancelled:
            response_text = ap_event.data.get("response", response_text)
            opencode_command = ap_event.data.get("opencode_command", opencode_command)
        
        return response_text, opencode_command, aggregated_usage
    
    def _prepare_messages(self, user_message: str, context: Dict) -> List[Dict]:
        """Prepara mensagens no formato para API"""
        context = {**context, "current_user_message": user_message}
        system_prompt = self.generate_system_prompt(context)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Adicionar histórico de conversa se existir
        if context.get("conversation_history"):
            for msg in context["conversation_history"][-6:]:  # Últimas 6 mensagens
                messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})
        
        return messages

    def _select_llm_route(self, user_message: str, context: Dict) -> ModelRoute:
        return self.router.select_route(user_message, context)

    def _get_agent_learning_context(self) -> str:
        return self.router.get_agent_learning_context()

    def _detect_stuck_context(self, context: Dict) -> str:
        conversation_messages = context.get("conversation_messages") or []
        if not conversation_messages:
            return ""

        consecutive_blocked = 0
        reason_codes: List[str] = []
        for msg in reversed(conversation_messages):
            if msg.get("role") != "assistant":
                continue
            status = msg.get("commandStatus")
            if status in ("blocked", "failed"):
                consecutive_blocked += 1
                rc = msg.get("reasonCode")
                if rc and rc not in reason_codes:
                    reason_codes.append(rc)
            else:
                break

        if consecutive_blocked < 2:
            return ""

        details = ""
        if reason_codes:
            details = f" Razões dos bloqueios: {', '.join(reason_codes)}."

        return (
            f"\n## STUCK AWARENESS\n"
            f"- As últimas {consecutive_blocked} tentativas de execução falharam ou foram bloqueadas."
            f"{details}\n"
            "- O usuário pode estar travado. NÃO repita a mesma ação.\n"
            "- Proponha uma alternativa com outro tipo de ferramenta, ou explique o bloqueio "
            "e pergunte se o usuário quer ajustar permissões ou projeto.\n"
        )

    def _get_project_memory_context(
        self,
        project_name: Optional[str],
        user_message: str,
    ) -> str:
        if not hasattr(self.memory, "get_project_memory_context"):
            return "Nenhuma memória procedural relevante encontrada."
        try:
            return self.memory.get_project_memory_context(project_name, user_message)
        except Exception:
            logger.debug("Could not load procedural memory context", exc_info=True)
            return "Nenhuma memória procedural relevante encontrada."

    def _get_skills_context(
        self,
        user_message: str,
        project_name: Optional[str],
    ) -> str:
        if not hasattr(self.memory, "get_skills_context"):
            return "Nenhuma skill registrada ainda."
        try:
            return self.memory.get_skills_context(user_message, project_name=project_name)
        except Exception:
            logger.debug("Could not load skills context", exc_info=True)
            return "Nenhuma skill registrada ainda."

    def _start_agent_run_if_needed(
        self,
        conversation_id: Optional[str],
        user_message: str,
        project_name: Optional[str],
        context: Dict,
    ) -> Optional[Dict]:
        if not conversation_id:
            return None

        active_run = None
        if hasattr(self.memory, "get_active_agent_run"):
            try:
                active_run = self.memory.get_active_agent_run(conversation_id)
            except Exception:
                logger.debug("Could not load active agent run", exc_info=True)

        should_track = active_run is not None or self._user_request_expects_tool(user_message)
        if should_track and hasattr(self.memory, "start_or_resume_agent_run"):
            try:
                active_run = self.memory.start_or_resume_agent_run(
                    conversation_id=conversation_id,
                    goal=user_message,
                    project_name=project_name,
                )
            except Exception:
                logger.debug("Could not start agent run", exc_info=True)

        if hasattr(self.memory, "get_agent_run_context"):
            try:
                context["agent_run_context"] = self.memory.get_agent_run_context(conversation_id)
            except Exception:
                logger.debug("Could not load agent run context", exc_info=True)

        return active_run

    def _record_agent_command_result(
        self,
        conversation_id: Optional[str],
        goal: str,
        command: str,
        success: bool,
        result: str,
        output: Optional[str],
        status: str,
        reason_code: Optional[str],
        project_name: Optional[str],
    ) -> None:
        if not hasattr(self.memory, "record_agent_command_result"):
            return
        try:
            self.memory.record_agent_command_result(
                conversation_id=conversation_id,
                goal=goal,
                command=command,
                success=success,
                result=result,
                output=output,
                status=status,
                reason_code=reason_code,
                project_name=project_name,
            )
        except Exception:
            logger.debug("Could not record agent command result", exc_info=True)

    def _record_agent_final_response(
        self,
        agent_run: Optional[Dict],
        conversation_id: Optional[str],
        response_text: str,
        has_pending_command: bool,
        project_name: Optional[str],
    ) -> None:
        if not agent_run or not hasattr(self.memory, "record_agent_final_response"):
            return
        try:
            self.memory.record_agent_final_response(
                run_id=agent_run["id"],
                conversation_id=conversation_id,
                response=response_text,
                has_pending_command=has_pending_command,
                project_name=project_name,
            )
        except Exception:
            logger.debug("Could not record agent final response", exc_info=True)

    def _review_completed_task(
        self,
        conversation_id: Optional[str],
        user_message: str,
        ai_response: str,
        project_name: Optional[str],
        opencode_command: Optional[str],
        route: ModelRoute,
        tool_iterations: int,
    ) -> None:
        if not hasattr(self.memory, "review_completed_task"):
            return
        try:
            self.memory.review_completed_task(
                conversation_id=conversation_id,
                user_message=user_message,
                ai_response=ai_response,
                project_name=project_name,
                opencode_command=opencode_command,
                route=route,
                tool_iterations=tool_iterations,
            )
        except Exception:
            logger.debug("Could not run learning nudge", exc_info=True)

    def _record_agent_route_decision(
        self,
        conversation_id: Optional[str],
        route: ModelRoute,
        usage: Optional[Dict],
        project_name: Optional[str],
        opencode_command: Optional[str],
    ) -> None:
        if not hasattr(self.memory, "record_agent_route_decision"):
            return
        try:
            self.memory.record_agent_route_decision(
                conversation_id=conversation_id,
                route=route,
                usage=usage,
                project_name=project_name,
                opencode_command=opencode_command,
            )
        except Exception:
            logger.debug("Could not persist agent route decision", exc_info=True)

    def _persist_repos_project_if_needed(self, project_name: Optional[str]) -> None:
        if not project_name or not hasattr(self.memory, "add_project"):
            return

        settings = app_settings.get_settings()
        repos_root = settings.dev_repos_root.expanduser().resolve()
        project_root = (repos_root / project_name).resolve()
        try:
            project_root.relative_to(repos_root)
        except ValueError:
            return
        if not project_root.exists():
            return

        try:
            if hasattr(self.memory, "get_project") and self.memory.get_project(project_name):
                return
            self.memory.add_project(
                project_name,
                str(project_root),
                project_type="project",
                priority="medium",
                replace=False,
            )
        except Exception:
            logger.debug("Could not persist generated project %s", project_name, exc_info=True)

    async def _call_llm_api(
        self,
        messages: List[Dict],
        route: Optional[ModelRoute] = None,
        tool_choice: object = "auto",
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> LLMResult:
        """Chama API do DeepSeek e retorna resposta degradada se a API falhar."""

        if not self.deepseek.configured:
            return LLMResult(content=self._get_fallback_response(messages))

        model = route.model if route else self.deepseek.model
        start_time = time.perf_counter()
        try:
            return await self._complete_and_record(
                messages, model, tool_choice, route, user_id, conversation_id, start_time,
            )
        except Exception as e:
            fallback_model = route.fallback_model if route else None
            if fallback_model and fallback_model != model:
                try:
                    logger.warning(
                        "DeepSeek %s call failed (%s); retrying with %s",
                        model, e, fallback_model,
                    )
                    return await self._complete_and_record(
                        messages, fallback_model, tool_choice, route, user_id,
                        conversation_id, start_time,
                    )
                except Exception as fallback_error:
                    logger.warning(
                        "DeepSeek fallback model %s failed: %s",
                        fallback_model, fallback_error,
                    )

            self._record_llm_request_telemetry(
                user_id=user_id, conversation_id=conversation_id,
                provider=None, model=model, route=route, success=False,
                usage=None,
                total_latency_ms=(time.perf_counter() - start_time) * 1000,
                error_message=str(e),
            )
            logger.warning(f"DeepSeek API falhou: {e}. Usando resposta degradada.")
            return LLMResult(content=self._get_fallback_response(messages))

    async def _complete_and_record(
        self,
        messages: List[Dict],
        model: str,
        tool_choice: object,
        route: Optional[ModelRoute],
        user_id: Optional[str],
        conversation_id: Optional[str],
        start_time: float,
    ) -> LLMResult:
        result = await asyncio.to_thread(
            self.deepseek.chat_completion,
            messages, OPENCODE_TOOLS, model=model, tool_choice=tool_choice,
        )
        usage = self._enrich_usage_cost(result.provider, result.model, result.usage)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._record_llm_request_telemetry(
            user_id=user_id, conversation_id=conversation_id,
            provider=result.provider, model=result.model,
            route=route, success=True, usage=usage,
            first_token_latency_ms=elapsed_ms, total_latency_ms=elapsed_ms,
        )
        return LLMResult(
            content=result.content,
            provider=result.provider,
            model=result.model,
            usage=usage,
            tool_calls=result.tool_calls,
            reasoning_content=result.reasoning_content,
        )

    def _enrich_usage_cost(
        self,
        provider: Optional[str],
        model: Optional[str],
        usage: Optional[Dict],
    ) -> Optional[Dict]:
        if not usage:
            return usage
        if usage.get("estimated_cost_usd") is not None:
            return usage
        if not provider or not model or not hasattr(self.memory, "get_llm_model"):
            return usage
        catalog = self.memory.get_llm_model(provider, model)
        if not isinstance(catalog, dict):
            return usage
        input_cost = catalog.get("input_cost_per_token")
        output_cost = catalog.get("output_cost_per_token")
        cache_cost = catalog.get("cache_read_cost_per_token")
        if input_cost is None or output_cost is None:
            return usage
        cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
        cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        if prompt_tokens and not cache_hit_tokens and not cache_miss_tokens:
            cache_miss_tokens = prompt_tokens
        cost = (
            cache_hit_tokens * float(cache_cost if cache_cost is not None else input_cost)
            + cache_miss_tokens * float(input_cost)
            + completion_tokens * float(output_cost)
        )
        enriched = dict(usage)
        enriched["estimated_cost_usd"] = round(cost, 8)
        return enriched

    def _record_llm_request_telemetry(self, **kwargs) -> None:
        if not hasattr(self.memory, "record_llm_request_telemetry"):
            return
        try:
            self.memory.record_llm_request_telemetry(**kwargs)
        except Exception:
            logger.debug("Could not record LLM request telemetry", exc_info=True)



    @staticmethod
    def _command_completion_fallback(executed_command: Dict) -> str:
        status = executed_command.get("status")
        reason_code = executed_command.get("reason_code")
        project_name = executed_command.get("project_name")
        project_suffix = f" Projeto: {project_name}." if project_name else ""

        if status == "success":
            return f"Execução concluída. O resultado do comando está disponível abaixo.{project_suffix}"
        if status == "blocked":
            if reason_code == "project_scope_mismatch":
                return (
                    "A execução foi bloqueada porque o comando tentou sair do escopo "
                    f"do projeto.{project_suffix}"
                )
            return (
                "A execução foi bloqueada por uma regra de segurança ou permissão."
                f"{project_suffix}"
            )
        if reason_code == "interactive_sudo_required":
            return (
                "O comando exige senha ou terminal interativo para `sudo`. Execute essa "
                "etapa manualmente no terminal, ou configure as dependências fora do "
                f"DevSynapse antes de continuar.{project_suffix}"
            )
        if reason_code == "privileged_setup_required":
            return (
                "Esta etapa exige setup privilegiado fora do chat. Execute os comandos "
                "necessários no terminal e use Revalidar pré-requisitos antes de "
                f"continuar.{project_suffix}"
            )
        return f"A execução terminou com falha e precisa de revisão.{project_suffix}"

    @staticmethod
    def _command_failure_message(
        command: str,
        message: str,
        reason_code: Optional[str],
        project_name: Optional[str],
    ) -> str:
        project_suffix = f" Projeto: {project_name}." if project_name else ""
        if reason_code == "interactive_sudo_required":
            return (
                f"O comando `{command}` exige senha ou terminal interativo para `sudo` "
                "e não pode ser concluído pelo chat. Execute essa etapa manualmente no "
                f"terminal, ou configure as dependências fora do DevSynapse.{project_suffix}"
            )
        if reason_code == "privileged_setup_required":
            return (
                f"O comando `{command}` exige setup privilegiado e foi bloqueado antes de "
                "rodar. Execute essa etapa manualmente no terminal e use Revalidar "
                f"pré-requisitos para continuar.{project_suffix}"
            )
        return f"O comando `{command}` não pôde ser executado: {message}{project_suffix}"

    def _coerce_llm_result(self, result: str | LLMResult) -> LLMResult:
        if isinstance(result, LLMResult):
            return result
        return LLMResult(content=result)

    def _merge_usage(self, base: Optional[Dict], extra: Optional[Dict]) -> Optional[Dict]:
        if not base and not extra:
            return None
        if not base:
            return dict(extra)
        if not extra:
            return dict(base)

        merged = {
            "provider": extra.get("provider") or base.get("provider"),
            "model": extra.get("model") or base.get("model"),
            "prompt_tokens": int(base.get("prompt_tokens") or 0)
            + int(extra.get("prompt_tokens") or 0),
            "completion_tokens": int(base.get("completion_tokens") or 0)
            + int(extra.get("completion_tokens") or 0),
            "total_tokens": int(base.get("total_tokens") or 0)
            + int(extra.get("total_tokens") or 0),
            "prompt_cache_hit_tokens": int(base.get("prompt_cache_hit_tokens") or 0)
            + int(extra.get("prompt_cache_hit_tokens") or 0),
            "prompt_cache_miss_tokens": int(base.get("prompt_cache_miss_tokens") or 0)
            + int(extra.get("prompt_cache_miss_tokens") or 0),
            "reasoning_tokens": int(base.get("reasoning_tokens") or 0)
            + int(extra.get("reasoning_tokens") or 0),
            "estimated_cost_usd": None,
        }

        base_cost = base.get("estimated_cost_usd")
        extra_cost = extra.get("estimated_cost_usd")
        if base_cost is not None or extra_cost is not None:
            merged["estimated_cost_usd"] = round(
                float(base_cost or 0.0) + float(extra_cost or 0.0),
                8,
            )

        return merged

    @staticmethod
    def _max_autoexec_rounds(auto_execute: bool, user_role: Optional[str]) -> int:
        """Allow trusted admin runs enough turns to build, test and fix without stopping early."""

        if auto_execute and user_role == "admin":
            return 20
        if auto_execute:
            return 8
        return 5

    @staticmethod
    def _should_replay_command_result(
        auto_execute: bool,
        user_role: Optional[str],
        status: str,
        reason_code: Optional[str],
        message: Optional[str] = None,
        output: Optional[str] = None,
    ) -> bool:
        """Let auto mode recover from normal failures and explain blocked actions."""

        if not auto_execute:
            return False

        if status == "failed" and reason_code == "execution_failed":
            if DevSynapseBrain._looks_like_interactive_sudo_failure(message, output):
                return False

            return True

        return status == "blocked" and reason_code in {
            "authorization_failed",
            "project_scope_mismatch",
            "validation_failed",
        }

    @staticmethod
    def _looks_like_interactive_sudo_failure(
        message: Optional[str],
        output: Optional[str],
    ) -> bool:
        text = f"{message or ''}\n{output or ''}".lower()
        sudo_markers = [
            "sudo:",
            "a terminal is required",
            "um terminal é necessário",
            "a password is required",
            "uma senha é necessária",
            "no tty present",
            "askpass",
        ]
        return "sudo" in text and any(marker in text for marker in sudo_markers)

    def _should_retry_missing_tool(
        self,
        auto_execute: bool,
        user_message: str,
        response_text: str,
        opencode_command: Optional[str],
    ) -> bool:
        """Recover when the model promises action but emits no executable tool call."""

        if not auto_execute or opencode_command:
            return False
        if response_text:
            return self._response_promises_pending_action(response_text)
        return self._user_request_expects_tool(user_message)

    @staticmethod
    def _build_task_checklist(user_message: str) -> Optional[TaskChecklist]:
        """Extract a small objective completion checklist from implementation requests."""

        text = user_message or ""
        file_matches = re.findall(
            r"(?<![\w./-])([\w.-]+(?:/[\w.-]+)*\.(?:py|tsx|ts|js|jsx|json|toml|md|css|html|rs|yml|yaml))(?![\w./-])",
            text,
            flags=re.IGNORECASE,
        )
        expected_files = {
            match.strip("`'\".,;:()[]{}").lstrip("./")
            for match in file_matches
            if match.strip("`'\".,;:()[]{}")
        }
        requires_pytest = bool(re.search(r"\b(pytest|testes?\s+passar|tests?\s+pass)\b", text, re.I))
        if not expected_files and not requires_pytest:
            return None
        return TaskChecklist(
            expected_files=expected_files,
            completed_files=set(),
            requires_pytest=requires_pytest,
        )

    @staticmethod
    def _update_task_checklist(
        checklist: TaskChecklist,
        command: str,
        output: Optional[str],
    ) -> None:
        write_match = re.match(r'write\s+"([^"]+)"', command)
        if write_match:
            written_path = write_match.group(1).lstrip("./")
            for expected_file in checklist.expected_files:
                if written_path.endswith(expected_file):
                    checklist.completed_files.add(expected_file)

        if "pytest" in command.lower():
            result_text = f"{output or ''}".lower()
            if re.search(r"\b\d+\s+passed\b", result_text) or "passed" in result_text:
                checklist.pytest_passed = True

    @staticmethod
    def _task_checklist_complete(checklist: TaskChecklist) -> bool:
        files_done = checklist.expected_files.issubset(checklist.completed_files)
        tests_done = not checklist.requires_pytest or checklist.pytest_passed
        return files_done and tests_done

    @staticmethod
    def _task_checklist_status(checklist: TaskChecklist) -> str:
        missing_files = sorted(checklist.expected_files - checklist.completed_files)
        lines = []
        if checklist.expected_files:
            done = sorted(checklist.completed_files)
            lines.append(f"Files done: {', '.join(done) if done else '(none)'}")
            lines.append(f"Files missing: {', '.join(missing_files) if missing_files else '(none)'}")
        if checklist.requires_pytest:
            lines.append(f"Pytest passed: {'yes' if checklist.pytest_passed else 'no'}")
        return "\n".join(lines)

    @staticmethod
    def _build_checklist_repair_messages(
        assistant_text: str,
        checklist: TaskChecklist,
    ) -> List[Dict[str, str]]:
        return [
            {"role": "assistant", "content": assistant_text or "Continuing the task."},
            {
                "role": "user",
                "content": (
                    "The original task is not complete according to this objective checklist:\n"
                    f"{DevSynapseBrain._task_checklist_status(checklist)}\n\n"
                    "Continue the original task now. Emit exactly one next tool call. "
                    "Do not provide a final summary until every listed file exists and "
                    "the required test command has passed."
                ),
            },
        ]

    @staticmethod
    def _user_request_expects_tool(user_message: str) -> bool:
        normalized = " ".join((user_message or "").strip().lower().split())
        if not normalized:
            return False

        explanatory_question_patterns = [
            r"^(como|how)\b",
            r"\b(o que|what|why|por que|porque)\b",
        ]
        if any(re.search(pattern, normalized) for pattern in explanatory_question_patterns):
            return False

        action_patterns = [
            r"\b(crie|criar|cria|implemente|implementar|gere|gerar|monte|montar|adicione|adicionar|edite|editar|salve|salvar|rode|rodar|execute|executar|leia|ler|liste|listar|inspecione|inspecionar)\b",
            r"\b(create|implement|generate|build|add|edit|save|run|execute|read|list|inspect)\b",
            r"\b(pode\s+continuar|continue|continuar)\b",
        ]
        return any(re.search(pattern, normalized) for pattern in action_patterns)

    @staticmethod
    def _response_promises_pending_action(response_text: str) -> bool:
        normalized = " ".join(response_text.strip().lower().split())
        if not normalized:
            return False

        pending_action_patterns = [
            r"\b(vou|irei|vamos)\s+(criar|escrever|gerar|montar|adicionar|editar|salvar|rodar|executar|ler|listar|inspecionar)\b",
            r"\b(agora|em seguida)\s+(vou|vamos)\s+(criar|escrever|gerar|montar|adicionar|editar|salvar|rodar|executar|ler|listar|inspecionar)\b",
            r"\b(agora|em seguida|pr[oó]ximo|next)\s+(?:o|a|os|as|the)?\s*[`'\"*_]*(arquivo|readme(?:\.md)?|teste|testes|c[oó]digo|pacote|m[oó]dulo|pyproject(?:\.toml)?|file|test|tests|code|package|module)\b[^.!?]*:?\s*$",
            r"\b(i'?ll|i will|let me|i am going to|i'm going to)\s+(create|write|generate|add|edit|save|run|execute|read|list|inspect)\b",
        ]
        return any(re.search(pattern, normalized) for pattern in pending_action_patterns)

    @staticmethod
    def _build_command_result_replay_messages(
        assistant_text: str,
        command: str,
        success: bool,
        message: str,
        output: Optional[str],
    ) -> List[Dict[str, str]]:
        """Replay tool output in a provider-compatible text form."""

        result_text = output or message or "(no output)"
        status = "success" if success else "failed"
        return [
            {"role": "assistant", "content": assistant_text or f"Executed `{command}`."},
            {
                "role": "user",
                "content": (
                    f"Command `{command}` finished with status `{status}`.\n"
                    f"Result: {message}\n\n"
                    f"Output:\n```\n{result_text[:3000]}\n```\n\n"
                    "Never report success for a command whose status is `failed` or "
                    "`blocked`, even if part of a shell pipeline produced output. "
                    "Continue the original task. If more filesystem or command work is "
                    "needed, emit exactly one next tool call. If the task is complete, "
                    "give the final concise result. Do not stop only because a dependency "
                    "or command is unavailable; continue with any useful project-scoped "
                    "work that is still possible and mention the missing prerequisite in "
                    "the final answer. If the command was blocked by permission or project "
                    "scope, choose an allowed action inside the active project or explain "
                    "the exact permission/project selection required."
                ),
            },
        ]

    def _build_tool_repair_messages(
        self,
        user_message: str,
        context: Dict,
        previous_response: str,
    ) -> List[Dict[str, str]]:
        repair_context = {
            **context,
            "current_user_message": user_message,
        }
        system_prompt = (
            self.generate_system_prompt(repair_context)
            + "\n\n## CRITICAL TOOL REPAIR\n"
            + "Your previous response promised a development action but emitted no tool call. "
            + "For this retry, emit exactly one available tool call and no prose. "
            + "For small new projects, call `write` for the first real source file; "
            + "`write` creates parent directories automatically."
        )
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Original request:\n{user_message}\n\n"
                    f"Previous non-executable response:\n{previous_response[:1000]}\n\n"
                    "Emit exactly one tool call now. Do not answer with intent text."
                ),
            },
        ]
    
    @staticmethod
    def _tool_calls_to_opencode_command(tool_calls: Optional[List[Dict]]) -> Optional[str]:
        """Convert OpenAI-compatible tool_calls into an OpenCode command string."""
        if not tool_calls:
            return None

        tc = tool_calls[0]
        func = tc.get("function", {})
        name = func.get("name", "")
        raw_args = func.get("arguments", "{}")

        try:
            import json as _json
            args = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except Exception:
            return None

        if name == "bash":
            command = DevSynapseBrain._escape_opencode_arg(args.get("command", ""))
            if command:
                return f'bash "{command}"'
        elif name == "read":
            path = DevSynapseBrain._escape_opencode_arg(args.get("path", ""))
            if path:
                return f'read "{path}"'
        elif name == "glob":
            pattern = DevSynapseBrain._escape_opencode_arg(args.get("pattern", ""))
            if pattern:
                return f'glob "{pattern}"'
        elif name == "grep":
            pattern = DevSynapseBrain._escape_opencode_arg(args.get("pattern", ""))
            include = DevSynapseBrain._escape_opencode_arg(args.get("include", ""))
            if pattern:
                if include:
                    return f'grep "{pattern}" --include="{include}"'
                return f'grep "{pattern}"'
        elif name == "edit":
            path = DevSynapseBrain._escape_opencode_arg(args.get("path", ""))
            old = DevSynapseBrain._escape_opencode_arg(args.get("old", ""))
            new = DevSynapseBrain._escape_opencode_arg(args.get("new", ""))
            if path:
                return f'edit "{path}" --old="{old}" --new="{new}"'
        elif name == "write":
            path = DevSynapseBrain._escape_opencode_arg(args.get("path", ""))
            content = DevSynapseBrain._escape_opencode_arg(args.get("content", ""))
            if path:
                return f'write "{path}" --content="{content}"'

        return None

    @staticmethod
    def _escape_opencode_arg(value: object) -> str:
        """Escape a JSON tool argument so it remains one quoted OpenCode argument."""
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )

    @staticmethod
    def _can_autoexecute_command(command: str, user_role: Optional[str] = None) -> bool:
        """Check whether a command may run without an explicit confirmation click."""
        if not command:
            return False

        lower = command.lower()
        for pattern in BLACKLISTED_PATTERNS:
            if pattern in lower:
                return False

        parts = command.split(None, 1)
        cmd_type = parts[0].lower() if parts else ""

        if user_role == "admin":
            return cmd_type in set(ALLOWED_COMMANDS)

        if cmd_type == "bash":
            bash_command = parts[1].strip("\"' ") if len(parts) > 1 else ""
            if DevSynapseBrain._is_read_only_bash_command(bash_command):
                return True

        return False

    @staticmethod
    def _is_read_only_command(command: str) -> bool:
        """Compatibility wrapper for non-admin low-risk auto-execution checks."""
        return DevSynapseBrain._can_autoexecute_command(command, user_role="user")

    @staticmethod
    def _is_read_only_bash_command(command: str) -> bool:
        try:
            parts = shlex.split(command)
        except ValueError:
            return False

        if not parts:
            return False

        first_word = parts[0].lower()
        if first_word in AUTOEXEC_READ_ONLY_BASH_COMMANDS:
            return not DevSynapseBrain._has_output_redirect_flag(parts[1:])

        if first_word == "git":
            if len(parts) == 1:
                return True
            subcommand = parts[1].lower()
            if subcommand not in AUTOEXEC_READ_ONLY_GIT_SUBCOMMANDS:
                return False
            return not DevSynapseBrain._has_output_redirect_flag(parts[2:])

        return False

    @staticmethod
    def _has_output_redirect_flag(parts: List[str]) -> bool:
        return any(part in AUTOEXEC_BASH_OUTPUT_FLAGS or part.startswith("--output=") for part in parts)

    def _extract_opencode_command(self, response_text: str) -> Optional[str]:
        """
        Extrai comando OpenCode da resposta do LLM
        
        Procura por padrões como:
        - bash "comando"
        - read "/path"
        - etc.
        """
        
        # Padrões para diferentes comandos
        patterns = {
            "bash": r'bash\s+"([^"]+)"',
            "read": r'read\s+"([^"]+)"',
            "glob": r'glob\s+"([^"]+)"',
            "grep": r'grep\s+"([^"]+)"(?:\s+--include="([^"]+)")?',
            "edit": r'edit\s+"([^"]+)"\s+--old="([^"]+)"\s+--new="([^"]+)"',
            "write": r'write\s+"([^"]+)"\s+--content="([^"]+)"'
        }

        matches = []
        for command_type, pattern in patterns.items():
            for match in re.finditer(pattern, response_text, re.IGNORECASE | re.DOTALL):
                matches.append((match.start(), command_type, match))

        if not matches:
            return self._extract_flexible_opencode_command(response_text)

        _, command_type, match = max(matches, key=lambda item: item[0])

        if command_type == "bash":
            return f'bash "{match.group(1)}"'
        elif command_type == "read":
            return f'read "{match.group(1)}"'
        elif command_type == "glob":
            return f'glob "{match.group(1)}"'
        elif command_type == "grep":
            if match.group(2):  # Tem include
                return f'grep "{match.group(1)}" --include="{match.group(2)}"'
            else:
                return f'grep "{match.group(1)}"'
        elif command_type == "edit":
            return (
                f'edit "{match.group(1)}" '
                f'--old="{match.group(2)}" --new="{match.group(3)}"'
            )
        elif command_type == "write":
            return f'write "{match.group(1)}" --content="{match.group(2)}"'

        return self._extract_flexible_opencode_command(response_text)

    def _extract_flexible_opencode_command(self, response_text: str) -> Optional[str]:
        """Handle loosely formatted commands such as `bash ls -la` or bare `docker ps`."""

        lines = [line.strip() for line in response_text.splitlines() if line.strip()]

        for line in reversed(lines):
            normalized = line.strip().strip("`").strip()
            normalized = re.sub(r"^[-*]\s+", "", normalized)
            normalized = re.sub(r"^\d+\.\s+", "", normalized)

            if not normalized:
                continue

            explicit = self._normalize_explicit_command_line(normalized)
            if explicit:
                return explicit

            bare_shell = self._normalize_bare_shell_line(normalized)
            if bare_shell:
                return bare_shell

        return None

    def _normalize_explicit_command_line(self, line: str) -> Optional[str]:
        if any(operator in line for operator in ["&&", "||", ">", "|", ";"]):
            return None

        explicit_match = re.match(
            r'^(bash|read|glob|grep)\s+(?:"([^"]+)"|(.+))$',
            line,
            re.IGNORECASE,
        )
        if not explicit_match:
            return None

        command_type = explicit_match.group(1).lower()
        argument = (explicit_match.group(2) or explicit_match.group(3) or "").strip()
        if not argument:
            return None

        if command_type == "bash":
            return f'bash "{argument}"'
        if command_type == "read":
            return f'read "{argument}"'
        if command_type == "glob":
            return f'glob "{argument}"'
        if command_type == "grep":
            return f'grep "{argument}"'

        return None

    def _normalize_bare_shell_line(self, line: str) -> Optional[str]:
        if any(operator in line for operator in ["&&", "||", ">", "|", ";"]):
            return None

        bare_shell_match = re.match(r'^([a-zA-Z0-9_.-]+)(?:\s+.+)?$', line)
        if not bare_shell_match:
            return None

        if any(punct in line for punct in [":", "?", "!", "```"]):
            return None

        first_word = bare_shell_match.group(1).lower()
        if first_word not in {
            "ls",
            "pwd",
            "cat",
            "head",
            "tail",
            "grep",
            "find",
            "git",
            "npm",
            "node",
            "python",
            "python3",
            "echo",
            "touch",
            "mkdir",
            "cp",
            "mv",
            "rm",
            "chmod",
            "df",
            "du",
            "ps",
            "top",
            "kill",
            "curl",
            "wget",
            "tar",
            "gzip",
            "gunzip",
            "zip",
            "unzip",
            "docker",
        }:
            return None

        return f'bash "{line}"'

    def _sanitize_unconfirmed_execution_claims(
        self,
        response_text: str,
        opencode_command: Optional[str],
    ) -> str:
        """Prevent the assistant from claiming side effects that never executed."""

        if opencode_command:
            return response_text

        shell_like = re.search(
            r'(^|\n)\s*(echo|cat|touch|mkdir|rm|mv|cp|find|grep|sed)\b.*(>|>>|\|\||&&)',
            response_text,
            re.IGNORECASE,
        )
        success_claim = re.search(
            r'\b(done|completed|file created|created the file|finished|ready[!,]?\s+created)\b',
            response_text,
            re.IGNORECASE,
        )

        if not shell_like and not success_claim:
            return response_text

        return (
            "I haven't executed any changes yet.\n\n"
            "I can only propose actions using my available tools, which then need "
            "to be confirmed in the interface. Ask me to try again and I'll respond "
            "with a single executable command."
        )

    def _get_fallback_response(self, messages: List[Dict]) -> str:
        """Resposta degradada quando a API DeepSeek falha."""
        
        fallback_responses = [
            "The DeepSeek API timed out and I switched to degraded mode. "
            "I can still help with basic tasks if you specify what you need.",

            "DeepSeek is temporarily unavailable. "
            "You can ask me to run specific commands like 'bash ls' or 'read file'.",

            "Sorry, I'm having technical difficulties. "
            "In the meantime, I can help with tasks that don't require complex AI analysis."
        ]
        
        import random
        return random.choice(fallback_responses)
