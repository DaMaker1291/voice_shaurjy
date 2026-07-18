"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function EnterprisePage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [showRegister, setShowRegister] = useState(false);
  const [regForm, setRegForm] = useState({ username: "", password: "", email: "", role: "viewer" });

  useEffect(() => { fetchData(); }, []);

  async function fetchData() {
    try {
      const [d, u, a] = await Promise.all([
        fetch(`${API}/api/enterprise/dashboard`).then(r => r.json()),
        fetch(`${API}/api/enterprise/users`).then(r => r.json()),
        fetch(`${API}/api/enterprise/audit?limit=30`).then(r => r.json()),
      ]);
      setDashboard(d);
      setUsers(u.users || []);
      setAudit(a.audit_log || []);
    } catch {}
  }

  async function registerUser() {
    if (!regForm.username || !regForm.password) return;
    try {
      await fetch(`${API}/api/auth/register`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(regForm),
      });
      setShowRegister(false);
      setRegForm({ username: "", password: "", email: "", role: "viewer" });
      fetchData();
    } catch {}
  }

  return (
    <div style={{ minHeight: "100vh", background: "#080a0d", color: "#e5e5e5", padding: "24px 32px", fontFamily: "'JetBrains Mono', monospace" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, color: "#00FF66" }}>Enterprise Control</h1>
            <p style={{ fontSize: 10, color: "#667085" }}>Multi-user auth, RBAC, teams, compliance</p>
          </div>
          <button onClick={() => setShowRegister(!showRegister)} style={{ padding: "6px 14px", borderRadius: 6, background: "#00FF66", color: "#000", fontSize: 10, fontWeight: 700, border: "none", cursor: "pointer" }}>+ New User</button>
        </div>

        {/* Dashboard Stats */}
        {dashboard && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 24 }}>
            <Card label="Users" value={dashboard.users?.total || 0} sub={`${dashboard.users?.active || 0} active`} color="#00FF66" />
            <Card label="Teams" value={dashboard.teams?.total || 0} color="#3b82f6" />
            <Card label="Audit (24h)" value={dashboard.audit?.last_24h || 0} sub={`${dashboard.audit?.last_7d || 0} (7d)`} color="#fbbf24" />
            <Card label="Sessions" value={dashboard.sessions?.active || 0} color="#a855f7" />
            <Card label="Compliance" value={`${dashboard.compliance_score || 0}%`} color={dashboard.compliance_score > 80 ? "#00FF66" : "#ef4444"} />
          </div>
        )}

        {/* Register Form */}
        {showRegister && (
          <div style={{ padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid rgba(0,255,102,0.2)", marginBottom: 24 }}>
            <h3 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", marginBottom: 12 }}>Create User</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 8 }}>
              <input value={regForm.username} onChange={e => setRegForm({ ...regForm, username: e.target.value })} placeholder="Username" style={inputStyle} />
              <input value={regForm.password} onChange={e => setRegForm({ ...regForm, password: e.target.value })} placeholder="Password" type="password" style={inputStyle} />
              <input value={regForm.email} onChange={e => setRegForm({ ...regForm, email: e.target.value })} placeholder="Email" style={inputStyle} />
              <select value={regForm.role} onChange={e => setRegForm({ ...regForm, role: e.target.value })} style={inputStyle}>
                <option value="viewer">Viewer</option>
                <option value="operator">Operator</option>
                <option value="editor">Editor</option>
                <option value="admin">Admin</option>
              </select>
              <button onClick={registerUser} style={{ padding: "6px 14px", borderRadius: 6, background: "#00FF66", color: "#000", fontSize: 10, fontWeight: 700, border: "none", cursor: "pointer" }}>Create</button>
            </div>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Users */}
          <div>
            <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>USERS</h2>
            <div style={{ display: "grid", gap: 6 }}>
              {users.map(u => (
                <div key={u.id} style={{ display: "grid", gridTemplateColumns: "1fr 80px 80px 1fr", gap: 8, alignItems: "center", padding: "10px 14px", borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 11 }}>
                  <span style={{ fontWeight: 600 }}>{u.username}</span>
                  <span style={{ color: u.role === "admin" ? "#fbbf24" : u.role === "editor" ? "#3b82f6" : "#667085" }}>{u.role}</span>
                  <span style={{ color: u.is_active ? "#00FF66" : "#ef4444" }}>{u.is_active ? "active" : "inactive"}</span>
                  <span style={{ color: "#667085", fontSize: 9 }}>{u.last_login ? `Last: ${u.last_login.slice(0, 10)}` : "Never logged in"}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Role Distribution */}
          {dashboard?.roles && (
            <div>
              <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>ROLE DISTRIBUTION</h2>
              <div style={{ display: "grid", gap: 6 }}>
                {dashboard.roles.map((r: any) => (
                  <div key={r.role} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderRadius: 6, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 11 }}>
                    <span style={{ textTransform: "uppercase", fontWeight: 600 }}>{r.role}</span>
                    <span style={{ color: "#00FF66" }}>{r.count} users</span>
                  </div>
                ))}
              </div>

              {dashboard.audit?.top_actions && (
                <>
                  <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginTop: 20, marginBottom: 8 }}>TOP ACTIONS (7d)</h2>
                  <div style={{ display: "grid", gap: 4 }}>
                    {dashboard.audit.top_actions.map((a: any, i: number) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 12px", borderRadius: 4, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10 }}>
                        <span style={{ color: "#e5e5e5" }}>{a.action}</span>
                        <span style={{ color: "#00FF66" }}>{a.count}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Audit Log */}
        <div style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 12, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>AUDIT LOG</h2>
          {audit.length === 0 ? <Empty text="No audit entries" /> : (
            <div style={{ display: "grid", gap: 4 }}>
              {audit.slice(0, 20).map((a, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 120px 100px 1fr", gap: 8, padding: "6px 12px", borderRadius: 4, background: "#0d0f12", border: "1px solid #1a1d23", fontSize: 10 }}>
                  <span style={{ color: "#00FF66" }}>{a.action}</span>
                  <span style={{ color: "#667085" }}>{a.username || a.user_id}</span>
                  <span style={{ color: "#667085" }}>{a.resource_type}</span>
                  <span style={{ color: "#667085" }}>{a.created_at?.slice(0, 16)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Card({ label, value, sub, color }: { label: string; value: any; sub?: string; color: string }) {
  return <div style={{ padding: 16, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23", textAlign: "center" }}><div style={{ fontSize: 9, color: "#667085", marginBottom: 4 }}>{label}</div><div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>{sub && <div style={{ fontSize: 8, color: "#667085", marginTop: 2 }}>{sub}</div>}</div>;
}
function Empty({ text }: { text: string }) {
  return <div style={{ padding: 20, textAlign: "center", color: "#667085", fontSize: 10, background: "#0d0f12", borderRadius: 6, border: "1px solid #1a1d23" }}>{text}</div>;
}
const inputStyle = { padding: "6px 10px", borderRadius: 6, background: "#080a0d", border: "1px solid #1a1d23", color: "#e5e5e5", fontSize: 10, fontFamily: "inherit", outline: "none" };
