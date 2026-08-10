"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import GlobeSimulation from "./scenes/GlobeSimulation";
import DocumentSimulation from "./scenes/DocumentSimulation";
import NetworkSimulation from "./scenes/NetworkSimulation";
import SystemSimulation from "./scenes/SystemSimulation";

interface SceneData {
  type: string;
  title: string;
  progress: number;
  subtitle: string;
  details: Record<string, any>;
}

interface StepEvent {
  step: string;
  result: string;
}

interface SSEEvent {
  type: "scene_init" | "scene_update" | "plan" | "status" | "result" | "complete";
  scene?: SceneData;
  steps?: string[];
  text?: string;
  progress?: number;
  step?: string;
  result?: string;
}

export default function SimulationPanel({ task, active }: { task: string | null; active: boolean }) {
  const [scene, setScene] = useState<SceneData | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [statusText, setStatusText] = useState("");
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<StepEvent[]>([]);
  const [phase, setPhase] = useState<"idle" | "planning" | "executing" | "complete">("idle");
  const eventSourceRef = useRef<EventSource | null>(null);
  const resultsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll results
  useEffect(() => {
    resultsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [results]);

  // Connect SSE when a task is active
  useEffect(() => {
    if (!task || !active) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (!active) return;
      return;
    }

    // Cleanup previous connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setSteps([]);
    setResults([]);
    setProgress(0);
    setPhase("planning");
    setStatusText("Connecting...");

    const es = new EventSource(`/api/task/execute?task=${encodeURIComponent(task)}`);

    es.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data);

        switch (data.type) {
          case "scene_init":
            if (data.scene) {
              setScene(data.scene);
            }
            break;
          case "plan":
            if (data.steps) {
              setSteps(data.steps);
              setPhase("executing");
            }
            break;
          case "status":
            setStatusText(data.text || "");
            if (data.progress !== undefined) setProgress(data.progress);
            break;
          case "scene_update":
            if (data.scene) {
              setScene(data.scene);
              if (data.scene.progress !== undefined) setProgress(data.scene.progress);
              setStatusText(data.scene.subtitle || "");
            }
            break;
          case "result":
            if (data.step && data.result) {
              setResults((prev) => [...prev, { step: data.step!, result: data.result! }]);
            }
            break;
          case "complete":
            setPhase("complete");
            setProgress(100);
            setStatusText("Complete!");
            es.close();
            break;
        }
      } catch (e) {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setStatusText("Connection lost. Reconnecting...");
    };

    eventSourceRef.current = es;

    return () => {
      es.close();
    };
  }, [task, active]);

  // Scene type to component mapping
  const renderScene = () => {
    const st = scene?.type || "system";
    switch (st) {
      case "travel":
        return <GlobeSimulation data={scene?.details} progress={progress} />;
      case "document":
        return <DocumentSimulation data={scene?.details} progress={progress} />;
      case "network":
        return <NetworkSimulation data={scene?.details} progress={progress} />;
      case "system":
      default:
        return <SystemSimulation data={scene?.details} progress={progress} />;
    }
  };

  if (!active) return null;

  return (
    <div className="w-full h-full flex flex-col bg-gradient-to-b from-black/40 via-purple-950/10 to-black/40">
      {/* Header */}
      <div className="px-4 py-2 border-b border-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${
              phase === "complete" ? "bg-green-500" :
              phase === "executing" ? "bg-blue-500 animate-pulse" :
              "bg-yellow-500 animate-pulse"
            }`} />
            <span className="text-[10px] font-mono text-white/40 uppercase tracking-wider">
              {phase === "planning" ? "Planning" :
               phase === "executing" ? "Executing" :
               phase === "complete" ? "Complete" : "Idle"}
            </span>
          </div>
          {scene && (
            <div className="flex items-center gap-2">
              <span className="text-[8px] font-mono text-white/20 bg-white/5 px-2 py-0.5 rounded">
                {scene.type}
              </span>
              <span className="text-[9px] font-mono text-white/50">{progress}%</span>
            </div>
          )}
        </div>
        {statusText && (
          <div className="text-[9px] font-mono text-white/30 mt-1 truncate">{statusText}</div>
        )}
      </div>

      {/* Simulation viewport */}
      <div className="flex-1 min-h-0 flex items-center justify-center relative">
        {scene ? (
          renderScene()
        ) : (
          <div className="flex flex-col items-center justify-center text-white/20 gap-3">
            <div className="w-16 h-16 border border-white/10 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.2" />
                <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>
            <span className="text-[10px] font-mono">Awaiting task...</span>
          </div>
        )}
      </div>

      {/* Steps + Results log */}
      <div className="border-t border-white/5 max-h-[140px] overflow-y-auto">
        <div className="px-3 py-1.5">
          {/* Active steps */}
          {steps.length > 0 && (
            <div className="mb-1 flex flex-wrap gap-1">
              {steps.map((s, i) => {
                const isDone = i < results.length;
                const isActive = i === results.length;
                return (
                  <div
                    key={i}
                    className={`text-[7px] font-mono px-1.5 py-0.5 rounded-full ${
                      isDone ? "bg-green-500/10 text-green-400/60" :
                      isActive ? "bg-blue-500/10 text-blue-400/60 animate-pulse" :
                      "bg-white/5 text-white/20"
                    }`}
                  >
                    {isDone ? "✓" : isActive ? "→" : "○"} {s.slice(0, 30)}
                  </div>
                );
              })}
            </div>
          )}

          {/* Result log */}
          {results.length > 0 && (
            <div className="space-y-0.5">
              {results.slice(-5).map((r, i) => (
                <div key={i} className="text-[7px] font-mono text-white/30 leading-relaxed animate-fadeIn">
                  <span className="text-green-400/50">{r.step}:</span> {r.result.slice(0, 100)}
                </div>
              ))}
              <div ref={resultsEndRef} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
