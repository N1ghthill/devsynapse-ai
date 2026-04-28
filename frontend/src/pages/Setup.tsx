import { useEffect, useState } from 'react';
import { Cpu, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { BootstrapForm } from '../components/BootstrapForm';
import { useAuth } from '../hooks/useAuth';
import type { BootstrapStatus } from '../types';

export function Setup() {
  const { auth, completeBootstrap } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState<BootstrapStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    authApi
      .bootstrapStatus()
      .then((nextStatus) => {
        if (cancelled) return;
        setStatus(nextStatus);
        if (!nextStatus.requires_setup) {
          navigate('/chat', { replace: true });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Failed to load setup status');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [navigate]);

  if (loading) {
    return (
      <div className="page-loading">
        <RefreshCw size={48} className="spinner" />
        <p>Loading setup...</p>
      </div>
    );
  }

  if (auth.user?.role !== 'admin') {
    return (
      <div className="page-error">
        <Cpu size={48} />
        <p>Admin access is required.</p>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Setup</h1>
      </div>

      {error && <div className="message-bar message-error">{error}</div>}

      {status && (
        <div className="settings-card setup-card">
          <BootstrapForm
            status={status}
            includeAdminPassword={status.admin_password_required}
            submitting={saving}
            submitLabel="Complete Setup"
            onSubmit={async (payload) => {
              setSaving(true);
              setError(null);
              try {
                await completeBootstrap(payload);
                navigate('/chat', { replace: true });
              } catch {
                setError('Failed to complete setup');
              } finally {
                setSaving(false);
              }
            }}
          />
        </div>
      )}
    </div>
  );
}
