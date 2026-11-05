import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ModulePlaceholder } from "@/components/module-placeholder";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "看板" };

export default async function DashboardPage() {
  const me = await requireMe();
  if (!can(me, "dashboard:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看运营看板的权限。" />;
  }

  return (
    <ModulePlaceholder
      eyebrow="运营"
      title="服务台看板"
      description="第一屏聚焦 Case 总量、知识解决率、转工单率、审批请求、拒绝和失败；所有数字都必须标注时间范围与样本量。"
      icon="chart"
      emptyTitle="看板将在 M2 接入真实指标"
      emptyDescription="M0 不展示模拟业务数字，避免把占位数据误当作运营结论。后续指标将直接来自业务数据库。"
      primaryHref={can(me, "case:create") ? "/chat" : "/audit"}
      primaryLabel={can(me, "case:create") ? "返回工作台" : "查看审计"}
      milestones={[
        "六类核心指标与时间范围",
        "分类、优先级和审批分布",
        "平均等待时间与失败原因"
      ]}
    />
  );
}
