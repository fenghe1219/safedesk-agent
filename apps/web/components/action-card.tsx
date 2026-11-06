import Link from "next/link";

import type { CaseAction } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";
import { StatusBadge } from "./status-badge";

function tone(risk: string): string {
  if (risk === "HIGH") return "border-danger/30 bg-danger-soft text-danger";
  if (risk === "MEDIUM") return "border-warning/30 bg-warning-soft text-warning";
  return "border-success/30 bg-success-soft text-success";
}

function displayValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function ActionCard({
  action,
  canViewApprovals
}: {
  action: CaseAction;
  canViewApprovals: boolean;
}) {
  const approvalHref = `/approvals?approval=${encodeURIComponent(action.approval.id)}`;
  return (
    <div className="sd-card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="sd-eyebrow">Controlled action</span>
            <StatusBadge status={action.status} label={action.status_label} />
            <span className={cn("rounded-full border px-2.5 py-1 text-[10px] font-medium", tone(action.risk_level))}>
              {action.risk_label}
            </span>
          </div>
          <h2 className="mt-2 text-sm font-semibold text-ink">{action.tool_label}</h2>
          <p className="mt-1 text-[10px] text-ink-tertiary">
            审批 {action.approval.status_label} · 有效期至 {formatDateTime(action.approval.expires_at)}
          </p>
        </div>
        {canViewApprovals ? (
          <Link href={approvalHref} className="sd-button-secondary h-8">
            查看审批材料
            <Icon name="arrow-right" size={13} />
          </Link>
        ) : (
          <span className="sd-chip">审批前不会执行</span>
        )}
      </div>

      <div className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="space-y-3">
          <div>
            <p className="text-[10px] font-semibold text-ink">影响范围</p>
            <p className="mt-1 text-[11px] leading-5 text-ink-secondary">{action.impact}</p>
          </div>
          <div>
            <p className="text-[10px] font-semibold text-ink">固定参数</p>
            <dl className="mt-1.5 overflow-hidden rounded-control border border-line">
              {Object.entries(action.args).map(([key, value], index) => (
                <div
                  key={key}
                  className={cn(
                    "grid grid-cols-[110px_minmax(0,1fr)] gap-2 px-2.5 py-1.5 text-[10px]",
                    index > 0 && "border-t border-line"
                  )}
                >
                  <dt className="text-ink-tertiary">{key}</dt>
                  <dd className="break-all font-mono text-ink-secondary">{displayValue(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
            <p className="text-[9px] text-ink-tertiary">申请人</p>
            <p className="mt-1 text-[11px] font-medium text-ink">{action.requested_by_name}</p>
          </div>
          <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
            <p className="text-[9px] text-ink-tertiary">参数快照</p>
            <p className="mt-1 break-all font-mono text-[9px] leading-4 text-ink-secondary">
              {action.args_hash}
            </p>
          </div>
          <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
            <p className="text-[9px] text-ink-tertiary">验证方式</p>
            <p className="mt-1 text-[10px] leading-4 text-ink-secondary">{action.verification_plan}</p>
          </div>
        </div>
      </div>

      {action.execution && (
        <div className="border-t border-line bg-subtle/60 px-5 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={action.execution.status} label={action.execution.status} />
            <span className="text-[10px] text-ink-secondary">
              {action.execution.result_summary || action.execution.error_message || "已记录执行结果"}
            </span>
          </div>
        </div>
      )}

      {action.blockers.length > 0 && action.status === "AWAITING_APPROVAL" && (
        <div className="border-t border-warning/30 bg-warning-soft px-5 py-2.5 text-[10px] leading-5 text-warning">
          当前阻断：{action.blockers.join("；")}
        </div>
      )}
    </div>
  );
}
