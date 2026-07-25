"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { BASE, safeJson } from "@/lib/api";

interface HardwareInfo {
  cpu: { brand: string; cores: number; threads: number; freq_ghz: number; arch: string; is_arm: boolean };
  ram: { total_gb: number; available_gb: number };
  gpu: { name: string; vram_gb: number; brand: string; driver: string };
  disk: { total_gb: number; free_gb: number };
  platform: { os: string; version: string; raw: string };
  performance_tier: string;
  recommended_models: any[];
  recommended_config: any;
}

const TIER_COLORS: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  potato: { bg: "rgba(255,51,51,0.1)", text: "#FF3333", border: "rgba(255,51,51,0.3)", glow: "0 0 20px rgba(255,51,51,0.2)" },
  low: { bg: "rgba(255,179,0,0.1)", text: "#FFB300", border: "rgba(255,179,0,0.3)", glow: "0 0 20px rgba(255,179,0,0.2)" },
  mid: { bg: "rgba(0,180,216,0.1)", text: "#00B4D8", border: "rgba(0,180,216,0.3)", glow: "0 0 20px rgba(0,180,216,0.2)" },
  high: { bg: "rgba(0,255,102,0.1)", text: "#00FF66", border: "rgba(0,255,102,0.3)", glow: "0 0 20px rgba(0,255,102,0.2)" },
  ultra: { bg: "rgba(168,85,247,0.1)", text: "#A855F7", border: "rgba(168,85,247,0.3)", glow: "0 0 20px rgba(168,85,247,0.2)" },
  godlike: { bg: "linear-gradient(135deg, rgba(255,51,51,0.1), rgba(168,85,247,0.1), rgba(0,180,216,0.1))", text: "#FFD700", border: "rgba(255,215,0,0.5)", glow: "0 0 30px rgba(255,215,0,0.3)" },
  unknown: { bg: "rgba(100,100,100,0.1)", text: "#888", border: "rgba(100,100,100,0.3)", glow: "none" },
};

const TIER_LABELS: Record<string, string> = {
  potato: "🥔 Potato",
  low: "🐌 Low",
  mid: "⚡ Mid",
  high: "🚀 High",
  ultra: "🔥 Ultra",
  godlike: "💎 GODLIKE",
  unknown: "❓ Unknown",
};

const GPU_BRAND_COLORS: Record<string, string> = {
  NVIDIA: "#76B900",
  AMD: "#ED1C24",
  Apple: "#A2AAAD",
  Intel: "#0071C5",
  None: "#666",
};

export default function HardwarePage() {
  const [hw, setHw] = useState<HardwareInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "models" | "config">("overview");

  const fetchHardware = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${BASE}/api/hardware/detect`);
      const data = await safeJson(res);
      if (data.error) throw new Error(data.error);
      setHw(data);
    } catch (e: any) {
      setError(e.message || "Failed to detect hardware");
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchHardware(); }, [fetchHardware]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#09090b", color: "#e4e4e7", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-sans, system-ui, sans-serif)" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <div style={{ fontSize: 14, color: "#a1a1aa" }}>Scanning your hardware...</div>
        </div>
      </div>
    );
  }

  if (error || !hw) {
    return (
      <div style={{ minHeight: "100vh", background: "#09090b", color: "#e4e4e7", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-sans, system-ui, sans-serif)" }}>
        <div style={{ textAlign: "center", maxWidth: 400 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <div style={{ fontSize: 16, marginBottom: 8 }}>{error || "Hardware detection failed"}</div>
          <button onClick={fetchHardware} style={{ padding: "8px 20px", borderRadius: 8, background: "#00B4D8", color: "#000", border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>Retry</button>
        </div>
      </div>
    );
  }

  const tierStyle = TIER_COLORS[hw.performance_tier] || TIER_COLORS.unknown;
  const topModel = hw.recommended_models?.[0];
  const localModels = hw.recommended_models?.filter((m: any) => m.type !== "cloud_api") || [];
  const cloudModels = hw.recommended_models?.filter((m: any) => m.type === "cloud_api") || [];

  return (
    <div style={{ minHeight: "100vh", background: "#09090b", color: "#e4e4e7", fontFamily: "var(--font-sans, system-ui, sans-serif)", padding: "20px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <Link href="/" style={{ fontSize: 12, color: "#52525b", textDecoration: "none" }}>← Back to JARVIS</Link>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: "4px 0 0", color: "#fff" }}>Hardware Intelligence</h1>
          <p style={{ fontSize: 13, color: "#71717a", margin: "2px 0 0" }}>Your machine detected — AI models optimized for your hardware</p>
        </div>
        <button onClick={fetchHardware} style={{ padding: "6px 14px", borderRadius: 6, background: "rgba(255,255,255,0.05)", color: "#a1a1aa", border: "1px solid rgba(255,255,255,0.1)", cursor: "pointer", fontSize: 12 }}>↻ Refresh</button>
      </div>

      {/* Tier Banner */}
      <div style={{ background: tierStyle.bg, border: `1px solid ${tierStyle.border}`, borderRadius: 12, padding: "20px 24px", marginBottom: 20, boxShadow: tierStyle.glow }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, color: "#71717a", marginBottom: 4 }}>PERFORMANCE TIER</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: tierStyle.text }}>{TIER_LABELS[hw.performance_tier]}</div>
          </div>
          {topModel && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: "#71717a", marginBottom: 2 }}>TOP RECOMMENDATION</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: "#e4e4e7" }}>{topModel.name}</div>
              <div style={{ fontSize: 11, color: "#a1a1aa" }}>{topModel.speed} • {topModel.size_gb || topModel.cost}</div>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
        {(["overview", "models", "config"] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            style={{ padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 500, border: "none", cursor: "pointer",
              background: activeTab === tab ? "rgba(0,180,216,0.15)" : "rgba(255,255,255,0.03)",
              color: activeTab === tab ? "#00B4D8" : "#71717a",
              transition: "all 0.2s" }}>
            {tab === "overview" ? "📊 Overview" : tab === "models" ? "🤖 AI Models" : "⚙️ Config"}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
          {/* CPU Card */}
          <HardwareCard title="CPU" icon="🧠" items={[
            { label: "Brand", value: hw.cpu.brand },
            { label: "Cores / Threads", value: `${hw.cpu.cores} / ${hw.cpu.threads}` },
            { label: "Clock Speed", value: `${hw.cpu.freq_ghz} GHz` },
            { label: "Architecture", value: hw.cpu.arch + (hw.cpu.is_arm ? " (ARM)" : " (x86)") },
          ]} />

          {/* RAM Card */}
          <HardwareCard title="Memory" icon="💾" items={[
            { label: "Total", value: `${hw.ram.total_gb} GB` },
            { label: "Available", value: `${hw.ram.available_gb} GB` },
            { label: "Usage", value: `${Math.round((1 - hw.ram.available_gb / hw.ram.total_gb) * 100)}%`, color: hw.ram.available_gb < 2 ? "#FF3333" : "#00FF66" },
          ]} />

          {/* GPU Card */}
          <HardwareCard title="GPU" icon="🎮" items={[
            { label: "Name", value: hw.gpu.name, color: GPU_BRAND_COLORS[hw.gpu.brand] || "#888" },
            { label: "VRAM", value: hw.gpu.vram_gb > 0 ? `${hw.gpu.vram_gb} GB` : "Integrated / None" },
            { label: "Brand", value: hw.gpu.brand },
            ...(hw.gpu.driver ? [{ label: "Driver", value: hw.gpu.driver }] : []),
          ]} />

          {/* Disk Card */}
          <HardwareCard title="Storage" icon="💿" items={[
            { label: "Total", value: `${hw.disk.total_gb} GB` },
            { label: "Free", value: `${hw.disk.free_gb} GB`, color: hw.disk.free_gb < 20 ? "#FF3333" : "#00FF66" },
            { label: "Usage", value: `${Math.round((1 - hw.disk.free_gb / hw.disk.total_gb) * 100)}%` },
          ]} />

          {/* Platform Card */}
          <HardwareCard title="Platform" icon="🖥️" items={[
            { label: "OS", value: hw.platform.os },
            { label: "Version", value: hw.platform.version?.substring(0, 50) || "Unknown" },
            { label: "Raw", value: hw.platform.raw?.substring(0, 60) || "" },
          ]} />

          {/* Quick Config Card */}
          <HardwareCard title="Recommended Config" icon="⚙️" items={[
            { label: "Local Model", value: hw.recommended_config.local_model_enabled ? "✅ Enabled" : "❌ Disabled" },
            { label: "Voice Engine", value: hw.recommended_config.voice_engine },
            { label: "Max Agents", value: `${hw.recommended_config.max_concurrent_agents}` },
            { label: "Headless VDI", value: hw.recommended_config.headless_workstation ? "✅ Available" : "❌ Not available" },
          ]} />
        </div>
      )}

      {/* Models Tab */}
      {activeTab === "models" && (
        <div>
          {localModels.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: "#00FF66" }}>🤖 Local Models (Run on Your Hardware)</h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 12 }}>
                {localModels.map((model: any, i: number) => (
                  <ModelCard key={i} model={model} />
                ))}
              </div>
            </div>
          )}

          {cloudModels.length > 0 && (
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: "#00B4D8" }}>☁️ Cloud APIs (When Local Isn&apos;t Enough)</h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 12 }}>
                {cloudModels.map((model: any, i: number) => (
                  <ModelCard key={i} model={model} isCloud />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Config Tab */}
      {activeTab === "config" && (
        <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, padding: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Optimal Configuration for Your Hardware</h2>
          <pre style={{ fontSize: 12, color: "#a1a1aa", lineHeight: 1.6, overflow: "auto", fontFamily: "var(--font-mono, monospace)" }}>
            {JSON.stringify(hw.recommended_config, null, 2)}
          </pre>
          <div style={{ marginTop: 16, padding: 12, background: "rgba(0,180,216,0.08)", borderRadius: 8, border: "1px solid rgba(0,180,216,0.2)" }}>
            <div style={{ fontSize: 12, color: "#00B4D8", fontWeight: 600, marginBottom: 4 }}>💡 Quick Setup</div>
            <div style={{ fontSize: 11, color: "#a1a1aa", lineHeight: 1.5 }}>
              {hw.recommended_config.local_model_enabled
                ? `Your hardware can run local AI models. Download the recommended model from the Models tab and place it in your JARVIS models folder. The engine will auto-detect and load it.`
                : `Your hardware is best suited for cloud APIs. We recommend Groq (free tier) for the fastest responses. Set GROQ_API_KEY in your .env file.`
              }
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function HardwareCard({ title, icon, items }: { title: string; icon: string; items: { label: string; value: string; color?: string }[] }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
        <span>{icon}</span> {title}
      </div>
      {items.map((item, i) => (
        <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: i < items.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}>
          <span style={{ fontSize: 11, color: "#71717a" }}>{item.label}</span>
          <span style={{ fontSize: 11, color: item.color || "#e4e4e7", fontWeight: 500, textAlign: "right", maxWidth: "60%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.value}</span>
        </div>
      ))}
    </div>
  );
}

function ModelCard({ model, isCloud = false }: { model: any; isCloud?: boolean }) {
  const tierColors: Record<string, string> = { potato: "#FF3333", low: "#FFB300", mid: "#00B4D8", high: "#00FF66", ultra: "#A855F7", godlike: "#FFD700" };

  return (
    <div style={{
      background: model.recommended ? "rgba(0,255,102,0.05)" : "rgba(255,255,255,0.02)",
      border: `1px solid ${model.recommended ? "rgba(0,255,102,0.2)" : "rgba(255,255,255,0.06)"}`,
      borderRadius: 10, padding: 16, position: "relative",
    }}>
      {model.recommended && (
        <div style={{ position: "absolute", top: 8, right: 8, fontSize: 9, background: "rgba(0,255,102,0.15)", color: "#00FF66", padding: "2px 8px", borderRadius: 4, fontWeight: 600 }}>★ RECOMMENDED</div>
      )}
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, paddingRight: model.recommended ? 90 : 0 }}>{model.name}</div>
      <div style={{ fontSize: 11, color: "#a1a1aa", marginBottom: 8, lineHeight: 1.4 }}>{model.quality}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
        {model.speed && <Tag color="#00B4D8">{model.speed}</Tag>}
        {model.size_gb && <Tag color="#A855F7">{model.size_gb} GB</Tag>}
        {model.license && <Tag color="#71717a">{model.license}</Tag>}
        {model.type === "cloud_api" && <Tag color="#FFB300">☁️ Cloud</Tag>}
        {model.use_case && <Tag color="#52525b">{model.use_case}</Tag>}
      </div>
      {model.tier && (
        <div style={{ display: "flex", gap: 4 }}>
          {model.tier.map((t: string) => (
            <span key={t} style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: `${tierColors[t]}15`, color: tierColors[t] }}>{t}</span>
          ))}
        </div>
      )}
      {model.url && (
        <a href={model.url} target="_blank" rel="noopener noreferrer"
          style={{ display: "inline-block", marginTop: 8, fontSize: 11, color: "#00B4D8", textDecoration: "none" }}>
          View on Hugging Face →
        </a>
      )}
    </div>
  );
}

function Tag({ color, children }: { color: string; children: React.ReactNode }) {
  return <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: `${color}15`, color, border: `1px solid ${color}30` }}>{children}</span>;
}
