"use client";

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import JARVISOrbSmart from "@/components/orb/JARVISOrbSmart";
import LiveWorkspace from "@/components/cockpit/LiveWorkspace";
import ApprovalOverlay from "@/components/cockpit/ApprovalOverlay";
import InterceptBar from "@/components/cockpit/InterceptBar";
import { BASE, safeJson } from "@/lib/api";

type Mode = "orb" | "home" | "acknowledging" | "cockpit" | "complete";
type OrbState =
  | "idle"
  | "listening"
  | "planning"
  | "working"
  | "waiting"
  | "needs_approval"
  | "error"
  | "recovering"
  | "complete";

interface MissionStep {
  id: string;
  label: string;
  status: "pending" | "active" | "done" | "failed";
}

export default function JarvisExperience() {
  const [mode, setMode] = useState<Mode>("home");
  const [input, setInput] = useState("");
  const [mission, setMission] = useState("");
  const [state, setState] = useState<OrbState>("idle");
  const [progress, setProgress] = useState(0);
  const [workspaceId, setWorkspaceId] = useState("");
  const [workspaceRunning, setWorkspaceRunning] = useState(false);
  const [missionId, setMissionId] = useState("");
  const [message, setMessage] = useState("Ready when you are.");
  const [history, setHistory] = useState<string[]>([]);
  const [acknowledgment, setAcknowledgment] = useState("");
  const [agentCount, setAgentCount] = useState(0);
  const [steps, setSteps] = useState<MissionStep[]>([]);
  const [approvalPending, setApprovalPending] = useState<any>(null);
  const [missionStats, setMissionStats] = useState<{ tasks: number; failures: number; verified: number } | null>(null);

  // Voice state
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const recognitionRef = useRef<any>(null);

  // Initialize voice recognition
  useEffect(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      setVoiceSupported(true);
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((r: any) => r[0].transcript)
          .join("");
        setInput(transcript);
        if (event.results[0]?.isFinal) {
          setIsListening(false);
          setState("idle");
        }
      };
      recognition.onend = () => {
        setIsListening(false);
        if (state === "listening") setState("idle");
      };
      recognition.onerror = () => {
        setIsListening(false);
        if (state === "listening") setState("idle");
      };
      recognitionRef.current = recognition;
    }
  }, []);

  // Toggle voice input
  const toggleVoice = useCallback(() => {
    if (!recognitionRef.current) return;
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
      setState("idle");
    } else {
      recognitionRef.current.start();
      setIsListening(true);
      setState("listening");
    }
  }, [isListening, state]);

  // Poll mission status
  useEffect(() => {
    if (!missionId) return;
    const poll = window.setInterval(async () => {
      try {
        const result = await safeJson(
          await fetch(
            `${BASE}/api/workspace/mission/status?mission_id=${encodeURIComponent(missionId)}`
          )
        );
        const live = result.mission;
        if (!live) return;

        const percent = Math.round((live.progress || 0) * 100);
        setProgress(percent);
        setMessage(live.current_action || "Executing mission safely in the workspace.");

        // Update steps from mission data
        if (live.steps) {
          setSteps(
            live.steps.map((s: any, i: number) => ({
              id: s.id || `step-${i}`,
              label: s.description || s.label || `Step ${i + 1}`,
              status: s.status === "done" ? "done" : s.status === "failed" ? "failed" : s.status === "running" ? "active" : "pending",
            }))
          );
        }

        // Update agent count
        if (live.agent_count !== undefined) {
          setAgentCount(live.agent_count);
        }

        // State transitions
        if (live.status === "completed") {
          setState("complete");
          setMode("complete");
          setMissionStats({
            tasks: live.steps?.length || 0,
            failures: live.failures || 0,
            verified: live.verified || 0,
          });
        } else if (live.status === "paused") {
          setState("waiting");
        } else if (live.status === "failed" || live.status === "stopped") {
          setState("error");
        } else if (live.status === "planning") {
          setState("planning");
        } else if (live.status === "recovering") {
          setState("recovering");
        } else {
          setState("working");
        }

        // Check for approval requests
        if (live.approval_pending) {
          setApprovalPending(live.approval_pending);
          setState("needs_approval");
        }
      } catch {
        setMessage("Connection interrupted.");
      }
    }, 1500);
    return () => window.clearInterval(poll);
  }, [missionId]);

  // Start a mission
  async function startMission(text = input) {
    if (!text.trim()) return;
    setMission(text.trim());
    setInput("");
    setProgress(0);
    setHistory((h) => [text.trim(), ...h].slice(0, 20));

    // Show acknowledgment
    const ack = generateAcknowledgment(text.trim());
    setAcknowledgment(ack);
    setMode("acknowledging");
    setState("planning");

    // After acknowledgment, start the mission
    setTimeout(async () => {
      setMode("cockpit");
      setMessage("Provisioning workspace\u2026");
      try {
        let activeWorkspaceId = workspaceId;
        if (!activeWorkspaceId) {
          const created = await safeJson(
            await fetch(`${BASE}/api/workspace/create`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ name: "JARVIS Workspace", width: 1920, height: 1080 }),
            })
          );
          activeWorkspaceId = created.workspace?.id;
          if (!activeWorkspaceId)
            throw new Error(created.error || "Could not create workspace");
          await safeJson(
            await fetch(`${BASE}/api/workspace/start`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ workspace_id: activeWorkspaceId }),
            })
          );
          setWorkspaceId(activeWorkspaceId);
          setWorkspaceRunning(true);
        }

        setMessage("Creating mission plan\u2026");
        const createdMission = await safeJson(
          await fetch(`${BASE}/api/workspace/mission/create`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ objective: text.trim(), workspace_id: activeWorkspaceId }),
          })
        );
        const activeMissionId = createdMission.mission?.id;
        if (!activeMissionId)
          throw new Error(createdMission.error || "Could not create mission");
        setMissionId(activeMissionId);

        await safeJson(
          await fetch(`${BASE}/api/workspace/mission/plan`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mission_id: activeMissionId }),
          })
        );
        await safeJson(
          await fetch(`${BASE}/api/workspace/mission/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mission_id: activeMissionId }),
          })
        );
        setState("working");
        setMessage("Mission started.");
      } catch (error) {
        setState("error");
        setMessage(error instanceof Error ? error.message : "Could not start mission.");
      }
    }, 2000); // 2s acknowledgment delay
  }

  // Control mission
  async function controlMission(action: "pause" | "resume" | "stop") {
    if (!missionId) return;
    try {
      await safeJson(
        await fetch(`${BASE}/api/workspace/mission/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mission_id: missionId }),
        })
      );
      setState(
        action === "pause" ? "waiting" : action === "stop" ? "idle" : "working"
      );
      setMessage(
        action === "stop"
          ? "Mission stopped."
          : action === "pause"
          ? "Paused."
          : "Resumed."
      );
      if (action === "stop") {
        setProgress(0);
        setMode("home");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update mission.");
    }
  }

  // Handle approval
  async function handleApproval(approved: boolean) {
    if (!approvalPending) return;
    try {
      await safeJson(
        await fetch(
          `${BASE}/api/workspace/approvals/${approved ? "approve" : "deny"}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: approvalPending.id }),
          }
        )
      );
      setApprovalPending(null);
      setState("working");
    } catch {}
  }

  // Generate acknowledgment message
  function generateAcknowledgment(goal: string): string {
    const lower = goal.toLowerCase();
    if (lower.includes("website") || lower.includes("site")) {
      return "I'll research the market, design the brand, build the website, and verify everything works before presenting it.";
    }
    if (lower.includes("research") || lower.includes("find")) {
      return "I'll search across multiple sources, compile the findings, analyze the data, and present a comprehensive report.";
    }
    if (lower.includes("animation") || lower.includes("3d") || lower.includes("blender")) {
      return "I'll set up the 3D environment, model the scene, animate it, render the output, and verify the result.";
    }
    if (lower.includes("build") || lower.includes("create") || lower.includes("make")) {
      return "I'll plan the approach, create the necessary components, assemble everything, and verify it works correctly.";
    }
    return "I'll break this down into steps, execute each one carefully, verify the results, and deliver the finished outcome.";
  }

  // Orb click handler
  const handleOrbClick = useCallback(() => {
    if (mode === "home") {
      // Focus the input field
      const inputEl = document.querySelector(".jv-input") as HTMLInputElement;
      if (inputEl) inputEl.focus();
    }
  }, [mode]);

  const Orb = ({ size }: { size: number }) => (
    <JARVISOrbSmart
      state={state}
      size={size}
      progress={progress}
      mission={mission}
      agentCount={agentCount}
      toolActive={state === "working"}
      interactive={mode === "home"}
      onClick={mode === "home" ? handleOrbClick : undefined}
      showLabel={size > 100}
    />
  );

  // Acknowledging mode
  if (mode === "acknowledging") {
    return (
      <div className="jv-app">
        <div className="jv-grid-bg" />
        <div className="jv-acknowledge">
          <Orb size={200} />
          <p className="jv-acknowledge-text">{acknowledgment}</p>
          <div className="jv-acknowledge-dots">
            <span className="jv-dot" style={{ animationDelay: "0s" }} />
            <span className="jv-dot" style={{ animationDelay: "0.2s" }} />
            <span className="jv-dot" style={{ animationDelay: "0.4s" }} />
          </div>
        </div>
      </div>
    );
  }

  // Completion mode
  if (mode === "complete" && missionStats) {
    return (
      <div className="jv-app">
        <div className="jv-grid-bg" />
        <div className="jv-complete">
          <Orb size={160} />
          <h2 className="jv-complete-title">MISSION COMPLETE</h2>
          <p className="jv-complete-mission">{mission}</p>
          <div className="jv-complete-stats">
            <div className="jv-complete-stat">
              <span className="jv-complete-stat-val">{missionStats.tasks}</span>
              <span className="jv-complete-stat-label">Tasks completed</span>
            </div>
            <div className="jv-complete-stat">
              <span className="jv-complete-stat-val">{missionStats.failures}</span>
              <span className="jv-complete-stat-label">Failures recovered</span>
            </div>
            <div className="jv-complete-stat">
              <span className="jv-complete-stat-val">{missionStats.verified}</span>
              <span className="jv-complete-stat-label">Checks passed</span>
            </div>
          </div>
          <div className="jv-complete-actions">
            <button className="jv-btn-primary" onClick={() => { setMode("home"); setMission(""); setProgress(0); setMissionId(""); setMissionStats(null); }}>
              NEW MISSION
            </button>
            <button className="jv-btn-ghost" onClick={() => setMode("cockpit")}>
              VIEW RESULT
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Orb-only mode (minimised)
  if (mode === "orb") {
    return (
      <div className="jv-app jv-minimal">
        <button className="jv-orb-fab" onClick={() => setMode("home")} aria-label="Open JARVIS">
          <Orb size={80} />
        </button>
      </div>
    );
  }

  return (
    <div className={`jv-app ${mode === "cockpit" ? "jv-cockpit-mode" : ""}`}>
      <div className="jv-grid-bg" />

      {/* Approval overlay */}
      {approvalPending && (
        <ApprovalOverlay
          action={approvalPending.action || "Unknown action"}
          details={approvalPending.details || {}}
          onApprove={() => handleApproval(true)}
          onDeny={() => handleApproval(false)}
        />
      )}

      {/* Intercept bar */}
      <InterceptBar
        onApprove={(id) => handleApproval(true)}
        onDeny={(id) => handleApproval(false)}
      />

      <header className="jv-topbar">
        <button className="jv-brand" onClick={() => setMode("home")}>
          <span className="jv-brand-dot" />
          <span className="jv-brand-text">JARVIS</span>
          <span className="jv-brand-tag">OS</span>
        </button>
        <div className="jv-topbar-right">
          {state !== "idle" && (
            <span className={`jv-status-chip jv-status-${state}`}>
              <span className="jv-status-dot" />
              {state.toUpperCase()}
            </span>
          )}
          <span className="jv-online">
            <span className="jv-online-dot" />
            ONLINE
          </span>
        </div>
      </header>

      {mode === "home" ? (
        <div className="jv-home">
          <div className="jv-home-glow" />
          <div className="jv-home-orb-wrap" onClick={handleOrbClick}>
            <Orb size={280} />
          </div>
          <p className="jv-eyebrow">NEURAL CORE</p>
          <h1 className="jv-headline">
            {mission ? "Ready for your next mission." : "Good morning."}
          </h1>
          <p className="jv-subtext">What should I do for you?</p>

          {/* Voice + Text input */}
          <div className="jv-input-wrap">
            {voiceSupported && (
              <button
                className={`jv-voice-btn ${isListening ? "jv-voice-active" : ""}`}
                onClick={toggleVoice}
                aria-label="Voice input"
              >
                {isListening ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                  </svg>
                )}
              </button>
            )}
            <input
              className="jv-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && startMission()}
              placeholder="Tell JARVIS what you need..."
            />
            <button className="jv-input-btn" onClick={() => startMission()}>
              ENTER
            </button>
          </div>

          <div className="jv-suggestions">
            {[
              "Build a company website",
              "Research AI competitors",
              "Create a 3D animation",
              "Set up my development environment",
            ].map((item) => (
              <button key={item} className="jv-chip" onClick={() => startMission(item)}>
                {item}
              </button>
            ))}
          </div>

          <div className="jv-stats-row">
            <StatBlock label="MISSIONS" values={["Website", "Research", "Animation"]} />
            <StatBlock label="WORKSPACE" values={["Windows", "Chrome", "VS Code"]} />
            <StatBlock label="MEMORY" values={["2,431 items", "Operational context"]} />
          </div>
        </div>
      ) : (
        <div className="jv-cockpit">
          <div className="jv-cockpit-left">
            <div className="jv-panel">
              <p className="jv-panel-label">MISSION</p>
              <h2 className="jv-mission-title">{mission || "Untitled mission"}</h2>
              <div className="jv-steps">
                {steps.length > 0
                  ? steps.map((step) => (
                      <div key={step.id} className={`jv-step ${step.status}`}>
                        <span className="jv-step-dot">
                          {step.status === "done"
                            ? "\u2713"
                            : step.status === "active"
                            ? "\u25CF"
                            : step.status === "failed"
                            ? "\u2717"
                            : "\u25CB"}
                        </span>
                        {step.label}
                      </div>
                    ))
                  : ["Understand", "Plan", "Create", "Verify"].map((step, i) => (
                      <div
                        key={step}
                        className={`jv-step ${
                          i < Math.min(3, Math.floor(progress / 25)) || progress === 100
                            ? "done"
                            : i === Math.min(3, Math.floor(progress / 25))
                            ? "active"
                            : ""
                        }`}
                      >
                        <span className="jv-step-dot">
                          {i < Math.min(3, Math.floor(progress / 25)) || progress === 100
                            ? "\u2713"
                            : i === Math.min(3, Math.floor(progress / 25))
                            ? "\u25CF"
                            : "\u25CB"}
                        </span>
                        {step}
                      </div>
                    ))}
              </div>
              <div className="jv-meter-block">
                <div className="jv-meter">
                  <div className="jv-meter-fill" style={{ width: `${progress}%` }} />
                </div>
                <span className="jv-meter-text">{progress}%</span>
              </div>
              <button className="jv-ghost-btn" onClick={() => setMode("orb")}>
                Minimise
              </button>
            </div>

            <div className="jv-panel">
              <p className="jv-panel-label">INTELLIGENCE</p>
              <div className="jv-intel-item">
                <span className="jv-intel-key">STATUS</span>
                <span className="jv-intel-val">
                  {state === "complete"
                    ? "Mission evidence verified."
                    : message}
                </span>
              </div>
              <div className="jv-intel-item">
                <span className="jv-intel-key">AGENTS</span>
                <span className="jv-intel-val">
                  {agentCount > 0 ? `${agentCount} active` : "Spawning..."}
                </span>
              </div>
              <div className="jv-intel-item">
                <span className="jv-intel-key">TOOLS</span>
                <span className="jv-intel-val">Workspace · Browser · File system</span>
              </div>
            </div>
          </div>

          <div className="jv-cockpit-center">
            <div className="jv-orb-bridge">
              <Orb size={56} />
              <div className="jv-bridge-line" />
              <span className="jv-bridge-label">
                {state === "complete"
                  ? "COMPLETE"
                  : state === "planning"
                  ? "PLANNING"
                  : state === "needs_approval"
                  ? "APPROVAL NEEDED"
                  : "EXECUTING"}
              </span>
            </div>
            <div className="jv-workspace-frame">
              <div className="jv-workspace-header">
                <span className="jv-live-badge">
                  <span className="jv-live-dot" /> LIVE
                </span>
                <span className="jv-workspace-title">JARVIS WORKSPACE</span>
              </div>
              <div className="jv-workspace-body">
                <LiveWorkspace
                  workspaceId={workspaceId || undefined}
                  isRunning={workspaceRunning}
                  currentAction={
                    state === "complete"
                      ? "Mission complete"
                      : progress > 65
                      ? "Verifying evidence"
                      : "JARVIS is working"
                  }
                  missionId={missionId || undefined}
                />
              </div>
              <div className="jv-workspace-footer">
                <span className="jv-footer-dot" />
                {state === "complete"
                  ? "Mission complete"
                  : "JARVIS is working in its own computer"}
              </div>
            </div>

            <div className="jv-bottom-bar">
              <div className="jv-input-wrap jv-input-compact">
                <span className="jv-input-icon">&#10022;</span>
                <input
                  className="jv-input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && startMission()}
                  placeholder="Tell JARVIS what to change..."
                />
                <button className="jv-input-btn" onClick={() => startMission()}>
                  ENTER
                </button>
              </div>
            </div>
          </div>

          <div className="jv-cockpit-footer">
            <button className="jv-footer-brand" onClick={() => setMode("home")}>
              <span className="jv-brand-dot" /> JARVIS
            </button>
            <span className="jv-footer-msg">
              {state === "complete"
                ? "Mission complete \u2014 evidence available"
                : message}
            </span>
            <div className="jv-footer-controls">
              <button
                className="jv-ctrl-btn"
                onClick={() =>
                  controlMission(state === "waiting" ? "resume" : "pause")
                }
              >
                {state === "waiting" ? "RESUME" : "PAUSE"}
              </button>
              <button
                className="jv-ctrl-btn jv-ctrl-stop"
                onClick={() => controlMission("stop")}
              >
                STOP
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatBlock({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="jv-stat-block">
      <span className="jv-stat-label">{label}</span>
      {values.map((v) => (
        <span key={v} className="jv-stat-val">
          {v}
        </span>
      ))}
    </div>
  );
}
