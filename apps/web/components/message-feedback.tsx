"use client";

import { useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type { Feedback } from "@/lib/types";
import { cn } from "@/lib/utils";

const REASONS = [
  { value: "inaccurate", label: "不准确" },
  { value: "no_citation", label: "无引用" },
  { value: "outdated", label: "内容过时" },
  { value: "missing_steps", label: "步骤缺失" },
  { value: "other", label: "其他" }
];

export function MessageFeedback({
  messageId,
  csrfToken
}: {
  messageId: string;
  csrfToken: string;
}) {
  const [mode, setMode] = useState<"helpful" | "unhelpful" | null>(null);
  const [reason, setReason] = useState("inaccurate");
  const [comment, setComment] = useState("");
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(rating: "helpful" | "unhelpful", selectedReason?: string) {
    setPending(true);
    setError(null);
    try {
      await clientRequest<Feedback>(`/api/messages/${encodeURIComponent(messageId)}/feedback`, {
        method: "POST",
        csrfToken,
        body: JSON.stringify({
          rating,
          reason: rating === "unhelpful" ? selectedReason ?? reason : null,
          comment: rating === "unhelpful" ? comment.trim() : ""
        })
      });
      setDone(true);
      setMode(null);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "反馈提交失败");
    } finally {
      setPending(false);
    }
  }

  if (done) {
    return <p className="mt-1.5 text-[9px] text-success">已记录反馈，不会直接修改知识库或模型。</p>;
  }

  return (
    <div className="mt-1.5">
      <div className="flex flex-wrap items-center gap-1.5 text-[9px] text-ink-tertiary">
        <span>这条回答有帮助吗？</span>
        <button
          type="button"
          onClick={() => {
            setMode("helpful");
            void submit("helpful");
          }}
          disabled={pending}
          className="rounded-full border border-line px-2 py-0.5 hover:border-success hover:text-success"
        >
          有帮助
        </button>
        <button
          type="button"
          onClick={() => setMode(mode === "unhelpful" ? null : "unhelpful")}
          disabled={pending}
          className={cn(
            "rounded-full border px-2 py-0.5",
            mode === "unhelpful"
              ? "border-warning bg-warning-soft text-warning"
              : "border-line hover:border-warning hover:text-warning"
          )}
        >
          没帮助
        </button>
      </div>
      {mode === "unhelpful" && (
        <div className="mt-1.5 space-y-1.5 rounded-control border border-line bg-surface p-2">
          <select
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            className="sd-input h-7 text-[10px]"
          >
            {REASONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <input
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            maxLength={1000}
            className="sd-input h-7 text-[10px]"
            placeholder="可选：具体问题"
          />
          <button
            type="button"
            onClick={() => void submit("unhelpful", reason)}
            disabled={pending}
            className="sd-button-secondary h-7 w-full text-[10px]"
          >
            {pending ? "提交中…" : "提交负反馈"}
          </button>
        </div>
      )}
      {error && <p className="mt-1 text-[9px] text-danger">{error}</p>}
    </div>
  );
}
