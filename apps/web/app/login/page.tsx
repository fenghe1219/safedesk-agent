import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { Icon } from "@/components/icons";
import { LoginForm } from "@/components/login-form";
import { getMe } from "@/lib/server-api";
import { DEMO_PASSWORD } from "@/lib/demo";

export const metadata: Metadata = { title: "登录" };

const CAPABILITIES = [
  "一个问题对应一条可追溯的 Case 主线",
  "检索依据、工单草稿和授权动作集中呈现",
  "审批、执行与审计保持同一条事实链"
];

export default async function LoginPage() {
  const me = await getMe();
  if (me) redirect(me.default_path);

  return (
    <main className="grid min-h-screen bg-canvas lg:grid-cols-[minmax(0,1fr)_minmax(420px,0.72fr)]">
      <section className="relative hidden overflow-hidden border-r border-line bg-[#edf4f1] px-12 py-10 lg:flex lg:flex-col">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-[9px] bg-brand text-sm font-semibold text-white shadow-card">
            S
          </span>
          <span className="text-base font-semibold tracking-[-0.01em] text-ink">SafeDesk</span>
        </div>

        <div className="my-auto max-w-[520px] pb-12">
          <p className="sd-eyebrow">企业服务台 Agent</p>
          <h1 className="mt-4 text-[34px] font-semibold leading-[1.25] tracking-[-0.025em] text-ink">
            把问题、依据和授权
            <br />
            收在同一条工作线上。
          </h1>
          <p className="mt-5 max-w-[440px] text-sm leading-7 text-ink-secondary">
            SafeDesk 面向员工、桌面支持与审批人，让每一次回答都有依据，每一次执行都可复核。
          </p>
          <ul className="mt-8 space-y-3">
            {CAPABILITIES.map((item) => (
              <li key={item} className="flex items-center gap-3 text-xs text-ink-secondary">
                <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full border border-brand-border bg-surface text-brand">
                  <Icon name="check" size={12} />
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-[10px] text-ink-tertiary">演示环境 · 仅使用合成数据</p>
        <div className="pointer-events-none absolute -right-28 top-24 h-64 w-64 rounded-full border border-brand-border" />
        <div className="pointer-events-none absolute -right-10 top-48 h-80 w-80 rounded-full border border-brand-border" />
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-[440px]">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <span className="grid h-8 w-8 place-items-center rounded-[9px] bg-brand text-sm font-semibold text-white">
              S
            </span>
            <span className="text-base font-semibold text-ink">SafeDesk</span>
          </div>

          <p className="sd-eyebrow">安全登录</p>
          <h2 className="mt-2 text-[24px] font-semibold tracking-[-0.02em] text-ink">进入工作台</h2>
          <p className="mt-2 text-xs leading-6 text-ink-secondary">
            M0 演示版已预置六类角色。选择账号后可使用统一密码 {DEMO_PASSWORD} 登录。
          </p>
          <div className="mt-7">
            <LoginForm />
          </div>
        </div>
      </section>
    </main>
  );
}
