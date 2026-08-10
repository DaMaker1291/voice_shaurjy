"""
Trading Dashboard — Interactive HTML portfolio dashboard.

Renders: allocation pie, momentum curves, order tickets, RSI gauges,
sector breakdown, dividend tracker.
"""

import json
import time
import logging
from typing import Dict, List, Optional
from pathlib import Path

log = logging.getLogger("jarvis-trading-dash")


def render_portfolio_dashboard(portfolio: Dict, analysis: List[Dict] = None,
                               rebalance: Dict = None, backtest: Dict = None) -> str:
    """Render a full Trading 212 portfolio dashboard.
    
    portfolio: PortfolioSnapshot.to_dict()
    analysis: list of TickerAnalysis.to_dict()
    rebalance: RebalanceOrder.to_dict()
    backtest: backtest_momentum result dict
    """
    positions = portfolio.get("positions", [])
    cash = portfolio.get("cash_balance", 0)
    total = portfolio.get("total_value", 0)
    invested = sum(p.get("market_value", 0) for p in positions)

    # Allocation data for pie chart
    alloc_labels = [p.get("ticker", "?") for p in positions] + ["Cash"]
    alloc_values = [p.get("market_value", 0) for p in positions] + [cash]
    alloc_colors = _pie_colors(len(positions) + 1)

    # Sector breakdown
    sector_data = {}
    for p in positions:
        sector = p.get("sector", "Unknown")
        sector_data[sector] = sector_data.get(sector, 0) + p.get("market_value", 0)

    # RSI data
    rsi_data = []
    if analysis:
        for a in analysis:
            rsi_data.append({"ticker": a["ticker"], "rsi": a["rsi"], "signal": a["rsi_signal"]})

    # Order tickets
    orders = rebalance.get("orders", []) if rebalance else []

    # Backtest momentum
    momentum_data = []
    if backtest and "all_results" in backtest:
        momentum_data = backtest["all_results"]

    # Build HTML
    sections = []

    # Header stats
    sections.append(f"""
<div class="stats">
  <div class="stat"><div class="stat-value">${total:,.0f}</div><div class="stat-label">Portfolio Value</div></div>
  <div class="stat"><div class="stat-value">${cash:,.0f}</div><div class="stat-label">Cash</div></div>
  <div class="stat"><div class="stat-value">${invested:,.0f}</div><div class="stat-label">Invested</div></div>
  <div class="stat"><div class="stat-value">{len(positions)}</div><div class="stat-label">Positions</div></div>
</div>""")

    # Allocation pie + sector breakdown
    sections.append(f"""
<div class="grid">
  <div class="card">
    <div class="card-header"><h2>Allocation</h2></div>
    <div class="card-body"><canvas id="allocPie" height="280"></canvas></div>
  </div>
  <div class="card">
    <div class="card-header"><h2>Sector Breakdown</h2></div>
    <div class="card-body"><canvas id="sectorPie" height="280"></canvas></div>
  </div>
</div>""")

    # RSI gauges
    if rsi_data:
        rsi_items = ""
        for r in rsi_data[:12]:
            color = "#ef4444" if r["rsi"] > 70 else "#4ade80" if r["rsi"] < 30 else "#60a5fa"
            rsi_items += f"""<div class="rsi-item">
<span class="rsi-ticker">{r['ticker']}</span>
<div class="rsi-bar-bg"><div class="rsi-bar" style="width:{r['rsi']}%;background:{color}"></div></div>
<span class="rsi-val" style="color:{color}">{r['rsi']:.0f}</span>
</div>"""
        sections.append(f"""
<div class="card"><div class="card-header"><h2>RSI Dashboard</h2></div>
<div class="card-body">{rsi_items}</div></div>""")

    # Positions table
    pos_rows = ""
    for p in positions:
        pnl_color = "#4ade80" if p.get("unrealized_pnl", 0) >= 0 else "#ef4444"
        pos_rows += f"""<tr>
<td><strong>{p.get('ticker','')}</strong><br><span class="sub">{p.get('name','')[:30]}</span></td>
<td>{p.get('quantity',0):.2f}</td>
<td>${p.get('current_price',0):.2f}</td>
<td>${p.get('market_value',0):,.0f}</td>
<td style="color:{pnl_color}">{p.get('unrealized_pnl_pct',0):+.1f}%</td>
<td>{p.get('weight',0):.1f}%</td>
<td>{p.get('dividend_yield',0):.1f}%</td>
</tr>"""

    sections.append(f"""
<div class="card"><div class="card-header"><h2>Positions</h2></div>
<div class="card-body"><table>
<thead><tr><th>Ticker</th><th>Qty</th><th>Price</th><th>Value</th><th>P&L</th><th>Weight</th><th>Yield</th></tr></thead>
<tbody>{pos_rows}</tbody>
</table></div></div>""")

    # Order tickets
    if orders:
        order_rows = ""
        for o in orders:
            side_color = "#4ade80" if o.get("side") == "buy" else "#ef4444"
            order_rows += f"""<tr>
<td><strong>{o.get('ticker','')}</strong></td>
<td style="color:{side_color};font-weight:700">{o.get('side','').upper()}</td>
<td>{o.get('quantity',0):.2f}</td>
<td>${o.get('estimated_price',0):.2f}</td>
<td>${o.get('estimated_total',0):,.0f}</td>
<td class="sub">{o.get('reason','')[:50]}</td>
</tr>"""
        total_val = rebalance.get("total_buy_value", 0) - rebalance.get("total_sell_value", 0)
        sections.append(f"""
<div class="card"><div class="card-header"><h2>Staged Orders</h2>
<span class="badge badge-amber">${total_val:,.0f} net</span></div>
<div class="card-body"><table>
<thead><tr><th>Ticker</th><th>Action</th><th>Qty</th><th>Price</th><th>Total</th><th>Reason</th></tr></thead>
<tbody>{order_rows}</tbody>
</table></div></div>""")

    # Momentum chart
    if momentum_data:
        labels = json.dumps([m["ticker"] for m in momentum_data[:10]])
        values = json.dumps([m.get("momentum", 0) for m in momentum_data[:10]])
        sections.append(f"""
<div class="card"><div class="card-header"><h2>Momentum Scores</h2></div>
<div class="card-body"><canvas id="momentumChart" height="200"></canvas></div></div>""")

    body = "\n".join(sections)

    # Chart.js scripts
    scripts = f"""
<script>
(function() {{
  // Allocation Pie
  var allocCtx = document.getElementById('allocPie');
  if (allocCtx) new Chart(allocCtx, {{
    type: 'doughnut',
    data: {{ labels: {json.dumps(alloc_labels)}, datasets: [{{ data: {json.dumps(alloc_values)}, backgroundColor: {json.dumps(alloc_colors)} }}] }},
    options: {{ responsive:true, plugins:{{ legend:{{ position:'right', labels:{{ color:'#94a3b8', font:{{size:11}} }} }} }} }}
  }});

  // Sector Pie
  var sectorLabels = {json.dumps(list(sector_data.keys()))};
  var sectorValues = {json.dumps(list(sector_data.values()))};
  var sectorColors = {json.dumps(_pie_colors(len(sector_data)))};
  var sectorCtx = document.getElementById('sectorPie');
  if (sectorCtx) new Chart(sectorCtx, {{
    type: 'doughnut',
    data: {{ labels: sectorLabels, datasets: [{{ data: sectorValues, backgroundColor: sectorColors }}] }},
    options: {{ responsive:true, plugins:{{ legend:{{ position:'right', labels:{{ color:'#94a3b8', font:{{size:11}} }} }} }} }}
  }});

  // Momentum Chart
  var momCtx = document.getElementById('momentumChart');
  if (momCtx) new Chart(momCtx, {{
    type: 'bar',
    data: {{ labels: {labels}, datasets: [{{ label:'Momentum', data: {values}, backgroundColor: {values}.map(v => v > 0 ? '#4ade8080' : '#ef444480'), borderColor: {values}.map(v => v > 0 ? '#4ade80' : '#ef4444'), borderWidth:1 }}] }},
    options: {{ responsive:true, scales:{{ y:{{ ticks:{{color:'#64748b'}}, grid:{{color:'#1e293b'}} }}, x:{{ ticks:{{color:'#64748b'}}, grid:{{color:'#1e293b'}} }} }}, plugins:{{ legend:{{display:false}} }} }}
  }});
}})();
</script>"""

    return _wrap_html("Trading 212 Portfolio Dashboard", body, scripts)


def render_order_ticket_html(rebalance: Dict) -> str:
    """Render a standalone order ticket view for Laser Gate."""
    orders = rebalance.get("orders", [])
    rows = ""
    for o in orders:
        side_color = "#4ade80" if o.get("side") == "buy" else "#ef4444"
        rows += f"""<tr>
<td><strong>{o.get('ticker','')}</strong></td>
<td style="color:{side_color};font-weight:700">{o.get('side','').upper()}</td>
<td>{o.get('quantity',0):.2f}</td>
<td>${o.get('estimated_price',0):.2f}</td>
<td>${o.get('estimated_total',0):,.0f}</td>
<td>{o.get('reason','')[:60]}</td>
</tr>"""

    total_buy = rebalance.get("total_buy_value", 0)
    total_sell = rebalance.get("total_sell_value", 0)
    net = total_buy - total_sell
    cash_after = rebalance.get("cash_after", 0)

    return _wrap_html("Order Tickets — Laser Gate Approval", f"""
<div class="stats">
  <div class="stat"><div class="stat-value">${total_sell:,.0f}</div><div class="stat-label">Total Sells</div></div>
  <div class="stat"><div class="stat-value">${total_buy:,.0f}</div><div class="stat-label">Total Buys</div></div>
  <div class="stat"><div class="stat-value" style="color:{'#4ade80' if net >= 0 else '#ef4444'}">${net:+,.0f}</div><div class="stat-label">Net</div></div>
  <div class="stat"><div class="stat-value">${cash_after:,.0f}</div><div class="stat-label">Cash After</div></div>
</div>
<div class="card"><div class="card-header"><h2>Order Tickets</h2><span class="badge badge-amber">AWAITING APPROVAL</span></div>
<div class="card-body"><table>
<thead><tr><th>Ticker</th><th>Action</th><th>Quantity</th><th>Price</th><th>Value</th><th>Reason</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<div style="margin-top:16px;text-align:center">
<div class="hold-prompt">Hold <strong>SPACEBAR</strong> for 1.5s to authorize execution</div>
<div class="progress-track"><div class="progress-fill" id="holdProgress"></div></div>
</div>
</div></div>""", _laser_gate_js())


def _laser_gate_js() -> str:
    return """<script>
(function(){
  var holding = false, startTime = 0, progress = document.getElementById('holdProgress');
  document.addEventListener('keydown', function(e){
    if(e.code==='Space' && !holding){ holding=true; startTime=Date.now(); e.preventDefault(); }
  });
  document.addEventListener('keyup', function(e){
    if(e.code==='Space'){ holding=false; if(progress) progress.style.width='0%'; }
  });
  function tick(){
    if(holding){
      var elapsed = Date.now()-startTime;
      var pct = Math.min(100, elapsed/1500*100);
      if(progress) progress.style.width=pct+'%';
      if(pct>=100){ /* Fire orders */ holding=false; }
    }
    requestAnimationFrame(tick);
  }
  tick();
})();
</script>"""


def _wrap_html(title: str, body: str, extra_scripts: str = "") -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0a0e1a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;}}
.header{{background:linear-gradient(135deg,#0f172a,#1e293b);padding:20px 28px;border-bottom:1px solid #1e293b;}}
.header h1{{font-size:1.3em;font-weight:600;}} .header .sub{{color:#94a3b8;font-size:0.85em;margin-top:4px;}}
.stats{{display:flex;gap:14px;padding:16px 20px;}}
.stat{{flex:1;background:#1e293b;border-radius:10px;padding:14px;text-align:center;}}
.stat .value{{font-size:1.5em;font-weight:700;color:#60a5fa;}} .stat .label{{font-size:0.75em;color:#64748b;margin-top:2px;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:14px 20px;}}
.card{{background:#111827;border:1px solid #1e293b;border-radius:10px;overflow:hidden;}}
.card-header{{padding:12px 16px;border-bottom:1px solid #1e293b;display:flex;align-items:center;justify-content:space-between;}}
.card-header h2{{font-size:0.9em;font-weight:600;color:#f1f5f9;}}
.card-body{{padding:16px;}}
table{{width:100%;border-collapse:collapse;font-size:0.82em;}}
th{{text-align:left;padding:8px 10px;background:#0f172a;color:#94a3b8;font-weight:600;border-bottom:1px solid #1e293b;}}
td{{padding:8px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1;}}
tr:hover td{{background:#1e293b;}}
.sub{{color:#64748b;font-size:0.8em;}}
.badge{{font-size:0.7em;padding:3px 8px;border-radius:9999px;font-weight:600;}}
.badge-amber{{background:#713f12;color:#fbbf24;}}
.rsi-item{{display:flex;align-items:center;gap:8px;padding:4px 0;}}
.rsi-ticker{{width:50px;font-weight:600;font-size:0.82em;}}
.rsi-bar-bg{{flex:1;height:6px;background:#1e293b;border-radius:3px;overflow:hidden;}}
.rsi-bar{{height:100%;border-radius:3px;transition:width 0.3s;}}
.rsi-val{{width:35px;text-align:right;font-size:0.8em;font-weight:600;}}
.hold-prompt{{font-size:1.1em;color:#fbbf24;margin:12px 0 8px;animation:pulse 1.5s infinite;}}
.progress-track{{width:200px;height:6px;background:#1e293b;border-radius:3px;margin:0 auto;overflow:hidden;}}
.progress-fill{{height:100%;background:linear-gradient(90deg,#f59e0b,#ef4444);width:0%;transition:width 0.1s;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:0.6;}}}}
</style></head><body>
<div class="header"><h1>{title}</h1><div class="sub">Generated {time.strftime('%Y-%m-%d %H:%M')}</div></div>
{body}
{extra_scripts}
</body></html>"""


def _pie_colors(n: int) -> List[str]:
    palette = ["#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#ec4899",
               "#06b6d4","#84cc16","#f97316","#6366f1","#14b8a6","#e879f9",
               "#22d3ee","#a3e635","#fb923c","#818cf8"]
    return [palette[i % len(palette)] for i in range(n)]


def save_dashboard(html: str, filename: str = "trading_dashboard.html",
                   output_dir: str = None) -> str:
    if output_dir is None:
        output_dir = str(Path.home() / "Desktop")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = Path(output_dir) / filename
    filepath.write_text(html, encoding="utf-8")
    return str(filepath)
