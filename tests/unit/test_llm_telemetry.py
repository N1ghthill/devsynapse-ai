"""Tests for core/memory/llm_telemetry.py."""

from datetime import datetime

from core.db import connect_db
from core.memory.llm_telemetry import LLMTelemetryStore


def _store(tmp_path):
    db_path = str(tmp_path / "llm_telemetry_test.db")
    conn = connect_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_model_catalog (
            provider TEXT NOT NULL,
            model_id TEXT NOT NULL,
            name TEXT,
            context_length INTEGER,
            input_cost_per_token REAL,
            output_cost_per_token REAL,
            cache_read_cost_per_token REAL,
            raw_pricing TEXT,
            capabilities TEXT,
            source_url TEXT,
            discovered_at TEXT,
            last_seen_at TEXT,
            enabled INTEGER DEFAULT 1,
            PRIMARY KEY (provider, model_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_request_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_id TEXT,
            conversation_id TEXT,
            provider TEXT,
            model TEXT,
            routing_reason TEXT,
            task_type TEXT,
            complexity TEXT,
            success INTEGER,
            error_message TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            prompt_cache_hit_tokens INTEGER,
            prompt_cache_miss_tokens INTEGER,
            reasoning_tokens INTEGER,
            estimated_cost_usd REAL,
            first_token_latency_ms REAL,
            total_latency_ms REAL
        )
        """
    )
    conn.commit()
    conn.close()
    return LLMTelemetryStore(db_path)


class TestUpsertModels:
    def test_insert_new(self, tmp_path):
        store = _store(tmp_path)
        models = [
            {
                "provider": "openai",
                "model_id": "gpt-4",
                "name": "GPT-4",
                "context_length": 8192,
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
            }
        ]
        count = store.upsert_models(models)
        assert count == 1
        model = store.get_model("openai", "gpt-4")
        assert model is not None
        assert model["name"] == "GPT-4"

    def test_update_existing(self, tmp_path):
        store = _store(tmp_path)
        models = [
            {
                "provider": "openai",
                "model_id": "gpt-4",
                "name": "GPT-4",
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
            }
        ]
        store.upsert_models(models)
        models[0]["name"] = "GPT-4 Turbo"
        models[0]["input_cost_per_token"] = 0.00001
        store.upsert_models(models)
        model = store.get_model("openai", "gpt-4")
        assert model["name"] == "GPT-4 Turbo"
        assert model["input_cost_per_token"] == 0.00001

    def test_empty_list(self, tmp_path):
        store = _store(tmp_path)
        count = store.upsert_models([])
        assert count == 0


class TestListModels:
    def test_all_enabled(self, tmp_path):
        store = _store(tmp_path)
        store.upsert_models([
            {"provider": "openai", "model_id": "gpt-4", "name": "GPT-4", "input_cost_per_token": 0.00003, "output_cost_per_token": 0.00006},
            {"provider": "openai", "model_id": "gpt-3.5", "name": "GPT-3.5", "input_cost_per_token": 0.000001, "output_cost_per_token": 0.000002},
        ])
        models = store.list_models()
        assert len(models) == 2

    def test_filter_by_provider(self, tmp_path):
        store = _store(tmp_path)
        store.upsert_models([
            {"provider": "openai", "model_id": "gpt-4", "name": "GPT-4", "input_cost_per_token": 0.00003, "output_cost_per_token": 0.00006},
            {"provider": "anthropic", "model_id": "claude-3", "name": "Claude 3", "input_cost_per_token": 0.000008, "output_cost_per_token": 0.000024},
        ])
        models = store.list_models(provider="openai")
        assert len(models) == 1
        assert models[0]["provider"] == "openai"

    def test_include_disabled(self, tmp_path):
        store = _store(tmp_path)
        store.upsert_models([
            {"provider": "openai", "model_id": "gpt-4", "name": "GPT-4", "input_cost_per_token": 0.00003, "output_cost_per_token": 0.00006},
        ])
        conn = connect_db(store.db_path)
        conn.execute("UPDATE llm_model_catalog SET enabled = 0")
        conn.commit()
        conn.close()
        models = store.list_models(enabled_only=False)
        assert len(models) == 1


class TestGetModel:
    def test_found(self, tmp_path):
        store = _store(tmp_path)
        store.upsert_models([
            {"provider": "openai", "model_id": "gpt-4", "name": "GPT-4", "input_cost_per_token": 0.00003, "output_cost_per_token": 0.00006},
        ])
        model = store.get_model("openai", "gpt-4")
        assert model is not None
        assert model["provider"] == "openai"
        assert model["model_id"] == "gpt-4"

    def test_not_found(self, tmp_path):
        store = _store(tmp_path)
        model = store.get_model("openai", "nonexistent")
        assert model is None


class TestRecordTelemetry:
    def test_success(self, tmp_path):
        store = _store(tmp_path)
        store.record_telemetry(
            user_id="u1", conversation_id="c1", provider="openai", model="gpt-4",
            route=None, success=True,
            usage={"prompt_tokens": 100, "completion_tokens": 50},
            first_token_latency_ms=120.0, total_latency_ms=500.0,
        )
        conn = connect_db(store.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM llm_request_telemetry")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1

    def test_error(self, tmp_path):
        store = _store(tmp_path)
        store.record_telemetry(
            user_id="u1", conversation_id="c1", provider="openai", model="gpt-4",
            route=None, success=False, error_message="API timeout",
            total_latency_ms=30000.0,
        )
        conn = connect_db(store.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT error_message FROM llm_request_telemetry WHERE success = 0")
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert "timeout" in row[0]


class TestGetTelemetryStats:
    def test_aggregation(self, tmp_path):
        store = _store(tmp_path)
        now = datetime.now().isoformat()
        conn = connect_db(store.db_path)
        for _ in range(3):
            conn.execute(
                """
                INSERT INTO llm_request_telemetry
                (timestamp, user_id, provider, model, success, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd)
                VALUES (?, ?, ?, ?, 1, 100, 50, 150, 0.001)
                """,
                (now, "u1", "openai", "gpt-4"),
            )
        conn.execute(
            """
            INSERT INTO llm_request_telemetry
            (timestamp, user_id, provider, model, success, error_message)
            VALUES (?, ?, ?, ?, 0, 'error')
            """,
            (now, "u1", "openai", "gpt-4"),
        )
        conn.commit()
        conn.close()
        stats = store.get_telemetry_stats(hours=24)
        assert len(stats["by_user_model"]) == 1
        entry = stats["by_user_model"][0]
        assert entry["request_count"] == 4
        assert entry["error_count"] == 1
