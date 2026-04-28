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
    Migration(
        version=9,
        description="Agent learning and route decision telemetry",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS agent_learning (
                task_signature TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                preferred_model TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                learned_reason TEXT,
                evidence TEXT,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_route_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                timestamp TEXT NOT NULL,
                task_signature TEXT NOT NULL,
                task_type TEXT NOT NULL,
                complexity TEXT NOT NULL,
                selected_model TEXT NOT NULL,
                fallback_model TEXT,
                budget_mode TEXT,
                routing_reason TEXT,
                learned_preference TEXT,
                learned_confidence REAL NOT NULL DEFAULT 0.0,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                cache_hit_rate_pct REAL,
                estimated_cost_usd REAL,
                project_name TEXT,
                opencode_command TEXT
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_agent_route_decisions_signature
            ON agent_route_decisions(task_signature, timestamp)
            """,
        ),
    ),
    Migration(
        version=10,
        description="Project memories, skills, and learning nudge events",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS project_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                memory_type TEXT NOT NULL DEFAULT 'fact',
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                confidence_score REAL NOT NULL DEFAULT 0.6,
                memory_decay_score REAL NOT NULL DEFAULT 0.02,
                evidence_count INTEGER NOT NULL DEFAULT 1,
                access_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_accessed_at TEXT,
                tags TEXT,
                metadata TEXT,
                UNIQUE(project_name, memory_type, content)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_project_memories_scope
            ON project_memories(project_name, memory_type, confidence_score)
            """,
            """
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                description TEXT NOT NULL,
                project_name TEXT,
                scope TEXT NOT NULL DEFAULT 'global',
                path TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                use_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,
                metadata TEXT,
                UNIQUE(scope, project_name, slug)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_skills_lookup
            ON skills(scope, project_name, category, is_active)
            """,
            """
            CREATE TABLE IF NOT EXISTS skill_activations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_slug TEXT NOT NULL,
                project_name TEXT,
                conversation_id TEXT,
                reason TEXT,
                activated_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_skill_activations_slug
            ON skill_activations(skill_slug, activated_at)
            """,
            """
            CREATE TABLE IF NOT EXISTS learning_nudge_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                project_name TEXT,
                nudge_type TEXT NOT NULL,
                trigger_reason TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_learning_nudge_events_scope
            ON learning_nudge_events(project_name, nudge_type, created_at)
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
