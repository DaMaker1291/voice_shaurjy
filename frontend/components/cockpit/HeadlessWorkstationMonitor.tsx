"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { BASE, safeJson } from "@/lib/api";

interface HeadlessSession {
  session_id: string;
  display_id: number;
  resolution: string;
  state: string;
  pid: number | null;
  launched_apps: string[];
  uptime: number;
  platform: string;
  error: string | null;
}

export default function HeadlessWorkstationMonitor() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [session, setSession] = useState<HeadlessSession | null>(null);
  const [currentTask, setCurrentTask] = useState<string>("");
  const [fps, setFps] = useState(0);
  const frameCountRef = useRef(0);
  const lastFpsTime = useRef(Date.now());
  const [launchApp, setLaunchApp] = useState("");
  const [launchCmd, setLaunchCmd] = useState("");
  const [error, setError] = useState("");

  const base = BASE;
  const wsBase = base.replace("http", "ws");

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    try {
      const ws = new WebSocket(`${wsBase}/api/headless/ws/stream`);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => { setConnected(false); setTimeout(connectWs, 3000); };
      ws.onerror = () => setConnected(false);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "frame" && msg.data) {
            const canvas = canvasRef.current;
            if (!canvas) return;
            const ctx = canvas.getContext("2d");
            if (!ctx) return;
            const bytes = Uint8Array.from(atob(msg.data), c => c.charCodeAt(0));
            const blob = new Blob([bytes], { type: "image/png" });
            const img = new Image();
            img.onload = () => {
              ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
              URL.revokeObjectURL(img.src);
            };
            img.src = URL.createObjectURL(blob);
            frameCountRef.current++;
            const now = Date.now();
            if (now - lastFpsTime.current >= 1000) {
              setFps(frameCountRef.current);
              frameCountRef.current = 0;
              lastFpsTime.current = now;
            }
          } else if (msg.type === "status") {
            setSession(prev => prev ? { ...prev, state: msg.state } : null);
          }
        } catch {}
      };
    } catch {}
  }, [wsBase]);

  useEffect(() => { connectWs(); return () => { wsRef.current?.close(); }; }, [connectWs]);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${base}/api/headless/status`);
        const data = await safeJson(res);
        if (data.sessions?.length > 0) setSession(data.sessions[0]);
        else if (data.session) setSession(data.session);
      } catch {}
    };
    poll();
    const i = setInterval(poll, 5000);
    return () => clearInterval(i);
  }, [base]);

  const sendWs = useCallback((cmd: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(cmd));
  }, []);

  const startSession = async () => {
    setError("");
    try {
      const res = await fetch(`${base}/api/headless/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: "default" }) });
      const data = await safeJson(res);
      if (data.ok) setSession(data.session);
      else setError(data.error || data.install_hint || "Failed to start");
    } catch (e: any) { setError(e.message); }
  };

  const stopSession = async () => {
    try {
      await fetch(`${base}/api/headless/stop?session_id=default`, { method: "POST" });
      setSession(null);
    } catch {}
  };

  const handleLaunch = async () => {
    if (!launchApp.trim()) return;
    setError("");
    const cmd = launchCmd.trim().split(/\s+/);
    try {
      const res = await fetch(`${base}/api/headless/launch`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: "default", app_name: launchApp, command: cmd.length ? cmd : [launchApp] }),
      });
      const data = await safeJson(res);
      if (data.ok) { setLaunchApp(""); setLaunchCmd(""); setCurrentTask(`Running: ${launchApp}`); }
      else setError(data.error || "Launch failed");
    } catch (e: any) { setError(e.message); }
  };

  const isRunning = session?.state === "running";

  return (
    <div style={{
      background: "linear-gradient(135deg, #0d0f12 0%, #12151a 100%)",
      border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden",
      display: "flex", flexDirection: "column", height: "100%",
    }}>
      {/* Header bar */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px", borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
            background: isRunning ? "#00FF66" : connected ? "#FFB300" : "#FF3333",
            boxShadow: `0 0 6px ${isRunning ? "rgba(0,255,102,0.5)" : connected ? "rgba(255,179,0,0.4)" : "rgba(255,51,51,0.4)"}`,
            animation: isRunning ? "glow-pulse 1.5s ease-in-out infinite" : "none",
          }} />
          <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.08em" }}>
            JARVIS // HEADLESS_WORKSTATION_VIEW
          </span>
          {session && (
            <span style={{
              fontSize: 7, padding: "1px 6px", borderRadius: 3,
              background: isRunning ? "rgba(0,255,102,0.1)" : "rgba(255,51,51,0.1)",
              border: `1px solid ${isRunning ? "rgba(0,255,102,0.2)" : "rgba(255,51,51,0.2)"}`,
              color: isRunning ? "#00FF66" : "#FF3333", fontFamily: "var(--font-mono)",
            }}>
              {isRunning ? "BACKGROUND_EXECUTION_ACTIVE" : session.state.toUpperCase()}
            </span>
          )}
        </div>
        <span style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
          {isRunning ? `${fps} FPS` : "---"}
        </span>
      </div>

      {/* Canvas viewport */}
      <div style={{ flex: 1, position: "relative", background: "#000", minHeight: 0 }}>
        <canvas ref={canvasRef} width={960} height={540}
          style={{ width: "100%", height: "100%", objectFit: "contain", opacity: isRunning ? 1 : 0.3 }} />

        {!isRunning && (
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <div style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-muted)", letterSpacing: "0.1em", textAlign: "center" }}>
              {connected ? "NO ACTIVE VIRTUAL DISPLAY" : "CONNECTING TO RELAY..."}
            </div>
            <button onClick={startSession} style={{
              padding: "8px 20px", borderRadius: 4,
              background: "var(--neon-green-dim)", border: "1px solid rgba(0,255,102,0.2)",
              color: "var(--neon-green)", fontFamily: "var(--font-mono)",
              fontSize: 9, cursor: "pointer", letterSpacing: "0.06em",
            }}>
              PROVISION VIRTUAL DISPLAY (:1)
            </button>
            {error && (
              <div style={{ fontSize: 8, fontFamily: "var(--font-mono)", color: "#FF3333", textAlign: "center", maxWidth: 300 }}>
                {error}
              </div>
            )}
          </div>
        )}

        {isRunning && currentTask && (
          <div style={{
            position: "absolute", top: 8, right: 8,
            padding: "4px 8px", borderRadius: 4,
            background: "rgba(0,0,0,0.75)", backdropFilter: "blur(8px)",
            border: "1px solid rgba(0,255,102,0.2)",
          }}>
            <span style={{ fontSize: 8, fontFamily: "var(--font-mono)", color: "#00FF66" }}>{currentTask}</span>
          </div>
        )}
      </div>

      {/* Session info bar */}
      {session && (
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "6px 12px", borderTop: "1px solid var(--border)",
          fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>DISPLAY :{session.display_id}</span>
            <span>{session.resolution}</span>
            <span>{session.platform}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {session.launched_apps.length > 0 && (
              <span style={{ color: "#00B4D8" }}>{session.launched_apps.length} APPS</span>
            )}
            <span>UPTIME {Math.floor(session.uptime)}s</span>
          </div>
        </div>
      )}

      {/* App launcher */}
      {isRunning && (
        <div style={{ padding: "8px 12px", borderTop: "1px solid var(--border)" }}>
          <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
            <input
              value={launchApp} onChange={e => setLaunchApp(e.target.value)}
              placeholder="App name" onKeyDown={e => e.key === "Enter" && handleLaunch()}
              style={{
                flex: 1, padding: "4px 8px", borderRadius: 3, border: "1px solid var(--border)",
                background: "var(--surface)", color: "var(--text-primary)", fontSize: 9,
                fontFamily: "var(--font-mono)", outline: "none",
              }}
            />
            <input
              value={launchCmd} onChange={e => setLaunchCmd(e.target.value)}
              placeholder="Command (optional)" onKeyDown={e => e.key === "Enter" && handleLaunch()}
              style={{
                flex: 2, padding: "4px 8px", borderRadius: 3, border: "1px solid var(--border)",
                background: "var(--surface)", color: "var(--text-primary)", fontSize: 9,
                fontFamily: "var(--font-mono)", outline: "none",
              }}
            />
            <button onClick={handleLaunch} style={{
              padding: "4px 10px", borderRadius: 3, border: "1px solid rgba(0,255,102,0.2)",
              background: "var(--neon-green-dim)", color: "var(--neon-green)",
              fontSize: 8, fontFamily: "var(--font-mono)", cursor: "pointer",
            }}>
              LAUNCH
            </button>
          </div>
          {/* Quick launch buttons */}
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {[
              { name: "Chrome", cmd: "google-chrome --headless" },
              { name: "Excel", cmd: "libreoffice --calc --norestore" },
              { name: "Terminal", cmd: "xterm" },
              { name: "Blender", cmd: "blender --background" },
            ].map(app => (
              <button key={app.name} onClick={() => { setLaunchApp(app.name); setLaunchCmd(app.cmd); }}
                style={{
                  padding: "2px 6px", borderRadius: 2, border: "1px solid var(--border)",
                  background: "var(--surface-raised)", color: "var(--text-muted)",
                  fontSize: 7, fontFamily: "var(--font-mono)", cursor: "pointer",
                }}>
                {app.name}
              </button>
            ))}
          </div>
          {isRunning && (
            <button onClick={stopSession} style={{
              marginTop: 6, width: "100%", padding: "4px 0", borderRadius: 3,
              border: "1px solid rgba(255,51,51,0.2)", background: "rgba(255,51,51,0.08)",
              color: "#FF3333", fontSize: 8, fontFamily: "var(--font-mono)", cursor: "pointer",
            }}>
              STOP VIRTUAL DISPLAY
            </button>
          )}
        </div>
      )}
    </div>
  );
}
