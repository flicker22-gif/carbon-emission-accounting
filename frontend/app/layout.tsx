import Link from "next/link";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "碳排放核算工具",
  description: "GHG Protocol 范围一/二/三碳排放核算",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="site-header">
          <div className="container header-inner">
            <span className="logo">🌱 碳排放核算</span>
            <nav>
              <Link href="/">仪表盘</Link>
              <Link href="/records">数据录入</Link>
              <Link href="/facilities">厂区管理</Link>
              <Link href="/factors">排放因子</Link>
            </nav>
          </div>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
