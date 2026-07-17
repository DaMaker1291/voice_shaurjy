"use client";

import { useState, useEffect, useCallback } from "react";

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

interface InterceptAction {
  id: string;
  text: string;
  type: "script" | "device" | "network" | "file";
}

export default function InterceptBar({ onApprove, onDeny }: { onApprove: (id: string) => void; onDeny: (id: string) => void }) {
  const [pending, setPending] = useState<InterceptAction | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const checkPending = async () => {
      try {
        const res = await fetch("/api/sovereign/pending-actions");
        const data = await safeJson(res);
        if (data.actions?.length > 0) {
          setPending(data.actions[0]);
          setVisible(true);
        }
      } catch {}
    };
    const interval = setInterval(checkPending, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!visible || !pending) return;
    if (e.code === "Space") {
      e.preventDefault();
      onApprove(pending.id);
      setVisible(false);
      setPending(null);
    } else if (e.code === "Escape") {
      e.preventDefault();
      onDeny(pending.id);
      setVisible(false);
      setPending(null);
    }
  }, [visible, pending, onApprove, onDeny]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (!visible || !pending) return null;

  const typeIcon = { script: "📜", device: "🔌", network: "🌐", file: "📁" }[pending.type];

  return (
    <div className="animate-intercept" style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 1000,
      background: "var(--surface)", borderTop: "2px solid var(--crimson)",
      boxShadow: "var(--glow-crimson)",
    }}>
      {/* Diagonal stripe overlay */}
      <div className="intercept-overlay" style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />

      <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 20px", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--crimson)", boxShadow: "0 0 12px rgba(255,51,51,0.5)", animation: "glow-pulse 1s ease-in-out infinite" }} />
          <span style={{ fontSize: 10, color: "var(--crimson)", fontFamily: "var(--font-mono)", fontWeight: 700, letterSpacing: "0.1em" }}>INTERCEPT</span>
          <span style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>{typeIcon} {pending.type.toUpperCase()}</span>
        </div>

        <div style={{ flex: 1, fontSize: 11, color: "var(--text-primary)", fontFamily: "var(--font-mono)", textAlign: "center" }}>
          {pending.text}
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => { onApprove(pending.id); setVisible(false); setPending(null); }} style={{
            padding: "5px 14px", borderRadius: 4, fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
            background: "var(--neon-green-dim)", color: "var(--neon-green)", border: "1px solid rgba(0,255,102,0.2)",
            cursor: "pointer", letterSpacing: "0.05em", transition: "all 0.15s",
          }}>
            APPROVE [SPACE]
          </button>
          <button onClick={() => { onDeny(pending.id); setVisible(false); setPending(null); }} style={{
            padding: "5px 14px", borderRadius: 4, fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
            background: "var(--crimson-dim)", color: "var(--crimson)", border: "1px solid rgba(255,51,51,0.2)",
            cursor: "pointer", letterSpacing: "0.05em", transition: "all 0.15s",
          }}>
            DENY [ESC]
          </button>
        </div>
      </div>
    </div>
  );
}
