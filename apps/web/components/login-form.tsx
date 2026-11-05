"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demo";
import type { MeResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Icon } from "./icons";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState(DEMO_ACCOUNTS[0].email);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const me = await clientRequest<MeResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      router.replace(me.default_path);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "登录失败，请稍后重试");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <label className="sd-label" htmlFor="email">
          邮箱
        </label>
        <div className="relative">
          <Icon name="user" size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
          <input
            id="email"
            className="sd-input pl-9"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label className="sd-label" htmlFor="password">
          密码
        </label>
        <div className="relative">
          <Icon name="lock" size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-tertiary" />
          <input
            id="password"
            className="sd-input pl-9"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>
      </div>

      {error && (
        <div className="rounded-control border border-danger-soft bg-danger-soft px-3 py-2 text-xs text-danger" role="alert">
          {error}
        </div>
      )}

      <button className="sd-button-primary h-10 w-full text-[13px]" type="submit" disabled={pending}>
        {pending ? "正在登录…" : "登录 SafeDesk"}
        <Icon name="arrow-right" size={15} />
      </button>

      <div className="border-t border-line pt-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-medium text-ink-secondary">演示账号</span>
          <span className="text-[10px] text-ink-tertiary">统一密码 {DEMO_PASSWORD}</span>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {DEMO_ACCOUNTS.map((account) => (
            <button
              key={account.email}
              type="button"
              onClick={() => {
                setEmail(account.email);
                setPassword(DEMO_PASSWORD);
                setError(null);
              }}
              className={cn(
                "rounded-control border px-2.5 py-2 text-left transition-colors",
                email === account.email
                  ? "border-brand-border bg-brand-soft"
                  : "border-line bg-surface hover:border-line-strong"
              )}
            >
              <span className="block text-[11px] font-medium text-ink">{account.label} · {account.name}</span>
              <span className="block truncate text-[10px] text-ink-tertiary">{account.email}</span>
            </button>
          ))}
        </div>
      </div>
    </form>
  );
}
