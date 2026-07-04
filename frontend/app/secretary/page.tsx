"use client";

import { useState, useEffect, useCallback } from "react";
import { getCalendar, addCalendarEvent, getContacts, searchContacts, webResearch, getBusinessSummary } from "@/lib/api";
import type { BusinessSummary as BS, CalendarEvent, Contact, ResearchResult } from "@/lib/types";
import Navbar from "@/components/Navbar";

type Tab = "overview" | "email" | "calendar" | "contacts" | "research";

export default function SecretaryPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [summary, setSummary] = useState<BS | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [research, setResearch] = useState<ResearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddEvent, setShowAddEvent] = useState(false);
  const [eventTitle, setEventTitle] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [researchQ, setResearchQ] = useState("");
  const [searchQ, setSearchQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const [s, e, c] = await Promise.allSettled([
      getBusinessSummary(), getCalendar(), getContacts(),
    ]);
    if (s.status === "fulfilled") setSummary(s.value);
    if (e.status === "fulfilled") setEvents(e.value?.events || e.value || []);
    if (c.status === "fulfilled") setContacts(c.value?.contacts || c.value || []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAddEvent = useCallback(async () => {
    if (!eventTitle || !eventDate) return;
    await addCalendarEvent(eventTitle, eventDate);
    setShowAddEvent(false); setEventTitle(""); setEventDate("");
    const e = await getCalendar(); setEvents(e?.events || e || []);
  }, [eventTitle, eventDate]);

  const handleResearch = useCallback(async () => {
    if (!researchQ.trim()) return;
    setResearch(await webResearch(researchQ));
  }, [researchQ]);

  const handleSearchContact = useCallback(async (q: string) => {
    if (!q) return;
    const r = await searchContacts(q);
    setContacts(r?.results || r || []);
  }, []);

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "email", label: "Email" },
    { key: "calendar", label: "Calendar" },
    { key: "contacts", label: "Contacts" },
    { key: "research", label: "Research" },
  ];

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">Business Secretary</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Email, calendar, contacts & research</p>
        </div>

        <div className="flex border-b border-white/[0.06] overflow-x-auto">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors duration-150 whitespace-nowrap ${
                tab === t.key
                  ? "text-zinc-100 border-violet-500"
                  : "text-zinc-500 hover:text-zinc-300 border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 animate-pulse">
                <div className="h-3 bg-white/[0.06] rounded w-1/2 mb-2" />
                <div className="h-5 bg-white/[0.04] rounded w-1/3" />
              </div>
            ))}
          </div>
        ) : (
          <>
            {tab === "overview" && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatCard title="Emails" value={summary?.total_emails?.toString() || "0"} sub={`${summary?.unread_emails || 0} unread`} />
                  <StatCard title="Events" value={summary?.upcoming_events?.toString() || "0"} sub="upcoming" />
                  <StatCard title="Contacts" value={summary?.total_contacts?.toString() || "0"} sub="saved" />
                  <StatCard title="Status" value="Connected" sub="All systems" />
                </div>
                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                  <p className="text-sm text-zinc-500">Use the tabs to manage email, schedule events, search contacts, and research topics.</p>
                </div>
              </div>
            )}

            {tab === "email" && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Email</h2>
                <p className="text-sm text-zinc-500">Configure SMTP/IMAP in Settings. Use chat to send and read emails.</p>
              </div>
            )}

            {tab === "calendar" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-zinc-100">Calendar</h2>
                  <button onClick={() => setShowAddEvent(!showAddEvent)} className="text-sm text-violet-400 hover:text-violet-300 transition-colors duration-150">
                    + Add Event
                  </button>
                </div>
                {showAddEvent && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3 animate-fade-in">
                    <input
                      value={eventTitle}
                      onChange={e => setEventTitle(e.target.value)}
                      placeholder="Event title"
                      className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                    />
                    <input
                      type="date"
                      value={eventDate}
                      onChange={e => setEventDate(e.target.value)}
                      className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                    />
                    <button onClick={handleAddEvent} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
                      Save
                    </button>
                  </div>
                )}
                {events.length > 0 ? (
                  <div className="space-y-2">
                    {events.map((e, i) => (
                      <div
                        key={i}
                        className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex items-center justify-between animate-fade-in"
                        style={{ animationDelay: `${i * 40}ms` }}
                      >
                        <span className="text-sm text-zinc-200">{e.title}</span>
                        <span className="text-xs text-zinc-500 font-mono">{e.date}{e.time ? ` ${e.time}` : ""}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-16 text-zinc-600 text-sm">No events.</div>
                )}
              </div>
            )}

            {tab === "contacts" && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Contacts</h2>
                <input
                  value={searchQ}
                  onChange={e => { setSearchQ(e.target.value); handleSearchContact(e.target.value); }}
                  placeholder="Search contacts..."
                  className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                />
                {contacts.length > 0 ? (
                  <div className="space-y-2">
                    {contacts.map((c, i) => (
                      <div
                        key={i}
                        className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 animate-fade-in"
                        style={{ animationDelay: `${i * 40}ms` }}
                      >
                        <p className="text-sm text-zinc-200">{c.name}</p>
                        <p className="text-xs text-zinc-500">{c.email}{c.phone ? ` • ${c.phone}` : ""}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-16 text-zinc-600 text-sm">No contacts found.</div>
                )}
              </div>
            )}

            {tab === "research" && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Web Research</h2>
                <div className="flex gap-2">
                  <input
                    value={researchQ}
                    onChange={e => setResearchQ(e.target.value)}
                    placeholder="Research topic..."
                    className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                  />
                  <button onClick={handleResearch} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
                    Search
                  </button>
                </div>
                {research && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3">
                    <p className="text-sm text-zinc-300">{research.summary}</p>
                    {research.sources?.length > 0 && (
                      <div className="space-y-1">
                        {research.sources.map((s, i) => (
                          <p key={i} className="text-xs text-zinc-500">• {s.title}</p>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function StatCard({ title, value, sub }: { title: string; value: string; sub: string }) {
  return (
    <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
      <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-1">{title}</p>
      <p className="text-sm font-semibold text-zinc-200">{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-0.5">{sub}</p>}
    </div>
  );
}
