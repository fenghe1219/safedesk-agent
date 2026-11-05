import { cn } from "@/lib/utils";

const PHASES = [
  { key: "intake", label: "受理", description: "理解问题" },
  { key: "retrieval", label: "查证", description: "查找依据" },
  { key: "solution", label: "方案", description: "回答或转单" },
  { key: "approval", label: "审批与执行", description: "授权与回滚" },
  { key: "done", label: "完成", description: "结果与复盘" }
] as const;

export function CaseProgress({ phase }: { phase: string }) {
  const activeIndex = Math.max(0, PHASES.findIndex((item) => item.key === phase));

  return (
    <ol className="grid grid-cols-5 gap-2" aria-label="Case 阶段">
      {PHASES.map((item, index) => {
        const complete = index < activeIndex;
        const active = index === activeIndex;
        return (
          <li key={item.key} className="min-w-0">
            <div
              className={cn(
                "h-1 rounded-full",
                complete || active ? "bg-brand" : "bg-line"
              )}
            />
            <div className="mt-2.5 flex items-start gap-2">
              <span
                className={cn(
                  "mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full border text-[9px] font-semibold",
                  active
                    ? "border-brand bg-brand text-white"
                    : complete
                      ? "border-brand bg-brand-soft text-brand"
                      : "border-line bg-surface text-ink-tertiary"
                )}
                aria-current={active ? "step" : undefined}
              >
                {complete ? "✓" : index + 1}
              </span>
              <span className="min-w-0">
                <span
                  className={cn(
                    "block truncate text-[11px] font-medium",
                    active ? "text-brand" : complete ? "text-ink" : "text-ink-tertiary"
                  )}
                >
                  {item.label}
                </span>
                <span className="hidden truncate text-[9px] text-ink-tertiary sm:block">
                  {item.description}
                </span>
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
