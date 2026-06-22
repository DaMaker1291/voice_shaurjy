import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Second Brain - Sassy Voice Assistant",
  description: "Your sassy, voice-first second brain. Talk to your notes.",
};

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/agent", label: "Agent" },
  { href: "/settings", label: "Settings" },
  { href: "/reminders", label: "Reminders" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950">
        <nav className="fixed top-0 left-0 right-0 z-[100] px-4 py-2">
          <div className="max-w-5xl mx-auto flex items-center justify-between">
            <Link href="/" className="text-sm font-bold text-purple-400/70 hover:text-purple-400 tracking-wider transition-colors">Second Brain</Link>
            <div className="flex items-center gap-4">
              {navLinks.map((l) => (
                <Link key={l.href} href={l.href} className="text-xs text-gray-600 hover:text-purple-400 transition-colors tracking-wider">{l.label}</Link>
              ))}
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
