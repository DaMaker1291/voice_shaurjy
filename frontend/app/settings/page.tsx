"use client";

import PricingCard from "@/components/PricingCard";
import { useState, useEffect } from "react";
import { setBackendUrl, getBackendUrl } from "@/lib/api";

export default function Settings() {
  const [tier, setTier] = useState("free");
  const [urlInput, setUrlInput] = useState("");
  const [copied, setCopied] = useState(false);
  const [origin, setOrigin] = useState("");

  useEffect(() => {
    setUrlInput(getBackendUrl());
    setOrigin(window.location.origin);
  }, []);

  const downloadLink = `${origin}/relay_agent.py`;
  const psCommand = origin ? `powershell -c "iwr -Uri '${downloadLink}' -OutFile '%TEMP%\\relay_agent.py'; python '%TEMP%\\relay_agent.py' --user $env:USERNAME"` : "";

  useEffect(() => {
    setUrlInput(getBackendUrl());
  }, []);

  return (
    <main className="max-w-2xl mx-auto p-4 space-y-6">
      <h1 className="text-2xl font-bold text-purple-400">Settings & Billing</h1>

      <section className="bg-gray-900 rounded-xl p-4">
        <h2 className="text-lg font-semibold mb-3">Backend Connection</h2>
        <p className="text-sm text-gray-400 mb-3">
          Set a custom backend URL (e.g. ngrok tunnel) to run all Windows actions from anywhere.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://your-ngrok-url.ngrok.io"
            className="flex-1 bg-gray-800 text-white rounded px-3 py-2 text-sm border border-gray-700 focus:border-purple-500 outline-none"
          />
          <button
            onClick={() => setBackendUrl(urlInput)}
            className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded text-sm font-medium"
          >
            Save
          </button>
          {getBackendUrl() && (
            <button
              onClick={() => setBackendUrl("")}
              className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded text-sm"
            >
              Reset
            </button>
          )}
        </div>
        {getBackendUrl() && (
          <p className="text-xs text-green-400 mt-2">
            Using custom backend: {getBackendUrl()}
          </p>
        )}
      </section>

      <section className="bg-gray-900 rounded-xl p-4 border border-purple-900/40">
        <h2 className="text-lg font-semibold mb-3 text-purple-300">🤖 Windows Agent</h2>
        <p className="text-sm text-gray-400 mb-4">
          To execute Windows actions (battery, OneNote, volume, etc.), run the relay agent on your PC.
          It connects to the cloud and executes actions locally.
        </p>
        {origin ? (<div className="flex flex-wrap gap-3">
          <a
            href={downloadLink}
            download
            className="bg-purple-600 hover:bg-purple-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium inline-flex items-center gap-2"
          >
            ⬇️ Download Agent
          </a>
          <button
            onClick={() => { navigator.clipboard.writeText(psCommand); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
            className="bg-gray-800 hover:bg-gray-700 text-gray-300 px-5 py-2.5 rounded-lg text-sm border border-gray-700"
          >
            {copied ? "✅ Copied!" : "📋 Copy PowerShell Command"}
          </button>
        </div>) : (
          <div className="animate-pulse h-10 bg-gray-800 rounded-lg" />
        )}
        {psCommand && (<div className="mt-3 bg-gray-950 rounded-lg p-3 text-xs text-gray-500 font-mono overflow-x-auto">
          <span className="text-green-400"># Run this in PowerShell on your Windows PC:</span><br />
          {psCommand}
        </div>)}
        <p className="text-xs text-gray-500 mt-3">
          The agent polls the cloud every 0.5s for actions assigned to your user. It auto-detects your Windows username.
        </p>
      </section>

      <section className="bg-gray-900 rounded-xl p-4">
        <h2 className="text-lg font-semibold mb-3">Your Plan</h2>
        <p className="text-sm text-gray-400 mb-4">
          Currently on <span className="text-purple-400 font-medium">{tier}</span> tier.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <PricingCard
            title="Free"
            price="$0"
            features={[
              "15 min voice chat / day",
              "General knowledge",
              "Full sass persona",
            ]}
            active={tier === "free"}
            onSelect={() => {}}
          />
          <PricingCard
            title="Premium"
            price="$12/mo"
            features={[
              "Unlimited voice",
              "Document RAG engine",
              "Flashcards & spaced rep",
              "Mock exams",
            ]}
            active={tier === "premium"}
            onSelect={async () => {
              const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/billing/checkout`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  user_id: "demo-user",
                  return_url: window.location.origin + "/settings",
                }),
              });
              const data = await res.json();
              if (data.url) window.location.href = data.url;
            }}
          />
        </div>
      </section>

      <section className="bg-gray-900 rounded-xl p-4">
        <h2 className="text-lg font-semibold mb-3">Manage Subscription</h2>
        <button
          onClick={async () => {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/billing/portal`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                user_id: "demo-user",
                return_url: window.location.origin + "/settings",
              }),
            });
            const data = await res.json();
            if (data.url) window.location.href = data.url;
          }}
          className="text-sm text-purple-400 hover:text-purple-300 underline"
        >
          Open billing portal &rarr;
        </button>
      </section>
    </main>
  );
}
