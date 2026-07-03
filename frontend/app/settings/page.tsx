"use client";

import PricingCard from "@/components/PricingCard";
import { useState, useEffect } from "react";
import { setBackendUrl, getBackendUrl } from "@/lib/api";

const HF_API = "https://dgfhgjhj-jarvis-ai-brain.hf.space";

export default function Settings() {
  const [tier, setTier] = useState("free");
  const [urlInput, setUrlInput] = useState("");
  const [copied, setCopied] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState<"idle" | "checking" | "ok" | "error">("idle");

  useEffect(() => {
    setUrlInput(getBackendUrl());
    fetch(`${HF_API}/relay`, { method: "HEAD" })
      .then(r => setDownloadStatus(r.ok ? "ok" : "error"))
      .catch(() => setDownloadStatus("error"));
  }, []);

  const psCommand = `powershell -c "curl.exe -sL '${HF_API}/relay' -o \\$env:TEMP\\relay.py; python \\$env:TEMP\\relay.py --user \\$env:USERNAME"`;

  const copyCmd = async () => {
    try {
      await navigator.clipboard.writeText(psCommand);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { }
  };

  return (
    <main className="max-w-2xl mx-auto p-4 space-y-6">
      <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-300 to-cyan-300 bg-clip-text text-transparent">Settings</h1>

      {/* ── Backend Connection ── */}
      <section className="glass-card p-4">
        <h2 className="text-sm font-semibold text-gray-200 mb-3">Backend Connection</h2>
        <p className="text-xs text-gray-500 mb-3">
          Set a custom backend URL (e.g. ngrok tunnel) to run actions from anywhere.
        </p>
        <div className="space-y-2">
          <p className="text-[10px] font-mono text-gray-600">
            Active server: <span className="text-cyan-400">{HF_API}</span>
          </p>
          <div className="flex gap-2">
            <input type="text" value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://your-ngrok-url.ngrok.io"
              className="flex-1 bg-gray-900 text-gray-300 rounded-lg px-3 py-2 text-xs font-mono border border-gray-800 focus:border-purple-500/50 outline-none transition-all" />
            <button onClick={() => setBackendUrl(urlInput)}
              className="bg-purple-600/80 hover:bg-purple-500 text-white px-4 py-2 rounded-lg text-xs font-medium transition-all">
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
        {getBackendUrl() && <p className="text-xs text-green-400 mt-2">Using custom backend: {getBackendUrl()}</p>}
      </section>

      {/* ── Windows Relay Agent ── */}
      <section className="glass-card p-4 border border-purple-800/30">
        <div className="flex items-center gap-2 mb-3">
          <div className={`w-2 h-2 rounded-full ${downloadStatus === "ok" ? "bg-green-400" : downloadStatus === "error" ? "bg-red-400" : "bg-gray-600"}`} />
          <h2 className="text-sm font-semibold text-gray-200">Windows Agent</h2>
        </div>
        <p className="text-xs text-gray-500 mb-4 leading-relaxed">
          This lets JARVIS control your Windows PC — battery, volume, brightness, screenshots, OneNote,
          Chrome, network scan, and 200+ other actions. The agent polls the cloud every 0.5s.
        </p>

        <div className="bg-gray-950/60 rounded-xl p-4 space-y-4">
          <div className="flex items-center gap-3">
            <div className="step-num">1</div>
            <p className="text-xs text-gray-400">Install Python 3.10+ from <a href="https://python.org/downloads" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 underline">python.org</a></p>
          </div>

          <div className="flex items-center gap-3">
            <div className="step-num">2</div>
            <p className="text-xs text-gray-400">Open <strong className="text-gray-300">PowerShell</strong> and paste this:</p>
          </div>

          <div className="bg-gray-900 rounded-xl p-3 text-xs text-gray-300 break-all select-all relative group font-mono border border-purple-800/20">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[9px] font-mono text-gray-600 tracking-wider">PowerShell (one command)</span>
              <button onClick={copyCmd}
                className={`text-[9px] font-mono px-2 py-1 rounded-lg transition-all ${copied ? "bg-green-900/30 text-green-400" : "bg-gray-800 text-gray-500 hover:text-gray-300 hover:bg-gray-700"}`}>
                {copied ? "✓ Copied" : "Copy"}
              </button>
            </div>
            <code className="text-[11px] leading-relaxed text-purple-200/80">{psCommand}</code>
          </div>

          <div className="flex items-center gap-3">
            <div className="step-num">3</div>
            <p className="text-xs text-gray-400">Keep the terminal window open — you're connected.</p>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <a href={`${HF_API}/relay`} download
            className="inline-flex items-center gap-2 bg-purple-600 hover:bg-purple-500 text-white px-5 py-2.5 rounded-xl text-xs font-medium transition-all">
            Download relay.py
          </a>
          {downloadStatus === "error" && (
            <span className="text-[10px] text-red-400 font-mono">Download endpoint unreachable</span>
          )}
          {downloadStatus === "ok" && (
            <span className="text-[10px] text-green-400/60 font-mono">Ready</span>
          )}
        </div>

        <p className="text-[10px] text-gray-600 mt-3">
          Actions include: volume, brightness, screenshots, OneNote, Outlook, Chrome, system stats,
          network scan, file ops, and 200+ more.
        </p>
      </section>

      {/* ── Plan ── */}
      <section className="glass-card p-4">
        <h2 className="text-sm font-semibold text-gray-200 mb-3">Your Plan</h2>
        <p className="text-xs text-gray-500 mb-4">
          Currently on <span className="text-purple-400 font-medium">{tier}</span> tier.
        </p>
        <div className="grid grid-cols-2 gap-4">
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
        }} className="text-xs text-purple-400 hover:text-purple-300 underline">
          Open billing portal &rarr;
        </button>
      </section>
    </main>
  );
}
