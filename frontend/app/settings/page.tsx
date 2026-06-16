"use client";

import PricingCard from "@/components/PricingCard";
import { useState, useEffect } from "react";
import { setBackendUrl, getBackendUrl } from "@/lib/api";

export default function Settings() {
  const [tier, setTier] = useState("free");
  const [urlInput, setUrlInput] = useState("");

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
          Run the relay agent on your Windows PC to execute actions locally (battery, OneNote, volume, network scan, etc.).
          It polls the cloud every 0.5s and runs actions on your machine.
        </p>

        <div className="bg-gray-950 rounded-lg p-4 space-y-3 text-sm font-mono">
          <p className="text-green-400 text-xs font-semibold tracking-wide"># One-click install — run this in PowerShell:</p>
          <div className="bg-gray-900 rounded p-3 text-xs text-gray-300 break-all select-all leading-relaxed">
            {"powershell -c \"& { iwr -Uri 'https://dgfhgjhj-my-actual-brain.hf.space/relay_agent.py' -OutFile \"$env:TEMP\\relay_agent.py\"; python \"$env:TEMP\\relay_agent.py\" --user $env:USERNAME }\""}
          </div>

          <div className="pt-3 border-t border-gray-800 space-y-1.5">
            <p className="text-purple-400 text-xs font-semibold tracking-wide"># Manual setup (if one-click fails):</p>
            <p className="text-gray-500 text-xs">
              1. Install Python 3.10+ from <a href="https://python.org/downloads" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300">python.org</a>
            </p>
            <p className="text-gray-500 text-xs">
              2. Clone the repo and run:
            </p>
            <div className="bg-gray-900/60 rounded p-2 text-xs text-gray-400 break-all select-all">
              git clone https://github.com/DaMaker1291/voice_shaurjy.git &amp;&amp; cd voice_shaurjy &amp;&amp; pip install -r backend/requirements-render.txt &amp;&amp; python relay_agent.py --user local
            </div>
          </div>
        </div>

        <p className="text-xs text-gray-500 mt-3">
          The agent polls the cloud every 0.5s for actions assigned to your user. Keep the terminal window open while using the assistant.
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
