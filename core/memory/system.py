"""
Persistent storage for DevSynapse — facade composing domain stores.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config.settings import DEFAULT_PREFERENCES, KNOWN_PROJECTS, get_settings
from core.memory.conversations import ConversationStore
from core.memory.learning import AgentLearningStore
from core.memory.projects import ProjectRegistry
from core.memory.settings import SettingsStore
from core.migrations import build_memory_migration_manager

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

    def get_project(self, name: str) -> Optional[Dict[str, Any]]:
        return self.projects.get_project(name)

    def list_projects(self) -> list[Dict[str, Any]]:
        return self.projects.list_projects()

    def list_project_names(self) -> list[str]:
        return self.projects.list_project_names()

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
