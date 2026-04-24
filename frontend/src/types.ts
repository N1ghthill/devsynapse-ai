export type CommandExecutionStatus =
  | 'proposed'
  | 'running'
  | 'success'
  | 'blocked'
  | 'failed';

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
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  success: boolean;
  command?: string;
  opencode_command?: string;
  requires_confirmation?: boolean;
  llm_usage?: TokenUsage | null;
}

export interface CommandResult {
  success: boolean;
  message: string;
  output?: string;
  status: 'success' | 'blocked' | 'failed';
  reason_code?: string;
  project_name?: string | null;
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
      reasoning_tokens: number;
      estimated_cost_usd: number;
    };
    by_day: Array<{
      day: string;
      request_count: number;
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
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

export interface SettingsData {
  deepseek_api_key: boolean | string;
  deepseek_model: string;
  openai_model: string;
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
