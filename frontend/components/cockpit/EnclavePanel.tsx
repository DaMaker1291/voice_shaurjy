"use client";

import React, { useState, useEffect, useCallback } from "react";
import { BASE, safeJson } from "@/lib/api";

export default function EnclavePanel() {
  const [status, setStatus] = useState<any>(null);
  const [sealedItems, setSealedItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/enclave/status`);
      setStatus(await safeJson(res));
    } catch {}
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const sealKG = async () => {
    setLoading(true);
    try {
      // Fetch current knowledge graph and seal it
      const graphRes = await fetch(`${BASE}/api/entity/memory`);
      const graph = await graphRes.json();
      await fetch(`${BASE}/api/enclave/seal-knowledge-graph`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ graph }),
      });
      loadStatus();
    } catch {}
    setLoading(false);
  };

  const verifyIntegrity = async () => {
    try {
      const res = await fetch(`${BASE}/api/enclave/verify`);
      const data = await safeJson(res);
      setStatus((prev: any) => ({ ...prev, integrity_valid: data.integrity_valid }));
    } catch {}
  };

  return (
    <div style={{ background: "linear-gradient(135deg, #0d0f12 0%, #12151a 100%)", border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden", display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: status?.integrity_valid ? "#00FF66" : "#FF3333", boxShadow: `0 0 6px ${status?.integrity_valid ? "rgba(0,255,102,0.5)" : "rgba(255,51,51,0.4)"}` }} />
          <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)", letterSpacing: "0.08em" }}>SECURE_ENCLAVE</span>
        </div>
        <span style={{ fontSize: 7, padding: "1px 6px", borderRadius: 3, background: status?.hardware_backed ? "rgba(0,255,102,0.1)" : "rgba(255,179,0,0.1)", border: `1px solid ${status?.hardware_backed ? "rgba(0,255,102,0.2)" : "rgba(255,179,0,0.2)"}`, color: status?.hardware_backed ? "#00FF66" : "#FFB300", fontFamily: "var(--font-mono)" }}>
          {status?.hardware_backed ? "HARDWARE" : "SOFTWARE"}
        </span>
      </div>

      {/* Status grid */}
      {status && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
          {[
            { label: "ENCLAVE", value: status.enclave_type?.replace(/_/g, " ") || "unknown" },
            { label: "ITEMS", value: status.total_items || 0 },
            { label: "SEALED BYTES", value: status.total_sealed_bytes ? `${(status.total_sealed_bytes / 1024).toFixed(1)}KB` : "0" },
            { label: "ENCRYPTION", value: "AES-256-GCM" },
          ].map(item => (
            <div key={item.label} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-primary)", fontWeight: 600, textTransform: "capitalize" }}>{item.value}</div>
              <div style={{ fontSize: 6, fontFamily: "var(--font-mono)", color: "var(--text-muted)", letterSpacing: "0.08em" }}>{item.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Integrity status */}
      <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: status?.integrity_valid ? "#00FF66" : "#FF3333" }} />
          <span style={{ fontSize: 8, fontFamily: "var(--font-mono)", color: status?.integrity_valid ? "#00FF66" : "#FF3333" }}>
            INTEGRITY: {status?.integrity_valid ? "VERIFIED" : "COMPROMISED"}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div style={{ flex: 1, overflowY: "auto", minHeight: 0, padding: "8px 12px" }}>
        <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: 6, letterSpacing: "0.08em" }}>ENCLAVE OPERATIONS</div>
        {[
          { label: "Seal Knowledge Graph", action: sealKG, icon: "🧠" },
          { label: "Verify Integrity", action: verifyIntegrity, icon: "🔍" },
        ].map(btn => (
          <button key={btn.label} onClick={btn.action} disabled={loading} style={{
            width: "100%", textAlign: "left", padding: "6px 8px", marginBottom: 4, borderRadius: 3,
            background: "var(--surface)", border: "1px solid var(--border)", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 8, opacity: loading ? 0.5 : 1,
          }}>
            <span style={{ fontSize: 11 }}>{btn.icon}</span>
            <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>{btn.label}</span>
          </button>
        ))}
      </div>

      {/* Key derivation info */}
      <div style={{ padding: "6px 12px", borderTop: "1px solid var(--border)" }}>
        <div style={{ fontSize: 7, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
          KDF: PBKDF2-SHA256 · 600k iterations · vault: {status?.vault_path?.split(/[/\\]/).pop() || "~/.jarvis/vault"}
        </div>
      </div>
    </div>
  );
}
