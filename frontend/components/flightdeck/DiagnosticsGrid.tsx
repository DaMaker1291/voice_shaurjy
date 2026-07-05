"use client";

import { useEffect, useState } from "react";

interface DiagnosticsGridProps {
  p95Latency?: number;
  p50Latency?: number;
  currentLatency?: number;
  slaViolations?: number;
  selfHealingRate?: number;
  totalHeals?: number;
  successfulHeals?: number;
  sandboxMethod?: string;
  grammarCount?: number;
  entityCount?: number;
  eventCount?: number;
  activeAgents?: number;
}

interface MetricCardProps {
  label: string;
  value: string;
  subtext?: string;
  color: string;
  trend?: "up" | "down" | "stable";
  target?: string;
  hit?: boolean;
}

function MetricCard({ label, value, subtext, color, trend, target, hit }: MetricCardProps) {
  return (
    <div
      className="rounded-lg border px-3 py-2.5 transition-all duration-300"
      style={{
        borderColor: `${color}22`,
        backgroundColor: `${color}06`,
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] font-mono text-zinc-500 tracking-wider uppercase">
          {label}
        </span>
        {target && (
          <span
            className="text-[8px] font-mono px-1 py-0.5 rounded"
            style={{
              color: hit ? "#34d399" : "#f97316",
              backgroundColor: hit ? "rgba(52,211,153,0.1)" : "rgba(249,115,22,0.1)",
            }}
          >
            target: {target}
          </span>
        )}
      </div>
      <div className="flex items-end gap-2">
        <span
          className="text-xl font-light font-mono"
          style={{ color }}
        >
          {value}
        </span>
        {subtext && (
          <span className="text-[9px] font-mono text-zinc-500 mb-0.5">
            {subtext}
          </span>
        )}
      </div>
      {trend && (
        <div className="mt-1 flex items-center gap-1">
          <svg
            className="w-2.5 h-2.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke={
              trend === "up" ? "#34d399" : trend === "down" ? "#ef4444" : "#6b7280"
            }
            strokeWidth="2"
          >
            {trend === "up" && (
              <path strokeLinecap="round" strokeLinejoin="round" d="M7 17l9.2-9.2M17 17V7H7" />
            )}
            {trend === "down" && (
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 7l-9.2 9.2M7 7v10h10" />
            )}
            {trend === "stable" && (
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
            )}
          </svg>
          <span
            className="text-[8px] font-mono"
            style={{
              color: trend === "up" ? "#34d399" : trend === "down" ? "#ef4444" : "#6b7280",
            }}
          >
            {trend === "up" ? "improving" : trend === "down" ? "degrading" : "stable"}
          </span>
        </div>
      )}
    </div>
  );
}

export default function DiagnosticsGrid({
  p95Latency = 0,
  p50Latency = 0,
  currentLatency = 0,
  slaViolations = 0,
  selfHealingRate = 0,
  totalHeals = 0,
  successfulHeals = 0,
  sandboxMethod = "process",
  grammarCount = 6,
  entityCount = 0,
  eventCount = 0,
  activeAgents = 0,
}: DiagnosticsGridProps) {
  const [history, setHistory] = useState<number[]>([]);

  useEffect(() => {
    setHistory((h) => [...h.slice(-29), currentLatency]);
  }, [currentLatency]);

  const healingPct = totalHeals > 0 ? (successfulHeals / totalHeals) * 100 : 0;

  return (
    <div className="space-y-3">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <div className="w-1 h-4 rounded-full bg-violet-500" />
        <span className="text-[10px] font-mono text-zinc-400 tracking-widest uppercase">
          Performance Diagnostics
        </span>
      </div>

      {/* Latency sparkline */}
      <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[9px] font-mono text-zinc-500">LATENCY TRACE (30s)</span>
          <span className="text-[9px] font-mono text-zinc-600">
            {history.length} samples
          </span>
        </div>
        <svg viewBox="0 0 300 40" className="w-full h-10">
          {/* Grid */}
          {[0, 10, 20, 30, 40].map((y) => (
            <line
              key={y}
              x1={0}
              y1={y}
              x2={300}
              y2={y}
              stroke="rgba(255,255,255,0.03)"
              strokeWidth="0.5"
            />
          ))}
          {/* SLA line at 50ms */}
          <line
            x1={0}
            y1={20}
            x2={300}
            y2={20}
            stroke="rgba(251,191,36,0.3)"
            strokeWidth="0.5"
            strokeDasharray="4,4"
          />
          <text x={302} y={22} fill="rgba(251,191,36,0.4)" fontSize="6" fontFamily="monospace">
            50ms
          </text>
          {/* Latency line */}
          {history.length > 1 && (
            <polyline
              points={history
                .map((v, i) => {
                  const x = (i / Math.max(history.length - 1, 1)) * 300;
                  const y = Math.min(40, Math.max(0, 40 - (v / 100) * 40));
                  return `${x},${y}`;
                })
                .join(" ")}
              fill="none"
              stroke="#a78bfa"
              strokeWidth="1.5"
              strokeLinejoin="round"
              filter="url(#sparkGlow)"
            />
          )}
          {/* Glow filter */}
          <defs>
            <filter id="sparkGlow">
              <feGaussianBlur stdDeviation="1.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {/* Current point */}
          {history.length > 0 && (
            <circle
              cx={300}
              cy={Math.min(40, Math.max(0, 40 - (history[history.length - 1] / 100) * 40))}
              r="3"
              fill="#a78bfa"
              filter="url(#sparkGlow)"
            />
          )}
        </svg>
      </div>

      {/* Metric cards grid */}
      <div className="grid grid-cols-2 gap-2">
        <MetricCard
          label="P95 Latency"
          value={`${p95Latency.toFixed(0)}`}
          subtext="ms"
          color="#a78bfa"
          target="<15ms"
          hit={p95Latency < 15}
          trend={p95Latency < 15 ? "stable" : p95Latency < 50 ? "up" : "down"}
        />
        <MetricCard
          label="P50 Latency"
          value={`${p50Latency.toFixed(0)}`}
          subtext="ms"
          color="#22d3ee"
          target="<10ms"
          hit={p50Latency < 10}
        />
        <MetricCard
          label="Self-Heal Rate"
          value={`${healingPct.toFixed(0)}`}
          subtext="%"
          color="#34d399"
          target=">94%"
          hit={healingPct > 94}
        />
        <MetricCard
          label="SLA Breaks"
          value={`${slaViolations}`}
          color={slaViolations > 0 ? "#ef4444" : "#34d399"}
          target="0"
          hit={slaViolations === 0}
        />
        <MetricCard
          label="Active Agents"
          value={`${activeAgents}`}
          subtext="/4"
          color="#f472b6"
        />
        <MetricCard
          label="Memories"
          value={`${entityCount}`}
          subtext="entities"
          color="#c084fc"
        />
      </div>

      {/* Sandbox & Grammar status */}
      <div className="flex gap-2">
        <div
          className="flex-1 rounded-lg border px-3 py-2"
          style={{
            borderColor: "rgba(34,211,238,0.15)",
            backgroundColor: "rgba(34,211,238,0.03)",
          }}
        >
          <div className="text-[8px] font-mono text-zinc-600 mb-1">SANDBOX</div>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <span className="text-[10px] font-mono text-emerald-400">
              {sandboxMethod.toUpperCase()}_ISOLATED
            </span>
          </div>
        </div>
        <div
          className="flex-1 rounded-lg border px-3 py-2"
          style={{
            borderColor: "rgba(251,191,36,0.15)",
            backgroundColor: "rgba(251,191,36,0.03)",
          }}
        >
          <div className="text-[8px] font-mono text-zinc-600 mb-1">GRAMMARS</div>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
            <span className="text-[10px] font-mono text-yellow-400">
              {grammarCount} LOCKED
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
