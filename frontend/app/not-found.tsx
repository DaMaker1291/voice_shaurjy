"use client";

import Link from "next/link";

export default function NotFound() {
  return (
    <div style={{
      height: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace",
      position: "relative",
    }}>
      {/* Background grid */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", opacity: 0.3,
        backgroundImage: "linear-gradient(rgba(0,255,102,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,102,0.03) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      <style jsx>{`
        @keyframes float { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-8px); } }
        .fl { animation: float 3s ease-in-out infinite; }
      `}</style>

      <div style={{ textAlign: "center", position: "relative", zIndex: 1 }}>
        <div className="fl" style={{ fontSize: 72, marginBottom: 16, opacity: 0.15 }}>404</div>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Lost in the Network</div>
        <div style={{ fontSize: 11, color: "#667085", marginBottom: 24, maxWidth: 320, lineHeight: 1.6 }}>
          This page doesn't exist in JARVIS's sovereign network.
          <br />Let me guide you back.
        </div>
        <Link href="/" style={{
          padding: "10px 24px", borderRadius: 6, fontSize: 11, fontWeight: 600,
          fontFamily: "inherit", textDecoration: "none",
          background: "#00FF66", color: "#030303",
          display: "inline-block", letterSpacing: "0.08em",
        }}>
          RETURN TO JARVIS →
        </Link>
      </div>
    </div>
  );
}
