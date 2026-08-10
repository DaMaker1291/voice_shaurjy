"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { BASE, safeJson } from "@/lib/api";

interface Step {
  number: number;
  description: string;
  action: string;
  status: string;
}

interface Mission {
  id: string;
  objective: string;
  status: string;
  current_action: string;
  steps: Step[];
}

export default function PIPCockpit() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [active, setActive] = useState(false);
  const [manualControl, setManualControl] = useState(false);
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const lastFpsTime = useRef(Date.now());
  const [connected, setConnected] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [goal, setGoal] = useState("Build a landing page for my new business.");
  const [currentAction, setCurrentAction] = useState("Creating website components");
  const [missionStatus, setMissionStatus] = useState("WORKING");
  const [steps, setSteps] = useState<Step[]>([
    { number: 1, description: "Research", action: "research", status: "completed" },
    { number: 2, description: "Project setup", action: "setup", status: "completed" },
    { number: 3, description: "Website development", action: "develop", status: "running" },
    { number: 4, description: "Testing", action: "test", status: "pending" },
    { number: 5, description: "Deployment", action: "deploy", status: "pending" },
  ]);
  const [appSequence, setAppSequence] = useState<string[]>(["Chrome", "VS Code", "Terminal", "Chrome"]);
  const [activeMissionId, setActiveMissionId] = useState<string | null>(null);

  const base = BASE;
  const wsBase = base.replace("http", "ws");

  const startStream = useCallback(async () => {
    try {
      const res = await fetch(`${base}/api/pip/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: "pip_main", display_id: 1, resolution: [640, 360], fps: 15, quality: 70 }),
      });
      const data = await safeJson(res);
      if (data.ok) {
        setActive(true);
        connectWs();
      }
    } catch {}
  }, [base]);

  const stopStream = useCallback(async () => {
    try {
      if (activeMissionId) {
        await fetch(`${base}/api/workspace/mission/stop`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mission_id: activeMissionId }),
        });
      }
      await fetch(`${base}/api/pip/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: "pip_main" }),
      });
      setActive(false);
      wsRef.current?.close();
      setConnected(false);
      setMissionStatus("STOPPED");
    } catch {}
  }, [base, activeMissionId]);

  const toggleManualControl = useCallback(async () => {
    try {
      const newManual = !manualControl;
      setManualControl(newManual);
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ cmd: newManual ? "pause" : "resume" }));
      }
    } catch {}
  }, [manualControl]);

  const togglePause = useCallback(async () => {
    const isPaused = missionStatus === "PAUSED";
    const newStatus = isPaused ? "WORKING" : "PAUSED";
    setMissionStatus(newStatus);
    if (activeMissionId) {
      const endpoint = isPaused ? "/api/workspace/mission/resume" : "/api/workspace/mission/pause";
      try {
        await fetch(`${base}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mission_id: activeMissionId }),
        });
      } catch {}
    }
  }, [missionStatus, activeMissionId, base]);

  const submitGoal = useCallback(async () => {
    if (!goal.trim()) return;
    try {
      const res = await fetch(`${base}/api/workspace/mission/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective: goal.trim(), workspace_id: "default" }),
      });
      const data = await safeJson(res);
      if (data.ok) {
        setActiveMissionId(data.mission.id);
        setMissionStatus("WORKING");
        await fetch(`${base}/api/workspace/mission/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mission_id: data.mission.id }),
        });
      }
    } catch {}
  }, [goal, base]);

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    try {
      const ws = new WebSocket(`${wsBase}/api/workspace/ws/stream?workspace_id=default&fps=15&quality=70`);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); if (active) setTimeout(connectWs, 3000); };
      ws.onerror = () => setConnected(false);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "frame" && msg.data) {
            const canvas = canvasRef.current;
            if (!canvas) return;
            const ctx = canvas.getContext("2d");
            if (!ctx) return;
            const img = new Image();
            img.onload = () => {
              ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            };
            img.src = "data:image/jpeg;base64," + msg.data;
            frameCountRef.current++;
            const now = Date.now();
            if (now - lastFpsTime.current >= 1000) {
              setFps(frameCountRef.current);
              frameCountRef.current = 0;
              lastFpsTime.current = now;
            }
          } else if (msg.type === "status" || msg.type === "mission_event") {
            if (msg.missions && msg.missions.length > 0) {
              const m = msg.missions[msg.missions.length - 1];
              setActiveMissionId(m.id);
              if (m.objective) setGoal(m.objective);
              if (m.current_action) setCurrentAction(m.current_action);
              if (m.status === "paused") setMissionStatus("PAUSED");
              else if (m.status === "executing" || m.status === "running") setMissionStatus("WORKING");
              if (m.steps && m.steps.length > 0) setSteps(m.steps);
            }
          }
        } catch {}
      };
    } catch {}
  }, [wsBase, active]);

  useEffect(() => { return () => { wsRef.current?.close(); }; }, []);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!manualControl || !wsRef.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 1920);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 1080);
    wsRef.current.send(JSON.stringify({ cmd: "click", x, y, button: e.button === 2 ? 3 : 1 }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!manualControl || !wsRef.current) return;
    if (e.key === "Enter") {
      wsRef.current.send(JSON.stringify({ cmd: "key", key: "Return" }));
    } else if (e.key.length === 1) {
      wsRef.current.send(JSON.stringify({ cmd: "type", text: e.key }));
    }
  };

  if (minimized) {
    return (
      <div onClick={() => setMinimized(false)} style={{
        position: "fixed", bottom: 60, right: 16, width: 180, height: 110,
        borderRadius: 8, overflow: "hidden", border: "2px solid var(--neon-green)",
        boxShadow: "0 0 20px rgba(0,255,102,0.3)", cursor: "pointer", zIndex: 999,
        background: "#05070a", padding: 6, display: "flex", flexDirection: "column", gap: 4
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 8, fontFamily: "var(--font-mono)", color: "#00FF66" }}>
          <span>JARVIS</span>
          <span>● {missionStatus}</span>
        </div>
        <canvas ref={canvasRef} width={320} height={180} style={{ width: "100%", flex: 1, borderRadius: 4, objectFit: "cover" }} />
      </div>
    );
  }

  return (
    <div style={{
      background: "linear-gradient(135deg, #090c10 0%, #0d1117 100%)",
      border: "1px solid rgba(0,255,102,0.2)", borderRadius: 10, overflow: "hidden",
      display: "flex", flexDirection: "column", height: "100%", width: "100%",
      boxShadow: "0 8px 32px rgba(0,0,0,0.5), 0 0 15px rgba(0,255,102,0.1)",
      fontFamily: "var(--font-mono, monospace)"
    }}>
      {/* 1. Header Bar: JARVIS ● WORKING */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--border)", background: "rgba(15,20,28,0.9)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "var(--text-primary)" }}>JARVIS</span>
          <div style={{
            display: "flex", alignItems: "center", gap: 5, padding: "2px 8px", borderRadius: 10,
            background: missionStatus === "WORKING" ? "rgba(0,255,102,0.12)" : missionStatus === "PAUSED" ? "rgba(255,179,0,0.12)" : "rgba(255,51,51,0.12)",
            border: `1px solid ${missionStatus === "WORKING" ? "rgba(0,255,102,0.3)" : missionStatus === "PAUSED" ? "rgba(255,179,0,0.3)" : "rgba(255,51,51,0.3)"}`,
            color: missionStatus === "WORKING" ? "#00FF66" : missionStatus === "PAUSED" ? "#FFB300" : "#FF3333",
            fontSize: 8, fontWeight: 600
          }}>
            <span style={{
              width: 5, height: 5, borderRadius: "50%",
              background: missionStatus === "WORKING" ? "#00FF66" : missionStatus === "PAUSED" ? "#FFB300" : "#FF3333",
              boxShadow: `0 0 6px ${missionStatus === "WORKING" ? "#00FF66" : "#FFB300"}`
            }} />
            ● {missionStatus}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 7, color: "var(--text-muted)" }}>{active ? `${fps} FPS` : "OFFLINE"}</span>
          <button onClick={() => setMinimized(true)} style={{ fontSize: 8, background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}>DOCK</button>
        </div>
      </div>

      <div style={{ flex: 1, padding: 10, display: "flex", flexDirection: "column", gap: 8, overflowY: "auto" }}>
        {/* Goal Input Box */}
        <div style={{
          background: "rgba(18,24,33,0.8)", border: "1px solid var(--border)", borderRadius: 6,
          padding: "6px 10px", display: "flex", alignItems: "center", gap: 8
        }}>
          <span style={{ color: "#00FF66", fontSize: 12 }}>🎯</span>
          <input
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitGoal()}
            placeholder="Give JARVIS a goal..."
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: "var(--text-primary)", fontSize: 11, fontFamily: "inherit"
            }}
          />
        </div>

        {/* 2. LIVE JARVIS COMPUTER Frame */}
        <div style={{ background: "#000", border: "1px solid var(--border)", borderRadius: 6, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 8px", background: "rgba(15,20,28,0.95)", fontSize: 8, color: "var(--text-muted)" }}>
            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>LIVE JARVIS COMPUTER</span>
            <div style={{ display: "flex", gap: 4, color: "#00B4D8", fontWeight: 600 }}>
              {appSequence.map((app, idx) => (
                <React.Fragment key={idx}>
                  <span>{app}</span>
                  {idx < appSequence.length - 1 && <span style={{ color: "var(--text-muted)", fontWeight: "normal" }}>→</span>}
                </React.Fragment>
              ))}
            </div>
          </div>
          <div
            style={{ position: "relative", width: "100%", aspectRatio: "16/9", background: "#020408" }}
            tabIndex={0}
            onKeyDown={handleKeyDown}
          >
            <canvas
              ref={canvasRef} width={640} height={360}
              onClick={handleCanvasClick}
              style={{ width: "100%", height: "100%", objectFit: "contain", opacity: active ? 1 : 0.4, cursor: manualControl ? "crosshair" : "default" }}
            />
            {!active && (
              <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6 }}>
                <span style={{ fontSize: 9, color: "var(--text-muted)", letterSpacing: "0.08em" }}>STANDBY MODE</span>
                <button onClick={startStream} style={{ padding: "5px 14px", borderRadius: 4, background: "rgba(0,255,102,0.12)", border: "1px solid rgba(0,255,102,0.3)", color: "#00FF66", fontSize: 9, cursor: "pointer" }}>
                  CONNECT VIRTUAL DESKTOP
                </button>
              </div>
            )}
            <div style={{
              position: "absolute", top: 6, left: 6, padding: "2px 6px", borderRadius: 3,
              fontSize: 7, fontWeight: 700,
              background: manualControl ? "rgba(255,179,0,0.2)" : "rgba(0,0,0,0.7)",
              border: `1px solid ${manualControl ? "rgba(255,179,0,0.4)" : "rgba(255,255,255,0.1)"}`,
              color: manualControl ? "#FFB300" : "#00FF66"
            }}>
              {manualControl ? "HUMAN TAKEOVER" : "AI CONTROL"}
            </div>
          </div>
        </div>

        {/* 3. CURRENTLY */}
        <div>
          <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.1em", color: "var(--text-muted)", marginBottom: 4 }}>CURRENTLY</div>
          <div style={{
            background: "rgba(18,24,33,0.6)", border: "1px solid var(--border)", borderLeft: "2px solid #00FF66",
            borderRadius: 4, padding: "6px 8px", fontSize: 10, display: "flex", alignItems: "center", gap: 6, color: "var(--text-primary)"
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 6px #00FF66" }} />
            {currentAction}
          </div>
        </div>

        {/* 4. PROGRESS */}
        <div>
          <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.1em", color: "var(--text-muted)", marginBottom: 4 }}>PROGRESS</div>
          <div style={{ background: "rgba(18,24,33,0.6)", border: "1px solid var(--border)", borderRadius: 4, padding: "6px 8px", display: "flex", flexDirection: "column", gap: 4, maxHeight: 90, overflowY: "auto" }}>
            {steps.map((s, idx) => {
              const isCompleted = s.status === "completed";
              const isActive = s.status === "running" || s.status === "executing";
              return (
                <div key={idx} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 9, color: isCompleted ? "var(--text-primary)" : isActive ? "#00FF66" : "var(--text-muted)", fontWeight: isActive ? 600 : 400 }}>
                  <span style={{ color: isCompleted ? "#00FF66" : isActive ? "#00FF66" : "var(--text-muted)" }}>
                    {isCompleted ? "✓" : isActive ? "●" : "○"}
                  </span>
                  <span>{s.description}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 5. Control Actions: [ PAUSE ] [ TAKE CONTROL ] [ STOP ] */}
        <div style={{ display: "flex", gap: 6, marginTop: "auto", paddingTop: 4 }}>
          <button onClick={togglePause} style={{
            flex: 1, padding: "6px 0", borderRadius: 4, border: "1px solid rgba(255,179,0,0.3)",
            background: "rgba(255,179,0,0.08)", color: "#FFB300", fontSize: 9, fontWeight: 700, cursor: "pointer"
          }}>
            {missionStatus === "PAUSED" ? "RESUME" : "PAUSE"}
          </button>
          <button onClick={toggleManualControl} style={{
            flex: 1, padding: "6px 0", borderRadius: 4,
            border: manualControl ? "1px solid rgba(255,179,0,0.5)" : "1px solid rgba(0,255,102,0.3)",
            background: manualControl ? "rgba(255,179,0,0.2)" : "rgba(0,255,102,0.08)",
            color: manualControl ? "#FFB300" : "#00FF66", fontSize: 9, fontWeight: 700, cursor: "pointer"
          }}>
            {manualControl ? "RETURN TO JARVIS" : "TAKE CONTROL"}
          </button>
          <button onClick={stopStream} style={{
            flex: 1, padding: "6px 0", borderRadius: 4, border: "1px solid rgba(255,51,51,0.3)",
            background: "rgba(255,51,51,0.08)", color: "#FF3333", fontSize: 9, fontWeight: 700, cursor: "pointer"
          }}>
            STOP
          </button>
        </div>
      </div>
    </div>
  );
}
