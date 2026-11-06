"use client";

import { useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type {
  AdminSettings,
  AdminUser,
  DemoResetResponse,
  PromptVersion,
  Role,
  RuntimeConfig,
  ToolPolicy,
  ToolPolicyListResponse
} from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";

const ROLE_OPTIONS: Array<{ value: Role; label: string }> = [
  { value: "employee", label: "员工" },
  { value: "support", label: "支持专员" },
  { value: "approver", label: "审批人" },
  { value: "admin", label: "管理员" },
  { value: "evaluator", label: "评估员" },
  { value: "auditor", label: "审计员" }
];

interface UserDraft {
  role: Role;
  department: string;
  is_active: boolean;
}

export function SettingsConsole({
  initialSettings,
  initialTools,
  csrfToken,
  currentUserId
}: {
  initialSettings: AdminSettings;
  initialTools: ToolPolicyListResponse;
  csrfToken: string;
  currentUserId: string;
}) {
  const [settings, setSettings] = useState(initialSettings);
  const [tools, setTools] = useState(initialTools);
  const [runtime, setRuntime] = useState<RuntimeConfig>(initialSettings.runtime_config);
  const [killReason, setKillReason] = useState(initialTools.kill_switch_reason ?? "");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [userDrafts, setUserDrafts] = useState<Record<string, UserDraft>>(() =>
    Object.fromEntries(
      initialSettings.users.map((user) => [
        user.id,
        { role: user.role, department: user.department, is_active: user.is_active }
      ])
    )
  );
  const [promptForm, setPromptForm] = useState({
    version: "",
    name: "",
    system_prompt: "",
    activate: false
  });
  const [resetPhrase, setResetPhrase] = useState("");
  const [resetConfirmed, setResetConfirmed] = useState(false);
  const [resetResult, setResetResult] = useState<DemoResetResponse | null>(null);

  async function updateTool(tool: ToolPolicy, patch: { enabled?: boolean; mock_mode?: string }) {
    setPending(`tool:${tool.name}`);
    setError(null);
    setNotice(null);
    try {
      const updated = await clientRequest<ToolPolicy>(`/api/admin/tools/${encodeURIComponent(tool.name)}`, {
        method: "PATCH",
        csrfToken,
        body: JSON.stringify(patch)
      });
      setTools((current) => ({
        ...current,
        items: current.items.map((item) => (item.name === updated.name ? updated : item))
      }));
      setNotice(`工具「${updated.label}」策略已更新，并写入配置审计。`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "更新工具策略失败");
    } finally {
      setPending(null);
    }
  }

  async function toggleKillSwitch(next: boolean) {
    if (
      next &&
      !window.confirm("确认开启全局 Kill Switch？所有写工具执行都会被阻断，直到管理员关闭。")
    ) {
      return;
    }
    setPending("kill-switch");
    setError(null);
    setNotice(null);
    try {
      const response = await clientRequest<{ enabled: boolean; reason: string | null }>(
        "/api/admin/kill-switch",
        {
          method: "PUT",
          csrfToken,
          body: JSON.stringify({ enabled: next, reason: killReason.trim() || null })
        }
      );
      setTools((current) => ({
        ...current,
        kill_switch_enabled: response.enabled,
        kill_switch_reason: response.reason
      }));
      setNotice(response.enabled ? "Kill Switch 已开启，所有写操作暂停。" : "Kill Switch 已关闭。");
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "更新 Kill Switch 失败");
    } finally {
      setPending(null);
    }
  }

  async function saveRuntime() {
    setPending("runtime");
    setError(null);
    setNotice(null);
    try {
      const updated = await clientRequest<RuntimeConfig>("/api/admin/runtime-config", {
        method: "PUT",
        csrfToken,
        body: JSON.stringify(runtime)
      });
      setRuntime(updated);
      setSettings((current) => ({ ...current, runtime_config: updated }));
      setNotice("运行参数已保存，前后值已写入配置审计。");
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "保存运行参数失败");
    } finally {
      setPending(null);
    }
  }

  async function saveUser(user: AdminUser) {
    const draft = userDrafts[user.id];
    if (!draft) return;
    setPending(`user:${user.id}`);
    setError(null);
    setNotice(null);
    try {
      const updated = await clientRequest<AdminUser>(`/api/admin/users/${encodeURIComponent(user.id)}`, {
        method: "PATCH",
        csrfToken,
        body: JSON.stringify({
          role: draft.role,
          department: draft.department,
          is_active: draft.is_active
        })
      });
      setSettings((current) => ({
        ...current,
        users: current.users.map((item) => (item.id === updated.id ? updated : item))
      }));
      setUserDrafts((current) => ({
        ...current,
        [updated.id]: {
          role: updated.role,
          department: updated.department,
          is_active: updated.is_active
        }
      }));
      setNotice(`用户「${updated.name}」的角色与状态已更新。`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "更新用户失败");
    } finally {
      setPending(null);
    }
  }

  async function createPrompt(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!promptForm.version.trim() || !promptForm.name.trim() || !promptForm.system_prompt.trim()) {
      setError("请完整填写 Prompt 版本、名称和系统提示词");
      return;
    }
    setPending("prompt:create");
    setError(null);
    setNotice(null);
    try {
      const created = await clientRequest<PromptVersion>("/api/admin/prompts", {
        method: "POST",
        csrfToken,
        body: JSON.stringify(promptForm)
      });
      setSettings((current) => ({
        ...current,
        prompts: created.is_active
          ? [
              ...current.prompts.map((item) => ({ ...item, is_active: false })),
              created
            ]
          : [...current.prompts, created]
      }));
      setPromptForm({ version: "", name: "", system_prompt: "", activate: false });
      setNotice(`Prompt 版本 ${created.version} 已创建${created.is_active ? "并设为生效版本" : ""}。`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "创建 Prompt 版本失败");
    } finally {
      setPending(null);
    }
  }

  async function activatePrompt(prompt: PromptVersion) {
    setPending(`prompt:${prompt.id}`);
    setError(null);
    setNotice(null);
    try {
      const updated = await clientRequest<PromptVersion>(
        `/api/admin/prompts/${encodeURIComponent(prompt.id)}/activate`,
        { method: "POST", csrfToken }
      );
      setSettings((current) => ({
        ...current,
        prompts: current.prompts.map((item) => ({
          ...item,
          is_active: item.id === updated.id
        }))
      }));
      setNotice(`Prompt ${updated.version} 已设为当前生效版本。`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "切换 Prompt 版本失败");
    } finally {
      setPending(null);
    }
  }

  async function resetDemo() {
    if (!resetConfirmed || resetPhrase.trim() !== "RESET-DEMO") return;
    if (
      !window.confirm(
        "最后确认：将删除 Case、工单、审批、评估 Run 和知识文档，并恢复 Mock 工具默认状态。审计历史会保留。"
      )
    ) {
      return;
    }
    setPending("reset");
    setError(null);
    setNotice(null);
    try {
      const response = await clientRequest<DemoResetResponse>("/api/admin/reset-demo", {
        method: "POST",
        csrfToken,
        body: JSON.stringify({ confirmation: "RESET-DEMO" })
      });
      setResetResult(response);
      setNotice(response.message);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "重置演示数据失败");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="mx-auto max-w-[1320px] space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="sd-eyebrow">管理</p>
          <h1 className="sd-page-title mt-1">系统配置</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-ink-secondary">
            工具连接器由代码固定，管理界面只启停与演练；所有配置变更记录操作者、时间和前后值。
          </p>
        </div>
        <span className="sd-chip">
          <Icon name="lock" size={12} />
          仅管理员
        </span>
      </header>

      {error && <Alert tone="danger">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="sd-card p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">全局 Kill Switch</h2>
              <p className="mt-1 text-[10px] leading-5 text-ink-secondary">
                开启后，所有写工具在审批与执行前都会被阻断。
              </p>
            </div>
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-[9px] font-medium",
                tools.kill_switch_enabled
                  ? "bg-danger-soft text-danger"
                  : "bg-success-soft text-success"
              )}
            >
              {tools.kill_switch_enabled ? "已开启" : "正常"}
            </span>
          </div>
          <label className="mt-4 block">
            <span className="sd-label">原因（开启时建议填写）</span>
            <input
              value={killReason}
              onChange={(event) => setKillReason(event.target.value)}
              maxLength={300}
              className="sd-input"
              placeholder="例如：安全演练 / 生产事故处置"
            />
          </label>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => void toggleKillSwitch(true)}
              disabled={pending === "kill-switch" || tools.kill_switch_enabled}
              className="sd-button-secondary border-danger/40 text-danger"
            >
              开启 Kill Switch
            </button>
            <button
              type="button"
              onClick={() => void toggleKillSwitch(false)}
              disabled={pending === "kill-switch" || !tools.kill_switch_enabled}
              className="sd-button-primary"
            >
              恢复正常
            </button>
          </div>
        </div>

        <div className="sd-card p-5">
          <h2 className="text-sm font-semibold text-ink">运行参数</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <NumberField
              label="检索 Top-K"
              value={runtime.retrieval_limit}
              min={1}
              max={10}
              onChange={(value) => setRuntime((current) => ({ ...current, retrieval_limit: value }))}
            />
            <NumberField
              label="最大上下文片段"
              value={runtime.max_context_chunks}
              min={1}
              max={10}
              onChange={(value) => setRuntime((current) => ({ ...current, max_context_chunks: value }))}
            />
            <NumberField
              label="检索最低相关度"
              value={runtime.retrieval_min_score}
              min={0}
              max={1}
              step={0.05}
              onChange={(value) => setRuntime((current) => ({ ...current, retrieval_min_score: value }))}
            />
            <NumberField
              label="最大步骤数"
              value={runtime.max_steps}
              min={1}
              max={20}
              onChange={(value) => setRuntime((current) => ({ ...current, max_steps: value }))}
            />
            <NumberField
              label="审批有效期（秒）"
              value={runtime.approval_ttl_seconds}
              min={60}
              max={86400}
              onChange={(value) => setRuntime((current) => ({ ...current, approval_ttl_seconds: value }))}
            />
            <NumberField
              label="回归门禁阈值（比例）"
              value={runtime.evaluation_regression_threshold}
              min={0}
              max={1}
              step={0.01}
              onChange={(value) => setRuntime((current) => ({ ...current, evaluation_regression_threshold: value }))}
            />
            <label className="block sm:col-span-2">
              <span className="sd-label">回答风格</span>
              <select
                value={runtime.answer_style}
                onChange={(event) =>
                  setRuntime((current) => ({
                    ...current,
                    answer_style: event.target.value as RuntimeConfig["answer_style"]
                  }))
                }
                className="sd-input"
              >
                <option value="concise">简洁</option>
                <option value="detailed">详细</option>
              </select>
            </label>
          </div>
          <button
            type="button"
            onClick={() => void saveRuntime()}
            disabled={pending === "runtime"}
            className="sd-button-primary mt-3"
          >
            保存运行参数
          </button>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
        <div className="sd-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">Prompt 版本</h2>
            <span className="sd-chip">{settings.prompts.length} 个版本</span>
          </div>
          <div className="mt-3 space-y-2.5">
            {settings.prompts.map((prompt) => (
              <div key={prompt.id} className="rounded-control border border-line px-3 py-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-medium text-ink">
                      {prompt.name}{" "}
                      <span className="ml-1 font-mono text-[9px] text-ink-tertiary">{prompt.version}</span>
                    </p>
                    <p className="mt-1 text-[9px] text-ink-tertiary">
                      {prompt.created_by_name || "系统"} · {formatDateTime(prompt.created_at)}
                    </p>
                  </div>
                  {prompt.is_active ? (
                    <span className="rounded-full bg-success-soft px-2 py-0.5 text-[9px] font-medium text-success">
                      当前生效
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => void activatePrompt(prompt)}
                      disabled={pending === `prompt:${prompt.id}`}
                      className="sd-button-secondary h-7"
                    >
                      设为生效
                    </button>
                  )}
                </div>
                <p className="mt-2 line-clamp-2 text-[10px] leading-5 text-ink-secondary">{prompt.system_prompt}</p>
              </div>
            ))}
          </div>
        </div>

        <form onSubmit={createPrompt} className="sd-card p-5">
          <h2 className="text-sm font-semibold text-ink">新建 Prompt 版本</h2>
          <div className="mt-3 space-y-2.5">
            <label className="block">
              <span className="sd-label">版本标识</span>
              <input
                value={promptForm.version}
                onChange={(event) => setPromptForm((current) => ({ ...current, version: event.target.value }))}
                maxLength={80}
                className="sd-input"
                placeholder="例如：m4-safe-v3"
              />
            </label>
            <label className="block">
              <span className="sd-label">名称</span>
              <input
                value={promptForm.name}
                onChange={(event) => setPromptForm((current) => ({ ...current, name: event.target.value }))}
                maxLength={120}
                className="sd-input"
                placeholder="例如：安全强化 v3"
              />
            </label>
            <label className="block">
              <span className="sd-label">系统提示词</span>
              <textarea
                value={promptForm.system_prompt}
                onChange={(event) =>
                  setPromptForm((current) => ({ ...current, system_prompt: event.target.value }))
                }
                rows={6}
                maxLength={8000}
                className="sd-textarea text-xs"
                placeholder="说明隐私、拒答、引用和写操作审批边界"
              />
            </label>
            <label className="flex items-center gap-2 text-[10px] text-ink-secondary">
              <input
                type="checkbox"
                checked={promptForm.activate}
                onChange={(event) =>
                  setPromptForm((current) => ({ ...current, activate: event.target.checked }))
                }
              />
              创建后立即设为当前生效版本
            </label>
            <button
              type="submit"
              disabled={pending === "prompt:create"}
              className="sd-button-primary w-full"
            >
              创建 Prompt 版本
            </button>
          </div>
        </form>
      </section>

      <section className="sd-card border-danger/20 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Icon name="alert" size={15} className="text-danger" />
              重置演示数据
            </h2>
            <p className="mt-1 max-w-2xl text-[10px] leading-5 text-ink-secondary">
              删除 Case、工单、审批、工具执行、评估 Run、知识文档与配置覆盖，恢复 12 篇合成文档和默认 Mock 工具状态。
              审计历史不会删除。
            </p>
          </div>
          <span className="sd-chip border-danger/30 text-danger">高危操作</span>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
          <label className="flex items-start gap-2 rounded-control border border-line bg-subtle px-3 py-2.5 text-[10px] leading-5 text-ink-secondary">
            <input
              type="checkbox"
              checked={resetConfirmed}
              onChange={(event) => setResetConfirmed(event.target.checked)}
              className="mt-0.5"
            />
            我已了解该操作会清空当前演示业务数据，并保留审计事件。
          </label>
          <label className="block">
            <span className="sd-label">输入 RESET-DEMO 确认</span>
            <input
              value={resetPhrase}
              onChange={(event) => setResetPhrase(event.target.value)}
              className="sd-input"
              placeholder="RESET-DEMO"
            />
          </label>
          <button
            type="button"
            onClick={() => void resetDemo()}
            disabled={!resetConfirmed || resetPhrase.trim() !== "RESET-DEMO" || pending === "reset"}
            className="sd-button-secondary border-danger/50 text-danger"
          >
            {pending === "reset" ? "重置中…" : "二次确认并重置"}
          </button>
        </div>
        {resetResult && (
          <div className="mt-3 rounded-control border border-line bg-subtle px-3 py-2.5 text-[10px] leading-5 text-ink-secondary">
            <p className="font-medium text-ink">{resetResult.message}</p>
            <p className="mt-1">
              恢复文档 {resetResult.reseeded_documents} 篇 · 删除 Case {resetResult.deleted.cases ?? 0} 个 ·
              工单 {resetResult.deleted.tickets ?? 0} 个 · 审计事件 {resetResult.audit_event_id}
            </p>
          </div>
        )}
      </section>
      <section className="sd-card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">工具策略</h2>
            <p className="mt-0.5 text-[9px] text-ink-tertiary">
              工具白名单来自代码注册表；页面只能启停和选择 Mock 成功/失败/超时。
            </p>
          </div>
          <span className="sd-chip">{tools.items.length} 个固定工具</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead className="border-b border-line bg-subtle text-[10px] text-ink-tertiary">
              <tr>
                <th className="px-4 py-2.5 font-medium">工具</th>
                <th className="px-4 py-2.5 font-medium">类型/风险</th>
                <th className="px-4 py-2.5 font-medium">审批</th>
                <th className="px-4 py-2.5 font-medium">启用</th>
                <th className="px-4 py-2.5 font-medium">Mock 模式</th>
              </tr>
            </thead>
            <tbody>
              {tools.items.map((tool) => (
                <tr key={tool.name} className="border-b border-line/70 last:border-0">
                  <td className="px-4 py-3">
                    <p className="font-medium text-ink">{tool.label}</p>
                    <p className="mt-0.5 font-mono text-[9px] text-ink-tertiary">{tool.name}</p>
                    <p className="mt-1 max-w-xl text-[10px] leading-5 text-ink-secondary">{tool.description}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-ink-secondary">{tool.tool_type}</p>
                    <p className="text-[9px] text-ink-tertiary">{tool.risk_level}</p>
                  </td>
                  <td className="px-4 py-3 text-ink-secondary">
                    {tool.requires_approval ? "需要人工审批" : "只读自动执行"}
                  </td>
                  <td className="px-4 py-3">
                    <label className="inline-flex items-center gap-2 text-[10px] text-ink-secondary">
                      <input
                        type="checkbox"
                        checked={tool.enabled}
                        disabled={pending === `tool:${tool.name}`}
                        onChange={(event) => void updateTool(tool, { enabled: event.target.checked })}
                      />
                      {tool.enabled ? "启用" : "停用"}
                    </label>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={tool.mock_mode}
                      disabled={pending === `tool:${tool.name}`}
                      onChange={(event) => void updateTool(tool, { mock_mode: event.target.value })}
                      className="sd-input h-8 w-32 text-[11px]"
                    >
                      <option value="success">成功</option>
                      <option value="fail">失败</option>
                      <option value="timeout">超时</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="sd-card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">用户、角色与部门</h2>
            <p className="mt-0.5 text-[9px] text-ink-tertiary">
              角色决定服务端权限；不能停用自己或移除最后一名启用管理员。
            </p>
          </div>
          <span className="sd-chip">{settings.users.length} 个账号</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[940px] text-left text-xs">
            <thead className="border-b border-line bg-subtle text-[10px] text-ink-tertiary">
              <tr>
                <th className="px-4 py-2.5 font-medium">用户</th>
                <th className="px-4 py-2.5 font-medium">角色</th>
                <th className="px-4 py-2.5 font-medium">部门</th>
                <th className="px-4 py-2.5 font-medium">启用</th>
                <th className="px-4 py-2.5 font-medium">创建时间</th>
                <th className="px-4 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody>
              {settings.users.map((user) => {
                const draft = userDrafts[user.id] ?? {
                  role: user.role,
                  department: user.department,
                  is_active: user.is_active
                };
                const isSelf = user.id === currentUserId;
                return (
                  <tr key={user.id} className="border-b border-line/70 last:border-0">
                    <td className="px-4 py-3">
                      <p className="font-medium text-ink">
                        {user.name} {isSelf && <span className="text-[9px] text-brand">（当前账号）</span>}
                      </p>
                      <p className="font-mono text-[9px] text-ink-tertiary">{user.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={draft.role}
                        disabled={isSelf}
                        onChange={(event) =>
                          setUserDrafts((current) => ({
                            ...current,
                            [user.id]: { ...draft, role: event.target.value as Role }
                          }))
                        }
                        className="sd-input h-8 w-32 text-[11px]"
                      >
                        {ROLE_OPTIONS.map((role) => (
                          <option key={role.value} value={role.value}>
                            {role.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        value={draft.department}
                        onChange={(event) =>
                          setUserDrafts((current) => ({
                            ...current,
                            [user.id]: { ...draft, department: event.target.value }
                          }))
                        }
                        maxLength={80}
                        className="sd-input h-8 w-36 text-[11px]"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <label className="inline-flex items-center gap-2 text-[10px] text-ink-secondary">
                        <input
                          type="checkbox"
                          checked={draft.is_active}
                          disabled={isSelf}
                          onChange={(event) =>
                            setUserDrafts((current) => ({
                              ...current,
                              [user.id]: { ...draft, is_active: event.target.checked }
                            }))
                          }
                        />
                        {draft.is_active ? "启用" : "停用"}
                      </label>
                    </td>
                    <td className="px-4 py-3 text-[9px] text-ink-tertiary">
                      {formatDateTime(user.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => void saveUser(user)}
                        disabled={pending === `user:${user.id}`}
                        className="sd-button-secondary h-7"
                      >
                        保存
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="sd-card p-5">
        <h2 className="text-sm font-semibold text-ink">分类与技能矩阵</h2>
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <div>
            <p className="text-[9px] font-medium text-ink-tertiary">工单分类</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {settings.taxonomy.categories.map((item) => (
                <span key={item.key} className="sd-chip text-[9px]">
                  {item.label}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[9px] font-medium text-ink-tertiary">优先级规则</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {settings.taxonomy.priorities.map((item) => (
                <span key={item.key} className="sd-chip text-[9px]">
                  {item.label}
                </span>
              ))}
            </div>
          </div>
        </div>
        <details className="mt-4 rounded-control border border-line bg-subtle px-3 py-2.5">
          <summary className="cursor-pointer text-[10px] font-medium text-ink">查看角色权限矩阵</summary>
          <div className="mt-3 space-y-2">
            {settings.taxonomy.roles.map((role) => (
              <div key={role.key} className="text-[9px] leading-5">
                <span className="font-medium text-ink">{role.label}</span>
                <span className="ml-2 font-mono text-ink-tertiary">{role.permissions.join(", ")}</span>
              </div>
            ))}
          </div>
        </details>
      </section>
    </div>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  onChange
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <span className="sd-label">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step ?? 1}
        onChange={(event) => onChange(Number(event.target.value))}
        className="sd-input"
      />
    </label>
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
