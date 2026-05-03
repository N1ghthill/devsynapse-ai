import { useEffect, useState, type FormEvent } from 'react';
import { Loader2, LogIn } from 'lucide-react';
import { authApi } from '../api/client';
import { BootstrapForm } from '../components/BootstrapForm';
import { useAuth } from '../hooks/useAuth';
import type { BootstrapStatus } from '../types';

export function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkingBootstrap, setCheckingBootstrap] = useState(true);
  const [loading, setLoading] = useState(false);
  const { completeBootstrap, login } = useAuth();
  const requiresFirstRunSetup = Boolean(bootstrapStatus?.admin_password_required);
  let buttonLabel = 'Entrar';
  if (checkingBootstrap) {
    buttonLabel = 'Verificando...';
  } else if (loading) {
    buttonLabel = 'Entrando...';
  }

  let buttonIcon = <LogIn size={20} />;
  if (loading || checkingBootstrap) {
    buttonIcon = <Loader2 size={20} className="spinner" />;
  }

  useEffect(() => {
    let cancelled = false;

    authApi
      .bootstrapStatus()
      .then((status) => {
        if (cancelled) return;
        setBootstrapStatus(status);
        if (status.admin_password_required) {
          setUsername(status.default_admin_username);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Backend ainda não está pronto');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCheckingBootstrap(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    setLoading(true);
    setError(null);

    try {
      if (!username || !password) {
        setError('Preencha todos os campos');
        return;
      }
      await login(username, password);
    } catch {
      setError('Credenciais inválidas');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <img src="/devsynapse-favicon.png" className="login-logo" alt="" />
          <h1>DevSynapse</h1>
          <p>{requiresFirstRunSetup ? 'Configuração inicial' : 'Development Synapse AI'}</p>
        </div>

        {requiresFirstRunSetup && bootstrapStatus ? (
          <BootstrapForm
            status={bootstrapStatus}
            includeAdminPassword
            submitting={loading}
            submitLabel="Concluir configuração"
            onSubmit={async (payload) => {
              setLoading(true);
              setError(null);
              try {
                await completeBootstrap(payload);
              } catch {
                setError('Falha ao concluir configuração');
              } finally {
                setLoading(false);
              }
            }}
          />
        ) : (
          <form onSubmit={handleSubmit} className="login-form">
            {error && <div className="form-error">{error}</div>}

            <div className="form-field">
              <label htmlFor="username">Usuário</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Digite seu usuário"
                autoFocus
              />
            </div>

            <div className="form-field">
              <label htmlFor="password">Senha</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Digite sua senha"
              />
            </div>

            <button type="submit" className="login-btn" disabled={loading || checkingBootstrap}>
              {buttonIcon}
              {buttonLabel}
            </button>
          </form>
        )}
        {requiresFirstRunSetup && error && <div className="form-error setup-error">{error}</div>}
      </div>
    </div>
  );
}
