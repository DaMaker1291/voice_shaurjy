"use client";

import { useState, useEffect } from "react";

interface CredentialModalProps {
  open: boolean;
  title: string;
  description: string;
  fields: { name: string; label: string; type?: string; placeholder?: string }[];
  onSubmit: (values: Record<string, string>) => void;
  onClose: () => void;
}

export default function CredentialModal({ open, title, description, fields, onSubmit, onClose }: CredentialModalProps) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setTimeout(() => setVisible(true), 10);
      const init: Record<string, string> = {};
      fields.forEach(f => { init[f.name] = ""; });
      setValues(init);
    } else {
      setVisible(false);
    }
  }, [open, fields]);

  const handleSubmit = async () => {
    setSubmitting(true);
    // Brief delay for UX
    await new Promise(r => setTimeout(r, 300));
    onSubmit(values);
    setSubmitting(false);
  };

  if (!open) return null;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 10000,
      display: "flex", alignItems: "center", justifyContent: "center",
      background: "rgba(2,8,8,0.92)", backdropFilter: "blur(8px)",
      opacity: visible ? 1 : 0, transition: "opacity 0.3s",
    }}>
      {/* Encrypted mesh background */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "linear-gradient(rgba(10,74,64,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(10,74,64,0.03) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      {/* Modal */}
      <div style={{
        width: 420, maxWidth: "90vw",
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 6, padding: 0, position: "relative",
        transform: visible ? "translateY(0) scale(1)" : "translateY(20px) scale(0.95)",
        transition: "transform 0.3s cubic-bezier(0.16,1,0.3,1)",
        boxShadow: "0 0 60px rgba(10,74,64,0.15), 0 0 120px rgba(10,74,64,0.05)",
      }}>
        {/* Header */}
        <div style={{ padding: "20px 24px 16px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: "var(--neon-green)", boxShadow: "0 0 8px rgba(0,255,102,0.4)",
            }} />
            <span style={{ fontSize: 11, color: "var(--neon-green)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", fontWeight: 600 }}>
              ENCRYPTED CHANNEL
            </span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--font-mono)", marginBottom: 4 }}>
            {title}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6 }}>
            {description}
          </div>
        </div>

        {/* Fields */}
        <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 12 }}>
          {fields.map(field => (
            <div key={field.name}>
              <label style={{
                fontSize: 9, color: "var(--text-muted)", fontFamily: "var(--font-mono)",
                letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: 4,
              }}>{field.label}</label>
              <input
                type={field.type || "password"}
                value={values[field.name] || ""}
                onChange={e => setValues(p => ({ ...p, [field.name]: e.target.value }))}
                onKeyDown={e => { if (e.key === "Enter") handleSubmit(); }}
                placeholder={field.placeholder || "••••••••"}
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: 4, fontSize: 12,
                  fontFamily: "var(--font-mono)", background: "var(--surface-raised)",
                  border: "1px solid var(--border)", color: "var(--text-primary)", outline: "none",
                  transition: "border-color 0.15s",
                }}
                onFocus={e => { e.target.style.borderColor = "rgba(0,255,102,0.3)"; }}
                onBlur={e => { e.target.style.borderColor = "var(--border)"; }}
              />
            </div>
          ))}
        </div>

        {/* Privacy notice */}
        <div style={{ padding: "0 24px 16px" }}>
          <div style={{
            padding: "8px 10px", borderRadius: 4, background: "var(--surface-raised)",
            border: "1px solid var(--border)", fontSize: 9, color: "var(--text-muted)",
            lineHeight: 1.5, fontFamily: "var(--font-mono)",
          }}>
            <span style={{ color: "var(--neon-green)" }}>🔒 </span>
            Credentials are encrypted end-to-end and stored locally on your machine only. They are never sent to our servers.
          </div>
        </div>

        {/* Actions */}
        <div style={{ padding: "12px 24px 20px", display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{
            padding: "7px 16px", borderRadius: 4, fontSize: 10, fontWeight: 600,
            fontFamily: "var(--font-mono)", cursor: "pointer", letterSpacing: "0.05em",
            background: "transparent", color: "var(--text-muted)", border: "1px solid var(--border)",
            transition: "all 0.15s",
          }}>CANCEL</button>
          <button onClick={handleSubmit} disabled={submitting || fields.some(f => !values[f.name])} style={{
            padding: "7px 20px", borderRadius: 4, fontSize: 10, fontWeight: 600,
            fontFamily: "var(--font-mono)", cursor: "pointer", letterSpacing: "0.05em",
            background: submitting || fields.some(f => !values[f.name]) ? "var(--surface-raised)" : "var(--neon-green)",
            color: submitting || fields.some(f => !values[f.name]) ? "var(--text-muted)" : "#000",
            border: "none", transition: "all 0.15s",
          }}>
            {submitting ? "ENCRYPTING..." : "CONNECT"}
          </button>
        </div>

        {/* Corner brackets */}
        <div style={{ position: "absolute", top: 8, left: 8, width: 12, height: 12, borderLeft: "1px solid rgba(0,255,102,0.2)", borderTop: "1px solid rgba(0,255,102,0.2)" }} />
        <div style={{ position: "absolute", top: 8, right: 8, width: 12, height: 12, borderRight: "1px solid rgba(0,255,102,0.2)", borderTop: "1px solid rgba(0,255,102,0.2)" }} />
        <div style={{ position: "absolute", bottom: 8, left: 8, width: 12, height: 12, borderLeft: "1px solid rgba(0,255,102,0.2)", borderBottom: "1px solid rgba(0,255,102,0.2)" }} />
        <div style={{ position: "absolute", bottom: 8, right: 8, width: 12, height: 12, borderRight: "1px solid rgba(0,255,102,0.2)", borderBottom: "1px solid rgba(0,255,102,0.2)" }} />
      </div>
    </div>
  );
}
