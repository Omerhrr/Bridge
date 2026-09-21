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
  category: 'trigger' | 'voice' | 'ai' | 'messaging' | 'logic' | 'flow'
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
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
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
  }
  ai: {
    provider: string
    configured: boolean
  }
  environment: string
}
