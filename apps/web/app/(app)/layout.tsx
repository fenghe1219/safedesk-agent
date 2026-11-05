import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { requireMe } from "@/lib/page-guard";

export default async function AuthenticatedLayout({ children }: { children: ReactNode }) {
  const me = await requireMe();
  return <AppShell me={me}>{children}</AppShell>;
}
