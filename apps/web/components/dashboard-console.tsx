"use client";

import { useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type { DashboardDistributionItem, DashboardResponse } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function minutes(value: number): string {
  return value >= 60 ? `${(value / 60).toFixed(1)} 小时` : `${value.toFixed(1)} 分钟`;
}

export function DashboardConsole({ initialData }: { initialData: DashboardResponse }) {
  const [data, setData] = useState(initialData);
  const [range, setRange] = useState<"7d" | "30d">(
    initialData.range === "7d" ? "7d" : "30d"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function changeRange(next: "7d" | "30d") {
    if (next === range || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await clientRequest<DashboardResponse>(`/api/dashboard?range=${next}`);
      setData(response);
      setRange(next);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "看板加载失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1280px] space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="sd-eyebrow">运营</p>
          <h1 className="sd-page-title mt-1">服务台看板</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-secondary">
            全部指标来自业务表与审计事件。每个比率都附带样本量；统计口径在页面底部明确列出。
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(["7d", "30d"] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => void changeRange(item)}
              disabled={loading}
              className={cn(
                "h-8 rounded-control border px-3 text-[11px] font-medium",
                range === item
                  ? "border-brand bg-brand text-white"
                  : "border-line bg-surface text-ink-secondary hover:border-ink-tertiary"
              )}
            >
              {item === "7d" ? "最近 7 天" : "最近 30 天"}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <div className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-xs text-danger">
          {error}
        </div>
      )}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <Kpi title="Case 总量" value={String(data.cases_total)} note={`${data.range_label} · 全量`} />
        <Kpi
          title="知识解决率"
          value={pct(data.knowledge_resolution_rate)}
          note={`样本 ${data.sample_sizes.knowledge_resolution_rate ?? 0}`}
        />
        <Kpi
          title="转工单率"
          value={pct(data.ticket_rate)}
          note={`样本 ${data.sample_sizes.ticket_rate ?? 0}`}
        />
        <Kpi
          title="审批请求"
          value={String(data.approval_requests)}
          note={`拒绝 ${data.approval_rejected} · 失败 ${data.approval_failed}`}
        />
        <Kpi
          title="审批通过率"
          value={pct(data.approval_pass_rate)}
          note={`样本 ${data.sample_sizes.approval_pass_rate ?? 0}`}
        />
        <Kpi
          title="重复执行拦截"
          value={String(data.duplicate_execution_blocked)}
          note={`样本 ${data.sample_sizes.approval_requests ?? 0} 个审批`}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <DistributionCard
          title="工单分类分布"
          sample={data.sample_sizes.ticket_rate ?? 0}
          items={data.category_distribution}
        />
        <DistributionCard
          title="工单优先级分布"
          sample={data.sample_sizes.ticket_rate ?? 0}
          items={data.priority_distribution}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <div className="sd-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Icon name="shield" size={15} className="text-brand" />
              审批与处理效率
            </h2>
            <span className="sd-chip">{data.range_label}</span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Fact label="平均审批等待" value={minutes(data.avg_approval_wait_minutes)} note={`样本 ${data.sample_sizes.approval_pass_rate ?? 0}`} />
            <Fact label="审批过期率" value={pct(data.approval_expiry_rate)} note={`样本 ${data.sample_sizes.approval_expiry_rate ?? 0}`} />
            <Fact label="平均处理时长" value={minutes(data.avg_handling_minutes)} note={`样本 ${data.sample_sizes.avg_handling_minutes ?? 0}`} />
            <Fact label="人工修正率" value={pct(data.manual_correction_rate)} note={`样本 ${data.sample_sizes.manual_correction_rate ?? 0} 个工单`} />
          </div>
          <div className="mt-4 rounded-control border border-line bg-subtle px-3 py-2.5 text-[10px] leading-5 text-ink-secondary">
            审批失败数来自 Action 状态为 FAILED 的记录；重复执行拦截来自 `tool.duplicate_blocked` 审计事件。
          </div>
        </div>

        <div className="sd-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Icon name="clock" size={15} className="text-brand" />
              延迟与成本
            </h2>
            <span className="sd-chip">本地估算</span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Fact label="回答延迟" value={`${data.avg_answer_latency_ms.toFixed(1)} ms`} note={`样本 ${data.sample_sizes.avg_answer_latency_ms ?? 0}`} />
            <Fact label="检索延迟" value={`${data.avg_retrieval_latency_ms.toFixed(1)} ms`} note={`样本 ${data.sample_sizes.avg_retrieval_latency_ms ?? 0}`} />
            <Fact label="工具延迟" value={`${data.avg_tool_latency_ms.toFixed(1)} ms`} note={`样本 ${data.sample_sizes.avg_tool_latency_ms ?? 0}`} />
            <Fact label="平均 Token 成本" value={`$${data.avg_answer_cost_usd.toFixed(8)}`} note={`样本 ${data.sample_sizes.avg_answer_cost_usd ?? 0} · 规则基线估算`} />
          </div>
        </div>
      </section>

      <section className="sd-card p-5">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Icon name="flask" size={15} className="text-brand" />
            评估指标趋势
          </h2>
          <span className="sd-chip">{data.eval_trend.length} 个 Run</span>
        </div>
        {data.eval_trend.length === 0 ? (
          <p className="mt-6 text-center text-xs text-ink-tertiary">当前时间范围内还没有已完成的 Eval Run。</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead>
                <tr className="border-b border-line text-[10px] text-ink-tertiary">
                  <th className="pb-2 font-medium">Run</th>
                  <th className="pb-2 font-medium">数据集</th>
                  <th className="pb-2 font-medium">样本量</th>
                  <th className="pb-2 font-medium">关键指标</th>
                  <th className="pb-2 font-medium">通过率</th>
                  <th className="pb-2 font-medium">时间</th>
                </tr>
              </thead>
              <tbody>
                {data.eval_trend.map((point) => (
                  <tr key={point.run_id} className="border-b border-line/70 last:border-0">
                    <td className="max-w-[240px] truncate py-2.5 text-ink">{point.label}</td>
                    <td className="py-2.5 text-ink-secondary">{point.dataset_type}</td>
                    <td className="py-2.5 text-ink-secondary">{point.sample_size}</td>
                    <td className="py-2.5 text-ink">
                      {point.key_metric_label} {pct(point.key_metric_value)}
                    </td>
                    <td className="py-2.5 text-ink-secondary">{pct(point.pass_rate)}</td>
                    <td className="py-2.5 text-ink-tertiary">{formatDateTime(point.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <details className="sd-card p-5">
        <summary className="cursor-pointer text-xs font-semibold text-ink">统计口径与样本说明</summary>
        <dl className="mt-3 space-y-2">
          {Object.entries(data.methodology).map(([key, value]) => (
            <div key={key} className="grid gap-1 text-[10px] leading-5 sm:grid-cols-[160px_minmax(0,1fr)]">
              <dt className="font-mono text-ink-tertiary">{key}</dt>
              <dd className="text-ink-secondary">{value}</dd>
            </div>
          ))}
        </dl>
      </details>
    </div>
  );
}

function Kpi({ title, value, note }: { title: string; value: string; note: string }) {
  return (
    <div className="sd-card p-4">
      <p className="text-[10px] font-medium text-ink-tertiary">{title}</p>
      <p className="mt-1 text-2xl font-semibold tracking-[-0.02em] text-ink">{value}</p>
      <p className="mt-1 text-[9px] leading-4 text-ink-tertiary">{note}</p>
    </div>
  );
}

function Fact({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
      <p className="text-[9px] text-ink-tertiary">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{value}</p>
      <p className="mt-0.5 text-[9px] text-ink-tertiary">{note}</p>
    </div>
  );
}

function DistributionCard({
  title,
  sample,
  items
}: {
  title: string;
  sample: number;
  items: DashboardDistributionItem[];
}) {
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <div className="sd-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        <span className="text-[9px] text-ink-tertiary">样本 {sample}</span>
      </div>
      {items.length === 0 ? (
        <p className="mt-6 text-center text-xs text-ink-tertiary">当前范围没有工单数据。</p>
      ) : (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <div key={item.key}>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-ink-secondary">{item.label}</span>
                <span className="font-mono text-ink-tertiary">
                  {item.count} · {pct(item.rate)}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-subtle">
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: `${Math.max(4, (item.count / max) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
