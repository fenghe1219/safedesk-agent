import type { Metadata } from "next";

import { AccessDenied } from "@/components/access-denied";
import { SettingsConsole } from "@/components/settings-console";
import { can, requireMe } from "@/lib/page-guard";
import { getAdminSettings, getAdminTools } from "@/lib/server-api";

export const metadata: Metadata = { title: "配置" };

export default async function SettingsPage() {
  const me = await requireMe();
  if (!can(me, "settings:manage")) {
    return <AccessDenied me={me} detail="当前角色没有管理系统配置的权限。" />;
  }

  const [settings, tools] = await Promise.all([getAdminSettings(), getAdminTools()]);
  if (!settings) {
    return <AccessDenied me={me} detail="配置数据暂时不可用，请稍后刷新。" />;
  }
  return (
    <SettingsConsole
      initialSettings={settings}
      initialTools={tools}
      csrfToken={me.csrf_token}
      currentUserId={me.user.id}
    />
  );
}
