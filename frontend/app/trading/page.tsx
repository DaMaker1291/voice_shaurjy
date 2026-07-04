"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getTradingPortfolio, getTradingHistory, searchStocks, tradingBuy, tradingSell,
  tradingAnalyze, getTradingStrategies, runTradingStrategy, startAutoTrading, stopAutoTrading,
} from "@/lib/api";
import type { TradingPortfolio, TradeHistoryEntry, StockAnalysis, TradingStrategy } from "@/lib/types";
import Navbar from "@/components/Navbar";

export default function TradingPage() {
  const [portfolio, setPortfolio] = useState<TradingPortfolio | null>(null);
  const [history, setHistory] = useState<TradeHistoryEntry[]>([]);
  const [analysis, setAnalysis] = useState<StockAnalysis | null>(null);
  const [strategies, setStrategies] = useState<TradingStrategy[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [buySymbol, setBuySymbol] = useState("");
  const [buyShares, setBuyShares] = useState("");
  const [loading, setLoading] = useState(true);
  const [autoTrading, setAutoTrading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [p, h, s] = await Promise.allSettled([
      getTradingPortfolio(), getTradingHistory(), getTradingStrategies(),
    ]);
    if (p.status === "fulfilled") setPortfolio(p.value);
    if (h.status === "fulfilled") setHistory(h.value?.trades || h.value || []);
    if (s.status === "fulfilled") setStrategies(s.value?.strategies || s.value || []);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSearch = useCallback(async (q: string) => {
    if (!q) { setSearchResults([]); return; }
    setSearchQ(q);
    const r = await searchStocks(q);
    setSearchResults(r?.results || r || []);
  }, []);

  const handleAnalyze = useCallback(async (symbol: string) => {
    const a = await tradingAnalyze(symbol);
    setAnalysis(a);
  }, []);

  const handleBuy = useCallback(async () => {
    if (!buySymbol || !buyShares) return;
    await tradingBuy(buySymbol, parseInt(buyShares));
    setBuySymbol(""); setBuyShares("");
    load();
  }, [buySymbol, buyShares, load]);

  const handleSell = useCallback(async (symbol: string) => {
    await tradingSell(symbol, 1);
    load();
  }, [load]);

  const handleRunStrategy = useCallback(async (id: string) => {
    await runTradingStrategy(id);
  }, []);

  const handleAutoToggle = useCallback(async () => {
    if (autoTrading) {
      await stopAutoTrading();
    } else {
      await startAutoTrading(60);
    }
    setAutoTrading(!autoTrading);
  }, [autoTrading]);

  return (
    <div className="flex flex-col h-screen bg-transparent">
      <Navbar />
      <main className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto w-full space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Paper Trading</h1>
            <p className="text-sm text-zinc-500 mt-0.5">Simulated stock trading with analysis & strategies</p>
          </div>
          <button
            onClick={handleAutoToggle}
            className={`text-sm font-medium px-4 py-2 rounded-lg border transition-colors duration-150 ${
              autoTrading
                ? "bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/20"
                : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20"
            }`}
          >
            {autoTrading ? "Stop Auto" : "Start Auto"}
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2].map(i => (
              <div key={i} className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 animate-pulse">
                <div className="h-3 bg-white/[0.06] rounded w-1/3 mb-3" />
                <div className="h-6 bg-white/[0.04] rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                <p className="text-xs font-mono text-zinc-500 uppercase">Portfolio Value</p>
                <p className="text-2xl font-bold text-emerald-400">${(portfolio?.total_value || 0).toLocaleString()}</p>
                <p className="text-xs text-zinc-500 mt-1">Cash: ${(portfolio?.cash || 0).toLocaleString()}</p>
              </div>
              <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                <p className="text-xs font-mono text-zinc-500 uppercase">Holdings</p>
                <p className="text-2xl font-bold text-zinc-200">{portfolio?.holdings?.length || 0}</p>
                <p className="text-xs text-zinc-500 mt-1">positions</p>
              </div>
              <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5">
                <p className="text-xs font-mono text-zinc-500 uppercase">Trades</p>
                <p className="text-2xl font-bold text-zinc-200">{history.length}</p>
                <p className="text-xs text-zinc-500 mt-1">all time</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Trade</h2>
                <input
                  value={searchQ}
                  onChange={e => handleSearch(e.target.value)}
                  placeholder="Search stocks..."
                  className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                />
                {searchResults.length > 0 && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-2 space-y-0.5">
                    {searchResults.map((r, i) => (
                      <button
                        key={i}
                        onClick={() => { setBuySymbol(r.symbol || r); handleAnalyze(r.symbol || r); }}
                        className="w-full text-left px-3 py-2 text-sm text-zinc-300 hover:bg-white/[0.04] rounded-lg transition-colors duration-150"
                      >
                        {r.symbol || r} {r.name ? `— ${r.name}` : ""}
                      </button>
                    ))}
                  </div>
                )}
                <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-3">
                  <div className="flex gap-2">
                    <input
                      value={buySymbol}
                      onChange={e => setBuySymbol(e.target.value.toUpperCase())}
                      placeholder="Symbol"
                      className="flex-1 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono uppercase placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                    />
                    <input
                      value={buyShares}
                      onChange={e => setBuyShares(e.target.value)}
                      type="number"
                      placeholder="Shares"
                      className="w-24 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-violet-500/30 focus:ring-2 focus:ring-violet-500/10 transition-colors duration-150"
                    />
                  </div>
                  <button onClick={handleBuy} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-3 py-2 rounded-lg transition-colors duration-150">
                    Buy
                  </button>
                </div>
                {analysis && (
                  <div className="bg-[#111113] border border-white/[0.06] rounded-xl p-5 space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium text-zinc-200">{analysis.symbol}</h3>
                      <span className={`text-sm font-mono ${analysis.change_percent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        ${analysis.current_price} ({analysis.change_percent >= 0 ? "+" : ""}{analysis.change_percent?.toFixed(2)}%)
                      </span>
                    </div>
                    <p className="text-xs text-zinc-500">
                      Recommendation: <span className="text-violet-400">{analysis.recommendation}</span>
                    </p>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-zinc-100">Holdings</h2>
                {(portfolio?.holdings?.length ?? 0) > 0 ? (
                  <div className="space-y-2">
                    {portfolio!.holdings!.map((h, i) => (
                      <div
                        key={i}
                        className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex items-center justify-between animate-fade-in"
                        style={{ animationDelay: `${i * 40}ms` }}
                      >
                        <div>
                          <p className="text-sm text-zinc-200">{h.symbol}</p>
                          <p className="text-xs text-zinc-500">{h.shares} shares @ ${h.avg_price}</p>
                        </div>
                        <div className="text-right">
                          <p className={`text-sm font-mono ${h.gain_loss_percent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            ${h.total_value} ({h.gain_loss_percent >= 0 ? "+" : ""}{h.gain_loss_percent?.toFixed(1)}%)
                          </p>
                          <button onClick={() => handleSell(h.symbol)} className="text-xs text-red-400 hover:text-red-300 transition-colors duration-150">
                            Sell 1
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-zinc-600 text-sm">No holdings.</div>
                )}

                <h2 className="text-lg font-semibold text-zinc-100 mt-6">Strategies</h2>
                {strategies.length > 0 ? (
                  <div className="space-y-2">
                    {strategies.map((s, i) => (
                      <div key={i} className="bg-[#111113] border border-white/[0.06] rounded-xl p-4 flex items-center justify-between">
                        <div>
                          <p className="text-sm text-zinc-200">{s.name}</p>
                          <p className="text-xs text-zinc-500">Win rate: {s.performance?.win_rate || 0}%</p>
                        </div>
                        <button onClick={() => handleRunStrategy(s.id)} className="bg-white/[0.04] hover:bg-white/[0.06] text-zinc-400 hover:text-zinc-200 text-sm px-4 py-2 rounded-lg border border-white/[0.06] transition-colors duration-150">
                          Run
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-zinc-600 text-sm">No strategies configured.</div>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
