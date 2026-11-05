import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "SafeDesk",
    template: "%s | SafeDesk"
  },
  description: "可审计、可评估、可人工接管的企业服务台 Agent 工作台"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
