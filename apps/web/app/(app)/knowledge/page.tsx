import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { KnowledgeConsole } from "@/components/knowledge-console";
import { getKnowledgeDocuments } from "@/lib/server-api";
import { can, requireMe } from "@/lib/page-guard";

export const metadata: Metadata = { title: "知识库" };

export default async function KnowledgePage() {
  const me = await requireMe();
  if (!can(me, "knowledge:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看知识库的权限。" />;
  }

  const documents = await getKnowledgeDocuments();
  return (
    <KnowledgeConsole
      initialDocuments={documents.items}
      csrfToken={me.csrf_token}
      canManage={can(me, "knowledge:manage")}
    />
  );
}
