import { useEffect, useState } from 'react';
import { AlertCircle, FolderPlus, RefreshCw, Save, Shield } from 'lucide-react';
import { adminApi } from '../api/client';
import type { AdminAuditLog, AdminUser, ProjectInfo } from '../types';

const getErrorMessage = (error: unknown, fallback: string) => {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'detail' in error.response.data &&
    typeof error.response.data.detail === 'string'
  ) {
    return error.response.data.detail;
  }

  return fallback;
};

export function Admin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [logs, setLogs] = useState<AdminAuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingUser, setSavingUser] = useState<string | null>(null);
  const [creatingProject, setCreatingProject] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectForm, setProjectForm] = useState({
    name: '',
    path: '',
    type: 'project',
    priority: 'medium',
  });

  useEffect(() => {
    const load = async () => {
      try {
        const [usersData, logsData, projectList] = await Promise.all([
          adminApi.listUsers(),
          adminApi.listAuditLogs(),
          adminApi.listProjects(),
        ]);
        setUsers(usersData.users);
        setLogs(logsData.logs);
        setProjects(projectList);
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

  const createProject = async () => {
    setCreatingProject(true);
    try {
      const createdProject = await adminApi.createProject({
        name: projectForm.name.trim(),
        path: projectForm.path.trim(),
        type: projectForm.type.trim() || 'project',
        priority: projectForm.priority.trim() || 'medium',
      });
      const [usersData, logsData] = await Promise.all([
        adminApi.listUsers(),
        adminApi.listAuditLogs(),
      ]);
      setProjects((prev) => {
        const withoutDuplicate = prev.filter((project) => project.name !== createdProject.name);
        return [...withoutDuplicate, createdProject].sort((a, b) => a.name.localeCompare(b.name));
      });
      setUsers(usersData.users);
      setLogs(logsData.logs);
      setProjectForm({
        name: '',
        path: '',
        type: 'project',
        priority: 'medium',
      });
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to register project'));
    }
    setCreatingProject(false);
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
              <label>{user.role === 'admin' ? 'Project Mutation Scope' : 'Project Mutation Allowlist'}</label>
              <textarea
                rows={6}
                value={user.project_mutation_allowlist.join('\n')}
                placeholder="One project per line"
                readOnly={user.role === 'admin'}
                onChange={(e) => updateAllowlist(user.username, e.target.value)}
              />
            </div>
            {user.role !== 'admin' && (
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
            )}
          </div>
        ))}
        <div className="settings-card">
          <div className="admin-card-header">
            <div>
              <h3>Projects</h3>
              <p className="admin-subtitle">{projects.length} registered</p>
            </div>
            <FolderPlus size={18} />
          </div>
          <div className="admin-project-list">
            {projects.map((project) => (
              <div className="admin-project-item" key={project.name}>
                <strong>{project.name}</strong>
                <span>{project.path || 'Path available to admins only'}</span>
              </div>
            ))}
          </div>
          <div className="admin-project-form">
            <div className="setting-field">
              <label>Name</label>
              <input
                type="text"
                value={projectForm.name}
                onChange={(e) => setProjectForm((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="setting-field">
              <label>Path</label>
              <input
                type="text"
                value={projectForm.path}
                onChange={(e) => setProjectForm((prev) => ({ ...prev, path: e.target.value }))}
              />
            </div>
            <div className="admin-project-fields">
              <div className="setting-field">
                <label>Type</label>
                <input
                  type="text"
                  value={projectForm.type}
                  onChange={(e) =>
                    setProjectForm((prev) => ({ ...prev, type: e.target.value }))
                  }
                />
              </div>
              <div className="setting-field">
                <label>Priority</label>
                <select
                  value={projectForm.priority}
                  onChange={(e) =>
                    setProjectForm((prev) => ({ ...prev, priority: e.target.value }))
                  }
                >
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
              </div>
            </div>
          </div>
          <button
            className="save-btn"
            onClick={createProject}
            disabled={creatingProject || !projectForm.name.trim() || !projectForm.path.trim()}
          >
            {creatingProject ? (
              <RefreshCw size={16} className="spinner" />
            ) : (
              <FolderPlus size={16} />
            )}
            {creatingProject ? 'Registering...' : 'Register Project'}
          </button>
        </div>
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
                const projectName =
                  typeof log.details.project_name === 'string' ? log.details.project_name : null;
                const actionLabel =
                  log.action === 'create_project'
                    ? 'Registered project'
                    : 'Updated mutation scope for';

                return (
                  <div className="admin-audit-item" key={log.id}>
                    <div className="admin-audit-meta">
                      <strong>{log.actor_username}</strong>
                      <span>{new Date(log.created_at).toLocaleString()}</span>
                    </div>
                    <p>
                      {actionLabel}{' '}
                      <strong>{projectName || log.target_username || 'unknown'}</strong>
                    </p>
                    <p className="admin-subtitle">
                      {projectName || projects.length > 0
                        ? projectName || projects.join(', ')
                        : 'No project mutations allowed'}
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
