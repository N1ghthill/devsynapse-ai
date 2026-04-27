"""
Persistent learning signals for the DevSynapse coding agent.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from config.settings import get_settings
from core.llm_optimization import ModelRoute, build_task_profile, cache_hit_rate_pct

POSITIVE_FEEDBACK = ("bom", "ótimo", "otimo", "excelente", "útil", "util", "correto", "perfeito")
NEGATIVE_FEEDBACK = ("ruim", "errado", "inútil", "inutil", "incorreto", "péssimo", "pessimo")


class AgentLearningStore:
    """Store explicit and implicit learning signals for future routing."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_learning_for_signature(self, task_signature: str) -> Optional[Dict[str, Any]]:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT task_signature, task_type, preferred_model, confidence,
                   success_count, failure_count, learned_reason, updated_at
            FROM agent_learning
            WHERE task_signature = ?
            """,
            (task_signature,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_learning_context(self, limit: int = 6) -> str:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT task_type, preferred_model, confidence, success_count,
                   failure_count, learned_reason
            FROM agent_learning
            WHERE confidence >= 0.55
            ORDER BY confidence DESC, updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not rows:
            return "Nenhum padrão de agente aprendido ainda."

        lines = ["Padrões aprendidos do agente:"]
        for row in rows:
            lines.append(
                "- "
                f"{row['task_type']}: preferir {row['preferred_model']} "
                f"(confiança {float(row['confidence']):.0%}, "
                f"sucessos {int(row['success_count'] or 0)}, "
                f"falhas {int(row['failure_count'] or 0)}, "
                f"motivo: {row['learned_reason']})"
            )
        return "\n".join(lines)

    def get_learning_stats(self) -> Dict[str, Any]:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS learned_patterns,
                SUM(COALESCE(success_count, 0)) AS success_signals,
                SUM(COALESCE(failure_count, 0)) AS failure_signals,
                AVG(confidence) AS avg_confidence
            FROM agent_learning
            """
        )
        totals = dict(cursor.fetchone())
        cursor.execute(
            """
            SELECT selected_model, COUNT(*) AS count
            FROM agent_route_decisions
            GROUP BY selected_model
            ORDER BY count DESC
            """
        )
        by_model = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {
            "learned_patterns": int(totals.get("learned_patterns") or 0),
            "success_signals": int(totals.get("success_signals") or 0),
            "failure_signals": int(totals.get("failure_signals") or 0),
            "avg_confidence": float(totals.get("avg_confidence") or 0.0),
            "by_model": by_model,
        }

    def record_route_decision(
        self,
        conversation_id: Optional[str],
        route: ModelRoute,
        usage: Optional[Dict[str, Any]] = None,
        project_name: Optional[str] = None,
        opencode_command: Optional[str] = None,
    ) -> None:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_route_decisions (
                conversation_id, timestamp, task_signature, task_type, complexity,
                selected_model, fallback_model, budget_mode, routing_reason,
                learned_preference, learned_confidence, prompt_tokens,
                completion_tokens, cache_hit_rate_pct, estimated_cost_usd,
                project_name, opencode_command
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                datetime.now().isoformat(),
                route.task_signature,
                route.task_type,
                route.complexity,
                (usage or {}).get("model") or route.model,
                route.fallback_model,
                route.budget_mode,
                route.reason,
                route.learned_preference,
                route.learned_confidence,
                (usage or {}).get("prompt_tokens"),
                (usage or {}).get("completion_tokens"),
                cache_hit_rate_pct(usage or {}),
                (usage or {}).get("estimated_cost_usd"),
                project_name,
                opencode_command,
            ),
        )
        conn.commit()
        conn.close()

    def learn_from_feedback(
        self,
        conversation_id: Optional[str],
        feedback: str,
        score: Optional[int] = None,
    ) -> None:
        if not conversation_id:
            return

        row = self._latest_conversation(conversation_id)
        if not row:
            return

        sentiment = self._feedback_sentiment(feedback, score)
        if sentiment == "neutral":
            return

        selected_model = row.get("llm_model") or get_settings().deepseek_flash_model
        preferred_model = (
            selected_model if sentiment == "positive" else get_settings().deepseek_pro_model
        )
        profile = build_task_profile(row.get("user_message") or "")
        reason = f"feedback_{sentiment}"
        self._upsert_learning(
            task_signature=profile.signature,
            task_type=profile.task_type,
            preferred_model=preferred_model,
            positive=sentiment == "positive",
            learned_reason=reason,
            evidence={
                "conversation_id": conversation_id,
                "feedback": feedback[:500],
                "score": score,
                "selected_model": selected_model,
            },
        )

    def learn_from_command_outcome(
        self,
        conversation_id: Optional[str],
        command: str,
        success: bool,
        result: str,
    ) -> None:
        if not conversation_id:
            return

        row = self._latest_conversation(conversation_id)
        if not row:
            return

        selected_model = row.get("llm_model") or get_settings().deepseek_flash_model
        preferred_model = selected_model if success else get_settings().deepseek_pro_model
        profile = build_task_profile(f"{row.get('user_message') or ''}\n{command}")
        self._upsert_learning(
            task_signature=profile.signature,
            task_type=profile.task_type,
            preferred_model=preferred_model,
            positive=success,
            learned_reason="command_success" if success else "command_failure",
            evidence={
                "conversation_id": conversation_id,
                "command": command,
                "result": result[:500],
                "selected_model": selected_model,
            },
        )

    def _latest_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT conversation_id, user_message, ai_response, llm_model,
                   opencode_command, execution_status, conversation_project_name
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

    def _upsert_learning(
        self,
        task_signature: str,
        task_type: str,
        preferred_model: str,
        positive: bool,
        learned_reason: str,
        evidence: Dict[str, Any],
    ) -> None:
        now = datetime.now().isoformat()
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT preferred_model, confidence, success_count, failure_count
            FROM agent_learning
            WHERE task_signature = ?
            """,
            (task_signature,),
        )
        row = cursor.fetchone()

        if row is None:
            confidence = 0.6 if positive else 0.68
            success_count = 1 if positive else 0
            failure_count = 0 if positive else 1
            cursor.execute(
                """
                INSERT INTO agent_learning (
                    task_signature, task_type, preferred_model, confidence,
                    success_count, failure_count, learned_reason, evidence, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_signature,
                    task_type,
                    preferred_model,
                    confidence,
                    success_count,
                    failure_count,
                    learned_reason,
                    json.dumps([evidence], ensure_ascii=False),
                    now,
                ),
            )
        else:
            current = dict(row)
            current_model = current["preferred_model"]
            confidence = float(current["confidence"] or 0.0)
            success_count = int(current["success_count"] or 0)
            failure_count = int(current["failure_count"] or 0)

            if positive:
                success_count += 1
                if current_model == preferred_model:
                    confidence = min(0.95, confidence + 0.08)
                else:
                    confidence = max(0.35, confidence - 0.10)
            else:
                failure_count += 1
                if current_model == preferred_model:
                    confidence = min(0.95, confidence + 0.12)
                else:
                    confidence = max(0.35, confidence - 0.16)

            if confidence < 0.5:
                current_model = preferred_model
                confidence = 0.6 if positive else 0.68

            previous_evidence = self._safe_json_list(
                cursor,
                "SELECT evidence FROM agent_learning WHERE task_signature = ?",
                (task_signature,),
            )
            previous_evidence.append(evidence)
            cursor.execute(
                """
                UPDATE agent_learning
                SET task_type = ?,
                    preferred_model = ?,
                    confidence = ?,
                    success_count = ?,
                    failure_count = ?,
                    learned_reason = ?,
                    evidence = ?,
                    updated_at = ?
                WHERE task_signature = ?
                """,
                (
                    task_type,
                    current_model,
                    confidence,
                    success_count,
                    failure_count,
                    learned_reason,
                    json.dumps(previous_evidence[-20:], ensure_ascii=False),
                    now,
                    task_signature,
                ),
            )

        conn.commit()
        conn.close()

    @staticmethod
    def _safe_json_list(
        cursor: sqlite3.Cursor,
        query: str,
        params: tuple[Any, ...],
    ) -> list[Dict[str, Any]]:
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return []
        try:
            data = json.loads(row[0] or "[]")
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    @staticmethod
    def _feedback_sentiment(feedback: str, score: Optional[int]) -> str:
        lowered = feedback.lower()
        if score is not None:
            if score >= 4:
                return "positive"
            if score <= 2:
                return "negative"
        if any(keyword in lowered for keyword in POSITIVE_FEEDBACK):
            return "positive"
        if any(keyword in lowered for keyword in NEGATIVE_FEEDBACK):
            return "negative"
        return "neutral"
