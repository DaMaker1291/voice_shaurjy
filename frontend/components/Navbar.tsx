"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();

  // Hide on standalone pages (they have their own headers)
  if (pathname === "/sovereign" || pathname === "/agents") return null;

  return (
    <header style={{ borderBottom: "1px solid var(--border-subtle)", background: "rgba(9,9,11,0.85)", backdropFilter: "blur(20px) saturate(180%)" }}>
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "0 20px", height: 52, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          <div style={{ width: 28, height: 28, borderRadius: 7, background: "var(--accent-dim)", border: "1px solid rgba(139,92,246,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>JARVIS</span>
        </Link>
        <div style={{ display: "flex", gap: 2 }}>
          {[
            { href: "/", label: "Chat" },
            { href: "/agents", label: "Agents" },
            { href: "/sovereign", label: "Network" },
          ].map(item => (
            <Link key={item.href} href={item.href} style={{
              padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 500, textDecoration: "none", transition: "all 0.15s",
              background: pathname === item.href ? "var(--accent-dim)" : "transparent",
              color: pathname === item.href ? "var(--accent)" : "var(--text-muted)",
            }}>
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </header>
  );
}
