import { cache } from "react";
import { cookies } from "next/headers";

import type {
  CaseDetail,
  CaseListResponse,
  KnowledgeDocumentListResponse,
  MeResponse,
  MessageListResponse,
  TicketAssignee,
  TicketAssigneeListResponse,
  TicketDetail,
  TicketDraft,
  TicketListResponse,
  TimelineEvent,
  TimelineResponse
} from "./types";

const API_URL = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function serverFetch<T>(path: string): Promise<T | null> {
  const cookieStore = await cookies();
  const cookie = cookieStore
    .getAll()
    .map((item) => `${item.name}=${item.value}`)
    .join("; ");

  try {
    const response = await fetch(`${API_URL}${path}`, {
      headers: cookie ? { cookie } : undefined,
      cache: "no-store"
    });
    if (response.status === 401 || response.status === 403 || response.status === 404) {
      return null;
    }
    if (!response.ok) {
      console.error("SafeDesk API error", path, response.status);
      return null;
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error("SafeDesk API unavailable", path, error);
    return null;
  }
}

export const getMe = cache(async (): Promise<MeResponse | null> => serverFetch<MeResponse>("/api/me"));

export async function getCases(): Promise<CaseListResponse> {
  const data = await serverFetch<CaseListResponse>("/api/cases?limit=20");
  return data ?? { items: [], next_cursor: null };
}

export async function getCase(caseId: string): Promise<CaseDetail | null> {
  return serverFetch<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`);
}

export async function getCaseTimeline(caseId: string): Promise<TimelineEvent[]> {
  const data = await serverFetch<TimelineResponse>(
    `/api/cases/${encodeURIComponent(caseId)}/timeline`
  );
  return data?.items ?? [];
}

export async function getCaseMessages(caseId: string): Promise<MessageListResponse> {
  const data = await serverFetch<MessageListResponse>(
    `/api/cases/${encodeURIComponent(caseId)}/messages`
  );
  return data ?? { items: [], next_cursor: null };
}

export async function getKnowledgeDocuments(): Promise<KnowledgeDocumentListResponse> {
  const data = await serverFetch<KnowledgeDocumentListResponse>("/api/knowledge/documents");
  return data ?? { items: [], next_cursor: null };
}

export async function getTickets(filters: {
  status?: string;
  category?: string;
  priority?: string;
  assignee_id?: string;
  q?: string;
  limit?: number;
} = {}): Promise<TicketListResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  const data = await serverFetch<TicketListResponse>(
    `/api/tickets${query ? `?${query}` : ""}`
  );
  return data ?? { items: [], next_cursor: null };
}

export async function getTicket(ticketId: string): Promise<TicketDetail | null> {
  return serverFetch<TicketDetail>(`/api/tickets/${encodeURIComponent(ticketId)}`);
}

export async function getTicketDraft(caseId: string): Promise<TicketDraft | null> {
  return serverFetch<TicketDraft>(`/api/cases/${encodeURIComponent(caseId)}/ticket-draft`);
}

export async function getTicketAssignees(): Promise<TicketAssignee[]> {
  const data = await serverFetch<TicketAssigneeListResponse>("/api/tickets/assignees");
  return data?.items ?? [];
}
