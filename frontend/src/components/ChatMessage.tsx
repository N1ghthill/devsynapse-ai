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
  onExecute: (messageId: string, toolRunId?: string) => void;
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
  const projectScope = projectName ? `Projeto: ${projectName}` : 'Escopo padrão';

  if (commandType === 'read') {
    return {
      commandType,
      expectedEffect: 'Ler conteúdo de arquivo',
      risk: 'low',
      riskLabel: 'Somente leitura',
      workingDirectory: projectName ? projectScope : 'Resolvido pelo caminho',
    };
  }

  if (commandType === 'glob') {
    return {
      commandType,
      expectedEffect: 'Encontrar arquivos por padrão',
      risk: 'low',
      riskLabel: 'Somente leitura',
      workingDirectory: projectScope,
    };
  }

  if (commandType === 'grep') {
    return {
      commandType,
      expectedEffect: 'Buscar em conteúdo de arquivos',
      risk: 'low',
      riskLabel: 'Somente leitura',
      workingDirectory: projectScope,
    };
  }

  if (commandType === 'edit' || commandType === 'write') {
    return {
      commandType,
      expectedEffect: commandType === 'edit' ? 'Modificar arquivo existente' : 'Escrever arquivo',
      risk: 'high',
      riskLabel: 'Muda arquivos',
      workingDirectory: projectName ? projectScope : 'Resolvido pelo destino',
    };
  }

  if (commandType === 'bash') {
    return {
      commandType,
      expectedEffect: 'Executar comando shell',
      risk: 'medium',
      riskLabel: 'Shell',
      workingDirectory: projectScope,
    };
  }

  return {
    commandType,
    expectedEffect: 'Executar ferramenta autorizada',
    risk: 'medium',
    riskLabel: 'Revisar',
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
  const toolRuns = message.toolRuns || [];
  const isPendingAssistant =
    !isUser &&
    !message.content &&
    !message.command &&
    !message.reasoningContent &&
    toolRuns.length === 0;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const canExecute = Boolean(message.command) && commandStatus !== 'running' && commandStatus !== 'success';
  const renderCommandReview = (command: string, projectName?: string | null) => {
    const review = getCommandReview(command, projectName);
    return (
      <div className="command-review-grid">
        <div className="command-review-item">
          <AlertTriangle size={13} />
          <span className="command-review-label">Risco</span>
          <span className={`command-review-value risk-${review.risk}`}>
            {review.riskLabel}
          </span>
        </div>
        <div className="command-review-item">
          <Folder size={13} />
          <span className="command-review-label">Diretório</span>
          <span className="command-review-value">{review.workingDirectory}</span>
        </div>
        <div className="command-review-item">
          <FileText size={13} />
          <span className="command-review-label">Efeito</span>
          <span className="command-review-value">{review.expectedEffect}</span>
        </div>
      </div>
    );
  };

  const renderCommandResult = (
    status: Message['commandStatus'],
    result?: string,
    messageText?: string
  ) => {
    const resultText = result || messageText;
    if (!resultText) return null;

    return (
      <div className={`command-result result-${status || 'proposed'}`}>
        <pre>{resultText}</pre>
      </div>
    );
  };

  return (
    <div
      className={`message ${isUser ? 'message-user' : 'message-ai'} ${
        isPendingAssistant ? 'message-streaming' : ''
      }`}
    >
      <div className="message-avatar">
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>

      <div className="message-content">
        <div className="message-header">
          <span className="message-role">{isUser ? 'Você' : 'DevSynapse'}</span>
          <span className="message-time">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
          {message.projectName && (
            <span className="message-project-chip">{message.projectName}</span>
          )}
        </div>

        <div className="message-body">
          {isPendingAssistant ? (
            <div className="typing-indicator" aria-label="DevSynapse está respondendo">
              <span></span>
              <span></span>
              <span></span>
            </div>
          ) : (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          )}
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
              <span>Raciocínio</span>
              {reasoningOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            </button>
            {reasoningOpen && (
              <div className="reasoning-body">
                <ReactMarkdown>{message.reasoningContent}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        {toolRuns.map((toolRun) => {
          const status = toolRun.status || 'proposed';
          const canRunTool = status !== 'running' && status !== 'success';

          return (
            <div key={toolRun.id} className={`message-command command-${status}`}>
              <div className="message-command-header">
                <div className="message-command-main">
                  <Terminal size={14} />
                  <div className="message-command-text">
                    <span className="command-label">Comando</span>
                    <code>{toolRun.command}</code>
                  </div>
                </div>
                <span className={`command-status-badge status-${status}`}>
                  {status === 'running' && <Loader2 size={12} className="spinner" />}
                  {status === 'success' && <CheckCircle2 size={12} />}
                  {status === 'blocked' && <ShieldAlert size={12} />}
                  {statusLabels[status]}
                </span>
                <button
                  className="execute-btn"
                  onClick={() => onExecute(message.id, toolRun.id)}
                  disabled={!canRunTool}
                  aria-label="Executar comando"
                >
                  {status === 'running' ? (
                    <Loader2 size={14} className="spinner" />
                  ) : (
                    <Play size={14} />
                  )}
                  {status === 'running' ? 'Executando...' : 'Executar'}
                </button>
              </div>
              {renderCommandReview(toolRun.command, toolRun.projectName || message.projectName)}
              {renderCommandResult(status, toolRun.result, toolRun.message)}
            </div>
          );
        })}

        {message.command && toolRuns.length === 0 && (
          <div className={`message-command command-${commandStatus}`}>
            <div className="message-command-header">
              <div className="message-command-main">
                <Terminal size={14} />
                <div className="message-command-text">
                  <span className="command-label">Comando</span>
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
                aria-label="Executar comando"
              >
                {commandStatus === 'running' ? (
                  <Loader2 size={14} className="spinner" />
                ) : (
                  <Play size={14} />
                )}
                {commandStatus === 'running' ? 'Executando...' : 'Executar'}
              </button>
            </div>
            {commandReview && (
              renderCommandReview(message.command, message.projectName)
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
          <button className="action-btn" onClick={handleCopy} aria-label="Copiar mensagem">
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
        </div>
      </div>
    </div>
  );
}
