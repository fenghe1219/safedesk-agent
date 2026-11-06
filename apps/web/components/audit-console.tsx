"use client";

import { useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type { AuditEvent, AuditEventListResponse } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";

export function AuditConsole({ initialData }: { initialData: AuditEventListResponse }) {
  const [data, setData] = useState(initialData);
  const [eventType, setEventType] = useState("");
  const [result, setResult] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function load(offset: number) {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(data.limit || 25)
    });
    if (eventType) params.set("event_type", eventType);
    if (result) params.set("result", result);
    if (query.trim()) params.set("q", query.trim());
    try {
      const response = await clientRequest<AuditEventListResponse>(`/api/audit/events?${params}`);
      setData(response);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "审计查询失败");
    } finally {
      setLoading(false);
    }
  }

  const page = Math.floor(data.offset / Math.max(data.limit, 1)) + 1;
  const pages = Math.max(1, Math.ceil(data.total / Math.max(data.limit, 1)));

  return (
    <div className="mx-auto max-w-[1280px] space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="sd-eyebrow">审计</p>
          <h1 className="sd-page-title mt-1">审计日志</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-secondary">
            只读查询业务事件。Payload 在服务端完成脱敏与截断，页面不提供修改或删除入口。
          </p>
        </div>
        <span className="sd-chip">
          <Icon name="lock" size={12} />
          只读 · {data.total} 条匹配
        </span>
      </header>

      <section className="sd-card p-4">
        <form
          className="grid gap-3 md:grid-cols-[minmax(0,1fr)_200px_140px_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            void load(0);
          }}
        >
          <label>
            <span className="sd-label">关键词</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="sd-input"
              placeholder="Case、用户、请求 ID 或 payload"
            />
          </label>
          <label>
            <span className="sd-label">事件类型</span>
            <select
              value={eventType}
              onChange={(event) => setEventType(event.target.value)}
              className="sd-input"
            >
              <option value="">全部事件</option>
              {data.event_types.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="sd-label">结果</span>
            <select
              value={result}
              onChange={(event) => setResult(event.target.value)}
              className="sd-input"
            >
              <option value="">全部</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
            </select>
          </label>
          <div className="flex items-end gap-2">
            <button type="submit" disabled={loading} className="sd-button-primary">
              <Icon name="search" size={13} />
              {loading ? "查询中…" : "查询"}
            </button>
            <button
              type="button"
              onClick={() => {
                setEventType("");
                setResult("");
                setQuery("");
                void load(0);
              }}
              className="sd-button-secondary"
            >
              清空
            </button>
          </div>
        </form>
      </section>

      {error && (
        <div className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-danger">
          {error}
        </div>
      )}

      <section className="sd-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-xs">
            <thead className="border-b border-line bg-subtle">
              <tr className="text-[10px] text-ink-tertiary">
                <th className="px-4 py-2.5 font-medium">时间</th>
                <th className="px-4 py-2.5 font-medium">事件</th>
                <th className="px-4 py-2.5 font-medium">角色</th>
                <th className="px-4 py-2.5 font-medium">结果</th>
                <th className="px-4 py-2.5 font-medium">Case</th>
                <th className="px-4 py-2.5 font-medium">Request ID</th>
                <th className="px-4 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-ink-tertiary">
                    没有匹配的审计事件。
                  </td>
                </tr>
              ) : (
                data.items.map((event) => (
                  <AuditRow
                    key={event.id}
                    event={event}
                    expanded={expanded === event.id}
                    onToggle={() => setExpanded(expanded === event.id ? null : event.id)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-line px-4 py-3 text-[10px] text-ink-tertiary">
          <span>
            第 {page} / {pages} 页 · 每页 {data.limit} 条
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={loading || data.offset === 0}
              onClick={() => void load(Math.max(0, data.offset - data.limit))}
              className="sd-button-secondary h-7"
            >
              上一页
            </button>
            <button
              type="button"
              disabled={loading || data.offset + data.limit >= data.total}
              onClick={() => void load(data.offset + data.limit)}
              className="sd-button-secondary h-7"
            >
              下一页
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function AuditRow({
  event,
  expanded,
  onToggle
}: {
  event: AuditEvent;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className="border-b border-line/70 align-top last:border-0">
        <td className="whitespace-nowrap px-4 py-3 text-[10px] text-ink-tertiary">
          {formatDateTime(event.created_at)}
        </td>
        <td className="px-4 py-3">
          <p className="font-medium text-ink">{event.summary}</p>
          <p className="mt-0.5 font-mono text-[9px] text-ink-tertiary">{event.event_type}</p>
        </td>
        <td className="px-4 py-3 text-ink-secondary">
          {event.actor_name || event.actor_id || "系统"}
          {event.actor_role && <span className="block text-[9px] text-ink-tertiary">{event.actor_role}</span>}
        </td>
        <td className="px-4 py-3">
          <span
            className={cn(
              "inline-flex rounded-full px-2 py-0.5 text-[9px] font-medium",
              event.result === "success"
                ? "bg-success-soft text-success"
                : "bg-danger-soft text-danger"
            )}
          >
            {event.result}
          </span>
        </td>
        <td className="px-4 py-3 font-mono text-[9px] text-ink-tertiary">
          {event.case_id ? event.case_id.slice(0, 12) : "—"}
        </td>
        <td className="px-4 py-3 font-mono text-[9px] text-ink-tertiary">{event.request_id}</td>
        <td className="px-4 py-3 text-right">
          <button type="button" onClick={onToggle} className="sd-button-ghost h-7 px-2 text-[10px]">
            {expanded ? "收起" : "Payload"}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-line bg-subtle/60 last:border-0">
          <td colSpan={7} className="px-4 py-3">
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-control border border-line bg-surface p-3 font-mono text-[9px] leading-5 text-ink-secondary">
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  );
}
