import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AccessDenied } from "@/components/access-denied";
import { CaseProgress } from "@/components/case-progress";
import { CaseWorkspace } from "@/components/case-workspace";
import { StatusBadge } from "@/components/status-badge";
import { getCase, getCaseMessages, getCaseTimeline, getTicketDraft } from "@/lib/server-api";
import { can, requireMe } from "@/lib/page-guard";
import { formatDateTime } from "@/lib/utils";

export const metadata: Metadata = { title: "Case 工作台" };

const PHASE_LABELS: Record<string, string> = {
  intake: "受理",
  retrieval: "查证",
  solution: "方案",
  approval: "审批与执行",
  done: "完成"
};

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const me = await requireMe();
  const { id } = await params;
  if (!can(me, "case:read")) {
    return <AccessDenied me={me} detail="当前角色没有读取 Case 的权限。" />;
  }

  const canViewTickets = can(me, "ticket:view");
  const [caseData, timeline, messages, ticketDraft] = await Promise.all([
    getCase(id),
    getCaseTimeline(id),
    getCaseMessages(id),
    canViewTickets ? getTicketDraft(id) : Promise.resolve(null)
  ]);
  if (!caseData) notFound();

  return (
    <div className="mx-auto max-w-[1440px]">
      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-tertiary">
          <Link href={me.default_path} className="transition-colors hover:text-brand">
            工作台
          </Link>
          <span aria-hidden="true">/</span>
          <span>Case</span>
          <span aria-hidden="true">/</span>
          <span className="max-w-40 truncate font-mono">{caseData.id}</span>
        </div>

        <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <StatusBadge status={caseData.status} label={caseData.status_label} />
              <span className="sd-chip">{PHASE_LABELS[caseData.phase] ?? caseData.phase}</span>
              <span className="text-[10px] text-ink-tertiary">节点 {caseData.current_node}</span>
            </div>
            <h1 className="mt-2.5 max-w-3xl text-[22px] font-semibold leading-8 tracking-[-0.02em] text-ink">
              {caseData.title}
            </h1>
            <p className="mt-2 text-[11px] text-ink-tertiary">
              创建于 {formatDateTime(caseData.created_at)} · 提交人 {caseData.requester_id}
              {caseData.intent ? ` · 意图 ${caseData.intent}` : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="sd-chip">M2 · 分诊与工单</span>
          </div>
        </div>

        <div className="mt-5 rounded-card border border-line bg-surface px-5 py-4 shadow-card">
          <CaseProgress phase={caseData.phase} />
        </div>
      </header>

      <CaseWorkspace
        caseData={caseData}
        initialMessages={messages.items}
        initialTimeline={timeline}
        initialTicketDraft={ticketDraft}
        csrfToken={me.csrf_token}
        userName={me.user.name}
        canSend={can(me, "case:read")}
        canAutoStart={me.user.id === caseData.requester_id}
        canManageTickets={can(me, "ticket:manage")}
      />
    </div>
  );
}
