import {
  Activity,
  Bot,
  CheckCircle2,
  CircleAlert,
  FolderGit2,
  FolderPlus,
  GitBranch,
  GitPullRequestArrow,
  HeartPulse,
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
import { useCallback, useEffect, useMemo, useState } from 'react'
import type {
  AppHealth,
  ConversationEvent,
  ConversationResponse,
  GitHubAccountStatusResult,
  GitHubAuthPollResult,
  GitHubAuthStartResult,
  GitHubRepositoryListResult,
  GitHubRepositorySummary,
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

type ConversationMessage = {
  id: string
  role: 'assistant' | 'user' | 'system'
  text: string
}

function requestId(prefix: string) {
  if (globalThis.crypto?.randomUUID) {
    return `${prefix}-${globalThis.crypto.randomUUID()}`
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
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
          <div className="brand-mark" aria-hidden="true">
            <Bot size={22} strokeWidth={2.2} />
          </div>
          <div>
            <strong>DevSynapse AI</strong>
            <span>GitHub copilot</span>
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

        <div className="shell-status">
          <HeartPulse size={17} aria-hidden="true" />
          <div>
            <strong>Backend {health.backend.status.replaceAll('_', ' ')}</strong>
            <span>Version {health.version}</span>
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

        {activeSection === 'conversation' && <ConversationPanel health={health} />}
        {activeSection === 'projects' && <ProjectsPanel />}
        {activeSection === 'activity' && (
          <ActivityPanel health={health} onRestartBackend={restartBackend} />
        )}
        {activeSection === 'settings' && <SettingsPanel />}
      </section>
    </main>
  )
}

function ConversationPanel({ health }: { health: AppHealth }) {
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

  return (
    <div className="content-grid">
      <section className="conversation-surface" aria-label="Conversation preview">
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
  const [projectEvidence, setProjectEvidence] = useState<string>('No project evidence loaded.')
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
        setProjectEvidence(JSON.stringify(response.result, null, 2))
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
      setProjectEvidence(JSON.stringify(response.result.project, null, 2))
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
      setProjectEvidence(JSON.stringify(response.result, null, 2))
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
      setProjectEvidence(JSON.stringify(response.result, null, 2))
    } catch (operationError) {
      setError(operationError instanceof Error ? operationError.message : String(operationError))
    } finally {
      setRepositoryBusy(false)
    }
  }, [repositories, selectedProject, selectedRepository])

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
        <pre>{projectEvidence}</pre>
      </div>
    </section>
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
  const [githubStatus, setGithubStatus] = useState<GitHubAccountStatusResult | null>(null)
  const [githubAuth, setGithubAuth] = useState<GitHubAuthStartResult | null>(null)
  const [githubMessage, setGithubMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

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

  useEffect(() => {
    const initialLoad = window.setTimeout(() => {
      void refreshGithubStatus()
    }, 0)
    return () => window.clearTimeout(initialLoad)
  }, [refreshGithubStatus])

  return (
    <section className="settings-list" aria-label="Settings">
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
    </section>
  )
}

export default App
