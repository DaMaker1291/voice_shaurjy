"use client";

import { useEffect, useState, useRef } from "react";

interface LogEntry {
  ts: number;
  level: "info" | "warn" | "error" | "success" | "vault";
  source: string;
  msg: string;
}

interface SystemTelemetryProps {
  systemStats?: {
    cpu?: { percent: number };
    memory?: { percent: number; used_gb: number; total_gb: number };
    battery?: { percent: number; charging: boolean };
  } | null;
  vaultMethod?: string;
  sandboxState?: string;
  healingRate?: number;
  grammarCount?: number;
  logs?: LogEntry[];
}

const LEVEL_COLORS: Record<string, string> = {
  info: "#6b7280",
  warn: "#fbbf24",
  error: "#ef4444",
  success: "#34d399",
  vault: "#a78bfa",
};

export default function SystemTelemetry({
  systemStats,
  vaultMethod = "process",
  sandboxState = "SECURE_ISOLATED",
  healingRate = 0,
  grammarCount = 6,
  logs = [],
}: SystemTelemetryProps) {
  const logEndRef = useRef<HTMLDivElement>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const i = setInterval(() => setTick((t) => t + 1), 2000);
    return () => clearInterval(i);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  const cpu = systemStats?.cpu?.percent ?? 0;
  const mem = systemStats?.memory?.percent ?? 0;
  const memUsed = systemStats?.memory?.used_gb ?? 0;
  const memTotal = systemStats?.memory?.total_gb ?? 16;
  const batt = systemStats?.battery?.percent ?? 0;
  const charging = systemStats?.battery?.charging ?? false;

  const getBarColor = (pct: number) =>
    pct > 90 ? "#ef4444" : pct > 70 ? "#fbbf24" : "#34d399";

  return (
    <div className="h-full flex flex-col font-mono">
      {/* Header */}
      <div className="px-3 py-2 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span className="text-[10px] text-zinc-500 tracking-widest uppercase">
            System Telemetry
          </span>
        </div>
      </div>

      {/* Hardware Meters */}
      <div className="px-3 py-3 border-b border-white/[0.06] space-y-3">
        {/* CPU */}
        <div>
          <div className="flex justify-between mb-1">
            <span className="text-[9px] text-zinc-500">CPU</span>
            <span className="text-[9px]" style={{ color: getBarColor(cpu) }}>
              {cpu.toFixed(1)}%
            </span>
          </div>
          <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width: `${cpu}%`,
                backgroundColor: getBarColor(cpu),
                boxShadow: `0 0 8px ${getBarColor(cpu)}44`,
              }}
            />
          </div>
        </div>

        {/* Memory */}
        <div>
          <div className="flex justify-between mb-1">
            <span className="text-[9px] text-zinc-500">RAM</span>
            <span className="text-[9px]" style={{ color: getBarColor(mem) }}>
              {memUsed.toFixed(1)}/{memTotal.toFixed(0)} GB ({mem.toFixed(0)}%)
            </span>
          </div>
          <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width: `${mem}%`,
                backgroundColor: getBarColor(mem),
                boxShadow: `0 0 8px ${getBarColor(mem)}44`,
              }}
            />
          </div>
        </div>

        {/* Battery */}
        {batt > 0 && (
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-[9px] text-zinc-500">
                BATT {charging ? "⚡" : ""}
              </span>
              <span className="text-[9px]" style={{ color: getBarColor(100 - batt) }}>
                {batt.toFixed(0)}%
              </span>
            </div>
            <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-1000"
                style={{
                  width: `${batt}%`,
                  backgroundColor: getBarColor(100 - batt),
                }}
              />
            </div>
          </div>
        )}

        {/* System status pills */}
        <div className="flex flex-wrap gap-1.5 pt-1">
          <StatusPill label="VAULT" value={vaultMethod} color="#a78bfa" />
          <StatusPill label="SANDBOX" value={sandboxState} color="#22d3ee" />
          <StatusPill label="HEAL" value={`${(healingRate * 100).toFixed(0)}%`} color="#34d399" />
          <StatusPill label="GRAMMAR" value={String(grammarCount)} color="#fbbf24" />
        </div>
      </div>

      {/* Transaction Ledger */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="px-3 py-2 border-b border-white/[0.06]">
          <span className="text-[9px] text-zinc-600 tracking-wider">
            TRANSACTION LEDGER
          </span>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
          {logs.length === 0 ? (
            <div className="text-[9px] text-zinc-700 italic">No transactions yet...</div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[9px] leading-relaxed">
                <span className="text-zinc-600 shrink-0 w-14">
                  {new Date(log.ts).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>
                <span
                  className="shrink-0 w-1 rounded-full mt-1"
                  style={{
                    height: "8px",
                    backgroundColor: LEVEL_COLORS[log.level],
                  }}
                />
                <span className="text-zinc-500 shrink-0">
                  [{log.source}]
                </span>
                <span
                  className="break-all"
                  style={{ color: LEVEL_COLORS[log.level] }}
                >
                  {log.msg}
                </span>
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}

function StatusPill({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div
      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] border"
      style={{
        borderColor: `${color}33`,
        backgroundColor: `${color}08`,
      }}
    >
      <span className="text-zinc-600">{label}</span>
      <span style={{ color }}>{value}</span>
    </div>
  );
}
