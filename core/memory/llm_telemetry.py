"""
LLM model catalog and telemetry persistence.

Extracted from MemorySystem to keep the facade thin.
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.db import connect_db
from core.llm_optimization import ModelRoute


class LLMTelemetryStore:
    """Persist LLM model catalog entries and request telemetry."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def upsert_models(self, models: List[Dict[str, Any]]) -> int:
        """Insert or update model catalog entries."""
        if not models:
            return 0

        now = datetime.now().isoformat()
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        for model in models:
            cursor.execute(
                """
                INSERT INTO llm_model_catalog (
                    provider, model_id, name, context_length, input_cost_per_token,
                    output_cost_per_token, cache_read_cost_per_token, raw_pricing,
                    capabilities, source_url, discovered_at, last_seen_at, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(provider, model_id) DO UPDATE SET
                    name = excluded.name,
                    context_length = excluded.context_length,
                    input_cost_per_token = excluded.input_cost_per_token,
                    output_cost_per_token = excluded.output_cost_per_token,
                    cache_read_cost_per_token = excluded.cache_read_cost_per_token,
                    raw_pricing = excluded.raw_pricing,
                    capabilities = excluded.capabilities,
                    source_url = excluded.source_url,
                    last_seen_at = excluded.last_seen_at,
                    enabled = 1
                """,
                (
                    model["provider"],
                    model["model_id"],
                    model.get("name"),
                    model.get("context_length"),
                    model.get("input_cost_per_token"),
                    model.get("output_cost_per_token"),
                    model.get("cache_read_cost_per_token"),
                    json.dumps(model.get("raw_pricing") or {}),
                    json.dumps(model.get("capabilities") or {}),
                    model.get("source_url"),
                    now,
                    now,
                ),
            )
        conn.commit()
        conn.close()
        return len(models)

    def list_models(
        self,
        provider: Optional[str] = None,
        enabled_only: bool = True,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """List models from the catalog."""
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        filters = []
        params: List[Any] = []
        if provider:
            filters.append("provider = ?")
            params.append(provider)
        if enabled_only:
            filters.append("enabled = 1")
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        cursor.execute(
            f"""
            SELECT provider, model_id, name, context_length, input_cost_per_token,
                   output_cost_per_token, cache_read_cost_per_token, raw_pricing,
                   capabilities, source_url, discovered_at, last_seen_at, enabled
            FROM llm_model_catalog
            {where}
            ORDER BY provider, COALESCE(input_cost_per_token, 999), model_id
            LIMIT ?
            """,
            (*params, limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_dict(row) for row in rows]

    def get_model(self, provider: str, model_id: str) -> Optional[Dict[str, Any]]:
        """Get a single model entry."""
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT provider, model_id, name, context_length, input_cost_per_token,
                   output_cost_per_token, cache_read_cost_per_token, raw_pricing,
                   capabilities, source_url, discovered_at, last_seen_at, enabled
            FROM llm_model_catalog
            WHERE provider = ? AND model_id = ?
            """,
            (provider, model_id),
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_dict(row) if row else None

    def record_telemetry(
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
        """Record a single LLM request telemetry entry."""
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO llm_request_telemetry (
                timestamp, user_id, conversation_id, provider, model, routing_reason,
                task_type, complexity, success, error_message, prompt_tokens,
                completion_tokens, total_tokens, prompt_cache_hit_tokens,
                prompt_cache_miss_tokens, reasoning_tokens, estimated_cost_usd,
                first_token_latency_ms, total_latency_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                user_id,
                conversation_id,
                provider,
                model,
                route.reason if route else None,
                route.task_type if route else None,
                route.complexity if route else None,
                int(success),
                error_message[:1000] if error_message else None,
                (usage or {}).get("prompt_tokens"),
                (usage or {}).get("completion_tokens"),
                (usage or {}).get("total_tokens"),
                (usage or {}).get("prompt_cache_hit_tokens"),
                (usage or {}).get("prompt_cache_miss_tokens"),
                (usage or {}).get("reasoning_tokens"),
                (usage or {}).get("estimated_cost_usd"),
                first_token_latency_ms,
                total_latency_ms,
            ),
        )
        conn.commit()
        conn.close()

    def get_telemetry_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get aggregated telemetry stats for the given time window."""
        conn = connect_db(self.db_path)
        cursor = conn.cursor()
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute(
            """
            SELECT provider, model, user_id,
                   COUNT(*) AS request_count,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS error_count,
                   AVG(first_token_latency_ms) AS avg_first_token_latency_ms,
                   AVG(total_latency_ms) AS avg_total_latency_ms,
                   SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
            FROM llm_request_telemetry
            WHERE timestamp >= ?
            GROUP BY provider, model, user_id
            ORDER BY request_count DESC
            LIMIT 50
            """,
            (since_time,),
        )
        rows = cursor.fetchall()
        conn.close()
        return {
            "by_user_model": [
                {
                    "provider": row["provider"],
                    "model": row["model"],
                    "user_id": row["user_id"],
                    "request_count": int(row["request_count"] or 0),
                    "error_count": int(row["error_count"] or 0),
                    "error_rate": (
                        float(row["error_count"] or 0) / float(row["request_count"] or 1)
                    ),
                    "avg_first_token_latency_ms": row["avg_first_token_latency_ms"],
                    "avg_total_latency_ms": row["avg_total_latency_ms"],
                    "estimated_cost_usd": float(row["estimated_cost_usd"] or 0.0),
                }
                for row in rows
            ]
        }

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        return {
            "provider": row["provider"],
            "model_id": row["model_id"],
            "name": row["name"],
            "context_length": row["context_length"],
            "input_cost_per_token": row["input_cost_per_token"],
            "output_cost_per_token": row["output_cost_per_token"],
            "cache_read_cost_per_token": row["cache_read_cost_per_token"],
            "raw_pricing": json.loads(row["raw_pricing"] or "{}"),
            "capabilities": json.loads(row["capabilities"] or "{}"),
            "source_url": row["source_url"],
            "discovered_at": row["discovered_at"],
            "last_seen_at": row["last_seen_at"],
            "enabled": bool(row["enabled"]),
        }
