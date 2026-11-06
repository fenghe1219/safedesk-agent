import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { AuditConsole } from "@/components/audit-console";
import { can, requireMe } from "@/lib/page-guard";
import { getAuditEvents } from "@/lib/server-api";

export const metadata: Metadata = { title: "审计" };

export default async function AuditPage() {
  const me = await requireMe();
  if (!can(me, "audit:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看审计日志的权限。" />;
  }

  const data = await getAuditEvents(50);
  return <AuditConsole initialData={data} />;
}
