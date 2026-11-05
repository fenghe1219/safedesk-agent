"use client";

import { useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import { ROLE_OPTIONS } from "@/lib/demo";
import type { MeResponse, Role } from "@/lib/types";
import { Icon } from "./icons";

export function DemoSwitcher({
  currentRole,
  csrfToken,
  demoMode
}: {
  currentRole: Role;
  csrfToken: string;
  demoMode: boolean;
}) {
  const [role, setRole] = useState<Role>(currentRole);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!demoMode) return null;

  async function switchRole(nextRole: Role) {
    setRole(nextRole);
    setPending(true);
    setError(null);
    try {
      const me = await clientRequest<MeResponse>("/api/demo/switch-user", {
        method: "POST",
        body: JSON.stringify({ role: nextRole }),
        csrfToken
      });
      window.location.href = me.default_path;
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "切换失败");
      setRole(currentRole);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="relative hidden items-center gap-2 sm:flex">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-[3px] text-[10px] text-ink-secondary">
        <span className="h-1.5 w-1.5 rounded-full bg-success" />
        演示身份
      </span>
      <div className="relative">
        <select
          aria-label="切换演示身份"
          value={role}
          disabled={pending}
          onChange={(event) => void switchRole(event.target.value as Role)}
          className="h-7 appearance-none rounded-control border border-line bg-surface pl-2 pr-7 text-[11px] text-ink-secondary outline-none transition-colors hover:border-line-strong focus:border-brand disabled:opacity-50"
        >
          {ROLE_OPTIONS.map((option) => (
            <option key={option.role} value={option.role}>
              {option.label}
            </option>
          ))}
        </select>
        <Icon
          name="chevron-down"
          size={12}
          className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-ink-tertiary"
        />
      </div>
      {error && <span className="max-w-[112px] truncate text-[10px] text-danger" title={error}>{error}</span>}
    </div>
  );
}
