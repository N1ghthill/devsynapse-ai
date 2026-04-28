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
        setError('Password must be at least 8 characters');
        return;
      }
      if (adminPassword !== confirmPassword) {
        setError('Passwords do not match');
        return;
      }
    }

    if (!status.deepseek_api_key_configured && !deepseekApiKey.trim()) {
      setError('DeepSeek API key is required');
      return;
    }
    if (!reposRoot.trim()) {
      setError('Repository folder is required');
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
            <label htmlFor="admin-username">Admin Username</label>
            <input
              id="admin-username"
              type="text"
              value={status.default_admin_username}
              readOnly
            />
          </div>
          <div className="form-field">
            <label htmlFor="admin-password">New Admin Password</label>
            <input
              id="admin-password"
              type="password"
              value={adminPassword}
              onChange={(event) => setAdminPassword(event.target.value)}
              placeholder="Create a local admin password"
              autoFocus
            />
          </div>
          <div className="form-field">
            <label htmlFor="confirm-admin-password">Confirm Admin Password</label>
            <input
              id="confirm-admin-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Confirm your local admin password"
            />
          </div>
        </>
      )}

      <div className="form-field">
        <label htmlFor="deepseek-api-key">DeepSeek API Key</label>
        <input
          id="deepseek-api-key"
          type="password"
          value={deepseekApiKey}
          onChange={(event) => setDeepseekApiKey(event.target.value)}
          placeholder={status.deepseek_api_key_configured ? 'Configured' : 'sk-...'}
          autoFocus={!includeAdminPassword}
        />
      </div>

      <div className="form-field">
        <label htmlFor="workspace-root">Workspace Root</label>
        <input
          id="workspace-root"
          type="text"
          value={workspaceRoot}
          onChange={(event) => setWorkspaceRoot(event.target.value)}
        />
      </div>

      <div className="form-field">
        <label htmlFor="repos-root">Repository Folder</label>
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
          Register discovered Git projects
        </label>
      </div>

      <button type="submit" className="login-btn" disabled={submitting}>
        {submitting ? <Loader2 size={20} className="spinner" /> : <KeyRound size={20} />}
        {submitting ? 'Saving...' : submitLabel}
      </button>
    </form>
  );
}
