import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AccessDenied } from "@/components/access-denied";
import { CaseProgress } from "@/components/case-progress";
import { Icon } from "@/components/icons";
import { StatusBadge } from "@/components/status-badge";
import { getCase, getCaseTimeline } from "@/lib/server-api";
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

  const [caseData, timeline] = await Promise.all([getCase(id), getCaseTimeline(id)]);
  if (!caseData) notFound();

  return (
    <div className="mx-auto max-w-[1440px]">
      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-tertiary">
          <Link href={me.default_path} className="transition-colors hover:text-brand">工作台</Link>
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
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="sd-chip">M0 · Case 骨架</span>
            <button type="button" disabled className="sd-button-secondary" title="M1 开放">
              <Icon name="plus" size={14} />
              补充说明
            </button>
          </div>
        </div>

        <div className="mt-5 rounded-card border border-line bg-surface px-5 py-4 shadow-card">
          <CaseProgress phase={caseData.phase} />
        </div>
      </header>

      <div className="grid items-start gap-4 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_290px]">
        <section className="sd-card flex h-[620px] flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <h2 className="text-xs font-semibold text-ink">对话</h2>
            <span className="text-[9px] text-ink-tertiary">M1 接入流式回答</span>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            <div className="ml-7 rounded-card rounded-tr-[3px] bg-brand-soft px-3 py-2.5 text-xs leading-6 text-ink">
              {caseData.title}
            </div>
            <div className="flex items-start gap-2">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand text-[9px] font-semibold text-white">S</span>
              <div className="rounded-card rounded-tl-[3px] border border-line bg-subtle px-3 py-2.5 text-[11px] leading-5 text-ink-secondary">
                Case 已创建并写入审计时间线。M1 将在这里展示理解、查证、回答或转工单。
              </div>
            </div>
          </div>

          <div className="border-t border-line p-3">
            <textarea
              disabled
              className="min-h-16 w-full resize-none rounded-control border border-line bg-subtle px-3 py-2 text-xs leading-5 text-ink-tertiary outline-none"
              placeholder="M1 开放补充说明与追问"
            />
            <div className="mt-2 flex items-center justify-between text-[9px] text-ink-tertiary">
              <span>Enter 发送 · Shift + Enter 换行</span>
              <button type="button" disabled className="rounded-control bg-brand px-2.5 py-1 text-[10px] font-medium text-white opacity-40">发送</button>
            </div>
          </div>
        </section>

        <section className="min-h-[620px] space-y-4">
          <div className="sd-card overflow-hidden">
            <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="grid h-7 w-7 place-items-center rounded-control bg-brand-soft text-brand">
                    <Icon name="spark" size={15} />
                  </span>
                  <h2 className="text-sm font-semibold text-ink">当前主导卡</h2>
                </div>
                <p className="mt-2 text-[11px] leading-5 text-ink-secondary">由当前 Case 阶段决定主内容，避免对话区承担所有信息。</p>
              </div>
              <span className="sd-chip">等待 Agent</span>
            </div>

            <div className="px-5 py-8">
              <div className="mx-auto max-w-lg text-center">
                <span className="mx-auto grid h-11 w-11 place-items-center rounded-overlay border border-line bg-subtle text-ink-tertiary">
                  <Icon name="branch" size={20} />
                </span>
                <h3 className="mt-4 text-sm font-semibold text-ink">业务流程尚未接入</h3>
                <p className="mt-2 text-[11px] leading-6 text-ink-secondary">
                  M1 将在这里依次呈现问题理解、检索依据、回答草稿或工单建议，并保留人工接管入口。
                </p>
              </div>

              <div className="mt-7 grid gap-3 sm:grid-cols-3">
                {[
                  { icon: "search" as const, title: "检索依据", detail: "0 条引用" },
                  { icon: "ticket" as const, title: "方案 / 工单", detail: "尚未生成" },
                  { icon: "shield" as const, title: "授权动作", detail: "尚未提议" }
                ].map((item) => (
                  <div key={item.title} className="rounded-card border border-line bg-subtle px-3 py-3">
                    <div className="flex items-center justify-between">
                      <Icon name={item.icon} size={14} className="text-ink-tertiary" />
                      <span className="text-[9px] text-ink-tertiary">待接入</span>
                    </div>
                    <p className="mt-3 text-[11px] font-medium text-ink">{item.title}</p>
                    <p className="mt-0.5 text-[9px] text-ink-tertiary">{item.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="sd-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold text-ink">关联对象</h2>
              <span className="text-[9px] text-ink-tertiary">Ticket · Action · Approval</span>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {["Ticket", "Action", "Approval"].map((item) => (
                <div key={item} className="rounded-control border border-dashed border-line-strong px-3 py-2.5 text-[10px] text-ink-tertiary">
                  {item} <span className="float-right">—</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className="space-y-4 lg:col-span-2 xl:col-span-1">
          <div className="sd-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold text-ink">Case 状态</h2>
              <Icon name="clock" size={14} className="text-ink-tertiary" />
            </div>
            <dl className="mt-3 space-y-2.5 text-[10px]">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-tertiary">精确状态</dt>
                <dd className="font-medium text-ink">{caseData.status_label}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-tertiary">当前阶段</dt>
                <dd className="font-medium text-ink">{PHASE_LABELS[caseData.phase] ?? caseData.phase}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-tertiary">当前节点</dt>
                <dd className="font-mono text-ink">{caseData.current_node}</dd>
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
            <ol className="max-h-[390px] overflow-y-auto px-4 py-4">
              {timeline.length === 0 ? (
                <li className="py-5 text-center text-[10px] text-ink-tertiary">暂无事件</li>
              ) : (
                timeline.map((event, index) => (
                  <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
                    {index < timeline.length - 1 && (
                      <span className="absolute left-[5px] top-3 h-[calc(100%-4px)] w-px bg-line" aria-hidden="true" />
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
        </aside>
      </div>
    </div>
  );
}
