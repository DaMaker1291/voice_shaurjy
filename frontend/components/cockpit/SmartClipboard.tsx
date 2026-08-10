"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BASE, safeJson } from "@/lib/api";

interface ClipboardEntry {
  id: string;
  content: string;
  content_type: string;
  timestamp: number;
  formatted_versions: Record<string, string>;
  metadata: { char_count: number; word_count: number; line_count: number };
  pinned: boolean;
}

interface FormatSuggestion {
  action_id: string;
  label: string;
  description: string;
  icon: string;
  output: string;
  confidence: number;
}

export default function SmartClipboard() {
  const [history, setHistory] = useState<ClipboardEntry[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ClipboardEntry | null>(null);
  const [suggestions, setSuggestions] = useState<FormatSuggestion[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [toast, setToast] = useState("");

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/clipboard/history?limit=50&search=${encodeURIComponent(search)}`);
      const data = await safeJson(res);
      setHistory(data.entries || []);
    } catch {}
  }, [search]);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/clipboard/stats`);
      setStats(await safeJson(res));
    } catch {}
  }, []);

  useEffect(() => { loadHistory(); loadStats(); }, [loadHistory, loadStats]);

  useEffect(() => {
    const interval = setInterval(loadHistory, 3000);
    return () => clearInterval(interval);
  }, [loadHistory]);

  const processContent = async (content: string) => {
    try {
      const res = await fetch(`${BASE}/api/clipboard/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, source_app: "manual" }),
      });
      const data = await safeJson(res);
      setSuggestions(data.suggestions || []);
      loadHistory();
    } catch {}
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setToast("Copied!");
      setTimeout(() => setToast(""), 2000);
    } catch {
      setToast("Copy failed");
      setTimeout(() => setToast(""), 2000);
    }
  };

  const pinEntry = async (id: string) => {
    await fetch(`${BASE}/api/clipboard/pin/${id}`, { method: "POST" });
    loadHistory();
  };

  const deleteEntry = async (id: string) => {
    await fetch(`${BASE}/api/clipboard/${id}`, { method: "DELETE" });
    if (selected?.id === id) { setSelected(null); setSuggestions([]); }
    loadHistory();
  };

  const typeIcon: Record<string, string> = {
    json: "📋", code: "💻", url: "🔗", email: "📧",
    phone: "📞", base64: "🔓", markdown: "📝", html: "🌐", text: "📄",
  };

  return (
    <div style={{ background: "linear-gradient(135deg, #0d0f12 0%, #12151a 100%)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 6px rgba(0,255,102,0.5)" }} />
          <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.08em" }}>SMART_CLIPBOARD</span>
        </div>
        <span style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
          {stats?.total_entries || 0} entries
        </span>
      </div>

      {/* Search */}
      <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)" }}>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search clipboard..."
          style={{ width: "100%", padding: "4px 8px", borderRadius: 3, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text-primary)", fontSize: 9, fontFamily: "var(--font-mono)", outline: "none" }}
        />
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {selected ? (
          <div style={{ padding: 12 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--neon-green)" }}>{typeIcon[selected.content_type] || "📄"} {selected.content_type.toUpperCase()}</span>
              <button onClick={() => { setSelected(null); setSuggestions([]); }} style={{ fontSize: 8, fontFamily: "var(--font-mono)", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>BACK</button>
            </div>
            <div style={{ padding: 8, borderRadius: 4, background: "var(--surface)", border: "1px solid var(--border)", fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-secondary)", maxHeight: 120, overflow: "auto", wordBreak: "break-all", marginBottom: 8 }}>
              {selected.content.slice(0, 500)}
            </div>
            {suggestions.length > 0 && (
              <div>
                <div style={{ fontSize: 8, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: 4, letterSpacing: "0.08em" }}>FORMAT ACTIONS</div>
                {suggestions.filter(s => s.action_id !== "info_count").map(s => (
                  <button key={s.action_id} onClick={() => copyToClipboard(s.output)} style={{ width: "100%", textAlign: "left", padding: "6px 8px", marginBottom: 4, borderRadius: 3, background: "var(--surface)", border: "1px solid var(--border)", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 11 }}>{s.icon}</span>
                    <div>
                      <div style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{s.label}</div>
                      <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{s.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div>
            {history.length === 0 ? (
              <div style={{ padding: 20, textAlign: "center", fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>No clipboard entries yet</div>
            ) : (
              history.map(entry => (
                <div key={entry.id} onClick={() => { setSelected(entry); processContent(entry.content); }}
                  style={{ padding: "6px 12px", borderBottom: "1px solid var(--border)", cursor: "pointer", display: "flex", alignItems: "center", gap: 8, background: "transparent", transition: "background 0.15s" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "var(--surface)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                  <span style={{ fontSize: 11 }}>{typeIcon[entry.content_type] || "📄"}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {entry.content.slice(0, 80)}
                    </div>
                    <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                      {entry.content_type} · {entry.metadata?.word_count || 0} words · {new Date(entry.timestamp * 1000).toLocaleTimeString()}
                    </div>
                  </div>
                  {entry.pinned && <span style={{ fontSize: 8, color: "var(--neon-green)" }}>📌</span>}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {toast && (
        <div style={{ position: "absolute", bottom: 40, left: "50%", transform: "translateX(-50%)", padding: "4px 12px", borderRadius: 4, background: "var(--neon-green)", color: "#000", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600, zIndex: 10 }}>
          {toast}
        </div>
      )}
    </div>
  );
}
