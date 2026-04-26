import { useState, useRef, useEffect } from 'react';
import { Download, Loader2, MessageSquarePlus, Pencil, Search, Trash2 } from 'lucide-react';
import { ChatMessage } from '../components/ChatMessage';
import { ChatInput } from '../components/ChatInput';
import { chatApi, dashboardApi, settingsApi } from '../api/client';
import type { BudgetWindowStatus, ConversationSummary, Message, ProjectInfo, TokenUsage } from '../types';

const CONVERSATION_STORAGE_KEY = 'devsynapse_conversation_id';

const reasonLabels: Record<string, string> = {
  validation_failed: 'Bloqueado por regra de segurança do comando.',
  authorization_failed: 'Bloqueado por permissão ou escopo de projeto.',
  execution_failed: 'O comando foi aceito, mas falhou durante a execução.',
  plugin_cancelled: 'A execução foi cancelada por uma regra interna do sistema.',
};

export function Chat() {
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
    () => localStorage.getItem(CONVERSATION_STORAGE_KEY) || `session_${Date.now()}`
  );
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    localStorage.setItem(CONVERSATION_STORAGE_KEY, conversationId);
  }, [conversationId]);

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
        }
      } catch {
        if (!cancelled) {
          setMessages([]);
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
        const list = await settingsApi.listProjects();
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
  }, []);

  const updateMessage = (messageId: string, updates: Partial<Message>) => {
    setMessages((prev) =>
      prev.map((message) => (message.id === messageId ? { ...message, ...updates } : message))
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
        highest.window === 'daily' ? 'Daily' : 'Monthly'
      } budget at ${highest.usage_pct.toFixed(1)}% (${formatUsd(
        highest.actual_cost_usd
      )} / ${formatUsd(highest.budget_usd)}).`,
    };
  })();

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
    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };

    const assistantMessageId = `msg_${Date.now() + 1}`;
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      projectName: selectedProject || null,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsLoading(true);

    try {
      chatApi.sendMessageStreaming(
        {
          message: content,
          conversation_id: conversationId,
          project_name: selectedProject || undefined,
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
        (command) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, command, commandStatus: 'proposed' }
                : msg
            )
          );
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
        (usage) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? { ...msg, tokenUsage: usage }
                : msg
            )
          );
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
          void loadConversationList();
        }
      );
    } catch {
      const errorMessage: Message = {
        id: `msg_${Date.now() + 2}`,
        role: 'system',
        content: 'Failed to get response. Please check your connection.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }

    setIsLoading(false);
  };

  const handleExecute = async (messageId: string) => {
    const targetMessage = messages.find((message) => message.id === messageId);
    if (!targetMessage?.command) return;

    updateMessage(messageId, {
      commandStatus: 'running',
      commandResult: 'Aguardando retorno do backend...',
    });

    try {
      const response = await chatApi.executeCommand({
        conversation_id: conversationId,
        command: targetMessage.command,
        confirm: true,
        project_name: targetMessage.projectName || selectedProject || undefined,
      });

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

      updateMessage(messageId, {
        commandStatus: 'failed',
        commandResult: detail,
        commandNote: describeExecution('failed', undefined, detail),
      });
    }
  };

  const handleClear = () => {
    setMessages([]);
    const nextConversationId = `session_${Date.now()}`;
    setConversationId(nextConversationId);
    localStorage.setItem(CONVERSATION_STORAGE_KEY, nextConversationId);
  };

  const handleSelectConversation = (nextConversationId: string) => {
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
      conversation.preview.toLowerCase().includes(normalizedQuery)
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

  const currentConversation = conversations.find((conversation) => conversation.id === conversationId);
  const conversationUsage = summarizeUsage(messages);

  const renderConversationRail = () => (
    <aside className="chat-rail">
      <div className="chat-rail-header">
        <div>
          <h2>Conversas</h2>
          <p>Histórico recente da sessão local.</p>
        </div>
        <button className="new-chat-btn" onClick={handleClear} type="button">
          <MessageSquarePlus size={16} />
          <span>Nova</span>
        </button>
        <button className="new-chat-btn secondary" onClick={() => void downloadUsageCsv()} type="button">
          <Download size={16} />
          <span>CSV</span>
        </button>
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
        <div>
          <h1>DevSynapse Chat</h1>
          <p className="chat-subtitle">
            {currentConversation?.title || 'Sessão atual'}
          </p>
          {projects.length > 0 && (
            <div className="chat-project-selector">
              <select
                value={selectedProject}
                onChange={(e) => setSelectedProject(e.target.value)}
                aria-label="Selecionar projeto"
              >
                <option value="">Todos os projetos</option>
                {projects.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {budgetSummary && (
            <div className={`chat-budget-banner banner-${budgetSummary.severity}`}>
              {budgetSummary.text}
            </div>
          )}
          {conversationUsage && (
            <div className="chat-usage-summary">
              <span className="usage-pill">
                {conversationUsage.model || conversationUsage.provider || 'LLM'}
              </span>
              <span className="usage-pill">
                In: {conversationUsage.prompt_tokens.toLocaleString()}
              </span>
              <span className="usage-pill">
                Out: {conversationUsage.completion_tokens.toLocaleString()}
              </span>
              <span className="usage-pill">
                Total: {conversationUsage.total_tokens.toLocaleString()}
              </span>
              <span className="usage-pill usage-pill-cost">
                Custo: {formatUsd(conversationUsage.estimated_cost_usd)}
              </span>
            </div>
          )}
        </div>
        <div className="chat-header-actions">
          <span className="session-id">
            Session: {conversationId.slice(0, 20)}...
          </span>
          <button className="clear-btn" onClick={handleClear}>
            <Trash2 size={16} />
            Clear
          </button>
        </div>
      </div>

      <div className="messages-container">
        {!hasMessages && !isLoading && (
          <div className="empty-state">
            <div className="empty-icon">
              <Loader2 size={48} />
            </div>
            <h2>Welcome to DevSynapse</h2>
            <p>
              Your AI development assistant. Ask me anything about your code,
              projects, or development tasks.
            </p>
            <div className="suggestions">
              <button onClick={() => handleSend("List my projects")}>
                List my projects
              </button>
              <button onClick={() => handleSend("Show recent activity")}>
                Show recent activity
              </button>
              <button onClick={() => handleSend("Help me debug")}>
                Help me debug
              </button>
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

      <ChatInput onSend={handleSend} isLoading={isLoading} />
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
