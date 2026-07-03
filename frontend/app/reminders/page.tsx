"use client";

import { useState, useEffect, useCallback } from "react";
import { listReminders, createReminder, updateReminder, deleteReminder } from "@/lib/api";

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
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-purple-400">Reminders</h1>
          <p className="text-sm text-gray-500 mt-1">JARVIS remembers so you don&apos;t have to.</p>
        </div>
        <div className="text-xs font-mono text-gray-600">{active.length} active</div>
      </div>

      <section className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">New Reminder</h2>
        <div className="flex flex-col gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="What should JARVIS remind you about?"
            className="bg-gray-800/80 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-600 outline-none focus:border-purple-500/50"
          />
          <div className="flex gap-2">
            <input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Details (optional)"
              className="flex-1 bg-gray-800/80 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-gray-600 outline-none focus:border-purple-500/50"
            />
            <input
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              className="bg-gray-800/80 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200 outline-none focus:border-purple-500/50"
            />
            <button
              onClick={handleAdd}
              className="px-4 py-2 bg-purple-600/20 border border-purple-600/30 rounded-lg text-sm text-purple-300 hover:bg-purple-600/30 transition-colors"
            >
              Add
            </button>
          </div>
        </div>
      </section>

      {active.length > 0 && (
        <section className="space-y-2">
          {active.map((r) => (
            <div key={r.id} className="flex items-center gap-3 bg-gray-900/40 border border-gray-800/30 rounded-lg px-4 py-3">
              <button
                onClick={() => handleToggle(r.id, r.completed)}
                className="w-5 h-5 rounded-full border-2 border-gray-600 hover:border-purple-500 transition-colors flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200 truncate">{r.title}</p>
                {r.description && <p className="text-xs text-gray-500 truncate">{r.description}</p>}
              </div>
              {r.due_date && <span className="text-xs text-gray-600 font-mono whitespace-nowrap">{r.due_date}</span>}
              <button
                onClick={() => handleDelete(r.id)}
                className="text-gray-600 hover:text-red-400 transition-colors flex-shrink-0"
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
          <h2 className="text-xs font-mono text-gray-600 uppercase tracking-wider">Completed</h2>
          {done.map((r) => (
            <div key={r.id} className="flex items-center gap-3 bg-gray-900/20 border border-gray-800/20 rounded-lg px-4 py-2 opacity-50">
              <button
                onClick={() => handleToggle(r.id, r.completed)}
                className="w-5 h-5 rounded-full border-2 border-green-700 bg-green-700/30 flex-shrink-0"
              >
                <svg className="w-3 h-3 text-green-400 mx-auto mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              </button>
              <p className="text-sm text-gray-500 line-through flex-1">{r.title}</p>
              <button
                onClick={() => handleDelete(r.id)}
                className="text-gray-700 hover:text-red-400 transition-colors flex-shrink-0"
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
        <div className="text-center py-16">
          <div className="text-5xl mb-4 opacity-20">⏰</div>
          <p className="text-gray-600 text-sm">No reminders yet. Add one above.</p>
        </div>
      )}
    </div>
  );
}
