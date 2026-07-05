"use client";

import { useState, useEffect, useCallback } from "react";

interface InterceptModalProps {
  isOpen: boolean;
  actionType: string;
  targetIdentifier: string;
  scriptBody?: string;
  riskLevel: "low" | "medium" | "high" | "critical";
  onApprove: () => void;
  onDeny: () => void;
  onModify?: (modifiedScript: string) => void;
}

const RISK_COLORS: Record<string, { bg: string; border: string; text: string; glow: string }> = {
  low: { bg: "rgba(52,211,153,0.05)", border: "rgba(52,211,153,0.3)", text: "#34d399", glow: "rgba(52,211,153,0.1)" },
  medium: { bg: "rgba(251,191,36,0.05)", border: "rgba(251,191,36,0.3)", text: "#fbbf24", glow: "rgba(251,191,36,0.1)" },
  high: { bg: "rgba(249,115,22,0.05)", border: "rgba(249,115,22,0.3)", text: "#f97316", glow: "rgba(249,115,22,0.1)" },
  critical: { bg: "rgba(239,68,68,0.05)", border: "rgba(239,68,68,0.3)", text: "#ef4444", glow: "rgba(239,68,68,0.15)" },
};

const RISK_LABELS: Record<string, string> = {
  low: "LOW RISK",
  medium: "MEDIUM RISK",
  high: "HIGH RISK — REVIEW REQUIRED",
  critical: "CRITICAL — AUTHENTICATION REQUIRED",
};

export default function InterceptModal({
  isOpen,
  actionType,
  targetIdentifier,
  scriptBody,
  riskLevel,
  onApprove,
  onDeny,
  onModify,
}: InterceptModalProps) {
  const [countdown, setCountdown] = useState(5);
  const [isApproving, setIsApproving] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editedScript, setEditedScript] = useState(scriptBody || "");

  useEffect(() => {
    if (scriptBody) setEditedScript(scriptBody);
  }, [scriptBody]);

  useEffect(() => {
    if (!isOpen) {
      setCountdown(5);
      setIsApproving(false);
      setEditMode(false);
    }
  }, [isOpen]);

  // Auto-deny after 30s for safety
  useEffect(() => {
    if (!isOpen) return;
    const t = setTimeout(() => {
      if (!isApproving) onDeny();
    }, 30000);
    return () => clearTimeout(t);
  }, [isOpen, isApproving, onDeny]);

  // Countdown before approve button is enabled (safety delay)
  useEffect(() => {
    if (!isOpen || countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [isOpen, countdown]);

  const handleApprove = useCallback(() => {
    setIsApproving(true);
    setTimeout(() => onApprove(), 300);
  }, [onApprove]);

  if (!isOpen) return null;

  const colors = RISK_COLORS[riskLevel];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onDeny}
      />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg mx-4 rounded-xl border overflow-hidden"
        style={{
          backgroundColor: colors.bg,
          borderColor: colors.border,
          boxShadow: `0 0 60px ${colors.glow}, 0 0 120px ${colors.glow}`,
        }}
      >
        {/* Header */}
        <div
          className="px-5 py-4 border-b"
          style={{ borderColor: colors.border }}
        >
          <div className="flex items-center gap-3">
            {/* Warning icon */}
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: `${colors.text}15` }}
            >
              <svg
                className="w-5 h-5 animate-pulse"
                viewBox="0 0 24 24"
                fill="none"
                stroke={colors.text}
                strokeWidth="2"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
                />
              </svg>
            </div>
            <div>
              <h3
                className="text-sm font-semibold"
                style={{ color: colors.text }}
              >
                {RISK_LABELS[riskLevel]}
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Action requires human validation
              </p>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3">
          {/* Action details */}
          <div className="bg-black/30 rounded-lg p-3 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-mono text-zinc-500 w-20">ACTION</span>
              <span className="text-[10px] font-mono text-zinc-300">
                {actionType}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-mono text-zinc-500 w-20">TARGET</span>
              <span className="text-[10px] font-mono text-zinc-300">
                {targetIdentifier}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-mono text-zinc-500 w-20">RISK</span>
              <span
                className="text-[10px] font-mono font-semibold"
                style={{ color: colors.text }}
              >
                {riskLevel.toUpperCase()}
              </span>
            </div>
          </div>

          {/* Script preview */}
          {scriptBody && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] font-mono text-zinc-500 tracking-wider">
                  SCRIPT PAYLOAD
                </span>
                {onModify && (
                  <button
                    onClick={() => setEditMode(!editMode)}
                    className="text-[9px] font-mono text-violet-400 hover:text-violet-300"
                  >
                    {editMode ? "Cancel Edit" : "Edit Script"}
                  </button>
                )}
              </div>
              <div className="bg-black/40 rounded-lg border border-zinc-800/50 max-h-40 overflow-y-auto">
                {editMode ? (
                  <textarea
                    value={editedScript}
                    onChange={(e) => setEditedScript(e.target.value)}
                    className="w-full bg-transparent text-[10px] font-mono text-zinc-300 p-3 resize-none focus:outline-none"
                    rows={8}
                  />
                ) : (
                  <pre className="text-[10px] font-mono text-zinc-400 p-3 whitespace-pre-wrap break-all">
                    {scriptBody}
                  </pre>
                )}
              </div>
            </div>
          )}

          {/* Safety warning */}
          <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-black/20 border border-zinc-800/30">
            <svg
              className="w-3.5 h-3.5 text-zinc-500 mt-0.5 shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-[9px] text-zinc-500 leading-relaxed">
              This action was intercepted by the Security Vault. The operation
              will remain frozen until you explicitly approve or deny it. Auto-denies
              after 30 seconds of inactivity.
            </p>
          </div>
        </div>

        {/* Footer: Actions */}
        <div
          className="px-5 py-3 border-t flex items-center gap-3"
          style={{ borderColor: colors.border }}
        >
          {/* Countdown */}
          <div className="text-[9px] font-mono text-zinc-600">
            {countdown > 0 ? (
              <span>Ready in {countdown}s</span>
            ) : (
              <span className="text-zinc-500">Ready</span>
            )}
          </div>

          <div className="flex-1" />

          {/* Deny */}
          <button
            onClick={onDeny}
            className="px-4 py-1.5 rounded-lg text-[10px] font-mono font-medium transition-all border"
            style={{
              borderColor: "rgba(239,68,68,0.3)",
              color: "#f87171",
              backgroundColor: "rgba(239,68,68,0.05)",
            }}
          >
            Deny (Esc)
          </button>

          {/* Approve */}
          <button
            onClick={handleApprove}
            disabled={countdown > 0 || isApproving}
            className="px-4 py-1.5 rounded-lg text-[10px] font-mono font-medium transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            style={{
              borderColor: colors.border,
              color: colors.text,
              backgroundColor: `${colors.text}15`,
            }}
          >
            {isApproving ? (
              <span className="flex items-center gap-1">
                <svg className="w-2.5 h-2.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.3" />
                  <path d="M12 2a10 10 0 019.95 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
                Authorizing
              </span>
            ) : (
              "Approve (Enter)"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
