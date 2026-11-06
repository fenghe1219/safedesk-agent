"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type { TicketAssignee, TicketDetail, TimelineEvent } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";
import { StatusBadge } from "./status-badge";

const CATEGORY_OPTIONS = [
  ["account_permission", "账号与权限"],
  ["network_vpn", "网络与 VPN"],
  ["software", "软件与安装"],
  ["hardware", "硬件与设备"],
  ["email_collaboration", "邮箱与协作工具"],
  ["security_incident", "安全事件"],
  ["other", "其他"]
] as const;

const PRIORITY_OPTIONS = ["P1", "P2", "P3", "P4"] as const;

const TRANSITION_OPTIONS: Record<string, Array<[string, string]>> = {
  OPEN: [
    ["ASSIGNED", "分派处理人"],
    ["CANCELLED", "取消工单"]
  ],
  ASSIGNED: [
    ["IN_PROGRESS", "开始处理"],
    ["CANCELLED", "取消工单"]
  ],
  IN_PROGRESS: [
    ["RESOLVED", "标记已解决"],
    ["CANCELLED", "取消工单"]
  ],
  RESOLVED: [
    ["CLOSED", "关闭工单"],
    ["REOPENED", "重新打开"]
  ],
  CLOSED: [["REOPENED", "重新打开"]],
  REOPENED: [
    ["ASSIGNED", "重新分派"],
    ["IN_PROGRESS", "继续处理"]
  ],
  CANCELLED: []
};

const PRIORITY_STYLES: Record<string, string> = {
  P1: "bg-danger-soft text-danger",
  P2: "bg-warning-soft text-warning",
  P3: "bg-info-soft text-info",
  P4: "bg-subtle text-ink-secondary"
};

interface FieldForm {
  category: string;
  priority: string;
  priority_reason: string;
  affected_system: string;
  environment: string;
  error_message: string;
  urgency_reason: string;
  assignee_id: string;
}

function toFieldForm(ticket: TicketDetail): FieldForm {
  return {
    category: ticket.category,
    priority: ticket.priority,
    priority_reason: ticket.priority_reason,
    affected_system: ticket.affected_system ?? "",
    environment: ticket.environment ?? "",
    error_message: ticket.error_message ?? "",
    urgency_reason: ticket.urgency_reason ?? "",
    assignee_id: ticket.assignee_id ?? ""
  };
}

export function TicketDetailConsole({
  ticket: initialTicket,
  timeline,
  assignees,
  csrfToken,
  canManage
}: {
  ticket: TicketDetail;
  timeline: TimelineEvent[];
  assignees: TicketAssignee[];
  csrfToken: string;
  canManage: boolean;
}) {
  const router = useRouter();
  const [ticket, setTicket] = useState(initialTicket);
  const [form, setForm] = useState<FieldForm>(() => toFieldForm(initialTicket));
  const [transitionTo, setTransitionTo] = useState(() => TRANSITION_OPTIONS[initialTicket.status]?.[0]?.[0] ?? "");
  const [transitionAssignee, setTransitionAssignee] = useState(
    initialTicket.assignee_id ?? initialTicket.suggested_assignee_id ?? ""
  );
  const [transitionNote, setTransitionNote] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setTicket(initialTicket);
    setForm(toFieldForm(initialTicket));
    setTransitionTo(TRANSITION_OPTIONS[initialTicket.status]?.[0]?.[0] ?? "");
    setTransitionAssignee(
      initialTicket.assignee_id ?? initialTicket.suggested_assignee_id ?? ""
    );
  }, [initialTicket]);

  function update<K extends keyof FieldForm>(key: K, value: FieldForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setError(null);
    setMessage(null);
  }

  function handleError(err: unknown) {
    if (err instanceof ApiRequestError) {
      setError(
        err.code === "TYPE_CONFLICT"
          ? "工单已被其他操作更新，请刷新后重新提交。"
          : err.message
      );
    } else {
      setError("操作失败，请稍后重试。");
    }
  }

  async function saveFields() {
    if (!canManage || busy) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await clientRequest<TicketDetail>(
        `/api/tickets/${encodeURIComponent(ticket.id)}`,
        {
          method: "PATCH",
          csrfToken,
          body: JSON.stringify({
            version: ticket.version,
            fields: {
              category: form.category,
              priority: form.priority,
              priority_reason: form.priority_reason.trim(),
              affected_system: form.affected_system.trim() || null,
              environment: form.environment.trim() || null,
              error_message: form.error_message.trim() || null,
              urgency_reason: form.urgency_reason.trim() || null,
              assignee_id: form.assignee_id || null
            }
          })
        }
      );
      setTicket(updated);
      setMessage("字段已保存，修改记录已写入审计。");
      router.refresh();
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(false);
    }
  }

  async function applyTransition() {
    if (!canManage || busy || !transitionTo) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await clientRequest<TicketDetail>(
        `/api/tickets/${encodeURIComponent(ticket.id)}/transition`,
        {
          method: "POST",
          csrfToken,
          body: JSON.stringify({
            version: ticket.version,
            to_status: transitionTo,
            assignee_id:
              transitionTo === "ASSIGNED" ? transitionAssignee || null : undefined,
            note: transitionNote.trim() || null
          })
        }
      );
      setTicket(updated);
      setTransitionNote("");
      setMessage(`状态已更新为「${updated.status_label}」。`);
      router.refresh();
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(false);
    }
  }

  async function addNote() {
    if (!canManage || busy || !note.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await clientRequest(`/api/tickets/${encodeURIComponent(ticket.id)}/notes`, {
        method: "POST",
        csrfToken,
        body: JSON.stringify({ content: note.trim() })
      });
      const refreshed = await clientRequest<TicketDetail>(
        `/api/tickets/${encodeURIComponent(ticket.id)}`
      );
      setTicket(refreshed);
      setNote("");
      setMessage("处理备注已添加。");
      router.refresh();
    } catch (err) {
      handleError(err);
    } finally {
      setBusy(false);
    }
  }

  const statusOptions = TRANSITION_OPTIONS[ticket.status] ?? [];

  return (
    <div className="space-y-4">
      <section className="sd-card overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={ticket.status} label={ticket.status_label} />
              <span className="rounded-full bg-brand-soft px-2.5 py-1 text-[10px] font-medium text-brand">
                {ticket.category_label}
              </span>
              <span
                className={cn(
                  "rounded-full px-2.5 py-1 text-[10px] font-medium",
                  PRIORITY_STYLES[ticket.priority] ?? "bg-subtle text-ink-secondary"
                )}
              >
                {ticket.priority_label}
              </span>
              <span className="text-[9px] text-ink-tertiary">版本 {ticket.version}</span>
            </div>
            <h1 className="mt-2.5 text-[20px] font-semibold leading-7 tracking-[-0.01em] text-ink">
              {ticket.title}
            </h1>
            <p className="mt-1.5 text-[10px] text-ink-tertiary">
              {ticket.id} · 提交人 {ticket.requester_name} · 创建于{" "}
              {formatDateTime(ticket.created_at)}
            </p>
          </div>
          <Link
            href={`/cases/${encodeURIComponent(ticket.case_id)}`}
            className="sd-button-secondary h-8 shrink-0"
          >
            返回 Case
            <Icon name="arrow-right" size={13} />
          </Link>
        </div>

        <div className="grid gap-4 px-5 py-4 text-[11px] lg:grid-cols-3">
          <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
            <p className="text-[9px] text-ink-tertiary">处理人</p>
            <p className="mt-1 font-medium text-ink">{ticket.assignee_name || "未分派"}</p>
            {ticket.suggested_assignee_name && (
              <p className="mt-1 text-[9px] leading-5 text-ink-tertiary">
                建议：{ticket.suggested_assignee_name}。{ticket.suggested_assignee_reason}
              </p>
            )}
          </div>
          <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
            <p className="text-[9px] text-ink-tertiary">影响系统 / 环境</p>
            <p className="mt-1 font-medium text-ink">
              {ticket.affected_system || "未填写"} · {ticket.environment || "未填写"}
            </p>
            <p className="mt-1 text-[9px] text-ink-tertiary">
              报错：{ticket.error_message || "未填写"}
            </p>
          </div>
          <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
            <p className="text-[9px] text-ink-tertiary">优先级理由</p>
            <p className="mt-1 leading-5 text-ink-secondary">{ticket.priority_reason}</p>
            {ticket.urgency_reason && (
              <p className="mt-1 text-[9px] text-ink-tertiary">
                紧急原因：{ticket.urgency_reason}
              </p>
            )}
          </div>
        </div>
      </section>

      {canManage && (
        <section className="grid gap-4 lg:grid-cols-2">
          <div className="sd-card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">修正分诊字段</h2>
              <span className="text-[9px] text-ink-tertiary">乐观锁 v{ticket.version}</span>
            </div>
            <div className="mt-4 grid gap-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="sd-label">分类</span>
                  <select
                    className="sd-input"
                    value={form.category}
                    onChange={(event) => update("category", event.target.value)}
                  >
                    {CATEGORY_OPTIONS.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="sd-label">优先级</span>
                  <select
                    className="sd-input"
                    value={form.priority}
                    onChange={(event) => update("priority", event.target.value)}
                  >
                    {PRIORITY_OPTIONS.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="block">
                <span className="sd-label">优先级理由</span>
                <textarea
                  className="sd-textarea min-h-16 text-xs"
                  value={form.priority_reason}
                  maxLength={300}
                  onChange={(event) => update("priority_reason", event.target.value)}
                />
              </label>
              <label className="block">
                <span className="sd-label">处理人</span>
                <select
                  className="sd-input"
                  value={form.assignee_id}
                  onChange={(event) => update("assignee_id", event.target.value)}
                >
                  <option value="">未分派</option>
                  {assignees.map((assignee) => (
                    <option key={assignee.id} value={assignee.id}>
                      {assignee.name} · {assignee.department} · {assignee.open_ticket_count} 个活跃
                    </option>
                  ))}
                </select>
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="sd-label">影响系统</span>
                  <input
                    className="sd-input"
                    value={form.affected_system}
                    maxLength={120}
                    onChange={(event) => update("affected_system", event.target.value)}
                  />
                </label>
                <label className="block">
                  <span className="sd-label">环境</span>
                  <input
                    className="sd-input"
                    value={form.environment}
                    maxLength={120}
                    onChange={(event) => update("environment", event.target.value)}
                  />
                </label>
              </div>
              <label className="block">
                <span className="sd-label">报错信息</span>
                <input
                  className="sd-input"
                  value={form.error_message}
                  maxLength={1000}
                  onChange={(event) => update("error_message", event.target.value)}
                />
              </label>
              <button
                type="button"
                onClick={() => void saveFields()}
                disabled={busy || !form.priority_reason.trim()}
                className="sd-button-primary h-8 justify-self-start"
              >
                {busy ? "正在保存…" : "保存字段"}
              </button>
            </div>
          </div>

          <div className="sd-card p-5">
            <h2 className="text-sm font-semibold text-ink">状态流转</h2>
            {statusOptions.length === 0 ? (
              <p className="mt-4 text-[11px] text-ink-tertiary">当前状态没有可执行的操作。</p>
            ) : (
              <div className="mt-4 grid gap-3">
                <label className="block">
                  <span className="sd-label">目标状态</span>
                  <select
                    className="sd-input"
                    value={transitionTo}
                    onChange={(event) => setTransitionTo(event.target.value)}
                  >
                    {statusOptions.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                {transitionTo === "ASSIGNED" && (
                  <label className="block">
                    <span className="sd-label">处理人</span>
                    <select
                      className="sd-input"
                      value={transitionAssignee}
                      onChange={(event) => setTransitionAssignee(event.target.value)}
                    >
                      <option value="">请选择</option>
                      {assignees.map((assignee) => (
                        <option key={assignee.id} value={assignee.id}>
                          {assignee.name} · {assignee.department} · {assignee.open_ticket_count} 个活跃
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="block">
                  <span className="sd-label">流转备注（可选）</span>
                  <textarea
                    className="sd-textarea min-h-16 text-xs"
                    value={transitionNote}
                    maxLength={1000}
                    onChange={(event) => setTransitionNote(event.target.value)}
                    placeholder="例如：已联系用户，开始处理"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => void applyTransition()}
                  disabled={busy || !transitionTo}
                  className="sd-button-primary h-8 justify-self-start"
                >
                  {busy ? "正在提交…" : "执行流转"}
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      {(error || message) && (
        <div
          className={cn(
            "rounded-card border px-4 py-3 text-[11px]",
            error
              ? "border-danger bg-danger-soft text-danger"
              : "border-success bg-success-soft text-success"
          )}
          role={error ? "alert" : "status"}
        >
          {error ?? message}
        </div>
      )}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="sd-card overflow-hidden">
          <div className="border-b border-line px-5 py-3.5">
            <h2 className="text-sm font-semibold text-ink">问题描述</h2>
          </div>
          <div className="px-5 py-5">
            <p className="whitespace-pre-wrap text-[12px] leading-7 text-ink-secondary">
              {ticket.description}
            </p>
            <dl className="mt-5 grid gap-3 border-t border-line pt-4 text-[11px] sm:grid-cols-2">
              <div>
                <dt className="text-[9px] text-ink-tertiary">影响系统</dt>
                <dd className="mt-0.5 text-ink-secondary">{ticket.affected_system || "未填写"}</dd>
              </div>
              <div>
                <dt className="text-[9px] text-ink-tertiary">环境</dt>
                <dd className="mt-0.5 text-ink-secondary">{ticket.environment || "未填写"}</dd>
              </div>
              <div>
                <dt className="text-[9px] text-ink-tertiary">报错信息</dt>
                <dd className="mt-0.5 break-words text-ink-secondary">
                  {ticket.error_message || "未填写"}
                </dd>
              </div>
              <div>
                <dt className="text-[9px] text-ink-tertiary">紧急原因</dt>
                <dd className="mt-0.5 text-ink-secondary">{ticket.urgency_reason || "未填写"}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="space-y-4">
          <div className="sd-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="text-xs font-semibold text-ink">处理备注</h2>
              <span className="text-[9px] text-ink-tertiary">{ticket.notes.length} 条</span>
            </div>
            <div className="max-h-[320px] space-y-3 overflow-y-auto px-4 py-4">
              {ticket.notes.length === 0 ? (
                <p className="py-4 text-center text-[10px] text-ink-tertiary">
                  {canManage ? "暂无处理备注。" : "内部处理备注仅对支持人员可见。"}
                </p>
              ) : (
                ticket.notes.map((item) => (
                  <div key={item.id} className="rounded-control border border-line bg-subtle px-3 py-2.5">
                    <p className="text-[10px] leading-5 text-ink-secondary">{item.content}</p>
                    <p className="mt-1 text-[9px] text-ink-tertiary">
                      {item.author_name} · {formatDateTime(item.created_at)}
                    </p>
                  </div>
                ))
              )}
            </div>
            {canManage && (
              <div className="border-t border-line p-3">
                <textarea
                  className="sd-textarea min-h-16 text-xs"
                  value={note}
                  maxLength={2000}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="记录处理过程或内部备注"
                />
                <button
                  type="button"
                  onClick={() => void addNote()}
                  disabled={busy || !note.trim()}
                  className="sd-button-secondary mt-2 h-8"
                >
                  添加备注
                </button>
              </div>
            )}
          </div>

          <div className="sd-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="text-xs font-semibold text-ink">时间线</h2>
              <span className="text-[9px] text-ink-tertiary">{timeline.length} 条</span>
            </div>
            <ol className="max-h-[360px] overflow-y-auto px-4 py-4">
              {timeline.length === 0 ? (
                <li className="py-5 text-center text-[10px] text-ink-tertiary">暂无事件</li>
              ) : (
                timeline.map((event, index) => (
                  <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
                    {index < timeline.length - 1 && (
                      <span className="absolute left-[5px] top-3 h-[calc(100%-4px)] w-px bg-line" />
                    )}
                    <span className="relative mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border-2 border-surface bg-brand ring-1 ring-brand-border" />
                    <div className="min-w-0">
                      <p className="text-[10px] font-medium text-ink">{event.summary}</p>
                      <p className="mt-0.5 text-[9px] text-ink-tertiary">
                        {formatDateTime(event.created_at)}
                      </p>
                    </div>
                  </li>
                ))
              )}
            </ol>
          </div>
        </div>
      </section>
    </div>
  );
}
