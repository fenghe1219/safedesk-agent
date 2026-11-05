import { redirect } from "next/navigation";

import { getMe } from "./server-api";
import type { MeResponse } from "./types";

export async function requireMe(): Promise<MeResponse> {
  const me = await getMe();
  if (!me) redirect("/login");
  return me;
}

export function can(me: MeResponse, permission: string): boolean {
  return Boolean(me.permissions[permission]);
}
