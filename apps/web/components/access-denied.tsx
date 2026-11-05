import Link from "next/link";

import type { MeResponse } from "@/lib/types";
import { Icon } from "./icons";

export function AccessDenied({ me, detail }: { me: MeResponse; detail?: string }) {
  return (
    <div className="mx-auto max-w-[640px] pt-12">
      <div className="sd-card px-8 py-10 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-overlay border border-warning bg-warning-soft text-warning">
          <Icon name="lock" size={22} />
        </span>
        <h1 className="mt-5 text-lg font-semibold text-ink">当前角色没有访问权限</h1>
        <p className="mt-2 text-xs leading-6 text-ink-secondary">
          {detail ?? `你当前以「${me.user.role_label}」身份登录，无法打开这个页面。`}
        </p>
        <Link href={me.default_path} className="sd-button-secondary mt-6">
          返回我的工作区
          <Icon name="arrow-right" size={14} />
        </Link>
      </div>
    </div>
  );
}
