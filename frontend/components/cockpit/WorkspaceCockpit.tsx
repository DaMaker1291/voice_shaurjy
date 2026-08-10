"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { BASE, safeJson } from "@/lib/api";
import MissionTree from "./MissionTree";
import type { MissionNode } from "./MissionTree";
import TelemetryPanel from "./TelemetryPanel";
import ApprovalOverlay from "./ApprovalOverlay";
import InterceptBar from "./InterceptBar";

interface Workspace {
  id: string;
  name: string;
  status: string;
  display_id: number;
  resolution: number[];
  uptime: number;
  apps: { name: string; status: string; pid: number }[];
  current_action: string;
  agent_status: string;
}

interface Step {
  number: number;
  action: string;
  description: string;
  status: string;
  requires_approval: boolean;
  params?: any;
  error?: string;
  screenshot_after?: string;
}

interface Mission {
  id: string;
  objective: string;
  status: string;
  steps: Step[];
  progress: number;
  current_action: string;
}

interface Approval {
  mission_id: string;
  objective: string;
  step: { number: number; action: string; description: string; params: any };
  workspace_id: string;
}

function stepsToTree(steps: Step[], objective: string): MissionNode[] {
  if (!steps.length) return [];
  const groups: Record<string, MissionNode> = {};
  const order = ["research", "plan", "setup", "build", "test", "deploy", "verify"];

  for (const step of steps) {
    const action = step.action || "build";
    if (!groups[action]) {
      groups[action] = {
        id: action,
        label: action.charAt(0).toUpperCase() + action.slice(1),
        status: "pending",
        children: [],
      };
    }
    const nodeStatus: MissionNode["status"] =
      step.status === "completed" ? "done" :
      step.status === "running" ? "active" :
      step.status === "failed" ? "error" : "pending";

    groups[action].children!.push({
      id: `step-${step.number}`,
      label: step.description || `Step ${step.number}`,
      status: nodeStatus,
      evidence: step.error ? [{ check: "Error", passed: false, detail: step.error }] : undefined,
    });
  }

  const result: MissionNode[] = [];
  for (const key of order) {
    if (groups[key]) {
      const children = groups[key].children!;
      const doneCount = children.filter(c => c.status === "done").length;
      groups[key].status =
        doneCount === children.length ? "done" :
        children.some(c => c.status === "active") ? "active" :
        children.some(c => c.status === "error") ? "error" : "pending";
      groups[key].progress = children.length > 0 ? (doneCount / children.length) * 100 : 0;
      result.push(groups[key]);
    }
  }

  for (const [key, node] of Object.entries(groups)) {
    if (!order.includes(key)) result.push(node);
  }

  return result;
}

export default function WorkspaceCockpit() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [activeTab, setActiveTab] = useState<"cockpit" | "plan" | "timeline" | "workspace" | "capabilities" | "artifacts" | "settings">("cockpit");
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [currentAction, setCurrentAction] = useState("");
  const [actionWhy, setActionWhy] = useState("");
  const [activeApp, setActiveApp] = useState("");
  const [activeTool, setActiveTool] = useState("");
  const [connected, setConnected] = useState(false);
  const [active, setActive] = useState(false);
  const [fps, setFps] = useState(0);
  const [interactive, setInteractive] = useState(false);
  const [missionObjective, setMissionObjective] = useState("");
  const [showMissionInput, setShowMissionInput] = useState(false);
  const [error, setError] = useState("");
  const [showCompletionScreen, setShowCompletionScreen] = useState(false);
  const [completionStats, setCompletionStats] = useState({ actions: 0, recoveries: 0, verifications: 0, duration: "" });
  const [autonomyLevel, setAutonomyLevel] = useState(75);
  const [cursorPos, setCursorPos] = useState({ x: 320, y: 180, clicking: false });
  const [recentActivity, setRecentActivity] = useState<{ time: string; text: string; type: string }[]>([]);

  const frameCountRef = useRef(0);
  const lastFpsTime = useRef(Date.now());
  const base = BASE;
  const wsBase = base.replace("http", "ws");

  const activeMission = missions.length > 0 ? missions[missions.length - 1] : null;
  const treeData = activeMission ? stepsToTree(activeMission.steps, activeMission.objective) : [];

  useEffect(() => {
    if (!active) return;
    const interval = setInterval(() => {
      setCursorPos(prev => ({
        x: Math.min(Math.max(prev.x + (Math.random() - 0.5) * 40, 50), 900),
        y: Math.min(Math.max(prev.y + (Math.random() - 0.5) * 30, 40), 500),
        clicking: Math.random() > 0.75,
      }));
    }, 1200);
    return () => clearInterval(interval);
  }, [active]);

  const addActivity = useCallback((text: string, type: string = "success") => {
    const now = new Date();
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    setRecentActivity(prev => [...prev.slice(-12), { time, text, type }]);
  }, []);

  const startWorkspace = async () => {
    setError("");
    try {
      const res = await fetch(`${base}/api/workspace/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "JARVIS Workspace", width: 1920, height: 1080 }),
      });
      const data = await safeJson(res);
      if (data.ok) {
        const wsId = data.workspace.id;
        const startRes = await fetch(`${base}/api/workspace/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace_id: wsId }),
        });
        const startData = await safeJson(startRes);
        if (startData.ok) {
          setWorkspace(startData.workspace);
          setActive(true);
          addActivity("Workspace provisioned", "success");
          connectWs(wsId);
        }
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  const stopWorkspace = async () => {
    if (!workspace) return;
    try {
      await fetch(`${base}/api/workspace/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: workspace.id }),
      });
      setActive(false);
      setWorkspace(null);
      wsRef.current?.close();
      setConnected(false);
      addActivity("Workspace stopped", "warning");
    } catch {}
  };

  const startMission = async () => {
    if (!missionObjective.trim()) return;
    try {
      const res = await fetch(`${base}/api/workspace/mission/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective: missionObjective.trim(), workspace_id: workspace?.id || "default" }),
      });
      const data = await safeJson(res);
      if (data.ok) {
        const planRes = await fetch(`${base}/api/workspace/mission/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mission_id: data.mission.id }),
        });
        const planData = await safeJson(planRes);
        if (planData.ok) {
          setMissions(prev => [...prev, planData.mission]);
          setShowMissionInput(false);
          addActivity(`Mission started: ${missionObjective.slice(0, 40)}...`, "active");
          setMissionObjective("");
        }
      }
    } catch {}
  };

  const pauseMission = async (missionId: string) => {
    try {
      await fetch(`${base}/api/workspace/mission/pause`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mission_id: missionId }),
      });
      setMissions(prev => prev.map(m => m.id === missionId ? { ...m, status: "paused" } : m));
      addActivity("Mission paused", "warning");
    } catch {}
  };

  const resumeMission = async (missionId: string) => {
    try {
      await fetch(`${base}/api/workspace/mission/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mission_id: missionId }),
      });
      setMissions(prev => prev.map(m => m.id === missionId ? { ...m, status: "executing" } : m));
      addActivity("Mission resumed", "success");
    } catch {}
  };

  const stopMission = async (missionId: string) => {
    try {
      await fetch(`${base}/api/workspace/mission/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mission_id: missionId }),
      });
      setMissions(prev => prev.map(m => m.id === missionId ? { ...m, status: "stopped" } : m));
      addActivity("Mission stopped", "warning");
    } catch {}
  };

  const approveAction = async (missionId: string, stepNumber: number) => {
    try {
      await fetch(`${base}/api/workspace/approvals/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mission_id: missionId, step_number: stepNumber }),
      });
      setPendingApprovals(prev => prev.filter(a => !(a.mission_id === missionId && a.step.number === stepNumber)));
      addActivity(`Step ${stepNumber} approved`, "success");
    } catch {}
  };

  const denyAction = async (missionId: string, stepNumber: number) => {
    try {
      await fetch(`${base}/api/workspace/approvals/deny`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mission_id: missionId, step_number: stepNumber }),
      });
      setPendingApprovals(prev => prev.filter(a => !(a.mission_id === missionId && a.step.number === stepNumber)));
      addActivity(`Step ${stepNumber} denied`, "warning");
    } catch {}
  };

  const connectWs = useCallback((wsId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    try {
      const ws = new WebSocket(`${wsBase}/api/workspace/ws/stream?workspace_id=${wsId}&fps=15&quality=70`);
      wsRef.current = ws;
      ws.onopen = () => { setConnected(true); addActivity("Workspace stream connected", "success"); };
      ws.onclose = () => {
        setConnected(false);
        if (active) setTimeout(() => connectWs(wsId), 3000);
      };
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
              ctx.clearRect(0, 0, canvas.width, canvas.height);
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
          } else if (msg.type === "status") {
            if (msg.workspace) setWorkspace(msg.workspace);
            if (msg.missions) setMissions(msg.missions);
          } else if (msg.type === "mission_event") {
            if (msg.event === "approval_needed") {
              setPendingApprovals(prev => [...prev, {
                mission_id: msg.mission_id,
                objective: msg.data?.objective || "",
                step: msg.data,
                workspace_id: workspace?.id || "",
              }]);
              addActivity(`Approval needed: ${msg.data?.description || "action"}`, "warning");
            }
            if (msg.event === "step_start") {
              setCurrentAction(msg.data?.description || "");
              addActivity(`Starting: ${msg.data?.description || "step"}`, "active");
            }
            if (msg.event === "step_complete") {
              addActivity(`Completed: ${msg.data?.description || "step"}`, "success");
            }
            if (msg.event === "step_error") {
              addActivity(`Failed: ${msg.data?.error || "step"}`, "error");
            }
            if (msg.event === "recovering") {
              addActivity(`Self-healing: ${msg.data?.evidence || "attempting recovery"}`, "warning");
            }
            if (msg.event === "completed") {
              setShowCompletionScreen(true);
              setCompletionStats({
                actions: activeMission?.steps?.length || 0,
                recoveries: 0,
                verifications: activeMission?.steps?.length || 0,
                duration: "—",
              });
              addActivity("Mission complete", "success");
            }
          }
        } catch {}
      };
    } catch {}
  }, [wsBase, active, workspace?.id]);

  useEffect(() => { return () => { wsRef.current?.close(); }; }, []);

  const sendWs = useCallback((cmd: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!interactive || !active || !workspace) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * (workspace.resolution[0] || 1920));
    const y = Math.round(((e.clientY - rect.top) / rect.height) * (workspace.resolution[1] || 1080));
    sendWs({ cmd: "click", x, y, button: e.button === 2 ? 3 : 1 });
  };

  const firstApproval = pendingApprovals[0];

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100%", background: "#05070a",
      color: "#f0f6fc", fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)", overflow: "hidden"
    }}>
      {/* Top Navigation Bar */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "6px 12px", borderBottom: "1px solid rgba(0,255,102,0.15)", background: "rgba(13,17,23,0.95)",
        flexShrink: 0
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 10px #00FF66" }} />
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#fff" }}>JARVIS</span>
          </div>
          <span style={{ fontSize: 10, color: "var(--text-muted, #8b949e)" }}>|</span>
          <span style={{ fontSize: 10, color: "#fff", fontWeight: 600 }}>{activeMission?.objective || "No active mission"}</span>
          {active && (
            <span style={{
              fontSize: 8, padding: "2px 6px", borderRadius: 4, background: "rgba(0,255,102,0.12)",
              border: "1px solid rgba(0,255,102,0.3)", color: "#00FF66"
            }}>● LIVE</span>
          )}
          {activeMission && (
            <span style={{ fontSize: 9, color: "#00FF66", fontWeight: 700 }}>{Math.round((activeMission.progress || 0) * 100)}%</span>
          )}
        </div>

        <div style={{ display: "flex", gap: 4 }}>
          {([
            { id: "cockpit", label: "COCKPIT" },
            { id: "plan", label: "PLAN" },
            { id: "timeline", label: "TIMELINE" },
            { id: "capabilities", label: "CAPABILITIES" },
            { id: "settings", label: "SETTINGS" },
          ] as const).map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              style={{
                padding: "3px 8px", borderRadius: 4, fontSize: 8, fontWeight: 700, letterSpacing: "0.05em",
                background: activeTab === t.id ? "rgba(0,255,102,0.15)" : "transparent",
                border: `1px solid ${activeTab === t.id ? "rgba(0,255,102,0.4)" : "transparent"}`,
                color: activeTab === t.id ? "#00FF66" : "var(--text-muted, #8b949e)", cursor: "pointer"
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Cockpit Tab — The Live Mission View */}
      {activeTab === "cockpit" && (
        <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
          {/* Left: Mission Tree */}
          <div style={{ width: 240, borderRight: "1px solid rgba(255,255,255,0.08)", flexShrink: 0, overflowY: "auto" }}>
            <MissionTree
              mission={activeMission?.objective || ""}
              objective={activeMission?.current_action || ""}
              tree={treeData}
            />
            <div style={{ padding: "0 12px 12px" }}>
              <button onClick={() => setShowMissionInput(true)} style={{
                width: "100%", padding: "6px 0", borderRadius: 4,
                background: "rgba(0,255,102,0.12)", border: "1px solid rgba(0,255,102,0.3)",
                color: "#00FF66", fontSize: 9, fontWeight: 700, cursor: "pointer"
              }}>+ NEW MISSION</button>
            </div>
          </div>

          {/* Center: Live Workspace Stream */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#000", position: "relative", minWidth: 0 }}>
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "4px 10px", background: "rgba(15,20,28,0.95)", borderBottom: "1px solid rgba(255,255,255,0.08)", fontSize: 8
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontWeight: 700, color: "#fff" }}>LIVE JARVIS WORKSPACE</span>
                {workspace?.apps && workspace.apps.length > 0 && (
                  <>
                    <span style={{ color: "#8b949e" }}>|</span>
                    <div style={{ display: "flex", gap: 4, color: "#00B4D8", fontWeight: 600 }}>
                      {workspace.apps.slice(0, 3).map((app, i) => (
                        <React.Fragment key={i}>
                          {i > 0 && <span style={{ color: "#8b949e" }}>→</span>}
                          <span>{app.name}</span>
                        </React.Fragment>
                      ))}
                    </div>
                  </>
                )}
              </div>
              <div style={{ display: "flex", gap: 6, color: "#8b949e" }}>
                {fps > 0 && <span style={{ color: "#00FF66" }}>{fps} FPS</span>}
                <span>{connected ? "● CONNECTED" : "○ OFFLINE"}</span>
              </div>
            </div>

            <div style={{ flex: 1, position: "relative", background: "#020408", outline: "none" }} tabIndex={0}>
              <canvas
                ref={canvasRef} width={960} height={540}
                onClick={handleCanvasClick}
                style={{ width: "100%", height: "100%", objectFit: "contain", opacity: active ? 1 : 0.4, cursor: interactive ? "crosshair" : "default" }}
              />

              {!active && (
                <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 10 }}>
                  <span style={{ fontSize: 10, color: "#8b949e", letterSpacing: "0.1em" }}>VIRTUAL WORKSPACE OFFLINE</span>
                  <button onClick={startWorkspace} style={{
                    padding: "8px 18px", borderRadius: 4, background: "rgba(0,255,102,0.15)",
                    border: "1px solid rgba(0,255,102,0.3)", color: "#00FF66", fontSize: 9, fontWeight: 700, cursor: "pointer"
                  }}>
                    PROVISION WORKSPACE
                  </button>
                  {error && <span style={{ fontSize: 8, color: "#FF3333" }}>{error}</span>}
                </div>
              )}

              {active && !interactive && (
                <div style={{
                  position: "absolute", left: `${(cursorPos.x / 960) * 100}%`, top: `${(cursorPos.y / 540) * 100}%`,
                  pointerEvents: "none", transition: "all 0.8s cubic-bezier(0.16, 1, 0.3, 1)"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: "50%", background: "#00FF66",
                      boxShadow: "0 0 12px #00FF66", transform: cursorPos.clicking ? "scale(1.5)" : "scale(1)",
                      transition: "transform 0.15s ease"
                    }} />
                    <span style={{ fontSize: 7, fontWeight: 700, color: "#00FF66", background: "rgba(0,0,0,0.8)", padding: "1px 4px", borderRadius: 2 }}>JARVIS</span>
                  </div>
                </div>
              )}

              <div style={{
                position: "absolute", bottom: 8, left: 8,
                padding: "3px 8px", borderRadius: 3, fontSize: 7, fontWeight: 700,
                background: interactive ? "rgba(255,179,0,0.2)" : "rgba(0,0,0,0.8)",
                border: `1px solid ${interactive ? "rgba(255,179,0,0.4)" : "rgba(255,255,255,0.1)"}`,
                color: interactive ? "#FFB300" : "#00FF66"
              }}>
                {interactive ? "HUMAN TAKEOVER ACTIVE" : "AI AUTONOMOUS EXECUTION"}
              </div>
            </div>
          </div>

          {/* Right: Intelligence + Activity */}
          <div style={{ width: 280, borderLeft: "1px solid rgba(255,255,255,0.08)", padding: 10, display: "flex", flexDirection: "column", gap: 10, flexShrink: 0, overflowY: "auto" }}>
            <div>
              <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.1em", color: "#8b949e", marginBottom: 4 }}>CURRENT ACTION</div>
              <div style={{ fontSize: 10, fontWeight: 600, color: "#00FF66", display: "flex", alignItems: "center", gap: 6 }}>
                {currentAction ? (
                  <>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 6px #00FF66" }} />
                    {currentAction}
                  </>
                ) : (
                  <span style={{ color: "#8b949e", fontWeight: 400 }}>Idle</span>
                )}
              </div>
            </div>

            {actionWhy && (
              <div>
                <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.1em", color: "#8b949e", marginBottom: 4 }}>WHY</div>
                <div style={{ fontSize: 9, color: "var(--text-muted, #8b949e)", lineHeight: 1.4 }}>{actionWhy}</div>
              </div>
            )}

            <div style={{ display: "flex", gap: 6 }}>
              {activeApp && (
                <div style={{ flex: 1, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", padding: 6, borderRadius: 4 }}>
                  <div style={{ fontSize: 7, color: "#8b949e" }}>APPLICATION</div>
                  <div style={{ fontSize: 9, color: "#00B4D8", fontWeight: 600, marginTop: 2 }}>{activeApp}</div>
                </div>
              )}
              {activeTool && (
                <div style={{ flex: 1, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", padding: 6, borderRadius: 4 }}>
                  <div style={{ fontSize: 7, color: "#8b949e" }}>TOOL</div>
                  <div style={{ fontSize: 9, color: "#00FF66", fontWeight: 600, marginTop: 2 }}>{activeTool}</div>
                </div>
              )}
            </div>

            <div style={{ height: 1, background: "rgba(255,255,255,0.08)" }} />

            <div>
              <div style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.1em", color: "#8b949e", marginBottom: 6 }}>RECENT ACTIVITY</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {recentActivity.length === 0 && (
                  <div style={{ fontSize: 8, color: "#333" }}>No activity yet</div>
                )}
                {recentActivity.map((act, i) => (
                  <div key={i} style={{
                    fontSize: 8, padding: "4px 6px", borderRadius: 3,
                    background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)",
                    display: "flex", gap: 6,
                    color: act.type === "warning" ? "#FFB300" : act.type === "error" ? "#FF3333" : act.type === "active" ? "#00FF66" : "#8b949e"
                  }}>
                    <span style={{ color: "#8b949e" }}>{act.time}</span>
                    <span style={{ flex: 1 }}>{act.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Plan Tab — Mission Decomposition Tree */}
      {activeTab === "plan" && (
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <div style={{ width: 320, borderRight: "1px solid rgba(255,255,255,0.08)", overflowY: "auto" }}>
            <MissionTree
              mission={activeMission?.objective || ""}
              objective={activeMission?.current_action || ""}
              tree={treeData}
            />
          </div>
          <div style={{ flex: 1, padding: 16, overflowY: "auto" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#fff", marginBottom: 12 }}>MISSION DECOMPOSITION</div>
            {!activeMission && (
              <div style={{ fontSize: 10, color: "#8b949e" }}>
                Start a mission to see the decomposition tree.
                JARVIS will break your objective into phases, assign agents, and track progress.
              </div>
            )}
            {activeMission && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {activeMission.steps.map(step => (
                  <div key={step.number} style={{
                    padding: "8px 12px", borderRadius: 4,
                    background: step.status === "running" ? "rgba(0,255,102,0.06)" : "rgba(255,255,255,0.02)",
                    border: `1px solid ${step.status === "running" ? "rgba(0,255,102,0.2)" : step.status === "failed" ? "rgba(255,51,51,0.2)" : "rgba(255,255,255,0.05)"}`,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 8, color: step.status === "completed" ? "#00FF66" : step.status === "running" ? "#FFB300" : step.status === "failed" ? "#FF3333" : "#8b949e" }}>
                        {step.status === "completed" ? "✓" : step.status === "running" ? "●" : step.status === "failed" ? "✗" : "○"}
                      </span>
                      <span style={{ fontSize: 9, color: step.status === "running" ? "#fff" : "#ccc", fontWeight: step.status === "running" ? 600 : 400 }}>
                        {step.description}
                      </span>
                      {step.requires_approval && (
                        <span style={{ fontSize: 7, padding: "1px 4px", borderRadius: 2, background: "rgba(255,179,0,0.15)", color: "#FFB300" }}>APPROVAL</span>
                      )}
                    </div>
                    {step.error && (
                      <div style={{ fontSize: 8, color: "#FF3333", marginTop: 4, paddingLeft: 16 }}>{step.error}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Timeline Tab */}
      {activeTab === "timeline" && (
        <div style={{ flex: 1, padding: 16, overflowY: "auto" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#fff", marginBottom: 12 }}>MISSION TIMELINE</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {recentActivity.length === 0 && (
              <div style={{ fontSize: 10, color: "#8b949e" }}>No events yet</div>
            )}
            {recentActivity.map((act, i) => (
              <div key={i} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                <div style={{ width: 50, fontSize: 9, color: "#8b949e", textAlign: "right", flexShrink: 0 }}>{act.time}</div>
                <div style={{ width: 8, display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                  <div style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: act.type === "success" ? "#00FF66" : act.type === "warning" ? "#FFB300" : act.type === "error" ? "#FF3333" : act.type === "active" ? "#00B4D8" : "#8b949e",
                  }} />
                  {i < recentActivity.length - 1 && <div style={{ width: 1, flex: 1, background: "rgba(255,255,255,0.06)", marginTop: 4 }} />}
                </div>
                <div style={{ fontSize: 9, color: "#ccc", flex: 1 }}>{act.text}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Capabilities Tab */}
      {activeTab === "capabilities" && (
        <div style={{ flex: 1, overflow: "hidden" }}>
          <TelemetryPanel />
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === "settings" && (
        <div style={{ flex: 1, padding: 16, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16, maxWidth: 600 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>JARVIS SYSTEM SETTINGS</div>

          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: "#fff", marginBottom: 6 }}>AUTONOMY LEVEL</div>
            <input
              type="range" min="0" max="100" value={autonomyLevel}
              onChange={e => setAutonomyLevel(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 8, color: "#8b949e", marginTop: 4 }}>
              <span>CAUTIOUS</span>
              <span style={{ color: "#00FF66", fontWeight: 700 }}>BALANCED ({autonomyLevel}%)</span>
              <span>FULL AUTONOMY</span>
            </div>
          </div>

          <div style={{ height: 1, background: "rgba(255,255,255,0.08)" }} />

          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: "#fff", marginBottom: 6 }}>APPROVAL GATES</div>
            {["Financial transactions", "External communication", "Purchases & subscriptions", "System credential modifications", "Data deletion"].map(rule => (
              <label key={rule} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 9, color: "#f0f6fc", marginBottom: 6, cursor: "pointer" }}>
                <input type="checkbox" defaultChecked />
                {rule}
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Bottom Controls Toolbar */}
      <div style={{
        padding: "6px 12px", borderTop: "1px solid rgba(255,255,255,0.08)", background: "rgba(13,17,23,0.95)",
        display: "flex", gap: 8, flexShrink: 0
      }}>
        {activeMission && (
          <>
            <button onClick={() => activeMission.status === "paused" ? resumeMission(activeMission.id) : pauseMission(activeMission.id)} style={{
              flex: 1, padding: "6px 0", borderRadius: 4, border: "1px solid rgba(255,179,0,0.3)",
              background: "rgba(255,179,0,0.08)", color: "#FFB300", fontSize: 9, fontWeight: 700, cursor: "pointer"
            }}>
              {activeMission.status === "paused" ? "▶ RESUME" : "Ⅱ PAUSE"}
            </button>
            <button onClick={() => setInteractive(!interactive)} style={{
              flex: 2, padding: "6px 0", borderRadius: 4,
              border: interactive ? "1px solid rgba(255,179,0,0.5)" : "1px solid rgba(0,255,102,0.3)",
              background: interactive ? "rgba(255,179,0,0.2)" : "rgba(0,255,102,0.08)",
              color: interactive ? "#FFB300" : "#00FF66", fontSize: 9, fontWeight: 700, cursor: "pointer"
            }}>
              {interactive ? "RETURN CONTROL TO JARVIS" : "TAKE CONTROL"}
            </button>
            <button onClick={() => stopMission(activeMission.id)} style={{
              flex: 1, padding: "6px 0", borderRadius: 4, border: "1px solid rgba(255,51,51,0.3)",
              background: "rgba(255,51,51,0.08)", color: "#FF3333", fontSize: 9, fontWeight: 700, cursor: "pointer"
            }}>
              ■ STOP
            </button>
          </>
        )}
        {!activeMission && (
          <div style={{ flex: 1, textAlign: "center", fontSize: 9, color: "#8b949e", padding: "6px 0" }}>
            No active mission — start one from the cockpit or use the orb
          </div>
        )}
      </div>

      {/* Approval Overlay — High-risk action gate */}
      {firstApproval && (
        <ApprovalOverlay
          action={firstApproval.step.description || firstApproval.step.action}
          details={{
            Mission: firstApproval.objective.slice(0, 60),
            Step: String(firstApproval.step.number),
            Action: firstApproval.step.action,
          }}
          onApprove={() => approveAction(firstApproval.mission_id, firstApproval.step.number)}
          onDeny={() => denyAction(firstApproval.mission_id, firstApproval.step.number)}
          holdDuration={1.5}
        />
      )}

      {/* InterceptBar — Laser gate for critical actions */}
      <InterceptBar
        onApprove={(id) => addActivity(`Action ${id} approved`, "success")}
        onDeny={(id) => addActivity(`Action ${id} denied`, "warning")}
      />

      {/* Mission Input Modal */}
      {showMissionInput && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", backdropFilter: "blur(4px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 999 }}>
          <div style={{ background: "#0d1117", border: "1px solid rgba(0,255,102,0.3)", borderRadius: 8, padding: 20, width: 420, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#fff" }}>NEW MISSION</div>
            <div style={{ fontSize: 9, color: "#8b949e" }}>Describe what you want JARVIS to accomplish</div>
            <textarea
              value={missionObjective}
              onChange={e => setMissionObjective(e.target.value)}
              placeholder="e.g. Build a landing page for my startup"
              style={{
                width: "100%", height: 80, borderRadius: 6, border: "1px solid rgba(255,255,255,0.1)",
                background: "rgba(255,255,255,0.03)", color: "#fff", padding: 10,
                fontFamily: "var(--font-mono)", fontSize: 10, resize: "none",
              }}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); startMission(); } }}
            />
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => setShowMissionInput(false)} style={{
                flex: 1, padding: "8px 0", borderRadius: 4, border: "1px solid rgba(255,255,255,0.1)",
                background: "transparent", color: "#8b949e", fontSize: 9, cursor: "pointer"
              }}>CANCEL</button>
              <button onClick={startMission} style={{
                flex: 2, padding: "8px 0", borderRadius: 4, border: "1px solid rgba(0,255,102,0.3)",
                background: "rgba(0,255,102,0.15)", color: "#00FF66", fontSize: 9, fontWeight: 700, cursor: "pointer"
              }}>EXECUTE MISSION</button>
            </div>
          </div>
        </div>
      )}

      {/* Completion Screen */}
      {showCompletionScreen && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", backdropFilter: "blur(6px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}>
          <div style={{ background: "#0d1117", border: "1px solid #00FF66", boxShadow: "0 0 30px rgba(0,255,102,0.3)", borderRadius: 10, padding: 24, width: 440, textAlign: "center", display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontSize: 24, color: "#00FF66" }}>✓</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: "#00FF66", letterSpacing: "0.08em" }}>MISSION COMPLETE</div>
            <div style={{ fontSize: 12, color: "#fff" }}>{activeMission?.objective || "Task completed"}</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 9, color: "#8b949e", textAlign: "left", background: "rgba(255,255,255,0.02)", padding: 10, borderRadius: 6 }}>
              <div>{completionStats.actions} actions executed</div>
              <div>{completionStats.recoveries} self-healings</div>
              <div>{completionStats.verifications} verifications passed</div>
              <div>Duration: {completionStats.duration}</div>
            </div>
            <button onClick={() => { setShowCompletionScreen(false); setActive(false); }} style={{ padding: "8px 0", borderRadius: 6, background: "#00FF66", border: "none", color: "#000", fontSize: 10, fontWeight: 700, cursor: "pointer" }}>
              VIEW RESULT
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
