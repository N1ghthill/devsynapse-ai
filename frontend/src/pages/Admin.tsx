import { useEffect, useState } from 'react';
import { AlertCircle, FolderPlus, RefreshCw, Save, Shield, Trash2 } from 'lucide-react';
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
  const [deletingProject, setDeletingProject] = useState<string | null>(null);
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
        setError('Falha ao carregar dados administrativos');
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
      setError(`Falha ao atualizar permissões de ${user.username}`);
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
      setError(getErrorMessage(err, 'Falha ao registrar projeto'));
    }
    setCreatingProject(false);
  };

  const deleteProject = async (project: ProjectInfo) => {
    const confirmed = window.confirm(
      `Remover "${project.name}" do DevSynapse? Isso remove apenas o registro.`
    );
    if (!confirmed) return;

    setDeletingProject(project.name);
    try {
      await adminApi.deleteProject(project.name);
      const [usersData, logsData] = await Promise.all([
        adminApi.listUsers(),
        adminApi.listAuditLogs(),
      ]);
      setProjects((prev) => prev.filter((entry) => entry.name !== project.name));
      setUsers(usersData.users);
      setLogs(logsData.logs);
      setError(null);
    } catch {
      setError(`Falha ao remover projeto ${project.name}`);
    }
    setDeletingProject(null);
  };

  if (loading) {
    return (
      <div className="page-loading">
        <RefreshCw size={48} className="spinner" />
        <p>Carregando administração...</p>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Administração</h1>
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
                  papel={user.role} · ativo={String(user.is_active)}
                </p>
              </div>
              <Shield size={18} />
            </div>
            <div className="setting-field">
              <label>{user.role === 'admin' ? 'Escopo de mutação' : 'Allowlist de mutação'}</label>
              <textarea
                rows={6}
                value={user.project_mutation_allowlist.join('\n')}
                placeholder="Um projeto por linha"
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
                {savingUser === user.username ? 'Salvando...' : 'Salvar permissões'}
              </button>
            )}
          </div>
        ))}
        <div className="settings-card">
          <div className="admin-card-header">
            <div>
              <h3>Projetos</h3>
              <p className="admin-subtitle">
                {projects.filter((project) => project.path_exists !== false).length} ativos ·{' '}
                {projects.filter((project) => project.path_exists === false).length} ausentes
              </p>
            </div>
            <FolderPlus size={18} />
          </div>
          <div className="admin-project-list">
            {projects.map((project) => (
              <div className="admin-project-item" key={project.name}>
                <div>
                  <strong>{project.name}</strong>
                  <span>{project.path || 'Caminho disponível apenas para administradores'}</span>
                  {project.path_exists === false && (
                    <span className="admin-project-status stale">Ausente no disco</span>
                  )}
                </div>
                <button
                  className="icon-btn danger"
                  onClick={() => void deleteProject(project)}
                  disabled={deletingProject === project.name}
                  type="button"
                  title="Remover registro do projeto"
                >
                  {deletingProject === project.name ? (
                    <RefreshCw size={16} className="spinner" />
                  ) : (
                    <Trash2 size={16} />
                  )}
                </button>
              </div>
            ))}
          </div>
          <div className="admin-project-form">
            <div className="setting-field">
              <label>Nome</label>
              <input
                type="text"
                value={projectForm.name}
                onChange={(e) => setProjectForm((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="setting-field">
              <label>Caminho</label>
              <input
                type="text"
                value={projectForm.path}
                onChange={(e) => setProjectForm((prev) => ({ ...prev, path: e.target.value }))}
              />
            </div>
            <div className="admin-project-fields">
              <div className="setting-field">
                <label>Tipo</label>
                <input
                  type="text"
                  value={projectForm.type}
                  onChange={(e) =>
                    setProjectForm((prev) => ({ ...prev, type: e.target.value }))
                  }
                />
              </div>
              <div className="setting-field">
                <label>Prioridade</label>
                <select
                  value={projectForm.priority}
                  onChange={(e) =>
                    setProjectForm((prev) => ({ ...prev, priority: e.target.value }))
                  }
                >
                  <option value="high">alta</option>
                  <option value="medium">média</option>
                  <option value="low">baixa</option>
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
            {creatingProject ? 'Registrando...' : 'Registrar projeto'}
          </button>
        </div>
        <div className="settings-card">
          <div className="admin-card-header">
            <div>
              <h3>Trilha de auditoria</h3>
              <p className="admin-subtitle">Alterações administrativas recentes</p>
            </div>
            <Shield size={18} />
          </div>
          <div className="admin-audit-list">
            {logs.length === 0 ? (
              <p className="admin-subtitle">Nenhuma alteração administrativa registrada.</p>
            ) : (
              logs.map((log) => {
                const projects = Array.isArray(log.details.project_mutation_allowlist)
                  ? (log.details.project_mutation_allowlist as string[])
                  : [];
                const projectName =
                  typeof log.details.project_name === 'string' ? log.details.project_name : null;
                const actionLabel =
                  log.action === 'create_project' || log.action === 'restore_project'
                    ? 'Registrou projeto'
                    : log.action === 'delete_project'
                      ? 'Removeu projeto'
                    : 'Atualizou escopo de mutação de';

                return (
                  <div className="admin-audit-item" key={log.id}>
                    <div className="admin-audit-meta">
                      <strong>{log.actor_username}</strong>
                      <span>{new Date(log.created_at).toLocaleString()}</span>
                    </div>
                    <p>
                      {actionLabel}{' '}
                    <strong>{projectName || log.target_username || 'desconhecido'}</strong>
                    </p>
                    <p className="admin-subtitle">
                      {projectName || projects.length > 0
                        ? projectName || projects.join(', ')
                        : 'Nenhuma mutação de projeto permitida'}
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
