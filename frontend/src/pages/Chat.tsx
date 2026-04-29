import { useState, useRef, useEffect } from 'react';
import {
  ArrowDown,
  ArrowUp,
  BookOpenText,
  ClipboardList,
  Container,
  Download,
  FileSearch,
  FlaskConical,
  FolderOpen,
  FolderPlus,
  GitPullRequestArrow,
  ListTodo,
  Loader2,
  LockKeyhole,
  MessageSquarePlus,
  Pencil,
  Search,
  ShieldCheck,
  Trash2,
  X,
  type LucideIcon,
} from 'lucide-react';
import { ChatMessage } from '../components/ChatMessage';
import { ChatInput } from '../components/ChatInput';
import { adminApi, chatApi, dashboardApi, settingsApi } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type {
  BudgetWindowStatus,
  ConversationSummary,
  Message,
  ProjectInfo,
  TokenUsage,
  ToolRun,
} from '../types';

const CONVERSATION_STORAGE_KEY = 'devsynapse_conversation_id';
const AUTO_APPROVE_STORAGE_KEY = 'devsynapse_auto_approve_commands';

const createConversationId = () => `session_${Date.now()}`;

const workflowTemplates: Array<{
  title: string;
  description: string;
  prompt: string;
  icon: LucideIcon;
}> = [
  {
    title: 'Suite de testes',
    description: 'Detecta o comando correto e prepara a execução.',
    prompt: 'Analise o projeto selecionado e proponha o comando mais seguro para executar a suite de testes.',
    icon: FlaskConical,
  },
  {
    title: 'Falha de teste',
    description: 'Organiza causa provável, evidências e próxima correção.',
    prompt: 'Revise a última falha de teste ou me peça a saída; explique a causa provável e a próxima correção.',
    icon: ClipboardList,
  },
  {
    title: 'TODOs críticos',
    description: 'Lista débitos comentados por prioridade.',
    prompt: 'Busque comentários TODO e FIXME neste projeto e resuma os itens de limpeza mais prioritários.',
    icon: ListTodo,
  },
  {
    title: 'Mapa do repo',
    description: 'Resume stack, estrutura e pontos de entrada.',
    prompt: 'Resuma a estrutura, stack tecnológica e pontos de entrada mais importantes do repositório selecionado.',
    icon: BookOpenText,
  },
  {
    title: 'Changelog',
    description: 'Gera release notes do histórico recente.',
    prompt: 'Crie um rascunho de changelog conciso a partir do histórico git recente deste projeto.',
    icon: GitPullRequestArrow,
  },
  {
    title: 'Docker',
    description: 'Revisa containers e comandos locais.',
    prompt: 'Inspecione a configuração Docker deste projeto e explique como executá-lo localmente.',
    icon: Container,
  },
];

const reasonLabels: Record<string, string> = {
  validation_failed: 'Bloqueado por regra de segurança do comando.',
  authorization_failed: 'Bloqueado por permissão ou escopo de projeto.',
  execution_failed: 'O comando foi aceito, mas falhou durante a execução.',
  plugin_cancelled: 'A execução foi cancelada por uma regra interna do sistema.',
  project_scope_mismatch: 'Bloqueado porque o comando tentou sair do projeto da conversa.',
};

export function Chat() {
  const { auth } = useAuth();
  const isAdmin = auth.user?.role === 'admin';
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationQuery, setConversationQuery] = useState('');
  const [budgetStatus, setBudgetStatus] = useState<{
    overall_status: 'disabled' | 'healthy' | 'warning' | 'critical';
    daily: BudgetWindowStatus;
    monthly: BudgetWindowStatus;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>(
    () => localStorage.getItem(CONVERSATION_STORAGE_KEY) || createConversationId()
  );
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [showProjectMenu, setShowProjectMenu] = useState(false);
  const [creatingProject, setCreatingProject] = useState(false);
  const [projectDraftName, setProjectDraftName] = useState('');
  const [projectDraftPath, setProjectDraftPath] = useState('');
  const [projectError, setProjectError] = useState<string | null>(null);
  const [autoApprove, setAutoApprove] = useState(
    () => localStorage.getItem(AUTO_APPROVE_STORAGE_KEY) === 'true'
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const pinnedToLatestRef = useRef(true);
  const messageIdSequenceRef = useRef(0);
  const toolRunSequenceRef = useRef(0);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

  useEffect(() => {
    if (pinnedToLatestRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages, isLoading]);

  useEffect(() => {
    localStorage.setItem(CONVERSATION_STORAGE_KEY, conversationId);
  }, [conversationId]);

  useEffect(() => {
    localStorage.setItem(AUTO_APPROVE_STORAGE_KEY, String(autoApprove));
  }, [autoApprove]);

  const loadConversationList = async () => {
    try {
      const response = await chatApi.listConversations();
      setConversations(response.conversations || []);
    } catch {
      setConversations([]);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const loadConversation = async () => {
      try {
        const [conversationResponse, listResponse] = await Promise.all([
          chatApi.getConversation(conversationId),
          chatApi.listConversations(),
        ]);
        if (!cancelled) {
          setMessages(conversationResponse.history || []);
          setConversations(listResponse.conversations || []);
          setSelectedProject(conversationResponse.project_name || '');
        }
      } catch {
        if (!cancelled) {
          setMessages([]);
          setSelectedProject('');
          void loadConversationList();
        }
      }
    };

    void loadConversation();

    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  useEffect(() => {
    let cancelled = false;

    const loadBudgetStatus = async () => {
      try {
        const stats = await dashboardApi.getStats(24);
        if (!cancelled) {
          setBudgetStatus(stats.llm_usage.budget);
        }
      } catch {
        if (!cancelled) {
          setBudgetStatus(null);
        }
      }
    };

    void loadBudgetStatus();
    const interval = setInterval(loadBudgetStatus, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadProjects = async () => {
      try {
        const list = isAdmin ? await adminApi.listProjects() : await settingsApi.listProjects();
        if (!cancelled) {
          setProjects(list);
        }
      } catch {
        if (!cancelled) {
          setProjects([]);
        }
      }
    };

    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  const updateMessage = (messageId: string, updates: Partial<Message>) => {
    setMessages((prev) =>
      prev.map((message) => (message.id === messageId ? { ...message, ...updates } : message))
    );
  };

  const syncScrollState = () => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const distanceToBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = distanceToBottom < 140;

    pinnedToLatestRef.current = isNearBottom;
    setShowScrollTop(container.scrollTop > 280);
    setShowJumpToLatest(!isNearBottom);
  };

  const scrollToLatest = () => {
    pinnedToLatestRef.current = true;
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    setShowJumpToLatest(false);
  };

  const scrollToStart = () => {
    pinnedToLatestRef.current = false;
    messagesContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const createMessageId = () => {
    messageIdSequenceRef.current += 1;
    return `msg_${conversationId}_${messageIdSequenceRef.current}`;
  };

  const createToolRunId = () => {
    toolRunSequenceRef.current += 1;
    return `tool_${conversationId}_${toolRunSequenceRef.current}`;
  };

  const updateToolRun = (
    messageId: string,
    command: string,
    updates: Partial<ToolRun>
  ) => {
    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== messageId) return message;
        const existingRuns = message.toolRuns || [];
        const index = [...existingRuns]
          .reverse()
          .findIndex((run) => run.command === command && run.status !== 'success');
        const actualIndex = index === -1 ? -1 : existingRuns.length - 1 - index;
        if (actualIndex === -1) {
          return message;
        }
        const nextRuns = [...existingRuns];
        nextRuns[actualIndex] = { ...nextRuns[actualIndex], ...updates };
        return { ...message, toolRuns: nextRuns };
      })
    );
  };

  const summarizeUsage = (items: Message[]): TokenUsage | null => {
    const usages = items
      .map((message) => message.tokenUsage)
      .filter((usage): usage is TokenUsage => Boolean(usage));

    if (usages.length === 0) return null;

    return usages.reduce<TokenUsage>(
      (acc, usage) => ({
        provider: acc.provider || usage.provider,
        model: acc.model || usage.model,
        prompt_tokens: acc.prompt_tokens + usage.prompt_tokens,
        completion_tokens: acc.completion_tokens + usage.completion_tokens,
        total_tokens: acc.total_tokens + usage.total_tokens,
        prompt_cache_hit_tokens: acc.prompt_cache_hit_tokens + usage.prompt_cache_hit_tokens,
        prompt_cache_miss_tokens:
          acc.prompt_cache_miss_tokens + usage.prompt_cache_miss_tokens,
        reasoning_tokens: acc.reasoning_tokens + usage.reasoning_tokens,
        estimated_cost_usd:
          (acc.estimated_cost_usd || 0) + (usage.estimated_cost_usd || 0),
      }),
      {
        provider: null,
        model: null,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        prompt_cache_hit_tokens: 0,
        prompt_cache_miss_tokens: 0,
        reasoning_tokens: 0,
        estimated_cost_usd: 0,
      }
    );
  };

  const formatUsd = (value?: number | null) => {
    if (value == null) return 'n/d';
    return value < 0.01 ? `$${value.toFixed(6)}` : `$${value.toFixed(4)}`;
  };

  const budgetSummary = (() => {
    if (!budgetStatus) return null;
    if (budgetStatus.overall_status === 'disabled') return null;

    const highest =
      budgetStatus.daily.level === 'critical' || budgetStatus.daily.level === 'warning'
        ? budgetStatus.daily
        : budgetStatus.monthly;

    if (highest.level !== 'critical' && highest.level !== 'warning') {
      return null;
    }

    return {
      severity: highest.level,
      text: `${
        highest.window === 'daily' ? 'Diário' : 'Mensal'
      } em ${highest.usage_pct.toFixed(1)}% (${formatUsd(
        highest.actual_cost_usd
      )} / ${formatUsd(highest.budget_usd)}).`,
    };
  })();

  const currentConversation = conversations.find(
    (conversation) => conversation.id === conversationId
  );
  const messageProject = messages.find((message) => message.projectName)?.projectName || null;
  const lockedProject = currentConversation?.project_name || messageProject || null;
  const currentScopeProject = lockedProject || selectedProject || null;
  const projectScopeLocked = Boolean(lockedProject);
  const conversationUsage = summarizeUsage(messages);
  const toolRunTotal = messages.reduce(
    (total, message) =>
      total + (message.toolRuns?.length || 0) + (message.command ? 1 : 0),
    0
  );
  const activeToolRunTotal = messages.reduce(
    (total, message) =>
      total +
      (message.toolRuns?.filter((toolRun) => toolRun.status === 'running').length || 0) +
      (message.commandStatus === 'running' ? 1 : 0),
    0
  );

  const downloadUsageCsv = async () => {
    const csv = await chatApi.exportUsageCsv();
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'devsynapse-usage.csv';
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  const startConversationForProject = (projectName: string) => {
    pinnedToLatestRef.current = true;
    setMessages([]);
    setSelectedProject(projectName);
    const nextConversationId = createConversationId();
    setConversationId(nextConversationId);
    localStorage.setItem(CONVERSATION_STORAGE_KEY, nextConversationId);
  };

  const handleProjectSelection = (projectName: string) => {
    setProjectError(null);
    setShowProjectMenu(false);
    if (projectScopeLocked && projectName !== lockedProject) {
      startConversationForProject(projectName);
      return;
    }
    setSelectedProject(projectName);
  };

  const getRequestError = (error: unknown, fallback: string) => {
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error &&
      typeof error.response === 'object' &&
      error.response !== null &&
      'data' in error.response &&
      typeof error.response.data === 'object' &&
      error.response.data !== null &&
      'detail' in error.response.data &&
      typeof error.response.data.detail === 'string'
    ) {
      return error.response.data.detail;
    }

    return fallback;
  };

  const handleCreateProject = async () => {
    const name = projectDraftName.trim();
    if (!name || creatingProject || !isAdmin) return;

    setCreatingProject(true);
    setProjectError(null);
    try {
      const created = await adminApi.createProject({
        name,
        ...(projectDraftPath.trim() ? { path: projectDraftPath.trim() } : {}),
        type: 'project',
        priority: 'medium',
        create_directory: true,
      });
      setProjects((prev) => {
        const withoutDuplicate = prev.filter((project) => project.name !== created.name);
        return [...withoutDuplicate, created].sort((a, b) => a.name.localeCompare(b.name));
      });
      setProjectDraftName('');
      setProjectDraftPath('');
      setShowProjectMenu(false);
      startConversationForProject(created.name);
      void loadConversationList();
    } catch (error) {
      setProjectError(getRequestError(error, 'Falha ao criar projeto'));
    } finally {
      setCreatingProject(false);
    }
  };

  const describeExecution = (
    status: 'success' | 'blocked' | 'failed',
    reasonCode?: string,
    rawMessage?: string,
    projectName?: string | null
  ) => {
    const projectSuffix = projectName ? ` Projeto: ${projectName}.` : '';
    if (status === 'success') {
      return `Execução concluída com sucesso.${projectSuffix}`;
    }
    if (reasonCode && reasonLabels[reasonCode]) {
      return `${reasonLabels[reasonCode]}${projectSuffix}`;
    }
    if (status === 'blocked') {
      return `A execução foi recusada antes de rodar.${projectSuffix}`;
    }
    if (rawMessage && /tempo|timeout|expirou/i.test(rawMessage)) {
      return `A execução excedeu o tempo limite.${projectSuffix}`;
    }
    return `A execução falhou e precisa de revisão.${projectSuffix}`;
  };

  const handleSend = async (content: string) => {
    const prompt = content.trim();
    if (!prompt || isLoading) return;

    const userMessageId = createMessageId();
    const assistantMessageId = createMessageId();
    const userMessage: Message = {
      id: userMessageId,
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
      projectName: currentScopeProject,
    };

    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      projectName: currentScopeProject,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);

    try {
      chatApi.sendMessageStreaming(
        {
          message: prompt,
          conversation_id: conversationId,
          project_name: currentScopeProject || undefined,
          execute_command: autoApprove,
        },
        (token) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content + token }
                : msg
            )
          );
        },
        (command, autoExecute) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? autoExecute
                  ? {
                      ...msg,
                      command: undefined,
                      commandStatus: undefined,
                      toolRuns: [
                        ...(msg.toolRuns || []),
                        {
                          id: createToolRunId(),
                          command,
                          status: 'proposed',
                          projectName: msg.projectName,
                        },
                      ],
                    }
                  : { ...msg, command, commandStatus: 'proposed' }
                : msg
            )
          );
        },
        (command, status) => {
          updateToolRun(assistantMessageId, command, {
            status,
            result: status === 'running' ? 'Aguardando retorno do backend...' : undefined,
          });
        },
        (command, result) => {
          updateToolRun(assistantMessageId, command, {
            status: result.status,
            result: result.output || result.message,
            message: describeExecution(
              result.status,
              result.reason_code,
              result.message,
              result.project_name
            ),
            reasonCode: result.reason_code,
            projectName: result.project_name,
          });
          if (result.project_name && !projectScopeLocked) {
            setSelectedProject(result.project_name);
          }
        },
        (reasoning) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, reasoningContent: (msg.reasoningContent || '') + reasoning }
                : msg
            )
          );
        },
        (usage, projectName) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, tokenUsage: usage, projectName: projectName || msg.projectName }
                : msg.id === userMessageId && projectName
                  ? { ...msg, projectName }
                  : msg
            )
          );
          if (projectName && !projectScopeLocked) {
            setSelectedProject(projectName);
          }
          setIsLoading(false);
          void loadConversationList();
        },
        (error) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, content: msg.content || error, commandStatus: undefined }
                : msg
            )
          );
          setIsLoading(false);
          void loadConversationList();
        }
      );
    } catch {
      const errorMessage: Message = {
        id: createMessageId(),
        role: 'system',
        content: 'Failed to get response. Please check your connection.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setIsLoading(false);
    }
  };

  const handleExecute = async (messageId: string, toolRunId?: string) => {
    const targetMessage = messages.find((message) => message.id === messageId);
    const targetToolRun = toolRunId
      ? targetMessage?.toolRuns?.find((toolRun) => toolRun.id === toolRunId)
      : undefined;
    const command = targetToolRun?.command || targetMessage?.command;
    if (!targetMessage || !command) return;

    if (targetToolRun) {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === messageId
            ? {
                ...message,
                toolRuns: (message.toolRuns || []).map((toolRun) =>
                  toolRun.id === toolRunId
                    ? {
                        ...toolRun,
                        status: 'running',
                        result: 'Aguardando retorno do backend...',
                      }
                    : toolRun
                ),
              }
            : message
        )
      );
    } else {
      updateMessage(messageId, {
        commandStatus: 'running',
        commandResult: 'Aguardando retorno do backend...',
      });
    }

    try {
      const response = await chatApi.executeCommand({
        conversation_id: conversationId,
        command,
        confirm: true,
        project_name:
          targetToolRun?.projectName ||
          targetMessage.projectName ||
          currentScopeProject ||
          currentConversation?.project_name ||
          undefined,
      });

      if (targetToolRun) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  toolRuns: (message.toolRuns || []).map((toolRun) =>
                    toolRun.id === toolRunId
                      ? {
                          ...toolRun,
                          status: response.status,
                          result: response.output || response.message,
                          message: describeExecution(
                            response.status,
                            response.reason_code,
                            response.message,
                            response.project_name
                          ),
                          reasonCode: response.reason_code,
                          projectName: response.project_name,
                        }
                      : toolRun
                  ),
                }
              : message
          )
        );
      } else {
        updateMessage(messageId, {
          commandStatus: response.status,
          commandResult: response.output || response.message,
          reasonCode: response.reason_code,
          projectName: response.project_name,
          commandInterpretation: response.interpretation,
          commandNote: describeExecution(
            response.status,
            response.reason_code,
            response.message,
            response.project_name
          ),
        });
      }
    } catch (error) {
      const detail =
        typeof error === 'object' &&
        error !== null &&
        'response' in error &&
        typeof error.response === 'object' &&
        error.response !== null &&
        'data' in error.response &&
        typeof error.response.data === 'object' &&
        error.response.data !== null &&
        'detail' in error.response.data &&
        typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : 'Falha ao executar comando';

      if (targetToolRun) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  toolRuns: (message.toolRuns || []).map((toolRun) =>
                    toolRun.id === toolRunId
                      ? {
                          ...toolRun,
                          status: 'failed',
                          result: detail,
                          message: describeExecution('failed', undefined, detail),
                        }
                      : toolRun
                  ),
                }
              : message
          )
        );
      } else {
        updateMessage(messageId, {
          commandStatus: 'failed',
          commandResult: detail,
          commandNote: describeExecution('failed', undefined, detail),
        });
      }
    }
  };

  const handleClear = () => {
    pinnedToLatestRef.current = true;
    setMessages([]);
    const nextConversationId = createConversationId();
    setConversationId(nextConversationId);
    localStorage.setItem(CONVERSATION_STORAGE_KEY, nextConversationId);
  };

  const handleSelectConversation = (nextConversationId: string) => {
    const nextConversation = conversations.find(
      (conversation) => conversation.id === nextConversationId
    );
    pinnedToLatestRef.current = true;
    setSelectedProject(nextConversation?.project_name || '');
    setConversationId(nextConversationId);
  };

  const handleRenameConversation = async (targetConversation: ConversationSummary) => {
    const nextTitle = window.prompt('Novo título da conversa:', targetConversation.title);
    if (!nextTitle || !nextTitle.trim()) return;

    await chatApi.renameConversation(targetConversation.id, nextTitle.trim());
    await loadConversationList();
  };

  const handleDeleteConversation = async (targetConversation: ConversationSummary) => {
    const confirmed = window.confirm(`Excluir a conversa "${targetConversation.title}"?`);
    if (!confirmed) return;

    await chatApi.deleteConversation(targetConversation.id);

    if (targetConversation.id === conversationId) {
      handleClear();
    } else {
      await loadConversationList();
    }
  };

  const formatConversationTime = (value: string) =>
    new Date(value).toLocaleString([], {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

  const hasMessages = messages.length > 0;

  const normalizedQuery = conversationQuery.trim().toLowerCase();
  const visibleConversations = conversations.filter((conversation) => {
    if (!normalizedQuery) return true;
    return (
      conversation.title.toLowerCase().includes(normalizedQuery) ||
      conversation.preview.toLowerCase().includes(normalizedQuery) ||
      (conversation.project_name || '').toLowerCase().includes(normalizedQuery)
    );
  });

  const getConversationGroupLabel = (updatedAt: string) => {
    const current = new Date();
    const target = new Date(updatedAt);
    const dayStart = new Date(current.getFullYear(), current.getMonth(), current.getDate());
    const yesterdayStart = new Date(dayStart);
    yesterdayStart.setDate(dayStart.getDate() - 1);
    const targetDay = new Date(target.getFullYear(), target.getMonth(), target.getDate());

    if (targetDay.getTime() === dayStart.getTime()) return 'Hoje';
    if (targetDay.getTime() === yesterdayStart.getTime()) return 'Ontem';
    return 'Mais antigas';
  };

  const groupedConversations = visibleConversations.reduce<Record<string, ConversationSummary[]>>(
    (groups, conversation) => {
      const label = getConversationGroupLabel(conversation.updated_at);
      groups[label] = [...(groups[label] || []), conversation];
      return groups;
    },
    {}
  );
  const orderedGroupLabels = ['Hoje', 'Ontem', 'Mais antigas'].filter(
    (label) => (groupedConversations[label] || []).length > 0
  );

  const renderConversationItem = (conversation: ConversationSummary) => (
    <div
      key={conversation.id}
      className={`conversation-item ${conversation.id === conversationId ? 'active' : ''}`}
    >
      <button
        className="conversation-select"
        onClick={() => handleSelectConversation(conversation.id)}
        type="button"
      >
        <div className="conversation-item-top">
          <span className="conversation-title">{conversation.title}</span>
          <span className="conversation-time">{formatConversationTime(conversation.updated_at)}</span>
        </div>
        <p className="conversation-preview">{conversation.preview || 'Sem resumo disponível.'}</p>
        {conversation.project_name && (
          <span className="conversation-project-chip">{conversation.project_name}</span>
        )}
        <div className="conversation-metrics">
          <span>{(conversation.total_tokens || 0).toLocaleString()} tok</span>
          <span>{formatUsd(conversation.estimated_cost_usd || 0)}</span>
        </div>
      </button>
      <div className="conversation-actions">
        <button
          className="conversation-action-btn"
          onClick={() => void handleRenameConversation(conversation)}
          type="button"
          aria-label="Renomear conversa"
        >
          <Pencil size={14} />
        </button>
        <button
          className="conversation-action-btn danger"
          onClick={() => void handleDeleteConversation(conversation)}
          type="button"
          aria-label="Excluir conversa"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );

  const renderConversationRail = () => (
    <aside className="chat-rail">
      <div className="chat-rail-header">
        <div>
          <h2>Conversas</h2>
          <p>{conversations.length} sessões locais</p>
        </div>
        <div className="rail-actions">
          <button className="new-chat-btn" onClick={handleClear} type="button">
            <MessageSquarePlus size={16} />
            <span>Nova</span>
          </button>
          <button
            className="new-chat-btn secondary"
            onClick={() => void downloadUsageCsv()}
            type="button"
          >
            <Download size={16} />
            <span>CSV</span>
          </button>
        </div>
      </div>

      <div className="conversation-search">
        <Search size={15} className="conversation-search-icon" />
        <input
          type="text"
          value={conversationQuery}
          onChange={(event) => setConversationQuery(event.target.value)}
          placeholder="Buscar conversa..."
          aria-label="Buscar conversa"
        />
      </div>

      <div className="conversation-list">
        {visibleConversations.length > 0 ? (
          orderedGroupLabels.map((label) => (
            <section key={label} className="conversation-group">
              <div className="conversation-group-label">{label}</div>
              <div className="conversation-group-items">
                {groupedConversations[label].map(renderConversationItem)}
              </div>
            </section>
          ))
        ) : (
          <div className="conversation-empty">
            <p>
              {normalizedQuery
                ? 'Nenhuma conversa corresponde à busca.'
                : 'Nenhuma conversa salva ainda.'}
            </p>
          </div>
        )}
      </div>
    </aside>
  );

  const renderChatPanel = () => (
    <>
      <div className="chat-header">
        <div className="chat-header-main">
          <div className="workspace-title-row">
            <span className="workspace-kicker">Workspace local</span>
            <span className="workspace-live-dot">Pronto</span>
          </div>
          <h1>DevSynapse</h1>
          <p className="chat-subtitle">
            {currentConversation?.title || 'Nova sessão de desenvolvimento'}
          </p>
        </div>
        <div className="chat-header-actions">
          <button
            className={`header-auto-approve ${autoApprove ? 'active' : ''}`}
            onClick={() => setAutoApprove((enabled) => !enabled)}
            type="button"
            aria-pressed={autoApprove}
            title={
              isAdmin
                ? 'Admin: executar comandos suportados sem confirmação por etapa'
                : 'Executar comandos autorizados automaticamente'
            }
          >
            <ShieldCheck size={15} />
            <span>
              {autoApprove
                ? isAdmin
                  ? 'Admin automático'
                  : 'Execução automática'
                : 'Revisão manual'}
            </span>
          </button>
          <span className="session-id">
            {conversationId.slice(0, 20)}...
          </span>
          <button className="clear-btn" onClick={handleClear} type="button">
            <Trash2 size={16} />
            Limpar
          </button>
        </div>

        <div className="chat-context-strip">
          <div className="context-project-control">
            <span className="context-label">Projeto</span>
            <div className="project-menu-wrap">
              <button
                className="project-menu-trigger"
                type="button"
                onClick={() => setShowProjectMenu((visible) => !visible)}
                aria-expanded={showProjectMenu}
              >
                {projectScopeLocked ? <LockKeyhole size={15} /> : <FolderOpen size={15} />}
                <span>{currentScopeProject || 'Selecionar projeto'}</span>
              </button>

              {showProjectMenu && (
                <div className="project-menu">
                  <div className="project-menu-head">
                    <strong>Projeto da conversa</strong>
                    <button
                      type="button"
                      className="project-menu-close"
                      onClick={() => setShowProjectMenu(false)}
                      aria-label="Fechar menu de projetos"
                    >
                      <X size={14} />
                    </button>
                  </div>

                  {projectScopeLocked && (
                    <div className="project-lock-note">
                      <LockKeyhole size={14} />
                      <span>Esta conversa está travada em {lockedProject}.</span>
                    </div>
                  )}

                  <div className="project-menu-list">
                    {projects.map((project) => (
                      <button
                        key={project.name}
                        type="button"
                        className={`project-menu-item ${
                          project.name === currentScopeProject ? 'active' : ''
                        }`}
                        onClick={() => handleProjectSelection(project.name)}
                      >
                        <span>{project.name}</span>
                        {project.path && <small>{project.path}</small>}
                      </button>
                    ))}
                    {projects.length === 0 && (
                      <span className="project-menu-empty">Nenhum projeto registrado.</span>
                    )}
                  </div>

                  {isAdmin && (
                    <div className="project-create-panel">
                      <label htmlFor="project-name-input">Novo projeto</label>
                      <div className="project-create-row">
                        <input
                          id="project-name-input"
                          type="text"
                          value={projectDraftName}
                          onChange={(event) => setProjectDraftName(event.target.value)}
                          placeholder="nome-do-projeto"
                        />
                        <button
                          type="button"
                          className="project-create-btn"
                          onClick={() => void handleCreateProject()}
                          disabled={creatingProject || !projectDraftName.trim()}
                        >
                          <FolderPlus size={15} />
                          <span>{creatingProject ? 'Criando' : 'Criar'}</span>
                        </button>
                      </div>
                      <input
                        type="text"
                        value={projectDraftPath}
                        onChange={(event) => setProjectDraftPath(event.target.value)}
                        placeholder="caminho opcional; vazio usa a pasta de repositórios"
                      />
                      {projectError && <p className="project-menu-error">{projectError}</p>}
                    </div>
                  )}
                </div>
              )}
            </div>
            {projectScopeLocked && (
              <span className="scope-chip locked">
                <LockKeyhole size={13} />
                Travado
              </span>
            )}
            {!projectScopeLocked && projects.length === 0 && (
              <span className="scope-chip">Sem projetos</span>
            )}
            <span className={currentScopeProject ? 'scope-chip active' : 'scope-chip'}>
              {currentScopeProject ? currentScopeProject : 'Escopo global'}
            </span>
            {projectScopeLocked && selectedProject && selectedProject !== lockedProject && (
              <div className="project-lock-note inline">
                Abra uma nova conversa para trocar de projeto.
              </div>
            )}
          </div>

          <div className="context-metrics" aria-label="Resumo da sessão">
            <span className="context-pill">
              <strong>{messages.length.toLocaleString()}</strong>
              <span>mensagens</span>
            </span>
            <span className="context-pill">
              <strong>{(conversationUsage?.total_tokens || 0).toLocaleString()}</strong>
              <span>tokens</span>
            </span>
            <span className="context-pill">
              <strong>{formatUsd(conversationUsage?.estimated_cost_usd || 0)}</strong>
              <span>custo</span>
            </span>
            <span className={activeToolRunTotal > 0 ? 'context-pill active' : 'context-pill'}>
              <strong>{toolRunTotal.toLocaleString()}</strong>
              <span>{activeToolRunTotal > 0 ? 'rodando' : 'execuções'}</span>
            </span>
            {budgetSummary && (
              <div className={`chat-budget-banner banner-${budgetSummary.severity}`}>
                {budgetSummary.text}
              </div>
            )}
          </div>
        </div>
      </div>

      <div
        className="messages-container"
        ref={messagesContainerRef}
        onScroll={syncScrollState}
      >
        {!hasMessages && !isLoading && (
          <div className="empty-state">
            <div className="empty-icon">
              <FileSearch size={44} />
            </div>
            <h2>Escolha um fluxo</h2>
            <p>
              {currentScopeProject
                ? `Projeto ativo: ${currentScopeProject}`
                : 'Escopo global ativo para descoberta inicial.'}
            </p>
            <div className="workflow-templates">
              {workflowTemplates.map((template) => {
                const Icon = template.icon;
                return (
                  <button
                    key={template.title}
                    className="workflow-template-btn"
                    onClick={() => void handleSend(template.prompt)}
                    disabled={isLoading}
                    type="button"
                  >
                    <Icon size={18} />
                    <span>
                      <strong>{template.title}</strong>
                      <small>{template.description}</small>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            onExecute={handleExecute}
          />
        ))}

        {isLoading && (
          <div className="message message-ai">
            <div className="message-avatar">
              <Loader2 size={20} className="spinner" />
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {(showScrollTop || showJumpToLatest) && (
        <div className="chat-scroll-controls" aria-label="Navegação da conversa">
          {showScrollTop && (
            <button
              type="button"
              className="chat-scroll-btn"
              onClick={scrollToStart}
              aria-label="Voltar ao topo da conversa"
            >
              <ArrowUp size={15} />
              <span>Topo</span>
            </button>
          )}
          {showJumpToLatest && (
            <button
              type="button"
              className="chat-scroll-btn primary"
              onClick={scrollToLatest}
              aria-label="Ir para as mensagens recentes"
            >
              <ArrowDown size={15} />
              <span>Recente</span>
            </button>
          )}
        </div>
      )}

      <ChatInput
        onSend={handleSend}
        isLoading={isLoading}
        autoApprove={autoApprove}
        isAdmin={isAdmin}
        onAutoApproveChange={setAutoApprove}
      />
    </>
  );

  return (
    <div className="chat-page">
      <div className="chat-shell">
        {renderConversationRail()}
        <section className="chat-main-panel">
          {renderChatPanel()}
        </section>
      </div>
    </div>
  );
}
