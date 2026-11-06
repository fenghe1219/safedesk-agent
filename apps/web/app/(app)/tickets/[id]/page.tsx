import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AccessDenied } from "@/components/access-denied";
import { TicketDetailConsole } from "@/components/ticket-detail-console";
import { can, requireMe } from "@/lib/page-guard";
import { getCaseTimeline, getTicket, getTicketAssignees } from "@/lib/server-api";

export const metadata: Metadata = { title: "工单详情" };

export default async function TicketPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await requireMe();
  if (!can(me, "ticket:view")) {
    return <AccessDenied me={me} detail="当前角色没有查看工单的权限。" />;
  }

  const { id } = await params;
  const ticket = await getTicket(id);
  if (!ticket) notFound();

  const canManage = can(me, "ticket:manage");
  const [timeline, assignees] = await Promise.all([
    getCaseTimeline(ticket.case_id),
    canManage ? getTicketAssignees() : Promise.resolve([])
  ]);

  return (
    <div className="mx-auto max-w-[1280px]">
      <div className="mb-4 flex flex-wrap items-center gap-2 text-[11px] text-ink-tertiary">
        <Link href="/tickets" className="transition-colors hover:text-brand">
          工单
        </Link>
        <span aria-hidden="true">/</span>
        <span className="max-w-48 truncate font-mono">{ticket.id}</span>
      </div>
      <TicketDetailConsole
        ticket={ticket}
        timeline={timeline}
        assignees={assignees}
        csrfToken={me.csrf_token}
        canManage={canManage}
      />
    </div>
  );
}
