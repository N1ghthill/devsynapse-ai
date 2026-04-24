"""
Schema migrations for DevSynapse SQLite databases.
"""

from core.db import Migration, MigrationManager

MEMORY_MIGRATIONS = (
    Migration(
        version=1,
        description="Initial memory schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                timestamp TEXT,
                user_message TEXT,
                ai_response TEXT,
                opencode_command TEXT,
                command_executed INTEGER DEFAULT 0,
                execution_result TEXT,
                user_feedback TEXT,
                feedback_score INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT,
                source TEXT,
                confidence REAL DEFAULT 1.0,
                last_updated TEXT,
                evidence_count INTEGER DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS projects (
                name TEXT PRIMARY KEY,
                path TEXT,
                type TEXT,
                priority TEXT,
                last_accessed TEXT,
                access_count INTEGER DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_hash TEXT,
                decision TEXT,
                outcome TEXT,
                user_rating INTEGER,
                learned_lesson TEXT,
                timestamp TEXT
            )
            """,
        ),
    ),
    Migration(
        version=2,
        description="Users and runtime settings",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=3,
        description="Per-user project permissions",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS project_permissions (
                username TEXT NOT NULL,
                project_name TEXT NOT NULL,
                permission TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (username, project_name, permission)
            )
            """,
        ),
    ),
    Migration(
        version=4,
        description="Admin audit log",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_username TEXT NOT NULL,
                target_username TEXT,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=5,
        description="Command execution metadata",
        statements=(
            """
            ALTER TABLE conversations ADD COLUMN execution_output TEXT
            """,
            """
            ALTER TABLE conversations ADD COLUMN execution_status TEXT
            """,
            """
            ALTER TABLE conversations ADD COLUMN execution_reason_code TEXT
            """,
        ),
    ),
    Migration(
        version=6,
        description="Conversation titles",
        statements=(
            """
            ALTER TABLE conversations ADD COLUMN conversation_title TEXT
            """,
        ),
    ),
    Migration(
        version=7,
        description="LLM usage telemetry",
        statements=(
            """
            ALTER TABLE conversations ADD COLUMN llm_provider TEXT
            """,
            """
            ALTER TABLE conversations ADD COLUMN llm_model TEXT
            """,
            """
            ALTER TABLE conversations ADD COLUMN prompt_tokens INTEGER
            """,
            """
            ALTER TABLE conversations ADD COLUMN completion_tokens INTEGER
            """,
            """
            ALTER TABLE conversations ADD COLUMN total_tokens INTEGER
            """,
            """
            ALTER TABLE conversations ADD COLUMN prompt_cache_hit_tokens INTEGER
            """,
            """
            ALTER TABLE conversations ADD COLUMN prompt_cache_miss_tokens INTEGER
            """,
            """
            ALTER TABLE conversations ADD COLUMN reasoning_tokens INTEGER
            """,
            """
            ALTER TABLE conversations ADD COLUMN estimated_cost_usd REAL
            """,
        ),
    ),
    Migration(
        version=8,
        description="Explicit conversation project attribution",
        statements=(
            """
            ALTER TABLE conversations ADD COLUMN conversation_project_name TEXT
            """,
        ),
    ),
)


MONITORING_MIGRATIONS = (
    Migration(
        version=1,
        description="Initial monitoring schema",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS command_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                command_type TEXT,
                command_text TEXT,
                success INTEGER,
                execution_time REAL,
                user_id TEXT,
                project_name TEXT,
                error_message TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                endpoint TEXT,
                method TEXT,
                status_code INTEGER,
                response_time REAL,
                user_id TEXT,
                ip_address TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                metric_name TEXT,
                metric_value REAL,
                tags TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                resolved INTEGER DEFAULT 0,
                resolved_at TEXT
            )
            """,
        ),
    ),
)


def build_memory_migration_manager(db_path):
    return MigrationManager(
        db_path=db_path,
        schema_name="memory",
        migrations=MEMORY_MIGRATIONS,
    )


def build_monitoring_migration_manager(db_path):
    return MigrationManager(
        db_path=db_path,
        schema_name="monitoring",
        migrations=MONITORING_MIGRATIONS,
    )


def get_migration_managers(memory_db_path, monitoring_db_path):
    return (
        build_memory_migration_manager(memory_db_path),
        build_monitoring_migration_manager(monitoring_db_path),
    )


def apply_all_migrations(memory_db_path, monitoring_db_path) -> dict:
    return {
        manager.schema_name: manager.apply_migrations()
        for manager in get_migration_managers(memory_db_path, monitoring_db_path)
    }


def get_all_migration_status(memory_db_path, monitoring_db_path) -> list[dict]:
    return [
        manager.status()
        for manager in get_migration_managers(memory_db_path, monitoring_db_path)
    ]
