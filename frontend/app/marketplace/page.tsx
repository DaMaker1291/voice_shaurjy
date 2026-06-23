"use client";
import { useState, useEffect, useCallback } from "react";
import { getMarketplacePlugins, installPlugin, getInstalledPlugins, publishPlugin } from "@/lib/api";
import type { MarketplacePlugin } from "@/lib/types";
import { SkeletonCard } from "@/components/LoadingSkeleton";

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
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-xl font-bold text-purple-400">Plugin Marketplace</h1><p className="text-xs text-gray-500 mt-0.5">Extend your second brain with community plugins</p></div>
        <button onClick={() => setShowPublish(!showPublish)} className="text-xs text-purple-400 hover:text-purple-300">+ Publish</button>
      </div>
      {showPublish && (
        <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 space-y-3">
          <input value={pubName} onChange={e => setPubName(e.target.value)} placeholder="Plugin name" className="w-full bg-gray-800/50 border border-gray-700/50 rounded px-3 py-1.5 text-xs text-gray-200" />
          <input value={pubDesc} onChange={e => setPubDesc(e.target.value)} placeholder="Description" className="w-full bg-gray-800/50 border border-gray-700/50 rounded px-3 py-1.5 text-xs text-gray-200" />
          <input value={pubVer} onChange={e => setPubVer(e.target.value)} placeholder="Version" className="w-full bg-gray-800/50 border border-gray-700/50 rounded px-3 py-1.5 text-xs text-gray-200" />
          <button onClick={handlePublish} className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-lg">Publish</button>
        </div>
      )}
      <div className="flex gap-1 border-b border-gray-800/30 pb-2 overflow-x-auto">
        {cats.map(c => (
          <button key={c} onClick={() => setCategory(c)} className={`px-4 py-1.5 text-xs font-mono rounded-t-lg whitespace-nowrap ${category === c ? "text-purple-400 bg-purple-900/10 border-b-2 border-purple-500" : "text-gray-600 hover:text-gray-400"}`}>
            {c || "All"}
          </button>
        ))}
      </div>
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>
      ) : plugins.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plugins.map((p, i) => (
            <div key={i} className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm text-gray-200">{p.name}</h3>
                <span className="text-[10px] text-gray-500 font-mono">v{p.version}</span>
              </div>
              <p className="text-xs text-gray-500">{p.description}</p>
              <div className="flex items-center justify-between text-[10px] text-gray-600">
                <span>by {p.author}</span>
                <span>{p.downloads} downloads</span>
              </div>
              {installed.includes(p.id) ? (
                <span className="inline-block text-[10px] text-green-400 bg-green-900/20 px-2 py-0.5 rounded-full">Installed</span>
              ) : (
                <button onClick={() => handleInstall(p.id)} className="w-full px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-lg">Install</button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-20 text-gray-600 text-sm">No plugins found in this category.</div>
      )}
    </div>
  );
}
