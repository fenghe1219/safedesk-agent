"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import { consumeSSE } from "@/lib/sse";
import type {
  ActionRecord,
  Approval,
  CaseAction,
  CaseDetail,
  ChatMessage,
  KnowledgeLocator,
  MessageCitation,
  MessageListResponse,
  TicketDetail,
  TicketDraft,
  TimelineEvent
} from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { ActionCard } from "./action-card";
import { Icon } from "./icons";
import { MessageFeedback } from "./message-feedback";
import { StatusBadge } from "./status-badge";
import { TicketDraftCard } from "./ticket-draft-card";

interface WorkspaceStatus {
  status: string;
  label: string;
  phase: string;
}

interface StepState {
  name: string;
  label: string;
  status: string;
}

const EMPTY_STEPS: StepState[] = [];
const EMPTY_CITATIONS: MessageCitation[] = [];

export function CaseWorkspace({
  caseData,
  initialMessages,
  initialTimeline,
  initialTicketDraft,
  initialAction,
  csrfToken,
  userName,
  canSend,
  canAutoStart,
  canManageTickets,
  canViewApprovals
}: {
  caseData: CaseDetail;
  initialMessages: ChatMessage[];
  initialTimeline: TimelineEvent[];
  initialTicketDraft: TicketDraft | null;
  initialAction: CaseAction | null;
  csrfToken: string;
  userName: string;
  canSend: boolean;
  canAutoStart: boolean;
  canManageTickets: boolean;
  canViewApprovals: boolean;
}) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [timeline, setTimeline] = useState<TimelineEvent[]>(initialTimeline);
  const [status, setStatus] = useState<WorkspaceStatus>({
    status: caseData.status,
    label: caseData.status_label,
    phase: caseData.phase
  });
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [streamSteps, setStreamSteps] = useState<StepState[]>([]);
  const [streamCitations, setStreamCitations] = useState<MessageCitation[]>([]);
  const [lastRefused, setLastRefused] = useState(caseData.status === "REFUSED");
  const [ticketDraft, setTicketDraft] = useState<TicketDraft | null>(initialTicketDraft);
  const [action, setAction] = useState<CaseAction | null>(initialAction);
  const [confirmedTicket, setConfirmedTicket] = useState<TicketDetail | null>(null);
  const [ticketId, setTicketId] = useState<string | null>(caseData.ticket_id);
  const [error, setError] = useState<string | null>(null);
  const [sourceView, setSourceView] = useState<{
    citation: MessageCitation;
    locator: KnowledgeLocator | null;
    loading: boolean;
  } | null>(null);
  const autoStarted = useRef(false);
  const textRef = useRef("");
  const citationRef = useRef<MessageCitation[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setTimeline(initialTimeline);
  }, [initialTimeline]);

  useEffect(() => {
    setAction(initialAction);
  }, [initialAction]);

  useEffect(() => {
    setTicketId(caseData.ticket_id);
  }, [caseData.ticket_id]);

  useEffect(() => {
    if (!canSend || !canAutoStart || initialMessages.length > 0 || autoStarted.current) return;
    autoStarted.current = true;
    let initialContent = caseData.title;
    try {
      const stored = window.sessionStorage.getItem(`safedesk.initial.${caseData.id}`);
      if (stored) {
        initialContent = stored;
        window.sessionStorage.removeItem(`safedesk.initial.${caseData.id}`);
      }
    } catch {}
    void sendMessage(initialContent);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAutoStart, canSend, caseData.id, caseData.title, initialMessages.length]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [messages, streamText, streaming]);

  const latestAssistant = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant") ?? null,
    [messages]
  );
  const activeCitations = streaming
    ? streamCitations
    : latestAssistant?.citations ?? EMPTY_CITATIONS;
  const activeRefused = streaming ? false : lastRefused;

  async function sendMessage(rawContent: string) {
    const content = rawContent.trim();
    if (!content || streaming || !canSend) return;

    const clientId =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `web_${Date.now()}`;
    const optimisticMessage: ChatMessage = {
      id: `local_${clientId}`,
      case_id: caseData.id,
      role: "user",
      content,
      status: "COMPLETE",
      citations: [],
      model_version: "",
      prompt_version: "",
      created_at: new Date().toISOString()
    };

    setMessages((current) => [...current, optimisticMessage]);
    setDraft("");
    setError(null);
    setStreaming(true);
    setStreamText("");
    textRef.current = "";
    citationRef.current = [];
    setStreamCitations([]);
    setStreamSteps([]);
    setLastRefused(false);
    setStatus((current) => ({
      ...current,
      status: "RETRIEVING",
      label: "正在检索",
      phase: "retrieval"
    }));

    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(caseData.id)}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken
        },
        body: JSON.stringify({ content, client_message_id: clientId })
      });

      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as
          | { error?: { message?: string; code?: string; request_id?: string } }
          | null;
        throw new ApiRequestError(
          body?.error?.message ?? "发送消息失败，请稍后重试",
          body?.error?.code ?? "REQUEST_FAILED",
          response.status,
          body?.error?.request_id
        );
      }

      await consumeSSE<Record<string, unknown>>(response, (frame) => {
        if (frame.event === "step") {
          const step = frame.data as { name?: string; label?: string; status?: string };
          if (!step.name || !step.label) return;
          const stepName = step.name;
          const stepLabel = step.label;
          const stepStatus = step.status ?? "running";
          setStreamSteps((current) => {
            const next = current.filter((item) => item.name !== stepName);
            next.push({ name: stepName, label: stepLabel, status: stepStatus });
            return next;
          });
        } else if (frame.event === "token") {
          const text = String((frame.data as { text?: string }).text ?? "");
          textRef.current += text;
          setStreamText(textRef.current);
        } else if (frame.event === "citation") {
          const raw = frame.data as unknown as MessageCitation & { citation_id?: string };
          const citation: MessageCitation = {
            ...raw,
            id: raw.id ?? raw.citation_id ?? `${raw.doc_id}-${raw.chunk_id}`
          };
          citationRef.current = [...citationRef.current, citation];
          setStreamCitations(citationRef.current);
        } else if (frame.event === "status") {
          const value = frame.data as { case_status?: string; status_label?: string; phase?: string };
          if (value.case_status) {
            setStatus({
              status: value.case_status,
              label: value.status_label ?? value.case_status,
              phase: value.phase ?? "solution"
            });
          }
        } else if (frame.event === "done") {
          const value = frame.data as { refused?: boolean };
          setLastRefused(Boolean(value.refused));
        } else if (frame.event === "ticket_draft") {
          setTicketDraft(frame.data as unknown as TicketDraft);
        } else if (frame.event === "action") {
          const value = frame.data as {
            action: ActionRecord;
            approval: Approval;
            case: { status: string; status_label: string };
          };
          setAction({
            ...value.action,
            case_status: value.case.status,
            case_status_label: value.case.status_label,
            approval: value.approval,
            execution: null,
            permissions: { can_view: true, can_decide: false },
            blockers: []
          });
        } else if (frame.event === "error") {
          const value = frame.data as { message?: string };
          setError(value.message ?? "生成回答失败，请稍后重试");
        }
      });

      const synced = await clientRequest<MessageListResponse>(
        `/api/cases/${encodeURIComponent(caseData.id)}/messages`
      );
      setMessages(synced.items);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "发送消息失败，请稍后重试");
      setMessages((current) => current.filter((message) => message.id !== optimisticMessage.id));
    } finally {
      setStreaming(false);
    }
  }

  async function openSource(citation: MessageCitation) {
    setSourceView({ citation, locator: null, loading: true });
    try {
      const locator = await clientRequest<KnowledgeLocator>(
        `/api/knowledge/documents/${encodeURIComponent(citation.doc_id)}/locator?chunk_id=${encodeURIComponent(citation.chunk_id)}`
      );
      setSourceView({ citation, locator, loading: false });
    } catch {
      setSourceView({ citation, locator: null, loading: false });
    }
  }

  function handleTicketConfirmed(ticket: TicketDetail) {
    setConfirmedTicket(ticket);
    setTicketDraft(null);
    setTicketId(ticket.id);
    setStatus({ status: "TICKET_OPEN", label: "已转工单", phase: "solution" });
    router.refresh();
  }

  return (
    <>
      <div className="grid items-start gap-4 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[310px_minmax(0,1fr)_290px]">
        <section className="sd-card flex h-[680px] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 className="text-xs font-semibold text-ink">对话</h2>
            <span className="text-[9px] text-ink-tertiary">依据可追溯</span>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4" aria-live="polite">
            {messages.map((message) =>
              message.role === "user" ? (
                <div key={message.id} className="ml-5">
                  <p className="mb-1 text-right text-[9px] text-ink-tertiary">{userName}</p>
                  <div className="rounded-card rounded-tr-[3px] bg-brand-soft px-3 py-2.5 text-xs leading-6 text-ink">
                    {message.content}
                  </div>
                </div>
              ) : (
                <div key={message.id} className="flex items-start gap-2">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand text-[9px] font-semibold text-white">
                    S
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="rounded-card rounded-tl-[3px] border border-line bg-subtle px-3 py-2.5 text-[11px] leading-5 text-ink-secondary">
                      {message.content}
                    </div>
                    {message.citations.length > 0 && (
                      <p className="mt-1.5 text-[9px] text-ink-tertiary">
                        引用 {message.citations.length} 条依据 · 可在中间查看原文
                      </p>
                    )}
                    {message.status === "COMPLETE" && (
                      <MessageFeedback messageId={message.id} csrfToken={csrfToken} />
                    )}
                  </div>
                </div>
              )
            )}

            {streaming && (
              <div className="flex items-start gap-2">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand text-[9px] font-semibold text-white">
                  S
                </span>
                <div className="min-w-0 flex-1">
                  {streamSteps.length > 0 && (
                    <ol className="mb-2 space-y-1.5 rounded-control border border-line bg-surface px-3 py-2.5">
                      {streamSteps.map((step) => (
                        <li key={step.name} className="flex items-center gap-2 text-[10px] text-ink-secondary">
                          <span
                            className={cn(
                              "grid h-3.5 w-3.5 place-items-center rounded-full border text-[8px]",
                              step.status === "complete"
                                ? "border-brand bg-brand text-white"
                                : "border-brand-border bg-brand-soft text-brand"
                            )}
                          >
                            {step.status === "complete" ? "✓" : "•"}
                          </span>
                          {step.label}
                        </li>
                      ))}
                    </ol>
                  )}
                  <div className="rounded-card rounded-tl-[3px] border border-line bg-subtle px-3 py-2.5 text-[11px] leading-5 text-ink-secondary">
                    {streamText ? (
                      <span className="whitespace-pre-wrap">{streamText}</span>
                    ) : (
                      <span className="inline-flex items-center gap-2 text-ink-tertiary">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />
                        正在整理可核对依据…
                      </span>
                    )}
                    <span className="ml-0.5 inline-block h-3 w-[2px] animate-pulse bg-brand align-middle" />
                  </div>
                </div>
              </div>
            )}

            {messages.length === 0 && !streaming && (
              <div className="flex items-start gap-2">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand text-[9px] font-semibold text-white">
                  S
                </span>
                <div className="rounded-card rounded-tl-[3px] border border-line bg-subtle px-3 py-2.5 text-[11px] leading-5 text-ink-secondary">
                  描述你的补充信息后，我会先检索内部知识，再给出带来源的回答。
                </div>
              </div>
            )}
          </div>

          <form
            className="border-t border-line p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage(draft);
            }}
          >
            <textarea
              ref={composerRef}
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value);
                setError(null);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              disabled={!canSend || streaming}
              maxLength={2000}
              className="min-h-16 w-full resize-none rounded-control border border-line bg-surface px-3 py-2 text-xs leading-5 text-ink outline-none transition-colors focus:border-brand disabled:bg-subtle disabled:text-ink-tertiary"
              placeholder={streaming ? "正在生成回答…" : "补充说明或继续追问"}
            />
            <div className="mt-2 flex items-center justify-between gap-2 text-[9px] text-ink-tertiary">
              <span>Enter 发送 · Shift + Enter 换行</span>
              <button
                type="submit"
                disabled={!canSend || streaming || !draft.trim()}
                className="rounded-control bg-brand px-2.5 py-1 text-[10px] font-medium text-white transition-opacity disabled:opacity-40"
              >
                {streaming ? "生成中…" : "发送"}
              </button>
            </div>
          </form>
        </section>

        <section className="min-h-[680px] space-y-4">
          <div className="sd-card overflow-hidden">
            <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="grid h-7 w-7 place-items-center rounded-control bg-brand-soft text-brand">
                    <Icon name={activeRefused ? "shield" : "spark"} size={15} />
                  </span>
                  <h2 className="text-sm font-semibold text-ink">
                    {activeRefused ? "无法处理此请求" : "知识回答"}
                  </h2>
                </div>
                <p className="mt-2 text-[11px] leading-5 text-ink-secondary">
                  {activeRefused
                    ? "这是安全分支，不会执行越权操作。"
                    : "结论与步骤只使用检索到的内部知识片段，引用由服务端组装。"}
                </p>
              </div>
              <span className="sd-chip">
                {streaming
                  ? "生成中"
                  : activeRefused
                    ? "安全拒答"
                    : activeCitations.length > 0
                      ? `证据充分 · ${activeCitations.length} 条`
                      : "等待问题"}
              </span>
            </div>

            <div className="px-5 py-5">
              {latestAssistant || streaming ? (
                <AnswerBody
                  content={streaming ? streamText : latestAssistant?.content ?? ""}
                  refused={activeRefused}
                  streaming={streaming}
                  onContinue={() => composerRef.current?.focus()}
                />
              ) : (
                <div className="mx-auto max-w-lg py-8 text-center">
                  <span className="mx-auto grid h-11 w-11 place-items-center rounded-overlay border border-line bg-subtle text-ink-tertiary">
                    <Icon name="branch" size={20} />
                  </span>
                  <h3 className="mt-4 text-sm font-semibold text-ink">等待你的补充信息</h3>
                  <p className="mt-2 text-[11px] leading-6 text-ink-secondary">
                    发送问题后，这里会依次呈现检索步骤、回答、证据来源和来源原文。
                  </p>
                </div>
              )}
            </div>
          </div>

          {action && (
            <ActionCard action={action} canViewApprovals={canViewApprovals} />
          )}

          {ticketDraft && (
            <TicketDraftCard
              draft={ticketDraft}
              caseId={caseData.id}
              csrfToken={csrfToken}
              canManage={canManageTickets}
              onConfirmed={handleTicketConfirmed}
              onError={setError}
            />
          )}

          {confirmedTicket && (
            <div className="sd-card border-success/40 p-5">
              <div className="flex items-start gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-control bg-success-soft text-success">
                  <Icon name="ticket" size={17} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="sd-eyebrow">工单已创建</p>
                  <h2 className="mt-1 text-sm font-semibold text-ink">
                    {confirmedTicket.title}
                  </h2>
                  <p className="mt-1 text-[10px] text-ink-tertiary">
                    {confirmedTicket.id} · {confirmedTicket.status_label} · 版本{" "}
                    {confirmedTicket.version}
                  </p>
                  <Link
                    href={`/tickets/${encodeURIComponent(confirmedTicket.id)}`}
                    className="sd-button-primary mt-3 h-8"
                  >
                    打开工单
                    <Icon name="arrow-right" size={13} />
                  </Link>
                </div>
              </div>
            </div>
          )}

          <div id="evidence-panel" className="sd-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div>
                <h2 className="text-xs font-semibold text-ink">证据与来源</h2>
                <p className="mt-0.5 text-[9px] text-ink-tertiary">引用原文来自文档切分快照</p>
              </div>
              <span className="text-[9px] text-ink-tertiary">{activeCitations.length} 条</span>
            </div>
            {activeCitations.length === 0 ? (
              <p className="px-4 py-7 text-center text-[10px] text-ink-tertiary">
                {activeRefused ? "拒答不引用知识片段，避免误导。" : "回答生成后会在这里显示引用。"}
              </p>
            ) : (
              <ol className="divide-y divide-line">
                {activeCitations.map((citation) => (
                  <li key={citation.id || `${citation.doc_id}-${citation.chunk_id}`} className="px-4 py-4">
                    <div className="flex items-start gap-3">
                      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-soft text-[10px] font-semibold text-brand">
                        {citation.index}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          <p className="text-[11px] font-medium text-ink">{citation.title}</p>
                          <span className="text-[9px] text-ink-tertiary">
                            {citation.version} · 第 {citation.page} 页 · {citation.section || "正文"}
                          </span>
                          {!citation.source_available && (
                            <span className="rounded-full bg-warning-soft px-1.5 py-0.5 text-[8px] text-warning">
                              来源已停用
                            </span>
                          )}
                        </div>
                        <p className="mt-2 border-l-[3px] border-brand-border bg-brand-soft/60 px-3 py-2 text-[10px] leading-5 text-ink-secondary">
                          {citation.quote}
                        </p>
                        <button
                          type="button"
                          onClick={() => void openSource(citation)}
                          className="mt-2 text-[10px] font-medium text-brand hover:underline"
                        >
                          查看原文
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>

        <aside className="space-y-4 lg:col-span-2 xl:col-span-1">
          <div className="sd-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold text-ink">Case 状态</h2>
              <StatusBadge status={status.status} label={status.label} />
            </div>
            <dl className="mt-4 space-y-2.5 text-[10px]">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-tertiary">当前阶段</dt>
                <dd className="font-medium text-ink">{PHASE_LABELS[status.phase] ?? status.phase}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-tertiary">知识依据</dt>
                <dd className="font-medium text-ink">{activeCitations.length} 条引用</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-tertiary">最近更新</dt>
                <dd className="text-ink">{formatDateTime(caseData.updated_at)}</dd>
              </div>
            </dl>
          </div>

          <div className="sd-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="text-xs font-semibold text-ink">时间线</h2>
              <span className="text-[9px] text-ink-tertiary">{timeline.length} 条事件</span>
            </div>
            <ol className="max-h-[430px] overflow-y-auto px-4 py-4">
              {timeline.length === 0 ? (
                <li className="py-5 text-center text-[10px] text-ink-tertiary">暂无事件</li>
              ) : (
                timeline.map((event, index) => (
                  <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
                    {index < timeline.length - 1 && (
                      <span
                        className="absolute left-[5px] top-3 h-[calc(100%-4px)] w-px bg-line"
                        aria-hidden="true"
                      />
                    )}
                    <span className="relative mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border-2 border-surface bg-brand ring-1 ring-brand-border" />
                    <div className="min-w-0">
                      <p className="text-[10px] font-medium text-ink">{event.summary}</p>
                      <p className="mt-0.5 text-[9px] text-ink-tertiary">
                        {formatDateTime(event.created_at)}
                        {event.actor_role ? ` · ${event.actor_role}` : ""}
                      </p>
                    </div>
                  </li>
                ))
              )}
            </ol>
          </div>

          <div className="sd-card p-4">
            <h2 className="text-xs font-semibold text-ink">关联对象</h2>
            <div className="mt-3 grid gap-2">
              {ticketId ? (
                <Link
                  href={`/tickets/${encodeURIComponent(ticketId)}`}
                  className="rounded-control border border-brand-border bg-brand-soft px-3 py-2 text-[10px] font-medium text-brand transition-colors hover:border-brand"
                >
                  Ticket <span className="float-right">查看</span>
                </Link>
              ) : (
                <div className="rounded-control border border-dashed border-line-strong px-3 py-2 text-[10px] text-ink-tertiary">
                  Ticket <span className="float-right">待确认</span>
                </div>
              )}
              {action ? (
                <>
                  {canViewApprovals ? (
                    <Link
                      href={`/approvals?approval=${encodeURIComponent(action.approval.id)}`}
                      className="rounded-control border border-brand-border bg-brand-soft px-3 py-2 text-[10px] font-medium text-brand transition-colors hover:border-brand"
                    >
                      Action <span className="float-right">{action.status_label}</span>
                    </Link>
                  ) : (
                    <div className="rounded-control border border-line bg-subtle px-3 py-2 text-[10px] text-ink-secondary">
                      Action <span className="float-right">{action.status_label}</span>
                    </div>
                  )}
                  {canViewApprovals ? (
                    <Link
                      href={`/approvals?approval=${encodeURIComponent(action.approval.id)}`}
                      className="rounded-control border border-brand-border bg-brand-soft px-3 py-2 text-[10px] font-medium text-brand transition-colors hover:border-brand"
                    >
                      Approval <span className="float-right">{action.approval.status_label}</span>
                    </Link>
                  ) : (
                    <div className="rounded-control border border-line bg-subtle px-3 py-2 text-[10px] text-ink-secondary">
                      Approval <span className="float-right">{action.approval.status_label}</span>
                    </div>
                  )}
                </>
              ) : (
                <div className="rounded-control border border-dashed border-line-strong px-3 py-2 text-[10px] text-ink-tertiary">
                  Action / Approval <span className="float-right">未生成</span>
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      {error && (
        <div
          className="fixed bottom-5 left-1/2 z-50 w-[min(560px,calc(100%-2rem))] -translate-x-1/2 rounded-card border border-danger bg-danger-soft px-4 py-3 text-xs text-danger shadow-overlay"
          role="alert"
        >
          {error}
        </div>
      )}

      {sourceView && (
        <SourceReader
          state={sourceView}
          onClose={() => setSourceView(null)}
        />
      )}
    </>
  );
}

const PHASE_LABELS: Record<string, string> = {
  intake: "受理",
  retrieval: "查证",
  solution: "方案",
  approval: "审批与执行",
  done: "完成"
};

function AnswerBody({
  content,
  refused,
  streaming,
  onContinue
}: {
  content: string;
  refused: boolean;
  streaming: boolean;
  onContinue: () => void;
}) {
  const lines = content.split("\n");
  return (
    <div>
      <div className="space-y-1.5 text-[12px] leading-6 text-ink">
        {lines.map((line, index) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={index} className="h-1" />;
          if (["结论", "处理步骤", "下一步", "你可以："].includes(trimmed)) {
            return (
              <h3 key={index} className="pt-2 text-[11px] font-semibold text-brand">
                {trimmed}
              </h3>
            );
          }
          const numbered = /^\d+[.、]/.test(trimmed);
          return (
            <p
              key={index}
              className={cn(
                "whitespace-pre-wrap",
                numbered ? "pl-1 text-[11px] leading-6 text-ink-secondary" : "text-ink-secondary"
              )}
            >
              {trimmed}
            </p>
          );
        })}
        {!content && streaming && <span className="text-ink-tertiary">正在生成…</span>}
      </div>
      {!streaming && (
        <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <button type="button" onClick={onContinue} className="sd-button-secondary h-8">
            继续追问
          </button>
          {refused ? (
            <Link href="/tickets" className="sd-button-primary h-8">
              转人工处理
              <Icon name="arrow-right" size={13} />
            </Link>
          ) : (
            <a href="#evidence-panel" className="sd-button-primary h-8">
              核对引用来源
              <Icon name="arrow-right" size={13} />
            </a>
          )}
        </div>
      )}
    </div>
  );
}

function SourceReader({
  state,
  onClose
}: {
  state: { citation: MessageCitation; locator: KnowledgeLocator | null; loading: boolean };
  onClose: () => void;
}) {
  const locator = state.locator;
  const quoteIndex = locator
    ? locator.raw_content.indexOf(
        state.citation.quote,
        Math.max(0, locator.offset_start - 80)
      )
    : -1;
  const highlightStart = locator
    ? quoteIndex >= 0
      ? quoteIndex
      : locator.offset_start
    : 0;
  const highlightEnd = locator
    ? quoteIndex >= 0
      ? quoteIndex + state.citation.quote.length
      : locator.offset_end
    : 0;
  const before = locator ? locator.raw_content.slice(0, highlightStart) : "";
  const highlighted = locator ? locator.raw_content.slice(highlightStart, highlightEnd) : "";
  const after = locator ? locator.raw_content.slice(highlightEnd) : "";

  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-ink/30 p-4" role="dialog" aria-modal="true">
      <div className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-overlay border border-line bg-surface shadow-overlay">
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <p className="sd-eyebrow">来源原文</p>
            <h2 className="mt-1 text-sm font-semibold text-ink">{state.citation.title}</h2>
            <p className="mt-1 text-[10px] text-ink-tertiary">
              {state.citation.version} · 第 {state.citation.page} 页 · {state.citation.section || "正文"}
            </p>
          </div>
          <button type="button" onClick={onClose} className="sd-button-secondary h-8" aria-label="关闭原文">
            <Icon name="close" size={14} />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-5">
          {state.loading ? (
            <p className="py-10 text-center text-xs text-ink-tertiary">正在定位原文…</p>
          ) : locator ? (
            <pre className="whitespace-pre-wrap font-sans text-[12px] leading-7 text-ink-secondary">
              {before}
              <mark className="rounded-sm bg-brand-soft px-1 py-0.5 text-ink ring-1 ring-brand-border">
                {highlighted || locator.quote}
              </mark>
              {after}
            </pre>
          ) : (
            <div>
              <p className="rounded-control border border-warning bg-warning-soft px-3 py-2 text-[10px] text-warning">
                无法读取完整原文，以下为引用时保存的精确片段。
              </p>
              <p className="mt-3 border-l-[3px] border-brand-border bg-brand-soft px-3 py-2 text-xs leading-6 text-ink-secondary">
                {state.citation.quote}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
