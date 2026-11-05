"use client";

import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-5">
      <div className="sd-card w-full max-w-[520px] px-8 py-10 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-overlay border border-danger-soft bg-danger-soft text-danger">
          !
        </span>
        <h1 className="mt-5 text-lg font-semibold text-ink">页面加载失败</h1>
        <p className="mt-2 text-xs leading-6 text-ink-secondary">
          服务可能暂时不可用。可以重试；若问题持续，请将请求信息交给管理员。
        </p>
        {error.digest && <p className="mt-2 font-mono text-[10px] text-ink-tertiary">请求 {error.digest}</p>}
        <button type="button" onClick={reset} className="sd-button-primary mt-6">
          重新尝试
        </button>
      </div>
    </main>
  );
}
