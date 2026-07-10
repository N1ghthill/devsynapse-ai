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
