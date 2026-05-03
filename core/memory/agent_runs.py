"""
Persistent task-run state for DevSynapse agent work.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Optional

ACTIVE_STATUSES = {"running", "waiting_confirmation", "blocked"}


class AgentRunStore:
    """Track agent goals, execution events, and next actions per conversation."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def start_or_resume_run(
        self,
        conversation_id: Optional[str],
        goal: str,
        project_name: Optional[str] = None,
        next_action: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if not conversation_id or not goal.strip():
            return None

        active = self.get_active_run(conversation_id)
        now = datetime.now().isoformat()
        if active is not None:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE agent_runs
                SET project_name = COALESCE(?, project_name),
                    next_action = COALESCE(?, next_action),
                    updated_at = ?
                WHERE id = ?
                """,
                (project_name, next_action, now, active["id"]),
            )
            conn.commit()
            conn.close()
            return self.get_run(active["id"])

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_runs
            (conversation_id, goal, project_name, status, next_action, created_at, updated_at)
            VALUES (?, ?, ?, 'running', ?, ?, ?)
            """,
            (
                conversation_id,
                goal.strip(),
                project_name,
                next_action or "Executar a próxima etapa útil dentro do projeto ativo.",
                now,
                now,
            ),
        )
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        self.record_event(
            run_id=run_id,
            conversation_id=conversation_id,
            event_type="goal",
            title="Objetivo recebido",
            status="running",
            details={"goal": goal.strip()},
            project_name=project_name,
        )
        return self.get_run(run_id)

    def get_run(self, run_id: int) -> Optional[dict[str, Any]]:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, conversation_id, goal, project_name, status, next_action,
                   created_at, updated_at, completed_at
            FROM agent_runs
            WHERE id = ?
            """,
            (run_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_active_run(self, conversation_id: Optional[str]) -> Optional[dict[str, Any]]:
        if not conversation_id:
            return None
        conn = self.get_db_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        cursor.execute(
            f"""
            SELECT id, conversation_id, goal, project_name, status, next_action,
                   created_at, updated_at, completed_at
            FROM agent_runs
            WHERE conversation_id = ?
              AND status IN ({placeholders})
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (conversation_id, *sorted(ACTIVE_STATUSES)),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_run_status(
        self,
        run_id: int,
        status: str,
        next_action: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        now = datetime.now().isoformat()
        completed_at = now if status == "completed" else None
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE agent_runs
            SET status = ?,
                next_action = COALESCE(?, next_action),
                project_name = COALESCE(?, project_name),
                updated_at = ?,
                completed_at = COALESCE(?, completed_at)
            WHERE id = ?
            """,
            (status, next_action, project_name, now, completed_at, run_id),
        )
        conn.commit()
        conn.close()
        return self.get_run(run_id)

    def record_event(
        self,
        run_id: int,
        conversation_id: Optional[str],
        event_type: str,
        title: str,
        status: Optional[str] = None,
        command: Optional[str] = None,
        reason_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        project_name: Optional[str] = None,
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_run_events
            (run_id, conversation_id, event_type, title, status, command,
             reason_code, details, project_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                conversation_id,
                event_type,
                title,
                status,
                command,
                reason_code,
                json.dumps(details or {}, ensure_ascii=False),
                project_name,
                now,
            ),
        )
        event_id = cursor.lastrowid
        cursor.execute(
            "UPDATE agent_runs SET updated_at = ?, project_name = COALESCE(?, project_name) WHERE id = ?",
            (now, project_name, run_id),
        )
        conn.commit()
        cursor.execute(
            """
            SELECT id, run_id, conversation_id, event_type, title, status, command,
                   reason_code, details, project_name, created_at
            FROM agent_run_events
            WHERE id = ?
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return self._event_from_row(row)

    def record_command_result(
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
    ) -> Optional[dict[str, Any]]:
        run = self.start_or_resume_run(
            conversation_id=conversation_id,
            goal=goal,
            project_name=project_name,
            next_action="Analisar o resultado do comando e continuar a tarefa.",
        )
        if run is None:
            return None

        normalized_status = status or ("success" if success else "failed")
        if success:
            next_action = "Continuar a tarefa com base no resultado do comando."
            run_status = "running"
        elif normalized_status == "blocked":
            next_action = "Escolher uma ação permitida ou informar a permissão necessária."
            run_status = "blocked"
        else:
            next_action = "Corrigir a falha ou escolher uma alternativa viável."
            run_status = "running"

        event = self.record_event(
            run_id=run["id"],
            conversation_id=conversation_id,
            event_type="command_result",
            title="Comando executado" if success else "Comando não concluiu",
            status=normalized_status,
            command=command,
            reason_code=reason_code,
            details={
                "success": success,
                "result": result,
                "output_excerpt": (output or "")[:1000],
            },
            project_name=project_name,
        )
        self.update_run_status(
            run["id"],
            status=run_status,
            next_action=next_action,
            project_name=project_name,
        )
        return event

    def record_final_response(
        self,
        run_id: int,
        conversation_id: Optional[str],
        response: str,
        has_pending_command: bool,
        project_name: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if has_pending_command:
            status = "waiting_confirmation"
            next_action = "Aguardar confirmação do comando proposto na interface."
        else:
            status = "completed"
            next_action = "Tarefa concluída ou resumida para o usuário."

        event = self.record_event(
            run_id=run_id,
            conversation_id=conversation_id,
            event_type="final_response",
            title="Resposta final gerada",
            status=status,
            details={"response_excerpt": response[:1000]},
            project_name=project_name,
        )
        self.update_run_status(
            run_id,
            status=status,
            next_action=next_action,
            project_name=project_name,
        )
        return event

    def get_run_events(self, run_id: int, limit: int = 20) -> list[dict[str, Any]]:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, run_id, conversation_id, event_type, title, status, command,
                   reason_code, details, project_name, created_at
            FROM agent_run_events
            WHERE run_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (run_id, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._event_from_row(row) for row in reversed(rows)]

    def get_run_context(self, conversation_id: Optional[str], limit: int = 8) -> str:
        run = self.get_active_run(conversation_id)
        if run is None:
            return "Nenhuma tarefa de agente ativa."

        lines = [
            f"Run #{run['id']} - status: {run['status']}",
            f"Objetivo: {run['goal']}",
        ]
        if run.get("project_name"):
            lines.append(f"Projeto: {run['project_name']}")
        if run.get("next_action"):
            lines.append(f"Próxima ação: {run['next_action']}")

        events = self.get_run_events(run["id"], limit=limit)
        if events:
            lines.append("Eventos recentes:")
            for event in events[-limit:]:
                suffix = f" [{event['status']}]" if event.get("status") else ""
                command = f" - {event['command']}" if event.get("command") else ""
                reason = f" ({event['reason_code']})" if event.get("reason_code") else ""
                lines.append(f"- {event['title']}{suffix}{reason}{command}")
        return "\n".join(lines)

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
        event = dict(row)
        try:
            event["details"] = json.loads(event.get("details") or "{}")
        except (TypeError, json.JSONDecodeError):
            event["details"] = {}
        return event
