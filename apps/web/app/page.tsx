import { redirect } from "next/navigation";

import { getMe } from "@/lib/server-api";

export default async function HomePage() {
  const me = await getMe();
  redirect(me?.default_path ?? "/login");
}
