"""
Pydantic schemas shared by the API routes.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class AuthResponse(BaseModel):
    access_token: str
    token: str
    token_type: str = "bearer"
    user: Dict


class TokenVerifyResponse(BaseModel):
    valid: bool
    user: Optional[Dict] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    execute_command: bool = Field(default=False)
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=120)


class LLMUsageResponse(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    reasoning_tokens: int = 0
    estimated_cost_usd: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    success: bool = True
    opencode_command: Optional[str] = None
    command: Optional[str] = None
    requires_confirmation: bool = Field(default=False)
    llm_usage: Optional[LLMUsageResponse] = None
    project_name: Optional[str] = None


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str
    preview: str
    updated_at: str
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    project_name: Optional[str] = None


class ConversationListResponse(BaseModel):
    conversations: List[ConversationSummaryResponse]


class ConversationRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class ConversationMutationResponse(BaseModel):
    success: bool
    conversation_id: str


class CommandExecutionRequest(BaseModel):
    conversation_id: str
    command: str
    confirm: bool = Field(default=True)
    project_name: Optional[str] = None


class CommandExecutionResponse(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None
    status: str
    reason_code: Optional[str] = None
    project_name: Optional[str] = None


class FeedbackRequest(BaseModel):
    conversation_id: str
    feedback: str
    score: Optional[int] = Field(None, ge=1, le=5)


class FeedbackResponse(BaseModel):
    success: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    memory_entries: int
    deepseek_configured: bool


class DashboardStats(BaseModel):
    system_health: Dict
    command_stats: Dict
    api_stats: Dict
    llm_usage: Dict
    active_alerts: List[Dict]


class SettingsResponse(BaseModel):
    deepseek_api_key: bool | str
    deepseek_model: str
    temperature: float
    max_tokens: int
    conversation_history_limit: int
    llm_daily_budget_usd: float
    llm_monthly_budget_usd: float
    llm_budget_warning_threshold_pct: float
    llm_budget_critical_threshold_pct: float
    api_host: str
    api_port: int
    project_mutation_allowlist: List[str]


class SettingsUpdateRequest(BaseModel):
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000)
    conversation_history_limit: Optional[int] = Field(default=None, ge=1, le=100)
    llm_daily_budget_usd: Optional[float] = Field(default=None, ge=0)
    llm_monthly_budget_usd: Optional[float] = Field(default=None, ge=0)
    llm_budget_warning_threshold_pct: Optional[float] = Field(default=None, ge=0, le=100)
    llm_budget_critical_threshold_pct: Optional[float] = Field(default=None, ge=0, le=200)


class ProjectSummaryResponse(BaseModel):
    name: str
    type: str
    priority: str
    last_accessed: str
    access_count: int


class ProjectResponse(ProjectSummaryResponse):
    path: str


class ProjectListResponse(BaseModel):
    projects: List[ProjectSummaryResponse]
    count: int


class AdminProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    count: int


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    path: str = Field(..., min_length=1, max_length=500)
    type: Optional[str] = Field(default=None, max_length=80)
    priority: Optional[str] = Field(default=None, max_length=40)


class AdminUserSummary(BaseModel):
    username: str
    role: str
    is_active: bool
    project_mutation_allowlist: List[str]


class AdminUsersResponse(BaseModel):
    users: List[AdminUserSummary]


class AdminUserPermissionsUpdateRequest(BaseModel):
    project_mutation_allowlist: List[str]


class AdminAuditLogEntry(BaseModel):
    id: int
    actor_username: str
    target_username: Optional[str] = None
    action: str
    details: Dict
    created_at: str


class AdminAuditLogsResponse(BaseModel):
    logs: List[AdminAuditLogEntry]
