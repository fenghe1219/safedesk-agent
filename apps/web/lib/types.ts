export type Role = "employee" | "support" | "approver" | "admin" | "evaluator" | "auditor";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  role_label: string;
  department: string;
}

export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: string;
}

export interface MeResponse {
  user: User;
  permissions: Record<string, boolean>;
  navigation: NavItem[];
  demo_mode: boolean;
  csrf_token: string;
  default_path: string;
}

export interface CaseSummary {
  id: string;
  title: string;
  status: string;
  status_label: string;
  phase: "intake" | "retrieval" | "solution" | "approval" | "done";
  requester_id: string;
  current_node: string;
  intent: string | null;
  ticket_id: string | null;
  action_id: string | null;
  created_at: string;
  updated_at: string;
}

export type CaseDetail = CaseSummary;

export interface CaseListResponse {
  items: CaseSummary[];
  next_cursor: string | null;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  summary: string;
  actor_id: string | null;
  actor_role: string | null;
  result: string;
  created_at: string;
}

export interface TimelineResponse {
  items: TimelineEvent[];
}

export interface MessageCitation {
  id: string;
  index: number;
  chunk_id: string;
  doc_id: string;
  title: string;
  version: string;
  page: number;
  section: string;
  quote: string;
  offset_start: number;
  offset_end: number;
  source_available: boolean;
}

export interface ChatMessage {
  id: string;
  case_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "STREAMING" | "COMPLETE" | "STOPPED" | "FAILED";
  citations: MessageCitation[];
  model_version: string;
  prompt_version: string;
  created_at: string;
}

export interface MessageListResponse {
  items: ChatMessage[];
  next_cursor: string | null;
}

export interface KnowledgeDocument {
  id: string;
  title: string;
  version: string;
  owner_id: string;
  effective_at: string;
  source_type: string;
  acl: { departments?: string[] };
  status: "DRAFT" | "PROCESSING" | "READY" | "FAILED" | "DISABLED";
  parse_error: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentListResponse {
  items: KnowledgeDocument[];
  next_cursor: string | null;
}

export interface KnowledgeChunk {
  id: string;
  doc_id: string;
  doc_version: string;
  content: string;
  page: number;
  section: string;
  offset_start: number;
  offset_end: number;
  ordinal: number;
  created_at: string;
}

export interface KnowledgeLocator {
  doc_id: string;
  chunk_id: string;
  title: string;
  version: string;
  status: string;
  page: number;
  section: string;
  offset_start: number;
  offset_end: number;
  quote: string;
  raw_content: string;
}

export interface KnowledgeSearchItem {
  chunk_id: string;
  doc_id: string;
  title: string;
  version: string;
  page: number;
  section: string;
  quote: string;
  score: number;
}

export interface KnowledgeSearchResponse {
  query: string;
  items: KnowledgeSearchItem[];
}

export interface Ticket {
  id: string;
  case_id: string;
  requester_id: string;
  requester_name: string;
  title: string;
  description: string;
  category: string;
  category_label: string;
  priority: string;
  priority_label: string;
  priority_reason: string;
  affected_system: string | null;
  environment: string | null;
  error_message: string | null;
  urgency_reason: string | null;
  suggested_assignee_id: string | null;
  suggested_assignee_name: string | null;
  suggested_assignee_reason: string | null;
  assignee_id: string | null;
  assignee_name: string | null;
  status: string;
  status_label: string;
  fields: Record<string, unknown>;
  missing_fields: string[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TicketNote {
  id: string;
  ticket_id: string;
  author_id: string;
  author_name: string;
  content: string;
  created_at: string;
}

export interface TicketDetail extends Ticket {
  notes: TicketNote[];
}

export interface TicketListResponse {
  items: Ticket[];
  next_cursor: string | null;
}

export interface TicketCreateResponse {
  ticket: TicketDetail;
  case: CaseSummary;
}

export interface TicketDraft extends Ticket {
  ticket_id: string;
}

export interface TicketAssignee {
  id: string;
  name: string;
  email: string;
  role: string;
  role_label: string;
  department: string;
  open_ticket_count: number;
}

export interface TicketAssigneeListResponse {
  items: TicketAssignee[];
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type ActionStatus =
  | "PROPOSED"
  | "AWAITING_APPROVAL"
  | "APPROVED"
  | "EXECUTING"
  | "SUCCEEDED"
  | "FAILED"
  | "REJECTED"
  | "EXPIRED"
  | "CANCELLED";
export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED" | "CANCELLED";

export interface ToolExecution {
  id: string;
  action_id: string;
  tool_name: string;
  status: string;
  idempotency_key: string;
  args_hash: string;
  output: Record<string, unknown>;
  result_summary: string;
  verification: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Approval {
  id: string;
  action_id: string;
  status: ApprovalStatus;
  status_label: string;
  args_hash: string;
  approver_id: string | null;
  approver_name: string | null;
  decision_reason: string | null;
  requested_at: string;
  expires_at: string;
  decided_at: string | null;
  version: number;
}

export interface ActionRecord {
  id: string;
  case_id: string;
  tool_name: string;
  tool_label: string;
  tool_type: "READ" | "WRITE";
  risk_level: RiskLevel;
  risk_label: string;
  status: ActionStatus;
  status_label: string;
  args: Record<string, unknown>;
  args_hash: string;
  rationale: string;
  impact: string;
  verification_plan: string;
  rollback_plan: string;
  evidence_ids: string[];
  requested_by_id: string;
  requested_by_name: string;
  expires_at: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface CaseAction extends ActionRecord {
  case_status: string;
  case_status_label: string;
  approval: Approval;
  execution: ToolExecution | null;
  permissions: Record<string, boolean>;
  blockers: string[];
}

export interface ApprovalListItem {
  id: string;
  action_id: string;
  case_id: string;
  case_title: string;
  requester_id: string;
  requester_name: string;
  tool_name: string;
  tool_label: string;
  risk_level: RiskLevel;
  risk_label: string;
  impact: string;
  status: ApprovalStatus;
  status_label: string;
  requested_at: string;
  expires_at: string;
  decided_at: string | null;
  can_decide: boolean;
}

export interface ApprovalDetail {
  approval: Approval;
  action: ActionRecord;
  case: CaseSummary;
  execution: ToolExecution | null;
  timeline: TimelineEvent[];
  permissions: Record<string, boolean>;
  blockers: string[];
}

export interface ApprovalListResponse {
  items: ApprovalListItem[];
}

export interface ActionDecisionResponse {
  approval: Approval;
  action: ActionRecord;
  case: CaseSummary;
  execution: ToolExecution | null;
  message: string;
}

export interface WorkflowCheckpoint {
  id: string;
  case_id: string;
  thread_id: string;
  sequence: number;
  node: string;
  status: string;
  workflow_version: number;
  state: Record<string, unknown>;
  created_at: string;
}

export interface CheckpointListResponse {
  items: WorkflowCheckpoint[];
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
}
