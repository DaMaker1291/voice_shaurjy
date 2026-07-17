'use client';

import React, { useState, useEffect } from 'react';

type OS = 'windows' | 'mac' | 'linux' | 'unknown';

function detectOS(): OS {
  if (typeof window === 'undefined') return 'unknown';
  const ua = navigator.userAgent || '';
  const plat = navigator.platform || '';
  if (/win/i.test(ua) || /win/i.test(plat)) return 'windows';
  if (/mac/i.test(ua) || /mac/i.test(plat)) return 'mac';
  if (/linux/i.test(ua) || /linux/i.test(plat)) return 'linux';
  return 'unknown';
}

const OS_DATA: Record<OS, { icon: string; label: string; ext: string; file: string }> = {
  windows: { icon: '⊞', label: 'Windows', ext: '.zip', file: 'JARVIS-Windows.zip' },
  mac:     { icon: '⌘', label: 'macOS',   ext: '.dmg', file: 'JARVIS-4.0.0-arm64.dmg' },
  linux:   { icon: '⏣', label: 'Linux',   ext: '.AppImage', file: 'JARVIS-4.0.0.AppImage' },
  unknown: { icon: '⬡', label: 'Your OS', ext: '', file: '' },
};

const REPO = 'https://github.com/DaMaker1291/voice_shaurjy';

function dlUrl(os: OS): string {
  if (os === 'windows') return 'https://dgfhgjhj-jarvis-ai-brain.hf.space/api/download/windows';
  const f = OS_DATA[os].file;
  return f ? `${REPO}/releases/latest/download/${f}` : '#';
}

const installCmds: Record<OS, { label: string; cmd: string }[]> = {
  windows: [
    { label: 'PowerShell (one-liner)', cmd: 'irm https://dgfhgjhj-jarvis-ai-brain.hf.space/install.ps1 | iex' },
    { label: 'Build from source', cmd: `git clone ${REPO}.git && cd "voice_shaurjy/desktop" && build-windows.bat` },
  ],
  mac: [
    { label: 'Terminal (one-liner)', cmd: `curl -fsSL https://dgfhgjhj-jarvis-ai-brain.hf.space/install.ps1 | python3` },
    { label: 'Build from source', cmd: `git clone ${REPO}.git && cd "voice_shaurjy/desktop" && npm install && npm run build:mac` },
  ],
  linux: [
    { label: 'Terminal (one-liner)', cmd: `curl -fsSL https://dgfhgjhj-jarvis-ai-brain.hf.space/install.ps1 | python3` },
    { label: 'Build from source', cmd: `git clone ${REPO}.git && cd "voice_shaurjy/desktop" && npm install && npm run build:linux` },
  ],
  unknown: [
    { label: 'Build from source', cmd: `git clone ${REPO}.git && cd "voice_shaurjy/desktop" && npm install && npm start` },
  ],
};

export default function DownloadPage() {
  const [os, setOs] = useState<OS>('unknown');
  const [copied, setCopied] = useState('');

  useEffect(() => {
    const detected = detectOS();
    setOs(detected);
    // Allow scrolling on this page
    document.body.classList.add('allow-scroll');
    return () => document.body.classList.remove('allow-scroll');
  }, []);

  const copy = (text: string, id: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(id);
    setTimeout(() => setCopied(''), 2000);
  };

  const info = OS_DATA[os];
  const cmds = installCmds[os];

  return (
    <div style={{
      minHeight: '100vh', background: '#000', color: '#fff',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* keyframes injected via useEffect */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes jarvis-float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
        @keyframes jarvis-glow { 0%,100%{box-shadow:0 0 30px rgba(0,255,102,0.4)} 50%{box-shadow:0 0 50px rgba(0,255,102,0.6)} }
      `}} />

      {/* Nav */}
      <nav style={{ padding: '16px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #1a1a1a' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,255,102,0.15) 0%, transparent 70%)', border: '1px solid rgba(0,255,102,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#00ff66', boxShadow: '0 0 12px rgba(0,255,102,0.5)' }} />
          </div>
          <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: '0.05em' }}>JARVIS</span>
        </div>
        <div style={{ display: 'flex', gap: 24, fontSize: 13, color: '#888' }}>
          <a href="/voice_shaurjy/" style={{ color: '#888', textDecoration: 'none' }}>Home</a>
          <a href="/voice_shaurjy/capabilities" style={{ color: '#888', textDecoration: 'none' }}>Features</a>
          <a href="/voice_shaurjy/enterprise" style={{ color: '#888', textDecoration: 'none' }}>Enterprise</a>
        </div>
      </nav>

      {/* Hero */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 24px 60px', textAlign: 'center' }}>
        {/* Orb */}
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,255,102,0.1) 0%, transparent 70%)',
          border: '1px solid rgba(0,255,102,0.15)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 32, animation: 'jarvis-float 3s ease-in-out infinite',
        }}>
          <div style={{
            width: 16, height: 16, borderRadius: '50%',
            background: '#00ff66',
            boxShadow: '0 0 30px rgba(0,255,102,0.4)',
            animation: 'jarvis-glow 2s ease-in-out infinite',
          }} />
        </div>

        <h1 style={{
          fontSize: 48, fontWeight: 700, letterSpacing: '-0.02em',
          lineHeight: 1.1, marginBottom: 16,
          background: 'linear-gradient(135deg, #fff 0%, #888 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          Download JARVIS
        </h1>

        <p style={{ fontSize: 17, color: '#888', maxWidth: 500, lineHeight: 1.6, marginBottom: 48 }}>
          Your sovereign AI brain. Runs natively on your machine.
          Controls your devices, automates your tasks, owns its intelligence.
        </p>

        {/* ── Primary Download Button ── */}
        {os !== 'unknown' && info.file && (
          <div style={{ marginBottom: 24 }}>
            <a
              href={dlUrl(os)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 12,
                padding: '18px 48px', background: '#00ff66', color: '#000',
                borderRadius: 12, fontSize: 17, fontWeight: 700, textDecoration: 'none',
                boxShadow: '0 4px 24px rgba(0,255,102,0.25)',
                transition: 'transform 0.2s, box-shadow 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.transform = 'translateY(-2px) scale(1.02)';
                e.currentTarget.style.boxShadow = '0 8px 40px rgba(0,255,102,0.4)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.transform = 'none';
                e.currentTarget.style.boxShadow = '0 4px 24px rgba(0,255,102,0.25)';
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              Download for {info.label}
              <span style={{ fontSize: 13, opacity: 0.6, fontWeight: 400 }}>{info.ext}</span>
            </a>
            <div style={{ marginTop: 12, fontSize: 12, color: '#555' }}>
              v4.0.0 — MIT License — ~32 MB
            </div>
          </div>
        )}

        {/* ── All Platform Buttons (always show) ── */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 48, flexWrap: 'wrap', justifyContent: 'center' }}>
          {(['windows', 'mac', 'linux'] as OS[]).map(p => {
            const pi = OS_DATA[p];
            const isCurrent = p === os;
            return (
              <a key={p} href={dlUrl(p)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '10px 20px',
                  background: isCurrent ? 'rgba(0,255,102,0.08)' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${isCurrent ? 'rgba(0,255,102,0.25)' : '#222'}`,
                  borderRadius: 8,
                  color: isCurrent ? '#00ff66' : '#999',
                  fontSize: 13, textDecoration: 'none',
                  transition: 'all 0.15s',
                }}
              >
                {pi.icon} {pi.label}
                <span style={{ fontSize: 11, opacity: 0.5 }}>{pi.ext}</span>
                {isCurrent && <span style={{ fontSize: 9, color: '#00ff66', opacity: 0.6 }}>detected</span>}
              </a>
            );
          })}
        </div>

        {/* ── Divider ── */}
        <div style={{ width: 60, height: 1, background: '#222', marginBottom: 48 }} />

        {/* ── Install Commands ── */}
        <div style={{ maxWidth: 640, width: '100%' }}>
          <div style={{ fontSize: 13, color: '#666', marginBottom: 20, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Install commands
          </div>

          {cmds.map((c, i) => (
            <div key={i} style={{
              background: '#0a0a0a', border: '1px solid #1a1a1a',
              borderRadius: 10, padding: '16px 20px', marginBottom: 10,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: '#888', fontWeight: 500 }}>
                  <span style={{ color: info.icon === '⬡' ? '#888' : '#00ccff' }}>{info.icon}</span> {c.label}
                </span>
                <button onClick={() => copy(c.cmd, c.label)}
                  style={{
                    padding: '4px 12px',
                    background: copied === c.label ? '#00ff66' : 'rgba(0,255,102,0.08)',
                    color: copied === c.label ? '#000' : '#00ff66',
                    border: '1px solid rgba(0,255,102,0.15)',
                    borderRadius: 5, fontSize: 10, fontWeight: 600,
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}>
                  {copied === c.label ? '✓ Copied' : 'Copy'}
                </button>
              </div>
              <code style={{
                display: 'block', fontSize: 12, color: '#00ff66',
                fontFamily: '"SF Mono", "Fira Code", Consolas, monospace',
                background: '#111', padding: '8px 12px', borderRadius: 6,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {c.cmd}
              </code>
            </div>
          ))}

          {/* Web App */}
          <div style={{
            background: '#0a0a0a', border: '1px solid #1a1a1a',
            borderRadius: 10, padding: '16px 20px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 12, color: '#888', fontWeight: 500 }}>
                <span style={{ color: '#a78bfa' }}>🌐</span> Use in browser (no install)
              </span>
              <a href="https://dgfhgjhj-jarvis-ai-brain.hf.space"
                style={{
                  padding: '4px 12px',
                  background: 'rgba(167,139,250,0.1)',
                  color: '#a78bfa',
                  border: '1px solid rgba(167,139,250,0.2)',
                  borderRadius: 5, fontSize: 10, fontWeight: 600, textDecoration: 'none',
                }}>
                Open →
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* ── Features ── */}
      <div style={{ borderTop: '1px solid #111', padding: '64px 24px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <h2 style={{ fontSize: 22, fontWeight: 600, textAlign: 'center', marginBottom: 40 }}>
            What&apos;s included
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 16 }}>
            {[
              { icon: '⬡', title: 'Native Desktop App', desc: 'Custom window, system tray, global hotkeys, auto-launch' },
              { icon: '🧠', title: 'Full AI Brain', desc: '345+ routes, RAG engine, 50+ agent actions, voice control' },
              { icon: '📡', title: 'Device Control', desc: 'Discovers and controls all devices on your network' },
              { icon: '🖥️', title: 'Headless Workstation', desc: 'Runs apps in isolated virtual displays' },
              { icon: '🛡️', title: 'Enterprise Security', desc: 'OAuth2, guardrails, compliance ledger, MCP routing' },
              { icon: '🔌', title: 'MCP Protocol', desc: 'Connects to filesystem, GitHub, Postgres, Docker, and more' },
            ].map((item, i) => (
              <div key={i} style={{ padding: 20, background: '#080808', border: '1px solid #151515', borderRadius: 10 }}>
                <div style={{ fontSize: 20, marginBottom: 10 }}>{item.icon}</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, color: '#eee' }}>{item.title}</div>
                <div style={{ fontSize: 11, color: '#666', lineHeight: 1.5 }}>{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{ borderTop: '1px solid #111', padding: '20px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#333' }}>
        <span>© 2026 JARVIS AI — MIT License</span>
        <div style={{ display: 'flex', gap: 20 }}>
          <a href={REPO} style={{ color: '#333', textDecoration: 'none' }}>GitHub</a>
          <a href="https://dgfhgjhj-jarvis-ai-brain.hf.space" style={{ color: '#333', textDecoration: 'none' }}>Web App</a>
        </div>
      </div>
    </div>
  );
}
