"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();

  // Hide navbar on sovereign and agents pages
  if (pathname === "/sovereign" || pathname === "/agents") return null;

  return (
    <header style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "rgba(10,10,15,0.95)", backdropFilter: "blur(20px)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", height: 48, padding: "0 20px" }}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          <div style={{ width: 28, height: 28, borderRadius: 6, background: "rgba(139,92,246,0.1)", border: "1px solid rgba(139,92,246,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: "#fafafa" }}>JARVIS</span>
        </Link>

        <nav style={{ display: "flex", gap: 4 }}>
          <Link href="/" style={{
            padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 500, textDecoration: "none",
            background: pathname === "/" ? "rgba(139,92,246,0.1)" : "transparent",
            color: pathname === "/" ? "#a78bfa" : "#52525b",
            border: pathname === "/" ? "1px solid rgba(139,92,246,0.2)" : "1px solid transparent",
          }}>
            Chat
          </Link>
          <Link href="/agents" style={{
            padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 500, textDecoration: "none",
            background: pathname === "/agents" ? "rgba(139,92,246,0.1)" : "transparent",
            color: pathname === "/agents" ? "#a78bfa" : "#52525b",
            border: pathname === "/agents" ? "1px solid rgba(139,92,246,0.2)" : "1px solid transparent",
          }}>
            Agents
          </Link>
          <Link href="/sovereign" style={{
            padding: "6px 14px", borderRadius: 6, fontSize: 12, fontWeight: 500, textDecoration: "none",
            background: pathname === "/sovereign" ? "rgba(139,92,246,0.1)" : "transparent",
            color: pathname === "/sovereign" ? "#a78bfa" : "#52525b",
            border: pathname === "/sovereign" ? "1px solid rgba(139,92,246,0.2)" : "1px solid transparent",
          }}>
            Network
          </Link>
        </nav>
      </div>
    </header>
  );
}
