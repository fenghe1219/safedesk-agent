import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ApprovalsConsole } from "@/components/approvals-console";
import { can, requireMe } from "@/lib/page-guard";
import { getApprovals } from "@/lib/server-api";

export const metadata: Metadata = { title: "审批" };

export default async function ApprovalsPage({
  searchParams
}: {
  searchParams: Promise<{ approval?: string }>;
}) {
  const me = await requireMe();
  if (!can(me, "approval:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看审批队列的权限。" />;
  }

  const [items, params] = await Promise.all([getApprovals(), searchParams]);
  const pending = items.filter((item) => item.status === "PENDING").length;
  const highRisk = items.filter(
    (item) => item.status === "PENDING" && item.risk_level === "HIGH"
  ).length;

  return (
    <div className="mx-auto max-w-[1440px]">
      <header className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="sd-eyebrow">Human in the loop</p>
          <h1 className="sd-page-title mt-1">审批与受控执行</h1>
          <p className="mt-2 max-w-3xl text-[11px] leading-6 text-ink-secondary">
            高风险写动作必须经过人工确认。批准前请核对影响对象、固定参数、证据、验证方式与回滚方案；拒绝原因会进入审计时间线。
          </p>
        </div>
        <div className="flex gap-2">
          <div className="rounded-control border border-warning/30 bg-warning-soft px-3 py-2 text-center">
            <p className="text-lg font-semibold leading-6 text-warning">{pending}</p>
            <p className="text-[9px] text-warning">待审批</p>
          </div>
          <div className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-center">
            <p className="text-lg font-semibold leading-6 text-danger">{highRisk}</p>
            <p className="text-[9px] text-danger">高风险</p>
          </div>
        </div>
      </header>

      <ApprovalsConsole
        initialItems={items}
        csrfToken={me.csrf_token}
        currentUserId={me.user.id}
        initialSelectedId={params.approval}
      />
    </div>
  );
}
