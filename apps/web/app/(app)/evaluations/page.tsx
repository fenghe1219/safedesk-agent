import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ModulePlaceholder } from "@/components/module-placeholder";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "评估" };

export default async function EvaluationsPage() {
  const me = await requireMe();
  if (!can(me, "eval:manage")) {
    return <AccessDenied me={me} detail="当前角色没有进入评估控制台的权限。" />;
  }

  return (
    <ModulePlaceholder
      eyebrow="评估"
      title="评估控制台"
      description="按数据集、Eval Run 和样本结果三层组织。指标必须同时显示样本量，不把未经校准的模型置信度当作结论。"
      icon="flask"
      emptyTitle="评估模块将在 M4 接入"
      emptyDescription="M4 将提供数据集管理、运行配置、版本对比、样本详情和人工判定，保留成本与延迟指标。"
      primaryHref="/knowledge"
      primaryLabel="查看知识库"
      milestones={[
        "数据集与 Eval Run 管理",
        "Prompt / 模型 / 检索配置对比",
        "样本详情、引用与人工判定"
      ]}
    />
  );
}
