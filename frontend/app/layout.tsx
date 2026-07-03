import type { Metadata } from "next";
import ClientLayout from "@/components/ClientLayout";
import "./globals.css";

export const metadata: Metadata = {
  title: "J.A.R.V.I.S. — Sovereign Digital Entity",
  description: "Your omnipresent AI. Voice-first OS, smart home, and web automation.",
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
