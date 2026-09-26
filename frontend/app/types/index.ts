/** Shared API/domain types for the Bridge frontend. */

export interface NodeConfigField {
  name: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'boolean'
  required?: boolean
  options?: string[]
  default?: string | number | boolean
  hint?: string
}

export interface NodeMeta {
  type: string
  label: string
  category: 'trigger' | 'voice' | 'ai' | 'messaging' | 'telecom' | 'logic' | 'flow'
  description: string
  icon: string
  inputs: string[]
  outputs: string[]
  config_schema: NodeConfigField[]
}

export interface NodeDefinition {
  id: string
  type: string
  position?: { x: number; y: number }
  config: Record<string, unknown>
}

export interface EdgeDefinition {
  source: string
  target: string
  source_handle?: string | null
  target_handle?: string | null
}

export interface WorkflowDefinition {
  nodes: NodeDefinition[]
  edges: EdgeDefinition[]
}

export interface WorkflowVersion {
  id: number
  version_number: number
  definition: WorkflowDefinition
  comment: string
  created_at: string
}

export interface Workflow {
  id: number
  name: string
  description: string
  status: 'active' | 'inactive'
  version_count: number
  current_version: WorkflowVersion | null
  created_at: string
  updated_at: string
}

export interface ValidationIssue {
  level: 'error' | 'warning'
  node_id: string | null
  message: string
}

export interface ValidationReport {
  valid: boolean
  checks_passed: number
  issues: ValidationIssue[]
}

export interface WorkflowEvent {
  id: number
  node_id: string | null
  node_type: string | null
  event: string
  payload: Record<string, unknown>
  created_at: string
}

export interface WorkflowRun {
  id: string
  workflow_id: number
  status: 'pending' | 'running' | 'waiting' | 'completed' | 'failed' | 'cancelled'
  current_node: string | null
  variables: Record<string, unknown>
  error: string | null
  started_at: string
  finished_at: string | null
  events: WorkflowEvent[]
}

export interface ConversationMessage {
  id: number
  role: string
  channel: string
  content: string
  translated_content: string | null
  source_language: string | null
  target_language: string | null
  created_at: string
}

export interface Conversation {
  id: number
  channel: 'voice' | 'sms' | 'ussd'
  status: 'active' | 'completed' | 'failed'
  a_number: string | null
  b_number: string | null
  source_language: string | null
  target_language: string | null
  workflow_run_id: string | null
  started_at: string
  ended_at: string | null
  messages: ConversationMessage[]
}

export interface TimelineEvent {
  timestamp: string
  kind: string
  label: string
  detail: Record<string, unknown>
}

export interface DashboardSummary {
  status: string
  calls: number
  sms: number
  active_workflows: number
  total_workflows: number
  success_rate: number
  recent_conversations: Array<Record<string, unknown> & {
    id: number
    channel: string
    a_number: string | null
    b_number: string | null
    source_language: string | null
    target_language: string | null
    status: string
    started_at: string
  }>
  workflow_activity: Array<{
    id: number
    name: string
    status: string
    runs: number
    success_rate: number
  }>
}

export interface ProviderStatus {
  telecom: {
    provider: string
    configured: boolean
    sandbox: boolean
    phone_number: string | null
    sender_id: string | null
    shortcode?: string | null
  }
  ai: {
    provider: string
    configured: boolean
    model?: string | null
  }
  environment: string
}

// ---- Messaging -----------------------------------------------------------

export interface LanguageOption {
  code: string
  name: string
}

export interface Contact {
  id: number
  phone_number: string
  name: string
  language: string | null
  language_name: string | null
  language_locked: boolean
  partner_number: string | null
  message_count: number
  created_at: string
}

export interface MessageLogEntry {
  id: number
  direction: 'inbound' | 'outbound'
  kind: 'inbound' | 'relay' | 'broadcast' | 'reply' | 'system' | 'workflow' | 'answer'
  from_number: string | null
  to_number: string | null
  original_text: string | null
  text: string
  source_language: string | null
  target_language: string | null
  status: string
  error: string | null
  run_id: string | null
  created_at: string
}

export interface DeliveryResult {
  to: string
  status: string
  text: string
  original_text: string
  target_language: string | null
  source_language: string | null
  message_id: string | null
  error: string | null
}

export interface SendResponse {
  sent: number
  failed: number
  results: DeliveryResult[]
}

export interface MessagingInfo {
  default_sender: string | null
  ai_provider: string
  ai_configured: boolean
  sandbox: boolean
}

// ---- Knowledge ------------------------------------------------------------

export type KnowledgeKind = 'website' | 'google_doc' | 'google_sheet' | 'database' | 'text'

export interface BusinessProfile {
  name: string
  description: string
  contact: string
  fallback_message: string
  assistant_enabled: boolean
  sources: number
  ready_sources: number
  passages: number
  questions: number
  unanswered: number
  ai_configured: boolean
  available: boolean
}

export interface KnowledgeSource {
  id: number
  name: string
  kind: KnowledgeKind
  config: Record<string, any>
  has_secret: boolean
  status: 'pending' | 'syncing' | 'ready' | 'error'
  error: string | null
  chunk_count: number
  last_synced_at: string | null
  created_at: string
}

export interface KnowledgeChunk {
  id: number
  title: string
  location: string
  content: string
}

export interface AskResult {
  answered: boolean
  answer: string
  reason: string
  language: string | null
  evidence: string[]
  sources: { source_id: number; source_name: string; title: string; location: string; excerpt: string }[]
}

// ---- API keys (public assistant access) -----------------------------------

export interface ApiKey {
  id: number
  name: string
  prefix: string
  revoked_at: string | null
  last_used_at: string | null
  request_count: number
  created_at: string
}

export interface ApiKeyCreated extends ApiKey {
  key: string
}

export interface KnowledgeQuery {
  id: number
  phone_number: string | null
  channel: string
  question: string
  answer: string
  answered: boolean
  reason: string
  language: string | null
  created_at: string
}
