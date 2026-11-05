import Link from "next/link";

import type { CaseSummary } from "@/lib/types";
import { formatRelative } from "@/lib/utils";
import { Icon } from "./icons";
import { StatusBadge } from "./status-badge";

export function CaseList({ cases }: { cases: CaseSummary[] }) {
  if (cases.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
        <span className="grid h-9 w-9 place-items-center rounded-full bg-subtle text-ink-tertiary">
          <Icon name="document" size={17} />
        </span>
        <p className="mt-3 text-xs font-medium text-ink">还没有 Case</p>
        <p className="mt-1 text-[10px] leading-5 text-ink-secondary">创建第一个问题后，它会出现在这里。</p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-line">
      {cases.map((item) => (
        <li key={item.id}>
          <Link href={`/cases/${item.id}`} className="group flex gap-3 px-4 py-3.5 transition-colors hover:bg-subtle">
            <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-control border border-line bg-surface text-ink-tertiary group-hover:text-brand">
              <Icon name="document" size={14} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-start justify-between gap-3">
                <span className="line-clamp-1 text-xs font-medium text-ink group-hover:text-brand">
                  {item.title}
                </span>
                <StatusBadge status={item.status} label={item.status_label} />
              </span>
              <span className="mt-1.5 flex items-center gap-2 text-[10px] text-ink-tertiary">
                <span>{formatRelative(item.updated_at)}</span>
                <span aria-hidden="true">·</span>
                <span className="truncate font-mono">{item.id}</span>
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
