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

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
}
