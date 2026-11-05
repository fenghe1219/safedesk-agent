"use client";

import { useState } from "react";

import { clientRequest } from "@/lib/api";
import { Icon } from "./icons";

export function LogoutButton({ csrfToken }: { csrfToken: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function logout() {
    setPending(true);
    setError(null);
    try {
      await clientRequest<void>("/api/auth/logout", {
        method: "POST",
        csrfToken
      });
      window.location.href = "/login";
    } catch {
      setError("退出失败，请重试");
    } finally {
      setPending(false);
    }
  }

  return (
    <button
      type="button"
      onClick={() => void logout()}
      disabled={pending}
      aria-label="退出登录"
      title={error ?? "退出登录"}
      className="grid h-8 w-8 place-items-center rounded-control text-ink-tertiary transition-colors hover:bg-subtle hover:text-ink disabled:opacity-50"
    >
      <Icon name="logout" size={16} />
      {error && <span className="sr-only" role="alert">{error}</span>}
    </button>
  );
}
