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

export type EvalDatasetType = "knowledge" | "triage" | "security";

export interface EvalDataset {
  id: string;
  name: string;
  dataset_type: EvalDatasetType;
  version: string;
  description: string;
  item_count: number;
  is_fixed: boolean;
  created_at: string;
}

export interface EvalDatasetListResponse {
  items: EvalDataset[];
}

export interface EvalItem {
  id: string;
  ordinal: number;
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
  labels: Record<string, unknown>;
  source: string;
}

export interface EvalDatasetDetail extends EvalDataset {
  items: EvalItem[];
}

export interface EvalMetrics {
  sample_size: number;
  pass_rate: number;
  avg_latency_ms: number;
  avg_cost_usd: number;
  cost_note?: string;
  latency_note?: string;
  metric_sample_sizes?: Record<string, number>;
  [key: string]: unknown;
}

export interface EvalRun {
  id: string;
  dataset_id: string;
  dataset_name: string;
  dataset_type: EvalDatasetType;
  label: string;
  prompt_version: string;
  model_settings: Record<string, unknown>;
  retrieval_config: Record<string, unknown>;
  run_config: Record<string, unknown>;
  status: string;
  metrics: EvalMetrics;
  sample_count: number;
  created_by_id: string | null;
  created_by_name: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface EvalRunListResponse {
  items: EvalRun[];
}

export interface EvalResult {
  id: string;
  run_id: string;
  item_id: string;
  ordinal: number;
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
  labels: Record<string, unknown>;
  actual: Record<string, unknown>;
  score: number;
  passed: boolean;
  failure_reason: string;
  citations: Array<Record<string, unknown>>;
  latency_ms: number;
  token_count: number;
  cost_usd: number;
  manual_verdict: "PASS" | "FAIL" | null;
  manual_note: string;
  reviewed_by_id: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface EvalResultListResponse {
  items: EvalResult[];
  total: number;
  offset: number;
  limit: number;
}

export interface EvalRunDetail {
  run: EvalRun;
  results: EvalResultListResponse;
}

export interface EvalMetricDiff {
  key: string;
  label: string;
  unit: string;
  baseline: number | null;
  candidate: number | null;
  delta: number | null;
  lower_is_better: boolean;
  regressed: boolean;
}

export interface EvalCompareResponse {
  baseline: EvalRun;
  candidate: EvalRun;
  metrics: EvalMetricDiff[];
  regression_blocked: boolean;
  threshold: number;
  blocking_metrics: string[];
}

export interface EvalAblationVariant {
  label: string;
  prompt_version?: string | null;
  model_settings?: Record<string, unknown>;
  retrieval_config?: Record<string, unknown>;
  run_config?: Record<string, unknown>;
}

export interface EvalAblationResponse {
  runs: EvalRun[];
  comparisons: EvalCompareResponse[];
}

export interface DashboardDistributionItem {
  key: string;
  label: string;
  count: number;
  rate: number;
}

export interface EvalTrendPoint {
  run_id: string;
  dataset_type: string;
  label: string;
  sample_size: number;
  pass_rate: number;
  key_metric: string;
  key_metric_label: string;
  key_metric_value: number;
  created_at: string;
}

export interface DashboardResponse {
  range: string;
  range_label: string;
  generated_at: string;
  cases_total: number;
  knowledge_resolution_rate: number;
  ticket_rate: number;
  approval_requests: number;
  approval_rejected: number;
  approval_failed: number;
  category_distribution: DashboardDistributionItem[];
  priority_distribution: DashboardDistributionItem[];
  manual_correction_rate: number;
  avg_handling_minutes: number;
  approval_pass_rate: number;
  avg_approval_wait_minutes: number;
  approval_expiry_rate: number;
  duplicate_execution_blocked: number;
  avg_answer_latency_ms: number;
  avg_retrieval_latency_ms: number;
  avg_tool_latency_ms: number;
  avg_answer_cost_usd: number;
  eval_trend: EvalTrendPoint[];
  sample_sizes: Record<string, number>;
  methodology: Record<string, string>;
}

export interface AuditEvent {
  id: string;
  case_id: string | null;
  actor_id: string | null;
  actor_name: string | null;
  actor_role: string | null;
  event_type: string;
  summary: string;
  payload: Record<string, unknown>;
  request_id: string;
  result: string;
  created_at: string;
}

export interface AuditEventListResponse {
  items: AuditEvent[];
  total: number;
  offset: number;
  limit: number;
  event_types: string[];
}

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  role_label: string;
  department: string;
  is_active: boolean;
  created_at: string;
}

export interface RuntimeConfig {
  retrieval_limit: number;
  max_context_chunks: number;
  retrieval_min_score: number;
  max_steps: number;
  approval_ttl_seconds: number;
  evaluation_regression_threshold: number;
  answer_style: "concise" | "detailed";
  answer_mode: "auto" | "local" | "model";
  memory_enabled: boolean;
  query_rewrite_enabled: boolean;
  agent_tools_enabled: boolean;
}

export interface PromptVersion {
  id: string;
  version: string;
  name: string;
  system_prompt: string;
  is_active: boolean;
  created_by_id: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface TaxonomyResponse {
  categories: Array<{ key: string; label: string }>;
  priorities: Array<{ key: string; label: string }>;
  roles: Array<{ key: string; label: string; permissions: string[] }>;
}

export interface AdminSettings {
  runtime_config: RuntimeConfig;
  prompts: PromptVersion[];
  taxonomy: TaxonomyResponse;
  users: AdminUser[];
  agent_runtime: AgentRuntimeInfo;
}

export interface AgentRuntimeInfo {
  provider: string;
  model: string;
  configured: boolean;
  api_key_configured: boolean;
  active_prompt_version: string;
  max_model_calls: number;
}

export interface DemoResetResponse {
  reset_at: string;
  deleted: Record<string, number>;
  reseeded_documents: number;
  audit_event_id: string;
  message: string;
}

export interface Feedback {
  id: string;
  message_id: string;
  user_id: string;
  rating: "helpful" | "unhelpful";
  reason: string | null;
  comment: string;
  created_at: string;
  updated_at: string;
}

export interface ToolPolicy {
  name: string;
  label: string;
  tool_type: "READ" | "WRITE";
  risk_level: RiskLevel;
  description: string;
  requires_approval: boolean;
  timeout_seconds: number;
  enabled: boolean;
  mock_mode: "success" | "fail" | "timeout";
}

export interface ToolPolicyListResponse {
  items: ToolPolicy[];
  kill_switch_enabled: boolean;
  kill_switch_reason: string | null;
}
