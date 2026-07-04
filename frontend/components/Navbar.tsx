"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Command", icon: "⚡" },
  { href: "/dashboard", label: "Brain", icon: "🧠" },
  { href: "/life", label: "Life OS", icon: "🫀" },
  { href: "/trading", label: "Trading", icon: "📈" },
  { href: "/secretary", label: "Secretary", icon: "📋" },
  { href: "/agent", label: "Agent", icon: "🤖" },
  { href: "/reminders", label: "Reminders", icon: "⏰" },
  { href: "/marketplace", label: "Plugins", icon: "🧩" },
  { href: "/settings", label: "Config", icon: "⚙" },
];

interface NavbarProps {
  entityMood?: string;
  entityMoodEmoji?: string;
  entityThought?: string;
}

export default function Navbar({ entityMood, entityMoodEmoji, entityThought }: NavbarProps) {
  const pathname = usePathname();

  return (
    <nav className="glass-strong flex items-center justify-between px-4 sm:px-6 py-3 border-b border-purple-900/20 flex-shrink-0 z-20 relative">
      <Link href="/" className="flex items-center gap-2.5 shrink-0">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500/20 to-purple-500/20 border border-emerald-500/20 flex items-center justify-center shadow-[0_0_12px_rgba(52,211,153,0.15)]">
          <span className="text-sm">🌌</span>
        </div>
        <div className="hidden sm:block">
          <span className="text-xs font-mono font-bold text-[#34d399] tracking-[0.1em]">J.A.R.V.I.S</span>
          <span className="block text-[8px] font-mono text-white/20 tracking-[0.12em]">COGNITIVE ARCHITECTURE v3.0</span>
        </div>
      </Link>

      <div className="hidden lg:flex items-center gap-1">
        {NAV_ITEMS.map((n) => {
          const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[10px] font-mono tracking-wide transition-all nav-link ${
                active
                  ? "text-[#34d399] bg-[#34d399]/[0.08] border border-[#34d399]/15"
                  : "text-white/30 hover:text-white/50 border border-transparent"
              }`}
            >
              <span>{n.icon}</span>
              <span>{n.label}</span>
            </Link>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        {entityThought && (
          <span className="hidden md:block text-[9px] font-mono text-white/20 max-w-[140px] truncate">
            {entityThought.slice(0, 50)}
          </span>
        )}
        {entityMood && (
          <div className="flex items-center gap-1.5 px-2 py-1 rounded-full border border-white/[0.06] bg-white/[0.02]">
            <span className="text-[10px]">{entityMoodEmoji || "🔍"}</span>
            <span className="text-[9px] font-mono text-white/30 tracking-wide">{entityMood}</span>
          </div>
        )}

        <div className="lg:hidden dropdown relative">
          <button className="text-white/40 hover:text-white/60 p-1.5 rounded-md border border-white/[0.06] transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          <div className="dropdown-menu hidden absolute right-0 top-full mt-1 w-48 glass-strong rounded-xl border border-purple-900/20 py-1 z-50 shadow-xl shadow-black/30">
            {NAV_ITEMS.map((n) => {
              const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`flex items-center gap-2 px-3 py-2 text-xs font-mono transition-colors ${
                    active ? "text-[#34d399] bg-[#34d399]/[0.06]" : "text-white/40 hover:text-white/60 hover:bg-white/[0.03]"
                  }`}
                >
                  <span>{n.icon}</span>
                  <span>{n.label}</span>
                </Link>
              );
            })}
          </div>
        </div>

        <Link href="/settings" className="text-white/30 hover:text-white/50 p-1.5 rounded-md border border-white/[0.06] hover:border-purple-500/20 transition-all hidden sm:flex items-center justify-center">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </Link>
      </div>
    </nav>
  );
}
