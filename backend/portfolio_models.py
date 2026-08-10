"""
Portfolio Models — Financial data models for Trading 212 and general portfolio management.

Defines Position, Order, Portfolio, and related data structures.
"""

import time
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

log = logging.getLogger("jarvis-portfolio")


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    STAGED = "staged"
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class InstrumentType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    FUND = "fund"
    BOND = "bond"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


@dataclass
class Position:
    ticker: str
    quantity: float
    avg_price: float
    currency: str = "USD"
    instrument_type: str = "stock"
    name: str = ""
    sector: str = ""
    country: str = ""
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    dividend_yield: float = 0.0
    weight: float = 0.0
    beta: float = 0.0
    pe_ratio: float = 0.0
    last_dividend: float = 0.0
    buy_date: str = ""

    def to_dict(self):
        return asdict(self)

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_price

    @property
    def annual_dividend(self) -> float:
        return self.market_value * (self.dividend_yield / 100) if self.dividend_yield else 0


@dataclass
class OrderTicket:
    ticker: str
    side: str  # buy | sell
    quantity: float
    order_type: str = "market"
    limit_price: float = 0.0
    stop_price: float = 0.0
    currency: str = "USD"
    instrument_type: str = "stock"
    estimated_price: float = 0.0
    estimated_total: float = 0.0
    reason: str = ""
    confidence: float = 0.0
    status: str = "staged"
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)

    @property
    def notional_value(self) -> float:
        price = self.limit_price if self.order_type == "limit" else self.estimated_price
        return self.quantity * price


@dataclass
class PortfolioSnapshot:
    account_id: str = ""
    cash_balance: float = 0.0
    currency: str = "USD"
    total_value: float = 0.0
    positions: List[Position] = field(default_factory=list)
    open_orders: List[OrderTicket] = field(default_factory=list)
    pie_allocations: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    account_type: str = "paper"  # paper | live

    def to_dict(self):
        return {
            "account_id": self.account_id,
            "cash_balance": self.cash_balance,
            "currency": self.currency,
            "total_value": self.total_value,
            "positions": [p.to_dict() for p in self.positions],
            "open_orders": [o.to_dict() for o in self.open_orders],
            "pie_allocations": self.pie_allocations,
            "timestamp": self.timestamp,
            "account_type": self.account_type,
        }

    @property
    def invested_value(self) -> float:
        return sum(p.market_value for p in self.positions)

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions)

    @property
    def portfolio_beta(self) -> float:
        total = sum(p.weight * p.beta for p in self.positions if p.beta)
        return total if total else 1.0

    @property
    def weighted_dividend_yield(self) -> float:
        return sum(p.weight * p.dividend_yield for p in self.positions if p.dividend_yield)

    @property
    def annual_dividend_income(self) -> float:
        return sum(p.annual_dividend for p in self.positions)

    @property
    def concentration_risk(self) -> Dict[str, float]:
        sector_weights = {}
        for p in self.positions:
            sector = p.sector or "Unknown"
            sector_weights[sector] = sector_weights.get(sector, 0) + p.weight
        max_sector = max(sector_weights.values()) if sector_weights else 0
        max_stock = max((p.weight for p in self.positions), default=0)
        return {
            "max_sector_weight": max_sector,
            "max_stock_weight": max_stock,
            "sector_count": len(sector_weights),
            "herfindahl": sum(w ** 2 for w in sector_weights.values()),
        }


@dataclass
class BacktestResult:
    ticker: str
    period_days: int
    total_return_pct: float
    annualized_return_pct: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    rsi_current: float
    rsi_signal: str  # oversold | overbought | neutral
    momentum_score: float  # -1 to 1
    above_200dma: bool
    above_50dma: bool
    sma_cross_signal: str  # bullish | bearish | none
    sector: str = ""
    signal: str = "hold"  # buy | sell | hold

    def to_dict(self):
        return asdict(self)


@dataclass
class RebalanceOrder:
    orders: List[OrderTicket] = field(default_factory=list)
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    net_value: float = 0.0
    cash_before: float = 0.0
    cash_after: float = 0.0
    max_slippage_pct: float = 0.5
    reason: str = ""

    def to_dict(self):
        return {
            "orders": [o.to_dict() for o in self.orders],
            "total_buy_value": self.total_buy_value,
            "total_sell_value": self.total_sell_value,
            "net_value": self.net_value,
            "cash_before": self.cash_before,
            "cash_after": self.cash_after,
            "max_slippage_pct": self.max_slippage_pct,
            "reason": self.reason,
        }

    def validate(self) -> Dict:
        issues = []
        if self.net_value > self.cash_before * 1.02:
            issues.append("Insufficient cash for buy orders")
        for o in self.orders:
            if o.quantity <= 0:
                issues.append(f"Invalid quantity for {o.ticker}")
            if o.side == "sell" and o.quantity > 0:
                # Would need position data to validate
                pass
        return {"valid": len(issues) == 0, "issues": issues}
