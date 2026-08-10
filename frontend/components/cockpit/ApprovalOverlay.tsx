"use client";

import React, { useState, useEffect, useCallback } from "react";

interface ApprovalOverlayProps {
  action?: string;
  details?: Record<string, string>;
  onApprove?: () => void;
  onDeny?: () => void;
  holdDuration?: number;
}

export default function ApprovalOverlay({
  action = "",
  details = {},
  onApprove,
  onDeny,
  holdDuration = 1.5,
}: ApprovalOverlayProps) {
  const [holding, setHolding] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const [startTime, setStartTime] = useState(0);

  const handleHoldStart = useCallback(() => {
    setHolding(true);
    setStartTime(Date.now());
    setHoldProgress(0);
  }, []);

  const handleHoldEnd = useCallback(() => {
    setHolding(false);
    setHoldProgress(0);
  }, []);

  useEffect(() => {
    if (!holding) return;
    const interval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      const progress = Math.min((elapsed / holdDuration) * 100, 100);
      setHoldProgress(progress);
      if (progress >= 100) {
        setHolding(false);
        if (onApprove) onApprove();
      }
    }, 50);
    return () => clearInterval(interval);
  }, [holding, startTime, holdDuration, onApprove]);

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      zIndex: 10000,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "rgba(0,0,0,0.85)",
      backdropFilter: "blur(12px)",
      animation: "fade-in 0.3s ease",
    }}>
      <div style={{
        width: 420,
        background: "linear-gradient(145deg, #0d0f12 0%, #111317 100%)",
        border: "1px solid rgba(239,68,68,0.3)",
        borderRadius: 16,
        overflow: "hidden",
        boxShadow: "0 0 80px rgba(239,68,68,0.1), 0 30px 60px rgba(0,0,0,0.5)",
        animation: "scale-in 0.3s ease",
      }}>
        <div style={{
          padding: "20px 24px 12px",
          textAlign: "center",
          borderBottom: "1px solid rgba(239,68,68,0.1)",
        }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>⚠</div>
          <div style={{
            fontSize: 13,
            color: "#EF4444",
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 600,
            letterSpacing: "0.08em",
            marginBottom: 4,
          }}>
            ACTION REQUIRED
          </div>
          <div style={{
            fontSize: 10,
            color: "#666",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            Nothing has happened yet
          </div>
        </div>

        <div style={{ padding: "16px 24px" }}>
          <div style={{
            fontSize: 12,
            color: "#e5e5e5",
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 500,
            marginBottom: 12,
          }}>
            {action}
          </div>

          {Object.keys(details).length > 0 && (
            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              padding: "10px 12px",
              borderRadius: 6,
              background: "rgba(0,0,0,0.3)",
              border: "1px solid rgba(255,255,255,0.04)",
            }}>
              {Object.entries(details).map(([key, val]) => (
                <div key={key} style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: 9,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  <span style={{ color: "#555" }}>{key}:</span>
                  <span style={{ color: "#ccc" }}>{val}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{
          display: "flex",
          gap: 8,
          padding: "12px 24px 20px",
        }}>
          {onDeny && (
            <button
              onClick={onDeny}
              style={{
                flex: 1,
                padding: "10px 0",
                borderRadius: 6,
                fontSize: 9,
                fontFamily: "'JetBrains Mono', monospace",
                background: "rgba(239,68,68,0.08)",
                border: "1px solid rgba(239,68,68,0.2)",
                color: "#EF4444",
                cursor: "pointer",
                letterSpacing: "0.05em",
              }}
            >
              CANCEL
            </button>
          )}
          <button
            onMouseDown={handleHoldStart}
            onMouseUp={handleHoldEnd}
            onMouseLeave={handleHoldEnd}
            onTouchStart={handleHoldStart}
            onTouchEnd={handleHoldEnd}
            style={{
              flex: 2,
              padding: "10px 0",
              borderRadius: 6,
              fontSize: 9,
              fontFamily: "'JetBrains Mono', monospace",
              background: holding
                ? "rgba(0,255,102," + (holdProgress / 100 * 0.2) + ")"
                : "rgba(0,255,102,0.08)",
              border: "1px solid rgba(0,255,102," + (holding ? 0.4 : 0.2) + ")",
              color: holding && holdProgress >= 100 ? "#00FF66" : "#888",
              cursor: "pointer",
              letterSpacing: "0.05em",
              position: "relative",
              overflow: "hidden",
              transition: "all 0.2s",
            }}
          >
            {holding && (
              <div style={{
                position: "absolute",
                left: 0,
                top: 0,
                bottom: 0,
                width: holdProgress + "%",
                background: "rgba(0,255,102,0.1)",
                transition: "width 0.05s linear",
              }} />
            )}
            <span style={{ position: "relative" }}>
              {holding
                ? holdProgress >= 100
                  ? "✓ APPROVED"
                  : "HOLDING... " + Math.round(holdProgress) + "%"
                : "HOLD TO APPROVE (" + holdDuration + "s)"}
            </span>
          </button>
        </div>
      </div>

      <style>{"\
        @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }\
        @keyframes scale-in { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }\
      "}</style>
    </div>
  );
}
