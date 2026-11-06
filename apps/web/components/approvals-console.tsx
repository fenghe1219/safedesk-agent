"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type {
  ActionDecisionResponse,
  ApprovalDetail,
  ApprovalListItem,
  ApprovalStatus
} from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";
import { StatusBadge } from "./status-badge";

type QueueFilter = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED" | "ALL";
type DecisionMode = "approve" | "reject";

const FILTERS: Array<{ key: QueueFilter; label: string }> = [
  { key: "PENDING", label: "待审批" },
  { key: "APPROVED", label: "已批准" },
  { key: "REJECTED", label: "已拒绝" },
  { key: "EXPIRED", label: "已过期" },
  { key: "ALL", label: "全部" }
];

function riskTone(risk: string): string {
  if (risk === "HIGH") return "border-danger/30 bg-danger-soft text-danger";
  if (risk === "MEDIUM") return "border-warning/30 bg-warning-soft text-warning";
  return "border-success/30 bg-success-soft text-success";
}

function argumentValue(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function ApprovalsConsole({
  initialItems,
  csrfToken,
  currentUserId,
  initialSelectedId
}: {
  initialItems: ApprovalListItem[];
  csrfToken: string;
  currentUserId: string;
  initialSelectedId?: string;
}) {
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [filter, setFilter] = useState<QueueFilter>(
    initialItems.some((item) => item.status === "PENDING") ? "PENDING" : "ALL"
  );
  const [selectedId, setSelectedId] = useState<string | null>(
    initialSelectedId ?? initialItems[0]?.id ?? null
  );
  const [detail, setDetail] = useState<ApprovalDetail | null>(null);
  const [loading, setLoading] = useState(Boolean(selectedId));
  const [mode, setMode] = useState<DecisionMode | null>(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const visibleItems = useMemo(
    () => (filter === "ALL" ? items : items.filter((item) => item.status === filter)),
    [filter, items]
  );
  const pendingCount = items.filter((item) => item.status === "PENDING").length;

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    clientRequest<ApprovalDetail>(`/api/approvals/${encodeURIComponent(selectedId)}`)
      .then((value) => {
        if (active) setDetail(value);
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof ApiRequestError ? err.message : "加载审批详情失败");
          setDetail(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  function selectItem(id: string) {
    setSelectedId(id);
    setMode(null);
    setReason("");
    setConfirmed(false);
    setNotice(null);
    setError(null);
  }

  async function refreshDetail(id: string) {
    const value = await clientRequest<ApprovalDetail>(
      `/api/approvals/${encodeURIComponent(id)}`
    );
    setDetail(value);
  }

  async function submitDecision() {
    if (!detail || !mode || submitting) return;
    const decisionReason = reason.trim();
    if (mode === "reject" && !decisionReason) {
      setError("拒绝时必须填写原因");
      return;
    }
    if (mode === "approve" && !confirmed) {
      setError("请先确认已核对参数哈希和影响范围");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const endpoint =
        mode === "approve"
          ? `/api/approvals/${encodeURIComponent(detail.approval.id)}/approve`
          : `/api/approvals/${encodeURIComponent(detail.approval.id)}/reject`;
      const body =
        mode === "approve"
          ? {
              expected_args_hash: detail.action.args_hash,
              approval_version: detail.approval.version,
              reason: decisionReason || null
            }
          : {
              approval_version: detail.approval.version,
              reason: decisionReason
            };
      const result = await clientRequest<ActionDecisionResponse>(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        csrfToken
      });
      setNotice(result.message);
      setMode(null);
      setReason("");
      setConfirmed(false);
      setItems((current) =>
        current.map((item) =>
          item.id === result.approval.id
            ? {
                ...item,
                status: result.approval.status,
                status_label: result.approval.status_label,
                decided_at: result.approval.decided_at,
                can_decide: false
              }
            : item
        )
      );
      await refreshDetail(detail.approval.id);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "提交审批决定失败");
    } finally {
      setSubmitting(false);
    }
  }

  const canDecide = Boolean(detail?.permissions.can_decide) && detail?.action.requested_by_id !== currentUserId;

  return (
    <div className="grid items-start gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
      <section className="sd-card overflow-hidden">
        <div className="border-b border-line px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="sd-eyebrow">Approval queue</p>
              <h2 className="mt-1 text-sm font-semibold text-ink">审批队列</h2>
            </div>
            <span className="rounded-full border border-warning/30 bg-warning-soft px-2.5 py-1 text-[10px] font-medium text-warning">
              {pendingCount} 待处理
            </span>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {FILTERS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setFilter(item.key)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-[10px] font-medium transition-colors",
                  filter === item.key
                    ? "border-brand bg-brand-soft text-brand"
                    : "border-line bg-surface text-ink-tertiary hover:border-line-strong hover:text-ink-secondary"
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="max-h-[720px] overflow-y-auto">
          {visibleItems.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <span className="mx-auto grid h-10 w-10 place-items-center rounded-overlay border border-line bg-subtle text-ink-tertiary">
                <Icon name="shield" size={18} />
              </span>
              <p className="mt-3 text-xs font-medium text-ink-secondary">当前筛选下没有审批</p>
              <p className="mt-1 text-[10px] leading-5 text-ink-tertiary">
                新的高风险动作会自动出现在这里，并按风险和剩余时间排序。
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {visibleItems.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => selectItem(item.id)}
                    className={cn(
                      "w-full px-4 py-3.5 text-left transition-colors",
                      selectedId === item.id ? "bg-brand-soft/70" : "hover:bg-subtle"
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-xs font-semibold text-ink">{item.case_title}</p>
                        <p className="mt-1 text-[10px] text-ink-tertiary">
                          {item.requester_name} · {item.tool_label}
                        </p>
                      </div>
                      <span
                        className={cn(
                          "shrink-0 rounded-full border px-2 py-0.5 text-[9px] font-semibold",
                          riskTone(item.risk_level)
                        )}
                      >
                        {item.risk_label}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <StatusBadge status={item.status} label={item.status_label} />
                      <span className="text-[9px] text-ink-tertiary">
                        至 {formatDateTime(item.expires_at)}
                      </span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="sd-card min-h-[620px] overflow-hidden">
        {loading ? (
          <div className="grid min-h-[620px] place-items-center text-xs text-ink-tertiary">
            正在加载审批材料…
          </div>
        ) : !detail ? (
          <div className="grid min-h-[620px] place-items-center px-8 text-center">
            <div>
              <span className="mx-auto grid h-12 w-12 place-items-center rounded-overlay border border-line bg-subtle text-ink-tertiary">
                <Icon name="document" size={20} />
              </span>
              <h2 className="mt-4 text-sm font-semibold text-ink">选择一条审批查看材料</h2>
              <p className="mt-2 text-[11px] leading-6 text-ink-secondary">
                批准前请同时核对影响对象、风险、固定参数、证据、验证方式和回滚方案。
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="border-b border-line px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={detail.approval.status} label={detail.approval.status_label} />
                    <span
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-[10px] font-medium",
                        riskTone(detail.action.risk_level)
                      )}
                    >
                      {detail.action.risk_label}
                    </span>
                    <span className="sd-chip">{detail.action.tool_type}</span>
                  </div>
                  <h2 className="mt-2 text-lg font-semibold text-ink">{detail.case.title}</h2>
                  <p className="mt-1 text-[11px] text-ink-tertiary">
                    {detail.action.tool_label} · 申请人 {detail.action.requested_by_name} · 提交于{' '}
                    {formatDateTime(detail.approval.requested_at)}
                  </p>
                </div>
                <Link
                  href={`/cases/${encodeURIComponent(detail.case.id)}`}
                  className="sd-button-secondary h-8"
                >
                  打开 Case
                  <Icon name="arrow-right" size={13} />
                </Link>
              </div>
            </div>

            <div className="space-y-5 px-5 py-5">
              {notice && (
                <p className="rounded-control border border-success/30 bg-success-soft px-3 py-2 text-[11px] text-success">
                  {notice}
                </p>
              )}
              {error && (
                <p className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-[11px] text-danger">
                  {error}
                </p>
              )}

              <div className="grid gap-3 sm:grid-cols-3">
                <Fact label="申请人" value={detail.action.requested_by_name} />
                <Fact label="有效期至" value={formatDateTime(detail.approval.expires_at)} />
                <Fact label="审批版本" value={`v${detail.approval.version}`} />
              </div>

              <section>
                <SectionTitle icon="spark" title="动作理由与影响" />
                <p className="mt-2 text-[11px] leading-6 text-ink-secondary">{detail.action.rationale}</p>
                <p className="mt-2 rounded-control border border-warning/30 bg-warning-soft px-3 py-2 text-[11px] leading-5 text-warning">
                  影响范围：{detail.action.impact}
                </p>
              </section>

              <section>
                <SectionTitle icon="document" title="固定参数" />
                <dl className="mt-2 overflow-hidden rounded-control border border-line">
                  {Object.entries(detail.action.args).map(([key, value], index) => (
                    <div
                      key={key}
                      className={cn(
                        "grid grid-cols-[130px_minmax(0,1fr)] gap-3 px-3 py-2 text-[10px]",
                        index > 0 && "border-t border-line"
                      )}
                    >
                      <dt className="font-medium text-ink-tertiary">{key}</dt>
                      <dd className="break-all font-mono text-ink-secondary">{argumentValue(value)}</dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-2 break-all font-mono text-[9px] text-ink-tertiary">
                  {detail.action.args_hash}
                </p>
              </section>

              <div className="grid gap-3 sm:grid-cols-2">
                <section className="rounded-control border border-line bg-subtle px-3 py-3">
                  <SectionTitle icon="check" title="验证方式" />
                  <p className="mt-2 text-[10px] leading-5 text-ink-secondary">
                    {detail.action.verification_plan}
                  </p>
                </section>
                <section className="rounded-control border border-line bg-subtle px-3 py-3">
                  <SectionTitle icon="shield" title="回滚方式" />
                  <p className="mt-2 text-[10px] leading-5 text-ink-secondary">
                    {detail.action.rollback_plan}
                  </p>
                </section>
              </div>

              <section>
                <SectionTitle icon="audit" title="证据" />
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {detail.action.evidence_ids.map((item) => (
                    <span key={item} className="rounded-full border border-line bg-surface px-2 py-1 font-mono text-[9px] text-ink-tertiary">
                      {item}
                    </span>
                  ))}
                </div>
              </section>

              {detail.execution && (
                <section className="rounded-control border border-line px-3 py-3">
                  <SectionTitle icon="branch" title="执行结果" />
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <StatusBadge status={detail.execution.status} label={detail.execution.status} />
                    <span className="text-[10px] text-ink-tertiary">
                      {formatDateTime(detail.execution.started_at)}
                    </span>
                  </div>
                  <p className="mt-2 text-[10px] leading-5 text-ink-secondary">
                    {detail.execution.result_summary || detail.execution.error_message || "暂无执行摘要"}
                  </p>
                </section>
              )}

              {detail.blockers.length > 0 && detail.approval.status === "PENDING" && (
                <section className="rounded-control border border-danger/30 bg-danger-soft px-3 py-3">
                  <p className="text-[10px] font-semibold text-danger">当前不可批准</p>
                  <ul className="mt-1.5 space-y-1 text-[10px] leading-5 text-danger">
                    {detail.blockers.map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                </section>
              )}

              {detail.approval.status === "PENDING" && (
                <section className="rounded-control border border-line bg-surface p-4">
                  {!canDecide ? (
                    <p className="text-[11px] leading-6 text-ink-secondary">
                      当前角色可以查看材料，但没有该动作的批准权限。申请人和无审批范围的角色不能自行批准。
                    </p>
                  ) : mode === null ? (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold text-ink">审批决定</p>
                        <p className="mt-1 text-[10px] text-ink-tertiary">
                          批准后会立即调用一次写工具，并执行只读复核。
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button type="button" onClick={() => setMode("reject")} className="sd-button-secondary h-8">
                          拒绝
                        </button>
                        <button type="button" onClick={() => setMode("approve")} className="sd-button-primary h-8">
                          批准执行
                          <Icon name="check" size={13} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <p className="text-xs font-semibold text-ink">
                        {mode === "approve" ? "二次确认：批准并执行" : "二次确认：拒绝动作"}
                      </p>
                      <p className="mt-1 text-[10px] leading-5 text-ink-secondary">
                        {mode === "approve"
                          ? `${detail.action.tool_label} 只会影响 ${detail.action.requested_by_name}，执行后会自动复核。`
                          : "拒绝原因会写入审计时间线，工具不会执行。"}
                      </p>
                      <textarea
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                        maxLength={1000}
                        rows={3}
                        className="sd-textarea mt-3 text-xs"
                        placeholder={mode === "reject" ? "必填：说明拒绝原因" : "可选：审批备注"}
                      />
                      {mode === "approve" && (
                        <label className="mt-3 flex items-start gap-2 text-[10px] leading-5 text-ink-secondary">
                          <input
                            type="checkbox"
                            checked={confirmed}
                            onChange={(event) => setConfirmed(event.target.checked)}
                            className="mt-0.5"
                          />
                          我已核对固定参数哈希、影响对象、验证方式和回滚方案。
                        </label>
                      )}
                      <div className="mt-3 flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setMode(null);
                            setError(null);
                            setReason("");
                            setConfirmed(false);
                          }}
                          className="sd-button-secondary h-8"
                          disabled={submitting}
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          onClick={() => void submitDecision()}
                          disabled={submitting || (mode === "reject" && !reason.trim())}
                          className={cn("h-8", mode === "approve" ? "sd-button-primary" : "sd-button-secondary border-danger text-danger")}
                        >
                          {submitting ? "提交中…" : mode === "approve" ? "确认批准并执行" : "确认拒绝"}
                        </button>
                      </div>
                    </div>
                  )}
                </section>
              )}

              <section>
                <SectionTitle icon="clock" title="最近审计事件" />
                <ol className="mt-2 space-y-2">
                  {detail.timeline.slice(-8).map((event) => (
                    <li key={event.id} className="flex items-start justify-between gap-3 text-[10px]">
                      <span className="text-ink-secondary">{event.summary}</span>
                      <span className="shrink-0 text-ink-tertiary">{formatDateTime(event.created_at)}</span>
                    </li>
                  ))}
                </ol>
              </section>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
      <p className="text-[9px] text-ink-tertiary">{label}</p>
      <p className="mt-1 truncate text-[11px] font-medium text-ink">{value}</p>
    </div>
  );
}

function SectionTitle({ icon, title }: { icon: "spark" | "document" | "check" | "shield" | "audit" | "branch" | "clock"; title: string }) {
  return (
    <h3 className="flex items-center gap-1.5 text-[11px] font-semibold text-ink">
      <Icon name={icon} size={13} className="text-brand" />
      {title}
    </h3>
  );
}

export type { ApprovalStatus };
