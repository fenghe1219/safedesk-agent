import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ModulePlaceholder } from "@/components/module-placeholder";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "工单" };

export default async function TicketsPage() {
  const me = await requireMe();
  if (!can(me, "ticket:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看工单的权限。" />;
  }

  return (
    <ModulePlaceholder
      eyebrow="工单"
      title={can(me, "ticket:manage") ? "工单处理台" : "我的工单"}
      description="工单是 Case 的关联对象。服务端会按角色和资源归属过滤列表，员工只可查看本人授权范围内的工单。"
      icon="ticket"
      emptyTitle="工单模块将在 M2 接入"
      emptyDescription="M2 将提供状态、分类、优先级、处理人与时间范围筛选，并在工单详情中保留证据、对话摘要和时间线。"
      milestones={[
        "工单列表与本人只读过滤",
        "分派、优先级与非法状态流转保护",
        "工单详情和关联 Case 回溯"
      ]}
    />
  );
}
