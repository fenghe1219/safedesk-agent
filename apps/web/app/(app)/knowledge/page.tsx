import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { ModulePlaceholder } from "@/components/module-placeholder";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "知识库" };

export default async function KnowledgePage() {
  const me = await requireMe();
  if (!can(me, "knowledge:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看知识库的权限。" />;
  }

  return (
    <ModulePlaceholder
      eyebrow="知识"
      title="知识库"
      description="文档导入、解析、切分和索引重建都由服务端记录状态。检索采用 pgvector + pg_trgm，并保留中文分词适配层。"
      icon="book"
      emptyTitle="知识库模块将在 M2 接入"
      emptyDescription="M2 将提供文档状态、ACL、版本、切分预览和引用定位样例，便于核对每个回答依据了哪一段原文。"
      primaryHref={can(me, "case:create") ? "/chat" : "/evaluations"}
      primaryLabel={can(me, "case:create") ? "返回工作台" : "查看评估"}
      milestones={[
        "上传、解析与失败重试",
        "切分预览、ACL 和版本管理",
        "索引重建与检索测试"
      ]}
    />
  );
}
