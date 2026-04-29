"""
Conversation storage and LLM usage tracking for DevSynapse.
"""

import csv
import io
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.llm_optimization import cache_hit_rate_pct

logger = logging.getLogger(__name__)


class ConversationStore:
    """Manages conversation persistence and LLM usage analytics."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_db_connection(self) -> sqlite3.Connection:
        """Return a SQLite connection for internal/service use."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_conversation_project_name(self, conversation_id: Optional[str]) -> Optional[str]:
        """Return the persisted project scope for a conversation, when one exists."""

        if not conversation_id:
            return None

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT conversation_project_name
            FROM conversations
            WHERE conversation_id = ?
              AND conversation_project_name IS NOT NULL
              AND TRIM(conversation_project_name) != ''
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (conversation_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return row["conversation_project_name"] if row else None

    async def get_conversation_context(self, conversation_id: Optional[str] = None) -> Dict:
        """Obtém contexto para uma conversa"""

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        context = {
            "conversation_history": [],
            "conversation_messages": [],
            "user_preferences": getattr(self, '_get_user_preferences_fn', lambda: "")( ),
            "projects_context": getattr(self, '_get_projects_context_fn', lambda: "")( ),
            "project_name": None,
            "recent_decisions": []
        }

        # Obter histórico recente da conversa
        if conversation_id:
            cursor.execute('''
                SELECT id, conversation_id, timestamp, user_message, ai_response,
                       opencode_command, command_executed, execution_result,
                       execution_output, execution_status, execution_reason_code,
                       llm_provider, llm_model, prompt_tokens, completion_tokens,
                       total_tokens, prompt_cache_hit_tokens, prompt_cache_miss_tokens,
                       reasoning_tokens, estimated_cost_usd, conversation_project_name
                FROM conversations 
                WHERE conversation_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 5
            ''', (conversation_id,))
        else:
            cursor.execute('''
                SELECT id, conversation_id, timestamp, user_message, ai_response,
                       opencode_command, command_executed, execution_result,
                       execution_output, execution_status, execution_reason_code,
                       llm_provider, llm_model, prompt_tokens, completion_tokens,
                       total_tokens, prompt_cache_hit_tokens, prompt_cache_miss_tokens,
                       reasoning_tokens, estimated_cost_usd, conversation_project_name
                FROM conversations 
                ORDER BY timestamp DESC 
                LIMIT 5
            ''')

        rows = cursor.fetchall()
        for row in reversed(rows):  # Ordem cronológica
            user_message = {
                "id": f"conv-{row['id']}-user",
                "role": "user",
                "content": row["user_message"],
                "timestamp": row["timestamp"],
            }
            assistant_message = {
                "id": f"conv-{row['id']}-assistant",
                "role": "assistant",
                "content": row["ai_response"],
                "timestamp": row["timestamp"],
            }

            if row["conversation_project_name"]:
                context["project_name"] = row["conversation_project_name"]
                user_message["projectName"] = row["conversation_project_name"]
                assistant_message["projectName"] = row["conversation_project_name"]

            if row["opencode_command"]:
                assistant_message["command"] = row["opencode_command"]
                assistant_message["commandStatus"] = (
                    row["execution_status"]
                    or ("success" if row["command_executed"] else "proposed")
                )
                assistant_message["commandResult"] = (
                    row["execution_output"] or row["execution_result"]
                )
                assistant_message["reasonCode"] = row["execution_reason_code"]

            if row["prompt_tokens"] is not None or row["completion_tokens"] is not None:
                assistant_message["tokenUsage"] = {
                    "provider": row["llm_provider"],
                    "model": row["llm_model"],
                    "prompt_tokens": row["prompt_tokens"] or 0,
                    "completion_tokens": row["completion_tokens"] or 0,
                    "total_tokens": row["total_tokens"] or 0,
                    "prompt_cache_hit_tokens": row["prompt_cache_hit_tokens"] or 0,
                    "prompt_cache_miss_tokens": row["prompt_cache_miss_tokens"] or 0,
                    "reasoning_tokens": row["reasoning_tokens"] or 0,
                    "estimated_cost_usd": row["estimated_cost_usd"],
                }

            history_user = {"role": "user", "content": row["user_message"]}
            history_assistant = {"role": "assistant", "content": row["ai_response"]}

            if row["opencode_command"] and row["command_executed"]:
                output_text = row["execution_output"] or row["execution_result"] or ""
                status = row["execution_status"] or "success"
                if output_text:
                    history_assistant["content"] += (
                        f"\n\n---\n"
                        f"User executed: `{row['opencode_command']}`\n"
                        f"Output:\n```\n{output_text[:2000]}\n```"
                    )
                else:
                    history_assistant["content"] += (
                        f"\n\n---\n"
                        f"User executed: `{row['opencode_command']}` (status: {status}, no output)"
                    )

            context["conversation_history"].extend([history_user, history_assistant])
            context["conversation_messages"].extend([user_message, assistant_message])

        # Obter decisões recentes
        cursor.execute('''
            SELECT decision, outcome, user_rating
            FROM decisions
            ORDER BY timestamp DESC
            LIMIT 3
        ''')

        decisions = cursor.fetchall()
        for decision in decisions:
            context["recent_decisions"].append({
                "decision": decision["decision"],
                "outcome": decision["outcome"],
                "rating": decision["user_rating"]
            })

        conn.close()
        return context

    def list_conversations(self, limit: int = 20) -> list[Dict[str, Any]]:
        """Return recent conversation summaries for the chat sidebar."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                c.conversation_id,
                c.timestamp AS updated_at,
                c.user_message,
                c.ai_response,
                c.conversation_title,
                c.conversation_project_name,
                COALESCE(agg.total_tokens, 0) AS total_tokens,
                COALESCE(agg.estimated_cost_usd, 0) AS estimated_cost_usd
            FROM conversations c
            INNER JOIN (
                SELECT conversation_id, MAX(timestamp) AS max_timestamp
                FROM conversations
                WHERE conversation_id IS NOT NULL
                GROUP BY conversation_id
            ) latest
                ON latest.conversation_id = c.conversation_id
               AND latest.max_timestamp = c.timestamp
            LEFT JOIN (
                SELECT
                    conversation_id,
                    SUM(COALESCE(total_tokens, 0)) AS total_tokens,
                    SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
                FROM conversations
                WHERE conversation_id IS NOT NULL
                GROUP BY conversation_id
            ) agg
                ON agg.conversation_id = c.conversation_id
            WHERE c.conversation_id IS NOT NULL
            ORDER BY c.timestamp DESC
            LIMIT ?
            ''',
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        summaries = []
        for row in rows:
            title_source = (row["conversation_title"] or row["user_message"] or "Nova conversa").strip()
            preview_source = (row["ai_response"] or row["user_message"] or "").strip()
            summaries.append(
                {
                    "id": row["conversation_id"],
                    "title": title_source[:60] or "Nova conversa",
                    "preview": preview_source[:120],
                    "updated_at": row["updated_at"],
                    "total_tokens": int(row["total_tokens"] or 0),
                    "estimated_cost_usd": float(row["estimated_cost_usd"] or 0.0),
                    "project_name": row["conversation_project_name"],
                }
            )

        return summaries

    def get_llm_usage_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Aggregate recent LLM usage and cost from persisted conversation rows."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        cursor.execute(
            '''
            SELECT
                COUNT(*) AS request_count,
                COUNT(DISTINCT conversation_id) AS conversation_count,
                SUM(COALESCE(prompt_tokens, 0)) AS prompt_tokens,
                SUM(COALESCE(completion_tokens, 0)) AS completion_tokens,
                SUM(COALESCE(total_tokens, 0)) AS total_tokens,
                SUM(COALESCE(prompt_cache_hit_tokens, 0)) AS prompt_cache_hit_tokens,
                SUM(COALESCE(prompt_cache_miss_tokens, 0)) AS prompt_cache_miss_tokens,
                SUM(COALESCE(reasoning_tokens, 0)) AS reasoning_tokens,
                SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
            FROM conversations
            WHERE timestamp >= ?
              AND total_tokens IS NOT NULL
            ''',
            (since_time,),
        )
        totals = dict(cursor.fetchone())

        cursor.execute(
            '''
            SELECT
                substr(timestamp, 1, 10) AS day,
                COUNT(*) AS request_count,
                SUM(COALESCE(prompt_tokens, 0)) AS prompt_tokens,
                SUM(COALESCE(completion_tokens, 0)) AS completion_tokens,
                SUM(COALESCE(total_tokens, 0)) AS total_tokens,
                SUM(COALESCE(prompt_cache_hit_tokens, 0)) AS prompt_cache_hit_tokens,
                SUM(COALESCE(prompt_cache_miss_tokens, 0)) AS prompt_cache_miss_tokens,
                SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
            FROM conversations
            WHERE total_tokens IS NOT NULL
            GROUP BY substr(timestamp, 1, 10)
            ORDER BY day DESC
            LIMIT 7
            '''
        )
        by_day = [dict(row) for row in cursor.fetchall()]
        conn.close()
        totals_usage = {
            "prompt_cache_hit_tokens": int(totals.get("prompt_cache_hit_tokens") or 0),
            "prompt_cache_miss_tokens": int(totals.get("prompt_cache_miss_tokens") or 0),
        }

        return {
            "totals": {
                "request_count": int(totals.get("request_count") or 0),
                "conversation_count": int(totals.get("conversation_count") or 0),
                "prompt_tokens": int(totals.get("prompt_tokens") or 0),
                "completion_tokens": int(totals.get("completion_tokens") or 0),
                "total_tokens": int(totals.get("total_tokens") or 0),
                "prompt_cache_hit_tokens": int(totals.get("prompt_cache_hit_tokens") or 0),
                "prompt_cache_miss_tokens": int(totals.get("prompt_cache_miss_tokens") or 0),
                "cache_hit_rate_pct": cache_hit_rate_pct(totals_usage),
                "reasoning_tokens": int(totals.get("reasoning_tokens") or 0),
                "estimated_cost_usd": float(totals.get("estimated_cost_usd") or 0.0),
            },
            "by_day": [
                {
                    "day": row["day"],
                    "request_count": int(row["request_count"] or 0),
                    "prompt_tokens": int(row["prompt_tokens"] or 0),
                    "completion_tokens": int(row["completion_tokens"] or 0),
                    "total_tokens": int(row["total_tokens"] or 0),
                    "prompt_cache_hit_tokens": int(row["prompt_cache_hit_tokens"] or 0),
                    "prompt_cache_miss_tokens": int(row["prompt_cache_miss_tokens"] or 0),
                    "cache_hit_rate_pct": cache_hit_rate_pct(row),
                    "estimated_cost_usd": float(row["estimated_cost_usd"] or 0.0),
                }
                for row in by_day
            ],
            "timeframe_hours": hours,
        }

    def _aggregate_llm_usage_between(
        self,
        start_time: str,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = self.get_db_connection()
        cursor = conn.cursor()

        if end_time is None:
            cursor.execute(
                '''
                SELECT
                    COUNT(*) AS request_count,
                    COUNT(DISTINCT conversation_id) AS conversation_count,
                    SUM(COALESCE(prompt_tokens, 0)) AS prompt_tokens,
                    SUM(COALESCE(completion_tokens, 0)) AS completion_tokens,
                    SUM(COALESCE(total_tokens, 0)) AS total_tokens,
                    SUM(COALESCE(prompt_cache_hit_tokens, 0)) AS prompt_cache_hit_tokens,
                    SUM(COALESCE(prompt_cache_miss_tokens, 0)) AS prompt_cache_miss_tokens,
                    SUM(COALESCE(reasoning_tokens, 0)) AS reasoning_tokens,
                    SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
                FROM conversations
                WHERE timestamp >= ?
                  AND total_tokens IS NOT NULL
                ''',
                (start_time,),
            )
        else:
            cursor.execute(
                '''
                SELECT
                    COUNT(*) AS request_count,
                    COUNT(DISTINCT conversation_id) AS conversation_count,
                    SUM(COALESCE(prompt_tokens, 0)) AS prompt_tokens,
                    SUM(COALESCE(completion_tokens, 0)) AS completion_tokens,
                    SUM(COALESCE(total_tokens, 0)) AS total_tokens,
                    SUM(COALESCE(prompt_cache_hit_tokens, 0)) AS prompt_cache_hit_tokens,
                    SUM(COALESCE(prompt_cache_miss_tokens, 0)) AS prompt_cache_miss_tokens,
                    SUM(COALESCE(reasoning_tokens, 0)) AS reasoning_tokens,
                    SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
                FROM conversations
                WHERE timestamp >= ?
                  AND timestamp < ?
                  AND total_tokens IS NOT NULL
                ''',
                (start_time, end_time),
            )

        row = dict(cursor.fetchone())
        conn.close()

        return {
            "request_count": int(row.get("request_count") or 0),
            "conversation_count": int(row.get("conversation_count") or 0),
            "prompt_tokens": int(row.get("prompt_tokens") or 0),
            "completion_tokens": int(row.get("completion_tokens") or 0),
            "total_tokens": int(row.get("total_tokens") or 0),
            "prompt_cache_hit_tokens": int(row.get("prompt_cache_hit_tokens") or 0),
            "prompt_cache_miss_tokens": int(row.get("prompt_cache_miss_tokens") or 0),
            "reasoning_tokens": int(row.get("reasoning_tokens") or 0),
            "estimated_cost_usd": float(row.get("estimated_cost_usd") or 0.0),
        }

    def get_project_usage_breakdown(self, hours: int = 24) -> list[Dict[str, Any]]:
        """Infer LLM usage by project from conversation text and commands."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute(
            '''
            SELECT
                conversation_id,
                conversation_project_name,
                user_message,
                ai_response,
                opencode_command,
                total_tokens,
                estimated_cost_usd
            FROM conversations
            WHERE timestamp >= ?
              AND total_tokens IS NOT NULL
            ORDER BY timestamp DESC
            ''',
            (since_time,),
        )
        rows = cursor.fetchall()
        conn.close()

        project_lookup = getattr(self, '_get_project_lookup_fn', lambda: {})( )
        project_totals: dict[str, dict[str, Any]] = {}

        for row in rows:
            matched_project = row["conversation_project_name"] or self._infer_project_name_from_text(
                project_lookup,
                row["user_message"],
                row["ai_response"],
                row["opencode_command"],
            )

            if not matched_project:
                continue

            entry = project_totals.setdefault(
                matched_project,
                {
                    "project_name": matched_project,
                    "request_count": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                },
            )
            entry["request_count"] += 1
            entry["total_tokens"] += int(row["total_tokens"] or 0)
            entry["estimated_cost_usd"] += float(row["estimated_cost_usd"] or 0.0)

        return sorted(
            project_totals.values(),
            key=lambda item: (item["estimated_cost_usd"], item["total_tokens"]),
            reverse=True,
        )

    def export_llm_usage_csv(self) -> str:
        """Export detailed per-message LLM usage as CSV."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT
                conversation_id,
                timestamp,
                llm_provider,
                llm_model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                prompt_cache_hit_tokens,
                prompt_cache_miss_tokens,
                reasoning_tokens,
                estimated_cost_usd,
                user_message
            FROM conversations
            WHERE total_tokens IS NOT NULL
            ORDER BY timestamp DESC
            '''
        )
        rows = cursor.fetchall()
        conn.close()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "conversation_id",
                "timestamp",
                "provider",
                "model",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "prompt_cache_hit_tokens",
                "prompt_cache_miss_tokens",
                "reasoning_tokens",
                "estimated_cost_usd",
                "user_message_preview",
            ]
        )

        for row in rows:
            writer.writerow(
                [
                    row["conversation_id"],
                    row["timestamp"],
                    row["llm_provider"],
                    row["llm_model"],
                    int(row["prompt_tokens"] or 0),
                    int(row["completion_tokens"] or 0),
                    int(row["total_tokens"] or 0),
                    int(row["prompt_cache_hit_tokens"] or 0),
                    int(row["prompt_cache_miss_tokens"] or 0),
                    int(row["reasoning_tokens"] or 0),
                    float(row["estimated_cost_usd"] or 0.0),
                    (row["user_message"] or "")[:160],
                ]
            )

        return buffer.getvalue()

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        """Persist a display title for a conversation."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE conversations
            SET conversation_title = ?
            WHERE conversation_id = ?
            ''',
            (title.strip(), conversation_id),
        )
        changed = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return changed

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete all rows that belong to a conversation."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            DELETE FROM conversations
            WHERE conversation_id = ?
            ''',
            (conversation_id,),
        )
        changed = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return changed

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
        """Salva uma interação na memória"""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        project_lookup = getattr(self, '_get_project_lookup_fn', lambda: {})( )
        inferred_project_name = project_name or self._infer_project_name_from_text(
            project_lookup,
            user_message,
            ai_response,
            opencode_command,
        )

        cursor.execute('''
            INSERT INTO conversations 
            (
                conversation_id, timestamp, user_message, ai_response, opencode_command,
                conversation_title, llm_provider, llm_model, prompt_tokens,
                completion_tokens, total_tokens, prompt_cache_hit_tokens,
                prompt_cache_miss_tokens, reasoning_tokens, estimated_cost_usd,
                conversation_project_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            conversation_id,
            timestamp,
            user_message,
            ai_response,
            opencode_command,
            conversation_title,
            llm_usage.get("provider") if llm_usage else None,
            llm_usage.get("model") if llm_usage else None,
            llm_usage.get("prompt_tokens") if llm_usage else None,
            llm_usage.get("completion_tokens") if llm_usage else None,
            llm_usage.get("total_tokens") if llm_usage else None,
            llm_usage.get("prompt_cache_hit_tokens") if llm_usage else None,
            llm_usage.get("prompt_cache_miss_tokens") if llm_usage else None,
            llm_usage.get("reasoning_tokens") if llm_usage else None,
            llm_usage.get("estimated_cost_usd") if llm_usage else None,
            inferred_project_name,
        ))

        conn.commit()
        conn.close()

        logger.debug(f"Interação salva: {user_message[:50]}...")
        return inferred_project_name

    def _infer_project_name_from_text(self, project_lookup: Dict, *texts: Optional[str]) -> Optional[str]:
        blob = " ".join(part for part in texts if part).lower()
        if not blob:
            return None

        for project_name, info in project_lookup.items():
            project_path = str(info.get("path", "")).lower()
            if project_name.lower() in blob or (project_path and project_path in blob):
                return project_name

        return None

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
        """Salva resultado da execução de um comando"""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE conversations 
            SET command_executed = 1,
                execution_result = ?,
                execution_output = ?,
                execution_status = ?,
                execution_reason_code = ?,
                conversation_project_name = COALESCE(?, conversation_project_name)
            WHERE conversation_id = ? 
            AND opencode_command = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (result, output, status, reason_code, project_name, conversation_id, command))

        # Aprender com o resultado
        if success:
            self._learn_from_success(command, result)
        else:
            self._learn_from_failure(command, result)

        conn.commit()
        conn.close()

    def _learn_from_success(self, command: str, result: str):
        """Aprende com execução bem-sucedida"""
        # Implementar aprendizado baseado em sucesso
        pass

    def _learn_from_failure(self, command: str, result: str):
        """Aprende com execução falha"""
        # Implementar aprendizado baseado em falha
        pass

    async def save_feedback(
        self,
        conversation_id: Optional[str],
        feedback: str,
        score: Optional[int] = None
    ):
        """Salva feedback do usuário"""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE conversations 
            SET user_feedback = ?,
                feedback_score = ?
            WHERE conversation_id = ? 
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (feedback, score, conversation_id))

        conn.commit()
        conn.close()

        # Aprender com feedback (após fechar primeira conexão)
        if feedback:
            self._learn_from_feedback(feedback, score)

    def _learn_from_feedback(self, feedback: str, score: Optional[int]):
        """Aprende com feedback explícito do usuário"""

        # Análise simples de feedback
        positive_keywords = ["bom", "ótimo", "excelente", "útil", "correto", "perfeito"]
        negative_keywords = ["ruim", "errado", "inútil", "incorreto", "péssimo"]

        feedback_lower = feedback.lower()

        # Atualizar preferências baseado no feedback
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Exemplo simples: se feedback positivo, aumentar confiança
        if any(keyword in feedback_lower for keyword in positive_keywords) or (score and score > 3):
            # Aumentar confiança nas preferências recentes
            cursor.execute('''
                UPDATE user_preferences 
                SET confidence = MIN(confidence * 1.1, 1.0),
                    evidence_count = evidence_count + 1,
                    last_updated = ?
                WHERE source IN ('learned', 'explicit')
            ''', (datetime.now().isoformat(),))

        # Se feedback negativo, reconsiderar
        elif any(keyword in feedback_lower for keyword in negative_keywords) or (score and score < 3):
            cursor.execute('''
                UPDATE user_preferences 
                SET confidence = MAX(confidence * 0.8, 0.1),
                    last_updated = ?
                WHERE source IN ('learned', 'explicit')
            ''', (datetime.now().isoformat(),))

        conn.commit()
        conn.close()
