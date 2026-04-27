import React from 'react';
import ReactMarkdown from 'react-markdown';
import {
  AlertTriangle,
  Bot,
  Brain,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  FileText,
  Folder,
  Loader2,
  Play,
  ShieldAlert,
  Terminal,
  User,
} from 'lucide-react';
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

type CommandRisk = 'low' | 'medium' | 'high';

interface CommandReview {
  commandType: string;
  expectedEffect: string;
  risk: CommandRisk;
  riskLabel: string;
  workingDirectory: string;
}

function getCommandType(command: string): string {
  return command.match(/^([a-z_][\w-]*)/i)?.[1]?.toLowerCase() || 'command';
}

function getCommandReview(command: string, projectName?: string | null): CommandReview {
  const commandType = getCommandType(command);
  const projectScope = projectName ? `Project root: ${projectName}` : 'Default execution scope';

  if (commandType === 'read') {
    return {
      commandType,
      expectedEffect: 'Read file contents',
      risk: 'low',
      riskLabel: 'Read-only',
      workingDirectory: projectName ? projectScope : 'Resolved from file path',
    };
  }

  if (commandType === 'glob') {
    return {
      commandType,
      expectedEffect: 'Find files by pattern',
      risk: 'low',
      riskLabel: 'Read-only',
      workingDirectory: projectScope,
    };
  }

  if (commandType === 'grep') {
    return {
      commandType,
      expectedEffect: 'Search file contents',
      risk: 'low',
      riskLabel: 'Read-only',
      workingDirectory: projectScope,
    };
  }

  if (commandType === 'edit' || commandType === 'write') {
    return {
      commandType,
      expectedEffect: commandType === 'edit' ? 'Modify an existing file' : 'Write file contents',
      risk: 'high',
      riskLabel: 'File mutation',
      workingDirectory: projectName ? projectScope : 'Resolved from target path',
    };
  }

  if (commandType === 'bash') {
    return {
      commandType,
      expectedEffect: 'Run a shell command',
      risk: 'medium',
      riskLabel: 'Shell execution',
      workingDirectory: projectScope,
    };
  }

  return {
    commandType,
    expectedEffect: 'Run an allowed tool command',
    risk: 'medium',
    riskLabel: 'Review required',
    workingDirectory: projectScope,
  };
}

export function ChatMessage({ message, onExecute }: ChatMessageProps) {
  const [copied, setCopied] = React.useState(false);
  const [reasoningOpen, setReasoningOpen] = React.useState(false);
  const isUser = message.role === 'user';
  const commandStatus = message.commandStatus ?? 'proposed';
  const commandReview = message.command
    ? getCommandReview(message.command, message.projectName)
    : null;

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
          {message.projectName && (
            <span className="message-project-chip">{message.projectName}</span>
          )}
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

        {message.reasoningContent && (
          <div className="message-reasoning">
            <button
              className="reasoning-toggle"
              onClick={() => setReasoningOpen((prev) => !prev)}
            >
              <Brain size={13} />
              <span>Chain of thought</span>
              {reasoningOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </button>
            {reasoningOpen && (
              <div className="reasoning-body">
                <ReactMarkdown>{message.reasoningContent}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {message.command && (
          <div className={`message-command command-${commandStatus}`}>
            <div className="message-command-header">
              <div className="message-command-main">
                <Terminal size={14} />
                <div className="message-command-text">
                  <span className="command-label">Command</span>
                  <code>{message.command}</code>
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
                {commandStatus === 'running' ? (
                  <Loader2 size={14} className="spinner" />
                ) : (
                  <Play size={14} />
                )}
                {commandStatus === 'running' ? 'Running...' : 'Run'}
              </button>
            </div>
            {commandReview && (
              <div className="command-review-grid">
                <div className="command-review-item">
                  <AlertTriangle size={13} />
                  <span className="command-review-label">Risk</span>
                  <span className={`command-review-value risk-${commandReview.risk}`}>
                    {commandReview.riskLabel}
                  </span>
                </div>
                <div className="command-review-item">
                  <Folder size={13} />
                  <span className="command-review-label">Directory</span>
                  <span className="command-review-value">{commandReview.workingDirectory}</span>
                </div>
                <div className="command-review-item">
                  <FileText size={13} />
                  <span className="command-review-label">Effect</span>
                  <span className="command-review-value">{commandReview.expectedEffect}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {message.commandResult && (
          <div className={`command-result result-${commandStatus}`}>
            <pre>{message.commandResult}</pre>
            {message.commandNote && (
              <div className="command-note">{message.commandNote}</div>
            )}
            {message.commandInterpretation && (
              <div className="command-interpretation">{message.commandInterpretation}</div>
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
