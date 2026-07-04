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

  const platforms: { key: Platform; label: string }[] = [
    { key: "windows", label: "Windows" },
    { key: "macos", label: "macOS" },
    { key: "linux", label: "Linux" },
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
    } catch {}
  };

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <h1 className="text-lg font-semibold text-zinc-100">Settings</h1>

        <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3">
          <h2 className="text-sm font-medium text-zinc-300">Backend Connection</h2>
          <p className="text-sm text-zinc-500">
            Set a custom backend URL (e.g. ngrok tunnel) to run actions from anywhere.
          </p>
          <div className="space-y-2">
            <p className="text-xs text-zinc-500 font-mono">
              Active server: <span className="text-violet-400">{HF_API}</span>
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="https://your-ngrok-url.ngrok.io"
                className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 font-mono outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
              />
              <button onClick={() => setBackendUrl(urlInput)} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
                Save
              </button>
              {getBackendUrl() && (
                <button onClick={() => setBackendUrl("")} className="bg-white/[0.04] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 text-sm px-4 py-2 rounded-lg border border-white/[0.06] transition-colors duration-150">
                  Reset
                </button>
              )}
            </div>
          </div>
          {getBackendUrl() && (
            <p className="text-sm text-emerald-400">Using custom backend: {getBackendUrl()}</p>
          )}
        </section>

        <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${downloadStatus === "ok" ? "bg-emerald-400" : downloadStatus === "error" ? "bg-red-400" : "bg-zinc-600"}`} />
            <h2 className="text-sm font-medium text-zinc-300">Desktop Agent</h2>
          </div>
          <p className="text-sm text-zinc-500 leading-relaxed">
            Lets JARVIS control your machine — battery, volume, brightness, screenshots, apps,
            network scan, and 200+ actions. The agent polls the cloud every 0.5s.
          </p>

          <div className="flex border-b border-white/[0.06]">
            {platforms.map((p) => (
              <button
                key={p.key}
                onClick={() => setPlatform(p.key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors duration-150 ${
                  platform === p.key
                    ? "text-zinc-100 border-violet-500"
                    : "text-zinc-500 hover:text-zinc-300 border-transparent"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="space-y-4">
            {cur.steps.map((step, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-6 h-6 rounded-full bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-xs text-violet-400 font-mono shrink-0">
                  {i + 1}
                </div>
                <p className="text-sm text-zinc-400">{step}</p>
              </div>
            ))}

            <div className="bg-white/[0.03] rounded-lg p-3 text-sm text-zinc-300 break-all select-all relative group font-mono border border-white/[0.06]">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[10px] font-mono text-zinc-500 tracking-wider">{cur.shell} (one command)</span>
                <button
                  onClick={() => copyCmd(cur.cmd, copyKey)}
                  className={`text-[10px] font-mono px-2 py-1 rounded-lg transition-colors duration-150 ${isCopied ? "bg-emerald-500/20 text-emerald-400" : "bg-white/[0.04] text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.06]"}`}
                >
                  {isCopied ? "✓ Copied" : "Copy"}
                </button>
              </div>
              <code className="text-xs leading-relaxed text-violet-400/80">{cur.cmd}</code>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <a
              href={`${HF_API}/relay`}
              download
              className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download relay.py
            </a>
            {downloadStatus === "error" && (
              <span className="text-xs text-red-400 font-mono">Download endpoint unreachable</span>
            )}
            {downloadStatus === "ok" && (
              <span className="text-xs text-emerald-400/60 font-mono">Ready</span>
            )}
          </div>

          <p className="text-xs text-zinc-600">
            Actions include: volume, brightness, screenshots, OneNote, Outlook, Chrome, system stats,
            network scan, file ops, and 200+ more.
          </p>
        </section>

        <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
          <h2 className="text-sm font-medium text-zinc-300 mb-3">Your Plan</h2>
          <p className="text-sm text-zinc-500 mb-4">
            Currently on <span className="text-violet-400 font-medium">{tier}</span> tier.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <PricingCard
              title="Free"
              price="$0"
              features={["15 min voice chat / day", "General knowledge", "Full sass persona"]}
              active={tier === "free"}
              onSelect={() => {}}
            />
            <PricingCard
              title="Premium"
              price="$12/mo"
              features={["Unlimited voice", "Document RAG engine", "Flashcards & spaced rep", "Mock exams"]}
              active={tier === "premium"}
              onSelect={async () => {
                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/billing/checkout`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ user_id: "demo-user", return_url: window.location.origin + "/settings" }),
                });
                const data = await res.json();
                if (data.url) window.location.href = data.url;
              }}
            />
          </div>
        </section>

        <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
          <h2 className="text-sm font-medium text-zinc-300 mb-3">Manage Subscription</h2>
          <button
            onClick={async () => {
              const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/billing/portal`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "demo-user", return_url: window.location.origin + "/settings" }),
              });
              const data = await res.json();
              if (data.url) window.location.href = data.url;
            }}
            className="text-sm text-violet-400 hover:text-violet-300 transition-colors duration-150"
          >
            Open billing portal &rarr;
          </button>
        </section>
      </main>
    </div>
  );
}
