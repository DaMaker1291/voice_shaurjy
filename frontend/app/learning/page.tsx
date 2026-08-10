"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function LearningPage() {
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [metrics, setMetrics] = useState<any>(null);
  const [curve, setCurve] = useState<any[]>([]);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);

  useEffect(() => { fetchLeaderboard(); }, []);

  useEffect(() => {
    if (selectedAgent) {
      fetchMetrics(selectedAgent);
      fetchCurve(selectedAgent);
      fetchStrategies(selectedAgent);
      fetchTimeline(selectedAgent);
    }
  }, [selectedAgent]);

  async function fetchLeaderboard() {
    try {
      const r = await fetch(`${API}/api/learning/leaderboard`);
      const d = await r.json();
      setLeaderboard(d.leaderboard || []);
      if (d.leaderboard?.length > 0) setSelectedAgent(d.leaderboard[0].agent_id);
    } catch { setLeaderboard([]); }
  }

  async function fetchMetrics(agentId: string) {
    try {
      const r = await fetch(`${API}/api/learning/metrics/${agentId}`);
      setMetrics(await r.json());
    } catch { setMetrics(null); }
  }

  async function fetchCurve(agentId: string) {
    try {
      const r = await fetch(`${API}/api/learning/curve/${agentId}`);
      const d = await r.json();
      setCurve(d.curve || []);
    } catch { setCurve([]); }
  }

  async function fetchStrategies(agentId: string) {
    try {
      const r = await fetch(`${API}/api/learning/strategies/${agentId}`);
      const d = await r.json();
      setStrategies(d.best_strategy ? [d.best_strategy] : []);
    } catch { setStrategies([]); }
  }

  async function fetchTimeline(agentId: string) {
    try {
      const r = await fetch(`${API}/api/learning/timeline/${agentId}`);
      const d = await r.json();
      setTimeline(d.timeline || []);
    } catch { setTimeline([]); }
  }

  const agents = ["os", "hal", "web", "core", "device", "monitor"];

  return (
    <div style={{ minHeight: "100vh", background: "#080a0d", color: "#e5e5e5", padding: "24px 32px", fontFamily: "'JetBrains Mono', monospace" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, color: "#00FF66" }}>Self-Improvement Engine</h1>
        <p style={{ fontSize: 10, color: "#667085", marginBottom: 24 }}>Track agent learning, measure improvement, evolve strategies</p>

        {/* Agent Selector */}
        <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
          {agents.map(a => (
            <button key={a} onClick={() => setSelectedAgent(a)} style={{
              padding: "6px 14px", borderRadius: 6, border: `1px solid ${selectedAgent === a ? "#00FF66" : "#1a1d23"}`,
              background: selectedAgent === a ? "rgba(0,255,102,0.1)" : "#0d0f12", color: selectedAgent === a ? "#00FF66" : "#667085",
              fontSize: 11, cursor: "pointer", fontFamily: "inherit", textTransform: "uppercase",
            }}>{a}</button>
          ))}
        </div>

        {/* Leaderboard */}
        <Section title="Agent Leaderboard">
          {leaderboard.length === 0 ? <Empty text="No interactions yet" /> : (
            <div style={{ display: "grid", gap: 6 }}>
              {leaderboard.map(a => (
                <div key={a.agent_id} onClick={() => setSelectedAgent(a.agent_id)} style={{
                  display: "grid", gridTemplateColumns: "40px 1fr 100px 100px 100px", gap: 12, alignItems: "center",
                  padding: "10px 14px", borderRadius: 6, background: selectedAgent === a.agent_id ? "rgba(0,255,102,0.05)" : "#0d0f12",
                  border: `1px solid ${selectedAgent === a.agent_id ? "rgba(0,255,102,0.2)" : "#1a1d23"}`,
                  cursor: "pointer", fontSize: 11,
                }}>
                  <span style={{ color: "#00FF66", fontWeight: 700 }}>#{a.rank}</span>
                  <span style={{ textTransform: "uppercase", fontWeight: 600 }}>{a.agent_id}</span>
                  <span style={{ color: "#667085" }}>{a.total_interactions} runs</span>
                  <span style={{ color: a.success_rate > 80 ? "#00FF66" : a.success_rate > 50 ? "#fbbf24" : "#ef4444" }}>{a.success_rate}%</span>
                  <span style={{ color: "#667085" }}>{a.avg_latency_ms}ms</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Metrics */}
        {metrics && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
            <MetricCard label="Success Rate" value={`${metrics.overall?.success_rate || 0}%`} color="#00FF66" />
            <MetricCard label="Avg Latency" value={`${metrics.overall?.avg_latency_ms || 0}ms`} color="#3b82f6" />
            <MetricCard label="Avg Confidence" value={`${(metrics.overall?.avg_confidence || 0).toFixed(3)}`} color="#fbbf24" />
            <MetricCard label="Improving?" value={metrics.improvement_rate?.is_improving ? "YES" : "NO"} color={metrics.improvement_rate?.is_improving ? "#00FF66" : "#ef4444"} />
          </div>
        )}

        {/* Learning Curve */}
        <Section title="Learning Curve (30d)">
          {curve.length === 0 ? <Empty text="No data yet" /> : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(80px, 1fr))", gap: 4 }}>
              {curve.map(day => (
                <div key={day.day} style={{ textAlign: "center", padding: "8px 4px", borderRadius: 4, background: "#0d0f12", border: "1px solid #1a1d23" }}>
                  <div style={{ fontSize: 7, color: "#667085", marginBottom: 4 }}>{day.day?.slice(5)}</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#00FF66" }}>{day.success_rate}%</div>
                  <div style={{ fontSize: 7, color: "#667085" }}>{day.total} runs</div>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Best Strategy */}
        <Section title="Best Strategy">
          {strategies.length === 0 ? <Empty text="No strategies" /> : strategies.map(s => (
            <div key={s.id} style={{ padding: 12, borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 11 }}>
              <div style={{ fontWeight: 600, color: "#00FF66", marginBottom: 4 }}>{s.name}</div>
              <div style={{ color: "#667085" }}>Success: {s.success_count} | Failures: {s.failure_count} | v{s.version}</div>
              <div style={{ color: "#667085", marginTop: 4 }}>Confidence: {s.avg_confidence?.toFixed(3)}</div>
            </div>
          ))}
        </Section>

        {/* Improvement Timeline */}
        <Section title="Improvement Timeline">
          {timeline.length === 0 ? <Empty text="No events yet" /> : (
            <div style={{ display: "grid", gap: 6 }}>
              {timeline.slice(0, 20).map((e, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", borderRadius: 4, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10 }}>
                  <span style={{ color: "#00FF66" }}>{e.event_type}</span>
                  <span style={{ color: "#9ca3af" }}>{e.description}</span>
                  <span style={{ color: "#667085" }}>{e.created_at?.slice(0, 16)}</span>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>{title.toUpperCase()}</h2>
      {children}
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23", textAlign: "center" }}>
      <div style={{ fontSize: 9, color: "#667085", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div style={{ padding: 20, textAlign: "center", color: "#667085", fontSize: 10, background: "#0d0f12", borderRadius: 6, border: "1px solid #1a1d23" }}>{text}</div>;
}
