export type BackendHealth = {
  status: string
  port?: number | null
  pid?: number | null
  dataDir?: string | null
  message?: string | null
}

export type AppHealth = {
  status: string
  version: string
  backend: BackendHealth
}

export type ConversationEventType =
  | 'response.started'
  | 'response.delta'
  | 'response.completed'
  | 'response.failed'
  | 'operation.started'
  | 'operation.progress'
  | 'operation.completed'
  | 'operation.failed'

export type ConversationEvent = {
  type: ConversationEventType
  requestId: string
  conversationId: string
  delta?: string | null
  error?: string | null
}

export type ConversationResponse = {
  conversationId: string
  events: ConversationEvent[]
}

export type OperationDefinition = {
  name: string
  riskClass: 'observe' | 'prepare' | 'local_mutation' | 'remote_mutation' | 'destructive'
  description: string
}

export type OperationListResponse = {
  operations: OperationDefinition[]
}

export type LlmProviderSummary = {
  id: string
  label: string
  configured: boolean
  selected: boolean
  model: string
  defaultModel: string
}

export type LlmModelSummary = {
  provider: string
  modelId: string
  name: string
  contextLength?: number | null
  free: boolean
  supportsTools: boolean
}

export type LlmProviderStatusResult = {
  defaultProvider: string
  activeModel: string
  ready: boolean
  providers: LlmProviderSummary[]
  models: LlmModelSummary[]
}

export type LlmModelDiscoverResult = {
  provider: string
  discovered: number
  models: LlmModelSummary[]
}

export type ProjectSummary = {
  name: string
  path: string
  type: string
  priority: string
  exists: boolean
  isGitRepository: boolean
  repository?: ProjectRepositoryLink | null
}

export type ProjectListResult = {
  projects: ProjectSummary[]
}

export type ProjectRegisterResult = {
  project: ProjectSummary
}

export type ProjectRepositoryLink = {
  provider: string
  owner: string
  name: string
  fullName: string
  htmlUrl?: string | null
  cloneUrl?: string | null
  defaultBranch?: string | null
  private: boolean
  accountLogin?: string | null
  connectedAt?: string | null
  updatedAt?: string | null
}

export type GitHubRepositorySummary = {
  id?: number | null
  owner: string
  name: string
  fullName: string
  private: boolean
  fork: boolean
  archived: boolean
  defaultBranch?: string | null
  description?: string | null
  htmlUrl?: string | null
  cloneUrl?: string | null
  sshUrl?: string | null
  permissions: Record<string, boolean>
  updatedAt?: string | null
  pushedAt?: string | null
}

export type GitHubRepositoryListResult = {
  repositories: GitHubRepositorySummary[]
  query: string
  limit: number
  totalReturned: number
}

export type ProjectConnectResult = {
  projectName: string
  repository: ProjectRepositoryLink
}

export type GitStatusCounts = {
  staged: number
  unstaged: number
  untracked: number
}

export type GitStatusFile = {
  path: string
  indexStatus: string
  worktreeStatus: string
}

export type GitStatusResult = {
  projectName: string
  path: string
  branch?: string | null
  headCommit?: string | null
  stateFingerprint: string
  counts: GitStatusCounts
  files: GitStatusFile[]
  isClean: boolean
}

export type CommitPreviewResult = {
  previewId: string
  projectName: string
  path: string
  riskClass: 'prepare'
  proposedOperation: 'commit.create'
  currentBranch?: string | null
  headCommit?: string | null
  stateFingerprint: string
  isStale: boolean
  isClean: boolean
  counts: GitStatusCounts
  files: GitStatusFile[]
  worktreeDiffStat: string
  stagedDiffStat: string
}

export type CommitPreviewValidationResult = {
  projectName: string
  path: string
  valid: boolean
  isStale: boolean
  expectedStateFingerprint: string
  currentStateFingerprint: string
  expectedPreviewId: string
  currentPreviewId: string
  currentBranch?: string | null
  headCommit?: string | null
  isClean: boolean
  counts: GitStatusCounts
  files: GitStatusFile[]
}

export type GitHubAccount = {
  login?: string | null
  id?: number | null
  name?: string | null
  avatarUrl?: string | null
  htmlUrl?: string | null
}

export type GitHubAuthStartResult = {
  authSessionId: string
  verificationUri: string
  userCode: string
  expiresIn: number
  interval: number
  scopes: string
}

export type GitHubAuthPollResult = {
  status: string
  authenticated: boolean
  interval?: number | null
  account?: GitHubAccount | null
  scopes?: string | null
}

export type GitHubAccountStatusResult = {
  connected: boolean
  secureStorageAvailable?: boolean | null
  error?: string | null
  account?: GitHubAccount | null
}

export type OperationRunResponse<T = unknown> = {
  requestId: string
  operationName: string
  riskClass: string
  status: string
  result: T
}
