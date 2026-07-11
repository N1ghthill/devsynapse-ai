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

export type ProjectSummary = {
  name: string
  path: string
  type: string
  priority: string
  exists: boolean
  isGitRepository: boolean
}

export type ProjectListResult = {
  projects: ProjectSummary[]
}

export type ProjectRegisterResult = {
  project: ProjectSummary
}

export type OperationRunResponse<T = unknown> = {
  requestId: string
  operationName: string
  riskClass: string
  status: string
  result: T
}
