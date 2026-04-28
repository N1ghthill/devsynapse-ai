export type CommandExecutionStatus =
  | 'proposed'
  | 'running'
  | 'success'
  | 'blocked'
  | 'failed';

export interface ProjectInfo {
  name: string;
  path?: string;
  type: string;
  priority: string;
  last_accessed: string;
  access_count: number;
}

export interface TokenUsage {
  provider?: string | null;
  model?: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  prompt_cache_hit_tokens: number;
  prompt_cache_miss_tokens: number;
  reasoning_tokens: number;
  estimated_cost_usd?: number | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  command?: string;
  commandStatus?: CommandExecutionStatus;
  commandResult?: string;
  reasonCode?: string | null;
  commandNote?: string;
  commandInterpretation?: string | null;
  reasoningContent?: string;
  projectName?: string | null;
  tokenUsage?: TokenUsage | null;
  metadata?: Record<string, unknown>;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  preview: string;
  updated_at: string;
  total_tokens: number;
  estimated_cost_usd: number;
  project_name?: string | null;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  project_name?: string;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  success: boolean;
  command?: string;
  opencode_command?: string;
  requires_confirmation?: boolean;
  llm_usage?: TokenUsage | null;
  project_name?: string | null;
}

export interface CommandResult {
  success: boolean;
  message: string;
  output?: string;
  status: 'success' | 'blocked' | 'failed';
  reason_code?: string;
  project_name?: string | null;
  interpretation?: string | null;
}

export interface ExecuteCommandRequest {
  conversation_id: string;
  command: string;
  confirm?: boolean;
  project_name?: string;
}

export interface DashboardStats {
  command_stats: {
    totals: { total: number; successful: number; failed: number };
    by_type: Array<{ command_type: string; count: number }>;
  };
  api_stats: {
    totals: { total_requests: number; avg_response_time: number };
    by_endpoint: Array<{ endpoint: string; request_count: number }>;
  };
  llm_usage: {
    totals: {
      request_count: number;
      conversation_count: number;
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
      prompt_cache_hit_tokens: number;
      prompt_cache_miss_tokens: number;
      cache_hit_rate_pct: number;
      reasoning_tokens: number;
      estimated_cost_usd: number;
    };
    by_day: Array<{
      day: string;
      request_count: number;
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
      prompt_cache_hit_tokens: number;
      prompt_cache_miss_tokens: number;
      cache_hit_rate_pct: number;
      estimated_cost_usd: number;
    }>;
    by_project: Array<{
      project_name: string;
      request_count: number;
      total_tokens: number;
      estimated_cost_usd: number;
    }>;
    budget: {
      overall_status: 'disabled' | 'healthy' | 'warning' | 'critical';
      daily: BudgetWindowStatus;
      monthly: BudgetWindowStatus;
    };
    agent_learning: {
      learned_patterns: number;
      success_signals: number;
      failure_signals: number;
      avg_confidence: number;
      by_model: Array<{ selected_model: string; count: number }>;
    };
    knowledge?: KnowledgeStats;
    timeframe_hours: number;
  };
  system_health: {
    overall_status: string;
    command_error_rate: number;
    api_error_rate: number;
    active_alerts: number;
  };
  active_alerts: Array<{
    id: number;
    alert_type: string;
    severity: string;
    message: string;
    timestamp: string;
  }>;
}

export interface BudgetWindowStatus {
  window: 'daily' | 'monthly';
  budget_usd: number;
  actual_cost_usd: number;
  usage_pct: number;
  warning_threshold_pct: number;
  critical_threshold_pct: number;
  warning_threshold_cost_usd: number;
  critical_threshold_cost_usd: number;
  level: 'disabled' | 'healthy' | 'warning' | 'critical';
}

export interface AuthState {
  token: string | null;
  user: { username: string; role: string } | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface BootstrapStatus {
  requires_setup: boolean;
  reasons: string[];
  admin_password_required: boolean;
  deepseek_api_key_configured: boolean;
  workspace_configured: boolean;
  default_admin_username: string;
  suggested_workspace_root: string;
  suggested_repos_root: string;
  workspace_root?: string | null;
  repos_root?: string | null;
  config_path: string;
  data_dir: string;
  logs_dir: string;
  discovered_project_count: number;
}

export interface BootstrapCompleteRequest {
  admin_password?: string | null;
  deepseek_api_key?: string | null;
  repos_root: string;
  workspace_root?: string | null;
  register_discovered_projects: boolean;
}

export interface BootstrapCompleteResponse {
  access_token?: string | null;
  token?: string | null;
  user?: { username: string; role: string } | null;
  status: BootstrapStatus;
  registered_projects: Array<{
    name: string;
    path: string;
    type: string;
    priority: string;
  }>;
}

export interface SettingsData {
  deepseek_api_key: boolean | string;
  deepseek_model: string;
  deepseek_flash_model: string;
  deepseek_pro_model: string;
  llm_model_routing_enabled: boolean;
  llm_auto_economy_enabled: boolean;
  llm_cache_hit_warning_threshold_pct: number;
  temperature: number;
  max_tokens: number;
  conversation_history_limit: number;
  llm_daily_budget_usd: number;
  llm_monthly_budget_usd: number;
  llm_budget_warning_threshold_pct: number;
  llm_budget_critical_threshold_pct: number;
  api_host: string;
  api_port: number;
  project_mutation_allowlist: string[];
}

export interface AdminUser {
  username: string;
  role: string;
  is_active: boolean;
  project_mutation_allowlist: string[];
}

export interface AdminAuditLog {
  id: number;
  actor_username: string;
  target_username: string | null;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ProjectCreateRequest {
  name: string;
  path: string;
  type?: string;
  priority?: string;
}

export interface ProjectMemory {
  id: number;
  project_name?: string | null;
  memory_type: string;
  content: string;
  source: string;
  confidence_score: number;
  memory_decay_score: number;
  effective_confidence: number;
  evidence_count: number;
  access_count: number;
  created_at: string;
  updated_at: string;
  last_accessed_at?: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface ProjectMemoryCreateRequest {
  content: string;
  project_name?: string | null;
  memory_type?: string;
  source?: string;
  confidence_score?: number;
  memory_decay_score?: number;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface SkillSummary {
  id: number;
  name: string;
  slug: string;
  category: string;
  description: string;
  project_name?: string | null;
  scope: string;
  path: string;
  is_active: boolean;
  use_count: number;
  created_at: string;
  updated_at: string;
  last_used_at?: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface SkillDetail extends SkillSummary {
  content: string;
  body: string;
}

export interface SkillCreateRequest {
  name: string;
  description: string;
  body: string;
  category?: string;
  project_name?: string | null;
  tags?: string[];
  replace?: boolean;
}

export interface KnowledgeStats {
  memories: {
    total_memories: number;
    avg_confidence: number;
    evidence_count: number;
    access_count: number;
    by_type: Array<{ memory_type: string; count: number }>;
  };
  skills: {
    total_skills: number;
    active_skills: number;
    use_count: number;
    by_category: Array<{ category: string; count: number }>;
  };
  nudges: {
    total_events: number;
    by_status: Array<{ nudge_type: string; status: string; count: number }>;
  };
}
