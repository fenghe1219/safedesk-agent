import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  NEW: "bg-subtle text-ink-secondary",
  UNDERSTANDING: "bg-brand-soft text-brand",
  RETRIEVING: "bg-info-soft text-info",
  DIAGNOSING: "bg-info-soft text-info",
  NEEDS_INPUT: "bg-warning-soft text-warning",
  ANSWERED: "bg-success-soft text-success",
  TICKET_DRAFT: "bg-warning-soft text-warning",
  TICKET_OPEN: "bg-success-soft text-success",
  ACTION_PROPOSED: "bg-warning-soft text-warning",
  AWAITING_APPROVAL: "bg-warning-soft text-warning",
  EXECUTING: "bg-brand-soft text-brand",
  REJECTED: "bg-danger-soft text-danger",
  EXPIRED: "bg-danger-soft text-danger",
  RESOLVED: "bg-success-soft text-success",
  FAILED: "bg-danger-soft text-danger",
  CANCELLED: "bg-subtle text-ink-tertiary",
  REFUSED: "bg-danger-soft text-danger"
};

const DOT_STYLES: Record<string, string> = {
  NEW: "bg-ink-tertiary",
  UNDERSTANDING: "bg-brand",
  RETRIEVING: "bg-info",
  DIAGNOSING: "bg-info",
  NEEDS_INPUT: "bg-warning",
  ANSWERED: "bg-success",
  TICKET_DRAFT: "bg-warning",
  TICKET_OPEN: "bg-success",
  ACTION_PROPOSED: "bg-warning",
  AWAITING_APPROVAL: "bg-warning",
  EXECUTING: "bg-brand",
  REJECTED: "bg-danger",
  EXPIRED: "bg-danger",
  RESOLVED: "bg-success",
  FAILED: "bg-danger",
  CANCELLED: "bg-ink-tertiary",
  REFUSED: "bg-danger"
};

export function StatusBadge({ status, label }: { status: string; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium",
        STATUS_STYLES[status] ?? "bg-subtle text-ink-secondary"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_STYLES[status] ?? "bg-ink-tertiary")} />
      {label}
    </span>
  );
}
