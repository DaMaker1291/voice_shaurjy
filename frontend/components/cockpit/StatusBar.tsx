"use client";

import { useEffect, useState } from "react";

export default function StatusBar() {
  const [relay, setRelay] = useState(false);
  const [agents, setAgents] = useState(0);
  const [devices, setDevices] = useState(0);
  const [mem, setMem] = useState("--");

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await window.fetch("/api/health");
        const data = await res.json();
        setRelay(!!data.relay);
        setMem(data.sandbox?.mem_mb ? `${data.sandbox.mem_mb}MB` : "--");
      } catch {}
      try {
        const res = await window.fetch("/api/autonomous/tasks");
        const data = await res.json();
        setAgents((data.tasks || []).filter((t: any) => t.status === "running").length);
      } catch {}
      try {
        const res = await window.fetch("/api/relay/devices?user_id=local");
        const data = await res.json();
        setDevices((data.devices || []).length);
      } catch {}
    };
    poll();
    const i = setInterval(poll, 8000);
    return () => clearInterval(i);
  }, []);

  return (
    <div style={{
      height: 22, background: "#08090c", borderTop: "1px solid #1a1d23",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 12px", fontFamily: "var(--font-mono)", fontSize: 8,
      color: "var(--text-muted)", flexShrink: 0, letterSpacing: "0.04em",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{ width: 4, height: 4, borderRadius: "50%", background: relay ? "#00FF66" : "#FF3333", boxShadow: `0 0 4px ${relay ? "rgba(0,255,102,0.4)" : "rgba(255,51,51,0.4)"}` }} />
          <span style={{ color: relay ? "#00FF66" : "#FF3333" }}>RELAY {relay ? "ONLINE" : "OFFLINE"}</span>
        </div>
        {agents > 0 && (
          <span style={{ color: "#FFB300" }}>{agents} AGENT{agents > 1 ? "S" : ""} RUNNING</span>
        )}
        {devices > 0 && (
          <span>{devices} DEVICE{devices > 1 ? "S" : ""}</span>
        )}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {mem !== "--" && <span>MEM {mem}</span>}
        <span>GROQ</span>
        <span style={{ color: "#00FF66" }}>JARVIS v3.0</span>
      </div>
    </div>
  );
}
