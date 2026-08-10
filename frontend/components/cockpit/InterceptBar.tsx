"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { BASE } from "@/lib/api";

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

interface InterceptAction {
  action_id: string;
  action_type: string;
  risk_level: string;
  description: string;
  payload_summary: string;
  expires_in_s: number;
  diff_preview?: any;
}

export default function InterceptBar({ onApprove, onDeny }: { onApprove: (id: string) => void; onDeny: (id: string) => void }) {
  const [pending, setPending] = useState<InterceptAction | null>(null);
  const [visible, setVisible] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const holdTimerRef = useRef<NodeJS.Timeout | null>(null);
  const holdStartRef = useRef<number>(0);
  const HOLD_DURATION = 1500; // 1.5 seconds

  useEffect(() => {
    const checkPending = async () => {
      try {
        const res = await fetch(`${BASE}/api/laser-gate/pending`);
        const data = await safeJson(res);
        if (data.actions?.length > 0) {
          setPending(data.actions[0]);
          setVisible(true);
        } else {
          setVisible(false);
          setPending(null);
        }
      } catch {}
    };
    const interval = setInterval(checkPending, 2000);
    return () => clearInterval(interval);
  }, []);

  const startHold = useCallback(() => {
    holdStartRef.current = Date.now();
    setHoldProgress(0);

    holdTimerRef.current = setInterval(() => {
      const elapsed = Date.now() - holdStartRef.current;
      const progress = Math.min(elapsed / HOLD_DURATION, 1);
      setHoldProgress(progress);

      if (progress >= 1) {
        if (holdTimerRef.current) clearInterval(holdTimerRef.current);
        if (pending) {
          onApprove(pending.action_id);
          fetch(`${BASE}/api/laser-gate/approve/${pending.action_id}`, { method: "POST" });
        }
        setVisible(false);
        setPending(null);
        setHoldProgress(0);
      }
    }, 16);
  }, [pending, onApprove]);

  const cancelHold = useCallback(() => {
    if (holdTimerRef.current) {
      clearInterval(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    setHoldProgress(0);
  }, []);

  useEffect(() => {
    return () => { if (holdTimerRef.current) clearInterval(holdTimerRef.current); };
  }, []);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!visible || !pending) return;
    if (e.code === "Space" && holdProgress === 0) {
      e.preventDefault();
      startHold();
    } else if (e.code === "Escape") {
      e.preventDefault();
      cancelHold();
      if (pending) {
        onDeny(pending.action_id);
        fetch(`${BASE}/api/laser-gate/deny/${pending.action_id}`, { method: "POST" });
      }
      setVisible(false);
      setPending(null);
    }
  }, [visible, pending, holdProgress, startHold, cancelHold, onDeny]);

  const handleKeyUp = useCallback((e: KeyboardEvent) => {
    if (e.code === "Space" && holdProgress > 0 && holdProgress < 1) {
      cancelHold();
    }
  }, [holdProgress, cancelHold]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [handleKeyDown, handleKeyUp]);

  if (!visible || !pending) return null;

  const riskColor: Record<string, string> = {
    critical: "#FF3333", high: "#FF6B35", medium: "#FFB300",
  };
  const color = riskColor[pending.risk_level] || "#FF3333";

  return (
    <div className="animate-intercept" style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 1000,
      background: "var(--surface)", borderTop: `3px solid ${color}`,
      boxShadow: `0 0 30px ${color}40, 0 -4px 20px rgba(0,0,0,0.5)`,
    }}>
      {/* Crimson diagonal stripe overlay */}
      <div className="intercept-overlay" style={{ position: "absolute", inset: 0, pointerEvents: "none" }} />

      {/* Hold progress bar */}
      {holdProgress > 0 && (
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: "var(--border)" }}>
          <div style={{ height: "100%", width: `${holdProgress * 100}%`, background: `linear-gradient(90deg, ${color}, #00FF66)`, transition: "width 0.016s linear" }} />
        </div>
      )}

      <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 20px", gap: 16 }}>
        {/* Left: Risk indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 180 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: color, boxShadow: `0 0 16px ${color}80`, animation: "glow-pulse 1s ease-in-out infinite" }} />
          <div>
            <div style={{ fontSize: 10, color: color, fontFamily: "var(--font-mono)", fontWeight: 700, letterSpacing: "0.1em" }}>LASER GATE</div>
            <div style={{ fontSize: 8, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              {pending.risk_level.toUpperCase()} RISK · {pending.action_type.replace(/_/g, " ").toUpperCase()}
            </div>
          </div>
        </div>

        {/* Center: Description */}
        <div style={{ flex: 1, fontSize: 11, color: "var(--text-primary)", fontFamily: "var(--font-mono)", textAlign: "center" }}>
          {pending.description}
          {pending.payload_summary && (
            <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>{pending.payload_summary}</div>
          )}
        </div>

        {/* Right: Hold to approve / Deny */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 280, justifyContent: "flex-end" }}>
          {/* Hold-spacebar-to-approve button */}
          <button
            onMouseDown={startHold}
            onMouseUp={cancelHold}
            onMouseLeave={cancelHold}
            style={{
              padding: "6px 18px", borderRadius: 4, fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
              background: holdProgress > 0 ? `rgba(0,255,102,${0.1 + holdProgress * 0.3})` : "var(--neon-green-dim)",
              color: "var(--neon-green)", border: "1px solid rgba(0,255,102,0.3)",
              cursor: "pointer", letterSpacing: "0.05em", transition: "all 0.15s",
              position: "relative", overflow: "hidden",
            }}
          >
            {holdProgress > 0 ? `HOLD... ${Math.round(holdProgress * 100)}%` : "HOLD SPACEBAR TO APPROVE"}
          </button>

          <button onClick={() => {
            cancelHold();
            if (pending) {
              onDeny(pending.action_id);
              fetch(`${BASE}/api/laser-gate/deny/${pending.action_id}`, { method: "POST" });
            }
            setVisible(false);
            setPending(null);
          }} style={{
            padding: "6px 14px", borderRadius: 4, fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600,
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
