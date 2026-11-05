import Link from "next/link";
import type { ReactNode } from "react";

import type { MeResponse } from "@/lib/types";
import { DemoSwitcher } from "./demo-switcher";
import { Icon } from "./icons";
import { LogoutButton } from "./logout-button";
import { NavLink } from "./nav-link";

export function AppShell({ me, children }: { me: MeResponse; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-20 border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-6 px-4 md:px-6">
          <Link href={me.default_path} className="flex shrink-0 items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center rounded-[8px] bg-brand text-[13px] font-semibold text-white shadow-card">
              S
            </span>
            <span className="text-[15px] font-semibold tracking-[-0.01em] text-ink">SafeDesk</span>
          </Link>

          <nav className="hidden h-full items-center gap-6 md:flex" aria-label="主导航">
            {me.navigation.map((item) => (
              <NavLink key={item.key} item={item} />
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <DemoSwitcher
              currentRole={me.user.role}
              csrfToken={me.csrf_token}
              demoMode={me.demo_mode}
            />
            <span className="hidden rounded-full border border-line px-2.5 py-[3px] text-[10px] text-ink-secondary lg:inline">
              {me.user.role_label}
            </span>
            <div className="flex items-center gap-2 text-xs text-ink-secondary">
              <span className="hidden sm:inline">{me.user.name}</span>
              <span className="grid h-7 w-7 place-items-center rounded-full bg-brand-soft text-[11px] font-semibold text-brand">
                {me.user.name.slice(0, 1)}
              </span>
            </div>
            <LogoutButton csrfToken={me.csrf_token} />
          </div>
        </div>

        <nav className="flex gap-2 overflow-x-auto border-t border-line px-4 py-2 md:hidden" aria-label="移动端导航">
          {me.navigation.map((item) => (
            <NavLink key={item.key} item={item} compact />
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-[1440px] px-4 py-6 md:px-6 md:py-8">{children}</main>
    </div>
  );
}
