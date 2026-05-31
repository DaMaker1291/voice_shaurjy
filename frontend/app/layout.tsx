import type { Metadata } from "next";
import "./globals.css";
import NavBar from "@/components/NavBar";

export const metadata: Metadata = {
  title: "Second Brain - Sassy Voice Assistant",
  description: "Your sassy, voice-first second brain. Talk to your notes.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-gray-950">
        <NavBar />
        <main className="flex-1 pt-14">{children}</main>
      </body>
    </html>
  );
}
