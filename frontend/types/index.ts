/** Shared API types mirroring the FastAPI schemas. */

export interface ConfigField {
  name: string;
  label: string;
  type: "text" | "textarea" | "select" | "number" | "boolean";
  required: boolean;
  default: unknown;
  options: string[];
  placeholder: string;
}

export interface NodeSpec {
  type: string;
  label: string;
  icon: string;
  category: "trigger" | "voice" | "ai" | "messaging" | "logic" | "flow";
  description: string;
  outputs: string[];
  config_fields: ConfigField[];
}

export interface WorkflowNode {
  id: string;
  type: string;
  label?: string;
  position?: { x: number; y: number };
  config: Record<string, unknown>;
}

export interface WorkflowEdge {
  source: string;
  target: string;
  source_handle?: string | null;
}

export interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface Workflow {
  id: number;
  name: string;
  description: string;
  enabled: boolean;
  current_version: number;
  definition: WorkflowDefinition;
  created_at?: string;
  updated_at?: string;
}

export interface ValidationIssue {
  node_id: string | null;
  severity: "ok" | "error" | "warning";
  message: string;
}

export interface ValidationReport {
  valid: boolean;
  checks: ValidationIssue[];
  summary: string;
}

export interface RunEvent {
  id: number;
  node_id: string;
  node_type: string;
  node_label: string;
  status: string;
  detail: Record<string, unknown>;
  created_at?: string;
}

export interface WorkflowRun {
  id: string;
  workflow_id: number;
  workflow_name?: string;
  version?: number;
  conversation_id?: number | null;
  status: "running" | "waiting_input" | "completed" | "failed";
  current_node?: string | null;
  variables: Record<string, unknown>;
  error?: string | null;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  events: RunEvent[];
}

export interface ConversationMessage {
  id: number;
  role: "user" | "system";
  channel: string;
  content: string;
  translated_content?: string | null;
  language?: string | null;
  created_at?: string;
}

export interface Conversation {
  id: number;
  channel: "voice" | "sms" | "ussd";
  status: "active" | "completed" | "failed";
  from_number: string;
  to_number?: string | null;
  language?: string | null;
  target_language?: string | null;
  workflow_id?: number | null;
  started_at?: string;
  ended_at?: string | null;
  duration_ms?: number | null;
  messages?: ConversationMessage[];
}

export interface Stats {
  calls: number;
  sms: number;
  active_workflows: number;
  total_workflows: number;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  success_rate: number | null;
  recent_conversations: Array<Conversation & { id: number }>;
  workflow_activity: Array<{
    workflow_id: number;
    name: string;
    runs: number;
    success_rate: number | null;
  }>;
}
