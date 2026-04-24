"""
Centralized settings for DevSynapse AI.
"""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class AppSettings(BaseSettings):
    """Application settings loaded from environment or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DevSynapse AI"
    app_version: str = "0.2.0"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_debug: bool = True
    api_base_url: Optional[str] = None

    deepseek_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    openai_model: str = "gpt-4-turbo-preview"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1500
    llm_request_timeout: int = 12
    deepseek_flash_input_cache_hit_price_usd_per_million: float = 0.028
    deepseek_flash_input_cache_miss_price_usd_per_million: float = 0.14
    deepseek_flash_output_price_usd_per_million: float = 0.28
    deepseek_pro_input_cache_hit_price_usd_per_million: float = 0.145
    deepseek_pro_input_cache_miss_price_usd_per_million: float = 1.74
    deepseek_pro_output_price_usd_per_million: float = 3.48

    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", "") or secrets.token_urlsafe(48)
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    memory_db_path: Path = DATA_DIR / "devsynapse_memory.db"
    monitoring_db_path: Path = DATA_DIR / "devsynapse_monitoring.db"
    conversation_history_limit: int = 20

    opencode_timeout: int = 30
    opencode_max_output: int = 10000
    opencode_max_file_size: int = 10 * 1024 * 1024
    opencode_backup_enabled: bool = True
    opencode_backup_suffix: str = ".devsynapse_backup"
    default_execution_cwd: Path = Path("/home/irving")

    max_edit_size: int = 1 * 1024 * 1024
    max_write_size: int = 5 * 1024 * 1024

    log_level: str = "INFO"
    log_file: Path = LOGS_DIR / "devsynapse.log"

    default_admin_username: str = "admin"
    default_admin_password: str = "devsynapse2026"
    default_user_username: str = "irving"
    default_user_password: str = "n1ghthill2026"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


_settings = get_settings()

# Legacy module-level aliases kept for compatibility with the existing code/tests.
DEEPSEEK_API_KEY: Optional[str] = _settings.deepseek_api_key
OPENAI_API_KEY: Optional[str] = _settings.openai_api_key
DEEPSEEK_MODEL = _settings.deepseek_model
DEEPSEEK_BASE_URL = _settings.deepseek_base_url
OPENAI_MODEL = _settings.openai_model
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

ALLOWED_DIRECTORIES = [
    "/home/irving/ruas/repos",
    "/home/irving",
    "/tmp",
    "/var/tmp",
]

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

KNOWN_PROJECTS = {
    "botassist-whatsapp": {
        "path": "/home/irving/ruas/repos/botassist-whatsapp",
        "type": "electron-app",
        "priority": "high",
    },
    "botassist-site": {
        "path": "/home/irving/ruas/repos/botassist-site",
        "type": "nextjs-site",
        "priority": "medium",
    },
    "devsynapse-ai": {
        "path": "/home/irving/ruas/repos/devsynapse-ai",
        "type": "ai-assistant",
        "priority": "high",
    },
}

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
