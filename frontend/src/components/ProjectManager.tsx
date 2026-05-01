import { useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  FolderPlus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import type { ProjectInfo } from '../types';

export type ProjectCreateDraft = {
  name: string;
  path: string;
  type: string;
  priority: string;
  createDirectory: boolean;
};

type ProjectStatusFilter = 'all' | 'active' | 'stale';

interface ProjectManagerProps {
  isAdmin: boolean;
  projects: ProjectInfo[];
  currentScopeProject: string | null;
  projectScopeLocked: boolean;
  lockedProject: string | null;
  projectError: string | null;
  creatingProject: boolean;
  deletingProject: string | null;
  refreshingProjects: boolean;
  onClose: () => void;
  onRefresh: () => Promise<void>;
  onSelectProject: (projectName: string) => void;
  onCreateProject: (draft: ProjectCreateDraft) => Promise<boolean>;
  onDeleteProject: (project: ProjectInfo) => Promise<void>;
}

const defaultDraft = (): ProjectCreateDraft => ({
  name: '',
  path: '',
  type: 'project',
  priority: 'medium',
  createDirectory: false,
});

export function ProjectManager({
  isAdmin,
  projects,
  currentScopeProject,
  projectScopeLocked,
  lockedProject,
  projectError,
  creatingProject,
  deletingProject,
  refreshingProjects,
  onClose,
  onRefresh,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
}: ProjectManagerProps) {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProjectStatusFilter>('active');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [draft, setDraft] = useState<ProjectCreateDraft>(() => defaultDraft());

  const normalizedQuery = query.trim().toLowerCase();
  const visibleProjects = useMemo(
    () =>
      projects.filter((project) => {
        const matchesQuery =
          !normalizedQuery ||
          project.name.toLowerCase().includes(normalizedQuery) ||
          (project.path || '').toLowerCase().includes(normalizedQuery) ||
          project.type.toLowerCase().includes(normalizedQuery);
        const isMissing = project.path_exists === false;
        const matchesStatus =
          statusFilter === 'all' ||
          (statusFilter === 'active' && !isMissing) ||
          (statusFilter === 'stale' && isMissing);
        return matchesQuery && matchesStatus;
      }),
    [normalizedQuery, projects, statusFilter]
  );

  const selectProject = (projectName: string) => {
    onSelectProject(projectName);
    onClose();
  };

  const submitProject = async () => {
    if (!draft.name.trim() || creatingProject || !isAdmin) return;

    const created = await onCreateProject({
      ...draft,
      name: draft.name.trim(),
      path: draft.path.trim(),
      type: draft.type.trim() || 'project',
      priority: draft.priority.trim() || 'medium',
    });

    if (created) {
      setDraft(defaultDraft());
      setShowCreateForm(false);
      onClose();
    }
  };

  const renderProjectCard = (project: ProjectInfo) => {
    const isSelected = project.name === currentScopeProject;
    const isMissing = project.path_exists === false;
    const opensNewConversation = projectScopeLocked && project.name !== lockedProject;

    return (
      <article
        key={project.name}
        className={`project-manager-card ${isSelected ? 'active' : ''} ${
          isMissing ? 'stale' : ''
        }`}
      >
        <div className="project-manager-card-head">
          <div>
            <h3>{project.name}</h3>
            <div className="project-manager-meta">
              <span>{project.type}</span>
              <span>{project.access_count || 0} acessos</span>
            </div>
          </div>
          <span className={isMissing ? 'project-status-chip stale' : 'project-status-chip'}>
            {isMissing ? <AlertCircle size={13} /> : <CheckCircle2 size={13} />}
            {isMissing ? 'Ausente' : 'Ativo'}
          </span>
        </div>

        <p className="project-manager-path">
          {project.path || 'Caminho visível apenas para administradores'}
        </p>

        <div className="project-manager-footer">
          <span>
            {opensNewConversation
              ? 'Trocar de projeto cria uma nova conversa.'
              : 'Pronto para usar nesta conversa.'}
          </span>
          <span className="project-manager-date">
            {project.last_accessed
              ? new Date(project.last_accessed).toLocaleDateString()
              : 'n/d'}
          </span>
        </div>

        <div className="project-manager-actions">
          <button
            type="button"
            className="project-action-btn"
            onClick={() => selectProject(project.name)}
          >
            {isSelected ? 'Selecionado' : opensNewConversation ? 'Abrir conversa' : 'Usar projeto'}
          </button>
          {isAdmin && (
            <button
              type="button"
              className="project-action-icon danger"
              onClick={() => void onDeleteProject(project)}
              disabled={deletingProject === project.name}
              aria-label={`Remover ${project.name}`}
            >
              {deletingProject === project.name ? (
                <RefreshCw size={15} className="spinner" />
              ) : (
                <Trash2 size={15} />
              )}
            </button>
          )}
        </div>
      </article>
    );
  };

  const renderProjectCreateForm = () => (
    <aside className="project-manager-create">
      <div className="project-create-header">
        <div>
          <h3>Adicionar projeto</h3>
          <p>Registre uma pasta existente ou crie uma nova no diretório de repositórios.</p>
        </div>
        <button
          type="button"
          className="project-action-icon"
          onClick={() => setShowCreateForm(false)}
          aria-label="Fechar formulário"
        >
          <X size={15} />
        </button>
      </div>
      <div className="project-create-field">
        <label htmlFor="project-create-name">Nome</label>
        <input
          id="project-create-name"
          type="text"
          value={draft.name}
          onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
          placeholder="nome-do-projeto"
        />
      </div>
      <div className="project-create-field">
        <label htmlFor="project-create-path">Caminho</label>
        <input
          id="project-create-path"
          type="text"
          value={draft.path}
          onChange={(event) => setDraft((current) => ({ ...current, path: event.target.value }))}
          placeholder="/home/user/repos/projeto"
        />
      </div>
      <div className="project-create-grid">
        <div className="project-create-field">
          <label htmlFor="project-create-type">Tipo</label>
          <input
            id="project-create-type"
            type="text"
            value={draft.type}
            onChange={(event) => setDraft((current) => ({ ...current, type: event.target.value }))}
          />
        </div>
        <div className="project-create-field">
          <label htmlFor="project-create-priority">Prioridade</label>
          <select
            id="project-create-priority"
            value={draft.priority}
            onChange={(event) =>
              setDraft((current) => ({ ...current, priority: event.target.value }))
            }
          >
            <option value="high">Alta</option>
            <option value="medium">Média</option>
            <option value="low">Baixa</option>
          </select>
        </div>
      </div>
      <label className="project-create-checkbox">
        <input
          type="checkbox"
          checked={draft.createDirectory}
          onChange={(event) =>
            setDraft((current) => ({ ...current, createDirectory: event.target.checked }))
          }
        />
        <span>Criar diretório se ele ainda não existir</span>
      </label>
      <button
        type="button"
        className="project-create-primary"
        onClick={() => void submitProject()}
        disabled={creatingProject || !draft.name.trim()}
      >
        {creatingProject ? (
          <RefreshCw size={16} className="spinner" />
        ) : (
          <FolderPlus size={16} />
        )}
        <span>{creatingProject ? 'Salvando' : 'Adicionar projeto'}</span>
      </button>
    </aside>
  );

  return (
    <div className="project-manager-backdrop" role="presentation">
      <section
        className="project-manager-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-manager-title"
      >
        <div className="project-manager-header">
          <div>
            <span className="workspace-kicker">Projetos</span>
            <h2 id="project-manager-title">Escolher projeto</h2>
            <p>
              {projectScopeLocked
                ? `Esta conversa está travada em ${lockedProject}. Outro projeto abre uma nova conversa.`
                : 'Escolha um projeto para fixar o contexto da próxima mensagem.'}
            </p>
          </div>
          <div className="project-manager-header-actions">
            <button
              type="button"
              className="project-action-icon"
              onClick={() => void onRefresh()}
              disabled={refreshingProjects}
              aria-label="Atualizar projetos"
            >
              <RefreshCw size={16} className={refreshingProjects ? 'spinner' : ''} />
            </button>
            <button
              type="button"
              className="project-action-icon"
              onClick={onClose}
              aria-label="Fechar projetos"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="project-current-panel">
          <div>
            <span className="context-label">Projeto atual</span>
            <strong>{currentScopeProject || 'Escopo global'}</strong>
          </div>
          {isAdmin && (
            <button
              type="button"
              className="project-create-toggle"
              onClick={() => setShowCreateForm((visible) => !visible)}
            >
              <FolderPlus size={15} />
              <span>{showCreateForm ? 'Ocultar formulário' : 'Adicionar projeto'}</span>
            </button>
          )}
        </div>

        {projectError && (
          <div className="message-bar message-error project-manager-error">
            <AlertCircle size={16} />
            {projectError}
          </div>
        )}

        <div className="project-manager-toolbar">
          <div className="project-manager-search">
            <Search size={15} />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar projeto"
              aria-label="Buscar projeto"
            />
          </div>
          <div className="project-status-tabs" aria-label="Filtrar projetos">
            {[
              ['active', 'Ativos'],
              ['all', 'Todos'],
              ['stale', 'Ausentes'],
            ].map(([status, label]) => (
              <button
                type="button"
                key={status}
                className={statusFilter === status ? 'active' : ''}
                onClick={() => setStatusFilter(status as ProjectStatusFilter)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className={`project-manager-body ${showCreateForm && isAdmin ? 'with-form' : ''}`}>
          <div className="project-manager-list">
            {visibleProjects.length > 0 ? (
              visibleProjects.map(renderProjectCard)
            ) : (
              <div className="project-manager-empty">
                {normalizedQuery
                  ? 'Nenhum projeto corresponde à busca.'
                  : 'Nenhum projeto ativo encontrado.'}
              </div>
            )}
          </div>

          {isAdmin && showCreateForm && renderProjectCreateForm()}
        </div>
      </section>
    </div>
  );
}
