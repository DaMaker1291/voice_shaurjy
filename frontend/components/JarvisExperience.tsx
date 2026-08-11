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
  const [evidenceTimeline, setEvidenceTimeline] = useState<any[]>([]);
  // Compositor state
  const [compositeView, setCompositeView] = useState<any>(null);
  const [workerWindows, setWorkerWindows] = useState<any[]>([]);
  const [appTimeline, setAppTimeline] = useState<any[]>([]);
  const [expandedStep, setExpandedStep] = useState<number | null>(null);
  const [stepDetails, setStepDetails] = useState<any>(null);
  const [selectedWorker, setSelectedWorker] = useState<string | null>(null);
  const [liveScreenshot, setLiveScreenshot] = useState<string | null>(null);
  const [showLiveView, setShowLiveView] = useState(false);
  const [createdFiles, setCreatedFiles] = useState<any[]>([]);

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
            live.steps.map((s: any, i: number) => {
              let label = s.description || s.label || `Step ${i + 1}`;
              if (s.result) {
                try {
                  const r = typeof s.result === "string" ? JSON.parse(s.result) : s.result;
                  if (r.path) {
                    const fname = r.path.split("/").pop();
                    label += ` → ${fname}`;
                  }
                } catch {}
              }
              return {
                id: s.id || `step-${i}`,
                label,
                status: s.status === "completed" || s.status === "done" ? "done" : s.status === "failed" ? "failed" : s.status === "running" ? "running" : "pending",
              };
            })
          );
        }

        // Track created files
        if (live.created_files) {
          setCreatedFiles(live.created_files);
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
          // Fetch evidence timeline
          try {
            const evRes = await safeJson(
              await fetch(`${BASE}/api/evidence/${missionId}/timeline`)
            );
            if (evRes?.events) {
              setEvidenceTimeline(evRes.events);
            }
          } catch {}

          // Fetch composite view
          try {
            const compRes = await safeJson(
              await fetch(`${BASE}/api/workspace/composite/${missionId}`)
            );
            if (compRes) {
              setCompositeView(compRes);
              setWorkerWindows(compRes.windows || []);
              setAppTimeline(compRes.timeline || []);
            }
          } catch {}
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

  // Live screenshot polling during mission execution
  useEffect(() => {
    if (!missionId || mode === "complete" || mode === "home") return;
    const pollScreenshot = window.setInterval(async () => {
      try {
        const res = await fetch(`${BASE}/api/screen/screenshot`);
        if (res.ok) {
          const data = await res.json();
          if (data.screenshot) {
            setLiveScreenshot(data.screenshot);
          }
        }
      } catch {}
    }, 2000);
    return () => window.clearInterval(pollScreenshot);
  }, [missionId, mode]);

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

  // Take control of a worker
  async function handleTakeControl(workerId: string) {
    try {
      await safeJson(
        await fetch(`${BASE}/api/workspace/take-control`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ worker_id: workerId }),
        })
      );
      setSelectedWorker(workerId);
    } catch {}
  }

  // Return control to JARVIS
  async function handleReturnControl(workerId: string) {
    try {
      await safeJson(
        await fetch(`${BASE}/api/workspace/return-control`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ worker_id: workerId }),
        })
      );
      setSelectedWorker(null);
    } catch {}
  }

  // Expand a mission step to see details
  async function handleExpandStep(stepNum: number) {
    if (expandedStep === stepNum) {
      setExpandedStep(null);
      setStepDetails(null);
      return;
    }
    setExpandedStep(stepNum);
    try {
      const res = await safeJson(
        await fetch(`${BASE}/api/workspace/step-details/${missionId}?step=${stepNum}`)
      );
      if (res && !res.error) {
        setStepDetails(res);
      }
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
          {evidenceTimeline.length > 0 && (
            <div className="jv-evidence-timeline">
              <p className="jv-panel-label">EVIDENCE TRAIL</p>
              <div className="jv-evidence-list">
                {evidenceTimeline.map((ev: any, i: number) => (
                  <div key={i} className={`jv-evidence-item jv-evidence-${ev.type || "action"}`}>
                    <span className="jv-evidence-time">
                      {ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : ""}
                    </span>
                    <span className="jv-evidence-type">{(ev.type || "action").toUpperCase()}</span>
                    <span className="jv-evidence-desc">{ev.description || ev.action_type || ""}</span>
                    {ev.success !== undefined && (
                      <span className={`jv-evidence-status ${ev.success ? "ok" : "fail"}`}>
                        {ev.success ? "\u2713" : "\u2717"}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {createdFiles.length > 0 && (
            <div style={{ width: "100%", maxWidth: 500, marginTop: 20 }}>
              <p className="jv-panel-label" style={{ marginBottom: 8, fontSize: 11, color: "#00FF66", fontFamily: "monospace", letterSpacing: "0.1em" }}>CREATED FILES</p>
              {createdFiles.map((f: any, i: number) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "10px 14px", background: "#141414", border: "1px solid #222",
                  borderRadius: 8, marginBottom: 6, fontFamily: "monospace", fontSize: 13,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ color: "#00FF66", fontSize: 16 }}>&#128196;</span>
                    <div>
                      <div style={{ color: "#e8e8e8", fontWeight: 600 }}>{f.name}</div>
                      <div style={{ color: "#666", fontSize: 11, marginTop: 2 }}>{f.path}</div>
                    </div>
                  </div>
                  <span style={{ color: "#888", fontSize: 12 }}>{f.size}b</span>
                </div>
              ))}
            </div>
          )}
          <div className="jv-complete-actions">
            <button className="jv-btn-primary" onClick={() => { setMode("home"); setMission(""); setProgress(0); setMissionId(""); setMissionStats(null); setEvidenceTimeline([]); setCreatedFiles([]); }}>
              NEW MISSION
            </button>
            <button className="jv-btn-ghost" onClick={() => { setMode("cockpit"); }}>
              VIEW RESULT
            </button>
          </div>
          <div className="jv-input-wrap" style={{ marginTop: 24 }}>
            <input
              className="jv-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") startMission(); }}
              placeholder="Tell JARVIS what you need..."
            />
            <button className="jv-input-btn" onClick={() => startMission()}>ENTER</button>
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
                  ? steps.map((step, i) => (
                      <div key={step.id} className={`jv-step ${step.status} ${expandedStep === i + 1 ? "expanded" : ""}`}
                           onClick={() => handleExpandStep(i + 1)}>
                        <span className="jv-step-dot">
                          {step.status === "done"
                            ? "\u2713"
                            : step.status === "running"
                            ? "\u25CF"
                            : step.status === "active"
                            ? "\u25CF"
                            : step.status === "failed"
                            ? "\u2717"
                            : "\u25CB"}
                        </span>
                        {step.label}
                        {expandedStep === i + 1 && stepDetails && (
                          <div className="jv-step-detail">
                            {stepDetails.app_name && <div className="jv-step-app">App: {stepDetails.app_name}</div>}
                            {stepDetails.worker_id && <div className="jv-step-worker">Worker: {stepDetails.worker_id.split("_").slice(-1)[0]}</div>}
                            {stepDetails.duration_ms > 0 && <div className="jv-step-dur">{Math.round(stepDetails.duration_ms)}ms</div>}
                            {stepDetails.verification?.verified !== undefined && (
                              <div className={`jv-step-verify ${stepDetails.verification.verified ? "ok" : "fail"}`}>
                                {stepDetails.verification.verified ? "\u2713 Verified" : "\u2717 Not verified"}
                              </div>
                            )}
                          </div>
                        )}
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
                {compositeView && (
                  <span className="jv-worker-count">
                    {compositeView.active_workers} worker{compositeView.active_workers !== 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <div className="jv-workspace-body">
                {workerWindows.length > 0 ? (
                  <div className="jv-compositor">
                    {workerWindows.map((w: any) => (
                      <div key={w.id} className={`jv-worker-window ${w.user_control ? "user-control" : ""}`}>
                        <div className="jv-worker-header">
                          <span className="jv-worker-title">{w.title}</span>
                          <span className={`jv-worker-status jv-status-${w.status}`}>
                            {w.status === "running" ? "\u25CF" : "\u25CB"}
                          </span>
                        </div>
                        <div className="jv-worker-activity">
                          {w.activity.action && (
                            <div className="jv-activity-row">
                              <span className="jv-activity-label">ACTION</span>
                              <span className="jv-activity-val">{w.activity.action}</span>
                            </div>
                          )}
                          {w.activity.tool && (
                            <div className="jv-activity-row">
                              <span className="jv-activity-label">TOOL</span>
                              <span className="jv-activity-val">{w.activity.tool}</span>
                            </div>
                          )}
                          {w.activity.object && (
                            <div className="jv-activity-row">
                              <span className="jv-activity-label">OBJECT</span>
                              <span className="jv-activity-val">{w.activity.object}</span>
                            </div>
                          )}
                          {w.activity.progress > 0 && (
                            <div className="jv-worker-progress">
                              <div className="jv-meter" style={{height: 4}}>
                                <div className="jv-meter-fill" style={{width: `${w.activity.progress * 100}%`}} />
                              </div>
                              <span className="jv-progress-text">{Math.round(w.activity.progress * 100)}%</span>
                            </div>
                          )}
                          {w.activity.verification && (
                            <div className={`jv-verify-badge ${w.activity.verification}`}>
                              {w.activity.verification === "passed" ? "\u2713 VERIFIED" : w.activity.verification === "failed" ? "\u2717 FAILED" : "\u25CB PENDING"}
                            </div>
                          )}
                        </div>
                        <div className="jv-worker-controls">
                          {w.user_control ? (
                            <button className="jv-btn-return" onClick={() => handleReturnControl(w.id)}>
                              RETURN TO JARVIS
                            </button>
                          ) : (
                            <button className="jv-btn-control" onClick={() => handleTakeControl(w.id)}>
                              TAKE CONTROL
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    {liveScreenshot && (
                      <div className="jv-live-screenshot" style={{
                        position: "relative",
                        borderBottom: "1px solid #222",
                        background: "#000",
                        maxHeight: "40vh",
                        overflow: "hidden",
                      }}>
                        <img
                          src={`data:image/jpeg;base64,${liveScreenshot}`}
                          alt="Live screen"
                          style={{ width: "100%", height: "100%", objectFit: "contain" }}
                        />
                        <div style={{
                          position: "absolute",
                          top: 8,
                          right: 8,
                          background: "rgba(0,0,0,0.7)",
                          padding: "4px 10px",
                          borderRadius: 6,
                          fontSize: 11,
                          color: "#00FF66",
                          fontFamily: "monospace",
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                        }}>
                          <span style={{
                            width: 6, height: 6, borderRadius: "50%",
                            background: "#00FF66",
                            animation: "pulse 1.5s infinite",
                          }} />
                          LIVE SCREEN
                        </div>
                      </div>
                    )}
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
                  </>
                )}
              </div>
              {appTimeline.length > 0 && (
                <div className="jv-timeline-bar">
                  {appTimeline.map((ev: any, i: number) => (
                    <div key={i} className={`jv-timeline-event jv-tl-${ev.event_type?.replace("_", "-")}`}>
                      <span className="jv-tl-time">
                        {ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) : ""}
                      </span>
                      <span className="jv-tl-app">{ev.app_name}</span>
                      <span className="jv-tl-desc">{ev.description?.substring(0, 40)}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="jv-workspace-footer">
                <span className="jv-footer-dot" />
                {state === "complete"
                  ? "Mission complete"
                  : compositeView
                  ? `${compositeView.active_workers} workers · ${compositeView.total_workers_created} total`
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
