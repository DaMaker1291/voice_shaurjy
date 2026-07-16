"use client";

import { useState } from "react";

type Mode = "login" | "signup";

export default function AuthPage({ onAuth }: { onAuth: (user: { name: string; email: string }) => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState<"form" | "verify">("form");
  const [code, setCode] = useState("");
  const [visible, setVisible] = useState(true);

  const handleSubmit = async () => {
    setError("");
    if (!email || !password) { setError("All fields required"); return; }
    if (mode === "signup" && password !== confirm) { setError("Passwords don't match"); return; }
    if (password.length < 8) { setError("Password must be 8+ characters"); return; }

    setLoading(true);
    // Simulate auth
    await new Promise(r => setTimeout(r, 1200));
    setLoading(false);

    if (mode === "signup") {
      setStep("verify");
      return;
    }

    // Login — store session and redirect
    const user = { name: name || email.split("@")[0], email };
    localStorage.setItem("jarvis-user", JSON.stringify(user));
    setVisible(false);
    setTimeout(() => onAuth(user), 300);
  };

  const handleVerify = async () => {
    if (code.length !== 6) { setError("Enter 6-digit code"); return; }
    setLoading(true);
    await new Promise(r => setTimeout(r, 800));
    setLoading(false);
    const user = { name: name || email.split("@")[0], email };
    localStorage.setItem("jarvis-user", JSON.stringify(user));
    setVisible(false);
    setTimeout(() => onAuth(user), 300);
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 10000,
      background: "#030303", display: "flex", alignItems: "center", justifyContent: "center",
      opacity: visible ? 1 : 0, transition: "opacity 0.4s",
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      {/* Background grid */}
      <div className="auth-grid" style={{
        position: "absolute", inset: 0, pointerEvents: "none", opacity: 0.4,
        backgroundImage: "linear-gradient(rgba(0,255,102,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,102,0.03) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      {/* Ambient glow */}
      <div style={{
        position: "absolute", top: "30%", left: "50%", transform: "translate(-50%, -50%)",
        width: 400, height: 400, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(0,255,102,0.06) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      <style jsx>{`
        @keyframes auth-in { from { opacity:0; transform:translateY(16px) scale(0.97); } to { opacity:1; transform:translateY(0) scale(1); } }
        .auth-card { animation: auth-in 0.5s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      <div className="auth-card modal-container" style={{
        width: 400, background: "#0d0f12", border: "1px solid #1a1d23",
        borderRadius: 12, padding: 32, position: "relative", zIndex: 1,
        boxShadow: "0 0 60px rgba(0,255,102,0.05), 0 20px 60px rgba(0,0,0,0.5)",
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#00FF66", boxShadow: "0 0 12px rgba(0,255,102,0.5)" }} />
            <span style={{ fontSize: 18, fontWeight: 700, color: "#e5e5e5", letterSpacing: "0.12em" }}>JARVIS</span>
          </div>
          <div style={{ fontSize: 10, color: "#667085", letterSpacing: "0.08em" }}>
            {mode === "login" ? "SOVEREIGN AI BRAIN" : "CREATE YOUR IDENTITY"}
          </div>
        </div>

        {step === "form" ? (
          <>
            {/* Mode Toggle */}
            <div style={{ display: "flex", background: "#030303", borderRadius: 6, padding: 3, marginBottom: 20, border: "1px solid #1a1d23" }}>
              {(["login", "signup"] as Mode[]).map(m => (
                <button key={m} onClick={() => { setMode(m); setError(""); }} style={{
                  flex: 1, padding: "8px 0", borderRadius: 4, fontSize: 10, fontWeight: 600,
                  fontFamily: "inherit", cursor: "pointer", letterSpacing: "0.08em", transition: "all 0.15s",
                  background: mode === m ? "rgba(0,255,102,0.12)" : "transparent",
                  color: mode === m ? "#00FF66" : "#667085",
                  border: "none",
                }}>
                  {m === "login" ? "SIGN IN" : "SIGN UP"}
                </button>
              ))}
            </div>

            {/* Fields */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {mode === "signup" && (
                <Field label="Name" value={name} onChange={setName} placeholder="Your name" />
              )}
              <Field label="Email" value={email} onChange={setEmail} placeholder="you@example.com" type="email" />
              <Field label="Password" value={password} onChange={setPassword} placeholder="8+ characters" type="password" />
              {mode === "signup" && (
                <Field label="Confirm Password" value={confirm} onChange={setConfirm} placeholder="Re-enter password" type="password" />
              )}
            </div>

            {error && (
              <div style={{ marginTop: 12, padding: "8px 12px", borderRadius: 4, background: "rgba(255,51,51,0.08)", border: "1px solid rgba(255,51,51,0.15)", fontSize: 10, color: "#FF3333" }}>
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={loading}
              style={{
                width: "100%", padding: "12px 0", borderRadius: 6, marginTop: 20,
                fontSize: 11, fontWeight: 600, fontFamily: "inherit", cursor: "pointer",
                background: loading ? "#1a1d23" : "#00FF66", color: loading ? "#667085" : "#030303",
                border: "none", letterSpacing: "0.08em", transition: "all 0.2s",
              }}
            >
              {loading ? (mode === "login" ? "AUTHENTICATING..." : "CREATING...") : (mode === "login" ? "SIGN IN" : "CREATE ACCOUNT")}
            </button>

            {/* Divider */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 20 }}>
              <div style={{ flex: 1, height: 1, background: "#1a1d23" }} />
              <span style={{ fontSize: 8, color: "#667085" }}>OR</span>
              <div style={{ flex: 1, height: 1, background: "#1a1d23" }} />
            </div>

            {/* Quick start */}
            <button
              onClick={() => {
                const user = { name: "Agent", email: "agent@jarvis.local" };
                localStorage.setItem("jarvis-user", JSON.stringify(user));
                setVisible(false);
                setTimeout(() => onAuth(user), 300);
              }}
              style={{
                width: "100%", padding: "10px 0", borderRadius: 6, marginTop: 16,
                fontSize: 10, fontFamily: "inherit", cursor: "pointer",
                background: "transparent", color: "#667085",
                border: "1px solid #1a1d23", transition: "all 0.15s",
              }}
            >
              CONTINUE AS GUEST →
            </button>

            <div style={{ textAlign: "center", marginTop: 16, fontSize: 9, color: "#667085" }}>
              <span style={{ opacity: 0.5 }}>Secured with AES-256-GCM encryption</span>
            </div>
          </>
        ) : (
          /* Email Verification Step */
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 32, marginBottom: 16 }}>📧</div>
            <div style={{ fontSize: 13, color: "#e5e5e5", marginBottom: 8 }}>Check your email</div>
            <div style={{ fontSize: 10, color: "#667085", marginBottom: 20, lineHeight: 1.5 }}>
              We sent a 6-digit verification code to<br />
              <span style={{ color: "#00FF66" }}>{email}</span>
            </div>
            <input
              value={code}
              onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              style={{
                width: 180, padding: "12px 0", borderRadius: 6, textAlign: "center",
                background: "#030303", border: "1px solid #1a1d23", fontSize: 24,
                color: "#e5e5e5", letterSpacing: "0.3em", fontFamily: "inherit", outline: "none",
              }}
            />
            {error && (
              <div style={{ marginTop: 12, fontSize: 10, color: "#FF3333" }}>{error}</div>
            )}
            <button
              onClick={handleVerify}
              disabled={loading || code.length !== 6}
              style={{
                width: "100%", padding: "12px 0", borderRadius: 6, marginTop: 16,
                fontSize: 11, fontWeight: 600, fontFamily: "inherit", cursor: "pointer",
                background: code.length === 6 ? "#00FF66" : "#1a1d23",
                color: code.length === 6 ? "#030303" : "#667085",
                border: "none", letterSpacing: "0.08em", transition: "all 0.2s",
              }}
            >
              {loading ? "VERIFYING..." : "VERIFY & ENTER"}
            </button>
            <button
              onClick={() => setStep("form")}
              style={{
                background: "none", border: "none", color: "#667085", fontSize: 9,
                fontFamily: "inherit", cursor: "pointer", marginTop: 12,
              }}
            >
              ← Back to sign up
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, type = "text" }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div>
      <div style={{ fontSize: 9, color: focused ? "#00FF66" : "#667085", marginBottom: 4, letterSpacing: "0.08em", transition: "color 0.15s" }}>
        {label.toUpperCase()}
      </div>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        type={type}
        style={{
          width: "100%", padding: "10px 12px", borderRadius: 6, fontSize: 12,
          background: "#030303", color: "#e5e5e5", fontFamily: "inherit",
          border: `1px solid ${focused ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
          outline: "none", transition: "border-color 0.15s",
        }}
      />
    </div>
  );
}
