import {
  Activity,
  Bot,
  CheckCircle2,
  CircleAlert,
  FolderGit2,
  GitPullRequestArrow,
  HeartPulse,
  MessageSquareText,
  RotateCw,
  Settings,
  ShieldCheck,
} from 'lucide-react'
import { invoke } from '@tauri-apps/api/core'
import { useCallback, useEffect, useMemo, useState } from 'react'

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

type BackendHealth = {
  status: string
  port?: number | null
  pid?: number | null
  dataDir?: string | null
  message?: string | null
}

type AppHealth = {
  status: string
  version: string
  backend: BackendHealth
}

const browserPreviewHealth: AppHealth = {
  status: 'preview',
  version: __APP_VERSION__,
  backend: {
    status: 'browser_preview',
    message: 'Tauri IPC is available only in the desktop shell.',
  },
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
            <span>No mutation surface</span>
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
  return (
    <div className="content-grid">
      <section className="conversation-surface" aria-label="Conversation preview">
        <article className="message assistant">
          <div className="avatar">
            <Bot size={18} aria-hidden="true" />
          </div>
          <div>
            <span className="message-author">DevSynapse</span>
            <p>
              I can help inspect projects, explain GitHub state and prepare safe actions.
              Repository-changing workflows will appear only after typed operations,
              previews and approvals are connected.
            </p>
          </div>
        </article>

        <div className="composer" aria-label="Composer placeholder">
          <MessageSquareText size={18} aria-hidden="true" />
          <span>Conversation IPC connects in the streaming milestone.</span>
        </div>
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
  return (
    <section className="empty-state">
      <FolderGit2 size={34} aria-hidden="true" />
      <h2>Project selection comes next</h2>
      <p>
        The first project workflow will use native folder selection and typed
        repository identity. The frontend will not parse Git output directly.
      </p>
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
  return (
    <section className="activity-stack" aria-label="Activity">
      <div className="backend-panel">
        <BackendStatus health={health} />
        <button className="icon-button" onClick={onRestartBackend} title="Restart backend" type="button">
          <RotateCw size={17} aria-hidden="true" />
        </button>
      </div>

      <div className="timeline">
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
  return (
    <section className="settings-list" aria-label="Settings">
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
