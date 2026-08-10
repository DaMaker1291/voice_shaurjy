"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BASE, safeJson } from "@/lib/api";

export default function WakeWordIndicator() {
  const [status, setStatus] = useState<any>(null);
  const [detected, setDetected] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/wakeword/status`);
      setStatus(await safeJson(res));
    } catch {}
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);
  useEffect(() => {
    const i = setInterval(loadStatus, 5000);
    return () => clearInterval(i);
  }, [loadStatus]);

  const toggleWakeWord = async () => {
    const endpoint = status?.enabled ? "disable" : "enable";
    try {
      await fetch(`${BASE}/api/wakeword/${endpoint}`, { method: "POST" });
      loadStatus();
    } catch {}
  };

  const updateSensitivity = async (val: number) => {
    try {
      await fetch(`${BASE}/api/wakeword/sensitivity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sensitivity: val }),
      });
      loadStatus();
    } catch {}
  };

  if (!status) return null;

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "6px 12px", borderRadius: 6,
      background: status.enabled ? "rgba(0,255,102,0.04)" : "rgba(255,51,51,0.04)",
      border: `1px solid ${status.enabled ? "rgba(0,255,102,0.15)" : "rgba(255,51,51,0.15)"}`,
    }}>
      {/* Mic icon with pulse */}
      <div style={{ position: "relative", width: 16, height: 16 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={status.enabled ? "#00FF66" : "#FF3333"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
        {status.enabled && (
          <div style={{
            position: "absolute", inset: -4, borderRadius: "50%",
            border: `1px solid rgba(0,255,102,${detected ? "0.6" : "0.2"})`,
            animation: detected ? "glow-pulse 0.5s ease-in-out" : "glow-pulse 2s ease-in-out infinite",
          }} />
        )}
      </div>

      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 8, fontFamily: "var(--font-mono)", color: status.enabled ? "#00FF66" : "#FF3333", fontWeight: 600, letterSpacing: "0.08em" }}>
            WAKE_WORD
          </span>
          <span style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
            "{status.wake_phrase}"
          </span>
        </div>
        <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginTop: 2 }}>
          engines: {status.engines?.join(", ")}
        </div>
      </div>

      <button onClick={toggleWakeWord} style={{
        padding: "3px 8px", borderRadius: 3, fontSize: 7, fontFamily: "var(--font-mono)",
        background: status.enabled ? "rgba(0,255,102,0.1)" : "rgba(255,51,51,0.1)",
        border: `1px solid ${status.enabled ? "rgba(0,255,102,0.2)" : "rgba(255,51,51,0.2)"}`,
        color: status.enabled ? "#00FF66" : "#FF3333", cursor: "pointer",
      }}>
        {status.enabled ? "ON" : "OFF"}
      </button>
    </div>
  );
}
