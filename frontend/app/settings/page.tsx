"use client";

import PricingCard from "@/components/PricingCard";
import { useState, useEffect } from "react";
import { setBackendUrl, getBackendUrl } from "@/lib/api";
import Navbar from "@/components/Navbar";

const HF_API = "https://dgfhgjhj-jarvis-ai-brain.hf.space";

type Platform = "windows" | "macos" | "linux";

function detectPlatform(): Platform {
  if (typeof window === "undefined") return "windows";
  const p = navigator.platform?.toLowerCase() || "";
  if (p.includes("win")) return "windows";
  if (p.includes("mac")) return "macos";
  return "linux";
}

export default function Settings() {
  const [tier, setTier] = useState("free");
  const [urlInput, setUrlInput] = useState("");
  const [copied, setCopied] = useState<Record<string, boolean>>({});
  const [downloadStatus, setDownloadStatus] = useState<"idle" | "checking" | "ok" | "error">("idle");
  const [platform, setPlatform] = useState<Platform>("windows");

  useEffect(() => {
    setPlatform(detectPlatform());
    setUrlInput(getBackendUrl());
    fetch(`${HF_API}/relay`, { method: "HEAD" })
      .then(r => setDownloadStatus(r.ok ? "ok" : "error"))
      .catch(() => setDownloadStatus("error"));
  }, []);

  const platforms: { key: Platform; label: string; icon: string }[] = [
    { key: "windows", label: "Windows", icon: "⊞" },
    { key: "macos", label: "macOS", icon: "⌘" },
    { key: "linux", label: "Linux", icon: "🐧" },
  ];

  const commands: Record<Platform, { shell: string; cmd: string; steps: string[] }> = {
    windows: {
      shell: "PowerShell",
      cmd: `powershell -c "curl.exe -sL '${HF_API}/relay' -o \\$env:TEMP\\relay.py; python \\$env:TEMP\\relay.py --user \\$env:USERNAME"`,
      steps: [
        "Install Python 3.10+ from python.org",
        "Open PowerShell and paste the command below",
        "Keep the terminal open — you're connected",
      ],
    },
    macos: {
      shell: "Terminal",
      cmd: `curl -sL '${HF_API}/relay' -o ~/relay.py && python3 ~/relay.py --user $(whoami)`,
      steps: [
        "macOS comes with Python 3 pre-installed",
        "Open Terminal and paste the command below",
        "Keep the terminal open — you're connected",
      ],
    },
    linux: {
      shell: "Terminal",
      cmd: `curl -sL '${HF_API}/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user $(whoami)`,
      steps: [
        "Ensure Python 3 is installed (python3 --version)",
        "Open a terminal and paste the command below",
        "Keep the terminal open — you're connected",
      ],
    },
  };

  const cur = commands[platform];
  const copyKey = platform;
  const isCopied = !!copied[copyKey];

  const copyCmd = async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied((p) => ({ ...p, [key]: true }));
      setTimeout(() => setCopied((p) => ({ ...p, [key]: false })), 2000);
    } catch { }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#030512]">
      <Navbar />
      <main className="page-ambient flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto p-4 sm:p-6 space-y-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-1 h-6 rounded-full bg-gradient-to-b from-[#a78bfa] to-[#22d3ee]" />
            <h1 className="text-xl font-bold bg-gradient-to-r from-purple-300 to-cyan-300 bg-clip-text text-transparent tracking-tight">Settings</h1>
            <div className="flex-1 h-px bg-gradient-to-r from-purple-800/20 to-transparent" />
          </div>

          <section className="glass-card p-4">
            <h2 className="text-sm font-semibold text-gray-200 mb-3">Backend Connection</h2>
            <p className="text-xs text-gray-500 mb-3">
              Set a custom backend URL (e.g. ngrok tunnel) to run actions from anywhere.
            </p>
            <div className="space-y-2">
              <p className="text-[10px] font-mono text-gray-600">
                Active server: <span className="text-[#22d3ee]">{HF_API}</span>
              </p>
              <div className="flex gap-2">
                <input type="text" value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://your-ngrok-url.ngrok.io"
                  className="flex-1 bg-gray-900 text-gray-300 rounded-lg px-3 py-2 text-xs font-mono border border-gray-800 focus:border-[#a78bfa]/50 outline-none transition-all" />
                <button onClick={() => setBackendUrl(urlInput)}
                  className="bg-[#a78bfa]/80 hover:bg-[#a78bfa] text-white px-4 py-2 rounded-lg text-xs font-medium transition-all">
                  Save
                </button>
                {getBackendUrl() && (
                  <button onClick={() => setBackendUrl("")}
                    className="bg-gray-800 hover:bg-gray-700 text-gray-400 px-4 py-2 rounded-lg text-xs transition-all">
                    Reset
                  </button>
                )}
              </div>
            </div>
            {getBackendUrl() && <p className="text-xs text-[#34d399] mt-2">Using custom backend: {getBackendUrl()}</p>}
          </section>

          <section className="glass-card p-4 border border-[#a78bfa]/[0.12]">
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-2 h-2 rounded-full ${downloadStatus === "ok" ? "bg-[#34d399]" : downloadStatus === "error" ? "bg-[#ef4444]" : "bg-gray-600"}`} />
              <h2 className="text-sm font-semibold text-gray-200">Desktop Agent</h2>
            </div>
            <p className="text-xs text-gray-500 mb-4 leading-relaxed">
              Lets JARVIS control your machine — battery, volume, brightness, screenshots, apps,
              network scan, and 200+ actions. The agent polls the cloud every 0.5s.
            </p>

            <div className="flex gap-1 mb-4 bg-gray-950/50 rounded-xl p-1 border border-purple-900/10">
              {platforms.map((p) => (
                <button
                  key={p.key}
                  onClick={() => setPlatform(p.key)}
                  className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[10px] font-mono transition-all ${
                    platform === p.key
                      ? "bg-[#a78bfa]/20 text-purple-300 border border-[#a78bfa]/30 shadow-sm"
                      : "text-gray-600 hover:text-gray-400 hover:bg-gray-900/50"
                  }`}
                >
                  <span>{p.icon}</span>
                  <span>{p.label}</span>
                </button>
              ))}
            </div>

            <div className="bg-gray-950/60 rounded-xl p-4 space-y-4">
              {cur.steps.map((step, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="step-num">{i + 1}</div>
                  <p className="text-xs text-gray-400">{step}</p>
                </div>
              ))}

              <div className="bg-gray-900 rounded-xl p-3 text-xs text-gray-300 break-all select-all relative group font-mono border border-[#a78bfa]/10">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] font-mono text-gray-600 tracking-wider">{cur.shell} (one command)</span>
                  <button onClick={() => copyCmd(cur.cmd, copyKey)}
                    className={`text-[9px] font-mono px-2 py-1 rounded-lg transition-all ${isCopied ? "bg-[#34d399]/30 text-[#34d399]" : "bg-gray-800 text-gray-500 hover:text-gray-300 hover:bg-gray-700"}`}>
                    {isCopied ? "✓ Copied" : "Copy"}
                  </button>
                </div>
                <code className="text-[11px] leading-relaxed text-[#a78bfa]/80">{cur.cmd}</code>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-3">
              <a href={`${HF_API}/relay`} download
                className="download-btn-pulse inline-flex items-center gap-2 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 text-white px-5 py-2.5 rounded-xl text-xs font-medium transition-all shadow-lg shadow-purple-900/20">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Download relay.py
              </a>
              {downloadStatus === "error" && (
                <span className="text-[10px] text-[#ef4444] font-mono">Download endpoint unreachable</span>
              )}
              {downloadStatus === "ok" && (
                <span className="text-[10px] text-[#34d399]/60 font-mono">Ready</span>
              )}
            </div>

            <p className="text-[10px] text-gray-600 mt-3">
              Actions include: volume, brightness, screenshots, OneNote, Outlook, Chrome, system stats,
              network scan, file ops, and 200+ more.
            </p>
          </section>

          <section className="glass-card p-4">
            <h2 className="text-sm font-semibold text-gray-200 mb-3">Your Plan</h2>
            <p className="text-xs text-gray-500 mb-4">
              Currently on <span className="text-[#a78bfa] font-medium">{tier}</span> tier.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <PricingCard title="Free" price="$0"
                features={["15 min voice chat / day", "General knowledge", "Full sass persona"]}
                active={tier === "free"} onSelect={() => {}} />
              <PricingCard title="Premium" price="$12/mo"
                features={["Unlimited voice", "Document RAG engine", "Flashcards & spaced rep", "Mock exams"]}
                active={tier === "premium"}
                onSelect={async () => {
                  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/billing/checkout`, {
                    method: "POST", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_id: "demo-user", return_url: window.location.origin + "/settings" }),
                  });
                  const data = await res.json();
                  if (data.url) window.location.href = data.url;
                }} />
            </div>
          </section>

          <section className="glass-card p-4">
            <h2 className="text-sm font-semibold text-gray-200 mb-3">Manage Subscription</h2>
            <button onClick={async () => {
              const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/billing/portal`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "demo-user", return_url: window.location.origin + "/settings" }),
              });
              const data = await res.json();
              if (data.url) window.location.href = data.url;
            }} className="text-xs text-[#a78bfa] hover:text-purple-300 underline">
              Open billing portal &rarr;
            </button>
          </section>
        </div>
      </main>
    </div>
  );
}
