"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getLifeDashboard, getLifeFinance, getLifeBudgets, getLifeSubscriptions, getLifeHealthSummary,
  getLifePlanner, getLifeHabits, getLifeGoals, getLifeJournal, getLifeMoodTrend,
  addLifeTransaction, addLifeTask,
} from "@/lib/api";
import { BASE } from "@/lib/api";
import type {
  LifeDashboard, LifeFinance, LifeBudget, LifeSubscription, LifeHealthSummary,
  LifeTask, LifeHabit, LifeGoal, LifeJournalEntry,
} from "@/lib/types";
import Navbar from "@/components/Navbar";

type Tab = "dashboard" | "finance" | "health" | "planner" | "habits" | "journal";

export default function LifePage() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [dash, setDash] = useState<LifeDashboard | null>(null);
  const [finance, setFinance] = useState<LifeFinance | null>(null);
  const [budgets, setBudgets] = useState<LifeBudget[]>([]);
  const [subscriptions, setSubscriptions] = useState<{ subscriptions?: LifeSubscription[]; monthly_cost: number } | null>(null);
  const [health, setHealth] = useState<LifeHealthSummary | null>(null);
  const [planner, setPlanner] = useState<{ pending: LifeTask[]; done_today: number; tasks_pending: number } | null>(null);
  const [habits, setHabits] = useState<LifeHabit[]>([]);
  const [goals, setGoals] = useState<any[]>([]);
  const [journal, setJournal] = useState<LifeJournalEntry[]>([]);
  const [mood, setMood] = useState<{ dominant_mood: string; average_energy: number; trend: string } | null>(null);
  const [briefing, setBriefing] = useState("");
  const [loading, setLoading] = useState(true);
  const [showAddTxn, setShowAddTxn] = useState(false);
  const [txnAmount, setTxnAmount] = useState("");
  const [txnCat, setTxnCat] = useState("general");
  const [txnDesc, setTxnDesc] = useState("");
  const [txnType, setTxnType] = useState("expense");
  const [showAddTask, setShowAddTask] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskPriority, setTaskPriority] = useState(3);
  const [journalEntry, setJournalEntry] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [d, f, b, s, h, p, hab, g, j, m, br] = await Promise.allSettled([
        getLifeDashboard(), getLifeFinance(), getLifeBudgets(), getLifeSubscriptions(),
        getLifeHealthSummary(), getLifePlanner(), getLifeHabits(), getLifeGoals(),
        getLifeJournal(), getLifeMoodTrend(), getLifeDashboard(),
      ]);
      if (d.status === "fulfilled") setDash(d.value);
      if (f.status === "fulfilled") setFinance(f.value);
      if (b.status === "fulfilled") setBudgets(b.value || []);
      if (s.status === "fulfilled") setSubscriptions(s.value);
      if (h.status === "fulfilled") setHealth(h.value);
      if (p.status === "fulfilled") setPlanner(p.value);
      if (hab.status === "fulfilled") setHabits(hab.value || []);
      if (g.status === "fulfilled") setGoals(Array.isArray(g.value) ? g.value : g.value?.goals || []);
      if (j.status === "fulfilled") setJournal(Array.isArray(j.value) ? j.value : j.value?.entries || []);
      if (m.status === "fulfilled") setMood(m.value);
      if (br.status === "fulfilled") setBriefing(br.value?.briefing || "");
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleAddTxn = useCallback(async () => {
    const amount = parseFloat(txnAmount);
    if (!amount) return;
    await addLifeTransaction(amount, txnCat, txnDesc, txnType);
    setShowAddTxn(false); setTxnAmount(""); setTxnDesc("");
    const f = await getLifeFinance(); setFinance(f);
  }, [txnAmount, txnCat, txnDesc, txnType]);

  const handleAddTask = useCallback(async () => {
    if (!taskTitle.trim()) return;
    await addLifeTask(taskTitle, taskPriority);
    setShowAddTask(false); setTaskTitle("");
    const p = await getLifePlanner(); setPlanner(p);
  }, [taskTitle, taskPriority]);

  const handleJournalSubmit = useCallback(async () => {
    if (!journalEntry.trim()) return;
    try {
      await fetch(`${BASE}/api/life/journal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: journalEntry }),
      });
    } catch {}
    setJournalEntry("");
    loadData();
  }, [journalEntry, loadData]);

  const tabs: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Overview" },
    { key: "finance", label: "Finance" },
    { key: "health", label: "Health" },
    { key: "planner", label: "Planner" },
    { key: "habits", label: "Habits" },
    { key: "journal", label: "Journal" },
  ];

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Life OS</h1>
            <p className="text-sm text-zinc-500 mt-0.5">Complete life operating system — finance, health, tasks, goals</p>
          </div>
          {(finance || health) && (
            <div className="text-right text-xs text-zinc-500 font-mono">
              <div>${finance?.balance || 0}</div>
              <div>{health?.workouts_this_week || 0} workouts</div>
            </div>
          )}
        </div>

        <div className="flex border-b border-white/[0.06] overflow-x-auto">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors duration-150 whitespace-nowrap ${
                activeTab === t.key
                  ? "text-zinc-100 border-violet-500"
                  : "text-zinc-500 hover:text-zinc-300 border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 animate-pulse">
                <div className="h-3 bg-white/[0.06] rounded w-1/2 mb-2" />
                <div className="h-5 bg-white/[0.04] rounded w-3/4" />
              </div>
            ))}
          </div>
        ) : (
          <>
            {activeTab === "dashboard" && (
              <div className="space-y-4">
                {briefing && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                    <p className="text-xs font-mono text-violet-400/60 uppercase tracking-wider mb-2">Morning Briefing</p>
                    <p className="text-sm text-zinc-300 leading-relaxed">{briefing}</p>
                  </div>
                )}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatCard title="Balance" value={`$${finance?.balance || 0}`} sub={`${finance?.transaction_count || 0} transactions`} />
                  <StatCard title="Health" value={`${health?.workouts_today || 0} workouts`} sub={`${health?.water_today_ml || 0}ml water`} />
                  <StatCard title="Tasks" value={`${planner?.tasks_pending || 0} pending`} sub={`${planner?.done_today || 0} done today`} />
                  <StatCard title="Mood" value={mood?.dominant_mood || "—"} sub={`Energy ${mood?.average_energy || "—"}/5`} />
                </div>
                {health?.sleep_last && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-4">
                    <p className="text-sm text-zinc-400">
                      Last sleep: <span className="text-zinc-200">{health.sleep_last.hours}h</span> — Quality:{" "}
                      <span className="text-zinc-200">{health.sleep_last.quality}/5</span>
                    </p>
                  </div>
                )}
              </div>
            )}

            {activeTab === "finance" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-zinc-100">Finance</h2>
                  <button onClick={() => setShowAddTxn(!showAddTxn)} className="text-sm text-violet-400 hover:text-violet-300 transition-colors duration-150">
                    + Add Transaction
                  </button>
                </div>
                {showAddTxn && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3 animate-fade-in">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-zinc-500 font-mono">Amount</label>
                        <input
                          type="number"
                          value={txnAmount}
                          onChange={e => setTxnAmount(e.target.value)}
                          className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 mt-1 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-zinc-500 font-mono">Category</label>
                        <select
                          value={txnCat}
                          onChange={e => setTxnCat(e.target.value)}
                          className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 mt-1 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                        >
                          <option>food</option>
                          <option>transport</option>
                          <option>shopping</option>
                          <option>bills</option>
                          <option>entertainment</option>
                          <option>health</option>
                          <option>education</option>
                          <option>general</option>
                        </select>
                      </div>
                      <div className="sm:col-span-2">
                        <label className="text-xs text-zinc-500 font-mono">Description</label>
                        <input
                          value={txnDesc}
                          onChange={e => setTxnDesc(e.target.value)}
                          className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 mt-1 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-zinc-500 font-mono">Type</label>
                        <div className="flex gap-2 mt-1">
                          <button
                            onClick={() => setTxnType("expense")}
                            className={`px-3 py-1.5 text-sm rounded-lg transition-colors duration-150 ${txnType === "expense" ? "bg-red-500/20 text-red-400 border border-red-500/30" : "bg-white/[0.03] text-zinc-500 border border-white/[0.06]"}`}
                          >
                            Expense
                          </button>
                          <button
                            onClick={() => setTxnType("income")}
                            className={`px-3 py-1.5 text-sm rounded-lg transition-colors duration-150 ${txnType === "income" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "bg-white/[0.03] text-zinc-500 border border-white/[0.06]"}`}
                          >
                            Income
                          </button>
                        </div>
                      </div>
                    </div>
                    <button onClick={handleAddTxn} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
                      Save
                    </button>
                  </div>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                    <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-1">Balance</p>
                    <p className="text-2xl font-bold text-emerald-400">${finance?.balance || 0}</p>
                  </div>
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                    <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-1">Income</p>
                    <p className="text-2xl font-bold text-zinc-200">${finance?.income || 0}</p>
                  </div>
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                    <p className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-1">Expenses</p>
                    <p className="text-2xl font-bold text-red-400">${finance?.expenses || 0}</p>
                  </div>
                </div>
                {(subscriptions?.subscriptions?.length ?? 0) > 0 && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                    <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Subscriptions</h3>
                    <div className="space-y-2">
                      {subscriptions!.subscriptions!.map((s: LifeSubscription, i: number) => (
                        <div key={i} className="flex items-center justify-between text-sm">
                          <span className="text-zinc-300">{s.name}</span>
                          <span className="text-zinc-500 font-mono">${s.cost}/{s.billing_cycle === "yearly" ? "yr" : "mo"}</span>
                        </div>
                      ))}
                      <p className="text-xs text-zinc-500 font-mono mt-2">Monthly total: ${subscriptions!.monthly_cost}</p>
                    </div>
                  </div>
                )}
                {budgets.length > 0 && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                    <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Budgets</h3>
                    {budgets.map((b: LifeBudget, i: number) => (
                      <div key={i} className="flex items-center justify-between py-1.5 text-sm border-b border-white/[0.04] last:border-0">
                        <span className="text-zinc-300">{b.category}</span>
                        <span className={`font-mono ${b.status === "over" ? "text-red-400" : b.status === "warning" ? "text-amber-400" : "text-zinc-500"}`}>
                          ${b.spent} / ${b.budget} ({b.pct_used}%)
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "health" && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Health & Fitness</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <StatCard title="Workouts Today" value={health?.workouts_today?.toString() || "0"} sub="" />
                  <StatCard title="Calories" value={health?.calories_today?.toString() || "0"} sub="today" />
                  <StatCard title="Water" value={`${health?.water_today_ml || 0}ml`} sub="today" />
                  <StatCard title="Streak" value={`${health?.streak_days || 0} days`} sub="workout streak" />
                </div>
                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                  <h3 className="text-xs font-mono text-zinc-500 mb-3">Quick Log</h3>
                  <p className="text-sm text-zinc-500">Use the chat to log workouts, meals, sleep, and water naturally.</p>
                </div>
              </div>
            )}

            {activeTab === "planner" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-zinc-100">Daily Planner</h2>
                  <button onClick={() => setShowAddTask(!showAddTask)} className="text-sm text-violet-400 hover:text-violet-300 transition-colors duration-150">
                    + Add Task
                  </button>
                </div>
                {showAddTask && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3 animate-fade-in">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="sm:col-span-2">
                        <label className="text-xs text-zinc-500 font-mono">Task</label>
                        <input
                          value={taskTitle}
                          onChange={e => setTaskTitle(e.target.value)}
                          className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 mt-1 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-zinc-500 font-mono">Priority (1-5)</label>
                        <input
                          type="number"
                          min={1}
                          max={5}
                          value={taskPriority}
                          onChange={e => setTaskPriority(Number(e.target.value))}
                          className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 mt-1 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                        />
                      </div>
                    </div>
                    <button onClick={handleAddTask} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
                      Add Task
                    </button>
                  </div>
                )}
                {(planner?.pending?.length ?? 0) > 0 ? (
                  <div className="space-y-2">
                    {planner!.pending!.map((t: any, i: number) => (
                      <div
                        key={i}
                        className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex items-center justify-between animate-fade-in"
                        style={{ animationDelay: `${i * 40}ms` }}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${t.priority >= 4 ? "bg-red-400" : t.priority >= 3 ? "bg-amber-400" : "bg-zinc-600"}`} />
                          <span className="text-sm text-zinc-200">{t.title}</span>
                        </div>
                        <span className="text-xs text-zinc-500 font-mono">P{t.priority}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-16 text-zinc-600 text-sm">No pending tasks.</div>
                )}
                {(planner?.done_today ?? 0) > 0 && (
                  <p className="text-xs text-zinc-500 font-mono">{planner!.done_today} tasks completed today</p>
                )}
              </div>
            )}

            {activeTab === "habits" && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Habits & Goals</h2>
                {habits.length > 0 ? (
                  <div className="space-y-2">
                    {habits.map((h: LifeHabit, i: number) => (
                      <div
                        key={i}
                        className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex items-center justify-between animate-fade-in"
                        style={{ animationDelay: `${i * 40}ms` }}
                      >
                        <div>
                          <p className="text-sm text-zinc-200">{h.name}</p>
                          <p className="text-xs text-zinc-500">{h.streak}-day streak (best: {h.longest_streak})</p>
                        </div>
                        <span className={`px-2 py-0.5 text-xs rounded-full ${h.done_today ? "bg-emerald-500/20 text-emerald-400" : "bg-white/[0.03] text-zinc-500 border border-white/[0.06]"}`}>
                          {h.done_today ? "Done" : "Pending"}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-16 text-zinc-600 text-sm">No habits tracked.</div>
                )}
                {goals.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-sm font-medium text-zinc-300 mb-3">Goals</h3>
                    {goals.map((g: any, i: number) => (
                      <div key={i} className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 mb-2">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-sm text-zinc-200">{g.title || g.goal}</span>
                          <span className="text-xs text-zinc-500 font-mono">{g.progress}%</span>
                        </div>
                        <div className="w-full h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                          <div className="h-full rounded-full bg-violet-500 transition-all duration-300" style={{ width: `${g.progress}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "journal" && (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Journal & Mood</h2>
                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3">
                  <textarea
                    value={journalEntry}
                    onChange={e => setJournalEntry(e.target.value)}
                    placeholder="Write a journal entry..."
                    className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 min-h-[100px] outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150 resize-none"
                  />
                  <button onClick={handleJournalSubmit} className="bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors duration-150">
                    Save Entry
                  </button>
                </div>
                {mood && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                    <h3 className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-3">Mood Trend</h3>
                    <div className="grid grid-cols-3 gap-3">
                      <StatCard title="Dominant" value={mood.dominant_mood || "—"} sub="" />
                      <StatCard title="Energy" value={`${mood.average_energy || "—"}/5`} sub="" />
                      <StatCard title="Trend" value={mood.trend || "stable"} sub="" />
                    </div>
                  </div>
                )}
                {journal.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium text-zinc-300 mb-2">Recent Entries</h3>
                    {journal.map((e: LifeJournalEntry, i: number) => (
                      <div
                        key={i}
                        className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 animate-fade-in"
                        style={{ animationDelay: `${i * 40}ms` }}
                      >
                        <p className="text-sm text-zinc-300">{e.content}</p>
                        <p className="text-xs text-zinc-500 mt-1 font-mono">{new Date(e.time || e.date || "").toLocaleString()}</p>
                      </div>
                    ))}
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
