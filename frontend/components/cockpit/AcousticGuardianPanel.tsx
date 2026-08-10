"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BASE, safeJson } from "@/lib/api";

interface AcousticEvent {
  event: string;
  timestamp: number;
  confidence: number;
  priority: string;
}

export default function AcousticGuardianPanel() {
  const [events, setEvents] = useState<AcousticEvent[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [enabled, setEnabled] = useState(true);

  const loadEvents = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/acoustic/events?limit=30`);
      const data = await safeJson(res);
      setEvents(data.events || []);
    } catch {}
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/acoustic/status`);
      const data = await safeJson(res);
      setStats(data);
      setEnabled(data.enabled !== false);
    } catch {}
  }, []);

  useEffect(() => { loadEvents(); loadStats(); }, [loadEvents, loadStats]);
  useEffect(() => {
    const i = setInterval(() => { loadEvents(); loadStats(); }, 5000);
    return () => clearInterval(i);
  }, [loadEvents, loadStats]);

  const toggleGuardian = async () => {
    const endpoint = enabled ? "disable" : "enable";
    try {
      await fetch(`${BASE}/api/acoustic/${endpoint === "enable" ? "events" : "events"}`, { method: "POST" });
      setEnabled(!enabled);
    } catch {}
  };

  const eventIcon: Record<string, string> = {
    glass_breaking: "💔", baby_crying: "👶", doorbell: "🔔",
    smoke_alarm: "🔥", dog_barking: "🐕", loud_noise: "📢",
    silence: "🤫", speech: "🗣️", music: "🎵",
  };

  const priorityColor: Record<string, string> = {
    critical: "#FF3333", high: "#FF6B35", medium: "#FFB300", low: "#00FF66",
  };

  return (
    <div style={{ background: "linear-gradient(135deg, #0d0f12 0%, #12151a 100%)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: enabled ? "#00FF66" : "#FF3333", boxShadow: `0 0 6px ${enabled ? "rgba(0,255,102,0.5)" : "rgba(255,51,51,0.4)"}`, animation: enabled ? "glow-pulse 1.5s ease-in-out infinite" : "none" }} />
          <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.08em" }}>ACOUSTIC_GUARDIAN</span>
        </div>
        <span style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: enabled ? "#00FF66" : "#FF3333" }}>
          {enabled ? "ACTIVE" : "DISABLED"}
        </span>
      </div>

      {/* Stats row */}
      {stats && (
        <div style={{ display: "flex", gap: 8, padding: "6px 12px", borderBottom: "1px solid var(--border)" }}>
          {[
            { label: "EVENTS", value: stats.total_events_detected || 0 },
            { label: "HOURLY", value: stats.hourly_alert_count || 0 },
            { label: "MONITORED", value: (stats.monitored_events || []).length },
          ].map(s => (
            <div key={s.label} style={{ flex: 1, textAlign: "center" }}>
              <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-primary)", fontWeight: 600 }}>{s.value}</div>
              <div style={{ fontSize: 6, fontFamily: "var(--font-mono)", color: "var(--text-muted)", letterSpacing: "0.08em" }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Monitored sounds */}
      {stats?.monitored_events && (
        <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.08em" }}>MONITORED SOUNDS</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
            {stats.monitored_events.map((event: string) => (
              <span key={event} style={{ padding: "2px 6px", borderRadius: 2, background: "var(--surface)", border: "1px solid var(--border)", fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                {eventIcon[event] || "🔊"} {event.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Events list */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {events.length === 0 ? (
          <div style={{ padding: 20, textAlign: "center", fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
            No sound events detected
          </div>
        ) : (
          events.map((event, i) => (
            <div key={i} style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12 }}>{eventIcon[event.event] || "🔊"}</span>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{event.event.replace(/_/g, " ")}</span>
                  <span style={{ fontSize: 7, padding: "1px 4px", borderRadius: 2, background: `${priorityColor[event.priority]}20`, border: `1px solid ${priorityColor[event.priority]}40`, color: priorityColor[event.priority], fontFamily: "var(--font-mono)" }}>
                    {event.priority}
                  </span>
                </div>
                <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                  confidence: {(event.confidence * 100).toFixed(0)}% · {new Date(event.timestamp * 1000).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
