"""
Persistent storage for DevSynapse.
"""

import csv
import io
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config.settings import DEFAULT_PREFERENCES, KNOWN_PROJECTS, MEMORY_DB_PATH
from core.migrations import build_memory_migration_manager

logger = logging.getLogger(__name__)


class MemorySystem:
    """Gerencia memória persistente do DevSynapse."""
    
    def __init__(self):
        self.db_path = MEMORY_DB_PATH
        self._init_database()
        
    def _init_database(self):
        """Inicializa banco de dados SQLite"""

        build_memory_migration_manager(self.db_path).apply_migrations()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Inserir preferências padrão
        for key, value in DEFAULT_PREFERENCES.items():
            cursor.execute('''
                INSERT OR IGNORE INTO user_preferences 
                (key, value, source, confidence, last_updated, evidence_count)
                VALUES (?, ?, 'default', 1.0, ?, 1)
            ''', (key, value, datetime.now().isoformat()))
        
        # Inserir projetos conhecidos
        for name, info in KNOWN_PROJECTS.items():
            cursor.execute('''
                INSERT OR REPLACE INTO projects 
                (name, path, type, priority, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, info['path'], info['type'], info['priority'], 
                  datetime.now().isoformat(), 0))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Banco de dados inicializado: {self.db_path}")

    def get_db_connection(self) -> sqlite3.Connection:
        """Return a SQLite connection for internal/service use."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    async def get_conversation_context(self, conversation_id: Optional[str] = None) -> Dict:
        """Obtém contexto para uma conversa"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        context = {
            "conversation_history": [],
            "conversation_messages": [],
            "user_preferences": self.get_user_preferences(),
            "projects_context": self.get_projects_context(),
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

            if row["conversation_project_name"]:
                assistant_message["projectName"] = row["conversation_project_name"]

            context["conversation_history"].extend([
                {"role": "user", "content": row["user_message"]},
                {"role": "assistant", "content": row["ai_response"]}
            ])
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

        return {
            "totals": {
                "request_count": int(totals.get("request_count") or 0),
                "conversation_count": int(totals.get("conversation_count") or 0),
                "prompt_tokens": int(totals.get("prompt_tokens") or 0),
                "completion_tokens": int(totals.get("completion_tokens") or 0),
                "total_tokens": int(totals.get("total_tokens") or 0),
                "prompt_cache_hit_tokens": int(totals.get("prompt_cache_hit_tokens") or 0),
                "prompt_cache_miss_tokens": int(totals.get("prompt_cache_miss_tokens") or 0),
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
                    "estimated_cost_usd": float(row["estimated_cost_usd"] or 0.0),
                }
                for row in by_day
            ],
            "timeframe_hours": hours,
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

        project_totals: dict[str, dict[str, Any]] = {}

        for row in rows:
            blob = " ".join(
                part for part in [
                    row["user_message"],
                    row["ai_response"],
                    row["opencode_command"],
                ] if part
            ).lower()
            matched_project = row["conversation_project_name"] or self._infer_project_name_from_text(
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
    
    def get_user_preferences(self) -> str:
        """Retorna preferências do usuário como texto formatado"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT key, value, confidence, source
            FROM user_preferences
            ORDER BY confidence DESC, evidence_count DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "Nenhuma preferência aprendida ainda."
        
        text = "Preferências conhecidas do Irving:\n"
        for row in rows:
            source_emoji = "🎯" if row["source"] == "explicit" else "📚" if row["source"] == "learned" else "⚙️"
            text += f"- {source_emoji} **{row['key']}**: {row['value']} "
            text += f"(confiança: {row['confidence']:.0%})\n"
        
        return text
    
    def get_projects_context(self) -> str:
        """Retorna contexto sobre projetos"""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, type, priority, last_accessed, access_count
            FROM projects
            ORDER BY priority DESC, access_count DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "Nenhum projeto registrado."
        
        text = "Projetos conhecidos:\n"
        for row in rows:
            priority_emoji = "🔥" if row["priority"] == "high" else "⚡" if row["priority"] == "medium" else "📁"
            last_access = datetime.fromisoformat(row["last_accessed"]).strftime("%d/%m %H:%M")
            text += f"- {priority_emoji} **{row['name']}** ({row['type']}) "
            text += f"- acessado {row['access_count']}x, último: {last_access}\n"
        
        return text
    
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
        
        inferred_project_name = project_name or self._infer_project_name_from_text(
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
        
        # Atualizar contador de acesso se mencionar projeto (após fechar conexão)
        self._update_project_access(user_message)
        
        logger.debug(f"Interação salva: {user_message[:50]}...")
    
    def _update_project_access(self, message: str):
        """Atualiza contador de acesso para projetos mencionados"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Verificar se mensagem menciona algum projeto conhecido
        cursor.execute('SELECT name FROM projects')
        projects = [row[0] for row in cursor.fetchall()]
        
        for project in projects:
            if project.lower() in message.lower():
                cursor.execute('''
                    UPDATE projects 
                    SET access_count = access_count + 1, 
                        last_accessed = ?
                    WHERE name = ?
                ''', (datetime.now().isoformat(), project))
                logger.debug(f"Projeto acessado: {project}")
        
        conn.commit()
        conn.close()

    def _infer_project_name_from_text(self, *texts: Optional[str]) -> Optional[str]:
        blob = " ".join(part for part in texts if part).lower()
        if not blob:
            return None

        for project_name, info in KNOWN_PROJECTS.items():
            if project_name.lower() in blob or str(info["path"]).lower() in blob:
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
    
    def update_preference(self, key: str, value: str, source: str = "learned"):
        """Atualiza ou cria uma preferência do usuário"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT value, confidence, evidence_count 
            FROM user_preferences 
            WHERE key = ?
        ''', (key,))
        
        row = cursor.fetchone()
        
        if row:
            # Já existe - atualizar
            old_value, old_confidence, old_count = row
            if old_value == value:
                # Mesmo valor - aumentar confiança
                new_confidence = min(old_confidence * 1.05, 1.0)
                new_count = old_count + 1
                cursor.execute(
                    '''
                    UPDATE user_preferences
                    SET confidence = ?, evidence_count = ?, last_updated = ?
                    WHERE key = ? AND value = ?
                    ''',
                    (new_confidence, new_count, datetime.now().isoformat(), key, old_value),
                )
            else:
                # Valor diferente - diminuir confiança no antigo, criar novo
                new_confidence = max(old_confidence * 0.7, 0.1)
                cursor.execute('''
                    UPDATE user_preferences 
                    SET confidence = ?, last_updated = ?
                    WHERE key = ? AND value = ?
                ''', (new_confidence, datetime.now().isoformat(), key, old_value))
                
                # Inserir novo valor
                cursor.execute('''
                    INSERT OR REPLACE INTO user_preferences 
                    (key, value, source, confidence, last_updated, evidence_count)
                    VALUES (?, ?, ?, ?, ?, 1)
                ''', (key, value, source, 0.5, datetime.now().isoformat()))
        else:
            # Nova preferência
            cursor.execute('''
                INSERT INTO user_preferences 
                (key, value, source, confidence, last_updated, evidence_count)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (key, value, source, 0.7, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Preferência atualizada: {key} = {value} ({source})")

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Return a stored user by username."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT username, password_hash, role, is_active, created_at, last_login
            FROM users
            WHERE username = ?
            ''',
            (username,),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return {
            "username": row["username"],
            "password_hash": row["password_hash"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
            "last_login": row["last_login"],
        }

    def upsert_user(self, username: str, password_hash: str, role: str = "user", is_active: bool = True):
        """Create or update a user record."""

        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO users (username, password_hash, role, is_active, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, NULL)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                role = excluded.role,
                is_active = excluded.is_active
            ''',
            (username, password_hash, role, int(is_active), now),
        )
        conn.commit()
        conn.close()

    def touch_user_login(self, username: str):
        """Update the user's last successful login timestamp."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE users
            SET last_login = ?
            WHERE username = ?
            ''',
            (datetime.now().isoformat(), username),
        )
        conn.commit()
        conn.close()

    def get_app_settings(self) -> Dict[str, Any]:
        """Return persisted application settings."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT key, value
            FROM app_settings
            '''
        )
        rows = cursor.fetchall()
        conn.close()
        return {row["key"]: row["value"] for row in rows}

    def update_app_settings(self, settings_data: Dict[str, Any]):
        """Persist runtime-adjustable settings."""

        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for key, value in settings_data.items():
            cursor.execute(
                '''
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                ''',
                (key, str(value), now),
            )
        conn.commit()
        conn.close()

    def get_project_permissions(self, username: Optional[str] = None) -> Dict[str, list[str]] | list[str]:
        """Return project mutation permissions for one user or for all users."""

        conn = self.get_db_connection()
        cursor = conn.cursor()

        if username is None:
            cursor.execute(
                """
                SELECT username, project_name
                FROM project_permissions
                WHERE permission = 'mutate'
                ORDER BY username, project_name
                """
            )
            rows = cursor.fetchall()
            conn.close()

            permissions: Dict[str, list[str]] = {}
            for row in rows:
                permissions.setdefault(row["username"], []).append(row["project_name"])
            return permissions

        cursor.execute(
            """
            SELECT project_name
            FROM project_permissions
            WHERE username = ? AND permission = 'mutate'
            ORDER BY project_name
            """,
            (username,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [row["project_name"] for row in rows]

    def replace_project_permissions(self, username: str, project_names: list[str], permission: str = "mutate"):
        """Replace a user's project permissions with an explicit list."""

        now = datetime.now().isoformat()
        unique_projects = sorted(set(project_names))
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM project_permissions
            WHERE username = ? AND permission = ?
            """,
            (username, permission),
        )
        for project_name in unique_projects:
            cursor.execute(
                """
                INSERT INTO project_permissions (username, project_name, permission, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, project_name, permission, now),
            )
        conn.commit()
        conn.close()

    def log_admin_action(
        self,
        actor_username: str,
        action: str,
        target_username: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Persist an administrative audit event."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO admin_audit_logs (
                actor_username,
                target_username,
                action,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                actor_username,
                target_username,
                action,
                json.dumps(details or {}),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def get_admin_audit_logs(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Return recent administrative audit events."""

        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, actor_username, target_username, action, details, created_at
            FROM admin_audit_logs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row["id"],
                "actor_username": row["actor_username"],
                "target_username": row["target_username"],
                "action": row["action"],
                "details": json.loads(row["details"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
