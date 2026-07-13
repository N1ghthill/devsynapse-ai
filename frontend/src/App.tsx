import {
  Activity,
  Bot,
  CheckCircle2,
  CircleAlert,
  FolderGit2,
  FolderPlus,
  GitBranch,
  GitPullRequestArrow,
  HeartHandshake,
  HeartPulse,
  KeyRound,
  Link2,
  MessageSquareText,
  RotateCw,
  Search,
  Send,
  Square,
  Settings,
  ShieldCheck,
} from 'lucide-react'
import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import { relaunch } from '@tauri-apps/plugin-process'
import { check } from '@tauri-apps/plugin-updater'
import type { ReactNode } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type {
  AppDistribution,
  AppHealth,
  CommitPreviewResult,
  CommitPreviewValidationResult,
  ConversationEvent,
  ConversationResponse,
  GitStatusCounts,
  GitStatusFile,
  GitStatusResult,
  GitHubAccountStatusResult,
  GitHubAuthPollResult,
  GitHubAuthStartResult,
  GitHubRepositoryListResult,
  GitHubRepositorySummary,
  LlmModelDiscoverResult,
  LlmProviderStatusResult,
  OperationListResponse,
  OperationRunResponse,
  ProjectConnectResult,
  ProjectListResult,
  ProjectRegisterResult,
  ProjectSummary,
} from './contracts/ipc'

type SectionId = 'conversation' | 'projects' | 'activity' | 'settings'

type NavItem = {
  id: SectionId
  label: string
  icon: typeof MessageSquareText
}

const navItems: NavItem[] = [
  { id: 'conversation', label: 'Conversation', icon: MessageSquareText },
  { id: 'projects', label: 'Projects', icon: FolderGit2 },
  { id: 'activity', label: 'Activity', icon: Activity },
  { id: 'settings', label: 'Settings', icon: Settings },
]

const readinessItems = [
  'Desktop shell restored without historical admin surfaces',
  'GitHub connection reserved for guided authentication',
  'Typed operations required before repository mutation',
  'Backend sidecar lifecycle connected through private health checks',
]

const browserPreviewHealth: AppHealth = {
  status: 'preview',
  version: __APP_VERSION__,
  backend: {
    status: 'browser_preview',
    message: 'Tauri IPC is available only in the desktop shell.',
  },
}

const selectedProjectStorageKey = 'devsynapse.selectedProject'
const contributionUrl = 'https://github.com/sponsors/N1ghthill'
const productionUpdateEndpoint =
  'https://github.com/N1ghthill/devsynapse-ai/releases/latest/download/latest.json'
const latestReleaseUrl = 'https://github.com/N1ghthill/devsynapse-ai/releases/latest'

const fallbackLlmProviders = [
  {
    id: 'openrouter',
    label: 'OpenRouter',
    configured: false,
    selected: true,
    model: 'openrouter/free',
    defaultModel: 'openrouter/free',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    configured: false,
    selected: false,
    model: 'deepseek-v4-pro',
    defaultModel: 'deepseek-v4-pro',
  },
]

type ConversationMessage = {
  id: string
  role: 'assistant' | 'user' | 'system'
  text: string
}

type ProjectEvidence = {
  operationName: string
  result: Record<string, unknown>
}

type UpdateStatusKind =
  | 'idle'
  | 'checking'
  | 'current'
  | 'manual'
  | 'available'
  | 'downloading'
  | 'installing'
  | 'failed'

type UpdateStatus = {
  kind: UpdateStatusKind
  currentVersion: string
  availableVersion?: string | null
  message: string
  downloadedBytes?: number
  totalBytes?: number | null
}

function requestId(prefix: string) {
  if (globalThis.crypto?.randomUUID) {
    return `${prefix}-${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function initialUpdateStatus(): UpdateStatus {
  return {
    kind: 'idle',
    currentVersion: __APP_VERSION__,
    message: 'Production builds check signed update artifacts.',
  }
}

function App() {
  const [activeSection, setActiveSection] = useState<SectionId>('conversation')
  const [health, setHealth] = useState<AppHealth>(browserPreviewHealth)

  const activeTitle = useMemo(
    () => navItems.find((item) => item.id === activeSection)?.label ?? 'Conversation',
    [activeSection],
  )

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await invoke<AppHealth>('app_health'))
    } catch {
      setHealth(browserPreviewHealth)
    }
  }, [])

  const restartBackend = useCallback(async () => {
    try {
      setHealth(await invoke<AppHealth>('restart_backend'))
    } catch {
      setHealth(browserPreviewHealth)
    }
  }, [])

  useEffect(() => {
    const firstRefresh = window.setTimeout(() => {
      void refreshHealth()
    }, 0)
    const interval = window.setInterval(refreshHealth, 4000)
    return () => {
      window.clearTimeout(firstRefresh)
      window.clearInterval(interval)
    }
  }, [refreshHealth])

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Primary">
        <div className="brand">
          <img className="brand-mark" src="/devsynapse-icon.png" alt="" aria-hidden="true" />
          <div>
            <strong>DevSynapse AI</strong>
            <span>Repository assistant</span>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon
            const selected = item.id === activeSection

            return (
              <button
                className="nav-item"
                data-selected={selected}
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                type="button"
              >
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="shell-status">
            <HeartPulse size={17} aria-hidden="true" />
            <div>
              <strong>Backend {health.backend.status.replaceAll('_', ' ')}</strong>
              <span>Version {health.version}</span>
            </div>
          </div>

          <div className="creator-panel">
            <img src="/ruas-logo.webp" alt="Ruas.dev" />
            <a className="support-button" href={contributionUrl} target="_blank" rel="noreferrer">
              <HeartHandshake size={16} aria-hidden="true" />
              <span>Contribuir</span>
            </a>
          </div>
        </div>
      </aside>

      <section className="workspace" aria-labelledby="workspace-title">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Packaged desktop target</p>
            <h1 id="workspace-title">{activeTitle}</h1>
          </div>
          <div className="risk-badge">
            <ShieldCheck size={17} aria-hidden="true" />
            <span>No repository mutation</span>
          </div>
        </header>

        {activeSection === 'conversation' && (
          <ConversationPanel health={health} onOpenSettings={() => setActiveSection('settings')} />
        )}
        {activeSection === 'projects' && <ProjectsPanel />}
        {activeSection === 'activity' && (
          <ActivityPanel health={health} onRestartBackend={restartBackend} />
        )}
        {activeSection === 'settings' && <SettingsPanel />}
      </section>
    </main>
  )
}

function ConversationPanel({
  health,
  onOpenSettings,
}: {
  health: AppHealth
  onOpenSettings: () => void
}) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ConversationMessage[]>([
    {
      id: 'intro',
      role: 'assistant',
      text:
        'I can help inspect projects, explain GitHub state and prepare safe actions. ' +
        'Repository-changing workflows will appear only after typed operations, previews and approvals are connected.',
    },
  ])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [llmReady, setLlmReady] = useState<boolean | null>(null)

  const appendEvents = useCallback((events: ConversationEvent[]) => {
    for (const event of events) {
      if (event.type === 'response.delta' && event.delta) {
        setMessages((current) => [
          ...current,
          {
            id: event.requestId,
            role: 'assistant',
            text: event.delta ?? '',
          },
        ])
      }
      if (event.type === 'response.failed') {
        setMessages((current) => [
          ...current,
          {
            id: event.requestId,
            role: 'system',
            text: event.error ?? 'Request failed',
          },
        ])
      }
    }
  }, [])

  const ensureConversation = useCallback(async () => {
    if (conversationId) {
      return conversationId
    }
    const response = await invoke<ConversationResponse>('conversation_start', {
      args: { requestId: requestId('start') },
    })
    setConversationId(response.conversationId)
    appendEvents(response.events)
    return response.conversationId
  }, [appendEvents, conversationId])

  const sendMessage = useCallback(async () => {
    const message = draft.trim()
    if (!message || busy) {
      return
    }
    setBusy(true)
    setDraft('')
    const userMessageId = requestId('user')
    setMessages((current) => [...current, { id: userMessageId, role: 'user', text: message }])

    try {
      const activeConversationId = await ensureConversation()
      const response = await invoke<ConversationResponse>('conversation_send', {
        args: {
          requestId: requestId('send'),
          conversationId: activeConversationId,
          message,
        },
      })
      appendEvents(response.events)
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: requestId('error'),
          role: 'system',
          text: error instanceof Error ? error.message : String(error),
        },
      ])
    } finally {
      setBusy(false)
    }
  }, [appendEvents, busy, draft, ensureConversation])

  const cancelConversation = useCallback(async () => {
    if (!conversationId) {
      return
    }
    setBusy(false)
    try {
      const response = await invoke<ConversationResponse>('conversation_cancel', {
        args: {
          requestId: requestId('cancel'),
          conversationId,
        },
      })
      appendEvents(response.events)
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: requestId('cancel-error'),
          role: 'system',
          text: error instanceof Error ? error.message : String(error),
        },
      ])
    }
  }, [appendEvents, conversationId])

  useEffect(() => {
    let active = true
    invoke<OperationRunResponse<LlmProviderStatusResult>>('operation_run', {
      args: {
        requestId: requestId('conversation-llm-status'),
        operationName: 'llm.provider.status',
        input: {},
      },
    })
      .then((response) => {
        if (active) {
          setLlmReady(response.result.ready)
        }
      })
      .catch(() => {
        if (active) {
          setLlmReady(null)
        }
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="content-grid">
      <section className="conversation-surface" aria-label="Conversation preview">
        {llmReady === false && (
          <div className="setup-callout">
            <KeyRound size={18} aria-hidden="true" />
            <div>
              <strong>AI provider required</strong>
              <span>Connect OpenRouter and choose a model before asking DevSynapse to analyze repositories.</span>
            </div>
            <button className="text-button" onClick={onOpenSettings} type="button">
              Open Settings
            </button>
          </div>
        )}
        <div className="message-list">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="avatar">
                {message.role === 'user' ? (
                  <MessageSquareText size={18} aria-hidden="true" />
                ) : (
                  <Bot size={18} aria-hidden="true" />
                )}
              </div>
              <div>
                <span className="message-author">
                  {message.role === 'user' ? 'You' : message.role === 'system' ? 'System' : 'DevSynapse'}
                </span>
                <p>{message.text}</p>
              </div>
            </article>
          ))}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault()
            void sendMessage()
          }}
        >
          <input
            aria-label="Message"
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Ask about this desktop foundation"
            value={draft}
          />
          {busy ? (
            <button className="icon-button" onClick={cancelConversation} title="Cancel" type="button">
              <Square size={16} aria-hidden="true" />
            </button>
          ) : (
            <button className="icon-button" disabled={!draft.trim()} title="Send" type="submit">
              <Send size={16} aria-hidden="true" />
            </button>
          )}
        </form>
      </section>

      <aside className="side-panel" aria-label="Readiness">
        <h2>Foundation checklist</h2>
        <BackendStatus health={health} />
        <ul className="check-list">
          {readinessItems.map((item) => (
            <li key={item}>
              <CheckCircle2 size={17} aria-hidden="true" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}

function ProjectsPanel() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [repositories, setRepositories] = useState<GitHubRepositorySummary[]>([])
  const [selectedProject, setSelectedProject] = useState<string | null>(() => {
    try {
      return window.localStorage.getItem(selectedProjectStorageKey)
    } catch {
      return null
    }
  })
  const [selectedRepository, setSelectedRepository] = useState<string>('')
  const [repositoryQuery, setRepositoryQuery] = useState('')
  const [projectEvidence, setProjectEvidence] = useState<ProjectEvidence | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [repositoryBusy, setRepositoryBusy] = useState(false)

  const selectProject = useCallback((projectName: string) => {
    setSelectedProject(projectName)
    try {
      window.localStorage.setItem(selectedProjectStorageKey, projectName)
    } catch {
      // Local storage can be unavailable in restricted browser contexts.
    }
  }, [])

  const loadProjects = useCallback(async () => {
    try {
      setError(null)
      const response = await invoke<OperationRunResponse<ProjectListResult>>('operation_run', {
        args: {
          requestId: requestId('project-list'),
          operationName: 'project.list',
          input: {},
        },
      })
      setProjects(response.result.projects)
      const storedSelection = response.result.projects.find(
        (project) => project.name === selectedProject,
      )
      if (storedSelection) {
        selectProject(storedSelection.name)
      } else if (response.result.projects[0]) {
        selectProject(response.result.projects[0].name)
      }
    } catch (operationError) {
      setError(operationError instanceof Error ? operationError.message : String(operationError))
    }
  }, [selectProject, selectedProject])

  const upsertProject = useCallback((project: ProjectSummary) => {
    setProjects((current) => {
      const existing = current.find((item) => item.name === project.name)
      if (existing) {
        return current.map((item) => (item.name === project.name ? project : item))
      }
      return [...current, project].sort((left, right) => left.name.localeCompare(right.name))
    })
  }, [])

  const selectedProjectRecord = useMemo(
    () => projects.find((project) => project.name === selectedProject) ?? null,
    [projects, selectedProject],
  )

  const inspectProject = useCallback(
    async (projectName: string, operationName: string) => {
      try {
        setError(null)
        const response = await invoke<OperationRunResponse<Record<string, unknown>>>('operation_run', {
          args: {
            requestId: requestId(operationName),
            operationName,
            input: { projectName },
          },
        })
        selectProject(projectName)
        setProjectEvidence({ operationName, result: response.result })
      } catch (operationError) {
        setError(operationError instanceof Error ? operationError.message : String(operationError))
      }
    },
    [selectProject],
  )

  const chooseProjectFolder = useCallback(async () => {
    try {
      setError(null)
      const selectedPath = await open({
        directory: true,
        multiple: false,
        title: 'Choose project folder',
      })
      if (typeof selectedPath !== 'string') {
        return
      }
      const response = await invoke<OperationRunResponse<ProjectRegisterResult>>('operation_run', {
        args: {
          requestId: requestId('project-register'),
          operationName: 'project.register',
          input: { path: selectedPath },
        },
      })
      upsertProject(response.result.project)
      selectProject(response.result.project.name)
      setProjectEvidence({
        operationName: 'project.register',
        result: response.result.project as unknown as Record<string, unknown>,
      })
    } catch (operationError) {
      setError(operationError instanceof Error ? operationError.message : String(operationError))
    }
  }, [selectProject, upsertProject])

  const loadGithubRepositories = useCallback(async () => {
    setRepositoryBusy(true)
    try {
      setError(null)
      const response = await invoke<OperationRunResponse<GitHubRepositoryListResult>>('operation_run', {
        args: {
          requestId: requestId('github-repository-list'),
          operationName: 'github.repository.list',
          input: { query: repositoryQuery, limit: 50 },
        },
      })
      setRepositories(response.result.repositories)
      const currentSelection = response.result.repositories.find(
        (repository) => repository.fullName === selectedRepository,
      )
      if (!currentSelection && response.result.repositories[0]) {
        setSelectedRepository(response.result.repositories[0].fullName)
      }
      setProjectEvidence({
        operationName: 'github.repository.list',
        result: response.result as unknown as Record<string, unknown>,
      })
    } catch (operationError) {
      setError(operationError instanceof Error ? operationError.message : String(operationError))
    } finally {
      setRepositoryBusy(false)
    }
  }, [repositoryQuery, selectedRepository])

  const connectSelectedRepository = useCallback(async () => {
    const repository = repositories.find((item) => item.fullName === selectedRepository)
    if (!selectedProject || !repository) {
      return
    }
    setRepositoryBusy(true)
    try {
      setError(null)
      const response = await invoke<OperationRunResponse<ProjectConnectResult>>('operation_run', {
        args: {
          requestId: requestId('project-connect'),
          operationName: 'project.connect',
          input: { projectName: selectedProject, repository },
        },
      })
      setProjects((current) =>
        current.map((project) =>
          project.name === selectedProject
            ? { ...project, repository: response.result.repository }
            : project,
        ),
      )
      setProjectEvidence({
        operationName: 'project.connect',
        result: response.result as unknown as Record<string, unknown>,
      })
    } catch (operationError) {
      setError(operationError instanceof Error ? operationError.message : String(operationError))
    } finally {
      setRepositoryBusy(false)
    }
  }, [repositories, selectedProject, selectedRepository])

  const validateCommitPreview = useCallback(async (preview: CommitPreviewResult) => {
    try {
      setError(null)
      const response = await invoke<OperationRunResponse<CommitPreviewValidationResult>>('operation_run', {
        args: {
          requestId: requestId('commit-preview-validate'),
          operationName: 'commit.preview.validate',
          input: {
            projectName: preview.projectName,
            stateFingerprint: preview.stateFingerprint,
          },
        },
      })
      setProjectEvidence({
        operationName: 'commit.preview.validate',
        result: response.result as unknown as Record<string, unknown>,
      })
    } catch (operationError) {
      setError(operationError instanceof Error ? operationError.message : String(operationError))
    }
  }, [])

  useEffect(() => {
    const initialLoad = window.setTimeout(() => {
      void loadProjects()
    }, 0)
    return () => window.clearTimeout(initialLoad)
  }, [loadProjects])

  return (
    <section className="projects-layout" aria-label="Projects">
      <div className="project-list">
        <div className="panel-header">
          <h2>Local projects</h2>
          <div className="panel-actions">
            <button className="icon-button" onClick={chooseProjectFolder} title="Add project folder" type="button">
              <FolderPlus size={16} aria-hidden="true" />
            </button>
            <button className="icon-button" onClick={loadProjects} title="Refresh projects" type="button">
              <RotateCw size={16} aria-hidden="true" />
            </button>
          </div>
        </div>

        {error && <p className="inline-error">{error}</p>}

        {projects.length === 0 ? (
          <div className="empty-inline">
            <FolderGit2 size={28} aria-hidden="true" />
            <span>No configured Git projects were found.</span>
          </div>
        ) : (
          projects.map((project) => (
            <article className="project-row" data-selected={project.name === selectedProject} key={project.name}>
              <div>
                <strong>{project.name}</strong>
                <span>{project.path}</span>
                {project.repository && <span>{project.repository.fullName}</span>}
              </div>
              <div className="project-actions">
                <button
                  className="text-button"
                  onClick={() => void inspectProject(project.name, 'repository.snapshot')}
                  type="button"
                >
                  Snapshot
                </button>
                <button
                  className="text-button"
                  onClick={() => void inspectProject(project.name, 'commit.preview')}
                  type="button"
                >
                  Preview
                </button>
                <button
                  className="text-button"
                  onClick={() => void inspectProject(project.name, 'git.status')}
                  type="button"
                >
                  Status
                </button>
              </div>
            </article>
          ))
        )}
      </div>

      <div className="evidence-panel">
        <div className="panel-header">
          <h2>Read-only evidence</h2>
          <GitBranch size={18} aria-hidden="true" />
        </div>
        <div className="remote-connect">
          <div>
            <strong>GitHub repository</strong>
            <span>
              {selectedProjectRecord?.repository
                ? selectedProjectRecord.repository.fullName
                : 'No remote repository associated.'}
            </span>
          </div>
          <div className="field-row">
            <Search size={16} aria-hidden="true" />
            <input
              aria-label="Repository search"
              onChange={(event) => setRepositoryQuery(event.target.value)}
              placeholder="owner/name"
              type="search"
              value={repositoryQuery}
            />
            <button
              className="icon-button"
              disabled={repositoryBusy}
              onClick={loadGithubRepositories}
              title="Load GitHub repositories"
              type="button"
            >
              <RotateCw size={16} aria-hidden="true" />
            </button>
          </div>
          <div className="field-row">
            <GitPullRequestArrow size={16} aria-hidden="true" />
            <select
              aria-label="GitHub repository"
              disabled={repositories.length === 0}
              onChange={(event) => setSelectedRepository(event.target.value)}
              value={selectedRepository}
            >
              {repositories.length === 0 ? (
                <option value="">Load repositories</option>
              ) : (
                repositories.map((repository) => (
                  <option key={repository.fullName} value={repository.fullName}>
                    {repository.fullName}
                  </option>
                ))
              )}
            </select>
            <button
              className="icon-button"
              disabled={!selectedProject || !selectedRepository || repositoryBusy}
              onClick={connectSelectedRepository}
              title="Associate selected repository"
              type="button"
            >
              <Link2 size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
        <ProjectEvidenceView evidence={projectEvidence} onValidatePreview={validateCommitPreview} />
      </div>
    </section>
  )
}

function ProjectEvidenceView({
  evidence,
  onValidatePreview,
}: {
  evidence: ProjectEvidence | null
  onValidatePreview: (preview: CommitPreviewResult) => void
}) {
  if (!evidence) {
    return (
      <div className="evidence-empty">
        <GitBranch size={24} aria-hidden="true" />
        <span>No project evidence loaded.</span>
      </div>
    )
  }

  if (evidence.operationName === 'git.status') {
    const status = evidence.result as unknown as GitStatusResult
    return (
      <GitEvidenceCard
        branch={status.branch}
        counts={status.counts}
        files={status.files}
        fingerprint={status.stateFingerprint}
        headCommit={status.headCommit}
        isClean={status.isClean}
        path={status.path}
        title="Git status"
      />
    )
  }

  if (evidence.operationName === 'commit.preview') {
    const preview = evidence.result as unknown as CommitPreviewResult
    return (
      <GitEvidenceCard
        action={
          <button className="text-button" onClick={() => onValidatePreview(preview)} type="button">
            Recheck
          </button>
        }
        branch={preview.currentBranch}
        counts={preview.counts}
        files={preview.files}
        fingerprint={preview.stateFingerprint}
        headCommit={preview.headCommit}
        isClean={preview.isClean}
        path={preview.path}
        previewId={preview.previewId}
        stagedDiffStat={preview.stagedDiffStat}
        stale={preview.isStale}
        title="Commit preview"
        worktreeDiffStat={preview.worktreeDiffStat}
      />
    )
  }

  if (evidence.operationName === 'commit.preview.validate') {
    const validation = evidence.result as unknown as CommitPreviewValidationResult
    return (
      <GitEvidenceCard
        branch={validation.currentBranch}
        counts={validation.counts}
        files={validation.files}
        fingerprint={validation.currentStateFingerprint}
        headCommit={validation.headCommit}
        isClean={validation.isClean}
        path={validation.path}
        previewId={validation.currentPreviewId}
        stale={validation.isStale}
        title="Preview validation"
      />
    )
  }

  return <pre>{JSON.stringify(evidence.result, null, 2)}</pre>
}

function GitEvidenceCard({
  action,
  branch,
  counts,
  files,
  fingerprint,
  headCommit,
  isClean,
  path,
  previewId,
  stagedDiffStat,
  stale,
  title,
  worktreeDiffStat,
}: {
  action?: ReactNode
  branch?: string | null
  counts: GitStatusCounts
  files: GitStatusFile[]
  fingerprint: string
  headCommit?: string | null
  isClean: boolean
  path: string
  previewId?: string
  stagedDiffStat?: string
  stale?: boolean
  title: string
  worktreeDiffStat?: string
}) {
  return (
    <div className="git-evidence-card">
      <div className="git-evidence-header">
        <div>
          <strong>{title}</strong>
          <span>{path}</span>
        </div>
        <div className="evidence-actions">
          {typeof stale === 'boolean' && (
            <div className="status-pill" data-ready={!stale}>
              {stale ? <CircleAlert size={14} aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}
              <span>{stale ? 'Stale' : 'Fresh'}</span>
            </div>
          )}
          {action}
        </div>
      </div>

      <div className="evidence-meta">
        <span>Branch {branch ?? 'unknown'}</span>
        <span>Head {headCommit ?? 'unknown'}</span>
        {previewId && <span>Preview {previewId}</span>}
        <span>{isClean ? 'Clean' : 'Changed'}</span>
      </div>

      <CountStrip counts={counts} />

      <div className="fingerprint-row">
        <span>State</span>
        <code>{fingerprint}</code>
      </div>

      <FileList files={files} />

      {(stagedDiffStat || worktreeDiffStat) && (
        <div className="diff-stat-grid">
          {stagedDiffStat && (
            <pre aria-label="Staged diff stat">{stagedDiffStat || 'No staged diff.'}</pre>
          )}
          {worktreeDiffStat && (
            <pre aria-label="Worktree diff stat">{worktreeDiffStat || 'No worktree diff.'}</pre>
          )}
        </div>
      )}
    </div>
  )
}

function CountStrip({ counts }: { counts: GitStatusCounts }) {
  return (
    <div className="count-strip">
      <div>
        <strong>{counts.staged}</strong>
        <span>Staged</span>
      </div>
      <div>
        <strong>{counts.unstaged}</strong>
        <span>Unstaged</span>
      </div>
      <div>
        <strong>{counts.untracked}</strong>
        <span>Untracked</span>
      </div>
    </div>
  )
}

function FileList({ files }: { files: GitStatusFile[] }) {
  if (files.length === 0) {
    return (
      <div className="file-list-empty">
        <CheckCircle2 size={16} aria-hidden="true" />
        <span>No changed files.</span>
      </div>
    )
  }

  return (
    <div className="file-list">
      {files.map((file) => (
        <div className="file-row" key={`${file.indexStatus}:${file.worktreeStatus}:${file.path}`}>
          <code>{file.path}</code>
          <span>{file.indexStatus}</span>
          <span>{file.worktreeStatus}</span>
        </div>
      ))}
    </div>
  )
}

function ActivityPanel({
  health,
  onRestartBackend,
}: {
  health: AppHealth
  onRestartBackend: () => void
}) {
  const [operations, setOperations] = useState<string[]>([])

  useEffect(() => {
    invoke<OperationListResponse>('operation_list')
      .then((response) =>
        setOperations(
          response.operations.map(
            (operation) => `${operation.name} (${operation.riskClass})`,
          ),
        ),
      )
      .catch(() => setOperations([]))
  }, [])

  return (
    <section className="activity-stack" aria-label="Activity">
      <div className="backend-panel">
        <BackendStatus health={health} />
        <button className="icon-button" onClick={onRestartBackend} title="Restart backend" type="button">
          <RotateCw size={17} aria-hidden="true" />
        </button>
      </div>

      <div className="timeline">
        {operations.length > 0 && (
          <div className="timeline-row">
            <ShieldCheck size={18} aria-hidden="true" />
            <div>
              <strong>Registered typed operations</strong>
              <span>{operations.join(', ')}</span>
            </div>
          </div>
        )}
        <div className="timeline-row">
          <Activity size={18} aria-hidden="true" />
          <div>
            <strong>Desktop shell initialized</strong>
            <span>Backend health is checked through authenticated local IPC.</span>
          </div>
        </div>
        <div className="timeline-row">
          <GitPullRequestArrow size={18} aria-hidden="true" />
          <div>
            <strong>GitHub operations pending</strong>
            <span>Remote actions require account identity, preview and confirmation.</span>
          </div>
        </div>
      </div>
    </section>
  )
}

function BackendStatus({ health }: { health: AppHealth }) {
  const healthy = health.backend.status === 'healthy'
  const Icon = healthy ? CheckCircle2 : CircleAlert
  const label = health.backend.status.replaceAll('_', ' ')

  return (
    <div className="backend-status" data-healthy={healthy}>
      <Icon size={18} aria-hidden="true" />
      <div>
        <strong>Backend {label}</strong>
        <span>
          {health.backend.pid ? `pid ${health.backend.pid}` : health.backend.message ?? 'not started'}
        </span>
      </div>
    </div>
  )
}

function SettingsPanel() {
  const [llmStatus, setLlmStatus] = useState<LlmProviderStatusResult | null>(null)
  const [selectedProvider, setSelectedProvider] = useState('openrouter')
  const [apiKey, setApiKey] = useState('')
  const [selectedModel, setSelectedModel] = useState('openrouter/free')
  const [freeOnly, setFreeOnly] = useState(true)
  const [llmMessage, setLlmMessage] = useState<string | null>(null)
  const [llmBusy, setLlmBusy] = useState(false)
  const [discoverBusy, setDiscoverBusy] = useState(false)
  const [githubStatus, setGithubStatus] = useState<GitHubAccountStatusResult | null>(null)
  const [githubAuth, setGithubAuth] = useState<GitHubAuthStartResult | null>(null)
  const [githubMessage, setGithubMessage] = useState<string | null>(null)
  const [appDistribution, setAppDistribution] = useState<AppDistribution | null>(null)
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>(() => initialUpdateStatus())
  const [busy, setBusy] = useState(false)
  const [updateBusy, setUpdateBusy] = useState(false)

  const refreshLlmStatus = useCallback(async () => {
    try {
      const response = await invoke<OperationRunResponse<LlmProviderStatusResult>>('operation_run', {
        args: {
          requestId: requestId('llm-provider-status'),
          operationName: 'llm.provider.status',
          input: {},
        },
      })
      setLlmStatus(response.result)
      setSelectedProvider(response.result.defaultProvider)
      setSelectedModel(response.result.activeModel)
      setLlmMessage(response.result.ready ? 'AI provider ready.' : 'AI provider not configured.')
    } catch (error) {
      setLlmMessage(error instanceof Error ? error.message : String(error))
    }
  }, [])

  const configureLlmProvider = useCallback(async () => {
    setLlmBusy(true)
    try {
      const response = await invoke<OperationRunResponse<LlmProviderStatusResult>>('operation_run', {
        args: {
          requestId: requestId('llm-provider-configure'),
          operationName: 'llm.provider.configure',
          input: {
            provider: selectedProvider,
            apiKey,
            model: selectedModel,
          },
        },
      })
      setApiKey('')
      setLlmStatus(response.result)
      setSelectedProvider(response.result.defaultProvider)
      setSelectedModel(response.result.activeModel)
      setLlmMessage('AI provider saved.')
    } catch (error) {
      setLlmMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setLlmBusy(false)
    }
  }, [apiKey, selectedModel, selectedProvider])

  const discoverModels = useCallback(async () => {
    setDiscoverBusy(true)
    try {
      const response = await invoke<OperationRunResponse<LlmModelDiscoverResult>>('operation_run', {
        args: {
          requestId: requestId('llm-model-discover'),
          operationName: 'llm.model.discover',
          input: { provider: selectedProvider },
        },
      })
      setLlmStatus((current) =>
        current
          ? {
              ...current,
              models: response.result.models,
            }
          : current,
      )
      setLlmMessage(`${response.result.discovered} models discovered.`)
    } catch (error) {
      setLlmMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setDiscoverBusy(false)
    }
  }, [selectedProvider])

  const llmProviders = llmStatus?.providers ?? fallbackLlmProviders
  const selectedProviderInfo = llmProviders.find((provider) => provider.id === selectedProvider)
  const modelOptions = useMemo(() => {
    const models = llmStatus?.models ?? []
    return models.filter((model) => {
      if (model.provider !== selectedProvider) {
        return false
      }
      return !freeOnly || model.free
    })
  }, [freeOnly, llmStatus?.models, selectedProvider])

  const selectedModelInfo = modelOptions.find((model) => model.modelId === selectedModel)

  const refreshGithubStatus = useCallback(async () => {
    try {
      const response = await invoke<OperationRunResponse<GitHubAccountStatusResult>>('operation_run', {
        args: {
          requestId: requestId('github-status'),
          operationName: 'github.account.status',
          input: {},
        },
      })
      setGithubStatus(response.result)
      if (response.result.error) {
        setGithubMessage(response.result.error)
      }
    } catch (error) {
      setGithubMessage(error instanceof Error ? error.message : String(error))
    }
  }, [])

  const refreshAppDistribution = useCallback(async () => {
    try {
      const distribution = await invoke<AppDistribution>('app_distribution')
      setAppDistribution(distribution)
      if (!distribution.updaterSupported) {
        setUpdateStatus({
          kind: 'manual',
          currentVersion: __APP_VERSION__,
          message: distribution.message,
        })
      }
    } catch {
      setAppDistribution(null)
    }
  }, [])

  const startGithubAuth = useCallback(async () => {
    setBusy(true)
    try {
      setGithubMessage(null)
      const response = await invoke<OperationRunResponse<GitHubAuthStartResult>>('operation_run', {
        args: {
          requestId: requestId('github-auth-start'),
          operationName: 'github.auth.start',
          input: {},
        },
      })
      setGithubAuth(response.result)
      setGithubMessage('Waiting for browser authentication.')
    } catch (error) {
      setGithubMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }, [])

  const pollGithubAuth = useCallback(async () => {
    if (!githubAuth) {
      return
    }
    try {
      const response = await invoke<OperationRunResponse<GitHubAuthPollResult>>('operation_run', {
        args: {
          requestId: requestId('github-auth-poll'),
          operationName: 'github.auth.poll',
          input: { authSessionId: githubAuth.authSessionId },
        },
      })
      if (response.result.authenticated) {
        setGithubAuth(null)
        setGithubStatus({
          connected: true,
          account: response.result.account,
        })
        setGithubMessage(`Connected as ${response.result.account?.login ?? 'GitHub user'}.`)
      } else {
        setGithubMessage(`GitHub authentication ${response.result.status}.`)
      }
    } catch (error) {
      setGithubMessage(error instanceof Error ? error.message : String(error))
    }
  }, [githubAuth])

  const disconnectGithub = useCallback(async () => {
    setBusy(true)
    try {
      await invoke<OperationRunResponse<GitHubAccountStatusResult>>('operation_run', {
        args: {
          requestId: requestId('github-auth-disconnect'),
          operationName: 'github.auth.disconnect',
          input: {},
        },
      })
      setGithubAuth(null)
      setGithubStatus({ connected: false })
      setGithubMessage('GitHub disconnected.')
    } catch (error) {
      setGithubMessage(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }, [])

  const checkForUpdate = useCallback(async () => {
    if (appDistribution && !appDistribution.updaterSupported) {
      setUpdateStatus({
        kind: 'manual',
        currentVersion: __APP_VERSION__,
        message: appDistribution.message,
      })
      return
    }

    setUpdateBusy(true)
    try {
      setUpdateStatus({
        kind: 'checking',
        currentVersion: __APP_VERSION__,
        message: 'Checking the signed updater manifest.',
      })
      const update = await check({ timeout: 15000 })
      if (!update) {
        setUpdateStatus({
          kind: 'current',
          currentVersion: __APP_VERSION__,
          message: 'DevSynapse AI is up to date.',
        })
        return
      }

      setUpdateStatus({
        kind: 'available',
        currentVersion: update.currentVersion,
        availableVersion: update.version,
        message: `Version ${update.version} is available.`,
      })
      let downloadedBytes = 0
      let totalBytes: number | null = null
      await update.downloadAndInstall((event) => {
        if (event.event === 'Started') {
          downloadedBytes = 0
          totalBytes = event.data.contentLength ?? null
          setUpdateStatus({
            kind: 'downloading',
            currentVersion: update.currentVersion,
            availableVersion: update.version,
            downloadedBytes,
            totalBytes,
            message: totalBytes
              ? `Downloading ${Math.round(totalBytes / 1024 / 1024)} MB update.`
              : 'Downloading update.',
          })
        }
        if (event.event === 'Progress') {
          downloadedBytes += event.data.chunkLength
          setUpdateStatus({
            kind: 'downloading',
            currentVersion: update.currentVersion,
            availableVersion: update.version,
            downloadedBytes,
            totalBytes,
            message: totalBytes
              ? `Downloaded ${Math.round(downloadedBytes / 1024 / 1024)} of ${Math.round(totalBytes / 1024 / 1024)} MB.`
              : `Downloaded ${Math.round(downloadedBytes / 1024 / 1024)} MB.`,
          })
        }
        if (event.event === 'Finished') {
          setUpdateStatus({
            kind: 'installing',
            currentVersion: update.currentVersion,
            availableVersion: update.version,
            message: 'Download complete. Installing update.',
          })
        }
      })
      setUpdateStatus({
        kind: 'installing',
        currentVersion: update.currentVersion,
        availableVersion: update.version,
        message: 'Update installed. Restarting DevSynapse AI.',
      })
      await relaunch()
    } catch (error) {
      setUpdateStatus({
        kind: 'failed',
        currentVersion: __APP_VERSION__,
        message: error instanceof Error ? error.message : String(error),
      })
    } finally {
      setUpdateBusy(false)
    }
  }, [appDistribution])

  useEffect(() => {
    const initialLoad = window.setTimeout(() => {
      void refreshLlmStatus()
      void refreshGithubStatus()
      void refreshAppDistribution()
    }, 0)
    return () => window.clearTimeout(initialLoad)
  }, [refreshAppDistribution, refreshGithubStatus, refreshLlmStatus])

  return (
    <section className="settings-list" aria-label="Settings">
      <div>
        <div className="settings-heading">
          <div>
            <strong>AI provider</strong>
            <span>
              {selectedProviderInfo?.configured
                ? `${selectedProviderInfo.label} configured with ${selectedProviderInfo.model}.`
                : 'No AI provider configured.'}
            </span>
          </div>
          <div className="status-pill" data-ready={llmStatus?.ready ?? false}>
            <KeyRound size={14} aria-hidden="true" />
            <span>{llmStatus?.ready ? 'Ready' : 'Needs key'}</span>
          </div>
        </div>
        <div className="provider-form">
          <label className="form-field">
            <span>Provider</span>
            <select
              value={selectedProvider}
              onChange={(event) => {
                const providerId = event.currentTarget.value
                const provider = llmStatus?.providers.find((item) => item.id === providerId)
                setSelectedProvider(providerId)
                setSelectedModel(provider?.model || provider?.defaultModel || '')
              }}
            >
              {llmProviders.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>API key</span>
            <input
              autoComplete="off"
              placeholder={selectedProviderInfo?.configured ? 'Configured' : 'Paste API key'}
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.currentTarget.value)}
            />
          </label>
          <div className="model-toolbar">
            <label>
              <input
                checked={freeOnly}
                type="checkbox"
                onChange={(event) => setFreeOnly(event.currentTarget.checked)}
              />
              <span>Free only</span>
            </label>
            <button className="text-button" disabled={discoverBusy} onClick={discoverModels} type="button">
              <Search size={15} aria-hidden="true" />
              Discover
            </button>
          </div>
          <label className="form-field">
            <span>Model</span>
            <select
              value={modelOptions.some((model) => model.modelId === selectedModel) ? selectedModel : ''}
              onChange={(event) => setSelectedModel(event.currentTarget.value)}
            >
              {!modelOptions.some((model) => model.modelId === selectedModel) && (
                <option value="">{selectedModel || 'Custom model'}</option>
              )}
              {modelOptions.map((model) => (
                <option key={`${model.provider}:${model.modelId}`} value={model.modelId}>
                  {model.name} ({model.modelId})
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Model ID</span>
            <input
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.currentTarget.value)}
            />
          </label>
          {selectedModelInfo && (
            <div className="model-meta">
              <span>{selectedModelInfo.free ? 'Free' : 'Paid'}</span>
              <span>{selectedModelInfo.supportsTools ? 'Tools' : 'Chat'}</span>
              <span>{selectedModelInfo.contextLength ? `${selectedModelInfo.contextLength} context` : 'Context unknown'}</span>
            </div>
          )}
        </div>
        {llmMessage && <span>{llmMessage}</span>}
        <div className="settings-actions">
          <button className="text-button" disabled={llmBusy} onClick={configureLlmProvider} type="button">
            <KeyRound size={15} aria-hidden="true" />
            Save AI provider
          </button>
          <button className="text-button" onClick={refreshLlmStatus} type="button">
            <RotateCw size={15} aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>
      <div>
        <strong>GitHub account</strong>
        <span>
          {githubStatus?.connected
            ? `Connected as ${githubStatus.account?.login ?? 'GitHub user'}`
            : 'No GitHub account connected.'}
        </span>
        {githubAuth && (
          <div className="auth-box">
            <span>{githubAuth.verificationUri}</span>
            <strong>{githubAuth.userCode}</strong>
          </div>
        )}
        {githubMessage && <span>{githubMessage}</span>}
        <div className="settings-actions">
          <button className="text-button" disabled={busy} onClick={startGithubAuth} type="button">
            <GitPullRequestArrow size={15} aria-hidden="true" />
            Connect
          </button>
          <button className="text-button" disabled={!githubAuth} onClick={pollGithubAuth} type="button">
            Check
          </button>
          <button className="text-button" onClick={disconnectGithub} type="button">
            Disconnect
          </button>
        </div>
      </div>
      <div>
        <strong>Conversation preferences</strong>
        <span>Experience, detail and guidance controls are scheduled for onboarding.</span>
      </div>
      <div>
        <strong>Credential boundary</strong>
        <span>GitHub and provider secrets remain backend-only in the target model.</span>
      </div>
      <div>
        <strong>Operation policy</strong>
        <span>Risk classes are deterministic and cannot be changed by model wording.</span>
      </div>
      <div>
        <div className="settings-heading">
          <div>
            <strong>Application updates</strong>
            <span>{updateStatus.message}</span>
          </div>
          <div className="status-pill" data-ready={!['failed', 'manual'].includes(updateStatus.kind)}>
            {['failed', 'manual'].includes(updateStatus.kind) ? (
              <CircleAlert size={14} aria-hidden="true" />
            ) : (
              <CheckCircle2 size={14} aria-hidden="true" />
            )}
            <span>{updateStatus.kind.replaceAll('_', ' ')}</span>
          </div>
        </div>
        <div className="update-grid">
          <div>
            <span>Current</span>
            <strong>{updateStatus.currentVersion}</strong>
          </div>
          <div>
            <span>Available</span>
            <strong>{updateStatus.availableVersion ?? 'None'}</strong>
          </div>
          <div>
            <span>Channel</span>
            <strong>{appDistribution?.updateChannel ?? 'GitHub latest'}</strong>
          </div>
          <div>
            <span>Package</span>
            <strong>{appDistribution?.packageType.replaceAll('_', ' ') ?? 'Unknown'}</strong>
          </div>
        </div>
        {appDistribution && !appDistribution.updaterSupported && (
          <div className="update-note">
            <CircleAlert size={16} aria-hidden="true" />
            <span>
              Installed Debian packages cannot be replaced by the Tauri updater. Install the
              newest .deb from Releases or use the APT repository when it is hosted.
            </span>
          </div>
        )}
        <div className="auth-box">
          <span>Manifest</span>
          <strong>{productionUpdateEndpoint}</strong>
        </div>
        <div className="settings-actions">
          <button
            className="text-button"
            disabled={updateBusy || appDistribution?.updaterSupported === false}
            onClick={checkForUpdate}
            type="button"
          >
            <RotateCw size={15} aria-hidden="true" />
            {updateBusy ? 'Checking' : 'Check for updates'}
          </button>
          {appDistribution?.updaterSupported === false && (
            <a className="text-button" href={latestReleaseUrl} target="_blank" rel="noreferrer">
              <Link2 size={15} aria-hidden="true" />
              Latest release
            </a>
          )}
        </div>
      </div>
    </section>
  )
}

export default App
