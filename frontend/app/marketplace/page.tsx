"use client";

import { useState, useEffect, useCallback } from "react";
import { getMarketplacePlugins, installPlugin, getInstalledPlugins, publishPlugin } from "@/lib/api";
import type { MarketplacePlugin } from "@/lib/types";
import Navbar from "@/components/Navbar";

export default function MarketplacePage() {
  const [plugins, setPlugins] = useState<MarketplacePlugin[]>([]);
  const [installed, setInstalled] = useState<string[]>([]);
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [showPublish, setShowPublish] = useState(false);
  const [pubName, setPubName] = useState("");
  const [pubDesc, setPubDesc] = useState("");
  const [pubVer, setPubVer] = useState("1.0.0");

  const load = useCallback(async () => {
    setLoading(true);
    const [p, i] = await Promise.allSettled([getMarketplacePlugins(category), getInstalledPlugins()]);
    if (p.status === "fulfilled") setPlugins(p.value?.plugins || p.value || []);
    if (i.status === "fulfilled") setInstalled(i.value?.plugins?.map((pl: MarketplacePlugin) => pl.id) || []);
    setLoading(false);
  }, [category]);

  useEffect(() => { load(); }, [load]);

  const handleInstall = useCallback(async (id: string) => {
    await installPlugin(id);
    setInstalled([...installed, id]);
  }, [installed]);

  const handlePublish = useCallback(async () => {
    if (!pubName.trim()) return;
    await publishPlugin(pubName, pubDesc, pubVer);
    setShowPublish(false); setPubName(""); setPubDesc(""); setPubVer("1.0.0");
    load();
  }, [pubName, pubDesc, pubVer, load]);

  const cats = ["", "productivity", "development", "data", "automation", "ai", "entertainment"];

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Plugin Marketplace</h1>
            <p className="text-sm text-zinc-500 mt-0.5">Extend your second brain with community plugins</p>
          </div>
          <button onClick={() => setShowPublish(!showPublish)} className="text-sm text-violet-400 hover:text-violet-300 transition-colors duration-150">
            + Publish
          </button>
        </div>

        {showPublish && (
          <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3 animate-fade-in">
            <input
              value={pubName}
              onChange={e => setPubName(e.target.value)}
              placeholder="Plugin name"
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
            />
            <input
              value={pubDesc}
              onChange={e => setPubDesc(e.target.value)}
              placeholder="Description"
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
            />
            <input
              value={pubVer}
              onChange={e => setPubVer(e.target.value)}
              placeholder="Version"
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
            />
            <button onClick={handlePublish} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
              Publish
            </button>
          </div>
        )}

        <div className="flex border-b border-white/[0.06] overflow-x-auto">
          {cats.map(c => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors duration-150 ${
                category === c
                  ? "text-zinc-100 border-violet-500"
                  : "text-zinc-500 hover:text-zinc-300 border-transparent"
              }`}
            >
              {c || "All"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 animate-pulse">
                <div className="h-4 bg-white/[0.06] rounded w-1/2 mb-3" />
                <div className="h-3 bg-white/[0.04] rounded w-full mb-2" />
                <div className="h-3 bg-white/[0.04] rounded w-3/4" />
              </div>
            ))}
          </div>
        ) : plugins.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {plugins.map((p, i) => (
              <div
                key={i}
                className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3 animate-fade-in"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-zinc-200">{p.name}</h3>
                  <span className="text-xs text-zinc-500 font-mono">v{p.version}</span>
                </div>
                <p className="text-sm text-zinc-500">{p.description}</p>
                <div className="flex items-center justify-between text-xs text-zinc-500">
                  <span>by {p.author}</span>
                  <span>{p.downloads} downloads</span>
                </div>
                {installed.includes(p.id) ? (
                  <span className="inline-block text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                    Installed
                  </span>
                ) : (
                  <button onClick={() => handleInstall(p.id)} className="w-full bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-3 py-2 rounded-lg transition-colors duration-150">
                    Install
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20 text-zinc-600">
            <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            <p className="text-sm">No plugins found in this category.</p>
          </div>
        )}
      </main>
    </div>
  );
}
