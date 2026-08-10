"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BASE, safeJson } from "@/lib/api";

export default function EnvironmentSyncPanel() {
  const [state, setState] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadState = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/environment/status`);
      setState(await safeJson(res));
    } catch {}
  }, []);

  useEffect(() => { loadState(); }, [loadState]);
  useEffect(() => {
    const i = setInterval(loadState, 10000);
    return () => clearInterval(i);
  }, [loadState]);

  const checkTriggers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/api/environment/check`, { method: "POST" });
      const data = await safeJson(res);
      if (data.actions?.length > 0) {
        for (const action of data.actions) {
          await fetch(`${BASE}/api/environment/execute`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(action),
          });
        }
      }
      loadState();
    } catch {}
    setLoading(false);
  };

  const stateColor: Record<string, string> = {
    idle: "#667085", meeting: "#FF3333", focus: "#FFB300",
    night: "#7C3AED", away: "#667085", active: "#00FF66",
  };

  return (
    <div style={{ background: "linear-gradient(135deg, #0d0f12 0%, #12151a 100%)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: stateColor[state?.state] || "#667085", boxShadow: `0 0 6px ${stateColor[state?.state] || "#667085"}60` }} />
          <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.08em" }}>ENVIRONMENT_SYNC</span>
        </div>
        <span style={{ fontSize: 7, padding: "1px 6px", borderRadius: 3, background: `${stateColor[state?.state]}20`, border: `1px solid ${stateColor[state?.state]}40`, color: stateColor[state?.state], fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>
          {state?.state || "unknown"}
        </span>
      </div>

      {/* Status grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
        {[
          { label: "IN MEETING", value: state?.in_meeting ? "YES" : "NO", color: state?.in_meeting ? "#FF3333" : "#00FF66" },
          { label: "IDLE TIME", value: `${state?.idle_minutes || 0}m`, color: (state?.idle_minutes || 0) > 30 ? "#FFB300" : "#00FF66" },
          { label: "ACTIVE APPS", value: state?.active_apps?.length || 0, color: "#00B4D8" },
          { label: "RULES ACTIVE", value: state?.rules_enabled || 0, color: "#7C3AED" },
        ].map(item => (
          <div key={item.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: item.color, fontWeight: 600 }}>{item.value}</div>
            <div style={{ fontSize: 6, fontFamily: "var(--font-mono)", color: "var(--text-muted)", letterSpacing: "0.08em" }}>{item.label}</div>
          </div>
        ))}
      </div>

      {/* Active apps */}
      {state?.active_apps?.length > 0 && (
        <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.08em" }}>ACTIVE WINDOWS</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {state.active_apps.map((app: string, i: number) => (
              <span key={i} style={{ padding: "2px 6px", borderRadius: 2, background: "var(--surface)", border: "1px solid var(--border)", fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--neon-green)" }}>
                {app}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recent actions */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        <div style={{ padding: "6px 12px" }}>
          <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.08em" }}>RECENT ACTIONS</div>
          {(state?.recent_actions || []).length === 0 ? (
            <div style={{ fontSize: 8, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>No actions executed yet</div>
          ) : (
            state.recent_actions.map((action: any, i: number) => (
              <div key={i} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: action.success ? "#00FF66" : "#FF3333", flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: 8, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{action.type}</span>
                  <span style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginLeft: 6 }}>{action.value}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Manual check button */}
      <div style={{ padding: "6px 12px", borderTop: "1px solid var(--border)" }}>
        <button onClick={checkTriggers} disabled={loading} style={{
          width: "100%", padding: "4px 0", borderRadius: 3, fontSize: 8, fontFamily: "var(--font-mono)",
          background: "var(--neon-green-dim)", border: "1px solid rgba(0,255,102,0.2)",
          color: "var(--neon-green)", cursor: "pointer", opacity: loading ? 0.5 : 1,
        }}>
          {loading ? "CHECKING..." : "CHECK TRIGGERS NOW"}
        </button>
      </div>
    </div>
  );
}
