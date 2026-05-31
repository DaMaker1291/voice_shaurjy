"use client";

import { useState } from "react";
import FileUploader from "@/components/FileUploader";
import UsageMeter from "@/components/UsageMeter";

export default function Dashboard() {
  const [docs, setDocs] = useState<{ name: string; chunks: number }[]>([]);

  const handleUploadComplete = (name: string, chunks: number) => {
    setDocs((prev) => [...prev, { name, chunks }]);
  };

  return (
    <main className="max-w-2xl mx-auto p-4 space-y-6">
      <h1 className="text-2xl font-bold text-purple-400">Dashboard</h1>

      <section className="bg-gray-900 rounded-xl p-4 space-y-3">
        <h2 className="text-lg font-semibold">Your Documents</h2>
        <FileUploader onUploadComplete={handleUploadComplete} />
        {docs.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No documents yet. Upload PDFs or notes to build your second brain.
          </p>
        ) : (
          <ul className="space-y-1">
            {docs.map((d, i) => (
              <li key={i} className="text-sm text-gray-300">
                {d.name} &mdash; {d.chunks} chunks indexed
              </li>
            ))}
          </ul>
        )}
      </section>

      <UsageMeter />
    </main>
  );
}
