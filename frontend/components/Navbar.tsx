"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();

  // Hide navbar on standalone pages (they have their own headers)
  if (pathname === "/sovereign" || pathname === "/agents") return null;

  return (
    <header style={{ borderBottom: "1px solid var(--border-subtle)", background: "rgba(9,9,11,0.85)", backdropFilter: "blur(20px) saturate(180%)" }}>
      <div style={{ maxWidth: 1400, margin: "0 auto", padding: "0 24px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: "var(--accent-dim)", border: "1px solid rgba(139,92,246,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <span style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "-0.01em" }}>JARVIS</span>
        </Link>

        <nav style={{ display: "flex", gap: 4 }}>
          <Link href="/" style={{
            padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 500, textDecoration: "none", transition: "all 0.15s",
            background: pathname === "/" ? "var(--accent-dim)" : "transparent",
            color: pathname === "/" ? "var(--accent)" : "var(--text-muted)",
            border: pathname === "/" ? "1px solid rgba(139,92,246,0.15)" : "1px solid transparent",
          }}>
            Chat
          </Link>
          <Link href="/agents" style={{
            padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 500, textDecoration: "none", transition: "all 0.15s",
            background: pathname === "/agents" ? "var(--accent-dim)" : "transparent",
            color: pathname === "/agents" ? "var(--accent)" : "var(--text-muted)",
            border: pathname === "/agents" ? "1px solid rgba(139,92,246,0.15)" : "1px solid transparent",
          }}>
            Agents
          </Link>
          <Link href="/sovereign" style={{
            padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 500, textDecoration: "none", transition: "all 0.15s",
            background: pathname === "/sovereign" ? "var(--accent-dim)" : "transparent",
            color: pathname === "/sovereign" ? "var(--accent)" : "var(--text-muted)",
            border: pathname === "/sovereign" ? "1px solid rgba(139,92,246,0.15)" : "1px solid transparent",
          }}>
            Network
          </Link>
        </nav>
      </div>
    </header>
  );
}
