import { cache } from "react";
import { cookies } from "next/headers";

import type {
  CaseDetail,
  CaseListResponse,
  KnowledgeDocumentListResponse,
  MeResponse,
  MessageListResponse,
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
