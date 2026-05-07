"""Core of DevSynapse - provider orchestration and agent loop."""

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

import config.settings as app_settings
from core.autoexec_policy import (
    can_autoexecute_command,
    max_autoexec_rounds,
    response_promises_pending_action,
    should_replay_command_result,
    should_retry_missing_tool,
    user_request_expects_tool,
)
from core.command_extraction import extract_opencode_command, tool_calls_to_opencode_command
from core.command_messages import (
    build_command_result_replay_messages,
    command_completion_fallback,
    command_failure_message,
)
from core.correlation import generate_tool_run_id
from core.deepseek import DeepSeekClient
from core.intent_detector import IntentDetector
from core.llm_executor import LLMExecutor
from core.llm_optimization import ModelRoute
from core.memory.protocol import BrainMemoryAdapter, BrainMemoryProtocol
from core.plugin_system import PluginManager, plugin_manager
from core.project_path_resolver import ProjectPathResolver
from core.prompts import build_system_prompt
from core.routing import RouteSelector
from core.tool_repair import coerce_llm_result, sanitize_unconfirmed_execution_claims
from core.tool_validation import validate_tool_calls
from core.usage_tracker import UsageTracker

if TYPE_CHECKING:
    from core.opencode_bridge import OpenCodeBridge

logger = logging.getLogger(__name__)


class DevSynapseBrain:
    """Manages DevSynapse intelligence through the configured LLM providers."""

    def __init__(
        self,
        memory_system: BrainMemoryProtocol,
        opencode_bridge: "OpenCodeBridge",
        plugin_manager_instance: Optional[PluginManager] = None,
    ) -> None:
        self.memory = memory_system
        self.memory_optional = BrainMemoryAdapter(memory_system)
        self.opencode = opencode_bridge
        self.plugin_manager = plugin_manager_instance or plugin_manager
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
            api_key=settings.deepseek_api_key,
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
                    "api_key": settings.openrouter_api_key,
                    "base_url": settings.openrouter_base_url,
                },
                "opencode-zen": {
                    "api_key": settings.opencode_zen_api_key,
                    "base_url": settings.opencode_zen_base_url,
                },
                "opencode-go": {
                    "api_key": settings.opencode_go_api_key,
                    "base_url": settings.opencode_go_base_url,
                },
            },
        )

        self.router = RouteSelector(
            memory=self.memory,
            deepseek_model=self.deepseek.model,
            provider_configs=self.deepseek.provider_configs,
            deepseek_api_key=self.deepseek.api_key,
            default_provider=settings.llm_default_provider,
            provider_model_defaults={
                "deepseek": settings.deepseek_model,
                "openrouter": settings.openrouter_model,
                "opencode-zen": settings.opencode_zen_model,
                "opencode-go": settings.opencode_go_model,
            },
        )

        self.usage = UsageTracker(
            memory=self.memory_optional,
            model_pricing_lookup=self.memory_optional.get_llm_model,
        )

        self.executor = LLMExecutor(
            deepseek_client=self.deepseek,
            usage_tracker=self.usage,
            get_settings=app_settings.get_settings,
        )

        # Path resolver for exact project location
        self.path_resolver = ProjectPathResolver(
            repos_root=settings.dev_repos_root,
            workspace_root=settings.dev_workspace_root,
            allowed_directories=[settings.dev_repos_root, settings.dev_workspace_root],
        )

        # Intent detector for 3-spectra system (Chat, Planning, Build)
        self.intent_detector = IntentDetector()

        if not self.deepseek.configured:
            logger.warning("No LLM provider key configured")

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
        if active_project_name:
            active_project = self.memory_optional.get_project(active_project_name)
            active_project_path = active_project.get("path") if active_project else None

        # Extract target path from user message for exact path resolution
        target_path_info = self._extract_target_path_from_message(current_request)

        return build_system_prompt(
            assistant_user_name=settings.assistant_user_name,
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
            agent_mode=str(context.get("agent_mode") or "build"),
            target_path=target_path_info,
        )

    def _extract_target_path_from_message(self, message: str) -> Optional[Dict]:
        """Extract target path from user message.

        Returns dict with:
        - path: absolute path
        - display_path: shortened path for display
        - project_name: extracted project name
        """
        if not message:
            return None

        resolution = self.path_resolver.resolve_from_message(message)
        if resolution.is_valid:
            return {
                "path": str(resolution.absolute_path),
                "display_path": resolution.display_path,
                "project_name": resolution.project_name,
            }

        return None

    async def process_message(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        project_name: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        project_mutation_allowlist: Optional[List[str]] = None,
        auto_execute: bool = False,
        agent_mode: str = "build",
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, Optional[str], Optional[Dict]]:
        """Process a user message and return response + OpenCode command.

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

        bp_event = await self.plugin_manager.emit_event("brain:before_process", event_data)
        if bp_event.cancelled:
            return "Processamento cancelado por plugin.", None, None
        user_message = bp_event.data.get("user_message", user_message)
        conversation_id = bp_event.data.get("conversation_id", conversation_id)
        project_name = bp_event.data.get("project_name", project_name)

        # Get conversation context
        context = await self.memory.get_conversation_context(conversation_id)
        context["agent_mode"] = self._normalize_agent_mode(agent_mode)

        # Detect user intent for 3-spectra system
        intent = self.intent_detector.detect(
            user_message,
            conversation_history=context.get("conversation_history", []),
        )
        context["intent_mode"] = intent.mode.value
        context["intent_confidence"] = intent.confidence
        logger.info(
            "Intent detected: mode=%s confidence=%.2f reasoning=%s",
            intent.mode.value,
            intent.confidence,
            intent.reasoning,
        )

        inferred_project_name = self._infer_and_register_project_from_text(user_message)
        effective_project_name = inferred_project_name or project_name or context.get("project_name")
        if not effective_project_name:
            effective_project_name = None
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
        await self.plugin_manager.emit_event("memory:before_save", mem_before)

        # Prepare messages for DeepSeek
        messages = self._prepare_messages(user_message, context)

        llm_event = await self.plugin_manager.emit_event("brain:before_llm_call", {"messages": messages})
        if not llm_event.cancelled:
            messages = llm_event.data.get("messages", messages)

        route = self._select_llm_route(user_message, context)

        # Check budget before making LLM call
        budget_status = self.memory.get_llm_budget_status()
        daily_level = budget_status.get("daily", {}).get("level", "healthy")
        monthly_level = budget_status.get("monthly", {}).get("level", "healthy")

        if daily_level == "critical" or monthly_level == "critical":
            budget_msg = (
                f"⚠️ Budget exceeded! "
                f"Daily: {budget_status['daily']['usage_pct']:.0f}% of ${budget_status['daily']['budget_usd']:.2f}, "
                f"Monthly: {budget_status['monthly']['usage_pct']:.0f}% of ${budget_status['monthly']['budget_usd']:.2f}. "
                f"LLM calls are blocked until budget is reset or increased. "
                f"Use /budget to adjust."
            )
            return budget_msg, None, None

        # Run LLM call with auto-execution loop
        response_text, opencode_command, aggregated_usage, autoexecuted_command = (
            await self._run_autoexec_loop(
                messages=messages,
                route=route,
                user_message=user_message,
                context=context,
                user_id=user_id,
                user_role=user_role,
                conversation_id=conversation_id,
                effective_project_name=effective_project_name,
                project_mutation_allowlist=project_mutation_allowlist or [],
                auto_execute=auto_execute,
                agent_mode=context["agent_mode"],
                on_token=on_token,
            )
        )

        await self.plugin_manager.emit_event("brain:after_llm_call", {"response": response_text})

        if not (autoexecuted_command is not None and autoexecuted_command["success"]):
            response_text = sanitize_unconfirmed_execution_claims(
                response_text,
                opencode_command,
            )
        if autoexecuted_command is not None and (
            not response_text.strip() or response_promises_pending_action(response_text)
        ):
            response_text = command_completion_fallback(autoexecuted_command)

        persisted_command = opencode_command
        if persisted_command is None and autoexecuted_command is not None:
            persisted_command = autoexecuted_command["command"]

        # Save to memory
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

        self.usage.record_route_decision(
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
            tool_iterations=max(0, self._count_tool_iterations(autoexecuted_command, opencode_command)),
        )
        self._record_agent_final_response(
            agent_run,
            conversation_id,
            response_text,
            has_pending_command=opencode_command is not None,
            project_name=effective_project_name,
        )

        await self.plugin_manager.emit_event("memory:after_save", {
            "conversation_id": conversation_id,
            "user_message": user_message,
            "response": response_text,
            "project_name": effective_project_name,
        })

        ap_event = await self.plugin_manager.emit_event("brain:after_process", {
            "response": response_text,
            "opencode_command": opencode_command,
        })
        if not ap_event.cancelled:
            response_text = ap_event.data.get("response", response_text)
            opencode_command = ap_event.data.get("opencode_command", opencode_command)

        return response_text, opencode_command, aggregated_usage

    async def _run_autoexec_loop(
        self,
        messages: List[Dict],
        route: ModelRoute,
        user_message: str,
        context: Dict,
        user_id: Optional[str],
        user_role: Optional[str],
        conversation_id: Optional[str],
        effective_project_name: Optional[str],
        project_mutation_allowlist: List[str],
        auto_execute: bool,
        agent_mode: str,
        on_token: Optional[Callable[[str], None]],
    ) -> Tuple[str, Optional[str], Optional[Dict], Optional[Dict]]:
        """Run LLM call with auto-execution loop for read-only commands.

        Respects 3-spectra intent mode:
        - CHAT: Skip tool calls, conversational only
        - PLANNING: Read-only commands only, no mutations
        - BUILD: Full auto-execution (default behavior)
        """
        intent_mode = context.get("intent_mode", "build")
        execution_role = "user" if self._normalize_agent_mode(agent_mode) == "plan" else user_role

        # CHAT mode: skip tool calls entirely, conversational only
        if intent_mode == "chat":
            llm_result = coerce_llm_result(
                await self.executor.call_api(
                    messages,
                    route=route,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    on_token=on_token,
                )
            )
            response_text = llm_result.content
            aggregated_usage = self.usage.merge_usage(None, llm_result.usage)
            return response_text, None, aggregated_usage, None

        # PLANNING mode: read-only commands only, no mutations
        if intent_mode == "planning":
            execution_role = "user"  # Force read-only
            max_rounds = min(max_autoexec_rounds(auto_execute, execution_role), 5)
        else:
            max_rounds = max_autoexec_rounds(auto_execute, execution_role)

        round_count = 0
        aggregated_usage = None
        opencode_command = None
        response_text = ""
        autoexecuted_command = None

        while round_count < max_rounds:
            round_count += 1
            llm_result = coerce_llm_result(
                await self.executor.call_api(
                    messages,
                    route=route,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    on_token=on_token,
                )
            )
            response_text = llm_result.content
            opencode_command = tool_calls_to_opencode_command(llm_result.tool_calls)
            if opencode_command is None:
                opencode_command = extract_opencode_command(response_text)
            aggregated_usage = self.usage.merge_usage(aggregated_usage, llm_result.usage)

            is_valid, validation_reason = validate_tool_calls(llm_result.tool_calls)
            if not is_valid and opencode_command:
                logger.warning("Invalid tool call schema: %s", validation_reason)
                opencode_command = None

            if should_retry_missing_tool(
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
                and can_autoexecute_command(opencode_command, execution_role)
            ):
                break

            tool_run_id = generate_tool_run_id()
            cmd_result = await self.opencode.execute_command(
                opencode_command,
                user_id=user_id,
                project_name=effective_project_name,
                user_role=execution_role,
                project_mutation_allowlist=project_mutation_allowlist,
                conversation_id=conversation_id,
                tool_run_id=tool_run_id,
            )
            success, msg, output, status, reason, proj = (
                cmd_result.success,
                cmd_result.message,
                cmd_result.output,
                cmd_result.status,
                cmd_result.reason_code,
                cmd_result.project_name,
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
                if should_replay_command_result(
                    auto_execute,
                    user_role,
                    status,
                    reason,
                    msg,
                    output,
                ):
                    messages.extend(
                        build_command_result_replay_messages(
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
                    f"{command_failure_message(opencode_command, msg, reason, proj)}"
                )
                opencode_command = None
                break

            messages.extend(
                build_command_result_replay_messages(
                    response_text,
                    opencode_command,
                    success,
                    msg,
                    output,
                )
            )

        return response_text, opencode_command, aggregated_usage, autoexecuted_command

    @staticmethod
    def _count_tool_iterations(
        autoexecuted_command: Optional[Dict],
        opencode_command: Optional[str],
    ) -> int:
        return 1 if autoexecuted_command is not None or opencode_command is not None else 0
    
    def _prepare_messages(self, user_message: str, context: Dict) -> List[Dict]:
        """Prepare messages in API format."""
        context = {**context, "current_user_message": user_message}
        system_prompt = self.generate_system_prompt(context)

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add conversation history if exists
        # Use configured limit instead of hardcoded value
        settings = app_settings.get_settings()
        history_limit = settings.conversation_history_limit
        if context.get("conversation_history"):
            for msg in context["conversation_history"][-history_limit:]:
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
        return self.memory_optional.get_project_memory_context(project_name, user_message)

    def _get_skills_context(
        self,
        user_message: str,
        project_name: Optional[str],
    ) -> str:
        return self.memory_optional.get_skills_context(user_message, project_name=project_name)

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
        active_run = self.memory_optional.get_active_agent_run(conversation_id)

        should_track = active_run is not None or user_request_expects_tool(user_message)
        if should_track:
            active_run = self.memory_optional.start_or_resume_agent_run(
                conversation_id=conversation_id,
                goal=user_message,
                project_name=project_name,
            )

        context["agent_run_context"] = self.memory_optional.get_agent_run_context(conversation_id)

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
        self.memory_optional.record_agent_command_result(
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

    def _record_agent_final_response(
        self,
        agent_run: Optional[Dict],
        conversation_id: Optional[str],
        response_text: str,
        has_pending_command: bool,
        project_name: Optional[str],
    ) -> None:
        if not agent_run:
            return
        self.memory_optional.record_agent_final_response(
            run_id=agent_run["id"],
            conversation_id=conversation_id,
            response=response_text,
            has_pending_command=has_pending_command,
            project_name=project_name,
        )

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
        self.memory_optional.review_completed_task(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=ai_response,
            project_name=project_name,
            opencode_command=opencode_command,
            route=route,
            tool_iterations=tool_iterations,
        )

    def _persist_repos_project_if_needed(self, project_name: Optional[str]) -> None:
        if not project_name:
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
            if self.memory_optional.get_project(project_name):
                return
            self.memory_optional.add_project(
                project_name,
                str(project_root),
                project_type="project",
                priority="medium",
                replace=False,
            )
        except (OSError, ValueError):
            logger.debug("Could not persist generated project %s", project_name, exc_info=True)

    def _infer_and_register_project_from_text(self, text: str) -> Optional[str]:
        """Infer a repos project from user text before the LLM plans filesystem work.

        Uses ProjectPathResolver to extract exact path from user message.
        Example: "Crie calculadora em ~/ruas/repositorios/calc_py"
        -> Resolves to exact path and registers project
        """
        # Try new path resolver first (extracts exact path from message)
        resolution = self.path_resolver.resolve_from_message(text)
        if resolution.is_valid and resolution.project_name:
            # Register the project with exact path
            self.opencode.register_project(
                name=resolution.project_name,
                path=str(resolution.absolute_path),
                project_type="project",
                priority="medium",
            )
            # Also call old method for backward compatibility
            register = getattr(self.opencode, "_register_repos_project_if_needed", None)
            if callable(register):
                register(resolution.project_name)
            self._persist_repos_project_if_needed(resolution.project_name)
            logger.info(
                "Project resolved from text: %s -> %s",
                resolution.project_name,
                resolution.absolute_path,
            )
            return resolution.project_name

        # Fallback to old resolver
        resolver = getattr(self.opencode, "_resolve_project_from_text", None)
        if not callable(resolver):
            return None

        project_name = resolver(text)
        if not isinstance(project_name, str) or not project_name.strip():
            return None

        register = getattr(self.opencode, "_register_repos_project_if_needed", None)
        if callable(register):
            register(project_name)
        self._persist_repos_project_if_needed(project_name)
        return project_name

    @staticmethod
    def _normalize_agent_mode(agent_mode: str) -> str:
        return "plan" if str(agent_mode).strip().lower() == "plan" else "build"

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
