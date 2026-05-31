"use client";

import { useEffect, useState } from "react";

interface SceneData {
  action?: string;
  target?: string;
}

const COMMANDS: string[] = [
  "Initializing system modules...",
  "Loading configuration profiles...",
  "Connecting to services...",
  "Optimizing performance parameters...",
  "Applying system preferences...",
  "Synchronizing data across devices...",
  "Updating security protocols...",
  "Running diagnostic checks...",
  "Configuring network interfaces...",
  "Installing required components...",
  "Verifying system integrity...",
  "Deploying configuration changes...",
  "Cleaning temporary cache...",
  "Rebuilding indexes...",
  "Finalizing setup...",
];

export default function SystemSimulation({ data, progress }: { data?: SceneData; progress?: number }) {
  const [lines, setLines] = useState<string[]>(["System ready."]);
  const [cmdIndex, setCmdIndex] = useState(0);

  useEffect(() => {
    setLines(["System ready."]);
    setCmdIndex(0);

    const interval = setInterval(() => {
      if (cmdIndex < COMMANDS.length) {
        setLines(prev => [...prev, `> ${COMMANDS[cmdIndex]}`]);
        setCmdIndex(prev => prev + 1);
      }
    }, 600 + Math.random() * 400);

    return () => clearInterval(interval);
  }, [data?.target, data?.action]);

  // Keep adding until the full list is shown
  useEffect(() => {
    if (cmdIndex < COMMANDS.length) return;
    const t = setTimeout(() => {
      if (lines.length < 25) {
        setLines(prev => [...prev, `[${new Date().toLocaleTimeString()}] Operation complete.`]);
      }
    }, 1000);
    return () => clearTimeout(t);
  }, [cmdIndex, lines.length]);

  return (
    <div className="w-full h-full flex flex-col p-3">
      {/* Terminal */}
      <div className="flex-1 bg-black/40 backdrop-blur-sm border border-white/5 rounded-lg overflow-hidden font-mono">
        {/* Title bar */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border-b border-white/5">
          <div className="w-2 h-2 rounded-full bg-red-500/50" />
          <div className="w-2 h-2 rounded-full bg-yellow-500/50" />
          <div className="w-2 h-2 rounded-full bg-green-500/50" />
          <span className="text-[9px] text-white/30 ml-2">jason@system:~</span>
        </div>
        {/* Output */}
        <div className="p-2.5 max-h-[250px] overflow-y-auto space-y-0.5">
          {lines.slice(-20).map((line, i) => (
            <div
              key={i}
              className={`text-[9px] font-mono ${
                line.startsWith(">") ? "text-green-400/60" : "text-white/40"
              } ${i === Math.min(lines.length - 1, 19) ? "animate-fadeIn" : ""}`}
            >
              {line}
              {i === Math.min(lines.length - 1, 19) && !line.includes("Complete") && (
                <span className="inline-block w-1.5 h-3 bg-green-400/40 ml-0.5 animate-pulse" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-2">
        <div className="flex justify-between text-[8px] font-mono text-white/30 mb-1">
          <span>{data?.target ? `Target: ${data.target}` : "Processing..."}</span>
          <span>{progress || 0}%</span>
        </div>
        <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-green-500 via-blue-500 to-purple-500 rounded-full transition-all duration-500"
            style={{ width: `${progress || 0}%` }}
          />
        </div>
      </div>

      {/* Status indicators */}
      <div className="flex gap-3 mt-2">
        {["CPU", "MEM", "DISK", "NET"].map((label) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500/40 animate-pulse" />
            <span className="text-[7px] font-mono text-white/30">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
