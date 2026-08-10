"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();
  // Navbar is now integrated into TopBar on cockpit page
  // This component handles agents/sovereign/settings pages
  if (pathname === "/") return null;

  return (
    <header style={{ height: 36, background: "var(--surface)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
      <Link href="/" style={{ display: "flex", alignItems: "center", gap: 6, textDecoration: "none" }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--neon-green)", boxShadow: "0 0 8px rgba(0,255,102,0.4)" }} />
        <span style={{ fontSize: 10, fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.1em" }}>JARVIS</span>
      </Link>
      <div style={{ display: "flex", gap: 2 }}>
        {[
          { href: "/", label: "CHAT" },
          { href: "/agents", label: "AGENTS" },
          { href: "/sovereign", label: "NETWORK" },
          { href: "/settings", label: "CONFIG" },
        ].map(item => (
          <Link key={item.href} href={item.href} style={{
            padding: "4px 10px", borderRadius: 3, fontSize: 9, fontWeight: 600, textDecoration: "none",
            fontFamily: "var(--font-mono)", letterSpacing: "0.08em", transition: "all 0.15s",
            background: pathname === item.href ? "var(--neon-green-dim)" : "transparent",
            color: pathname === item.href ? "var(--neon-green)" : "var(--text-muted)",
          }}>
            {item.label}
          </Link>
        ))}
      </div>
    </header>
  );
}
