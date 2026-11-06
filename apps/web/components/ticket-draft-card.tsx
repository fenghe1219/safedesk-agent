"use client";

import { useEffect, useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type { TicketCreateResponse, TicketDetail, TicketDraft } from "@/lib/types";
import { Icon } from "./icons";

const CATEGORY_OPTIONS = [
  ["account_permission", "账号与权限"],
  ["network_vpn", "网络与 VPN"],
  ["software", "软件与安装"],
  ["hardware", "硬件与设备"],
  ["email_collaboration", "邮箱与协作工具"],
  ["security_incident", "安全事件"],
  ["other", "其他"]
] as const;

const PRIORITY_OPTIONS = [
  ["P1", "P1 紧急"],
  ["P2", "P2 高"],
  ["P3", "P3 常规"],
  ["P4", "P4 低"]
] as const;

const FIELD_LABELS: Record<string, string> = {
  title: "问题标题",
  description: "问题描述",
  category: "分类",
  priority: "优先级",
  priority_reason: "优先级理由",
  affected_system: "影响系统",
  environment: "操作系统或设备环境",
  error_message: "具体报错或错误码",
  urgency_reason: "紧急原因"
};

interface DraftForm {
  title: string;
  description: string;
  category: string;
  priority: string;
  priority_reason: string;
  affected_system: string;
  environment: string;
  error_message: string;
  urgency_reason: string;
}

function draftToForm(draft: TicketDraft): DraftForm {
  return {
    title: draft.title,
    description: draft.description,
    category: draft.category,
    priority: draft.priority,
    priority_reason: draft.priority_reason,
    affected_system: draft.affected_system ?? "",
    environment: draft.environment ?? "",
    error_message: draft.error_message ?? "",
    urgency_reason: draft.urgency_reason ?? ""
  };
}

export function TicketDraftCard({
  draft,
  caseId,
  csrfToken,
  canManage,
  onConfirmed,
  onError
}: {
  draft: TicketDraft;
  caseId: string;
  csrfToken: string;
  canManage: boolean;
  onConfirmed: (ticket: TicketDetail) => void;
  onError: (message: string) => void;
}) {
  const [form, setForm] = useState<DraftForm>(() => draftToForm(draft));
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setForm(draftToForm(draft));
    setEditing(false);
  }, [draft]);

  const confidence = draft.fields.category_confidence;
  const confidenceText =
    typeof confidence === "number" ? `分类置信度 ${Math.round(confidence * 100)}%` : null;

  function update<K extends keyof DraftForm>(key: K, value: DraftForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setLocalError(null);
  }

  async function confirmDraft() {
    if (!canManage || busy) return;
    setBusy(true);
    setLocalError(null);
    try {
      const response = await clientRequest<TicketCreateResponse>("/api/tickets", {
        method: "POST",
        csrfToken,
        body: JSON.stringify({
          case_id: caseId,
          draft_version: draft.version,
          fields: {
            title: form.title.trim(),
            description: form.description.trim(),
            category: form.category,
            priority: form.priority,
            priority_reason: form.priority_reason.trim(),
            affected_system: form.affected_system.trim() || null,
            environment: form.environment.trim() || null,
            error_message: form.error_message.trim() || null,
            urgency_reason: form.urgency_reason.trim() || null,
            suggested_assignee_id: draft.suggested_assignee_id
          }
        })
      });
      onConfirmed(response.ticket);
    } catch (error) {
      const message =
        error instanceof ApiRequestError
          ? error.code === "TYPE_CONFLICT"
            ? "草稿已被更新，请刷新页面后重新确认。"
            : error.message
          : "创建工单失败，请稍后重试。";
      setLocalError(message);
      onError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sd-card overflow-hidden border-warning/60">
      <div className="flex items-start justify-between gap-3 border-b border-line bg-warning-soft/40 px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-control bg-warning-soft text-warning">
              <Icon name="ticket" size={15} />
            </span>
            <h2 className="text-sm font-semibold text-ink">工单草稿</h2>
            <span className="rounded-full bg-warning-soft px-2 py-0.5 text-[9px] font-medium text-warning">
              待确认
            </span>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-ink-secondary">
            草稿不会出现在工单列表中，确认创建后才会关联 Case 并进入人工处理。
          </p>
        </div>
        <span className="sd-chip shrink-0">{draft.status_label}</span>
      </div>

      <div className="px-5 py-5">
        {draft.missing_fields.length > 0 && (
          <div className="mb-4 rounded-control border border-warning bg-warning-soft px-3 py-2.5 text-[10px] leading-5 text-warning">
            仍缺少：{draft.missing_fields.map((field) => FIELD_LABELS[field] ?? field).join("、")}。
            继续在对话中补充后，草稿会在原位更新。
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-brand-soft px-2.5 py-1 text-[10px] font-medium text-brand">
            {draft.category_label}
          </span>
          <span className="rounded-full bg-surface px-2.5 py-1 text-[10px] font-medium text-ink-secondary ring-1 ring-line">
            {draft.priority_label}
          </span>
          {confidenceText && (
            <span className="text-[9px] text-ink-tertiary">{confidenceText}</span>
          )}
        </div>

        {editing && canManage ? (
          <div className="mt-4 grid gap-3">
            <label className="block">
              <span className="sd-label">标题</span>
              <input
                className="sd-input"
                value={form.title}
                maxLength={120}
                onChange={(event) => update("title", event.target.value)}
              />
            </label>
            <label className="block">
              <span className="sd-label">问题描述</span>
              <textarea
                className="sd-textarea min-h-20 text-xs"
                value={form.description}
                maxLength={2000}
                onChange={(event) => update("description", event.target.value)}
              />
            </label>
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
                  {PRIORITY_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
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
                <span className="sd-label">操作系统或设备环境</span>
                <input
                  className="sd-input"
                  value={form.environment}
                  maxLength={120}
                  onChange={(event) => update("environment", event.target.value)}
                />
              </label>
            </div>
            <label className="block">
              <span className="sd-label">具体报错或错误码</span>
              <input
                className="sd-input"
                value={form.error_message}
                maxLength={1000}
                onChange={(event) => update("error_message", event.target.value)}
              />
            </label>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <button
                type="button"
                disabled={busy || !form.title.trim() || !form.priority_reason.trim()}
                onClick={() => void confirmDraft()}
                className="sd-button-primary h-8"
              >
                {busy ? "正在创建…" : "确认创建工单"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setForm(draftToForm(draft));
                  setLocalError(null);
                }}
                className="sd-button-secondary h-8"
              >
                取消修改
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-4">
            <h3 className="text-sm font-semibold text-ink">{form.title}</h3>
            <p className="mt-1.5 whitespace-pre-wrap text-[11px] leading-6 text-ink-secondary">
              {form.description}
            </p>
            <dl className="mt-4 grid gap-2.5 rounded-control border border-line bg-subtle px-3 py-3 text-[10px] sm:grid-cols-2">
              <div>
                <dt className="text-ink-tertiary">优先级理由</dt>
                <dd className="mt-0.5 leading-5 text-ink-secondary">{form.priority_reason}</dd>
              </div>
              <div>
                <dt className="text-ink-tertiary">影响系统 / 环境</dt>
                <dd className="mt-0.5 leading-5 text-ink-secondary">
                  {form.affected_system || "未填写"} · {form.environment || "未填写"}
                </dd>
              </div>
              <div>
                <dt className="text-ink-tertiary">报错信息</dt>
                <dd className="mt-0.5 break-words leading-5 text-ink-secondary">
                  {form.error_message || "未填写"}
                </dd>
              </div>
              <div>
                <dt className="text-ink-tertiary">建议处理人</dt>
                <dd className="mt-0.5 leading-5 text-ink-secondary">
                  {draft.suggested_assignee_name || "待推荐"}
                </dd>
              </div>
            </dl>
            {draft.suggested_assignee_reason && (
              <p className="mt-2 text-[10px] leading-5 text-ink-tertiary">
                推荐理由：{draft.suggested_assignee_reason}
              </p>
            )}
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
              {canManage ? (
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="sd-button-secondary h-8"
                >
                  修改字段
                </button>
              ) : (
                <span className="text-[10px] text-ink-tertiary">
                  支持人员确认后创建工单；你也可以继续在对话中补充信息。
                </span>
              )}
              {canManage && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void confirmDraft()}
                  className="sd-button-primary h-8"
                >
                  {busy ? "正在创建…" : "确认创建工单"}
                </button>
              )}
            </div>
          </div>
        )}

        {localError && (
          <p className="mt-3 rounded-control border border-danger bg-danger-soft px-3 py-2 text-[10px] text-danger">
            {localError}
          </p>
        )}
        {draft.status === "DRAFT" && (
          <p className="mt-3 text-[9px] text-ink-tertiary">
            工单号 {draft.id} · 草稿版本 {draft.version}
          </p>
        )}
      </div>
    </div>
  );
}
