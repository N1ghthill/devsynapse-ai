import { useEffect, useState } from 'react';
import { Shield, Save, RefreshCw, AlertCircle } from 'lucide-react';
import { adminApi } from '../api/client';
import type { AdminAuditLog, AdminUser } from '../types';

export function Admin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingUser, setSavingUser] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [usersData, logsData] = await Promise.all([
          adminApi.listUsers(),
          adminApi.listAuditLogs(),
        ]);
        setUsers(usersData.users);
        setLogs(logsData.logs);
        setError(null);
      } catch {
        setError('Failed to load admin data');
      }
      setLoading(false);
    };

    load();
  }, []);

  const updateAllowlist = (username: string, rawValue: string) => {
    setUsers((prev) =>
      prev.map((user) =>
        user.username === username
          ? {
              ...user,
              project_mutation_allowlist: rawValue
                .split('\n')
                .map((item) => item.trim())
                .filter(Boolean),
            }
          : user
      )
    );
  };

  const savePermissions = async (user: AdminUser) => {
    setSavingUser(user.username);
    try {
      const updatedUser = await adminApi.updateUserPermissions(
        user.username,
        user.project_mutation_allowlist
      );
      setUsers((prev) =>
        prev.map((entry) => (entry.username === updatedUser.username ? updatedUser : entry))
      );
      const logsData = await adminApi.listAuditLogs();
      setLogs(logsData.logs);
      setError(null);
    } catch {
      setError(`Failed to update permissions for ${user.username}`);
    }
    setSavingUser(null);
  };

  if (loading) {
    return (
      <div className="page-loading">
        <RefreshCw size={48} className="spinner" />
        <p>Loading admin workspace...</p>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Admin</h1>
      </div>

      {error && (
        <div className="message-bar message-error">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="settings-grid">
        {users.map((user) => (
          <div className="settings-card" key={user.username}>
            <div className="admin-card-header">
              <div>
                <h3>{user.username}</h3>
                <p className="admin-subtitle">
                  role={user.role} · active={String(user.is_active)}
                </p>
              </div>
              <Shield size={18} />
            </div>
            <div className="setting-field">
              <label>Project Mutation Allowlist</label>
              <textarea
                rows={6}
                value={user.project_mutation_allowlist.join('\n')}
                placeholder="One project per line"
                onChange={(e) => updateAllowlist(user.username, e.target.value)}
              />
            </div>
            <button
              className="save-btn"
              onClick={() => savePermissions(user)}
              disabled={savingUser === user.username}
            >
              {savingUser === user.username ? (
                <RefreshCw size={16} className="spinner" />
              ) : (
                <Save size={16} />
              )}
              {savingUser === user.username ? 'Saving...' : 'Save Permissions'}
            </button>
          </div>
        ))}
        <div className="settings-card">
          <div className="admin-card-header">
            <div>
              <h3>Audit Trail</h3>
              <p className="admin-subtitle">Recent administrative permission changes</p>
            </div>
            <Shield size={18} />
          </div>
          <div className="admin-audit-list">
            {logs.length === 0 ? (
              <p className="admin-subtitle">No administrative changes recorded yet.</p>
            ) : (
              logs.map((log) => {
                const projects = Array.isArray(log.details.project_mutation_allowlist)
                  ? (log.details.project_mutation_allowlist as string[])
                  : [];

                return (
                  <div className="admin-audit-item" key={log.id}>
                    <div className="admin-audit-meta">
                      <strong>{log.actor_username}</strong>
                      <span>{new Date(log.created_at).toLocaleString()}</span>
                    </div>
                    <p>
                      Updated mutation scope for <strong>{log.target_username || 'unknown'}</strong>
                    </p>
                    <p className="admin-subtitle">
                      {projects.length > 0 ? projects.join(', ') : 'No project mutations allowed'}
                    </p>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
