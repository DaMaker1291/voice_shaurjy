"""
Rebalancer — Portfolio rebalancing logic and order ticket generation.

Takes current positions + target allocations and generates optimal
order tickets with minimal trades.
"""

import logging
from typing import Dict, List, Optional, Tuple
from portfolio_models import Position, OrderTicket, RebalanceOrder, PortfolioSnapshot

log = logging.getLogger("jarvis-rebalancer")


class PortfolioRebalancer:
    """Generate rebalancing order tickets from current vs target allocation."""

    def rebalance(self, portfolio: PortfolioSnapshot, target_weights: Dict[str, float],
                  available_cash: float = None, min_trade_pct: float = 0.5) -> RebalanceOrder:
        """Generate rebalance orders.
        
        Args:
            portfolio: Current portfolio state
            target_weights: {ticker: target_weight_pct} (e.g., {"AAPL": 30, "MSFT": 25})
            available_cash: Cash to deploy (defaults to portfolio cash balance)
            min_trade_pct: Minimum % change to trigger a trade
        
        Returns:
            RebalanceOrder with staged order tickets
        """
        cash = available_cash if available_cash is not None else portfolio.cash_balance
        total_value = portfolio.total_value

        if total_value <= 0:
            return RebalanceOrder(reason="Portfolio has no value")

        # Calculate current weights
        current_weights = {}
        for pos in portfolio.positions:
            current_weights[pos.ticker] = (pos.market_value / total_value) * 100

        # Find what to buy and sell
        orders = []
        sells = []
        buys = []

        # First: identify sells (overweight positions)
        for ticker, target_w in target_weights.items():
            current_w = current_weights.get(ticker, 0)
            diff = current_w - target_w
            if diff > min_trade_pct:
                # Need to sell
                pos = next((p for p in portfolio.positions if p.ticker == ticker), None)
                if pos and pos.quantity > 0:
                    sell_value = (diff / 100) * total_value
                    sell_qty = sell_value / pos.current_price if pos.current_price else 0
                    sell_qty = min(sell_qty, pos.quantity)
                    if sell_qty > 0:
                        sells.append(OrderTicket(
                            ticker=ticker,
                            side="sell",
                            quantity=round(sell_qty, 4),
                            estimated_price=pos.current_price,
                            estimated_total=round(sell_qty * pos.current_price, 2),
                            reason=f"Overweight: {current_w:.1f}% -> {target_w:.1f}%",
                        ))

        # Second: identify buys (underweight positions)
        for ticker, target_w in target_weights.items():
            current_w = current_weights.get(ticker, 0)
            diff = target_w - current_w
            if diff > min_trade_pct:
                buy_value = (diff / 100) * total_value
                # Use sell proceeds + available cash
                available = cash + sum(s.estimated_total for s in sells)
                buy_value = min(buy_value, available)
                if buy_value > 0:
                    # Estimate price from existing position or fetch
                    price = 0
                    pos = next((p for p in portfolio.positions if p.ticker == ticker), None)
                    if pos:
                        price = pos.current_price
                    if price > 0:
                        buy_qty = buy_value / price
                        buys.append(OrderTicket(
                            ticker=ticker,
                            side="buy",
                            quantity=round(buy_qty, 4),
                            estimated_price=price,
                            estimated_total=round(buy_value, 2),
                            reason=f"Underweight: {current_w:.1f}% -> {target_w:.1f}%",
                        ))

        # Third: handle positions not in target (should sell completely)
        for pos in portfolio.positions:
            if pos.ticker not in target_weights and pos.quantity > 0:
                sells.append(OrderTicket(
                    ticker=pos.ticker,
                    side="sell",
                    quantity=pos.quantity,
                    estimated_price=pos.current_price,
                    estimated_total=round(pos.quantity * pos.current_price, 2),
                    reason=f"Not in target allocation — full exit",
                ))

        orders = sells + buys
        total_sell = sum(o.estimated_total for o in sells)
        total_buy = sum(o.estimated_total for o in buys)

        return RebalanceOrder(
            orders=orders,
            total_buy_value=total_buy,
            total_sell_value=total_sell,
            net_value=total_buy - total_sell,
            cash_before=cash,
            cash_after=cash + total_sell - total_buy,
            reason=f"Sell {len(sells)} positions (${total_sell:,.2f}), buy {len(buys)} positions (${total_buy:,.2f})",
        )

    def momentum_rebalance(self, portfolio: PortfolioSnapshot,
                           analysis_results: List[Dict], max_positions: int = 15,
                           min_confidence: float = 0.4) -> RebalanceOrder:
        """Rebalance based on momentum/technical analysis signals.
        
        analysis_results: list of TickerAnalysis.to_dict() results
        """
        # Score each position
        sell_candidates = []
        buy_candidates = []

        for analysis in analysis_results:
            ticker = analysis["ticker"]
            signal = analysis.get("signal", "hold")
            confidence = analysis.get("confidence", 0)
            current_price = analysis.get("current_price", 0)

            if signal == "sell" and confidence >= min_confidence:
                sell_candidates.append(analysis)
            elif signal == "buy" and confidence >= min_confidence:
                buy_candidates.append(analysis)

        # Sort by confidence
        sell_candidates.sort(key=lambda x: x["confidence"], reverse=True)
        buy_candidates.sort(key=lambda x: x["confidence"], reverse=True)

        # Determine sell quantities (reduce positions with sell signals)
        target_weights = {}
        n_positions = len(portfolio.positions)

        # Keep hold positions at current weight
        for pos in portfolio.positions:
            has_sell = any(s["ticker"] == pos.ticker for s in sell_candidates)
            if not has_sell:
                target_weights[pos.ticker] = pos.weight

        # Reduce sell-signal positions
        for analysis in sell_candidates:
            ticker = analysis["ticker"]
            pos = next((p for p in portfolio.positions if p.ticker == ticker), None)
            if pos:
                # Reduce by half
                target_weights[ticker] = pos.weight * 0.5

        # Allocate to buy candidates (up to max_positions)
        available_slots = max_positions - len(target_weights)
        if available_slots > 0 and buy_candidates:
            cash = portfolio.cash_balance
            total_value = portfolio.total_value
            alloc_per = min(5.0, (cash / total_value * 100) / len(buy_candidates)) if total_value else 0
            for analysis in buy_candidates[:available_slots]:
                target_weights[analysis["ticker"]] = alloc_per

        return self.rebalance(portfolio, target_weights, min_trade_pct=0.3)

    def generate_pie_rebalance(self, portfolio: PortfolioSnapshot,
                               pie_target: Dict[str, float]) -> RebalanceOrder:
        """Rebalance to match a Trading 212 Pie allocation."""
        return self.rebalance(portfolio, pie_target, min_trade_pct=1.0)


_rebalancer = None

def get_rebalancer() -> PortfolioRebalancer:
    global _rebalancer
    if _rebalancer is None:
        _rebalancer = PortfolioRebalancer()
    return _rebalancer
