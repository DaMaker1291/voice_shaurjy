"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { modKey } from "@/hooks/useModKey";

async function safeJson(res: Response): Promise<any> {
  if (!res.ok) return null;
  const text = await res.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return null; }
}

const API = "";

interface FeedItem {
  id: string;
  type: "email" | "flight" | "calendar" | "notification" | "device" | "system";
  title: string;
  summary: string;
  time: string;
  priority: "high" | "medium" | "low";
  action?: string;
  source?: string;
}

export default function FeedPage() {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [scanning, setScanning] = useState(false);
  const [selectedItem, setSelectedItem] = useState<string | null>(null);

  // Generate feed from system state
  const fetchFeed = useCallback(async () => {
    const feed: FeedItem[] = [];

    // System events
    try {
      const res = await fetch(`${API}/api/health`);
      const data = await safeJson(res);
      feed.push({
        id: "sys-health", type: "system", title: "System Health",
        summary: `Relay: ${data.relay ? "Online" : "Offline"} | Model: ${data.models?.llm || "GROQ"}`,
        time: new Date().toLocaleTimeString(), priority: "low", source: "JARVIS Core",
      });
    } catch {}

    // Device events
    try {
      const res = await fetch(`${API}/api/relay/devices?user_id=local`);
      const data = await safeJson(res);
      const devices = data.devices || [];
      if (devices.length > 0) {
        feed.push({
          id: "dev-count", type: "device", title: "Devices Connected",
          summary: `${devices.length} devices on your network: ${devices.map((d: any) => d.name).join(", ")}`,
          time: new Date().toLocaleTimeString(), priority: "medium", source: "Network Scanner",
        });
      }
    } catch {}

    // Task events
    try {
      const res = await fetch(`${API}/api/autonomous/tasks`);
      const data = await safeJson(res);
      const tasks = data.tasks || [];
      tasks.forEach((t: any) => {
        feed.push({
          id: `task-${t.task_id}`, type: t.status === "running" ? "notification" : "system",
          title: t.status === "running" ? `Running: ${t.intent}` : `Completed: ${t.intent}`,
          summary: `Step ${t.current_step + 1}/${t.total_steps || "?"} • ${t.status}`,
          time: new Date().toLocaleTimeString(),
          priority: t.status === "running" ? "high" : "low",
          source: "Autonomous Agent",
        });
      });
    } catch {}

    // Add some contextual suggestions
    const hour = new Date().getHours();
    if (hour >= 6 && hour < 9) {
      feed.push({
        id: "morning", type: "calendar", title: "Morning Routine",
        summary: "Good morning! Want me to check your email, scan for flights, or read the news?",
        time: "Now", priority: "medium", source: "JARVIS",
        action: "check email for flights",
      });
    }
    if (hour >= 17 && hour < 20) {
      feed.push({
        id: "evening", type: "calendar", title: "Evening Summary",
        summary: "Want me to summarize your day, check tomorrow's schedule, or control your lights?",
        time: "Now", priority: "medium", source: "JARVIS",
        action: "summarize my day",
      });
    }

    feed.push({
      id: "tip", type: "notification", title: "Quick Tip",
      summary: `Press ${modKey()}K to open the command palette for instant access to any feature.`,
      time: "Now", priority: "low", source: "JARVIS",
    });

    setItems(feed.sort((a, b) => {
      const p = { high: 0, medium: 1, low: 2 };
      return p[a.priority] - p[b.priority];
    }));
  }, []);

  useEffect(() => { fetchFeed(); }, [fetchFeed]);
  useEffect(() => {
    const i = setInterval(fetchFeed, 10000);
    return () => clearInterval(i);
  }, [fetchFeed]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await fetch(`${API}/api/relay/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: "universal_scan", params: "", user_id: "local" }),
      });
      setTimeout(fetchFeed, 3000);
    } catch {}
    setScanning(false);
  };

  const handleAction = async (action: string) => {
    try {
      await fetch(`${API}/api/entity/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: action, user_id: "local", session_id: "feed" }),
      });
    } catch {}
  };

  const filtered = filter === "all" ? items : items.filter(i => i.type === filter);

  const typeColors: Record<string, string> = {
    email: "#00B4D8", flight: "#FFB300", calendar: "#A855F7",
    notification: "#00FF66", device: "#F97316", system: "#667085",
  };

  const typeIcons: Record<string, string> = {
    email: "📧", flight: "✈️", calendar: "📅",
    notification: "🔔", device: "📡", system: "⚙️",
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        .af { animation: fade-in 0.25s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Header */}
      <header style={{ height: 40, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
          <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
          <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>DATA FEED</span>
          <span style={{ fontSize: 9, color: "#667085" }}>{items.length} items</span>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          style={{
            padding: "5px 12px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
            cursor: "pointer", background: scanning ? "#1a1d23" : "rgba(0,255,102,0.1)",
            color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)",
          }}
        >
          {scanning ? "SCANNING..." : "REFRESH"}
        </button>
      </header>

      {/* Filters */}
      <div style={{ display: "flex", gap: 4, padding: "8px 16px", borderBottom: "1px solid #1a1d23", overflow: "auto" }}>
        {["all", "email", "flight", "calendar", "notification", "device", "system"].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "4px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit", cursor: "pointer",
            background: filter === f ? "rgba(0,255,102,0.15)" : "transparent",
            color: filter === f ? "#00FF66" : "#667085", border: `1px solid ${filter === f ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
          }}>
            {typeIcons[f] || "📋"} {f.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Feed */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        <div style={{ maxWidth: 700, margin: "0 auto" }}>
          {filtered.map((item, i) => (
            <div
              key={item.id}
              className="af"
              onClick={() => setSelectedItem(selectedItem === item.id ? null : item.id)}
              style={{
                background: "#0d0f12", border: `1px solid ${selectedItem === item.id ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
                borderRadius: 8, padding: 14, marginBottom: 8, cursor: "pointer", transition: "all 0.15s",
                borderLeft: `3px solid ${typeColors[item.type] || "#667085"}`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 14 }}>{typeIcons[item.type] || "📋"}</span>
                <span style={{ fontSize: 12, fontWeight: 500, flex: 1 }}>{item.title}</span>
                <span style={{ fontSize: 9, color: "#667085" }}>{item.time}</span>
                {item.priority === "high" && (
                  <span style={{ padding: "1px 6px", borderRadius: 3, fontSize: 8, background: "rgba(255,51,51,0.15)", color: "#FF3333" }}>
                    URGENT
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: "#9ca3af", lineHeight: 1.5 }}>{item.summary}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
                <span style={{ fontSize: 8, color: "#667085", padding: "2px 6px", borderRadius: 3, background: "#1a1d23" }}>
                  {item.source}
                </span>
                {item.action && (
                  <button
                    onClick={e => { e.stopPropagation(); handleAction(item.action!); }}
                    style={{
                      marginLeft: "auto", padding: "3px 8px", borderRadius: 3, fontSize: 9,
                      fontFamily: "inherit", cursor: "pointer", background: "rgba(0,255,102,0.1)",
                      color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)",
                    }}
                  >
                    Execute →
                  </button>
                )}
              </div>
            </div>
          ))}

          {filtered.length === 0 && (
            <div style={{ textAlign: "center", padding: "80px 20px" }}>
              <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.3 }}>📋</div>
              <div style={{ fontSize: 12, color: "#667085" }}>No feed items. Click REFRESH to scan.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
