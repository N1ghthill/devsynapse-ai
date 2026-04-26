import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import type {
  AdminAuditLog,
  AdminUser,
  ChatRequest,
  ChatResponse,
  CommandResult,
  ConversationSummary,
  DashboardStats,
  ExecuteCommandRequest,
  Message,
  ProjectCreateRequest,
  ProjectInfo,
  SettingsData,
  TokenUsage,
} from '../types';

const API_BASE_URL = (
  import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? '' : 'http://127.0.0.1:8000')
).replace(/\/$/, '');

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
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
    onCommand: (command: string) => void,
    onReasoning: (reasoning: string) => void,
    onDone: (usage: TokenUsage | null) => void,
    onError: (error: string) => void,
  ): AbortController => {
    const controller = new AbortController();
    const token = localStorage.getItem('auth_token');
    const url = `${API_BASE_URL}/chat/stream`;

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
      signal: controller.signal,
    })
      .then(async (response) => {
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

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6);
            try {
              const event = JSON.parse(dataStr);
              if (event.type === 'text') {
                onToken(event.content);
              } else if (event.type === 'reasoning') {
                onReasoning(event.content);
              } else if (event.type === 'command') {
                onCommand(event.command);
              } else if (event.type === 'done') {
                onDone(event.usage || null);
              } else if (event.type === 'error') {
                onError(event.message || 'Stream error');
              }
            } catch {
              // Skip unparseable lines
            }
          }
        }
      })
      .catch((err) => {
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
