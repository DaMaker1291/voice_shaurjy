"use client";

import Link from "next/link";

export default function NavBar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3 bg-gray-950/40 backdrop-blur-xl border-b border-gray-800/20" style={{ background: "rgba(3, 3, 15, 0.4)" }}>
      <Link href="/" className="flex items-center gap-2.5">
        <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse shadow-lg shadow-purple-500/30" />
        <span className="text-xs font-mono text-gray-500 tracking-[0.25em] uppercase">jason</span>
      </Link>
      <span className="text-[9px] font-mono text-gray-800 tracking-[0.15em] uppercase">neural interface v2</span>
    </nav>
  );
}
