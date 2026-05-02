"""
Pydantic schemas shared by the API routes.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AuthUserResponse(BaseModel):
    username: str
    role: str


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class AuthResponse(BaseModel):
    access_token: str
    token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class TokenVerifyResponse(BaseModel):
    valid: bool
    user: Optional[AuthUserResponse] = None


class BootstrapStatusResponse(BaseModel):
    requires_setup: bool
    reasons: list[str] = Field(default_factory=list)
    admin_password_required: bool
    deepseek_api_key_configured: bool
    workspace_configured: bool
    default_admin_username: str
    suggested_workspace_root: str
    suggested_repos_root: str
    workspace_root: Optional[str] = None
    repos_root: Optional[str] = None
    config_path: str
    data_dir: str
    logs_dir: str
    discovered_project_count: int = 0


class BootstrapAdminRequest(BaseModel):
    admin_password: Optional[str] = Field(default=None, min_length=8, max_length=100)
    deepseek_api_key: Optional[str] = Field(default=None, min_length=1, max_length=300)
    repos_root: str = Field(..., min_length=1, max_length=500)
    workspace_root: Optional[str] = Field(default=None, min_length=1, max_length=500)
    register_discovered_projects: bool = True


class BootstrapProjectResponse(BaseModel):
    name: str
    path: str
    type: str
    priority: str


class BootstrapCompleteResponse(BaseModel):
    access_token: Optional[str] = None
    token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[AuthUserResponse] = None
    status: BootstrapStatusResponse
    registered_projects: list[BootstrapProjectResponse] = Field(default_factory=list)


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
    conversations: list[ConversationSummaryResponse]


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
    interpretation: Optional[str] = None


class FeedbackRequest(BaseModel):
    conversation_id: str
    feedback: str
    score: Optional[int] = Field(None, ge=1, le=5)


class FeedbackResponse(BaseModel):
    success: bool
    message: str


class ProjectMemoryCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    memory_type: str = Field(default="fact", min_length=1, max_length=40)
    source: str = Field(default="manual", min_length=1, max_length=80)
    confidence_score: float = Field(default=0.6, ge=0, le=1)
    memory_decay_score: float = Field(default=0.02, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectMemoryFeedbackRequest(BaseModel):
    delta: float = Field(..., ge=-1, le=1)
    source: str = Field(default="feedback", min_length=1, max_length=80)


class ProjectMemoryResponse(BaseModel):
    id: int
    project_name: Optional[str] = None
    memory_type: str
    content: str
    source: str
    confidence_score: float
    memory_decay_score: float
    effective_confidence: float
    evidence_count: int
    access_count: int
    created_at: str
    updated_at: str
    last_accessed_at: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectMemoryListResponse(BaseModel):
    memories: list[ProjectMemoryResponse]


class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str = Field(..., min_length=1, max_length=1024)
    body: str = Field(..., min_length=1, max_length=20000)
    category: str = Field(default="general", min_length=1, max_length=80)
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list)
    replace: bool = False


class SkillUpdateRequest(BaseModel):
    description: Optional[str] = Field(default=None, min_length=1, max_length=1024)
    body: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=120)


class SkillActivateRequest(BaseModel):
    project_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    conversation_id: Optional[str] = None
    reason: str = Field(default="manual", min_length=1, max_length=120)


class SkillSummaryResponse(BaseModel):
    id: int
    name: str
    slug: str
    category: str
    description: str
    project_name: Optional[str] = None
    scope: str
    path: str
    is_active: bool
    use_count: int
    created_at: str
    updated_at: str
    last_used_at: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillDetailResponse(SkillSummaryResponse):
    content: str
    body: str


class SkillListResponse(BaseModel):
    skills: list[SkillSummaryResponse]


class SkillDeleteResponse(BaseModel):
    success: bool
    skill: str


class KnowledgeMemoryTypeCount(BaseModel):
    memory_type: str
    count: int


class KnowledgeMemoryStatsResponse(BaseModel):
    total_memories: int
    avg_confidence: float
    evidence_count: int
    access_count: int
    by_type: list[KnowledgeMemoryTypeCount] = Field(default_factory=list)


class KnowledgeSkillCategoryCount(BaseModel):
    category: str
    count: int


class KnowledgeSkillStatsResponse(BaseModel):
    total_skills: int
    active_skills: int
    use_count: int
    by_category: list[KnowledgeSkillCategoryCount] = Field(default_factory=list)


class LearningNudgeStatusCount(BaseModel):
    nudge_type: str
    status: str
    count: int


class LearningNudgeStatsResponse(BaseModel):
    total_events: int
    by_status: list[LearningNudgeStatusCount] = Field(default_factory=list)


class KnowledgeStatsResponse(BaseModel):
    memories: KnowledgeMemoryStatsResponse
    skills: KnowledgeSkillStatsResponse
    nudges: LearningNudgeStatsResponse


class HealthResponse(BaseModel):
    status: str
    version: str
    memory_entries: int
    deepseek_configured: bool


class CommandStatsTotalsResponse(BaseModel):
    total: int
    successful: int
    blocked: int
    failed: int


class CommandTypeStatsResponse(BaseModel):
    command_type: str
    count: int
    avg_time: Optional[float] = None
    successful: int = 0
    blocked: int = 0
    failed: int = 0


class RecentCommandExecutionResponse(BaseModel):
    timestamp: str
    command_type: str
    command_text: str
    success: bool
    execution_time: float
    outcome: Literal["success", "blocked", "failed"]


class CommandStatsResponse(BaseModel):
    totals: CommandStatsTotalsResponse
    by_type: list[CommandTypeStatsResponse] = Field(default_factory=list)
    recent: list[RecentCommandExecutionResponse] = Field(default_factory=list)
    timeframe_hours: int


class ApiStatsTotalsResponse(BaseModel):
    total_requests: int
    avg_response_time: Optional[float] = None
    unique_endpoints: int = 0


class ApiEndpointStatsResponse(BaseModel):
    endpoint: str
    method: str
    request_count: int
    avg_response_time: Optional[float] = None
    error_count: int = 0


class ApiStatusCodeStatsResponse(BaseModel):
    status_code: int
    count: int


class ApiStatsResponse(BaseModel):
    totals: ApiStatsTotalsResponse
    by_endpoint: list[ApiEndpointStatsResponse] = Field(default_factory=list)
    status_codes: list[ApiStatusCodeStatsResponse] = Field(default_factory=list)
    timeframe_hours: int


class BudgetWindowStatusResponse(BaseModel):
    window: Literal["daily", "monthly"]
    budget_usd: float
    actual_cost_usd: float
    usage_pct: float
    warning_threshold_pct: float
    critical_threshold_pct: float
    warning_threshold_cost_usd: float
    critical_threshold_cost_usd: float
    level: Literal["disabled", "healthy", "warning", "critical"]


class LlmBudgetStatusResponse(BaseModel):
    overall_status: Literal["disabled", "healthy", "warning", "critical"]
    daily: BudgetWindowStatusResponse
    monthly: BudgetWindowStatusResponse


class LlmUsageTotalsResponse(BaseModel):
    request_count: int
    conversation_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_cache_hit_tokens: int
    prompt_cache_miss_tokens: int
    cache_hit_rate_pct: float
    reasoning_tokens: int
    estimated_cost_usd: float


class LlmUsageDayResponse(BaseModel):
    day: str
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_cache_hit_tokens: int
    prompt_cache_miss_tokens: int
    cache_hit_rate_pct: float
    estimated_cost_usd: float


class LlmUsageProjectResponse(BaseModel):
    project_name: str
    request_count: int
    total_tokens: int
    estimated_cost_usd: float


class AgentLearningModelCountResponse(BaseModel):
    selected_model: Optional[str] = None
    count: int


class AgentLearningStatsResponse(BaseModel):
    learned_patterns: int
    success_signals: int
    failure_signals: int
    avg_confidence: float
    by_model: list[AgentLearningModelCountResponse] = Field(default_factory=list)


class LlmUsageStatsResponse(BaseModel):
    totals: LlmUsageTotalsResponse
    by_day: list[LlmUsageDayResponse] = Field(default_factory=list)
    timeframe_hours: int
    by_project: list[LlmUsageProjectResponse] = Field(default_factory=list)
    budget: LlmBudgetStatusResponse
    agent_learning: AgentLearningStatsResponse
    knowledge: KnowledgeStatsResponse


class SystemHealthResponse(BaseModel):
    overall_status: str
    command_error_rate: float
    api_error_rate: float
    policy_blocks: int
    active_alerts: int
    informational_alerts: int
    critical_alerts: int = 0
    last_updated: Optional[str] = None


class AlertResponse(BaseModel):
    id: int
    timestamp: str
    alert_type: str
    severity: str
    message: str


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse] = Field(default_factory=list)
    resolved: bool


class AlertResolveResponse(BaseModel):
    success: bool
    message: str


class DashboardStats(BaseModel):
    system_health: SystemHealthResponse
    command_stats: CommandStatsResponse
    api_stats: ApiStatsResponse
    llm_usage: LlmUsageStatsResponse
    active_alerts: list[AlertResponse] = Field(default_factory=list)


class SettingsResponse(BaseModel):
    deepseek_api_key: bool | str
    deepseek_model: str
    deepseek_flash_model: str
    deepseek_pro_model: str
    llm_model_routing_enabled: bool
    llm_auto_economy_enabled: bool
    llm_cache_hit_warning_threshold_pct: float
    temperature: float
    max_tokens: int
    conversation_history_limit: int
    llm_daily_budget_usd: float
    llm_monthly_budget_usd: float
    llm_budget_warning_threshold_pct: float
    llm_budget_critical_threshold_pct: float
    api_host: str
    api_port: int
    project_mutation_allowlist: list[str]


class SettingsUpdateRequest(BaseModel):
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    deepseek_flash_model: Optional[str] = Field(default=None, min_length=1, max_length=120)
    deepseek_pro_model: Optional[str] = Field(default=None, min_length=1, max_length=120)
    llm_model_routing_enabled: Optional[bool] = None
    llm_auto_economy_enabled: Optional[bool] = None
    llm_cache_hit_warning_threshold_pct: Optional[float] = Field(default=None, ge=0, le=100)
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
    path_exists: bool = True


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummaryResponse]
    count: int


class AdminProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    count: int


class ProjectDeleteResponse(BaseModel):
    success: bool
    project_name: str


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    path: Optional[str] = Field(default=None, min_length=1, max_length=500)
    type: Optional[str] = Field(default=None, max_length=80)
    priority: Optional[str] = Field(default=None, max_length=40)
    create_directory: bool = False


class AdminUserSummary(BaseModel):
    username: str
    role: str
    is_active: bool
    project_mutation_allowlist: list[str]


class AdminUsersResponse(BaseModel):
    users: list[AdminUserSummary]


class AdminUserPermissionsUpdateRequest(BaseModel):
    project_mutation_allowlist: list[str]


class AdminAuditLogEntry(BaseModel):
    id: int
    actor_username: str
    target_username: Optional[str] = None
    action: str
    details: dict[str, Any]
    created_at: str


class AdminAuditLogsResponse(BaseModel):
    logs: list[AdminAuditLogEntry]
