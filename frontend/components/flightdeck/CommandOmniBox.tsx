"use client";

import { useState, useRef, useEffect, useCallback } from "react";

interface CommandOmniBoxProps {
  onSend: (text: string) => void;
  isProcessing?: boolean;
  latencyMs?: number;
  activeAgent?: string;
  contextNodes?: { label: string; type: string; confidence: number }[];
}

export default function CommandOmniBox({
  onSend,
  isProcessing = false,
  latencyMs = 0,
  activeAgent,
  contextNodes = [],
}: CommandOmniBoxProps) {
  const [input, setInput] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [cursorPulse, setCursorPulse] = useState(0);

  useEffect(() => {
    const i = setInterval(() => setCursorPulse((p) => p + 1), 800);
    return () => clearInterval(i);
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isProcessing) return;
    onSend(trimmed);
    setInput("");
    setShowContext(false);
  }, [input, isProcessing, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const latencyColor =
    latencyMs < 15
      ? "#34d399"
      : latencyMs < 50
      ? "#fbbf24"
      : latencyMs < 100
      ? "#f97316"
      : "#ef4444";

  const borderColor = isProcessing
    ? "border-violet-500/40"
    : isFocused
    ? "border-zinc-600"
    : "border-zinc-800";

  return (
    <div className="relative">
      {/* Context preview */}
      {showContext && contextNodes.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 mb-2 bg-zinc-900/95 border border-zinc-700/50 rounded-lg px-3 py-2 backdrop-blur-sm max-h-40 overflow-y-auto">
          <div className="text-[9px] font-mono text-zinc-600 mb-1 tracking-wider">
            LOADED CONTEXT ({contextNodes.length} nodes)
          </div>
          <div className="flex flex-wrap gap-1.5">
            {contextNodes.map((node, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[9px] font-mono border"
                style={{
                  borderColor:
                    node.type === "RELATIONSHIP"
                      ? "rgba(244,114,182,0.3)"
                      : node.type === "PREFERENCE"
                      ? "rgba(34,211,238,0.3)"
                      : node.type === "GOAL"
                      ? "rgba(251,191,36,0.3)"
                      : "rgba(107,114,128,0.3)",
                  color:
                    node.type === "RELATIONSHIP"
                      ? "#f472b6"
                      : node.type === "PREFERENCE"
                      ? "#22d3ee"
                      : node.type === "GOAL"
                      ? "#fbbf24"
                      : "#9ca3af",
                  backgroundColor:
                    node.type === "RELATIONSHIP"
                      ? "rgba(244,114,182,0.05)"
                      : node.type === "PREFERENCE"
                      ? "rgba(34,211,238,0.05)"
                      : node.type === "GOAL"
                      ? "rgba(251,191,36,0.05)"
                      : "rgba(107,114,128,0.05)",
                }}
              >
                <span>{node.label}</span>
                {node.confidence > 0 && (
                  <span className="opacity-50">{(node.confidence * 100).toFixed(0)}%</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Main input area */}
      <div
        className={`relative rounded-xl border transition-all duration-200 ${borderColor} ${
          isProcessing ? "bg-zinc-900/80" : "bg-zinc-900/50"
        }`}
      >
        {/* Neon pulse effect when latency is low */}
        {latencyMs > 0 && latencyMs < 20 && (
          <div
            className="absolute inset-0 rounded-xl pointer-events-none"
            style={{
              boxShadow: `inset 0 0 30px rgba(52,211,153,${0.05 + (cursorPulse % 2) * 0.03})`,
            }}
          />
        )}

        {/* Top bar: agent indicator + latency */}
        <div className="flex items-center justify-between px-4 pt-2.5 pb-1">
          <div className="flex items-center gap-2">
            {activeAgent && (
              <span
                className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                style={{
                  backgroundColor:
                    activeAgent === "OS_AGENT"
                      ? "rgba(52,211,153,0.1)"
                      : activeAgent === "HAL_AGENT"
                      ? "rgba(34,211,238,0.1)"
                      : activeAgent === "WEB_AGENT"
                      ? "rgba(251,191,36,0.1)"
                      : "rgba(244,114,182,0.1)",
                  color:
                    activeAgent === "OS_AGENT"
                      ? "#34d399"
                      : activeAgent === "HAL_AGENT"
                      ? "#22d3ee"
                      : activeAgent === "WEB_AGENT"
                      ? "#fbbf24"
                      : "#f472b6",
                }}
              >
                {activeAgent.replace("_AGENT", "")}
              </span>
            )}
            {isProcessing && (
              <div className="flex items-center gap-1">
                <div className="w-1 h-1 rounded-full bg-violet-400 animate-pulse" />
                <span className="text-[9px] font-mono text-zinc-500">processing</span>
              </div>
            )}
          </div>

          {latencyMs > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-1 h-1 rounded-full" style={{ backgroundColor: latencyColor }} />
              <span className="text-[9px] font-mono" style={{ color: latencyColor }}>
                {latencyMs.toFixed(0)}ms
              </span>
            </div>
          )}
        </div>

        {/* Text area */}
        <div className="px-4 pb-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              setShowContext(e.target.value.length > 2);
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={isProcessing ? "JARVIS is executing..." : "Speak or type a command..."}
            disabled={isProcessing}
            rows={1}
            className="w-full bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 resize-none focus:outline-none disabled:opacity-40 font-mono"
            style={{ minHeight: "24px", maxHeight: "120px" }}
          />
        </div>

        {/* Bottom bar: keyboard shortcut + submit */}
        <div className="flex items-center justify-between px-4 pb-2.5">
          <div className="flex items-center gap-2">
            <kbd className="text-[8px] font-mono text-zinc-600 bg-zinc-800/50 px-1.5 py-0.5 rounded border border-zinc-700/50">
              Enter
            </kbd>
            <span className="text-[8px] font-mono text-zinc-700">to send</span>
            <kbd className="text-[8px] font-mono text-zinc-600 bg-zinc-800/50 px-1.5 py-0.5 rounded border border-zinc-700/50">
              Shift+Enter
            </kbd>
            <span className="text-[8px] font-mono text-zinc-700">newline</span>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!input.trim() || isProcessing}
            className="px-3 py-1 rounded-lg text-[10px] font-mono font-medium transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              backgroundColor: input.trim() ? "rgba(167,139,250,0.15)" : "transparent",
              color: input.trim() ? "#a78bfa" : "#52525b",
              border: `1px solid ${input.trim() ? "rgba(167,139,250,0.3)" : "rgba(255,255,255,0.06)"}`,
            }}
          >
            {isProcessing ? (
              <span className="flex items-center gap-1">
                <svg className="w-2.5 h-2.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                  <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
                Executing
              </span>
            ) : (
              "Send"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
