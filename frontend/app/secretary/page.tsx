"use client";
import { useState, useEffect, useCallback } from "react";
import { configureEmail, getEmailConfig, getCalendar, addCalendarEvent, getContacts,
  addContact, searchContacts, webResearch, getBusinessSummary } from "@/lib/api";
import type { BusinessSummary as BS, CalendarEvent, Contact, ResearchResult } from "@/lib/types";
import { SkeletonCard } from "@/components/LoadingSkeleton";

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

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div><h1 className="text-xl font-bold text-purple-400">Business Secretary</h1><p className="text-xs text-gray-500 mt-0.5">Email, calendar, contacts & research</p></div>
      <div className="flex gap-1 border-b border-gray-800/30 pb-2 overflow-x-auto">
        {(["overview", "email", "calendar", "contacts", "research"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-4 py-1.5 text-xs font-mono rounded-t-lg transition-colors whitespace-nowrap ${tab === t ? "text-purple-400 bg-purple-900/10 border-b-2 border-purple-500" : "text-gray-600 hover:text-gray-400"}`}>
            {t === "overview" ? "Overview" : t === "email" ? "Email" : t === "calendar" ? "Calendar" : t === "contacts" ? "Contacts" : "Research"}
          </button>
        ))}
      </div>
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4"><SkeletonCard /><SkeletonCard /><SkeletonCard /></div>
      ) : (
        <>
          {tab === "overview" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <StatCard title="Emails" value={summary?.total_emails?.toString() || "0"} sub={`${summary?.unread_emails || 0} unread`} />
                <StatCard title="Events" value={summary?.upcoming_events?.toString() || "0"} sub="upcoming" />
                <StatCard title="Contacts" value={summary?.total_contacts?.toString() || "0"} sub="saved" />
                <StatCard title="Status" value="Connected" sub="All systems" />
              </div>
              <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5">
                <p className="text-xs text-gray-500">Use the tabs to manage email, schedule events, search contacts, and research topics.</p>
              </div>
            </div>
          )}
          {tab === "email" && (
            <div className="space-y-4">
              <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">Email</h2>
              <p className="text-xs text-gray-600">Configure SMTP/IMAP in Settings. Use chat to send and read emails.</p>
            </div>
          )}
          {tab === "calendar" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">Calendar</h2>
                <button onClick={() => setShowAddEvent(!showAddEvent)} className="text-xs text-purple-400 hover:text-purple-300">+ Add Event</button>
              </div>
              {showAddEvent && (
                <div className="bg-gray-900/60 border border-gray-800/50 rounded-xl p-5 space-y-3">
                  <input value={eventTitle} onChange={e => setEventTitle(e.target.value)} placeholder="Event title" className="w-full bg-gray-800/50 border border-gray-700/50 rounded px-3 py-1.5 text-xs text-gray-200" />
                  <input type="date" value={eventDate} onChange={e => setEventDate(e.target.value)} className="w-full bg-gray-800/50 border border-gray-700/50 rounded px-3 py-1.5 text-xs text-gray-200" />
                  <button onClick={handleAddEvent} className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-lg">Save</button>
                </div>
              )}
              {events.length > 0 ? (
                <div className="space-y-2">
                  {events.map((e, i) => (
                    <div key={i} className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-4 flex items-center justify-between">
                      <span className="text-sm text-gray-200">{e.title}</span>
                      <span className="text-xs text-gray-500 font-mono">{e.date}{e.time ? ` ${e.time}` : ""}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-12 text-gray-600 text-sm">No events.</p>
              )}
            </div>
          )}
          {tab === "contacts" && (
            <div className="space-y-4">
              <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">Contacts</h2>
              <input value={searchQ} onChange={e => { setSearchQ(e.target.value); handleSearchContact(e.target.value); }} placeholder="Search contacts..." className="w-full bg-gray-800/50 border border-gray-700/50 rounded px-3 py-2 text-xs text-gray-200" />
              {contacts.length > 0 ? (
                <div className="space-y-2">
                  {contacts.map((c, i) => (
                    <div key={i} className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-4">
                      <p className="text-sm text-gray-200">{c.name}</p>
                      <p className="text-xs text-gray-500">{c.email}{c.phone ? ` • ${c.phone}` : ""}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-12 text-gray-600 text-sm">No contacts found.</p>
              )}
            </div>
          )}
          {tab === "research" && (
            <div className="space-y-4">
              <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider">Web Research</h2>
              <div className="flex gap-2">
                <input value={researchQ} onChange={e => setResearchQ(e.target.value)} placeholder="Research topic..." className="flex-1 bg-gray-800/50 border border-gray-700/50 rounded px-3 py-2 text-xs text-gray-200" />
                <button onClick={handleResearch} className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-lg">Search</button>
              </div>
              {research && (
                <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5 space-y-3">
                  <p className="text-xs text-gray-300">{research.summary}</p>
                  {research.sources?.length > 0 && (
                    <div className="space-y-1">
                      {research.sources.map((s, i) => (
                        <p key={i} className="text-[10px] text-gray-500">• {s.title}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ title, value, sub }: { title: string; value: string; sub: string }) {
  return (
    <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-4">
      <p className="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-1">{title}</p>
      <p className="text-sm font-semibold text-gray-200">{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}
