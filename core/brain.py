"""
Núcleo do DevSynapse - Integração com DeepSeek API
"""

import logging
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import AsyncIterator, Dict, List, Optional, Tuple

import requests

import config.settings as app_settings
from core.plugin_system import plugin_manager

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, int | float | str | None]] = None


class DevSynapseBrain:
    """Gerencia a inteligência do DevSynapse via API DeepSeek."""
    
    def __init__(self, memory_system, opencode_bridge):
        self.memory = memory_system
        self.opencode = opencode_bridge
        settings = app_settings.get_settings()
        self.api_key = app_settings.DEEPSEEK_API_KEY
        self.deepseek_model = settings.deepseek_model
        self.deepseek_base_url = settings.deepseek_base_url
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
        
        system_prompt = f"""Você é DevSynapse (Development Synapse),
assistente de desenvolvimento inteligente do Irving Ruas (também conhecido como N1ghthill).

## SEU PAPEL
Você é um engenheiro sênior de software e arquiteto técnico que ajuda Irving em seus projetos.
Combine habilidades técnicas profundas com comunicação conversacional natural.

## PREFERÊNCIAS DO IRVING
{user_prefs}

## PROJETOS ATUAIS
{projects_info}
{active_project_section}

## HABILIDADES DISPONÍVEIS
1. **Conversação técnica** - Discuta arquitetura, design patterns, trade-offs
2. **Análise de código** - Revise, sugere melhorias, detecte problemas
3. **Execução de comandos** - Pode executar comandos OpenCode (bash, read, edit, etc.)
4. **Planejamento** - Ajude a quebrar tarefas complexas
5. **Documentação** - Ajude a documentar decisões e código

## FORMATO DE RESPOSTA
- Seja direto mas amigável
- Quando relevante, sugira comandos OpenCode específicos
- Explique o "porquê" das suas sugestões
- Considere custo, complexidade e preferências do Irving
- Se não tiver certeza, seja honesto
- Nunca afirme que criou, editou, apagou ou executou algo antes da execução real ser confirmada
- Nunca escreva shell cru como `echo arquivo > x.txt`; use apenas formatos OpenCode válidos
- Se precisar propor uma ação, forneça no máximo um comando OpenCode executável por resposta

## COMANDOS OPENCODE
Use estes formatos quando apropriado:
- `bash "comando shell aqui"`
- `read "/caminho/do/arquivo"`
- `glob "**/*.py"`
- `grep "padrão" --include="*.js"`
- `edit "/caminho/do/arquivo" --old="texto antigo" --new="texto novo"`
- `write "/caminho/do/arquivo" --content="conteúdo"`

## EXEMPLOS
Usuário: "Mostre os arquivos do BotAssist"
Você: "Vou listar os arquivos do BotAssist para você. bash "ls -la /home/irving/ruas/repos/botassist-whatsapp""

Usuário: "Analise a arquitetura deste código"
Você: "Deixe-me analisar. Primeiro, vou ler o código: read "/caminho/do/arquivo". Baseado na análise..."

Usuário: "Preciso adicionar cache ao BotAssist"
Você: "Baseado nas suas preferências por soluções simples e de baixo custo, sugiro começar com cache em memória usando `node-cache`. Isso evita custos adicionais e mantém a simplicidade. Posso ajudar a implementar?"

## IMPORTANTE
- Sempre considere o contexto do projeto atual
- Aprenda com feedback do Irving
- Priorize soluções alinhadas com suas preferências conhecidas
"""
        
        return system_prompt
    
    async def process_message(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        """
        Processa uma mensagem do usuário e retorna resposta + comando OpenCode
        
        Returns:
            Tuple[response_text, opencode_command]
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

        # Chamar API
        llm_result = self._coerce_llm_result(await self._call_llm_api(messages))
        response_text = llm_result.content
        opencode_command = self._extract_opencode_command(response_text)
        aggregated_usage = self._merge_usage(None, llm_result.usage)

        if self._needs_command_repair(response_text, opencode_command):
            repair_messages = self._build_command_repair_messages(messages, response_text)
            repair_result = self._coerce_llm_result(await self._call_llm_api(repair_messages))
            response_text = repair_result.content
            opencode_command = self._extract_opencode_command(response_text)
            aggregated_usage = self._merge_usage(aggregated_usage, repair_result.usage)

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
        
        payload = {
            "model": self.deepseek_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False
        }
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=(5, self.request_timeout),
        )
        response.raise_for_status()
        
        result = response.json()
        usage = self._build_usage_snapshot(
            provider="deepseek",
            model=result.get("model") or self.deepseek_model,
            usage=result.get("usage") or {},
        )
        return LLMResult(
            content=result["choices"][0]["message"]["content"],
            provider="deepseek",
            model=result.get("model") or self.deepseek_model,
            usage=usage,
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

        payload = {
            "model": self.deepseek_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        collected_content = ""
        collected_usage: Optional[Dict] = None

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
                        content = delta.get("content", "")
                        if content:
                            collected_content += content
                            yield {"type": "text", "content": content}

                    usage_chunk = chunk.get("usage")
                    if usage_chunk:
                        collected_usage = usage_chunk

        usage = self._build_usage_snapshot(
            provider="deepseek",
            model=self.deepseek_model,
            usage=collected_usage or {},
        )
        yield {"type": "done", "content": collected_content, "usage": usage}

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
        try:
            async for chunk in self._call_deepseek_api_streaming(messages):
                if chunk["type"] == "text":
                    full_response += chunk["content"]
                    yield chunk
                elif chunk["type"] == "done":
                    full_response = chunk.get("content", full_response)
                    usage = chunk.get("usage")
                    break
        except Exception as e:
            logger.warning(f"DeepSeek streaming failed: {e}")
            fallback = self._get_fallback_response(messages)
            yield {"type": "text", "content": fallback}
            yield {"type": "done", "usage": None}
            return

        opencode_command = self._extract_opencode_command(full_response)

        if self._needs_command_repair(full_response, opencode_command):
            repair_messages = self._build_command_repair_messages(messages, full_response)
            yield {"type": "text", "content": "\n\n"}
            try:
                async for chunk in self._call_deepseek_api_streaming(repair_messages):
                    if chunk["type"] == "text":
                        full_response += chunk["content"]
                        yield chunk
                    elif chunk["type"] == "done":
                        full_response = chunk.get("content", full_response)
                        repair_usage = chunk.get("usage")
                        usage = self._merge_usage(usage, repair_usage)
                        break
            except Exception:
                pass

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
            r'\b(feito|conclu[ií]do|arquivo criado|criei o arquivo|terminei|pronto[,!]?\s+criei)\b',
            response_text,
            re.IGNORECASE,
        )

        if not shell_like and not success_claim:
            return response_text

        return (
            "Ainda não executei nenhuma alteração.\n\n"
            "Eu só posso propor ações usando um comando OpenCode válido, que depois precisa "
            "ser confirmado na interface. Peça para eu tentar novamente e eu vou responder "
            "com um único comando executável."
        )

    def _needs_command_repair(
        self,
        response_text: str,
        opencode_command: Optional[str],
    ) -> bool:
        if opencode_command:
            return False
        return self._sanitize_unconfirmed_execution_claims(response_text, None).startswith(
            "Ainda não executei nenhuma alteração."
        )

    def _build_command_repair_messages(
        self,
        messages: List[Dict],
        invalid_response: str,
    ) -> List[Dict]:
        repair_instruction = (
            "Sua resposta anterior usou shell cru ou alegou execução sem confirmação. "
            "Reescreva agora usando exatamente um único comando OpenCode válido, ou nenhum "
            "comando se a tarefa não exigir ação. Não diga que concluiu nada. "
            "Se for criar ou sobrescrever arquivo, use apenas "
            '`write "/caminho/arquivo" --content="conteúdo"`.'
        )
        return [
            *messages,
            {"role": "assistant", "content": invalid_response},
            {"role": "user", "content": repair_instruction},
        ]
    
    def _get_fallback_response(self, messages: List[Dict]) -> str:
        """Resposta degradada quando a API DeepSeek falha."""
        
        fallback_responses = [
            "A API DeepSeek demorou além do limite e eu entrei em modo degradado. "
            "Posso ainda ajudar com comandos OpenCode básicos se você especificar o que precisa.",
            
            "DeepSeek está temporariamente indisponível. "
            "Você pode me pedir para executar comandos específicos como 'bash ls' ou 'read arquivo'.",
            
            "Desculpe, estou tendo dificuldades técnicas. "
            "Enquanto isso, posso ajudar com tarefas que não requerem análise de IA complexa."
        ]
        
        import random
        return random.choice(fallback_responses)
