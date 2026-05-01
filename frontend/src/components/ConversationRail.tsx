import { Download, MessageSquarePlus, Pencil, Search, Trash2 } from 'lucide-react';
import type { ConversationSummary } from '../types';

interface ConversationRailProps {
  conversations: ConversationSummary[];
  activeConversationId: string;
  query: string;
  formatUsd: (value?: number | null) => string;
  onQueryChange: (query: string) => void;
  onNewConversation: () => void;
  onDownloadUsageCsv: () => Promise<void>;
  onSelectConversation: (conversationId: string) => void;
  onRenameConversation: (conversation: ConversationSummary) => Promise<void>;
  onDeleteConversation: (conversation: ConversationSummary) => Promise<void>;
}

const formatConversationTime = (value: string) =>
  new Date(value).toLocaleString([], {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
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

export function ConversationRail({
  conversations,
  activeConversationId,
  query,
  formatUsd,
  onQueryChange,
  onNewConversation,
  onDownloadUsageCsv,
  onSelectConversation,
  onRenameConversation,
  onDeleteConversation,
}: ConversationRailProps) {
  const normalizedQuery = query.trim().toLowerCase();
  const visibleConversations = conversations.filter((conversation) => {
    if (!normalizedQuery) return true;
    return (
      conversation.title.toLowerCase().includes(normalizedQuery) ||
      conversation.preview.toLowerCase().includes(normalizedQuery) ||
      (conversation.project_name || '').toLowerCase().includes(normalizedQuery)
    );
  });

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
      className={`conversation-item ${
        conversation.id === activeConversationId ? 'active' : ''
      }`}
    >
      <button
        className="conversation-select"
        onClick={() => onSelectConversation(conversation.id)}
        type="button"
      >
        <div className="conversation-item-top">
          <span className="conversation-title">{conversation.title}</span>
          <span className="conversation-time">
            {formatConversationTime(conversation.updated_at)}
          </span>
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
          onClick={() => void onRenameConversation(conversation)}
          type="button"
          aria-label="Renomear conversa"
        >
          <Pencil size={14} />
        </button>
        <button
          className="conversation-action-btn danger"
          onClick={() => void onDeleteConversation(conversation)}
          type="button"
          aria-label="Excluir conversa"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );

  return (
    <aside className="chat-rail">
      <div className="chat-rail-header">
        <div>
          <h2>Conversas</h2>
          <p>{conversations.length} sessões locais</p>
        </div>
        <div className="rail-actions">
          <button className="new-chat-btn" onClick={onNewConversation} type="button">
            <MessageSquarePlus size={16} />
            <span>Nova</span>
          </button>
          <button
            className="new-chat-btn secondary"
            onClick={() => void onDownloadUsageCsv()}
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
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
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
}
