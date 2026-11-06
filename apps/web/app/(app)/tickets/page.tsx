import type { Metadata } from "next";
import Link from "next/link";

import { AccessDenied } from "@/components/access-denied";
import { Icon } from "@/components/icons";
import { StatusBadge } from "@/components/status-badge";
import { can, requireMe } from "@/lib/page-guard";
import { getTicketAssignees, getTickets } from "@/lib/server-api";
import type { Ticket } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export const metadata: Metadata = { title: "工单" };

const CATEGORY_OPTIONS = [
  ["account_permission", "账号与权限"],
  ["network_vpn", "网络与 VPN"],
  ["software", "软件与安装"],
  ["hardware", "硬件与设备"],
  ["email_collaboration", "邮箱与协作工具"],
  ["security_incident", "安全事件"],
  ["other", "其他"]
] as const;

const STATUS_OPTIONS = [
  ["OPEN", "待处理"],
  ["ASSIGNED", "已分派"],
  ["IN_PROGRESS", "处理中"],
  ["RESOLVED", "已解决"],
  ["CLOSED", "已关闭"],
  ["REOPENED", "已重新打开"],
  ["CANCELLED", "已取消"]
] as const;

const PRIORITY_OPTIONS = ["P1", "P2", "P3", "P4"] as const;

const PRIORITY_STYLES: Record<string, string> = {
  P1: "bg-danger-soft text-danger",
  P2: "bg-warning-soft text-warning",
  P3: "bg-info-soft text-info",
  P4: "bg-subtle text-ink-secondary"
};

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function PriorityBadge({ ticket }: { ticket: Ticket }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-[9px] font-medium ${
        PRIORITY_STYLES[ticket.priority] ?? "bg-subtle text-ink-secondary"
      }`}
    >
      {ticket.priority_label}
    </span>
  );
}

export default async function TicketsPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const me = await requireMe();
  if (!can(me, "ticket:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看工单的权限。" />;
  }

  const params = await searchParams;
  const filters = {
    status: firstValue(params.status),
    category: firstValue(params.category),
    priority: firstValue(params.priority),
    assignee_id: firstValue(params.assignee_id),
    q: firstValue(params.q)
  };
  const canManage = can(me, "ticket:manage");
  const [tickets, assignees] = await Promise.all([
    getTickets(filters),
    canManage ? getTicketAssignees() : Promise.resolve([])
  ]);

  return (
    <div className="mx-auto max-w-[1280px]">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="sd-eyebrow">工单</p>
          <h1 className="sd-page-title mt-1">{canManage ? "工单处理台" : "我的工单"}</h1>
          <p className="mt-2 text-sm text-ink-secondary">
            {canManage
              ? "按状态、分类、优先级与处理人筛选，进入详情修正字段、分派和流转。"
              : "服务端按资源归属过滤，只展示与你有关的已确认工单。"}
          </p>
        </div>
        <span className="sd-chip">
          <span className="h-1.5 w-1.5 rounded-full bg-success" />
          M2 分诊已连接
        </span>
      </header>

      <form className="sd-card mb-4 grid gap-3 p-4 lg:grid-cols-[minmax(180px,1fr)_150px_160px_130px_180px_auto]">
        <label className="block">
          <span className="sd-label">搜索</span>
          <input
            className="sd-input"
            name="q"
            defaultValue={filters.q ?? ""}
            placeholder="标题或问题描述"
            maxLength={100}
          />
        </label>
        <label className="block">
          <span className="sd-label">状态</span>
          <select className="sd-input" name="status" defaultValue={filters.status ?? ""}>
            <option value="">全部</option>
            {STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="sd-label">分类</span>
          <select className="sd-input" name="category" defaultValue={filters.category ?? ""}>
            <option value="">全部</option>
            {CATEGORY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="sd-label">优先级</span>
          <select className="sd-input" name="priority" defaultValue={filters.priority ?? ""}>
            <option value="">全部</option>
            {PRIORITY_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        {canManage ? (
          <label className="block">
            <span className="sd-label">处理人</span>
            <select className="sd-input" name="assignee_id" defaultValue={filters.assignee_id ?? ""}>
              <option value="">全部</option>
              {assignees.map((assignee) => (
                <option key={assignee.id} value={assignee.id}>
                  {assignee.name} · {assignee.open_ticket_count} 个活跃
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="hidden lg:block" />
        )}
        <div className="flex items-end gap-2">
          <button type="submit" className="sd-button-primary h-9">
            <Icon name="search" size={14} />
            筛选
          </button>
          <Link href="/tickets" className="sd-button-secondary h-9">
            重置
          </Link>
        </div>
      </form>

      <section className="sd-card overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold text-ink">已确认工单</h2>
            <p className="mt-0.5 text-[10px] text-ink-tertiary">
              草稿不会出现在列表中，需在 Case 内确认后创建。
            </p>
          </div>
          <span className="sd-chip">{tickets.items.length} 条</span>
        </div>

        {tickets.items.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <span className="mx-auto grid h-11 w-11 place-items-center rounded-overlay border border-line bg-subtle text-ink-tertiary">
              <Icon name="ticket" size={20} />
            </span>
            <h3 className="mt-4 text-sm font-semibold text-ink">暂无匹配工单</h3>
            <p className="mt-2 text-[11px] text-ink-secondary">
              从 Case 对话生成工单草稿，确认后会在这里进入处理队列。
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left text-[11px]">
              <thead>
                <tr className="border-b border-line bg-subtle text-[10px] text-ink-tertiary">
                  <th className="px-5 py-2.5 font-medium">工单</th>
                  <th className="px-3 py-2.5 font-medium">状态</th>
                  <th className="px-3 py-2.5 font-medium">分类</th>
                  <th className="px-3 py-2.5 font-medium">优先级</th>
                  <th className="px-3 py-2.5 font-medium">处理人</th>
                  <th className="px-3 py-2.5 font-medium">提交人</th>
                  <th className="px-5 py-2.5 text-right font-medium">更新时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {tickets.items.map((ticket) => (
                  <tr key={ticket.id} className="align-top transition-colors hover:bg-subtle/60">
                    <td className="px-5 py-3.5">
                      <Link
                        href={`/tickets/${encodeURIComponent(ticket.id)}`}
                        className="font-medium text-ink hover:text-brand"
                      >
                        {ticket.title}
                      </Link>
                      <p className="mt-1 max-w-[360px] truncate text-[9px] text-ink-tertiary">
                        {ticket.id} · {ticket.affected_system || "未填写影响系统"}
                      </p>
                    </td>
                    <td className="px-3 py-3.5">
                      <StatusBadge status={ticket.status} label={ticket.status_label} />
                    </td>
                    <td className="px-3 py-3.5 text-ink-secondary">{ticket.category_label}</td>
                    <td className="px-3 py-3.5">
                      <PriorityBadge ticket={ticket} />
                    </td>
                    <td className="px-3 py-3.5 text-ink-secondary">
                      {ticket.assignee_name || ticket.suggested_assignee_name || "未分派"}
                    </td>
                    <td className="px-3 py-3.5 text-ink-secondary">{ticket.requester_name}</td>
                    <td className="px-5 py-3.5 text-right text-[10px] text-ink-tertiary">
                      {formatDateTime(ticket.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
