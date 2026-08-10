"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function SkillsPage() {
  const [skills, setSkills] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [selectedCat, setSelectedCat] = useState<string>("");
  const [search, setSearch] = useState("");
  const [selectedSkill, setSelectedSkill] = useState<any>(null);
  const [execResult, setExecResult] = useState<any>(null);

  useEffect(() => { fetchAll(); }, []);
  useEffect(() => { fetchSkills(); }, [selectedCat, search]);

  async function fetchAll() {
    try {
      const [s, c, st] = await Promise.all([
        fetch(`${API}/api/skills`).then(r => r.json()),
        fetch(`${API}/api/skills/categories`).then(r => r.json()),
        fetch(`${API}/api/skills/stats`).then(r => r.json()),
      ]);
      setSkills(s.skills || []);
      setCategories(c.categories || []);
      setStats(st);
    } catch {}
  }

  async function fetchSkills() {
    try {
      const params = new URLSearchParams();
      if (selectedCat) params.set("category", selectedCat);
      if (search) params.set("search", search);
      const r = await fetch(`${API}/api/skills?${params}`);
      const d = await r.json();
      setSkills(d.skills || []);
    } catch {}
  }

  async function toggleInstall(skill: any) {
    const endpoint = skill.installed ? "uninstall" : "install";
    try {
      await fetch(`${API}/api/skills/${skill.id}/${endpoint}`, { method: "POST" });
      fetchAll();
      if (selectedSkill?.id === skill.id) {
        const r = await fetch(`${API}/api/skills/${skill.id}`);
        setSelectedSkill(await r.json());
      }
    } catch {}
  }

  async function executeSkill(skillId: string) {
    try {
      const r = await fetch(`${API}/api/skills/${skillId}/execute`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      setExecResult(await r.json());
    } catch { setExecResult({ status: "error" }); }
  }

  async function viewSkill(skillId: string) {
    try {
      const r = await fetch(`${API}/api/skills/${skillId}`);
      setSelectedSkill(await r.json());
    } catch {}
  }

  const catIcons: Record<string, string> = { information: "📡", productivity: "⚡", automation: "🤖", development: "💻", intelligence: "🧠", security: "🔒", interface: "🎙️", data: "🔄", general: "🧩" };

  return (
    <div style={{ minHeight: "100vh", background: "#080a0d", color: "#e5e5e5", padding: "24px 32px", fontFamily: "'JetBrains Mono', monospace" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, color: "#00FF66" }}>Skill Marketplace</h1>
        <p style={{ fontSize: 10, color: "#667085", marginBottom: 24 }}>Install, configure, and execute agent skills</p>

        {/* Stats */}
        {stats && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
            <Stat label="Total Skills" value={stats.skills?.total || 0} color="#00FF66" />
            <Stat label="Installed" value={stats.skills?.installed || 0} color="#3b82f6" />
            <Stat label="Avg Rating" value={stats.reviews?.avg_rating || 0} color="#fbbf24" />
            <Stat label="Categories" value={stats.categories || 0} color="#a855f7" />
          </div>
        )}

        {/* Categories */}
        <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
          <button onClick={() => { setSelectedCat(""); setSearch(""); }} style={{
            padding: "5px 12px", borderRadius: 20, fontSize: 10, fontFamily: "inherit",
            background: !selectedCat ? "rgba(0,255,102,0.15)" : "#0d0f12",
            border: `1px solid ${!selectedCat ? "#00FF66" : "#1a1d23"}`,
            color: !selectedCat ? "#00FF66" : "#667085", cursor: "pointer",
          }}>All</button>
          {categories.map(c => (
            <button key={c.category} onClick={() => setSelectedCat(c.category)} style={{
              padding: "5px 12px", borderRadius: 20, fontSize: 10, fontFamily: "inherit",
              background: selectedCat === c.category ? "rgba(0,255,102,0.15)" : "#0d0f12",
              border: `1px solid ${selectedCat === c.category ? "#00FF66" : "#1a1d23"}`,
              color: selectedCat === c.category ? "#00FF66" : "#667085", cursor: "pointer",
            }}>{catIcons[c.category] || "🧩"} {c.category} ({c.total})</button>
          ))}
        </div>

        {/* Search */}
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search skills..."
          style={{ width: "100%", padding: "8px 14px", borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23", color: "#e5e5e5", fontSize: 11, fontFamily: "inherit", outline: "none", marginBottom: 20 }} />

        <div style={{ display: "grid", gridTemplateColumns: selectedSkill ? "1fr 1fr" : "1fr", gap: 20 }}>
          {/* Skills Grid */}
          <div style={{ display: "grid", gap: 8 }}>
            {skills.length === 0 ? <Empty text="No skills found" /> : skills.map(skill => (
              <div key={skill.id} onClick={() => viewSkill(skill.id)} style={{
                padding: 16, borderRadius: 8, cursor: "pointer",
                background: selectedSkill?.id === skill.id ? "rgba(0,255,102,0.05)" : "#0d0f12",
                border: `1px solid ${selectedSkill?.id === skill.id ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <span style={{ fontSize: 20 }}>{skill.icon}</span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 12 }}>{skill.display_name}</div>
                      <div style={{ fontSize: 9, color: "#667085" }}>v{skill.version} by {skill.author}</div>
                    </div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); toggleInstall(skill); }} style={{
                    padding: "4px 12px", borderRadius: 4, fontSize: 9, fontFamily: "inherit",
                    background: skill.installed ? "rgba(239,68,68,0.15)" : "#00FF66",
                    color: skill.installed ? "#ef4444" : "#000",
                    border: skill.installed ? "1px solid #ef4444" : "none",
                    fontWeight: 700, cursor: "pointer",
                  }}>{skill.installed ? "Uninstall" : "Install"}</button>
                </div>
                <div style={{ fontSize: 10, color: "#9ca3af", marginBottom: 6 }}>{skill.description}</div>
                <div style={{ display: "flex", gap: 12, fontSize: 9, color: "#667085" }}>
                  <span>⭐ {skill.rating?.toFixed(1)}</span>
                  <span>📥 {skill.install_count}</span>
                  <span>{skill.category}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Skill Detail */}
          {selectedSkill && (
            <div style={{ position: "sticky", top: 24 }}>
              <div style={{ padding: 20, borderRadius: 8, background: "#0d0f12", border: "1px solid #1a1d23" }}>
                <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 32 }}>{selectedSkill.icon}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>{selectedSkill.display_name}</div>
                    <div style={{ fontSize: 10, color: "#667085" }}>v{selectedSkill.version} by {selectedSkill.author} · {selectedSkill.license}</div>
                  </div>
                </div>
                <p style={{ fontSize: 11, color: "#9ca3af", marginBottom: 16, lineHeight: 1.6 }}>{selectedSkill.description}</p>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
                  <div style={{ textAlign: "center", padding: 8, borderRadius: 4, background: "#080a0d" }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#00FF66" }}>{selectedSkill.rating?.toFixed(1)}</div>
                    <div style={{ fontSize: 8, color: "#667085" }}>Rating</div>
                  </div>
                  <div style={{ textAlign: "center", padding: 8, borderRadius: 4, background: "#080a0d" }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#3b82f6" }}>{selectedSkill.install_count}</div>
                    <div style={{ fontSize: 8, color: "#667085" }}>Downloads</div>
                  </div>
                  <div style={{ textAlign: "center", padding: 8, borderRadius: 4, background: "#080a0d" }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#fbbf24" }}>{selectedSkill.rating_count}</div>
                    <div style={{ fontSize: 8, color: "#667085" }}>Reviews</div>
                  </div>
                </div>

                {selectedSkill.installed && (
                  <button onClick={() => executeSkill(selectedSkill.id)} style={{
                    width: "100%", padding: "8px 0", borderRadius: 6, background: "#00FF66", color: "#000",
                    fontSize: 11, fontWeight: 700, border: "none", cursor: "pointer", marginBottom: 12,
                  }}>Execute Skill</button>
                )}

                {execResult && (
                  <div style={{ padding: 10, borderRadius: 6, background: "#080a0d", border: "1px solid #1a1d23", fontSize: 9, color: execResult.status === "success" ? "#00FF66" : "#ef4444", marginBottom: 12, fontFamily: "inherit", wordBreak: "break-all" }}>
                    {JSON.stringify(execResult, null, 2)}
                  </div>
                )}

                {selectedSkill.reviews?.length > 0 && (
                  <>
                    <div style={{ fontSize: 10, fontWeight: 600, color: "#00FF66", marginBottom: 8 }}>REVIEWS</div>
                    <div style={{ display: "grid", gap: 6, maxHeight: 200, overflow: "auto" }}>
                      {selectedSkill.reviews.map((r: any, i: number) => (
                        <div key={i} style={{ padding: 8, borderRadius: 4, background: "#080a0d", border: "1px solid #1a1d23" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                            <span style={{ fontSize: 9, color: "#667085" }}>{r.user_id}</span>
                            <span style={{ fontSize: 9, color: "#fbbf24" }}>{"⭐".repeat(r.rating)}</span>
                          </div>
                          {r.comment && <div style={{ fontSize: 10, color: "#9ca3af" }}>{r.comment}</div>}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
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
