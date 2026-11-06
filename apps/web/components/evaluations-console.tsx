"use client";

import { useEffect, useMemo, useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type {
  EvalCompareResponse,
  EvalDataset,
  EvalResult,
  EvalResultListResponse,
  EvalRun,
  PromptVersion
} from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";

const TYPE_LABELS: Record<string, string> = {
  knowledge: "知识问答",
  triage: "工单分诊",
  security: "安全场景"
};

const METRICS_BY_TYPE: Record<string, Array<[string, string]>> = {
  knowledge: [
    ["citation_coverage", "引用覆盖率"],
    ["citation_consistency", "引用一致率"],
    ["refusal_accuracy", "拒答准确率"],
    ["answer_accuracy", "答案正确率"]
  ],
  triage: [
    ["category_accuracy", "分类准确率"],
    ["priority_accuracy", "优先级准确率"],
    ["field_completeness", "字段完整率"],
    ["assignee_top1_accuracy", "处理人 Top-1"]
  ],
  security: [
    ["unauthorized_refusal_rate", "越权拒答率"],
    ["approval_bypass_rate", "审批绕过率"],
    ["duplicate_execution_rate", "重复执行率"],
    ["injection_success_rate", "注入成功率"]
  ]
};

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}

function metricNumber(run: EvalRun | undefined, key: string): number | null {
  const value = run?.metrics?.[key];
  return typeof value === "number" ? value : null;
}

export function EvaluationsConsole({
  initialDatasets,
  initialRuns,
  prompts,
  csrfToken
}: {
  initialDatasets: EvalDataset[];
  initialRuns: EvalRun[];
  prompts: PromptVersion[];
  csrfToken: string;
}) {
  const [datasets, setDatasets] = useState(initialDatasets);
  const [runs, setRuns] = useState(initialRuns);
  const [selectedDatasetId, setSelectedDatasetId] = useState(initialDatasets[0]?.id ?? "");
  const [promptVersion, setPromptVersion] = useState(
    prompts.find((item) => item.is_active)?.version ?? prompts[0]?.version ?? "m1-knowledge-v1"
  );
  const [retrievalLimit, setRetrievalLimit] = useState(5);
  const [runLabel, setRunLabel] = useState("");
  const [selectedRunId, setSelectedRunId] = useState(initialRuns[0]?.id ?? "");
  const [results, setResults] = useState<EvalResultListResponse | null>(null);
  const [verdict, setVerdict] = useState("all");
  const [resultsLoading, setResultsLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [baselineId, setBaselineId] = useState(initialRuns[1]?.id ?? initialRuns[0]?.id ?? "");
  const [candidateId, setCandidateId] = useState(initialRuns[0]?.id ?? "");
  const [comparison, setComparison] = useState<EvalCompareResponse | null>(null);
  const [comparing, setComparing] = useState(false);
  const [importName, setImportName] = useState("");
  const [importType, setImportType] = useState("knowledge");
  const [importVersion, setImportVersion] = useState("v1");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);

  const selectedRun = useMemo(
    () => runs.find((item) => item.id === selectedRunId),
    [runs, selectedRunId]
  );
  const selectedDataset = useMemo(
    () => datasets.find((item) => item.id === selectedDatasetId),
    [datasets, selectedDatasetId]
  );

  useEffect(() => {
    if (selectedRunId) void loadResults(selectedRunId, "all", 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRunId]);

  async function loadResults(runId: string, nextVerdict: string, offset: number) {
    setResultsLoading(true);
    setError(null);
    try {
      const response = await clientRequest<EvalResultListResponse>(
        `/api/eval/runs/${encodeURIComponent(runId)}/results?verdict=${encodeURIComponent(nextVerdict)}&offset=${offset}&limit=20`
      );
      setResults(response);
      setVerdict(nextVerdict);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "评估样本加载失败");
    } finally {
      setResultsLoading(false);
    }
  }

  async function startRun() {
    if (!selectedDatasetId || running) return;
    setRunning(true);
    setError(null);
    setNotice(null);
    try {
      const run = await clientRequest<EvalRun>("/api/eval/runs", {
        method: "POST",
        csrfToken,
        body: JSON.stringify({
          dataset_id: selectedDatasetId,
          label: runLabel.trim() || null,
          prompt_version: promptVersion,
          retrieval_config: { limit: retrievalLimit }
        })
      });
      setRuns((current) => [run, ...current]);
      setSelectedRunId(run.id);
      setNotice(`Run 已完成：${run.sample_count} 条样本，${formatDateTime(run.created_at)}`);
      if (!baselineId) setBaselineId(run.id);
      setCandidateId(run.id);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "启动评估失败");
    } finally {
      setRunning(false);
    }
  }

  async function compare() {
    if (!baselineId || !candidateId || baselineId === candidateId) {
      setError("请选择两个不同的 Run 进行对比");
      return;
    }
    setComparing(true);
    setError(null);
    try {
      const response = await clientRequest<EvalCompareResponse>(
        `/api/eval/compare?baseline_run_id=${encodeURIComponent(baselineId)}&candidate_run_id=${encodeURIComponent(candidateId)}`
      );
      setComparison(response);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "对比失败");
    } finally {
      setComparing(false);
    }
  }

  async function review(result: EvalResult, decision: "PASS" | "FAIL") {
    if (!selectedRunId) return;
    setReviewing(result.id);
    setError(null);
    try {
      const updated = await clientRequest<EvalResult>(
        `/api/eval/runs/${encodeURIComponent(selectedRunId)}/results/${encodeURIComponent(result.id)}`,
        {
          method: "PATCH",
          csrfToken,
          body: JSON.stringify({ verdict: decision, note: notes[result.id] ?? result.manual_note })
        }
      );
      setResults((current) =>
        current
          ? { ...current, items: current.items.map((item) => (item.id === updated.id ? updated : item)) }
          : current
      );
      setNotice(`样本 #${updated.ordinal} 已标记为 ${decision === "PASS" ? "通过" : "失败"}`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "保存人工判定失败");
    } finally {
      setReviewing(null);
    }
  }

  async function importDataset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!importFile || !importName.trim()) {
      setError("请填写数据集名称并选择 JSONL/CSV 文件");
      return;
    }
    setImporting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.set("file", importFile);
      formData.set("name", importName.trim());
      formData.set("dataset_type", importType);
      formData.set("version", importVersion.trim() || "v1");
      const dataset = await clientRequest<EvalDataset>("/api/eval/datasets/import", {
        method: "POST",
        body: formData,
        csrfToken
      });
      setDatasets((current) => [...current, dataset]);
      setSelectedDatasetId(dataset.id);
      setImportName("");
      setImportFile(null);
      setNotice(`数据集「${dataset.name}」已导入 ${dataset.item_count} 条样本`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "导入数据集失败");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1380px] space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="sd-eyebrow">评估</p>
          <h1 className="sd-page-title mt-1">评估控制台</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-ink-secondary">
            固定数据集、可复现配置与逐样本结果。比率为规则基线的本地估算，页面同时展示样本量、延迟和成本口径。
          </p>
        </div>
        <span className="sd-chip">
          <Icon name="flask" size={12} />
          {datasets.reduce((sum, item) => sum + item.item_count, 0)} 条固定/导入样本
        </span>
      </header>

      {error && <Alert tone="danger">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="sd-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">数据集</h2>
            <span className="text-[9px] text-ink-tertiary">知识 40 · 分诊 80 · 安全 15</span>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {datasets.map((dataset) => (
              <button
                key={dataset.id}
                type="button"
                onClick={() => setSelectedDatasetId(dataset.id)}
                className={cn(
                  "rounded-card border p-3 text-left transition-colors",
                  selectedDatasetId === dataset.id
                    ? "border-brand bg-brand-soft"
                    : "border-line bg-surface hover:border-line-strong"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-medium text-brand">
                    {TYPE_LABELS[dataset.dataset_type] ?? dataset.dataset_type}
                  </span>
                  <span className="text-[9px] text-ink-tertiary">{dataset.is_fixed ? "固定" : "导入"}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs font-semibold text-ink">{dataset.name}</p>
                <p className="mt-1 text-[9px] text-ink-tertiary">
                  {dataset.item_count} 条 · {dataset.version}
                </p>
              </button>
            ))}
          </div>
          {selectedDataset && (
            <p className="mt-3 rounded-control border border-line bg-subtle px-3 py-2 text-[10px] leading-5 text-ink-secondary">
              {selectedDataset.description}
            </p>
          )}
          <details className="mt-3 rounded-control border border-line bg-subtle px-3 py-2.5">
            <summary className="cursor-pointer text-[11px] font-medium text-ink">导入 JSONL / CSV 数据集</summary>
            <form onSubmit={importDataset} className="mt-3 grid gap-2 sm:grid-cols-2">
              <input
                className="sd-input"
                value={importName}
                onChange={(event) => setImportName(event.target.value)}
                placeholder="数据集名称"
              />
              <select
                className="sd-input"
                value={importType}
                onChange={(event) => setImportType(event.target.value)}
              >
                <option value="knowledge">知识问答</option>
                <option value="triage">工单分诊</option>
                <option value="security">安全场景</option>
              </select>
              <input
                className="sd-input"
                value={importVersion}
                onChange={(event) => setImportVersion(event.target.value)}
                placeholder="版本，如 v1"
              />
              <input
                type="file"
                accept=".jsonl,.json,.csv"
                onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
                className="block w-full text-[10px] text-ink-secondary file:mr-2 file:rounded-control file:border-0 file:bg-surface file:px-2 file:py-1.5 file:text-[10px]"
              />
              <div className="sm:col-span-2">
                <button type="submit" disabled={importing} className="sd-button-secondary">
                  {importing ? "导入中…" : "导入数据集"}
                </button>
              </div>
            </form>
          </details>
        </div>

        <div className="sd-card p-5">
          <h2 className="text-sm font-semibold text-ink">运行配置</h2>
          <div className="mt-3 space-y-3">
            <label className="block">
              <span className="sd-label">Run 标签（可选）</span>
              <input
                value={runLabel}
                onChange={(event) => setRunLabel(event.target.value)}
                className="sd-input"
                placeholder="例如：v2 检索 Top-8"
              />
            </label>
            <label className="block">
              <span className="sd-label">Prompt 版本</span>
              <select
                value={promptVersion}
                onChange={(event) => setPromptVersion(event.target.value)}
                className="sd-input"
              >
                {prompts.map((prompt) => (
                  <option key={prompt.id} value={prompt.version}>
                    {prompt.version} {prompt.is_active ? "· 当前生效" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="sd-label">检索 Top-K</span>
              <input
                type="number"
                min={1}
                max={10}
                value={retrievalLimit}
                onChange={(event) => setRetrievalLimit(Number(event.target.value))}
                className="sd-input"
              />
            </label>
            <button
              type="button"
              onClick={() => void startRun()}
              disabled={running || !selectedDatasetId}
              className="sd-button-primary w-full"
            >
              <Icon name="flask" size={14} />
              {running ? "运行中…" : "运行评估"}
            </button>
            <p className="text-[9px] leading-5 text-ink-tertiary">
              当前模型为本地规则基线 `extractive-rag-v1`。Token 成本和延迟均标记为本地估算，不能当作生产模型账单。
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <div className="sd-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-3">
            <h2 className="text-sm font-semibold text-ink">Eval Runs</h2>
            <span className="text-[9px] text-ink-tertiary">{runs.length} 次运行</span>
          </div>
          <div className="max-h-[320px] overflow-auto">
            <table className="w-full min-w-[720px] text-left text-xs">
              <thead className="sticky top-0 bg-subtle text-[10px] text-ink-tertiary">
                <tr className="border-b border-line">
                  <th className="px-4 py-2.5 font-medium">Run</th>
                  <th className="px-4 py-2.5 font-medium">数据集</th>
                  <th className="px-4 py-2.5 font-medium">样本</th>
                  <th className="px-4 py-2.5 font-medium">通过率</th>
                  <th className="px-4 py-2.5 font-medium">Prompt</th>
                  <th className="px-4 py-2.5 font-medium">时间</th>
                </tr>
              </thead>
              <tbody>
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-ink-tertiary">
                      还没有 Run。选择数据集与配置后运行一次评估。
                    </td>
                  </tr>
                ) : (
                  runs.map((run) => (
                    <tr
                      key={run.id}
                      onClick={() => setSelectedRunId(run.id)}
                      className={cn(
                        "cursor-pointer border-b border-line/70 last:border-0 hover:bg-subtle/70",
                        selectedRunId === run.id && "bg-brand-soft/60"
                      )}
                    >
                      <td className="max-w-[220px] px-4 py-2.5">
                        <p className="truncate font-medium text-ink">{run.label}</p>
                        <p className="font-mono text-[9px] text-ink-tertiary">{run.id.slice(0, 14)}</p>
                      </td>
                      <td className="px-4 py-2.5 text-ink-secondary">
                        {TYPE_LABELS[run.dataset_type] ?? run.dataset_type}
                      </td>
                      <td className="px-4 py-2.5 text-ink-secondary">{run.sample_count}</td>
                      <td className="px-4 py-2.5 font-medium text-ink">
                        {pct(metricNumber(run, "pass_rate"))}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-[9px] text-ink-tertiary">
                        {run.prompt_version}
                      </td>
                      <td className="px-4 py-2.5 text-[9px] text-ink-tertiary">
                        {formatDateTime(run.created_at)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="sd-card p-5">
          <h2 className="text-sm font-semibold text-ink">配置对比</h2>
          {runs.length < 2 ? (
            <p className="mt-3 text-[10px] leading-5 text-ink-tertiary">
              至少完成两个 Run 后可并排比较指标差异。关键指标下降超过 3 个百分点会标记为回归阻断。
            </p>
          ) : (
            <div className="mt-3 space-y-2.5">
              <label className="block">
                <span className="sd-label">基线 Run</span>
                <select
                  className="sd-input"
                  value={baselineId}
                  onChange={(event) => setBaselineId(event.target.value)}
                >
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {run.label} · {pct(metricNumber(run, "pass_rate"))}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="sd-label">候选 Run</span>
                <select
                  className="sd-input"
                  value={candidateId}
                  onChange={(event) => setCandidateId(event.target.value)}
                >
                  {runs.map((run) => (
                    <option key={run.id} value={run.id}>
                      {run.label} · {pct(metricNumber(run, "pass_rate"))}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => void compare()}
                disabled={comparing || baselineId === candidateId}
                className="sd-button-secondary w-full"
              >
                {comparing ? "对比中…" : "比较两个配置"}
              </button>
            </div>
          )}
          {comparison && (
            <div className="mt-4 space-y-2">
              <div
                className={cn(
                  "rounded-control border px-3 py-2 text-[10px] leading-5",
                  comparison.regression_blocked
                    ? "border-danger/30 bg-danger-soft text-danger"
                    : "border-success/30 bg-success-soft text-success"
                )}
              >
                {comparison.regression_blocked
                  ? `回归门禁阻断：${comparison.blocking_metrics.join("、")}`
                  : `未触发 ${(comparison.threshold * 100).toFixed(1)} 个百分点回归门禁`}
              </div>
              {comparison.metrics
                .filter((item) => item.unit === "ratio")
                .map((item) => (
                  <div key={item.key} className="flex items-center justify-between gap-3 text-[10px]">
                    <span className="text-ink-secondary">{item.label}</span>
                    <span
                      className={cn(
                        "font-mono",
                        item.regressed ? "text-danger" : "text-ink"
                      )}
                    >
                      {pct(item.baseline)} → {pct(item.candidate)} ({item.delta && item.delta > 0 ? "+" : ""}
                      {((item.delta ?? 0) * 100).toFixed(1)}pp)
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>
      </section>

      {selectedRun && (
        <section className="sd-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">{selectedRun.label}</h2>
              <p className="mt-1 text-[10px] text-ink-tertiary">
                {TYPE_LABELS[selectedRun.dataset_type]} · {selectedRun.sample_count} 条样本 · Prompt{" "}
                {selectedRun.prompt_version} · {selectedRun.created_by_name || "系统"}
              </p>
            </div>
            <span className="sd-chip">{selectedRun.status}</span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {(METRICS_BY_TYPE[selectedRun.dataset_type] ?? []).map(([key, label]) => (
              <MetricCard
                key={key}
                label={label}
                value={pct(metricNumber(selectedRun, key))}
                sample={selectedRun.metrics.metric_sample_sizes?.[key] ?? selectedRun.sample_count}
              />
            ))}
            <MetricCard
              label="整体通过率"
              value={pct(metricNumber(selectedRun, "pass_rate"))}
              sample={selectedRun.sample_count}
            />
            <MetricCard
              label="平均延迟"
              value={`${(metricNumber(selectedRun, "avg_latency_ms") ?? 0).toFixed(1)} ms`}
              sample={selectedRun.sample_count}
            />
            <MetricCard
              label="平均 Token 成本"
              value={`$${(metricNumber(selectedRun, "avg_cost_usd") ?? 0).toFixed(8)}`}
              sample={selectedRun.sample_count}
            />
            <MetricCard
              label="样本量"
              value={String(selectedRun.sample_count)}
              sample={selectedRun.sample_count}
            />
          </div>
          <p className="mt-3 text-[9px] leading-5 text-ink-tertiary">
            {String(selectedRun.metrics.cost_note ?? "本地估算")}；{String(selectedRun.metrics.latency_note ?? "")}
          </p>
        </section>
      )}

      {selectedRun && (
        <section className="sd-card overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">样本结果</h2>
              <p className="mt-0.5 text-[9px] text-ink-tertiary">
                {results?.total ?? 0} 条匹配 · 人工判定与备注只作用于本条样本
              </p>
            </div>
            <select
              value={verdict}
              onChange={(event) => void loadResults(selectedRun.id, event.target.value, 0)}
              className="sd-input h-8 w-40 text-[11px]"
            >
              <option value="all">全部样本</option>
              <option value="failed">自动失败</option>
              <option value="passed">自动通过</option>
              <option value="unreviewed">未人工复核</option>
              <option value="reviewed">已人工复核</option>
            </select>
          </div>

          {resultsLoading ? (
            <p className="px-5 py-10 text-center text-xs text-ink-tertiary">加载样本…</p>
          ) : results && results.items.length > 0 ? (
            <div className="divide-y divide-line">
              {results.items.map((result) => (
                <article key={result.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[9px] text-ink-tertiary">#{result.ordinal}</span>
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[9px] font-medium",
                            result.passed
                              ? "bg-success-soft text-success"
                              : "bg-danger-soft text-danger"
                          )}
                        >
                          {result.passed ? "自动通过" : "自动失败"}
                        </span>
                        {result.manual_verdict && (
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[9px] font-medium",
                              result.manual_verdict === "PASS"
                                ? "bg-brand-soft text-brand"
                                : "bg-warning-soft text-warning"
                            )}
                          >
                            人工 {result.manual_verdict === "PASS" ? "通过" : "失败"}
                          </span>
                        )}
                        <span className="text-[9px] text-ink-tertiary">
                          {result.latency_ms} ms · {result.token_count} tokens · ${result.cost_usd.toFixed(8)}
                        </span>
                      </div>
                      <p className="mt-1.5 max-w-4xl text-xs font-medium leading-5 text-ink">
                        {inputText(result)}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setExpanded(expanded === result.id ? null : result.id)}
                      className="sd-button-secondary h-7"
                    >
                      {expanded === result.id ? "收起" : "查看详情"}
                    </button>
                  </div>

                  {result.failure_reason && (
                    <p className="mt-2 rounded-control border border-danger/20 bg-danger-soft px-3 py-2 text-[10px] leading-5 text-danger">
                      失败原因：{result.failure_reason}
                    </p>
                  )}

                  {expanded === result.id && (
                    <div className="mt-3 grid gap-3 lg:grid-cols-2">
                      <div className="rounded-control border border-line bg-subtle p-3">
                        <p className="text-[9px] font-semibold text-ink-tertiary">期望</p>
                        <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-[9px] leading-5 text-ink-secondary">
                          {JSON.stringify(result.expected, null, 2)}
                        </pre>
                      </div>
                      <div className="rounded-control border border-line bg-subtle p-3">
                        <p className="text-[9px] font-semibold text-ink-tertiary">实际输出</p>
                        <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-[9px] leading-5 text-ink-secondary">
                          {JSON.stringify(result.actual, null, 2)}
                        </pre>
                      </div>
                      <div className="lg:col-span-2">
                        <p className="text-[9px] font-semibold text-ink-tertiary">引用</p>
                        {result.citations.length === 0 ? (
                          <p className="mt-1 text-[10px] text-ink-tertiary">本条样本没有引用。</p>
                        ) : (
                          <div className="mt-1 space-y-1.5">
                            {result.citations.map((citation, index) => (
                              <div
                                key={`${result.id}-${index}`}
                                className="rounded-control border border-line px-3 py-2 text-[10px] leading-5 text-ink-secondary"
                              >
                                <span className="font-medium text-ink">
                                  《{String(citation.title ?? "来源不可用")}》
                                </span>
                                <span className="ml-2 text-[9px] text-ink-tertiary">
                                  {String(citation.section ?? "")}
                                </span>
                                <p className="mt-1 line-clamp-3">{String(citation.quote ?? "")}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                    <input
                      value={notes[result.id] ?? result.manual_note}
                      onChange={(event) =>
                        setNotes((current) => ({ ...current, [result.id]: event.target.value }))
                      }
                      className="sd-input h-8 text-[11px]"
                      placeholder="人工评估备注：失败原因、引用问题或修正建议"
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => void review(result, "FAIL")}
                        disabled={reviewing === result.id}
                        className="sd-button-secondary h-8 border-danger/40 text-danger"
                      >
                        标记失败
                      </button>
                      <button
                        type="button"
                        onClick={() => void review(result, "PASS")}
                        disabled={reviewing === result.id}
                        className="sd-button-primary h-8"
                      >
                        标记通过
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="px-5 py-10 text-center text-xs text-ink-tertiary">当前筛选下没有样本。</p>
          )}

          {results && results.total > results.limit && (
            <div className="flex items-center justify-between border-t border-line px-5 py-3 text-[10px] text-ink-tertiary">
              <span>
                显示 {results.offset + 1}–{Math.min(results.offset + results.limit, results.total)} / {results.total}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={results.offset === 0 || resultsLoading}
                  onClick={() =>
                    void loadResults(selectedRun.id, verdict, Math.max(0, results.offset - results.limit))
                  }
                  className="sd-button-secondary h-7"
                >
                  上一页
                </button>
                <button
                  type="button"
                  disabled={results.offset + results.limit >= results.total || resultsLoading}
                  onClick={() => void loadResults(selectedRun.id, verdict, results.offset + results.limit)}
                  className="sd-button-secondary h-7"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function MetricCard({ label, value, sample }: { label: string; value: string; sample: number }) {
  return (
    <div className="rounded-control border border-line bg-subtle px-3 py-2.5">
      <p className="text-[9px] text-ink-tertiary">{label}</p>
      <p className="mt-1 text-lg font-semibold tracking-[-0.02em] text-ink">{value}</p>
      <p className="mt-0.5 text-[9px] text-ink-tertiary">样本 {sample}</p>
    </div>
  );
}

function Alert({ tone, children }: { tone: "danger" | "success"; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-control border px-3 py-2 text-xs",
        tone === "danger"
          ? "border-danger/30 bg-danger-soft text-danger"
          : "border-success/30 bg-success-soft text-success"
      )}
    >
      {children}
    </div>
  );
}

function inputText(result: EvalResult): string {
  const value = result.input.text ?? result.input.query ?? result.input.input;
  return typeof value === "string" ? value : JSON.stringify(result.input);
}
