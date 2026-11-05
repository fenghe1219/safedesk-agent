import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ModulePlaceholder } from "@/components/module-placeholder";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "配置" };

export default async function SettingsPage() {
  const me = await requireMe();
  if (!can(me, "settings:manage")) {
    return <AccessDenied me={me} detail="当前角色没有管理系统配置的权限。" />;
  }

  return (
    <ModulePlaceholder
      eyebrow="管理"
      title="系统配置"
      description="工具连接器由代码固定，管理界面只能启停、配置风险等级和审批范围，不能任意新增可执行工具。"
      icon="settings"
      emptyTitle="配置模块将在 M4 接入"
      emptyDescription="后续将按用户与角色、分类与优先级、工具与策略、Prompt 版本和演示数据分组，并记录关键变更前后值。"
      milestones={[
        "用户、角色与演示数据重置",
        "工具启停、风险与审批范围",
        "Prompt 版本和变更审计"
      ]}
    />
  );
}
