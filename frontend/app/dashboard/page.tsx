"use client";

import { useState, useEffect, useCallback } from "react";
import { uploadDocument, getDocuments } from "@/lib/api";

export default function Dashboard() {
  const [docs, setDocs] = useState<{ name: string; chunks: number }[]>([]);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<{ name: string; content: string } | null>(null);
  const [hasDocs, setHasDocs] = useState(false);
  const [chunkCount, setChunkCount] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const r = await getDocuments();
        setHasDocs(r.has_documents);
        setChunkCount(r.chunk_count);
      } catch {}
    })();
  }, []);

  const handleFile = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setStatus(null);
    try {
      const text = await file.text();
      const b64 = btoa(text);
      const res = await uploadDocument(file.name, file.type || "text/plain", b64);
      setDocs((p) => [...p, { name: file.name, chunks: res.chunks }]);
      setHasDocs(true);
      setChunkCount((c) => c + res.chunks);
      setStatus({ name: file.name, content: `Indexed ${res.chunks} chunks` });
    } catch {
      setStatus({ name: file.name, content: "Upload failed" });
    }
    setUploading(false);
  }, []);

  const handleNote = useCallback(async () => {
    const text = prompt("Paste or type a note:");
    if (!text) return;
    setUploading(true);
    setStatus(null);
    try {
      const b64 = btoa(text);
      const res = await uploadDocument("note.txt", "text/plain", b64);
      setDocs((p) => [...p, { name: `note (${text.slice(0, 30)}...)`, chunks: res.chunks }]);
      setHasDocs(true);
      setChunkCount((c) => c + res.chunks);
      setStatus({ name: "note", content: `Indexed ${res.chunks} chunks` });
    } catch {
      setStatus({ name: "note", content: "Upload failed" });
    }
    setUploading(false);
  }, []);

  const totalDocs = docs.length + (hasDocs ? 1 : 0);

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-purple-400">Your Brain</h1>
          <p className="text-sm text-gray-500 mt-1">Upload notes, PDFs, or type ideas. Jason remembers everything.</p>
        </div>
        <div className="text-right text-xs font-mono text-gray-600">
          <div>{chunkCount} chunks indexed</div>
          <div>{totalDocs} documents</div>
        </div>
      </div>

      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">Upload</h2>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 px-4 py-2 bg-purple-600/20 border border-purple-600/30 rounded-lg text-sm text-purple-300 cursor-pointer hover:bg-purple-600/30 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
            </svg>
            Upload file
            <input type="file" accept=".txt,.pdf,.md,.csv" className="hidden" onChange={handleFile} disabled={uploading} />
          </label>
          <button
            onClick={handleNote}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:bg-gray-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Paste note
          </button>
          {uploading && <span className="text-xs text-gray-500 animate-pulse">Processing...</span>}
        </div>
        {status && (
          <div className="text-xs text-gray-400 bg-gray-800/50 rounded px-3 py-2">
            <span className="text-purple-400">{status.name}</span>: {status.content}
          </div>
        )}
      </section>

      {docs.length > 0 && (
        <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 space-y-3">
          <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">Uploaded Notes</h2>
          <div className="space-y-2">
            {docs.map((d, i) => (
              <div key={i} className="flex items-center justify-between bg-gray-800/40 rounded-lg px-4 py-2.5">
                <span className="text-sm text-gray-300 truncate">{d.name}</span>
                <span className="text-xs text-gray-600 font-mono">{d.chunks} chunks</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {!hasDocs && docs.length === 0 && (
        <div className="text-center py-16">
          <div className="text-5xl mb-4 opacity-20">🧠</div>
          <p className="text-gray-600 text-sm">Your brain is empty. Upload a file or paste a note to get started.</p>
        </div>
      )}
    </div>
  );
}
