import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ModulePlaceholder } from "@/components/module-placeholder";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "审批" };

export default async function ApprovalsPage() {
  const me = await requireMe();
  if (!can(me, "approval:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看审批队列的权限。" />;
  }

  return (
    <ModulePlaceholder
      eyebrow="审批"
      title="审批队列"
      description={
        can(me, "approval:decide")
          ? "需要授权的动作会进入这里。批准前必须同时看到影响对象、风险、证据、参数、验证和回滚方式。"
          : "当前角色可以查看审批材料，但没有批准或拒绝权限。管理员的审批权限同样受工具和部门范围约束。"
      }
      icon="shield"
      emptyTitle="审批模块将在 M3 接入"
      emptyDescription="M3 将提供按风险和剩余时间排序的队列、材料抽屉、二次确认、拒绝原因与审批过期处理。"
      milestones={[
        "审批队列与详情抽屉",
        "批准前二次确认和拒绝原因",
        "过期、执行中与失败状态回流 Case"
      ]}
    />
  );
}
