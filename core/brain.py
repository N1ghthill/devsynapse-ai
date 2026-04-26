"""
Núcleo do DevSynapse - Integração com DeepSeek API
"""

import logging
import re
import shlex
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import AsyncIterator, Dict, List, Optional, Tuple

import requests

import config.settings as app_settings
from config.settings import BLACKLISTED_PATTERNS, READ_ONLY_COMMANDS
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
        self.api_key = app_settings.DEEPSEEK_API_KEY
        self.deepseek_model = settings.deepseek_model
        self.deepseek_base_url = settings.deepseek_base_url
        self.reasoning_effort = settings.deepseek_reasoning_effort
        self.thinking_enabled = settings.deepseek_thinking_enabled
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self.request_timeout = settings.llm_request_timeout
        self.deepseek_flash_pricing = {
            "cache_hit": Decimal(
                str(settings.deepseek_flash_input_cache_hit_price_usd_per_million)
            ),
            "cache_miss": Decimal(
                str(settings.deepseek_flash_input_cache_miss_price_usd_per_million)
            ),
            "output": Decimal(str(settings.deepseek_flash_output_price_usd_per_million)),
        }
        self.deepseek_pro_pricing = {
            "cache_hit": Decimal(
                str(settings.deepseek_pro_input_cache_hit_price_usd_per_million)
            ),
            "cache_miss": Decimal(
                str(settings.deepseek_pro_input_cache_miss_price_usd_per_million)
            ),
            "output": Decimal(str(settings.deepseek_pro_output_price_usd_per_million)),
        }
        
        if not self.api_key:
            logger.warning("DeepSeek API key não configurada")
        
    def generate_system_prompt(self, context: Dict) -> str:
        """Gera prompt de sistema personalizado baseado no contexto"""
        
        user_prefs = self.memory.get_user_preferences()
        projects_info = self.memory.get_projects_context()
        active_project_name = context.get("project_name")
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
            return "Processamento cancelado por plugin.", None
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

        # Chamar API com loop de auto-execução para comandos read-only
        max_autoexec_rounds = 5
        round_count = 0
        aggregated_usage = None
        opencode_command = None
        response_text = ""

        while round_count < max_autoexec_rounds:
            round_count += 1
            llm_result = self._coerce_llm_result(await self._call_llm_api(messages))
            response_text = llm_result.content
            opencode_command = self._tool_calls_to_opencode_command(llm_result.tool_calls)
            if opencode_command is None:
                opencode_command = self._extract_opencode_command(response_text)
            aggregated_usage = self._merge_usage(aggregated_usage, llm_result.usage)

            autoexec_enabled = bool(user_id and user_role)
            if not (autoexec_enabled and opencode_command and self._is_read_only_command(opencode_command)):
                break

            success, msg, output, status, reason, proj = await self.opencode.execute_command(
                opencode_command,
                user_id=user_id,
                project_name=effective_project_name,
                user_role=user_role,
                project_mutation_allowlist=project_mutation_allowlist or [],
            )

            await self.memory.save_command_execution(
                conversation_id=conversation_id,
                command=opencode_command,
                success=success,
                result=msg,
                output=output,
                status=status,
                reason_code=reason,
                project_name=proj,
            )

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

        # Salvar na memória
        await self.memory.save_interaction(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=response_text,
            opencode_command=opencode_command,
            llm_usage=aggregated_usage,
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
    
    async def _call_llm_api(self, messages: List[Dict]) -> LLMResult:
        """Chama API do DeepSeek e retorna resposta degradada se a API falhar."""
        
        # Tentar DeepSeek primeiro
        if self.api_key:
            try:
                return await self._call_deepseek_api(messages)
            except Exception as e:
                logger.warning(f"DeepSeek API falhou: {e}. Usando resposta degradada.")

        return LLMResult(content=self._get_fallback_response(messages))
    
    async def _call_deepseek_api(self, messages: List[Dict]) -> LLMResult:
        """Chama API do DeepSeek"""
        
        url = f"{self.deepseek_base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        thinking_config = {"type": "enabled" if self.thinking_enabled else "disabled"}
        payload = {
            "model": self.deepseek_model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": False,
            "tools": OPENCODE_TOOLS,
            "tool_choice": "auto",
            "reasoning_effort": self.reasoning_effort,
            "thinking": thinking_config,
        }
        if not self.thinking_enabled:
            payload["temperature"] = self.temperature
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=(5, self.request_timeout),
        )
        response.raise_for_status()
        
        result = response.json()
        choice = result["choices"][0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")
        reasoning_content = message.get("reasoning_content")
        usage = self._build_usage_snapshot(
            provider="deepseek",
            model=result.get("model") or self.deepseek_model,
            usage=result.get("usage") or {},
        )
        return LLMResult(
            content=content,
            provider="deepseek",
            model=result.get("model") or self.deepseek_model,
            usage=usage,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )

    async def _call_deepseek_api_streaming(
        self, messages: List[Dict]
    ) -> AsyncIterator[Dict]:
        """Call DeepSeek API with streaming, yielding delta chunks."""
        import httpx

        url = f"{self.deepseek_base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        thinking_config = {"type": "enabled" if self.thinking_enabled else "disabled"}
        payload = {
            "model": self.deepseek_model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": True,
            "tools": OPENCODE_TOOLS,
            "tool_choice": "auto",
            "reasoning_effort": self.reasoning_effort,
            "thinking": thinking_config,
        }
        if not self.thinking_enabled:
            payload["temperature"] = self.temperature

        collected_content = ""
        collected_reasoning = ""
        collected_usage: Optional[Dict] = None
        tool_call_buffers: Dict[int, Dict] = {}

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=httpx.Timeout(5.0, read=self.request_timeout),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json

                        chunk = json.loads(data_str)
                    except Exception:
                        continue

                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        reasoning = delta.get("reasoning_content", "")
                        if reasoning:
                            collected_reasoning += reasoning
                            yield {"type": "reasoning", "content": reasoning}

                        content = delta.get("content", "")
                        if content:
                            collected_content += content
                            yield {"type": "text", "content": content}

                        tc_deltas = delta.get("tool_calls")
                        if tc_deltas:
                            for tc in tc_deltas:
                                idx = tc.get("index", 0)
                                buf = tool_call_buffers.setdefault(
                                    idx,
                                    {"id": None, "type": "function", "function": {"name": "", "arguments": ""}},
                                )
                                if "id" in tc and tc["id"]:
                                    buf["id"] = tc["id"]
                                if tc.get("function") and tc["function"].get("name"):
                                    buf["function"]["name"] = tc["function"]["name"]
                                if tc.get("function") and "arguments" in tc["function"]:
                                    buf["function"]["arguments"] += tc["function"]["arguments"]

                    usage_chunk = chunk.get("usage")
                    if usage_chunk:
                        collected_usage = usage_chunk

        collected_tool_calls = [
            tool_call_buffers[idx] for idx in sorted(tool_call_buffers)
        ] or None

        usage = self._build_usage_snapshot(
            provider="deepseek",
            model=self.deepseek_model,
            usage=collected_usage or {},
        )
        yield {"type": "done", "content": collected_content, "usage": usage, "tool_calls": collected_tool_calls, "reasoning_content": collected_reasoning or None}

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

        if not self.api_key:
            yield {"type": "text", "content": self._get_fallback_response(messages)}
            yield {"type": "done", "usage": None}
            return

        full_response = ""
        collected_tool_calls = None
        try:
            async for chunk in self._call_deepseek_api_streaming(messages):
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

        await self.memory.save_interaction(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=full_response,
            opencode_command=opencode_command,
            llm_usage=usage,
            project_name=effective_project_name,
        )

        yield {"type": "done", "usage": usage}

    def _coerce_llm_result(self, result: str | LLMResult) -> LLMResult:
        if isinstance(result, LLMResult):
            return result
        return LLMResult(content=result)

    def _build_usage_snapshot(
        self,
        provider: str,
        model: str,
        usage: Dict,
    ) -> Dict[str, int | float | str | None]:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        prompt_cache_hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
        prompt_cache_miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
        reasoning_tokens = int(
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
        )

        if prompt_tokens and not prompt_cache_hit_tokens and not prompt_cache_miss_tokens:
            prompt_cache_miss_tokens = prompt_tokens

        estimated_cost_usd = self._calculate_usage_cost(
            provider=provider,
            model=model,
            prompt_cache_hit_tokens=prompt_cache_hit_tokens,
            prompt_cache_miss_tokens=prompt_cache_miss_tokens,
            completion_tokens=completion_tokens,
        )

        return {
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_cache_hit_tokens": prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": prompt_cache_miss_tokens,
            "reasoning_tokens": reasoning_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        }

    def _calculate_usage_cost(
        self,
        provider: str,
        model: str,
        prompt_cache_hit_tokens: int,
        prompt_cache_miss_tokens: int,
        completion_tokens: int,
    ) -> Optional[float]:
        if provider != "deepseek":
            return None

        pricing = self._get_deepseek_model_pricing(model)
        if pricing is None:
            return None

        per_million = Decimal("1000000")
        total = (
            Decimal(prompt_cache_hit_tokens) * pricing["cache_hit"] / per_million
            + Decimal(prompt_cache_miss_tokens) * pricing["cache_miss"] / per_million
            + Decimal(completion_tokens) * pricing["output"] / per_million
        )
        return float(total.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))

    def _get_deepseek_model_pricing(self, model: str) -> Optional[Dict[str, Decimal]]:
        normalized = model.lower()
        if normalized in {"deepseek-chat", "deepseek-v4-flash"}:
            return self.deepseek_flash_pricing
        if normalized == "deepseek-v4-pro":
            return self.deepseek_pro_pricing
        return None

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
    def _is_read_only_command(command: str) -> bool:
        """Check whether an OpenCode command is read-only and safe for auto-execution."""
        if not command:
            return False

        lower = command.lower()
        for pattern in BLACKLISTED_PATTERNS:
            if pattern in lower:
                return False

        parts = command.split(None, 1)
        cmd_type = parts[0] if parts else ""

        if cmd_type in READ_ONLY_COMMANDS:
            return True

        if cmd_type == "bash":
            bash_command = parts[1].strip("\"' ") if len(parts) > 1 else ""
            if DevSynapseBrain._is_read_only_bash_command(bash_command):
                return True

        return False

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
        if not self.api_key:
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

            payload = {
                "model": self.deepseek_model,
                "messages": messages,
                "max_tokens": 400,
                "stream": False,
                "thinking": {"type": "disabled"},
            }

            url = f"{self.deepseek_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=(5, 15))
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

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
