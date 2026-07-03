import type { Metadata } from "next";
import ClientLayout from "@/components/ClientLayout";
import "./globals.css";

export const metadata: Metadata = {
  title: "JARVIS — The System Engine",
  description: "The Autonomous Ecosystem Orchestrator. Voice-first sovereign AI with system control, smart home, and web automation.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950">
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
