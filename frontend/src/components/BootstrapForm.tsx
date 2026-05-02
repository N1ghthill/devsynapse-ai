import { useState, type FormEvent } from 'react';
import { KeyRound, Loader2 } from 'lucide-react';
import type { BootstrapCompleteRequest, BootstrapStatus } from '../types';

type BootstrapFormProps = {
  status: BootstrapStatus;
  includeAdminPassword: boolean;
  submitting: boolean;
  submitLabel: string;
  onSubmit: (payload: BootstrapCompleteRequest) => Promise<void>;
};

export function BootstrapForm({
  status,
  includeAdminPassword,
  submitting,
  submitLabel,
  onSubmit,
}: BootstrapFormProps) {
  const [adminPassword, setAdminPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [deepseekApiKey, setDeepseekApiKey] = useState('');
  const [workspaceRoot, setWorkspaceRoot] = useState(status.suggested_workspace_root);
  const [reposRoot, setReposRoot] = useState(status.suggested_repos_root);
  const [registerProjects, setRegisterProjects] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);

    if (includeAdminPassword) {
      if (adminPassword.length < 8) {
        setError('A senha deve ter pelo menos 8 caracteres');
        return;
      }
      if (adminPassword !== confirmPassword) {
        setError('As senhas não conferem');
        return;
      }
    }

    if (!status.deepseek_api_key_configured && !deepseekApiKey.trim()) {
      setError('A chave da API DeepSeek é obrigatória');
      return;
    }
    if (!reposRoot.trim()) {
      setError('A pasta de repositórios é obrigatória');
      return;
    }

    await onSubmit({
      admin_password: includeAdminPassword ? adminPassword : null,
      deepseek_api_key: deepseekApiKey.trim() || null,
      repos_root: reposRoot.trim(),
      workspace_root: workspaceRoot.trim() || null,
      register_discovered_projects: registerProjects,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="login-form">
      {error && <div className="form-error">{error}</div>}

      {includeAdminPassword && (
        <>
          <div className="form-field">
            <label htmlFor="admin-username">Usuário administrador</label>
            <input
              id="admin-username"
              type="text"
              value={status.default_admin_username}
              readOnly
            />
          </div>
          <div className="form-field">
            <label htmlFor="admin-password">Nova senha do administrador</label>
            <input
              id="admin-password"
              type="password"
              value={adminPassword}
              onChange={(event) => setAdminPassword(event.target.value)}
              placeholder="Crie uma senha local de administrador"
              autoFocus
            />
          </div>
          <div className="form-field">
            <label htmlFor="confirm-admin-password">Confirmar senha do administrador</label>
            <input
              id="confirm-admin-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Confirme a senha local de administrador"
            />
          </div>
        </>
      )}

      <div className="form-field">
        <label htmlFor="deepseek-api-key">Chave da API DeepSeek</label>
        <input
          id="deepseek-api-key"
          type="password"
          value={deepseekApiKey}
          onChange={(event) => setDeepseekApiKey(event.target.value)}
          placeholder={status.deepseek_api_key_configured ? 'Configurada' : 'sk-...'}
          autoFocus={!includeAdminPassword}
        />
      </div>

      <div className="form-field">
        <label htmlFor="workspace-root">Raiz do workspace</label>
        <input
          id="workspace-root"
          type="text"
          value={workspaceRoot}
          onChange={(event) => setWorkspaceRoot(event.target.value)}
        />
      </div>

      <div className="form-field">
        <label htmlFor="repos-root">Pasta de repositórios</label>
        <input
          id="repos-root"
          type="text"
          value={reposRoot}
          onChange={(event) => setReposRoot(event.target.value)}
        />
      </div>

      <div className="setting-field checkbox-field">
        <label>
          <input
            type="checkbox"
            checked={registerProjects}
            onChange={(event) => setRegisterProjects(event.target.checked)}
          />
          Registrar projetos Git descobertos
        </label>
      </div>

      <button type="submit" className="login-btn" disabled={submitting}>
        {submitting ? <Loader2 size={20} className="spinner" /> : <KeyRound size={20} />}
        {submitting ? 'Salvando...' : submitLabel}
      </button>
    </form>
  );
}
