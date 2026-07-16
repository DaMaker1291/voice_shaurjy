'use client';

import React, { useState, useEffect } from 'react';

type Platform = 'windows' | 'mac' | 'linux' | 'unknown';

function detectPlatform(): Platform {
  if (typeof window === 'undefined') return 'unknown';
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes('win')) return 'windows';
  if (ua.includes('mac')) return 'mac';
  if (ua.includes('linux')) return 'linux';
  return 'unknown';
}

const PLATFORM_INFO: Record<Platform, { icon: string; label: string; ext: string; installNote: string }> = {
  windows: { icon: '⊞', label: 'Windows', ext: '.exe', installNote: 'Run the installer → Click Next → Done' },
  mac: { icon: '⌘', label: 'macOS', ext: '.dmg', installNote: 'Open .dmg → Drag to Applications → Done' },
  linux: { icon: '⏣', label: 'Linux', ext: '.AppImage', installNote: 'chmod +x → Run → Done' },
  unknown: { icon: '⬡', label: 'Your OS', ext: '', installNote: '' },
};

const ALL_PLATFORMS: Platform[] = ['windows', 'mac', 'linux'];

export default function DownloadPage() {
  const [platform, setPlatform] = useState<Platform>('unknown');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setPlatform(detectPlatform());
  }, []);

  const info = PLATFORM_INFO[platform];
  const altPlatforms = ALL_PLATFORMS.filter(p => p !== platform);

  const downloadUrl = platform === 'windows'
    ? 'https://github.com/DaMaker1291/voice_shaurjy/releases/latest/download/JARVIS_Setup_v3.0.0.exe'
    : platform === 'mac'
    ? 'https://github.com/DaMaker1291/voice_shaurjy/releases/latest/download/JARVIS-3.0.0.dmg'
    : platform === 'linux'
    ? 'https://github.com/DaMaker1291/voice_shaurjy/releases/latest/download/JARVIS-3.0.0.AppImage'
    : '';

  const psCommand = 'irm https://dgfhgjhj-jarvis-ai-brain.hf.space/install.ps1 | iex';

  const copyCommand = () => {
    navigator.clipboard.writeText(psCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#000',
      color: '#fff',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Nav */}
      <nav style={{
        padding: '16px 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #1a1a1a',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(0,255,102,0.15) 0%, transparent 70%)',
            border: '1px solid rgba(0,255,102,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#00ff66', boxShadow: '0 0 12px rgba(0,255,102,0.5)' }} />
          </div>
          <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: '0.05em', color: '#fff' }}>JARVIS</span>
        </div>
        <div style={{ display: 'flex', gap: 24, fontSize: 13, color: '#888' }}>
          <a href="/" style={{ color: '#888', textDecoration: 'none' }}>Home</a>
          <a href="/capabilities" style={{ color: '#888', textDecoration: 'none' }}>Features</a>
          <a href="/enterprise" style={{ color: '#888', textDecoration: 'none' }}>Enterprise</a>
        </div>
      </nav>

      {/* Hero */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 24px 60px',
        textAlign: 'center',
      }}>
        {/* Orb */}
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,255,102,0.1) 0%, transparent 70%)',
          border: '1px solid rgba(0,255,102,0.15)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 32,
          animation: 'float 3s ease-in-out infinite',
        }}>
          <div style={{
            width: 16, height: 16, borderRadius: '50%',
            background: '#00ff66',
            boxShadow: '0 0 30px rgba(0,255,102,0.4)',
            animation: 'glow 2s ease-in-out infinite',
          }} />
        </div>

        <h1 style={{
          fontSize: 48, fontWeight: 700, letterSpacing: '-0.02em',
          lineHeight: 1.1, marginBottom: 16,
          background: 'linear-gradient(135deg, #fff 0%, #888 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          Download JARVIS
        </h1>

        <p style={{
          fontSize: 17, color: '#888', maxWidth: 500, lineHeight: 1.6,
          marginBottom: 48,
        }}>
          Your sovereign AI brain. Runs natively on your machine.
          Controls your devices, automates your tasks, owns its intelligence.
        </p>

        {/* Primary Download Button */}
        {platform !== 'unknown' && downloadUrl && (
          <div style={{ marginBottom: 48 }}>
            <a
              href={downloadUrl}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 12,
                padding: '16px 40px',
                background: '#00ff66',
                color: '#000',
                borderRadius: 12,
                fontSize: 16,
                fontWeight: 600,
                textDecoration: 'none',
                transition: 'all 0.2s',
                boxShadow: '0 4px 24px rgba(0,255,102,0.25)',
              }}
              onMouseEnter={e => {
                (e.target as HTMLElement).style.transform = 'translateY(-2px)';
                (e.target as HTMLElement).style.boxShadow = '0 8px 32px rgba(0,255,102,0.35)';
              }}
              onMouseLeave={e => {
                (e.target as HTMLElement).style.transform = 'translateY(0)';
                (e.target as HTMLElement).style.boxShadow = '0 4px 24px rgba(0,255,102,0.25)';
              }}
            >
              <span style={{ fontSize: 20 }}>{info.icon}</span>
              Download for {info.label}
              <span style={{ fontSize: 13, opacity: 0.7 }}>({info.ext})</span>
            </a>

            <div style={{
              marginTop: 16, fontSize: 13, color: '#666',
            }}>
              {info.installNote}
            </div>
          </div>
        )}

        {/* Version info */}
        <div style={{
          display: 'flex', gap: 32, marginBottom: 48,
          fontSize: 12, color: '#555',
        }}>
          <span>v3.0.0</span>
          <span>•</span>
          <span>MIT License</span>
          <span>•</span>
          <span>32 MB</span>
        </div>

        {/* PowerShell one-liner */}
        <div style={{
          background: '#0a0a0a',
          border: '1px solid #1a1a1a',
          borderRadius: 12,
          padding: '20px 24px',
          maxWidth: 600,
          width: '100%',
          marginBottom: 64,
        }}>
          <div style={{ fontSize: 11, color: '#555', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Or install via PowerShell (Windows)
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: '#111',
            borderRadius: 8,
            padding: '12px 16px',
          }}>
            <code style={{
              fontSize: 13, color: '#00ff66',
              fontFamily: '"SF Mono", "Fira Code", Consolas, monospace',
              flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {psCommand}
            </code>
            <button
              onClick={copyCommand}
              style={{
                padding: '6px 14px',
                background: copied ? '#00ff66' : 'rgba(0,255,102,0.1)',
                color: copied ? '#000' : '#00ff66',
                border: '1px solid rgba(0,255,102,0.2)',
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'inherit',
                transition: 'all 0.2s',
                flexShrink: 0,
                marginLeft: 12,
              }}
            >
              {copied ? '✓ Copied' : 'Copy'}
            </button>
          </div>
        </div>

        {/* Other platforms */}
        {altPlatforms.length > 0 && (
          <div>
            <div style={{ fontSize: 12, color: '#555', marginBottom: 12 }}>Other platforms</div>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              {altPlatforms.map(p => {
                const altInfo = PLATFORM_INFO[p];
                const altUrl = p === 'windows'
                  ? 'https://github.com/DaMaker1291/voice_shaurjy/releases/latest/download/JARVIS_Setup_v3.0.0.exe'
                  : p === 'mac'
                  ? 'https://github.com/DaMaker1291/voice_shaurjy/releases/latest/download/JARVIS-3.0.0.dmg'
                  : 'https://github.com/DaMaker1291/voice_shaurjy/releases/latest/download/JARVIS-3.0.0.AppImage';
                return (
                  <a
                    key={p}
                    href={altUrl}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '10px 20px',
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid #222',
                      borderRadius: 8,
                      color: '#aaa',
                      fontSize: 13,
                      textDecoration: 'none',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => {
                      (e.target as HTMLElement).style.borderColor = '#333';
                      (e.target as HTMLElement).style.color = '#fff';
                    }}
                    onMouseLeave={e => {
                      (e.target as HTMLElement).style.borderColor = '#222';
                      (e.target as HTMLElement).style.color = '#aaa';
                    }}
                  >
                    <span>{altInfo.icon}</span>
                    {altInfo.label}
                    <span style={{ fontSize: 11, color: '#555' }}>{altInfo.ext}</span>
                  </a>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* What's included */}
      <div style={{
        borderTop: '1px solid #1a1a1a',
        padding: '64px 24px',
      }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <h2 style={{
            fontSize: 24, fontWeight: 600, textAlign: 'center',
            marginBottom: 48, color: '#fff',
          }}>
            What&apos;s included
          </h2>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: 24,
          }}>
            {[
              { icon: '⬡', title: 'Native Desktop App', desc: 'Custom frameless window, system tray, global hotkeys (Ctrl+Shift+J), auto-launch on boot' },
              { icon: '🧠', title: 'Full AI Brain', desc: '345+ routes, RAG engine, 50+ agent actions, voice control, autonomous task execution' },
              { icon: '📡', title: 'Device Control', desc: 'Discovers and controls all devices on your network — smart plugs, lights, printers, phones' },
              { icon: '🖥️', title: 'Headless Workstation', desc: 'Runs apps in isolated virtual displays without hijacking your mouse or keyboard' },
              { icon: '🛡️', title: 'Enterprise Security', desc: 'OAuth2/OIDC identity, deterministic guardrails, hash-chained compliance ledger, MCP routing' },
              { icon: '🔌', title: 'MCP Protocol', desc: 'Connects to any MCP server — filesystem, GitHub, Postgres, Docker, Kubernetes, and more' },
            ].map((item, i) => (
              <div key={i} style={{
                padding: 24,
                background: '#0a0a0a',
                border: '1px solid #1a1a1a',
                borderRadius: 12,
              }}>
                <div style={{ fontSize: 24, marginBottom: 12 }}>{item.icon}</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: '#fff' }}>{item.title}</div>
                <div style={{ fontSize: 12, color: '#666', lineHeight: 1.6 }}>{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{
        borderTop: '1px solid #1a1a1a',
        padding: '24px 32px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: 12,
        color: '#444',
      }}>
        <span>© 2026 JARVIS AI — MIT License</span>
        <div style={{ display: 'flex', gap: 20 }}>
          <a href="https://github.com/DaMaker1291/voice_shaurjy" style={{ color: '#444', textDecoration: 'none' }}>GitHub</a>
          <a href="https://dgfhgjhj-jarvis-ai-brain.hf.space" style={{ color: '#444', textDecoration: 'none' }}>Web App</a>
        </div>
      </div>

      <style jsx global>{`
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes glow {
          0%, 100% { box-shadow: 0 0 30px rgba(0,255,102,0.4); }
          50% { box-shadow: 0 0 50px rgba(0,255,102,0.6); }
        }
      `}</style>
    </div>
  );
}
