"use client";
import { useState, useEffect, useCallback } from "react";
import { getTradingPortfolio, getTradingHistory, searchStocks, tradingBuy, tradingSell,
  tradingAnalyze, getTradingStrategies, runTradingStrategy, startAutoTrading, stopAutoTrading } from "@/lib/api";
import type { TradingPortfolio, TradeHistoryEntry, StockAnalysis, TradingStrategy } from "@/lib/types";
import { SkeletonCard } from "@/components/LoadingSkeleton";

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
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-xl font-bold text-purple-400">Paper Trading</h1><p className="text-xs text-gray-500 mt-0.5">Simulated stock trading with analysis & strategies</p></div>
        <button onClick={handleAutoToggle} className={`px-4 py-1.5 text-xs rounded-lg ${autoTrading ? "bg-red-900/30 text-red-400 border border-red-800/30" : "bg-green-900/30 text-green-400 border border-green-800/30"}`}>
          {autoTrading ? "Stop Auto" : "Start Auto"}
        </button>
      </div>
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4"><SkeletonCard lines={4} /><SkeletonCard lines={4} /></div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5">
              <p className="text-[10px] font-mono text-gray-500 uppercase">Portfolio Value</p>
              <p className="text-2xl font-bold text-green-400">${(portfolio?.total_value || 0).toLocaleString()}</p>
              <p className="text-xs text-gray-500 mt-1">Cash: ${(portfolio?.cash || 0).toLocaleString()}</p>
            </div>
            <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5">
              <p className="text-[10px] font-mono text-gray-500 uppercase">Holdings</p>
              <p className="text-2xl font-bold text-gray-200">{portfolio?.holdings?.length || 0}</p>
              <p className="text-xs text-gray-500 mt-1">positions</p>
            </div>
            <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5">
              <p className="text-[10px] font-mono text-gray-500 uppercase">Trades</p>
              <p className="text-2xl font-bold text-gray-200">{history.length}</p>
              <p className="text-xs text-gray-500 mt-1">all time</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h2 className="text-sm font-mono text-gray-400 uppercase">Trade</h2>
              <div className="flex gap-2">
                <input value={searchQ} onChange={e => handleSearch(e.target.value)} placeholder="Search stocks..." className="flex-1 bg-gray-800/50 border border-gray-700/50 rounded px-3 py-2 text-xs text-gray-200" />
              </div>
              {searchResults.length > 0 && (
                <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-3 space-y-1">
                  {searchResults.map((r, i) => (
                    <button key={i} onClick={() => { setBuySymbol(r.symbol || r); handleAnalyze(r.symbol || r); }} className="w-full text-left px-3 py-2 text-xs text-gray-300 hover:bg-gray-800/40 rounded-lg">
                      {r.symbol || r} {r.name ? `— ${r.name}` : ""}
                    </button>
                  ))}
                </div>
              )}
              <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5 space-y-3">
                <div className="flex gap-2">
                  <input value={buySymbol} onChange={e => setBuySymbol(e.target.value.toUpperCase())} placeholder="Symbol" className="flex-1 bg-gray-800/50 border border-gray-700/50 rounded px-3 py-1.5 text-xs text-gray-200 font-mono uppercase" />
                  <input value={buyShares} onChange={e => setBuyShares(e.target.value)} type="number" placeholder="Shares" className="w-24 bg-gray-800/50 border border-gray-700/50 rounded px-3 py-1.5 text-xs text-gray-200" />
                </div>
                <div className="flex gap-2">
                  <button onClick={handleBuy} className="flex-1 px-3 py-1.5 bg-green-600/20 hover:bg-green-600/30 border border-green-700/30 text-green-400 text-xs rounded-lg">Buy</button>
                </div>
              </div>
              {analysis && (
                <div className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-5 space-y-2">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm text-gray-200">{analysis.symbol}</h3>
                    <span className={`text-sm font-mono ${analysis.change_percent >= 0 ? "text-green-400" : "text-red-400"}`}>
                      ${analysis.current_price} ({analysis.change_percent >= 0 ? "+" : ""}{analysis.change_percent?.toFixed(2)}%)
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500">Recommendation: <span className="text-purple-400">{analysis.recommendation}</span></p>
                </div>
              )}
            </div>
            <div className="space-y-4">
              <h2 className="text-sm font-mono text-gray-400 uppercase">Holdings</h2>
              {(portfolio?.holdings?.length ?? 0) > 0 ? (
                <div className="space-y-2">
                  {portfolio!.holdings!.map((h, i) => (
                    <div key={i} className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-4 flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-200">{h.symbol}</p>
                        <p className="text-[10px] text-gray-500">{h.shares} shares @ ${h.avg_price}</p>
                      </div>
                      <div className="text-right">
                        <p className={`text-sm font-mono ${h.gain_loss_percent >= 0 ? "text-green-400" : "text-red-400"}`}>
                          ${h.total_value} ({h.gain_loss_percent >= 0 ? "+" : ""}{h.gain_loss_percent?.toFixed(1)}%)
                        </p>
                        <button onClick={() => handleSell(h.symbol)} className="text-[10px] text-red-400 hover:text-red-300">Sell 1</button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-8 text-gray-600 text-sm">No holdings.</p>
              )}
              <h2 className="text-sm font-mono text-gray-400 uppercase mt-6">Strategies</h2>
              {strategies.length > 0 ? (
                <div className="space-y-2">
                  {strategies.map((s, i) => (
                    <div key={i} className="bg-gray-900/40 border border-gray-800/30 rounded-xl p-4 flex items-center justify-between">
                      <div>
                        <p className="text-xs text-gray-200">{s.name}</p>
                        <p className="text-[10px] text-gray-500">Win rate: {s.performance?.win_rate || 0}%</p>
                      </div>
                      <button onClick={() => handleRunStrategy(s.id)} className="px-3 py-1 text-xs bg-purple-600/20 hover:bg-purple-600/30 border border-purple-700/30 text-purple-400 rounded-lg">Run</button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-8 text-gray-600 text-sm">No strategies configured.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
