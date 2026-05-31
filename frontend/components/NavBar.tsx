"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function NavBar() {
  const path = usePathname();
  const links = [
    { href: "/", label: "Chat" },
    { href: "/dashboard", label: "Brain" },
    { href: "/reminders", label: "Reminders" },
    { href: "/settings", label: "Settings" },
  ];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3 bg-gray-950/80 backdrop-blur-xl border-b border-gray-800/50">
      <Link href="/" className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
        <span className="text-sm font-mono text-gray-400 tracking-wide">second_brain</span>
      </Link>
      <div className="flex items-center gap-6">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`text-xs font-mono tracking-wider uppercase transition-colors ${
              path === l.href ? "text-purple-400" : "text-gray-600 hover:text-gray-300"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
