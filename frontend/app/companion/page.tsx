"use client";

import { useState, useEffect, useCallback } from "react";
import Navbar from "@/components/Navbar";
import { BASE } from "@/lib/api";

interface CompanionResponse {
  mode: string;
  empathy_note?: string;
  revision_data?: {
    concept: string;
    summary: string;
    quiz_question: string;
    answer_key: string;
  };
  reminders: string[];
  memory_stored: boolean;
  proactive_triggers_fired: string[];
  crisis_detected: boolean;
  crisis_resources?: any;
  reply: string;
  confidence: number;
}

interface MemoryEntry {
  id: number;
  timestamp: number;
  category: string;
  content: string;
  importance: number;
}

interface Reminder {
  id: number;
  trigger_text: string;
  recurring_pattern: string;
  active: boolean;
  fire_count: number;
}

interface StudyCard {
  id: number;
  concept: string;
  summary: string;
  quiz_question: string;
  answer_key: string;
  field_name: string;
  next_review: number;
  ease_factor: number;
}

export default function CompanionPage() {
  const [input, setInput] = useState("");
  const [response, setResponse] = useState<CompanionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"chat" | "memory" | "reminders" | "study">("chat");
  const [memories, setMemories] = useState<MemoryEntry[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [dueCards, setDueCards] = useState<StudyCard[]>([]);
  const [showAnswer, setShowAnswer] = useState(false);
  const [crisisResources, setCrisisResources] = useState<any>(null);

  // Chat history
  const [chatHistory, setChatHistory] = useState<{ role: string; content: string; mode?: string; timestamp: number }[]>([]);

  const refreshMemory = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/api/companion/memory?limit=30`);
      const data = await r.json();
      setMemories(data.memories || []);
    } catch {}
  }, []);

  const refreshReminders = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/api/companion/reminders`);
      const data = await r.json();
      setReminders(data.reminders || []);
    } catch {}
  }, []);

  const refreshDueCards = useCallback(async () => {
    try {
      const r = await fetch(`${BASE}/api/companion/education/due?limit=20`);
      const data = await r.json();
      setDueCards(data.cards || []);
    } catch {}
  }, []);

  useEffect(() => {
    refreshMemory();
    refreshReminders();
    refreshDueCards();
  }, [refreshMemory, refreshReminders, refreshDueCards]);

  const processMessage = async () => {
    if (!input.trim() || loading) return;
    const msg = input.trim();
    setInput("");
    setLoading(true);

    setChatHistory((h) => [...h, { role: "user", content: msg, timestamp: Date.now() }]);

    try {
      const r = await fetch(`${BASE}/api/companion/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: msg }),
      });
      const data: CompanionResponse = await r.json();
      setResponse(data);
      setChatHistory((h) => [...h, { role: "assistant", content: data.reply, mode: data.mode, timestamp: Date.now() }]);

      if (data.crisis_detected) {
        const cr = await fetch(`${BASE}/api/companion/crisis/resources`);
        setCrisisResources(await cr.json());
      }

      refreshMemory();
      refreshReminders();
    } catch {
      setChatHistory((h) => [...h, { role: "assistant", content: "I'm here. Something went wrong, but I'm listening.", timestamp: Date.now() }]);
    }
    setLoading(false);
  };

  const reviewCard = async (cardId: number, quality: number) => {
    try {
      await fetch(`${BASE}/api/companion/education/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_id: cardId, quality }),
      });
      refreshDueCards();
    } catch {}
  };

  const modeColor = (mode: string) => {
    switch (mode) {
      case "SUPPORTIVE": return "text-teal-400 bg-teal-500/10 border-teal-500/20";
      case "EDUCATIONAL": return "text-indigo-400 bg-indigo-500/10 border-indigo-500/20";
      case "LOGISTICAL": return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      default: return "text-zinc-400 bg-white/[0.04] border-white/[0.06]";
    }
  };

  const categoryColor = (cat: string) => {
    switch (cat) {
      case "emotion": return "text-rose-400";
      case "concern": return "text-amber-400";
      case "preference": return "text-violet-400";
      case "habit": return "text-cyan-400";
      case "event": return "text-emerald-400";
      default: return "text-zinc-400";
    }
  };

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-4 md:p-6 max-w-6xl mx-auto w-full">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">CORE Companion</h1>
            <p className="text-xs text-zinc-500 font-mono mt-0.5">Memory · Education · Empathy · Life Context</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-white/[0.06] mb-6 overflow-x-auto">
          {[
            { id: "chat" as const, label: "Chat" },
            { id: "memory" as const, label: "Memory" },
            { id: "reminders" as const, label: "Reminders" },
            { id: "study" as const, label: "Study" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors duration-150 whitespace-nowrap ${
                tab === t.id
                  ? "text-zinc-100 border-violet-500"
                  : "text-zinc-500 hover:text-zinc-300 border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Chat Tab */}
        {tab === "chat" && (
          <div className="flex flex-col h-[calc(100vh-200px)]">
            {/* Crisis Banner */}
            {response?.crisis_detected && crisisResources && (
              <div className="mb-4 p-4 rounded-xl bg-red-500/10 border border-red-500/30">
                <p className="text-sm font-semibold text-red-400 mb-2">If you or someone you know is in crisis, please reach out:</p>
                {crisisResources.resources?.map((r: any, i: number) => (
                  <p key={i} className="text-xs font-mono text-red-300">
                    {r.name}: {r.number} ({r.country})
                  </p>
                ))}
              </div>
            )}

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto space-y-3 mb-4">
              {chatHistory.length === 0 && (
                <div className="text-center py-20 text-zinc-600">
                  <p className="text-lg mb-2">How are you feeling today?</p>
                  <p className="text-xs">I can help with memory, study, reminders, or just listen.</p>
                </div>
              )}
              {chatHistory.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-3 ${
                      msg.role === "user"
                        ? "bg-violet-500/10 border border-violet-500/20 text-zinc-200"
                        : "bg-[#111113] border border-white/[0.06] text-zinc-300"
                    }`}
                  >
                    {msg.mode && (
                      <span className={`inline-block text-[10px] font-mono uppercase px-1.5 py-0.5 rounded border mb-2 ${modeColor(msg.mode)}`}>
                        {msg.mode}
                      </span>
                    )}
                    <p className="text-sm leading-relaxed">{msg.content}</p>
                    {msg.role === "assistant" && response?.mode === msg.mode && response?.reminders && response.reminders.length > 0 && i === chatHistory.length - 1 && (
                      <div className="mt-2 pt-2 border-t border-white/[0.04]">
                        <p className="text-[10px] font-mono text-zinc-500 uppercase mb-1">Active triggers:</p>
                        {response.reminders.map((r, ri) => (
                          <p key={ri} className="text-[10px] text-amber-400/60">⚡ {r}</p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && processMessage()}
                placeholder="Talk to JARVIS... (how are you, remind me to..., teach me about..., I'm feeling stressed)"
                className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-xl px-4 py-3 text-sm text-zinc-300 outline-none focus:border-violet-500/30 placeholder:text-zinc-600 transition-colors"
              />
              <button
                onClick={processMessage}
                disabled={loading || !input.trim()}
                className="px-5 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400 text-sm font-medium hover:bg-violet-500/20 transition-colors disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </div>
        )}

        {/* Memory Tab */}
        {tab === "memory" && (
          <div>
            {memories.length === 0 ? (
              <div className="text-center py-20 text-zinc-600">
                <p className="text-sm">No memories stored yet</p>
                <p className="text-xs text-zinc-600 mt-2">Chat with JARVIS and your memories will accumulate here</p>
              </div>
            ) : (
              <div className="space-y-2">
                {memories.map((m) => (
                  <div key={m.id} className="bg-[#111113] border border-white/[0.06] rounded-xl p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-[10px] font-mono uppercase ${categoryColor(m.category)}`}>
                        {m.category}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono text-zinc-600">
                          importance: {m.importance}/10
                        </span>
                        <span className="text-[10px] font-mono text-zinc-600">
                          {new Date(m.timestamp * 1000).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <p className="text-xs text-zinc-300 leading-relaxed">{m.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Reminders Tab */}
        {tab === "reminders" && (
          <div>
            {reminders.length === 0 ? (
              <div className="text-center py-20 text-zinc-600">
                <p className="text-sm">No active reminders</p>
                <p className="text-xs text-zinc-600 mt-2">Say "remind me to..." and JARVIS will create triggers</p>
              </div>
            ) : (
              <div className="space-y-2">
                {reminders.map((r) => (
                  <div key={r.id} className="bg-[#111113] border border-white/[0.06] rounded-xl p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-zinc-300">{r.trigger_text}</p>
                        <div className="flex items-center gap-2 mt-1">
                          {r.recurring_pattern && (
                            <span className="text-[10px] font-mono text-amber-400/60 bg-amber-400/5 px-1.5 py-0.5 rounded">
                              {r.recurring_pattern}
                            </span>
                          )}
                          <span className="text-[10px] font-mono text-zinc-600">
                            fired {r.fire_count}x
                          </span>
                        </div>
                      </div>
                      <span className={`w-2 h-2 rounded-full ${r.active ? "bg-emerald-400" : "bg-zinc-600"}`} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Study Tab */}
        {tab === "study" && (
          <div>
            {dueCards.length === 0 ? (
              <div className="text-center py-20 text-zinc-600">
                <p className="text-sm">No cards due for review</p>
                <p className="text-xs text-zinc-600 mt-2">Add concepts via chat or the API to build your study deck</p>
              </div>
            ) : (
              <div className="space-y-3">
                {dueCards.map((card) => (
                  <div key={card.id} className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium text-zinc-200">{card.concept}</h3>
                      <span className="text-[10px] font-mono text-zinc-500 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.06]">
                        {card.field_name}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mb-3">{card.summary}</p>
                    <div className="bg-white/[0.02] border border-white/[0.04] rounded-lg p-3">
                      <p className="text-[10px] font-mono text-zinc-500 uppercase mb-1">Quiz:</p>
                      <p className="text-xs text-zinc-300 mb-2">{card.quiz_question}</p>
                      {showAnswer ? (
                        <p className="text-xs text-emerald-400 bg-emerald-500/5 p-2 rounded border border-emerald-500/10">
                          {card.answer_key}
                        </p>
                      ) : (
                        <button
                          onClick={() => setShowAnswer(true)}
                          className="text-[10px] font-mono text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded bg-white/[0.04] hover:bg-white/[0.06] transition-colors"
                        >
                          Show Answer
                        </button>
                      )}
                    </div>
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() => { reviewCard(card.id, 1); setShowAnswer(false); }}
                        className="flex-1 text-[10px] font-mono uppercase px-2 py-1.5 rounded-lg bg-red-500/5 border border-red-500/10 text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        Again
                      </button>
                      <button
                        onClick={() => { reviewCard(card.id, 3); setShowAnswer(false); }}
                        className="flex-1 text-[10px] font-mono uppercase px-2 py-1.5 rounded-lg bg-amber-500/5 border border-amber-500/10 text-amber-400/60 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
                      >
                        Hard
                      </button>
                      <button
                        onClick={() => { reviewCard(card.id, 5); setShowAnswer(false); }}
                        className="flex-1 text-[10px] font-mono uppercase px-2 py-1.5 rounded-lg bg-emerald-500/5 border border-emerald-500/10 text-emerald-400/60 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                      >
                        Easy
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
