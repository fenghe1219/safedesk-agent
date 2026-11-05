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

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
}
