import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { DashboardConsole } from "@/components/dashboard-console";
import { can, requireMe } from "@/lib/page-guard";
import { getDashboard } from "@/lib/server-api";

export const metadata: Metadata = { title: "看板" };

export default async function DashboardPage() {
  const me = await requireMe();
  if (!can(me, "dashboard:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看运营看板的权限。" />;
  }

  const data = await getDashboard("30d");
  if (!data) {
    return <AccessDenied me={me} detail="看板数据暂时不可用，请稍后刷新。" />;
  }
  return <DashboardConsole initialData={data} />;
}
