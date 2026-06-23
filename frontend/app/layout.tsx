import type { Metadata } from "next";
import Link from "next/link";
import ClientLayout from "@/components/ClientLayout";
import "./globals.css";

export const metadata: Metadata = {
  title: "Second Brain - Sassy Voice Assistant",
  description: "Your sassy, voice-first second brain. Talk to your notes.",
};

const navLinks = [
  { href: "/", label: "Chat" },
  { href: "/dashboard", label: "Brain" },
  { href: "/secretary", label: "Secretary" },
  { href: "/life", label: "Life OS" },
  { href: "/trading", label: "Trading" },
  { href: "/marketplace", label: "Plugins" },
  { href: "/smarthome", label: "Smart Home" },
  { href: "/settings", label: "Settings" },
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
        <main className="pt-12">
          <ClientLayout>{children}</ClientLayout>
        </main>
      </body>
    </html>
  );
}
