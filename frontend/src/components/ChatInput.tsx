import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { Send, Loader2, Sparkles, ShieldCheck } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  autoApprove: boolean;
  isAdmin: boolean;
  onAutoApproveChange: (enabled: boolean) => void;
}

export function ChatInput({
  onSend,
  isLoading,
  autoApprove,
  isAdmin,
  onAutoApproveChange,
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey || !e.shiftKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-input-container">
      <div className="chat-run-controls">
        <button
          type="button"
          className={`auto-approve-toggle ${autoApprove ? 'active' : ''}`}
          onClick={() => onAutoApproveChange(!autoApprove)}
          aria-pressed={autoApprove}
          title={
            isAdmin
              ? 'Admin: executar comandos suportados automaticamente e registrar auditoria'
              : 'Executar comandos autorizados automaticamente e registrar auditoria'
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
        <span className="auto-approve-note">
          {autoApprove
            ? isAdmin
              ? 'Comandos suportados rodam direto; tudo fica auditado'
              : 'Comandos permitidos entram na fila automaticamente'
            : 'Você aprova cada execução'}
        </span>
      </div>
      <div className="chat-input-wrapper">
        <Sparkles size={18} className="input-icon" />
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Peça uma análise, refatoração, teste ou comando local..."
          rows={1}
          disabled={isLoading}
        />
        <button
          className="send-btn"
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          title="Enviar mensagem"
        >
          {isLoading ? (
            <Loader2 size={20} className="spinner" />
          ) : (
            <Send size={20} />
          )}
        </button>
      </div>
    </div>
  );
}
