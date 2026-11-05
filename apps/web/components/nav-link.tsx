"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { NavItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Icon, type IconName } from "./icons";

export function NavLink({ item, compact = false }: { item: NavItem; compact?: boolean }) {
  const pathname = usePathname();
  const active =
    pathname === item.href ||
    pathname.startsWith(`${item.href}/`) ||
    (item.key === "chat" && pathname.startsWith("/cases"));

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-2 rounded-control text-xs font-medium transition-colors duration-150",
        compact ? "h-9 shrink-0 px-3" : "h-14 border-b-2 px-0",
        active
          ? compact
            ? "bg-brand-soft text-brand"
            : "border-brand text-brand"
          : "border-transparent text-ink-secondary hover:text-ink"
      )}
    >
      <Icon name={item.icon as IconName} size={compact ? 15 : 16} />
      <span>{item.label}</span>
    </Link>
  );
}
