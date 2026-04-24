import React from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot, Copy, Check, Terminal, Play, Loader2, ShieldAlert, CheckCircle2 } from 'lucide-react';
import type { Message } from '../types';

interface ChatMessageProps {
  message: Message;
  onExecute: (messageId: string) => void;
}

const statusLabels = {
  proposed: 'Proposto',
  running: 'Executando',
  success: 'Executado',
  blocked: 'Bloqueado',
  failed: 'Falhou',
} as const;

export function ChatMessage({ message, onExecute }: ChatMessageProps) {
  const [copied, setCopied] = React.useState(false);
  const isUser = message.role === 'user';
  const commandStatus = message.commandStatus ?? 'proposed';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const canExecute = Boolean(message.command) && commandStatus !== 'running' && commandStatus !== 'success';

  return (
    <div className={`message ${isUser ? 'message-user' : 'message-ai'}`}>
      <div className="message-avatar">
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>

      <div className="message-content">
        <div className="message-header">
          <span className="message-role">{isUser ? 'You' : 'DevSynapse'}</span>
          <span className="message-time">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        </div>

        <div className="message-body">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {message.tokenUsage && (
          <div className="message-usage">
            <span className="usage-pill">{message.tokenUsage.model || message.tokenUsage.provider || 'LLM'}</span>
            <span className="usage-pill">
              In: {message.tokenUsage.prompt_tokens.toLocaleString()}
            </span>
            <span className="usage-pill">
              Out: {message.tokenUsage.completion_tokens.toLocaleString()}
            </span>
            <span className="usage-pill">
              Total: {message.tokenUsage.total_tokens.toLocaleString()}
            </span>
            {message.tokenUsage.prompt_cache_hit_tokens > 0 && (
              <span className="usage-pill">
                Cache hit: {message.tokenUsage.prompt_cache_hit_tokens.toLocaleString()}
              </span>
            )}
            {typeof message.tokenUsage.estimated_cost_usd === 'number' && (
              <span className="usage-pill usage-pill-cost">
                Custo: $
                {message.tokenUsage.estimated_cost_usd < 0.01
                  ? message.tokenUsage.estimated_cost_usd.toFixed(6)
                  : message.tokenUsage.estimated_cost_usd.toFixed(4)}
              </span>
            )}
          </div>
        )}

        {message.command && (
          <div className={`message-command command-${commandStatus}`}>
            <div className="message-command-main">
              <Terminal size={14} />
              <div className="message-command-text">
                <code>{message.command}</code>
                {message.projectName && (
                  <span className="command-project-chip">Projeto: {message.projectName}</span>
                )}
              </div>
            </div>
            <span className={`command-status-badge status-${commandStatus}`}>
              {commandStatus === 'running' && <Loader2 size={12} className="spinner" />}
              {commandStatus === 'success' && <CheckCircle2 size={12} />}
              {commandStatus === 'blocked' && <ShieldAlert size={12} />}
              {statusLabels[commandStatus]}
            </span>
            <button
              className="execute-btn"
              onClick={() => onExecute(message.id)}
              disabled={!canExecute}
            >
              {commandStatus === 'running' ? <Loader2 size={14} className="spinner" /> : <Play size={14} />}
              {commandStatus === 'running' ? 'Running...' : 'Run'}
            </button>
          </div>
        )}

        {message.commandResult && (
          <div className={`command-result result-${commandStatus}`}>
            <pre>{message.commandResult}</pre>
            {message.commandNote && (
              <div className="command-note">{message.commandNote}</div>
            )}
          </div>
        )}

        <div className="message-actions">
          <button className="action-btn" onClick={handleCopy}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
}
