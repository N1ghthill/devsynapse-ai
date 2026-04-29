"""
Persistent storage for DevSynapse — facade composing domain stores.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import DEFAULT_PREFERENCES, KNOWN_PROJECTS, get_settings
from core.llm_optimization import ModelRoute, build_task_profile
from core.memory.conversations import ConversationStore
from core.memory.learning import AgentLearningStore
from core.memory.procedural import ProjectMemoryStore
from core.memory.projects import ProjectRegistry
from core.memory.settings import SettingsStore
from core.migrations import build_memory_migration_manager
from core.skills import SkillError, SkillStore

logger = logging.getLogger(__name__)
_settings = get_settings()


class MemorySystem:
    """Gerencia memória persistente do DevSynapse."""

    def __init__(self):
        from core.memory import MEMORY_DB_PATH

        self.db_path = MEMORY_DB_PATH
        self._init_database()

        self.projects = ProjectRegistry(self.db_path)
        self.conversations = ConversationStore(self.db_path)
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

    def _init_database(self):
        """Inicializa banco de dados SQLite"""

        build_memory_migration_manager(self.db_path).apply_migrations()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Inserir preferências padrão
        for key, value in DEFAULT_PREFERENCES.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_preferences
                (key, value, source, confidence, last_updated, evidence_count)
                VALUES (?, ?, 'default', 1.0, ?, 1)
                """,
                (key, value, datetime.now().isoformat()),
            )

        # Inserir projetos conhecidos
        for name, info in KNOWN_PROJECTS.items():
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
        conn.close()

        logger.info(f"Banco de dados inicializado: {self.db_path}")

    def get_db_connection(self) -> sqlite3.Connection:
        """Return a SQLite connection for internal/service use."""
        conn = sqlite3.connect(self.db_path)
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
        self._update_project_access(user_message, inferred)
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
        self.learning.learn_from_command_outcome(
            conversation_id=conversation_id,
            command=command,
            success=success,
            result=result,
        )
        try:
            row = self._latest_conversation_for_review(conversation_id)
            if row:
                self.review_completed_task(
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
        self.learning.learn_from_feedback(conversation_id, feedback, score)
        return result

    # ── agent learning delegation ───────────────────────────────────

    def get_agent_learning(self, task_signature: str) -> Optional[Dict[str, Any]]:
        return self.learning.get_learning_for_signature(task_signature)

    def get_agent_learning_context(self, limit: int = 6) -> str:
        return self.learning.get_learning_context(limit=limit)

    def get_agent_learning_stats(self) -> Dict[str, Any]:
        return self.learning.get_learning_stats()

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
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS total_events
            FROM learning_nudge_events
            """
        )
        totals = dict(cursor.fetchone())
        cursor.execute(
            """
            SELECT nudge_type, status, COUNT(*) AS count
            FROM learning_nudge_events
            GROUP BY nudge_type, status
            ORDER BY count DESC
            """
        )
        by_status = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {
            "total_events": int(totals.get("total_events") or 0),
            "by_status": by_status,
        }

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
        """Review a finished task and persist reusable learning when warranted."""

        reason = trigger_reason or self._learning_trigger_reason(
            route=route,
            opencode_command=opencode_command,
            command_success=command_success,
            tool_iterations=tool_iterations,
        )
        if reason == "not_complex":
            self._record_nudge_event(
                conversation_id,
                project_name,
                "review",
                reason,
                "skipped",
                {"message_preview": user_message[:160]},
            )
            return {"status": "skipped", "reason": reason}

        created_memories: list[Dict[str, Any]] = []
        created_skills: list[Dict[str, Any]] = []
        task_profile = build_task_profile(user_message)

        if command_success is True and opencode_command:
            memory = self.upsert_project_memory(
                content=self._command_procedure_memory(
                    user_message,
                    opencode_command,
                    command_result,
                    command_output,
                ),
                project_name=project_name,
                memory_type="procedure",
                source="nudge:command_success",
                confidence_score=0.72,
                memory_decay_score=0.01,
                tags=[task_profile.task_type, "command"],
                metadata={
                    "conversation_id": conversation_id,
                    "command": opencode_command,
                    "trigger": reason,
                },
            )
            created_memories.append(memory)
            skill = self._create_or_update_skill_from_command(
                task_profile.task_type,
                user_message,
                opencode_command,
                command_result,
                command_output,
                None,
            )
            if skill:
                created_skills.append(skill)
        elif (route and route.complexity == "complex") or tool_iterations >= 2:
            memory = self.upsert_project_memory(
                content=self._response_insight_memory(user_message, ai_response),
                project_name=project_name,
                memory_type="insight",
                source="nudge:complex_task",
                confidence_score=0.5,
                memory_decay_score=0.04,
                tags=[task_profile.task_type],
                metadata={"conversation_id": conversation_id, "trigger": reason},
            )
            created_memories.append(memory)

        status = "recorded" if created_memories or created_skills else "reviewed"
        details = {
            "reason": reason,
            "memories": [item.get("id") for item in created_memories],
            "skills": [item.get("slug") for item in created_skills],
        }
        self._record_nudge_event(
            conversation_id,
            project_name,
            "learning",
            reason,
            status,
            details,
        )
        return {"status": status, **details}

    def _learning_trigger_reason(
        self,
        route: Optional[ModelRoute],
        opencode_command: Optional[str],
        command_success: Optional[bool],
        tool_iterations: int,
    ) -> str:
        if command_success is True:
            return "command_success"
        if command_success is False:
            return "command_failure"
        if route and route.complexity == "complex":
            return "complex_task"
        if tool_iterations >= 2:
            return "multi_tool_task"
        if opencode_command:
            return "command_proposed"
        return "not_complex"

    def _record_nudge_event(
        self,
        conversation_id: Optional[str],
        project_name: Optional[str],
        nudge_type: str,
        trigger_reason: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO learning_nudge_events (
                conversation_id, project_name, nudge_type, trigger_reason,
                status, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                project_name,
                nudge_type,
                trigger_reason,
                status,
                json.dumps(details or {}, ensure_ascii=False),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def _latest_conversation_for_review(
        self,
        conversation_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not conversation_id:
            return None

        conn = self.get_db_connection()
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
        conn.close()
        return dict(row) if row else None

    def _command_procedure_memory(
        self,
        user_message: str,
        command: str,
        result: Optional[str],
        output: Optional[str],
    ) -> str:
        task = self._shorten(user_message, 220)
        outcome = self._shorten(output or result or "command succeeded", 320)
        return (
            f"For a task like '{task}', command `{command}` succeeded. "
            f"Useful outcome: {outcome}"
        )

    def _response_insight_memory(self, user_message: str, ai_response: str) -> str:
        task = self._shorten(user_message, 220)
        approach = self._shorten(ai_response, 420)
        return f"For a complex task like '{task}', previous useful approach: {approach}"

    def _create_or_update_skill_from_command(
        self,
        task_type: str,
        user_message: str,
        command: str,
        result: Optional[str],
        output: Optional[str],
        project_name: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if task_type in {"concept", "general"} and not self._command_is_repeatable(command):
            return None

        first_command = self._first_command_word(command)
        skill_name = f"{task_type} {first_command} workflow"
        description = (
            f"Repeatable workflow for {task_type} tasks using `{first_command}` "
            "from a successful DevSynapse run."
        )
        body = self._skill_body_from_command(user_message, command, result, output)
        tags = [task_type, first_command, "nudge"]

        try:
            return self.create_skill(
                name=skill_name,
                description=description,
                body=body,
                category=task_type,
                project_name=project_name,
                tags=tags,
                replace=False,
                source="nudge",
            )
        except SkillError:
            return self.update_skill(
                skill_name,
                body=body,
                description=description,
                project_name=project_name,
            )

    def _skill_body_from_command(
        self,
        user_message: str,
        command: str,
        result: Optional[str],
        output: Optional[str],
    ) -> str:
        return "\n".join(
            [
                "## When to Use",
                self._shorten(user_message, 500),
                "",
                "## Steps",
                "1. Confirm the selected project context is correct.",
                f"2. Run or adapt this command through the command tool: `{command}`.",
                "3. Inspect output before proposing edits or follow-up commands.",
                "",
                "## Last Known Outcome",
                self._shorten(output or result or "The command completed successfully.", 900),
                "",
                "## Verification",
                "- Prefer read-only inspection first when the task can be diagnosed safely.",
                "- Keep project-scoped mutation rules in place for any follow-up edits.",
            ]
        )

    @staticmethod
    def _command_is_repeatable(command: str) -> bool:
        lowered = command.lower()
        repeatable_markers = (
            "pytest",
            "test",
            "lint",
            "migrate",
            "build",
            "grep",
            "git ",
            "read ",
        )
        return any(marker in lowered for marker in repeatable_markers)

    @staticmethod
    def _first_command_word(command: str) -> str:
        match = re.search(r'"([^"]+)"', command)
        command_text = match.group(1) if match else command
        parts = command_text.strip().split()
        raw = parts[0] if parts else "command"
        return re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-") or "command"

    @staticmethod
    def _shorten(value: Optional[str], limit: int) -> str:
        normalized = " ".join((value or "").split()).strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."

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

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        return self.settings.get_user(username)

    def upsert_user(
        self, username: str, password_hash: str, role: str = "user", is_active: bool = True
    ):
        return self.settings.upsert_user(username, password_hash, role, is_active)

    def touch_user_login(self, username: str):
        return self.settings.touch_user_login(username)

    def get_app_settings(self) -> Dict[str, Any]:
        return self.settings.get_app_settings()

    def update_app_settings(self, settings_data: Dict[str, Any]):
        return self.settings.update_app_settings(settings_data)

    def log_admin_action(
        self,
        actor_username: str,
        action: str,
        target_username: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        return self.settings.log_admin_action(actor_username, action, target_username, details)

    def get_admin_audit_logs(self, limit: int = 50) -> list[Dict[str, Any]]:
        return self.settings.get_admin_audit_logs(limit)

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
