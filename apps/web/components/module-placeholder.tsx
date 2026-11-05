import Link from "next/link";

import { Icon, type IconName } from "./icons";

export function ModulePlaceholder({
  eyebrow,
  title,
  description,
  icon,
  emptyTitle,
  emptyDescription,
  primaryHref = "/chat",
  primaryLabel = "返回工作台",
  milestones
}: {
  eyebrow: string;
  title: string;
  description: string;
  icon: IconName;
  emptyTitle: string;
  emptyDescription: string;
  primaryHref?: string;
  primaryLabel?: string;
  milestones: string[];
}) {
  return (
    <div className="mx-auto max-w-[1100px]">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="sd-eyebrow">{eyebrow}</p>
          <h1 className="sd-page-title mt-1">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-secondary">{description}</p>
        </div>
        <span className="sd-chip">M0 骨架</span>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.65fr)]">
        <section className="sd-card flex min-h-80 flex-col items-center justify-center px-6 py-12 text-center">
          <span className="grid h-12 w-12 place-items-center rounded-overlay border border-brand-border bg-brand-soft text-brand">
            <Icon name={icon} size={22} />
          </span>
          <h2 className="mt-5 text-base font-semibold text-ink">{emptyTitle}</h2>
          <p className="mt-2 max-w-md text-xs leading-6 text-ink-secondary">{emptyDescription}</p>
          <Link href={primaryHref} className="sd-button-secondary mt-5">
            {primaryLabel}
            <Icon name="arrow-right" size={14} />
          </Link>
        </section>

        <aside className="sd-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">后续交付</h2>
            <Icon name="branch" size={16} className="text-ink-tertiary" />
          </div>
          <ol className="mt-4 space-y-3">
            {milestones.map((item, index) => (
              <li key={item} className="flex gap-3">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-subtle text-[10px] font-semibold text-ink-secondary">
                  {index + 1}
                </span>
                <span className="text-xs leading-5 text-ink-secondary">{item}</span>
              </li>
            ))}
          </ol>
          <div className="mt-5 rounded-control border border-line bg-subtle px-3 py-2.5 text-[10px] leading-5 text-ink-tertiary">
            M0 只建立工程、权限和 Case 骨架。业务流程将在 M1–M4 逐步接入。
          </div>
        </aside>
      </div>
    </div>
  );
}
