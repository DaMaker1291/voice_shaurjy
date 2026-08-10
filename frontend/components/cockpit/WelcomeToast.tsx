"use client";

import { useEffect, useState } from "react";
import { modKey } from "@/hooks/useModKey";

export default function WelcomeToast() {
  const [show, setShow] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const mod = modKey();

  useEffect(() => {
    const seen = sessionStorage.getItem("jarvis-welcome-seen");
    if (!seen) {
      setTimeout(() => setShow(true), 1500);
      setTimeout(() => { setShow(false); sessionStorage.setItem("jarvis-welcome-seen", "1"); }, 8000);
    }
  }, []);

  if (dismissed || !show) return null;

  return (
    <div
      onClick={() => { setDismissed(true); sessionStorage.setItem("jarvis-welcome-seen", "1"); }}
      style={{
        position: "fixed", bottom: 48, left: "50%", transform: "translateX(-50%)",
        zIndex: 9999, cursor: "pointer",
        padding: "12px 20px", borderRadius: 8,
        background: "linear-gradient(135deg, #0d0f12 0%, #12151a 100%)",
        border: "1px solid rgba(0,255,102,0.2)",
        boxShadow: "0 0 30px rgba(0,255,102,0.1), 0 8px 32px rgba(0,0,0,0.6)",
        display: "flex", alignItems: "center", gap: 12,
        animation: "toast-in 0.4s cubic-bezier(0.16,1,0.3,1) both",
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      <style jsx>{`
        @keyframes toast-in { from { opacity:0; transform:translateX(-50%) translateY(16px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }
      `}</style>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 8px rgba(0,255,102,0.5)" }} />
      <div>
        <div style={{ fontSize: 11, color: "#e5e5e5", fontWeight: 500 }}>Welcome to JARVIS</div>
        <div style={{ fontSize: 9, color: "#667085", marginTop: 2 }}>Press <span style={{ color: "#00FF66" }}>{mod}K</span> for commands · <span style={{ color: "#00FF66" }}>{mod}⇧?</span> for shortcuts</div>
      </div>
      <span style={{ fontSize: 8, color: "#667085", marginLeft: 8 }}>✕</span>
    </div>
  );
}
