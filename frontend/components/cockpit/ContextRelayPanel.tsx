"use client";

import React, { useState, useEffect, useCallback } from "react";

interface CalendarEvent {
  subject: string;
  start: string;
  end?: string;
  duration_min?: number;
  location?: string;
  importance?: number;
  source?: string;
}

interface EmailSnippet {
  sender: string;
  sender_email?: string;
  subject: string;
  received_at: string;
  snippet?: string;
  is_read?: boolean;
  importance?: number;
  source?: string;
}

interface Contact {
  name: string;
  email?: string;
  company?: string;
  phone?: string;
  source?: string;
}

interface UrgencySignal {
  level: "low" | "medium" | "high";
  signals: string[];
}

interface ContextRelayData {
  initialized: boolean;
  platform: string;
  calendar_source: string | null;
  email_source: string | null;
  contacts_source: string | null;
  calendar: { events: CalendarEvent[]; count: number; next_event: CalendarEvent | null };
  emails: { recent: EmailSnippet[]; count: number; unread_count: number };
  contacts: { people: Contact[]; count: number };
  urgency: UrgencySignal;
  patterns: {
    meeting_heavy_day: boolean;
    frequent_communicators: { name: string; count: number }[];
    upcoming_deadlines: { subject: string; start: string }[];
    work_hours_active: boolean;
  };
  summary: string;
}

const BASE =
  typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : "https://dgfhgjhj-jarvis-ai-brain.hf.space";

export default function ContextRelayPanel() {
  const [data, setData] = useState<ContextRelayData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"calendar" | "emails" | "contacts" | "patterns">("calendar");

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/context/relay/full?user_id=local`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setData(d);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to fetch context");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 30000);
    return () => clearInterval(iv);
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-zinc-950 rounded-xl border border-zinc-800">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs font-mono text-zinc-500">INITIALIZING CONTEXT RELAY...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-zinc-950 rounded-xl border border-zinc-800">
        <div className="text-center space-y-2 px-4">
          <p className="text-xs font-mono text-red-400">CONTEXT RELAY ERROR</p>
          <p className="text-[10px] text-zinc-500">{error}</p>
          <button onClick={fetchData} className="text-[10px] text-indigo-400 hover:text-indigo-300 font-mono">RETRY</button>
        </div>
      </div>
    );
  }

  const cal = data?.calendar || { events: [], count: 0, next_event: null };
  const em = data?.emails || { recent: [], count: 0, unread_count: 0 };
  const ct = data?.contacts || { people: [], count: 0 };
  const urg = data?.urgency || { level: "low", signals: [] };
  const pat = data?.patterns || { meeting_heavy_day: false, frequent_communicators: [], upcoming_deadlines: [], work_hours_active: false };

  const urgColor = urg.level === "high" ? "text-red-400 bg-red-950/50" : urg.level === "medium" ? "text-amber-400 bg-amber-950/50" : "text-zinc-400 bg-zinc-800/50";

  return (
    <div className="w-full h-full bg-zinc-950 text-zinc-100 font-sans rounded-xl border border-zinc-800 shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/80 shrink-0">
        <div>
          <span className="text-[9px] font-mono tracking-widest text-indigo-400 uppercase">Deep Context Relay</span>
          <h3 className="text-sm font-bold text-zinc-200">JARVIS // CONTEXT_INGESTION_ENGINE</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
            data?.initialized ? "bg-emerald-950/50 text-emerald-400" : "bg-zinc-800 text-zinc-500"
          }`}>
            {data?.initialized ? "ACTIVE" : "INACTIVE"}
          </span>
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${urgColor}`}>
            {urg.level.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Urgency Signals */}
      {urg.signals.length > 0 && (
        <div className="px-4 py-2 border-b border-zinc-800/50 bg-zinc-900/30 shrink-0">
          <div className="flex flex-wrap gap-1.5">
            {urg.signals.map((s, i) => (
              <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/40 text-indigo-300 border border-indigo-800/30">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Stats Bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-zinc-800/50 text-[10px] font-mono text-zinc-500 shrink-0">
        <span>CAL: <span className="text-zinc-300">{cal.count}</span></span>
        <span>EMAIL: <span className="text-zinc-300">{em.count}</span> <span className="text-amber-400">({em.unread_count} unread)</span></span>
        <span>CONTACTS: <span className="text-zinc-300">{ct.count}</span></span>
        <span className="ml-auto text-zinc-600">{data?.platform?.toUpperCase()}</span>
      </div>

      {/* Tab Bar */}
      <div className="flex border-b border-zinc-800/50 shrink-0">
        {(["calendar", "emails", "contacts", "patterns"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 text-[10px] font-mono uppercase tracking-wider py-2 transition-colors ${
              tab === t ? "text-indigo-400 border-b-2 border-indigo-400 bg-indigo-950/20" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {tab === "calendar" && (
          <>
            {cal.next_event && (
              <div className="p-3 rounded-lg border border-indigo-800/40 bg-indigo-950/20 mb-3">
                <p className="text-[9px] font-mono text-indigo-400 uppercase mb-1">Next Event</p>
                <p className="text-sm font-bold text-zinc-200">{cal.next_event.subject}</p>
                <p className="text-[10px] text-zinc-400 font-mono mt-1">{cal.next_event.start} ({cal.next_event.duration_min || "?"} min)</p>
                {cal.next_event.location && <p className="text-[10px] text-zinc-500">{cal.next_event.location}</p>}
              </div>
            )}
            {cal.events.length === 0 ? (
              <p className="text-xs text-zinc-600 text-center py-4 font-mono">No upcoming events</p>
            ) : (
              cal.events.map((evt, i) => (
                <div key={i} className="bg-zinc-900/40 p-3 rounded-lg border border-zinc-800/60 text-xs">
                  <div className="flex justify-between items-start">
                    <p className="font-bold text-zinc-200 truncate">{evt.subject}</p>
                    {evt.importance && evt.importance > 1 && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-950/50 text-red-400 font-mono shrink-0 ml-2">HIGH</span>
                    )}
                  </div>
                  <p className="text-[10px] text-zinc-500 font-mono mt-1">
                    {evt.start} ({evt.duration_min || "?"} min)
                    {evt.location ? ` | ${evt.location}` : ""}
                  </p>
                </div>
              ))
            )}
          </>
        )}

        {tab === "emails" && (
          <>
            {em.recent.length === 0 ? (
              <p className="text-xs text-zinc-600 text-center py-4 font-mono">No recent emails</p>
            ) : (
              em.recent.map((mail, i) => (
                <div key={i} className={`p-3 rounded-lg border text-xs space-y-1 ${
                  mail.is_read === false ? "bg-zinc-900/60 border-zinc-700/60" : "bg-zinc-900/30 border-zinc-800/40"
                }`}>
                  <div className="flex justify-between items-center">
                    <span className="font-medium text-indigo-300 truncate max-w-[140px]">{mail.sender}</span>
                    <div className="flex items-center gap-2">
                      {mail.is_read === false && <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />}
                      <span className="text-[9px] font-mono text-zinc-600">
                        {mail.received_at?.split(" ")?.[1] || mail.received_at?.slice(11, 16) || ""}
                      </span>
                    </div>
                  </div>
                  <p className="text-zinc-300 italic truncate">"{mail.subject}"</p>
                  {mail.snippet && <p className="text-[10px] text-zinc-500 truncate">{mail.snippet}</p>}
                </div>
              ))
            )}
          </>
        )}

        {tab === "contacts" && (
          <>
            {ct.people.length === 0 ? (
              <p className="text-xs text-zinc-600 text-center py-4 font-mono">No contacts loaded</p>
            ) : (
              ct.people.map((c, i) => (
                <div key={i} className="bg-zinc-900/30 p-3 rounded-lg border border-zinc-800/40 text-xs">
                  <p className="font-bold text-zinc-200">{c.name}</p>
                  {c.email && <p className="text-[10px] text-indigo-400 font-mono">{c.email}</p>}
                  {c.company && <p className="text-[10px] text-zinc-500">{c.company}</p>}
                  {c.phone && <p className="text-[10px] text-zinc-500 font-mono">{c.phone}</p>}
                </div>
              ))
            )}
          </>
        )}

        {tab === "patterns" && (
          <div className="space-y-3">
            <div className="bg-zinc-900/30 p-3 rounded-lg border border-zinc-800/40">
              <p className="text-[9px] font-mono text-zinc-500 uppercase mb-2">Behavioral Patterns</p>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Meeting-heavy day</span>
                  <span className={pat.meeting_heavy_day ? "text-amber-400" : "text-zinc-600"}>
                    {pat.meeting_heavy_day ? "YES" : "No"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Work hours active</span>
                  <span className={pat.work_hours_active ? "text-emerald-400" : "text-zinc-600"}>
                    {pat.work_hours_active ? "YES" : "No"}
                  </span>
                </div>
              </div>
            </div>

            {pat.upcoming_deadlines.length > 0 && (
              <div className="bg-red-950/20 p-3 rounded-lg border border-red-800/30">
                <p className="text-[9px] font-mono text-red-400 uppercase mb-2">Upcoming Deadlines</p>
                {pat.upcoming_deadlines.map((d, i) => (
                  <div key={i} className="text-xs">
                    <p className="text-zinc-300">{d.subject}</p>
                    <p className="text-[10px] text-zinc-500 font-mono">{d.start}</p>
                  </div>
                ))}
              </div>
            )}

            {pat.frequent_communicators.length > 0 && (
              <div className="bg-zinc-900/30 p-3 rounded-lg border border-zinc-800/40">
                <p className="text-[9px] font-mono text-zinc-500 uppercase mb-2">Frequent Communicators</p>
                {pat.frequent_communicators.map((c, i) => (
                  <div key={i} className="flex justify-between text-xs">
                    <span className="text-zinc-300">{c.name}</span>
                    <span className="text-zinc-500 font-mono">{c.count} msgs</span>
                  </div>
                ))}
              </div>
            )}

            {data?.summary && (
              <div className="bg-zinc-900/20 p-3 rounded-lg border border-zinc-800/30">
                <p className="text-[9px] font-mono text-zinc-500 uppercase mb-1">Context Summary</p>
                <p className="text-xs text-zinc-400">{data.summary}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-zinc-800/50 flex items-center justify-between shrink-0">
        <span className="text-[9px] font-mono text-zinc-600">
          {data?.calendar_source ? `CAL: ${data.calendar_source}` : "CAL: none"} | {data?.email_source ? `EMAIL: ${data.email_source}` : "EMAIL: none"}
        </span>
        <button onClick={fetchData} className="text-[9px] font-mono text-indigo-400 hover:text-indigo-300">
          REFRESH
        </button>
      </div>
    </div>
  );
}
