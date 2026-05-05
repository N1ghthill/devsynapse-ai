"""
Persistent storage for DevSynapse — facade composing domain stores.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import get_settings
from core.async_utils import run_blocking
from core.db import connect_db, db_session
from core.llm_optimization import ModelRoute
from core.memory.agent_runs import AgentRunStore
from core.memory.conversations import ConversationStore
from core.memory.learning import AgentLearningStore
from core.memory.llm_telemetry import LLMTelemetryStore
from core.memory.nudges import NudgeStore
from core.memory.procedural import ProjectMemoryStore
from core.memory.projects import ProjectRegistry
from core.memory.settings import SettingsStore
from core.migrations import build_memory_migration_manager
from core.skills import SkillStore

logger = logging.getLogger(__name__)
_settings = get_settings()


class MemorySystem:
    """Manages DevSynapse persistent memory."""

    def __init__(self):
        self.db_path = str(get_settings().memory_db_path)
        self._init_database()

        self.projects = ProjectRegistry(self.db_path)
        self.conversations = ConversationStore(self.db_path)
        self.agent_runs = AgentRunStore(self.db_path)
        self.settings = SettingsStore(self.db_path)
        self.learning = AgentLearningStore(self.db_path)
        self.project_memories = ProjectMemoryStore(self.db_path)
        self.skills = SkillStore(
            db_path=self.db_path,
            base_dir=Path(self.db_path).parent / "skills",
            project_lookup_fn=self.projects.get_project_lookup,
        )

        # Wire cross-cutting callbacks that stores use to avoid circular references.
        self.conversations._get_user_preferences_fn = self.settings.get_user_preferences
        self.conversations._get_projects_context_fn = self.projects.get_projects_context
        self.conversations._get_project_lookup_fn = self.projects._get_project_lookup

        self.llm_telemetry = LLMTelemetryStore(self.db_path)
        self.nudges = NudgeStore(
            db_path=self.db_path,
            memory_upserter=self.upsert_project_memory,
            skill_creator=self.create_skill,
            skill_updater=self.update_skill,
        )

    def _init_database(self):
        """Initialize SQLite database with migrations and seed data."""

        build_memory_migration_manager(self.db_path).apply_migrations()

        settings = get_settings()
        default_prefs = settings.build_default_preferences()
        known_projects = settings.build_known_projects()

        with db_session(self.db_path) as conn:
            cursor = conn.cursor()

            for key, value in default_prefs.items():
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO user_preferences
                    (key, value, source, confidence, last_updated, evidence_count)
                    VALUES (?, ?, 'default', 1.0, ?, 1)
                    """,
                    (key, value, datetime.now().isoformat()),
                )

            for name, info in known_projects.items():
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO projects
                    (name, path, type, priority, last_accessed, access_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, info["path"], info["type"], info["priority"],
                     datetime.now().isoformat(), 0),
                )

            conn.commit()

        logger.info("Database initialized: %s", self.db_path)

    def get_db_connection(self) -> sqlite3.Connection:
        """Return a SQLite connection for internal/service use."""
        conn = connect_db(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── project delegation ──────────────────────────────────────────

    def add_project(self, name, path, project_type="project", priority="medium", replace=True):
        return self.projects.add_project(name, path, project_type, priority, replace)

    def get_project(self, name: str, include_missing: bool = False) -> Optional[Dict[str, Any]]:
        return self.projects.get_project(name, include_missing=include_missing)

    def list_projects(self, include_missing: bool = False) -> list[Dict[str, Any]]:
        return self.projects.list_projects(include_missing=include_missing)

    def list_project_names(self) -> list[str]:
        return self.projects.list_project_names()

    def delete_project(self, name: str) -> bool:
        return self.projects.delete_project(name)

    def get_project_lookup(self) -> Dict[str, Dict[str, str]]:
        return self.projects.get_project_lookup()

    def get_projects_context(self) -> str:
        return self.projects.get_projects_context()

    def _update_project_access(self, message: str, project_name: Optional[str] = None):
        return self.projects._update_project_access(message, project_name)

    def get_project_permissions(
        self, username: Optional[str] = None
    ) -> Dict[str, list[str]] | list[str]:
        return self.projects.get_project_permissions(username)

    def replace_project_permissions(
        self, username: str, project_names: list[str], permission: str = "mutate"
    ):
        return self.projects.replace_project_permissions(username, project_names, permission)

    # ── conversation delegation ─────────────────────────────────────

    async def get_conversation_context(self, conversation_id: Optional[str] = None) -> Dict:
        return await self.conversations.get_conversation_context(conversation_id)

    def list_conversations(self, limit: int = 20) -> list[Dict[str, Any]]:
        return self.conversations.list_conversations(limit)

    def get_llm_usage_stats(self, hours: int = 24) -> Dict[str, Any]:
        return self.conversations.get_llm_usage_stats(hours)

    def get_project_usage_breakdown(self, hours: int = 24) -> list[Dict[str, Any]]:
        return self.conversations.get_project_usage_breakdown(hours)

    def get_conversation_project_name(self, conversation_id: Optional[str]) -> Optional[str]:
        return self.conversations.get_conversation_project_name(conversation_id)

    def export_llm_usage_csv(self) -> str:
        return self.conversations.export_llm_usage_csv()

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        return self.conversations.rename_conversation(conversation_id, title)

    def delete_conversation(self, conversation_id: str) -> bool:
        return self.conversations.delete_conversation(conversation_id)

    async def save_interaction(
        self,
        conversation_id: Optional[str],
        user_message: str,
        ai_response: str,
        opencode_command: Optional[str] = None,
        conversation_title: Optional[str] = None,
        llm_usage: Optional[Dict[str, Any]] = None,
        project_name: Optional[str] = None,
    ):
        inferred = await self.conversations.save_interaction(
            conversation_id=conversation_id,
            user_message=user_message,
            ai_response=ai_response,
            opencode_command=opencode_command,
            conversation_title=conversation_title,
            llm_usage=llm_usage,
            project_name=project_name,
        )
        await run_blocking(self._update_project_access, user_message, inferred)
        return inferred

    async def save_command_execution(
        self,
        conversation_id: Optional[str],
        command: str,
        success: bool,
        result: str,
        output: Optional[str] = None,
        status: Optional[str] = None,
        reason_code: Optional[str] = None,
        project_name: Optional[str] = None,
        record_agent_event: bool = True,
    ):
        result_value = await self.conversations.save_command_execution(
            conversation_id=conversation_id,
            command=command,
            success=success,
            result=result,
            output=output,
            status=status,
            reason_code=reason_code,
            project_name=project_name,
        )
        if record_agent_event:
            await run_blocking(
                self.record_agent_command_result,
                conversation_id=conversation_id,
                goal=f"Executar comando confirmado: {command}",
                command=command,
                success=success,
                result=result,
                output=output,
                status=status,
                reason_code=reason_code,
                project_name=project_name,
            )
        await run_blocking(
            self.learning.learn_from_command_outcome,
            conversation_id=conversation_id,
            command=command,
            success=success,
            result=result,
        )
        try:
            row = await run_blocking(self._latest_conversation_for_review, conversation_id)
            if row:
                await run_blocking(
                    self.review_completed_task,
                    conversation_id=conversation_id,
                    user_message=row.get("user_message") or "",
                    ai_response=row.get("ai_response") or "",
                    project_name=project_name or row.get("conversation_project_name"),
                    opencode_command=command,
                    command_success=success,
                    command_result=result,
                    command_output=output,
                    trigger_reason="command_success" if success else "command_failure",
                )
        except Exception:
            logger.debug("Could not run command completion nudge", exc_info=True)
        return result_value

    async def save_feedback(self, conversation_id: str, feedback: str, score: Optional[int] = None):
        result = await self.conversations.save_feedback(conversation_id, feedback, score)
        await run_blocking(self.learning.learn_from_feedback, conversation_id, feedback, score)
        return result

    # ── agent task-run delegation ──────────────────────────────────

    def start_or_resume_agent_run(
        self,
        conversation_id: Optional[str],
        goal: str,
        project_name: Optional[str] = None,
        next_action: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return self.agent_runs.start_or_resume_run(
            conversation_id=conversation_id,
            goal=goal,
            project_name=project_name,
            next_action=next_action,
        )

    def get_active_agent_run(self, conversation_id: Optional[str]) -> Optional[Dict[str, Any]]:
        return self.agent_runs.get_active_run(conversation_id)

    def get_agent_run_context(self, conversation_id: Optional[str], limit: int = 8) -> str:
        return self.agent_runs.get_run_context(conversation_id, limit=limit)

    def record_agent_run_event(
        self,
        run_id: int,
        conversation_id: Optional[str],
        event_type: str,
        title: str,
        status: Optional[str] = None,
        command: Optional[str] = None,
        reason_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.agent_runs.record_event(
            run_id=run_id,
            conversation_id=conversation_id,
            event_type=event_type,
            title=title,
            status=status,
            command=command,
            reason_code=reason_code,
            details=details,
            project_name=project_name,
        )

    def record_agent_command_result(
        self,
        conversation_id: Optional[str],
        goal: str,
        command: str,
        success: bool,
        result: str,
        output: Optional[str] = None,
        status: Optional[str] = None,
        reason_code: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return self.agent_runs.record_command_result(
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

    def record_agent_final_response(
        self,
        run_id: int,
        conversation_id: Optional[str],
        response: str,
        has_pending_command: bool,
        project_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return self.agent_runs.record_final_response(
            run_id=run_id,
            conversation_id=conversation_id,
            response=response,
            has_pending_command=has_pending_command,
            project_name=project_name,
        )

    # ── agent learning delegation ───────────────────────────────────

    def get_agent_learning(self, task_signature: str) -> Optional[Dict[str, Any]]:
        return self.learning.get_learning_for_signature(task_signature)

    def get_agent_learning_context(self, limit: int = 6) -> str:
        return self.learning.get_learning_context(limit=limit)

    def get_agent_learning_stats(self) -> Dict[str, Any]:
        return self.learning.get_learning_stats()

    # ── LLM model catalog and telemetry ─────────────────────────────

    def upsert_llm_models(self, models: list[Dict[str, Any]]) -> int:
        return self.llm_telemetry.upsert_models(models)

    def list_llm_models(
        self,
        provider: Optional[str] = None,
        enabled_only: bool = True,
        limit: int = 200,
    ) -> list[Dict[str, Any]]:
        return self.llm_telemetry.list_models(provider, enabled_only, limit)

    def get_llm_model(self, provider: str, model_id: str) -> Optional[Dict[str, Any]]:
        return self.llm_telemetry.get_model(provider, model_id)

    def record_llm_request_telemetry(
        self,
        user_id: Optional[str],
        conversation_id: Optional[str],
        provider: Optional[str],
        model: Optional[str],
        route: Optional[ModelRoute],
        success: bool,
        usage: Optional[Dict[str, Any]] = None,
        first_token_latency_ms: Optional[float] = None,
        total_latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        self.llm_telemetry.record_telemetry(
            user_id, conversation_id, provider, model, route,
            success, usage, first_token_latency_ms, total_latency_ms, error_message,
        )

    def get_llm_telemetry_stats(self, hours: int = 24) -> Dict[str, Any]:
        return self.llm_telemetry.get_telemetry_stats(hours)

    # ── procedural memory and skills ────────────────────────────────

    def upsert_project_memory(
        self,
        content: str,
        project_name: Optional[str] = None,
        memory_type: str = "fact",
        source: str = "manual",
        confidence_score: float = 0.6,
        memory_decay_score: float = 0.02,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.project_memories.upsert_memory(
            content=content,
            project_name=project_name,
            memory_type=memory_type,
            source=source,
            confidence_score=confidence_score,
            memory_decay_score=memory_decay_score,
            tags=tags,
            metadata=metadata,
        )

    def list_project_memories(
        self,
        project_name: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 20,
    ) -> list[Dict[str, Any]]:
        return self.project_memories.list_memories(
            project_name=project_name,
            query=query,
            include_global=True,
            limit=limit,
        )

    def get_project_memory(self, memory_id: int) -> Optional[Dict[str, Any]]:
        return self.project_memories.get_memory(memory_id)

    def adjust_project_memory_confidence(
        self,
        memory_id: int,
        delta: float,
        source: str = "feedback",
    ) -> Optional[Dict[str, Any]]:
        return self.project_memories.adjust_confidence(memory_id, delta, source)

    def get_project_memory_context(
        self,
        project_name: Optional[str],
        query: str,
        limit: int = 6,
    ) -> str:
        return self.project_memories.format_context(project_name, query, limit=limit)

    def create_skill(
        self,
        name: str,
        description: str,
        body: str,
        category: str = "general",
        project_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        replace: bool = False,
        source: str = "manual",
    ) -> Dict[str, Any]:
        return self.skills.create_skill(
            name=name,
            description=description,
            body=body,
            category=category,
            project_name=project_name,
            tags=tags,
            replace=replace,
            source=source,
        )

    def update_skill(
        self,
        name: str,
        body: Optional[str] = None,
        description: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return self.skills.update_skill(
            name,
            body=body,
            description=description,
            project_name=project_name,
        )

    def delete_skill(self, name: str, project_name: Optional[str] = None) -> bool:
        return self.skills.delete_skill(name, project_name=project_name)

    def list_skills(
        self,
        project_name: Optional[str] = None,
        include_global: bool = True,
    ) -> list[Dict[str, Any]]:
        return self.skills.list_skills(
            project_name=project_name,
            include_global=include_global,
        )

    def get_skill(self, name: str, project_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self.skills.get_skill(name, project_name=project_name)

    def activate_skill(
        self,
        name: str,
        project_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
        reason: str = "manual",
    ) -> Optional[Dict[str, Any]]:
        return self.skills.activate_skill(
            name,
            project_name=project_name,
            conversation_id=conversation_id,
            reason=reason,
        )

    def get_skills_context(
        self,
        query: str,
        project_name: Optional[str] = None,
        limit: int = 3,
    ) -> str:
        return self.skills.format_context(query, project_name=project_name, limit=limit)

    def get_knowledge_stats(self) -> Dict[str, Any]:
        return {
            "memories": self.project_memories.get_stats(),
            "skills": self.skills.get_stats(),
            "nudges": self.get_learning_nudge_stats(),
        }

    def get_learning_nudge_stats(self) -> Dict[str, Any]:
        return self.nudges.get_stats()

    def review_completed_task(
        self,
        conversation_id: Optional[str],
        user_message: str,
        ai_response: str,
        project_name: Optional[str] = None,
        opencode_command: Optional[str] = None,
        command_success: Optional[bool] = None,
        command_result: Optional[str] = None,
        command_output: Optional[str] = None,
        route: Optional[ModelRoute] = None,
        tool_iterations: int = 0,
        trigger_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.nudges.review_completed_task(
            conversation_id, user_message, ai_response, project_name,
            opencode_command, command_success, command_result, command_output,
            route, tool_iterations, trigger_reason,
        )

    def _latest_conversation_for_review(
        self,
        conversation_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not conversation_id:
            return None
        with db_session(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT conversation_id, user_message, ai_response, conversation_project_name
                FROM conversations
                WHERE conversation_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def record_agent_route_decision(
        self,
        conversation_id: Optional[str],
        route,
        usage: Optional[Dict[str, Any]] = None,
        project_name: Optional[str] = None,
        opencode_command: Optional[str] = None,
    ) -> None:
        self.learning.record_route_decision(
            conversation_id=conversation_id,
            route=route,
            usage=usage,
            project_name=project_name,
            opencode_command=opencode_command,
        )

    # ── settings delegation ─────────────────────────────────────────

    def get_user_preferences(self) -> str:
        return self.settings.get_user_preferences()

    def update_preference(self, key: str, value: str, source: str = "learned"):
        return self.settings.update_preference(key, value, source)

    def get_app_settings(self) -> Dict[str, Any]:
        return self.settings.get_app_settings()

    def update_app_settings(self, settings_data: Dict[str, Any]):
        return self.settings.update_app_settings(settings_data)

    # ── cross-cutting ───────────────────────────────────────────────

    def get_llm_budget_status(self) -> Dict[str, Any]:
        persisted = self.get_app_settings()
        daily_budget_usd = float(
            persisted.get("llm_daily_budget_usd", _settings.llm_daily_budget_usd)
        )
        monthly_budget_usd = float(
            persisted.get("llm_monthly_budget_usd", _settings.llm_monthly_budget_usd)
        )
        warning_threshold_pct = float(
            persisted.get(
                "llm_budget_warning_threshold_pct",
                _settings.llm_budget_warning_threshold_pct,
            )
        )
        critical_threshold_pct = float(
            persisted.get(
                "llm_budget_critical_threshold_pct",
                _settings.llm_budget_critical_threshold_pct,
            )
        )

        now = datetime.now()
        last_24h_start = (now - timedelta(hours=24)).isoformat()
        month_start = datetime(now.year, now.month, 1).isoformat()

        daily_usage = self.conversations._aggregate_llm_usage_between(last_24h_start)
        monthly_usage = self.conversations._aggregate_llm_usage_between(month_start)

        def build_status(
            window: str, actual_cost_usd: float, budget_usd: float
        ) -> Dict[str, Any]:
            warning_cost = (
                budget_usd * (warning_threshold_pct / 100) if budget_usd > 0 else 0.0
            )
            critical_cost = (
                budget_usd * (critical_threshold_pct / 100) if budget_usd > 0 else 0.0
            )
            usage_pct = (actual_cost_usd / budget_usd * 100) if budget_usd > 0 else 0.0

            if budget_usd <= 0:
                level = "disabled"
            elif actual_cost_usd >= critical_cost:
                level = "critical"
            elif actual_cost_usd >= warning_cost:
                level = "warning"
            else:
                level = "healthy"

            return {
                "window": window,
                "budget_usd": budget_usd,
                "actual_cost_usd": actual_cost_usd,
                "usage_pct": usage_pct,
                "warning_threshold_pct": warning_threshold_pct,
                "critical_threshold_pct": critical_threshold_pct,
                "warning_threshold_cost_usd": warning_cost,
                "critical_threshold_cost_usd": critical_cost,
                "level": level,
            }

        daily_status = build_status(
            "daily", daily_usage["estimated_cost_usd"], daily_budget_usd
        )
        monthly_status = build_status(
            "monthly",
            monthly_usage["estimated_cost_usd"],
            monthly_budget_usd,
        )

        overall_status = "disabled"
        if any(item["level"] == "critical" for item in (daily_status, monthly_status)):
            overall_status = "critical"
        elif any(item["level"] == "warning" for item in (daily_status, monthly_status)):
            overall_status = "warning"
        elif any(item["level"] == "healthy" for item in (daily_status, monthly_status)):
            overall_status = "healthy"

        return {
            "overall_status": overall_status,
            "daily": daily_status,
            "monthly": monthly_status,
        }
