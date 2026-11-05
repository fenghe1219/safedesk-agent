"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";
import { Icon } from "./icons";

const DEMO_PROMPTS = [
  "我的 VPN 一直连不上，提示证书无效。",
  "办公室打印机报错 0x0000011b，无法打印。",
  "账号被锁定了，今天上午还有一个重要会议。"
];

export function ChatComposer({
  csrfToken,
  canCreate
}: {
  csrfToken: string;
  canCreate: boolean;
}) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate) return;
    const title = text.trim().replace(/\s+/g, " ").slice(0, 80);
    if (!title) {
      setError("请先描述你遇到的问题");
      return;
    }

    setPending(true);
    setError(null);
    try {
      const created = await clientRequest<CaseDetail>("/api/cases", {
        method: "POST",
        body: JSON.stringify({ title }),
        csrfToken
      });
      router.push(`/cases/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "创建 Case 失败，请稍后重试");
    } finally {
      setPending(false);
    }
  }

  if (!canCreate) {
    return (
      <div className="rounded-card border border-line bg-subtle px-4 py-5 text-xs text-ink-secondary">
        当前角色没有创建 Case 的权限。请使用员工、支持专员、审批人或管理员演示账号体验工作台。
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="rounded-card border border-line-strong bg-surface p-3 transition-colors focus-within:border-brand focus-within:shadow-[0_0_0_3px_var(--sd-primary-soft)]">
        <textarea
          className="min-h-24 w-full resize-none border-0 bg-transparent p-1 text-sm leading-7 text-ink outline-none placeholder:text-ink-tertiary"
          placeholder="描述你遇到的 IT 或行政问题，例如：VPN 无法连接，提示证书无效…"
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setError(null);
          }}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.currentTarget.form?.requestSubmit();
            }
          }}
          maxLength={600}
        />
        <div className="flex items-center justify-between gap-3 border-t border-line pt-2.5">
          <span className="text-[10px] text-ink-tertiary">Ctrl / ⌘ + Enter 创建 · M1 接入 Agent</span>
          <button className="sd-button-primary" type="submit" disabled={pending}>
            {pending ? "正在创建…" : "创建 Case"}
            <Icon name="arrow-right" size={14} />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] text-ink-tertiary">试试：</span>
        {DEMO_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => {
              setText(prompt);
              setError(null);
            }}
            className="rounded-full border border-line bg-surface px-2.5 py-1 text-[10px] text-ink-secondary transition-colors hover:border-brand-border hover:bg-brand-soft hover:text-brand"
          >
            {prompt}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-control border border-danger bg-danger-soft px-3 py-2 text-xs text-danger" role="alert">
          {error}
        </div>
      )}
    </form>
  );
}
