"""
Núcleo do DevSynapse - Integração com DeepSeek API
"""

import logging
import re
import shlex
from dataclasses import dataclass
from decimal import Decimal
from typing import AsyncIterator, Dict, List, Optional, Tuple

import config.settings as app_settings
from config.settings import BLACKLISTED_PATTERNS, READ_ONLY_COMMANDS
from core.deepseek import DeepSeekClient
from core.llm_optimization import ModelRoute, ModelRouter, build_task_profile
from core.plugin_system import plugin_manager

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, int | float | str | None]] = None
    tool_calls: Optional[List[Dict]] = None
    reasoning_content: Optional[str] = None


OPENCODE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "strict": True,
            "description": (
                "Execute a shell command on the system. "
                "Use to list files, check git status, run tests, install dependencies, etc."
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
            "description": "Write content to a file (overwrites if it exists).",
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
        )

        if not self.deepseek.configured:
            logger.warning("DeepSeek API key não configurada")

    @property
    def api_key(self) -> Optional[str]:
        return self.deepseek.api_key

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self.deepseek.api_key = value
        
    def generate_system_prompt(self, context: Dict) -> str:
        """Gera prompt de sistema personalizado baseado no contexto"""
        
        user_prefs = self.memory.get_user_preferences()
        projects_info = self.memory.get_projects_context()
        agent_learning = self._get_agent_learning_context()
        active_project_name = context.get("project_name")
        current_request = context.get("current_user_message") or ""
        procedural_memory = self._get_project_memory_context(active_project_name, current_request)
        skills_context = self._get_skills_context(current_request, active_project_name)
        active_project_section = (
            f"\n## PROJETO ATIVO\n{active_project_name}\n"
            if active_project_name
            else ""
        )
        
        system_prompt = f"""You are DevSynapse (Development Synapse),
Irving Ruas (also known as N1ghthill)'s intelligent development assistant.

## YOUR ROLE
You are a senior software engineer and technical architect who helps Irving with his projects.
Blend deep technical skills with natural conversational communication.

## IRVING'S PREFERENCES
{user_prefs}

## AGENT LEARNING
{agent_learning}

## PROCEDURAL MEMORY
{procedural_memory}

## SKILLS
{skills_context}

## CURRENT PROJECTS
{projects_info}
{active_project_section}

## CAPABILITIES
1. **Technical conversation** - Discuss architecture, design patterns, trade-offs
2. **Code analysis** - Review, suggest improvements, detect issues
3. **Command execution** - You have tools to run shell commands, read/edit/write files, search code
4. **Planning** - Help break down complex tasks
5. **Documentation** - Help document decisions and code

## RESPONSE FORMAT
- Be direct yet friendly
- When relevant, use your available tools to take action
- Explain the "why" behind your suggestions
- Consider cost, complexity, and Irving's preferences
- If unsure, be honest
- Never claim you created, edited, deleted, or executed something before actual execution is confirmed
- Never write raw shell constructs like `echo file > x.txt`; use your tools instead
- Propose at most one tool call per response

## EXAMPLES
User: "Show me the BotAssist files"
You: "I'll list the BotAssist files for you." [uses bash tool with: ls -la /path/to/botassist]

User: "Analyze this code's architecture"
You: "Let me analyze. First, I'll read the code." [uses read tool] "Based on the analysis..."

User: "I need to add caching to BotAssist"
You: "Based on your preference for simple, low-cost solutions, I suggest starting with in-memory cache using node-cache. This avoids additional costs and keeps things simple. Can I help implement this?"

## IMPORTANT
- Always consider the current project context
- Learn from Irving's feedback
- Reuse relevant procedural memory and loaded skills before inventing a workflow
- After a complex task, command success, or hard-won fix, allow the learning nudge to save
  reusable memory or skills for future turns
- Prioritize solutions aligned with his known preferences
"""
        
        return system_prompt

    async def process_message(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        project_name: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        project_mutation_allowlist: Optional[List[str]] = None,
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        """
        Processa uma mensagem do usuário e retorna resposta + comando OpenCode.

        When user_id and user_role are provided, read-only commands are auto-executed
        and the result is fed back to the LLM in a loop until a final answer is reached.
        Mutation commands still require explicit confirmation.
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
        max_autoexec_rounds = 5
        round_count = 0
        aggregated_usage = None
        opencode_command = None
        response_text = ""
        autoexecuted_command = None

        while round_count < max_autoexec_rounds:
            round_count += 1
            llm_result = self._coerce_llm_result(await self._call_llm_api(messages, route=route))
            response_text = llm_result.content
            opencode_command = self._tool_calls_to_opencode_command(llm_result.tool_calls)
            if opencode_command is None:
                opencode_command = self._extract_opencode_command(response_text)
            aggregated_usage = self._merge_usage(aggregated_usage, llm_result.usage)

            autoexec_enabled = bool(self.api_key and user_id and user_role)
            if not (
                autoexec_enabled
                and opencode_command
                and self._can_autoexecute_command(opencode_command, user_role)
            ):
                break

            success, msg, output, status, reason, proj = await self.opencode.execute_command(
                opencode_command,
                user_id=user_id,
                project_name=effective_project_name,
                user_role=user_role,
                project_mutation_allowlist=project_mutation_allowlist or [],
            )
            autoexecuted_command = {
                "command": opencode_command,
                "success": success,
                "result": msg,
                "output": output,
                "status": status,
                "reason_code": reason,
                "project_name": proj,
            }

            if not success:
                response_text = (
                    f"{response_text}\n\n"
                    f"The command `{opencode_command}` could not be executed: {msg}"
                )
                opencode_command = None
                break

            tool_result = output or msg
            selected_tool_calls = llm_result.tool_calls[:1] if llm_result.tool_calls else None
            if selected_tool_calls and selected_tool_calls[0].get("id"):
                messages.append({
                    "role": "assistant",
                    "content": response_text or "",
                    "tool_calls": selected_tool_calls,
                })
                if llm_result.reasoning_content:
                    messages[-1]["reasoning_content"] = llm_result.reasoning_content
                messages.append({
                    "role": "tool",
                    "tool_call_id": selected_tool_calls[0]["id"],
                    "content": tool_result[:3000],
                })
            else:
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": f"Command output:\n{tool_result[:3000]}",
                })

        await plugin_manager.emit_event("brain:after_llm_call", {"response": response_text})

        response_text = self._sanitize_unconfirmed_execution_claims(
            response_text,
            opencode_command,
        )

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
            )

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
        persisted = self._get_persisted_app_settings()
        settings = app_settings.get_settings()
        profile = build_task_profile(user_message, context=context)
        learned_policy = self._get_agent_learning(profile.signature)
        router = ModelRouter(
            flash_model=str(
                persisted.get("deepseek_flash_model", settings.deepseek_flash_model)
            ),
            pro_model=str(persisted.get("deepseek_pro_model", settings.deepseek_pro_model)),
            default_model=str(persisted.get("deepseek_model", self.deepseek.model)),
            routing_enabled=self._as_bool(
                persisted.get("llm_model_routing_enabled", settings.llm_model_routing_enabled)
            ),
            auto_economy_enabled=self._as_bool(
                persisted.get("llm_auto_economy_enabled", settings.llm_auto_economy_enabled)
            ),
        )
        budget_status = None
        if router.auto_economy_enabled and hasattr(self.memory, "get_llm_budget_status"):
            try:
                budget_status = self.memory.get_llm_budget_status()
            except Exception:
                logger.debug("Could not read LLM budget status for routing", exc_info=True)

        route = router.select_model(
            user_message,
            context=context,
            budget_status=budget_status,
            learned_policy=learned_policy,
        )
        logger.info(
            "LLM route selected: model=%s complexity=%s reason=%s budget=%s fallback=%s",
            route.model,
            route.complexity,
            route.reason,
            route.budget_mode,
            route.fallback_model,
        )
        return route

    def _get_agent_learning(self, task_signature: str) -> Optional[Dict]:
        if not hasattr(self.memory, "get_agent_learning"):
            return None
        try:
            return self.memory.get_agent_learning(task_signature)
        except Exception:
            logger.debug("Could not load agent learning for routing", exc_info=True)
            return None

    def _get_agent_learning_context(self) -> str:
        if not hasattr(self.memory, "get_agent_learning_context"):
            return "Nenhum padrão de agente aprendido ainda."
        try:
            return self.memory.get_agent_learning_context()
        except Exception:
            logger.debug("Could not load agent learning context", exc_info=True)
            return "Nenhum padrão de agente aprendido ainda."

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

    def _get_persisted_app_settings(self) -> Dict[str, str]:
        if not hasattr(self.memory, "get_app_settings"):
            return {}
        try:
            persisted = self.memory.get_app_settings()
            return persisted if isinstance(persisted, dict) else {}
        except Exception:
            logger.debug("Could not load persisted app settings", exc_info=True)
            return {}

    @staticmethod
    def _as_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    async def _call_llm_api(
        self,
        messages: List[Dict],
        route: Optional[ModelRoute] = None,
    ) -> LLMResult:
        """Chama API do DeepSeek e retorna resposta degradada se a API falhar."""

        if self.deepseek.configured:
            model = route.model if route else self.deepseek.model
            try:
                result = self.deepseek.chat_completion(messages, OPENCODE_TOOLS, model=model)
                return LLMResult(
                    content=result["content"],
                    provider=result["provider"],
                    model=result["model"],
                    usage=result["usage"],
                    tool_calls=result["tool_calls"],
                    reasoning_content=result["reasoning_content"],
                )
            except Exception as e:
                fallback_model = route.fallback_model if route else None
                if fallback_model and fallback_model != model:
                    try:
                        logger.warning(
                            "DeepSeek %s call failed (%s); retrying with %s",
                            model,
                            e,
                            fallback_model,
                        )
                        result = self.deepseek.chat_completion(
                            messages,
                            OPENCODE_TOOLS,
                            model=fallback_model,
                        )
                        return LLMResult(
                            content=result["content"],
                            provider=result["provider"],
                            model=result["model"],
                            usage=result["usage"],
                            tool_calls=result["tool_calls"],
                            reasoning_content=result["reasoning_content"],
                        )
                    except Exception as fallback_error:
                        logger.warning(
                            "DeepSeek fallback model %s failed: %s",
                            fallback_model,
                            fallback_error,
                        )
                logger.warning(f"DeepSeek API falhou: {e}. Usando resposta degradada.")
                return LLMResult(content=self._get_fallback_response(messages))

        return LLMResult(content=self._get_fallback_response(messages))

    async def process_message_streaming(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> AsyncIterator[Dict]:
        """Process a message and stream the response as SSE events.

        Yields:
            {"type": "text", "content": "..."}
            {"type": "command", "command": "..."}
            {"type": "done", "usage": {...}, ...}
        """

        context = await self.memory.get_conversation_context(conversation_id)
        effective_project_name = project_name or context.get("project_name")
        if effective_project_name:
            context["project_name"] = effective_project_name

        messages = self._prepare_messages(user_message, context)
        route = self._select_llm_route(user_message, context)

        if not self.deepseek.configured:
            fallback = self._get_fallback_response(messages)
            yield {"type": "text", "content": fallback}
            yield {"type": "done", "usage": None}
            return

        full_response = ""
        collected_tool_calls = None
        usage = None
        try:
            async for chunk in self.deepseek.chat_completion_streaming(
                messages,
                OPENCODE_TOOLS,
                model=route.model,
            ):
                if chunk["type"] == "text":
                    full_response += chunk["content"]
                    yield chunk
                elif chunk["type"] == "reasoning":
                    yield chunk
                elif chunk["type"] == "done":
                    full_response = chunk.get("content", full_response)
                    usage = chunk.get("usage")
                    collected_tool_calls = chunk.get("tool_calls")
                    break
        except Exception as e:
            if route.fallback_model and not full_response:
                try:
                    logger.warning(
                        "DeepSeek streaming with %s failed (%s); retrying with %s",
                        route.model,
                        e,
                        route.fallback_model,
                    )
                    async for chunk in self.deepseek.chat_completion_streaming(
                        messages,
                        OPENCODE_TOOLS,
                        model=route.fallback_model,
                    ):
                        if chunk["type"] == "text":
                            full_response += chunk["content"]
                            yield chunk
                        elif chunk["type"] == "reasoning":
                            yield chunk
                        elif chunk["type"] == "done":
                            full_response = chunk.get("content", full_response)
                            usage = chunk.get("usage")
                            collected_tool_calls = chunk.get("tool_calls")
                            break
                except Exception as fallback_error:
                    logger.warning(f"DeepSeek streaming fallback failed: {fallback_error}")
                    fallback = self._get_fallback_response(messages)
                    yield {"type": "text", "content": fallback}
                    yield {"type": "done", "usage": None}
                    return
            else:
                logger.warning(f"DeepSeek streaming failed: {e}")
                fallback = self._get_fallback_response(messages)
                yield {"type": "text", "content": fallback}
                yield {"type": "done", "usage": None}
                return

        opencode_command = self._tool_calls_to_opencode_command(collected_tool_calls)
        if opencode_command is None:
            opencode_command = self._extract_opencode_command(full_response)

        if opencode_command:
            yield {"type": "command", "command": opencode_command}

        persisted_project_name = await self.memory.save_interaction(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=full_response,
            opencode_command=opencode_command,
            llm_usage=usage,
            project_name=effective_project_name,
        )
        self._record_agent_route_decision(
            conversation_id=conversation_id,
            route=route,
            usage=usage,
            project_name=persisted_project_name,
            opencode_command=opencode_command,
        )
        review_project_name = persisted_project_name if isinstance(persisted_project_name, str) else None
        self._review_completed_task(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=full_response,
            project_name=review_project_name,
            opencode_command=opencode_command,
            route=route,
            tool_iterations=1 if opencode_command else 0,
        )

        yield {"type": "done", "usage": usage, "project_name": persisted_project_name}

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
            return cmd_type in {"bash", *READ_ONLY_COMMANDS, "edit", "write"}

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

    async def interpret_execution_result(
        self,
        conversation_id: str,
        command: str,
        output: str,
        project_name: Optional[str] = None,
    ) -> Optional[str]:
        """Feed command output back to the LLM for natural language interpretation."""
        if not self.deepseek.configured:
            return None

        try:
            context = await self.memory.get_conversation_context(conversation_id)
            system_prompt = self.generate_system_prompt(context)

            messages = [{"role": "system", "content": system_prompt}]

            history = context.get("conversation_history") or []
            for msg in history[-6:]:
                messages.append(msg)

            result_text = output[:2000] if output else "(no output)"

            if result_text:
                messages.append({
                    "role": "user",
                    "content": (
                        f"I executed this command: `{command}`\n\n"
                        f"Output:\n```\n{result_text}\n```\n\n"
                        f"Briefly explain what this output means in natural language. "
                        f"Be concise — 1 to 3 sentences max."
                    ),
                })

            result = self.deepseek.chat_completion(
                messages,
                max_tokens=400,
                thinking={"type": "disabled"},
            )
            return result["content"].strip()

        except Exception:
            logger.debug("Failed to interpret execution result", exc_info=True)
            return None

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
