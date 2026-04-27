"""
Centralized settings for DevSynapse AI.
"""

from __future__ import annotations

import json
import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


def _expand_env_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _xdg_dir(env_name: str, default_relative: str) -> Path:
    base = os.getenv(env_name)
    if base:
        return _expand_env_path(base)
    return Path.home() / default_relative


def _runtime_home() -> Optional[Path]:
    value = os.getenv("DEVSYNAPSE_HOME")
    return _expand_env_path(value) if value else None


def parse_csv_or_json_list(value: str) -> List[str]:
    value = value.strip()
    if not value:
        return ["*"]
    if value.startswith("["):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()] or ["*"]
        return ["*"]
    return [item.strip() for item in value.split(",") if item.strip()] or ["*"]


def _default_config_dir() -> Path:
    runtime_home = _runtime_home()
    if runtime_home is not None:
        return runtime_home / "config"
    return _xdg_dir("XDG_CONFIG_HOME", ".config") / "devsynapse-ai"


def _default_data_dir() -> Path:
    runtime_home = _runtime_home()
    if runtime_home is not None:
        return runtime_home / "data"
    return _xdg_dir("XDG_DATA_HOME", ".local/share") / "devsynapse-ai" / "data"


def _default_logs_dir() -> Path:
    runtime_home = _runtime_home()
    if runtime_home is not None:
        return runtime_home / "logs"
    return _xdg_dir("XDG_STATE_HOME", ".local/state") / "devsynapse-ai" / "logs"


CONFIG_DIR = _expand_env_path(os.getenv("DEVSYNAPSE_CONFIG_DIR", _default_config_dir()))
CONFIG_FILE = _expand_env_path(os.getenv("DEVSYNAPSE_CONFIG_FILE", CONFIG_DIR / ".env"))
DATA_DIR = _expand_env_path(os.getenv("DEVSYNAPSE_DATA_DIR", _default_data_dir()))
LOGS_DIR = _expand_env_path(os.getenv("DEVSYNAPSE_LOGS_DIR", _default_logs_dir()))

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _default_workspace_root() -> Path:
    return Path.home()


def _default_repos_root() -> Path:
    home = Path.home()
    candidate = home / "repos"
    if candidate.is_dir():
        return candidate
    for entry in home.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            nested = entry / "repos"
            if nested.is_dir():
                return nested
    return home


class AppSettings(BaseSettings):
    """Application settings loaded from environment or the per-user runtime config."""

    model_config = SettingsConfigDict(
        env_file=CONFIG_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DevSynapse AI"
    app_version: str = "0.5.1"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_debug: bool = True
    api_base_url: Optional[str] = None
    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com/beta"
    deepseek_flash_model: str = "deepseek-v4-flash"
    deepseek_pro_model: str = "deepseek-v4-pro"
    deepseek_reasoner_model: str = "deepseek-reasoner"
    deepseek_reasoning_effort: str = "high"
    deepseek_thinking_enabled: bool = True
    llm_model_routing_enabled: bool = True
    llm_auto_economy_enabled: bool = True
    llm_cache_hit_warning_threshold_pct: float = 70.0
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1500
    llm_request_timeout: int = 12
    deepseek_flash_input_cache_hit_price_usd_per_million: float = 0.0028
    deepseek_flash_input_cache_miss_price_usd_per_million: float = 0.14
    deepseek_flash_output_price_usd_per_million: float = 0.28
    deepseek_pro_input_cache_hit_price_usd_per_million: float = 0.003625
    deepseek_pro_input_cache_miss_price_usd_per_million: float = 0.435
    deepseek_pro_output_price_usd_per_million: float = 0.87
    llm_daily_budget_usd: float = 1.0
    llm_monthly_budget_usd: float = 20.0
    llm_budget_warning_threshold_pct: float = 80.0
    llm_budget_critical_threshold_pct: float = 100.0

    dev_workspace_root: Path = Field(default_factory=_default_workspace_root)
    dev_repos_root: Path = Field(default_factory=_default_repos_root)
    dev_projects_json: str = ""

    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", "") or secrets.token_urlsafe(48)
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    memory_db_path: Path = Field(default_factory=lambda: DATA_DIR / "devsynapse_memory.db")
    monitoring_db_path: Path = Field(
        default_factory=lambda: DATA_DIR / "devsynapse_monitoring.db"
    )
    conversation_history_limit: int = 20

    opencode_timeout: int = 30
    opencode_max_output: int = 10000
    opencode_max_file_size: int = 10 * 1024 * 1024
    opencode_backup_enabled: bool = True
    opencode_backup_suffix: str = ".devsynapse_backup"
    default_execution_cwd: Path = Field(default_factory=_default_workspace_root)

    max_edit_size: int = 1 * 1024 * 1024
    max_write_size: int = 5 * 1024 * 1024

    log_level: str = "INFO"
    log_file: Path = Field(default_factory=lambda: LOGS_DIR / "devsynapse.log")

    default_admin_username: str = "admin"
    default_admin_password: str = "admin"
    default_user_username: str = ""
    default_user_password: str = ""

    def get_cors_allowed_origins(self) -> List[str]:
        return parse_csv_or_json_list(self.cors_allowed_origins)

    def build_allowed_directories(self) -> List[str]:
        roots = {str(self.dev_repos_root.resolve()), str(self.dev_workspace_root.resolve())}
        roots.add("/tmp")
        roots.add("/var/tmp")
        return sorted(roots)

    def build_known_projects(self) -> Dict[str, Dict[str, str]]:
        projects: Dict[str, Dict[str, str]] = {}

        if self.dev_projects_json:
            try:
                parsed = json.loads(self.dev_projects_json)
                if isinstance(parsed, dict):
                    projects.update(parsed)
            except (json.JSONDecodeError, TypeError):
                pass

        if not projects:
            repos = self.dev_repos_root
            if repos.is_dir():
                for entry in sorted(repos.iterdir()):
                    if entry.is_dir() and not entry.name.startswith("."):
                        if not (entry / ".git").is_dir():
                            continue
                        projects[entry.name] = {
                            "path": str(entry),
                            "type": "project",
                            "priority": "medium",
                        }

        return projects


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


_settings = get_settings()

# Legacy module-level aliases kept for compatibility with the existing code/tests.
DEEPSEEK_API_KEY: Optional[str] = _settings.deepseek_api_key
DEEPSEEK_MODEL = _settings.deepseek_model
DEEPSEEK_BASE_URL = _settings.deepseek_base_url
DEEPSEEK_FLASH_MODEL = _settings.deepseek_flash_model
DEEPSEEK_PRO_MODEL = _settings.deepseek_pro_model
DEEPSEEK_REASONER_MODEL = _settings.deepseek_reasoner_model
DEEPSEEK_REASONING_EFFORT = _settings.deepseek_reasoning_effort
DEEPSEEK_THINKING_ENABLED = _settings.deepseek_thinking_enabled
LLM_MODEL_ROUTING_ENABLED = _settings.llm_model_routing_enabled
LLM_AUTO_ECONOMY_ENABLED = _settings.llm_auto_economy_enabled
LLM_CACHE_HIT_WARNING_THRESHOLD_PCT = _settings.llm_cache_hit_warning_threshold_pct
LLM_REQUEST_TIMEOUT = _settings.llm_request_timeout
DEEPSEEK_FLASH_INPUT_CACHE_HIT_PRICE_USD_PER_MILLION = (
    _settings.deepseek_flash_input_cache_hit_price_usd_per_million
)
DEEPSEEK_FLASH_INPUT_CACHE_MISS_PRICE_USD_PER_MILLION = (
    _settings.deepseek_flash_input_cache_miss_price_usd_per_million
)
DEEPSEEK_FLASH_OUTPUT_PRICE_USD_PER_MILLION = (
    _settings.deepseek_flash_output_price_usd_per_million
)
DEEPSEEK_PRO_INPUT_CACHE_HIT_PRICE_USD_PER_MILLION = (
    _settings.deepseek_pro_input_cache_hit_price_usd_per_million
)
DEEPSEEK_PRO_INPUT_CACHE_MISS_PRICE_USD_PER_MILLION = (
    _settings.deepseek_pro_input_cache_miss_price_usd_per_million
)
DEEPSEEK_PRO_OUTPUT_PRICE_USD_PER_MILLION = (
    _settings.deepseek_pro_output_price_usd_per_million
)
MEMORY_DB_PATH = _settings.memory_db_path
MONITORING_DB_PATH = _settings.monitoring_db_path
VECTOR_DB_PATH = DATA_DIR / "chroma_db"
CONVERSATION_HISTORY_LIMIT = _settings.conversation_history_limit
OPENCODE_TIMEOUT = _settings.opencode_timeout
OPENCODE_MAX_OUTPUT = _settings.opencode_max_output
OPENCODE_MAX_FILE_SIZE = _settings.opencode_max_file_size
OPENCODE_BACKUP_ENABLED = _settings.opencode_backup_enabled
OPENCODE_BACKUP_SUFFIX = _settings.opencode_backup_suffix
MAX_EDIT_SIZE = _settings.max_edit_size
MAX_WRITE_SIZE = _settings.max_write_size
API_HOST = _settings.api_host
API_PORT = _settings.api_port
API_DEBUG = _settings.api_debug

ALLOWED_COMMANDS = [
    "bash",
    "read",
    "glob",
    "grep",
    "edit",
    "write",
]

ALLOWED_BASH_COMMANDS = [
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "git",
    "npm",
    "node",
    "python",
    "python3",
    "echo",
    "touch",
    "mkdir",
    "cp",
    "mv",
    "rm",
    "chmod",
    "df",
    "du",
    "ps",
    "top",
    "kill",
    "curl",
    "wget",
    "tar",
    "gzip",
    "gunzip",
    "zip",
    "unzip",
]

BLACKLISTED_PATTERNS = [
    "rm -rf",
    "format c:",
    "dd if=",
    "mkfs",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "> /dev/sda",
    "> /dev/sdb",
    "mkfs.ext",
    "fdisk",
    ":(){:|:&};:",
    "fork bomb patterns",
]

ALLOWED_DIRECTORIES = _settings.build_allowed_directories()

ALLOWED_FILE_EXTENSIONS = [
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".md",
    ".txt",
    ".csv",
    ".xml",
    ".sql",
    ".sh",
    ".bash",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".dart",
]

READ_ONLY_COMMANDS = [
    "read",
    "glob",
    "grep",
]

USER_BASH_COMMANDS = [
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "git",
    "npm",
    "node",
    "python",
    "python3",
    "echo",
    "df",
    "du",
    "ps",
    "top",
    "curl",
    "wget",
    "tar",
    "gzip",
    "gunzip",
    "zip",
    "unzip",
]

ADMIN_ONLY_COMMANDS = [
    "edit",
    "write",
]

ADMIN_ONLY_BASH_COMMANDS = [
    "touch",
    "mkdir",
    "cp",
    "mv",
    "rm",
    "chmod",
    "kill",
]

KNOWN_PROJECTS: Dict[str, Dict[str, str]] = _settings.build_known_projects()

DEFAULT_PREFERENCES = {
    "coding_style": "clean_simple",
    "cost_preference": "low_cost_first",
    "communication_style": "direct_conversational",
    "risk_tolerance": "medium",
    "detail_level": "balanced",
}


def validate_config():
    """Validate baseline runtime configuration."""

    errors = []

    if not MEMORY_DB_PATH.parent.exists():
        errors.append(f"Diretório de dados não existe: {MEMORY_DB_PATH.parent}")

    if not LOGS_DIR.exists():
        errors.append(f"Diretório de logs não existe: {LOGS_DIR}")

    return errors


if __name__ == "__main__":
    validation_errors = validate_config()
    if validation_errors:
        print("❌ Erros de configuração:")
        for error in validation_errors:
            print(f"  - {error}")
    else:
        print("✅ Configuração válida")
