"use client";

import { useState, useEffect, useCallback } from "react";
import { listReminders, createReminder, updateReminder, deleteReminder } from "@/lib/api";
import Navbar from "@/components/Navbar";

interface Reminder {
  id: string;
  title: string;
  description: string;
  due_date: string;
  completed: boolean;
  created_at: string;
}

export default function Reminders() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [due, setDue] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await listReminders();
      setReminders(r.reminders);
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = useCallback(async () => {
    if (!title.trim()) return;
    await createReminder(title.trim(), desc.trim(), due);
    setTitle("");
    setDesc("");
    setDue("");
    load();
  }, [title, desc, due, load]);

  const handleToggle = useCallback(async (id: string, completed: boolean) => {
    await updateReminder(id, { completed: !completed });
    load();
  }, [load]);

  const handleDelete = useCallback(async (id: string) => {
    await deleteReminder(id);
    load();
  }, [load]);

  const active = reminders.filter((r) => !r.completed);
  const done = reminders.filter((r) => r.completed);

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Reminders</h1>
            <p className="text-sm text-zinc-500 mt-1">JARVIS remembers so you don&apos;t have to.</p>
          </div>
          <div className="text-xs text-zinc-500 font-mono">{active.length} active</div>
        </div>

        <section className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3">
          <h2 className="text-sm font-medium text-zinc-300">New Reminder</h2>
          <div className="flex flex-col gap-2">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              placeholder="What should JARVIS remind you about?"
              className="bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
            />
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="Details (optional)"
                className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
              />
              <input
                type="date"
                value={due}
                onChange={(e) => setDue(e.target.value)}
                className="bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
              />
              <button onClick={handleAdd} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
                Add
              </button>
            </div>
          </div>
        </section>

        {active.length > 0 && (
          <section className="space-y-2">
            {active.map((r, i) => (
              <div
                key={r.id}
                className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex items-center gap-3 animate-fade-in"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <button
                  onClick={() => handleToggle(r.id, r.completed)}
                  className="w-5 h-5 rounded-full border-2 border-zinc-600 hover:border-violet-500 transition-colors duration-150 shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-zinc-200 truncate">{r.title}</p>
                  {r.description && <p className="text-xs text-zinc-500 truncate">{r.description}</p>}
                </div>
                {r.due_date && (
                  <span className="text-xs text-zinc-500 font-mono whitespace-nowrap">{r.due_date}</span>
                )}
                <button
                  onClick={() => handleDelete(r.id)}
                  className="text-zinc-600 hover:text-red-400 transition-colors duration-150 shrink-0"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </section>
        )}

        {done.length > 0 && (
          <section className="space-y-2">
            <h2 className="text-xs font-mono text-zinc-600 uppercase tracking-wider">Completed</h2>
            {done.map((r) => (
              <div key={r.id} className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex items-center gap-3 opacity-50">
                <button
                  onClick={() => handleToggle(r.id, r.completed)}
                  className="w-5 h-5 rounded-full border-2 border-emerald-400/70 bg-emerald-400/30 shrink-0"
                >
                  <svg className="w-3 h-3 text-emerald-400 mx-auto mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </button>
                <p className="text-sm text-zinc-500 line-through flex-1">{r.title}</p>
                <button
                  onClick={() => handleDelete(r.id)}
                  className="text-zinc-700 hover:text-red-400 transition-colors duration-150 shrink-0"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </section>
        )}

        {reminders.length === 0 && (
          <div className="text-center py-20 text-zinc-600">
            <svg className="w-10 h-10 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm">No reminders yet. Add one above.</p>
          </div>
        )}
      </main>
    </div>
  );
}
