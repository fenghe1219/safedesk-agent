import Link from "next/link";

import { Icon } from "@/components/icons";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-5">
      <div className="sd-card w-full max-w-[520px] px-8 py-10 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-overlay border border-line bg-subtle text-ink-tertiary">
          <Icon name="search" size={22} />
        </span>
        <p className="mt-5 font-mono text-[10px] text-brand">404 / NOT FOUND</p>
        <h1 className="mt-2 text-lg font-semibold text-ink">没有找到这个页面</h1>
        <p className="mt-2 text-xs leading-6 text-ink-secondary">
          页面不存在，或当前账号无权访问该对象。服务端不会通过存在性提示泄露资源信息。
        </p>
        <Link href="/" className="sd-button-secondary mt-6">
          返回工作区
          <Icon name="arrow-right" size={14} />
        </Link>
      </div>
    </main>
  );
}
