"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { uploadDocument, getDocuments } from "@/lib/api";
import Navbar from "@/components/Navbar";

export default function Dashboard() {
  const [docs, setDocs] = useState<{ name: string; chunks: number }[]>([]);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<{ name: string; content: string } | null>(null);
  const [hasDocs, setHasDocs] = useState(false);
  const [chunkCount, setChunkCount] = useState(0);
  const [noteText, setNoteText] = useState("");
  const [showNoteForm, setShowNoteForm] = useState(false);

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
    if (!noteText.trim()) return;
    setUploading(true);
    setStatus(null);
    try {
      const b64 = btoa(noteText);
      const res = await uploadDocument("note.txt", "text/plain", b64);
      setDocs((p) => [...p, { name: `note (${noteText.slice(0, 30)}...)`, chunks: res.chunks }]);
      setHasDocs(true);
      setChunkCount((c) => c + res.chunks);
      setStatus({ name: "note", content: `Indexed ${res.chunks} chunks` });
      setNoteText("");
      setShowNoteForm(false);
    } catch {
      setStatus({ name: "note", content: "Upload failed" });
    }
    setUploading(false);
  }, [noteText]);

  const totalDocs = docs.length + (hasDocs ? 1 : 0);

  const HF_API = "https://dgfhgjhj-jarvis-ai-brain.hf.space";

  function platformCmd(): string {
    if (typeof window === "undefined") return "";
    const p = navigator.platform?.toLowerCase() || "";
    if (p.includes("win"))
      return `powershell -c "curl.exe -sL '${HF_API}/relay' -o \\$env:TEMP\\relay.py; python \\$env:TEMP\\relay.py --user \\$env:USERNAME"`;
    if (p.includes("mac"))
      return `curl -sL '${HF_API}/relay' -o ~/relay.py && python3 ~/relay.py --user $(whoami)`;
    return `curl -sL '${HF_API}/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user $(whoami)`;
  }

  function platformLabel(): string {
    if (typeof window === "undefined") return "Windows";
    const p = navigator.platform?.toLowerCase() || "";
    if (p.includes("win")) return "Windows";
    if (p.includes("mac")) return "macOS";
    return "Linux";
  }

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Your Brain</h1>
            <p className="text-sm text-zinc-500 mt-1">Upload notes, PDFs, or type ideas. JARVIS remembers everything.</p>
          </div>
          <div className="text-right text-xs text-zinc-500 font-mono">
            <div>{chunkCount} chunks indexed</div>
            <div>{totalDocs} documents</div>
          </div>
        </div>

        <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-medium text-zinc-300">Desktop Agent</h2>
              <p className="text-xs text-zinc-500 mt-0.5">Let JARVIS control your {platformLabel().toLowerCase()} machine</p>
            </div>
            <Link href="/settings" className="text-xs text-violet-400 hover:text-violet-300 transition-colors duration-150">
              Settings &rarr;
            </Link>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <a
              href={`${HF_API}/relay`}
              download
              className="inline-flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium px-3.5 py-2 rounded-lg transition-colors duration-150"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Agent
            </a>
            <span className="text-xs text-zinc-600 font-mono">or run:</span>
            <code className="text-[10px] bg-white/[0.03] text-zinc-400 px-2.5 py-1.5 rounded select-all break-all max-w-md border border-white/[0.06]">
              {platformCmd()}
            </code>
          </div>
        </section>

        <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-zinc-300">Upload</h2>
            <button
              onClick={() => setShowNoteForm(!showNoteForm)}
              className="text-xs text-violet-400 hover:text-violet-300 transition-colors duration-150 font-mono"
            >
              {showNoteForm ? "Cancel" : "+ Paste note"}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <label className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600/10 border border-violet-500/20 rounded-lg text-sm text-violet-400 cursor-pointer hover:bg-violet-600/20 transition-colors duration-150">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
              </svg>
              Upload file
              <input type="file" accept=".txt,.pdf,.md,.csv" className="hidden" onChange={handleFile} disabled={uploading} />
            </label>
            {uploading && <span className="text-xs text-zinc-500 animate-pulse">Processing...</span>}
          </div>

          {showNoteForm && (
            <div className="space-y-3 animate-fade-in">
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Paste or type a note..."
                className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 min-h-[100px] font-mono outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150 resize-none"
              />
              <button
                onClick={handleNote}
                disabled={uploading || !noteText.trim()}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg transition-colors duration-150 disabled:opacity-40"
              >
                {uploading ? "Saving..." : "Save Note"}
              </button>
            </div>
          )}

          {status && (
            <div className="text-xs text-zinc-400 bg-white/[0.03] rounded-lg px-3 py-2 border border-white/[0.06]">
              <span className="text-violet-400">{status.name}</span>: {status.content}
            </div>
          )}
        </section>

        {docs.length > 0 && (
          <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3">
            <h2 className="text-sm font-medium text-zinc-300">Uploaded Notes</h2>
            <div className="space-y-2">
              {docs.map((d, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between bg-white/[0.02] rounded-lg px-4 py-2.5 border border-white/[0.04] animate-fade-in"
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                  <span className="text-sm text-zinc-300 truncate">{d.name}</span>
                  <span className="text-xs text-zinc-500 font-mono">{d.chunks} chunks</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {!hasDocs && docs.length === 0 && (
          <div className="text-center py-20 text-zinc-600">
            <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <p className="text-sm">Your brain is empty. Upload a file or paste a note to get started.</p>
          </div>
        )}
      </main>
    </div>
  );
}
