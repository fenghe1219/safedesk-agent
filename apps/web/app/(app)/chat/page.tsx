import type { Metadata } from "next";
import Link from "next/link";

import { AccessDenied } from "@/components/access-denied";
import { CaseList } from "@/components/case-list";
import { ChatComposer } from "@/components/chat-composer";
import { Icon } from "@/components/icons";
import { getCases } from "@/lib/server-api";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "工作台" };

export default async function ChatPage() {
  const me = await requireMe();
  if (!can(me, "case:create")) {
    return <AccessDenied me={me} detail="当前角色没有创建问题的权限。你可以从导航进入授权范围内的只读模块。" />;
  }

  const cases = can(me, "case:read") ? await getCases() : { items: [], next_cursor: null };
  const recentCases = cases.items.slice(0, 5);

  return (
    <div className="mx-auto max-w-[1160px]">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="sd-eyebrow">工作台</p>
          <h1 className="sd-page-title mt-1">你好，{me.user.name}</h1>
          <p className="mt-2 text-sm text-ink-secondary">从一个具体问题开始，SafeDesk 会把它整理成可追溯的 Case。</p>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-ink-tertiary">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          M0 服务已连接
        </div>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <section className="sd-card overflow-hidden">
          <div className="border-b border-line px-5 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-ink">描述你遇到的问题</h2>
                <p className="mt-1 text-[11px] text-ink-secondary">M0 会先创建 Case 并记录审计事件；Agent 检索与回答在 M1 接入。</p>
              </div>
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-control bg-brand-soft text-brand">
                <Icon name="spark" size={16} />
              </span>
            </div>
          </div>
          <div className="p-5">
            <ChatComposer csrfToken={me.csrf_token} canCreate={can(me, "case:create")} />
          </div>
        </section>

        <section className="sd-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
            <div>
              <h2 className="text-sm font-semibold text-ink">最近 Case</h2>
              <p className="mt-0.5 text-[10px] text-ink-tertiary">按最近更新时间排序</p>
            </div>
            {cases.items.length > 0 && (
              <Link href="/tickets" className="text-[10px] font-medium text-brand hover:underline">
                查看全部
              </Link>
            )}
          </div>
          <CaseList cases={recentCases} />
        </section>
      </div>

      <section className="mt-5 grid gap-3 sm:grid-cols-3">
        {[
          { title: "有依据的回答", body: "引用由服务端基于检索结果组装，不让模型编造来源。" },
          { title: "可接管的流程", body: "员工、支持和审批人共享同一条 Case 状态与时间线。" },
          { title: "受控的执行", body: "高风险动作必须经过审批、幂等键与执行后验证。" }
        ].map((item, index) => (
          <div key={item.title} className="rounded-card border border-line bg-surface px-4 py-4">
            <span className="font-mono text-[10px] text-brand">0{index + 1}</span>
            <h3 className="mt-2 text-xs font-semibold text-ink">{item.title}</h3>
            <p className="mt-1 text-[10px] leading-5 text-ink-secondary">{item.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
