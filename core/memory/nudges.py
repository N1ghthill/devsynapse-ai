"""
Learning nudge events and task review system.

Extracted from MemorySystem to keep the facade thin.
"""
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

from core.db import connect_db
from core.llm_optimization import ModelRoute, build_task_profile


class NudgeStore:
    """Manage learning nudge events and task review outcomes."""

    def __init__(
        self,
        db_path: str,
        memory_upserter,
        skill_creator,
        skill_updater,
    ) -> None:
        self.db_path = db_path
        self._memory_upserter = memory_upserter
        self._skill_creator = skill_creator
        self._skill_updater = skill_updater

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated nudge event stats."""
        conn = connect_db(self.db_path)
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

    def record_event(
        self,
        conversation_id: Optional[str],
        project_name: Optional[str],
        nudge_type: str,
        trigger_reason: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a learning nudge event."""
        conn = connect_db(self.db_path)
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
            self.record_event(
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
            memory = self._memory_upserter(
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
                project_name,
            )
            if skill:
                created_skills.append(skill)
        elif (route and route.complexity == "complex") or tool_iterations >= 2:
            memory = self._memory_upserter(
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
        self.record_event(
            conversation_id,
            project_name,
            "learning",
            reason,
            status,
            details,
        )
        return {"status": status, **details}

    @staticmethod
    def _learning_trigger_reason(
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

    @staticmethod
    def _command_procedure_memory(
        user_message: str,
        command: str,
        result: Optional[str],
        output: Optional[str],
    ) -> str:
        task = _shorten(user_message, 220)
        outcome = _shorten(output or result or "command succeeded", 320)
        return (
            f"For a task like '{task}', command `{command}` succeeded. "
            f"Useful outcome: {outcome}"
        )

    @staticmethod
    def _response_insight_memory(user_message: str, ai_response: str) -> str:
        task = _shorten(user_message, 220)
        approach = _shorten(ai_response, 420)
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
        if task_type in {"concept", "general"} and not _command_is_repeatable(command):
            return None

        first_command = _first_command_word(command)
        skill_name = f"{task_type} {first_command} workflow"
        description = (
            f"Repeatable workflow for {task_type} tasks using `{first_command}` "
            "from a successful DevSynapse run."
        )
        body = _skill_body_from_command(user_message, command, result, output)
        tags = [task_type, first_command, "nudge"]

        try:
            return self._skill_creator(
                name=skill_name,
                description=description,
                body=body,
                category=task_type,
                project_name=project_name,
                tags=tags,
                replace=False,
                source="nudge",
            )
        except Exception:
            return self._skill_updater(
                skill_name,
                body=body,
                description=description,
                project_name=project_name,
            )


def _shorten(value: Optional[str], limit: int) -> str:
    normalized = " ".join((value or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


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


def _first_command_word(command: str) -> str:
    match = re.search(r'"([^"]+)"', command)
    command_text = match.group(1) if match else command
    parts = command_text.strip().split()
    raw = parts[0] if parts else "command"
    return re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-") or "command"


def _skill_body_from_command(
    user_message: str,
    command: str,
    result: Optional[str],
    output: Optional[str],
) -> str:
    return "\n".join(
        [
            "## When to Use",
            _shorten(user_message, 500),
            "",
            "## Steps",
            "1. Confirm the selected project context is correct.",
            f"2. Run or adapt this command through the command tool: `{command}`.",
            "3. Inspect output before proposing edits or follow-up commands.",
            "",
            "## Last Known Outcome",
            _shorten(output or result or "The command completed successfully.", 900),
            "",
            "## Verification",
            "- Prefer read-only inspection first when the task can be diagnosed safely.",
            "- Keep project-scoped mutation rules in place for any follow-up edits.",
        ]
    )
