import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import { invoke } from '@tauri-apps/api/core';
import type {
  AdminAuditLog,
  AdminUser,
  BootstrapCompleteRequest,
  BootstrapCompleteResponse,
  BootstrapStatus,
  ChatRequest,
  ChatResponse,
  CommandResult,
  ConversationSummary,
  DashboardStats,
  ExecuteCommandRequest,
  KnowledgeStats,
  Message,
  ProjectMemory,
  ProjectMemoryCreateRequest,
  ProjectCreateRequest,
  ProjectInfo,
  SettingsData,
  SkillCreateRequest,
  SkillDetail,
  SkillSummary,
  TokenUsage,
} from '../types';

type BackendStatus = {
  port: number;
  running: boolean;
  pid: number;
};

export type DesktopUpdateStatus = {
  configured: boolean;
  available: boolean;
  currentVersion: string;
  version?: string | null;
  date?: string | null;
  body?: string | null;
  endpoint?: string | null;
};

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

const DEV_API_BASE_URL = 'http://127.0.0.1:8000';

const normalizeApiBaseUrl = (value?: string): string | null => {
  const trimmed = value?.trim();
  return trimmed ? trimmed.replace(/\/$/, '') : null;
};

const configuredApiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_URL);

let cachedApiBaseUrl: string | null =
  configuredApiBaseUrl ?? null;
let apiBaseUrlPromise: Promise<string> | null = null;

const isTauriRuntime = () =>
  typeof window !== 'undefined' && Boolean(window.__TAURI_INTERNALS__);

export const isDesktopRuntime = isTauriRuntime;

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const pingBackend = async (baseUrl: string): Promise<void> => {
  const response = await fetch(`${baseUrl}/health`, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`health check returned HTTP ${response.status}`);
  }
};

const waitForTauriBackendUrl = async (): Promise<string> => {
  let lastError = 'backend has not reported a port yet';

  for (let attempt = 0; attempt < 45; attempt += 1) {
    try {
      const status = await invoke<BackendStatus>('get_backend_status');
      if (status.running && status.port > 0) {
        const baseUrl = `http://127.0.0.1:${status.port}`;
        await pingBackend(baseUrl);
        return baseUrl;
      }
      lastError = status.port > 0 ? 'backend process is not running' : lastError;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }

    await sleep(Math.min(250 + attempt * 100, 1000));
  }

  throw new Error(`Tauri backend not ready: ${lastError}`);
};

export const resolveApiBaseUrl = async (): Promise<string> => {
  if (cachedApiBaseUrl !== null) {
    return cachedApiBaseUrl;
  }

  if (apiBaseUrlPromise) {
    return apiBaseUrlPromise;
  }

  apiBaseUrlPromise = (async () => {
    if (isTauriRuntime()) {
      try {
        cachedApiBaseUrl = await waitForTauriBackendUrl();
        return cachedApiBaseUrl;
      } catch (error) {
        if (!import.meta.env.DEV) {
          throw error;
        }
      }
    }

    cachedApiBaseUrl = import.meta.env.PROD ? '' : DEV_API_BASE_URL;
    return cachedApiBaseUrl;
  })().finally(() => {
    apiBaseUrlPromise = null;
  });

  return apiBaseUrlPromise;
};

const api: AxiosInstance = axios.create({
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  config.baseURL = await resolveApiBaseUrl();

  const token = localStorage.getItem('auth_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const chatApi = {
  sendMessage: async (data: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/chat', data);
    return response.data;
  },

  getHistory: async (conversationId?: string) => {
    const params = conversationId ? { conversation_id: conversationId } : {};
    const response = await api.get('/chat/history', { params });
    return response.data;
  },

  getConversation: async (
    conversationId: string
  ): Promise<{ conversation_id: string; history: Message[]; project_name?: string | null }> => {
    const response = await api.get<{
      conversation_id: string;
      history: Message[];
      project_name?: string | null;
    }>(`/conversations/${conversationId}`);
    return response.data;
  },

  listConversations: async (): Promise<{ conversations: ConversationSummary[] }> => {
    const response = await api.get<{ conversations: ConversationSummary[] }>('/conversations');
    return response.data;
  },

  renameConversation: async (conversationId: string, title: string) => {
    const response = await api.put(`/conversations/${conversationId}`, { title });
    return response.data;
  },

  deleteConversation: async (conversationId: string) => {
    const response = await api.delete(`/conversations/${conversationId}`);
    return response.data;
  },

  exportUsageCsv: async (): Promise<string> => {
    const response = await api.get('/conversations/export/usage.csv', {
      responseType: 'text',
    });
    return response.data as string;
  },

  executeCommand: async (data: ExecuteCommandRequest): Promise<CommandResult> => {
    const response = await api.post<CommandResult>('/execute', data);
    return response.data;
  },

  sendMessageStreaming: (
    data: ChatRequest,
    onToken: (token: string) => void,
    onCommand: (command: string, autoExecute?: boolean) => void,
    onCommandStatus: (command: string, status: CommandResult['status'] | 'running') => void,
    onCommandResult: (command: string, result: CommandResult) => void,
    onReasoning: (reasoning: string) => void,
    onDone: (usage: TokenUsage | null, projectName?: string | null) => void,
    onError: (error: string) => void,
  ): AbortController => {
    const controller = new AbortController();

    void (async () => {
      const apiBaseUrl = await resolveApiBaseUrl();
      const token = localStorage.getItem('auth_token');
      const url = `${apiBaseUrl}/chat/stream`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(data),
        signal: controller.signal,
      });

      if (response.status === 401) {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
        return;
      }
      if (!response.ok) {
        const text = await response.text();
        onError(`HTTP ${response.status}: ${text}`);
        return;
      }
      const reader = response.body?.getReader();
      if (!reader) {
        onError('Stream reader not available');
        return;
      }
      const decoder = new TextDecoder();
      let buffer = '';
      let streamCompleted = false;

      const processLine = (line: string) => {
        if (!line.startsWith('data: ')) return;
        const dataStr = line.slice(6);
        try {
          const event = JSON.parse(dataStr);
          if (event.type === 'text') {
            onToken(event.content);
          } else if (event.type === 'reasoning') {
            onReasoning(event.content);
          } else if (event.type === 'command') {
            onCommand(event.command, Boolean(event.auto_execute));
          } else if (event.type === 'command_status') {
            onCommandStatus(event.command, event.status);
          } else if (event.type === 'command_result') {
            onCommandResult(event.command, {
              success: Boolean(event.success),
              message: event.message || '',
              output: event.output || undefined,
              status: event.status,
              reason_code: event.reason_code,
              project_name: event.project_name,
              interpretation: null,
            });
          } else if (event.type === 'done') {
            streamCompleted = true;
            onDone(event.usage || null, event.project_name || null);
          } else if (event.type === 'error') {
            streamCompleted = true;
            onError(event.message || 'Stream error');
          }
        } catch {
          // Skip unparseable lines
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          processLine(line);
        }
      }

      if (buffer.trim()) {
        processLine(buffer.trim());
      }
      if (!streamCompleted) {
        onError('A conexão encerrou antes da confirmação final do backend.');
      }
    })().catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err.message || 'Stream failed');
      }
    });

    return controller;
  },
};

export const dashboardApi = {
  getStats: async (hours = 24): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>('/monitoring/stats', {
      params: { hours },
    });
    return response.data;
  },

  getHealth: async () => {
    const response = await api.get('/monitoring/health');
    return response.data;
  },

  getAlerts: async () => {
    const response = await api.get('/monitoring/alerts');
    return response.data;
  },
};

export const knowledgeApi = {
  getStats: async (): Promise<KnowledgeStats> => {
    const response = await api.get<KnowledgeStats>('/knowledge/stats');
    return response.data;
  },

  listMemories: async (
    projectName?: string,
    query?: string
  ): Promise<ProjectMemory[]> => {
    const response = await api.get<{ memories: ProjectMemory[] }>('/memories', {
      params: {
        ...(projectName ? { project_name: projectName } : {}),
        ...(query ? { query } : {}),
      },
    });
    return response.data.memories || [];
  },

  createMemory: async (data: ProjectMemoryCreateRequest): Promise<ProjectMemory> => {
    const response = await api.post<ProjectMemory>('/memories', data);
    return response.data;
  },

  adjustMemoryConfidence: async (
    memoryId: number,
    delta: number
  ): Promise<ProjectMemory> => {
    const response = await api.post<ProjectMemory>(`/memories/${memoryId}/feedback`, {
      delta,
    });
    return response.data;
  },

  listSkills: async (projectName?: string): Promise<SkillSummary[]> => {
    const response = await api.get<{ skills: SkillSummary[] }>('/skills', {
      params: projectName ? { project_name: projectName } : {},
    });
    return response.data.skills || [];
  },

  createSkill: async (data: SkillCreateRequest): Promise<SkillDetail> => {
    const response = await api.post<SkillDetail>('/skills', data);
    return response.data;
  },

  activateSkill: async (
    skillName: string,
    projectName?: string | null
  ): Promise<SkillDetail> => {
    const response = await api.post<SkillDetail>(`/skills/${skillName}/activate`, {
      project_name: projectName || null,
      reason: 'ui',
    });
    return response.data;
  },
};

export const settingsApi = {
  get: async (): Promise<SettingsData> => {
    const response = await api.get<SettingsData>('/settings');
    return response.data;
  },

  update: async (data: Partial<SettingsData>): Promise<SettingsData> => {
    const payload = { ...data };
    if (
      typeof payload.deepseek_api_key !== 'string' ||
      payload.deepseek_api_key.trim() === ''
    ) {
      delete payload.deepseek_api_key;
    }
    const response = await api.put<SettingsData>('/settings', payload);
    return response.data;
  },

  listProjects: async (): Promise<ProjectInfo[]> => {
    const response = await api.get<{ projects: ProjectInfo[] }>('/projects');
    return response.data.projects || [];
  },
};

export const desktopUpdaterApi = {
  check: async (): Promise<DesktopUpdateStatus> => {
    return invoke<DesktopUpdateStatus>('check_desktop_update');
  },

  install: async (): Promise<void> => {
    return invoke<void>('install_desktop_update');
  },
};

export const adminApi = {
  listUsers: async (): Promise<{ users: AdminUser[] }> => {
    const response = await api.get<{ users: AdminUser[] }>('/admin/users');
    return response.data;
  },

  listAuditLogs: async (): Promise<{ logs: AdminAuditLog[] }> => {
    const response = await api.get<{ logs: AdminAuditLog[] }>('/admin/audit-logs');
    return response.data;
  },

  listProjects: async (): Promise<ProjectInfo[]> => {
    const response = await api.get<{ projects: ProjectInfo[] }>('/admin/projects');
    return response.data.projects || [];
  },

  updateUserPermissions: async (
    username: string,
    projectMutationAllowlist: string[]
  ): Promise<AdminUser> => {
    const response = await api.put<AdminUser>(`/admin/users/${username}/permissions`, {
      project_mutation_allowlist: projectMutationAllowlist,
    });
    return response.data;
  },

  createProject: async (data: ProjectCreateRequest): Promise<ProjectInfo> => {
    const response = await api.post<ProjectInfo>('/admin/projects', data);
    return response.data;
  },
};

export const authApi = {
  bootstrapStatus: async (): Promise<BootstrapStatus> => {
    const response = await api.get<BootstrapStatus>('/bootstrap/status');
    return response.data;
  },

  completeBootstrap: async (
    data: BootstrapCompleteRequest
  ): Promise<BootstrapCompleteResponse> => {
    const response = await api.post<BootstrapCompleteResponse>('/bootstrap/complete', data);
    const token = response.data.token || response.data.access_token;
    if (token) {
      localStorage.setItem('auth_token', token);
    }
    return response.data;
  },

  login: async (username: string, password: string) => {
    const response = await api.post('/auth/login', { username, password });
    const token = response.data.token || response.data.access_token;
    localStorage.setItem('auth_token', token);
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('auth_token');
  },

  verify: async () => {
    const response = await api.get('/auth/verify');
    return response.data;
  },
};

export default api;
