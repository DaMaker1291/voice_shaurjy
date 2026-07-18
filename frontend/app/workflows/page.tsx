"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [selectedWf, setSelectedWf] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [running, setRunning] = useState<string | null>(null);

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    if (selectedWf) fetchRuns(selectedWf.id);
  }, [selectedWf]);

  async function fetchData() {
    try {
      const [w, s, e] = await Promise.all([
        fetch(`${API}/api/workflows`).then(r => r.json()),
        fetch(`${API}/api/workflows/stats`).then(r => r.json()),
        fetch(`${API}/api/workflows/events?limit=30`).then(r => r.json()),
      ]);
      setWorkflows(w.workflows || []);
      setStats(s);
      setEvents(e.events || []);
    } catch {}
  }

  async function fetchRuns(wfId: string) {
    try {
      const r = await fetch(`${API}/api/workflows/${wfId}/runs`);
      const d = await r.json();
      setRuns(d.runs || []);
    } catch { setRuns([]); }
  }

  async function runWorkflow(wfId: string) {
    setRunning(wfId);
    try {
      const r = await fetch(`${API}/api/workflows/${wfId}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      await r.json();
      fetchData();
      if (selectedWf?.id === wfId) fetchRuns(wfId);
    } catch {}
    setRunning(null);
  }

  return (
    <div style={{ minHeight: "100vh", background: "#080a0d", color: "#e5e5e5", padding: "24px 32px", fontFamily: "'JetBrains Mono', monospace" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, color: "#00FF66" }}>Autonomous Workflows</h1>
        <p style={{ fontSize: 10, color: "#667085", marginBottom: 24 }}>Event-driven triggers, autonomous actions, feedback loops</p>

        {stats && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
            <Stat label="Active Workflows" value={stats.workflows?.active || 0} color="#00FF66" />
            <Stat label="Total Runs" value={stats.runs?.total || 0} color="#3b82f6" />
            <Stat label="Success Rate" value={`${stats.runs?.success_rate || 0}%`} color="#00FF66" />
            <Stat label="Events Pending" value={stats.events?.pending || 0} color="#fbbf24" />
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: selectedWf ? "1fr 1fr" : "1fr", gap: 20 }}>
          {/* Workflow List */}
          <div>
            <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>WORKFLOWS</h2>
            {workflows.length === 0 ? <Empty text="No workflows" /> : (
              <div style={{ display: "grid", gap: 6 }}>
                {workflows.map(wf => {
                  const actions = JSON.parse(wf.actions || "[]");
                  return (
                    <div key={wf.id} onClick={() => setSelectedWf(wf)} style={{
                      padding: 14, borderRadius: 8, cursor: "pointer",
                      background: selectedWf?.id === wf.id ? "rgba(0,255,102,0.05)" : "#0d0f12",
                      border: `1px solid ${selectedWf?.id === wf.id ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <span style={{ fontWeight: 600, fontSize: 12 }}>{wf.name}</span>
                        <button onClick={e => { e.stopPropagation(); runWorkflow(wf.id); }} disabled={running === wf.id} style={{
                          padding: "3px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit",
                          background: running === wf.id ? "#667085" : "#00FF66", color: "#000", border: "none", cursor: "pointer",
                        }}>{running === wf.id ? "Running..." : "Run"}</button>
                      </div>
                      <div style={{ fontSize: 9, color: "#667085", marginBottom: 4 }}>{wf.description}</div>
                      <div style={{ display: "flex", gap: 8, fontSize: 9 }}>
                        <span style={{ color: "#667085" }}>{wf.trigger_type}</span>
                        <span style={{ color: "#667085" }}>P{wf.priority}</span>
                        <span style={{ color: "#667085" }}>{actions.length} actions</span>
                        <span style={{ color: "#667085" }}>Runs: {wf.run_count}</span>
                        <span style={{ color: wf.status === "active" ? "#00FF66" : "#667085" }}>{wf.status}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Selected Workflow Detail */}
          {selectedWf && (
            <div>
              <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>RUN HISTORY</h2>
              {runs.length === 0 ? <Empty text="No runs yet" /> : (
                <div style={{ display: "grid", gap: 4 }}>
                  {runs.map(r => (
                    <div key={r.id} style={{ padding: "8px 12px", borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ color: r.status === "success" ? "#00FF66" : "#ef4444" }}>{r.status}</span>
                        <span style={{ color: "#667085" }}>{r.latency_ms?.toFixed(1)}ms</span>
                      </div>
                      <div style={{ display: "flex", gap: 8, color: "#667085" }}>
                        <span>{r.actions_succeeded}/{r.actions_executed} succeeded</span>
                        <span>{r.started_at?.slice(0, 16)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginTop: 20, marginBottom: 8 }}>ACTIONS</h2>
              <div style={{ display: "grid", gap: 4 }}>
                {JSON.parse(selectedWf.actions || "[]").map((a: any, i: number) => (
                  <div key={i} style={{ padding: "6px 12px", borderRadius: 4, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10, display: "flex", gap: 12 }}>
                    <span style={{ color: "#00FF66" }}>{a.type}</span>
                    <span style={{ color: "#667085" }}>{JSON.stringify(a).slice(0, 80)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Events */}
        <div style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>RECENT EVENTS</h2>
          {events.length === 0 ? <Empty text="No events" /> : (
            <div style={{ display: "grid", gap: 4 }}>
              {events.slice(0, 15).map((e, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 12px", borderRadius: 4, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10 }}>
                  <span style={{ color: "#00FF66" }}>{e.event_type}</span>
                  <span style={{ color: "#667085" }}>{e.source}</span>
                  <span style={{ color: e.severity === "warning" ? "#fbbf24" : e.severity === "error" ? "#ef4444" : "#667085" }}>{e.severity}</span>
                  <span style={{ color: "#667085" }}>{e.created_at?.slice(0, 16)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: any; color: string }) {
  return <div style={{ padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23", textAlign: "center" }}><div style={{ fontSize: 9, color: "#667085", marginBottom: 4 }}>{label}</div><div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div></div>;
}
function Empty({ text }: { text: string }) {
  return <div style={{ padding: 20, textAlign: "center", color: "#667085", fontSize: 10, background: "#0d0f12", borderRadius: 6, border: "1px solid #1a1d23" }}>{text}</div>;
}
