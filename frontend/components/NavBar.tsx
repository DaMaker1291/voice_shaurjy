"use client";

import Link from "next/link";

export default function NavBar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3 bg-gray-950/80 backdrop-blur-xl border-b border-gray-800/50">
      <Link href="/" className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
        <span className="text-sm font-mono text-gray-400 tracking-wide">jason</span>
      </Link>
      <div className="flex items-center gap-3">
        <span className="text-[10px] font-mono text-gray-700 tracking-wider uppercase">always learning</span>
      </div>
    </nav>
  );
}
