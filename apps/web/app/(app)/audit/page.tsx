import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ModulePlaceholder } from "@/components/module-placeholder";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "审计" };

export default async function AuditPage() {
  const me = await requireMe();
  if (!can(me, "audit:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看审计日志的权限。" />;
  }

  return (
    <ModulePlaceholder
      eyebrow="审计"
      title="审计日志"
      description="审计记录保持只读，并与业务状态尽量在同一事务内写入。M0 的登录、退出、身份切换和 Case 创建事件已经落库。"
      icon="audit"
      emptyTitle="审计查询将在 M4 接入"
      emptyDescription="后续将提供按 Case、用户、事件类型、工具和时间范围筛选，并从事件还原完整的 Case 时间线。"
      primaryHref="/dashboard"
      primaryLabel="查看看板"
      milestones={[
        "只读事件查询与脱敏 payload",
        "Case、审批和工具执行回溯",
        "事件关联跳转与不可变约束"
      ]}
    />
  );
}
