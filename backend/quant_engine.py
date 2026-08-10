"""
Quant Engine — Technical analysis, momentum scoring, and backtesting.

Calculates: RSI, SMA/EMA crossovers, momentum scores, volatility,
Sharpe ratio, drawdown, sector rotation signals.

Uses pandas + yfinance for data. Falls back to basic calculations if unavailable.
"""

import os
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-quant")

try:
    import pandas as pd
    import numpy as np
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False
    log.warning("pandas/numpy not available — quant engine limited")

try:
    import yfinance as yf
    _HAS_YFINANCE = True
except ImportError:
    _HAS_YFINANCE = False
    log.warning("yfinance not available — using mock data")


# ── Technical Indicators ─────────────────────────────────────────────────────

def calc_rsi(prices: List[float], period: int = 14) -> float:
    """Calculate Relative Strength Index."""
    if not _HAS_PANDAS or len(prices) < period + 1:
        return 50.0

    deltas = pd.Series(prices).diff()
    gain = deltas.where(deltas > 0, 0.0).rolling(window=period).mean()
    loss = (-deltas.where(deltas < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else 50.0


def calc_sma(prices: List[float], period: int) -> float:
    """Simple Moving Average."""
    if not _HAS_PANDAS or len(prices) < period:
        return prices[-1] if prices else 0.0
    sma = pd.Series(prices).rolling(window=period).mean()
    return round(float(sma.iloc[-1]), 4) if not pd.isna(sma.iloc[-1]) else 0.0


def calc_ema(prices: List[float], period: int) -> float:
    """Exponential Moving Average."""
    if not _HAS_PANDAS or len(prices) < period:
        return prices[-1] if prices else 0.0
    ema = pd.Series(prices).ewm(span=period, adjust=False).mean()
    return round(float(ema.iloc[-1]), 4) if not pd.isna(ema.iloc[-1]) else 0.0


def calc_volatility(prices: List[float], annualize: bool = True) -> float:
    """Calculate volatility (standard deviation of returns)."""
    if not _HAS_PANDAS or len(prices) < 2:
        return 0.0
    returns = pd.Series(prices).pct_change().dropna()
    vol = returns.std()
    if annualize:
        vol *= np.sqrt(252)
    return round(float(vol), 4)


def calc_sharpe_ratio(prices: List[float], risk_free_rate: float = 0.05) -> float:
    """Calculate annualized Sharpe ratio."""
    if not _HAS_PANDAS or len(prices) < 25:
        return 0.0
    returns = pd.Series(prices).pct_change().dropna()
    excess = returns.mean() * 252 - risk_free_rate
    vol = returns.std() * np.sqrt(252)
    if vol == 0:
        return 0.0
    return round(float(excess / vol), 2)


def calc_max_drawdown(prices: List[float]) -> float:
    """Calculate maximum drawdown percentage."""
    if not _HAS_PANDAS or len(prices) < 2:
        return 0.0
    series = pd.Series(prices)
    peak = series.expanding().max()
    drawdown = (series - peak) / peak
    return round(float(drawdown.min()) * 100, 2)


def calc_momentum_score(prices: List[float], short_period: int = 20, long_period: int = 60) -> float:
    """Calculate momentum score from -1 (bearish) to +1 (bullish).
    
    Compares short-term vs long-term price trends.
    """
    if not _HAS_PANDAS or len(prices) < long_period:
        return 0.0

    series = pd.Series(prices)
    short_return = (series.iloc[-1] / series.iloc[-short_period] - 1) if short_period <= len(series) else 0
    long_return = (series.iloc[-1] / series.iloc[-long_period] - 1) if long_period <= len(series) else 0

    # Combine short and long momentum
    raw = (short_return * 0.6 + long_return * 0.4)
    # Normalize to [-1, 1]
    score = max(-1.0, min(1.0, raw / 0.15))
    return round(score, 3)


def calc_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict:
    """Calculate Bollinger Bands."""
    if not _HAS_PANDAS or len(prices) < period:
        mid = prices[-1] if prices else 0
        return {"upper": mid, "mid": mid, "lower": mid, "position": 0.5}

    series = pd.Series(prices)
    mid = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std

    current = float(series.iloc[-1])
    upper_val = float(upper.iloc[-1])
    lower_val = float(lower.iloc[-1])
    mid_val = float(mid.iloc[-1])

    if upper_val != lower_val:
        position = (current - lower_val) / (upper_val - lower_val)
    else:
        position = 0.5

    return {
        "upper": round(upper_val, 4),
        "mid": round(mid_val, 4),
        "lower": round(lower_val, 4),
        "position": round(float(position), 3),
    }


# ── Data Fetching ────────────────────────────────────────────────────────────

def fetch_prices(ticker: str, period: str = "3mo", interval: str = "1d") -> List[float]:
    """Fetch historical closing prices for a ticker."""
    if _HAS_YFINANCE:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)
            return hist["Close"].tolist()
        except Exception as e:
            log.debug(f"yfinance fetch failed for {ticker}: {e}")

    # Fallback: generate mock prices based on ticker hash
    return _mock_prices(ticker)


def fetch_info(ticker: str) -> Dict:
    """Fetch stock info (sector, pe, yield, etc.)."""
    if _HAS_YFINANCE:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return {
                "name": info.get("shortName", ticker),
                "sector": info.get("sector", "Unknown"),
                "pe_ratio": info.get("trailingPE", 0),
                "dividend_yield": (info.get("dividendYield", 0) or 0) * 100,
                "beta": info.get("beta", 1.0) or 1.0,
                "market_cap": info.get("marketCap", 0),
                "currency": info.get("currency", "USD"),
                "country": info.get("country", "Unknown"),
            }
        except Exception as e:
            log.debug(f"yfinance info failed for {ticker}: {e}")

    return {
        "name": ticker,
        "sector": "Unknown",
        "pe_ratio": 0,
        "dividend_yield": 0,
        "beta": 1.0,
        "market_cap": 0,
        "currency": "USD",
        "country": "Unknown",
    }


def fetch_current_price(ticker: str) -> float:
    """Fetch current stock price."""
    if _HAS_YFINANCE:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return info.get("regularMarketPrice", 0) or info.get("currentPrice", 0) or 0
        except Exception:
            pass
    return 0.0


# ── Backtest / Analysis ──────────────────────────────────────────────────────

@dataclass
class TickerAnalysis:
    ticker: str
    current_price: float = 0.0
    rsi: float = 50.0
    rsi_signal: str = "neutral"
    sma_50: float = 0.0
    sma_200: float = 0.0
    above_50dma: bool = False
    above_200dma: bool = False
    sma_cross: str = "none"
    momentum: float = 0.0
    volatility: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    bollinger: Dict = field(default_factory=dict)
    sector: str = ""
    pe_ratio: float = 0.0
    dividend_yield: float = 0.0
    signal: str = "hold"
    confidence: float = 0.0

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "current_price": self.current_price,
            "rsi": self.rsi,
            "rsi_signal": self.rsi_signal,
            "sma_50": self.sma_50,
            "sma_200": self.sma_200,
            "above_50dma": self.above_50dma,
            "above_200dma": self.above_200dma,
            "sma_cross": self.sma_cross,
            "momentum": self.momentum,
            "volatility": self.volatility,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "bollinger": self.bollinger,
            "sector": self.sector,
            "pe_ratio": self.pe_ratio,
            "dividend_yield": self.dividend_yield,
            "signal": self.signal,
            "confidence": self.confidence,
        }


def analyze_ticker(ticker: str) -> TickerAnalysis:
    """Full technical analysis of a single ticker."""
    prices = fetch_prices(ticker, period="1y", interval="1d")
    if not prices or len(prices) < 20:
        return TickerAnalysis(ticker=ticker, signal="hold", confidence=0.0)

    info = fetch_info(ticker)
    current = prices[-1]

    rsi = calc_rsi(prices)
    rsi_signal = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"

    sma50 = calc_sma(prices, 50)
    sma200 = calc_sma(prices, 200)
    above50 = current > sma50
    above200 = current > sma200

    # SMA crossover
    if len(prices) >= 201:
        sma50_prev = calc_sma(prices[:-5], 50)
        sma200_prev = calc_sma(prices[:-5], 200)
        if sma50_prev <= sma200_prev and sma50 > sma200:
            sma_cross = "bullish"
        elif sma50_prev >= sma200_prev and sma50 < sma200:
            sma_cross = "bearish"
        else:
            sma_cross = "none"
    else:
        sma_cross = "none"

    momentum = calc_momentum_score(prices)
    volatility = calc_volatility(prices)
    sharpe = calc_sharpe_ratio(prices)
    max_dd = calc_max_drawdown(prices)
    bollinger = calc_bollinger_bands(prices)

    # Generate signal
    signal, confidence = _generate_signal(
        rsi, rsi_signal, above50, above200, sma_cross, momentum, bollinger.get("position", 0.5)
    )

    return TickerAnalysis(
        ticker=ticker,
        current_price=current,
        rsi=rsi,
        rsi_signal=rsi_signal,
        sma_50=sma50,
        sma_200=sma200,
        above_50dma=above50,
        above_200dma=above200,
        sma_cross=sma_cross,
        momentum=momentum,
        volatility=volatility,
        sharpe=sharpe,
        max_drawdown=max_dd,
        bollinger=bollinger,
        sector=info.get("sector", ""),
        pe_ratio=info.get("pe_ratio", 0),
        dividend_yield=info.get("dividend_yield", 0),
        signal=signal,
        confidence=confidence,
    )


def analyze_portfolio(tickers: List[str]) -> List[TickerAnalysis]:
    """Analyze multiple tickers."""
    results = []
    for ticker in tickers:
        try:
            r = analyze_ticker(ticker)
            results.append(r)
        except Exception as e:
            log.error(f"Analysis failed for {ticker}: {e}")
            results.append(TickerAnalysis(ticker=ticker, signal="hold", confidence=0.0))
    return results


def backtest_momentum(tickers: List[str], days: int = 60, top_n: int = 5) -> Dict:
    """Run momentum backtest and return top performers."""
    results = []
    for ticker in tickers:
        prices = fetch_prices(ticker, period=f"{days}d", interval="1d")
        if len(prices) < 10:
            continue
        momentum = calc_momentum_score(prices, short_period=min(20, len(prices)-1))
        ret = (prices[-1] / prices[0] - 1) * 100 if prices[0] else 0
        results.append({
            "ticker": ticker,
            "momentum": momentum,
            "return_pct": round(ret, 2),
            "current_price": prices[-1],
        })

    results.sort(key=lambda x: x["momentum"], reverse=True)
    return {
        "top_momentum": results[:top_n],
        "bottom_momentum": results[-top_n:] if len(results) >= top_n else [],
        "all_results": results,
    }


def _generate_signal(rsi: float, rsi_signal: str, above50: bool, above200: bool,
                     sma_cross: str, momentum: float, bb_position: float) -> Tuple[str, float]:
    """Generate a buy/sell/hold signal with confidence."""
    score = 0
    weights = 0

    # RSI signal (weight: 0.2)
    if rsi_signal == "oversold":
        score += 0.2
    elif rsi_signal == "overbought":
        score -= 0.2
    weights += 0.2

    # Trend (weight: 0.3)
    trend = 0
    if above50:
        trend += 0.15
    else:
        trend -= 0.15
    if above200:
        trend += 0.15
    else:
        trend -= 0.15
    score += trend
    weights += 0.3

    # SMA cross (weight: 0.2)
    if sma_cross == "bullish":
        score += 0.2
    elif sma_cross == "bearish":
        score -= 0.2
    weights += 0.2

    # Momentum (weight: 0.2)
    score += momentum * 0.2
    weights += 0.2

    # Bollinger position (weight: 0.1)
    bb_score = (0.5 - bb_position) * 0.2  # Low position = oversold
    score += bb_score
    weights += 0.1

    total = score / weights if weights else 0

    if total > 0.15:
        return "buy", min(abs(total), 1.0)
    elif total < -0.15:
        return "sell", min(abs(total), 1.0)
    else:
        return "hold", 1.0 - abs(total)


def _mock_prices(ticker: str) -> List[float]:
    """Generate mock prices for testing when yfinance is unavailable."""
    import hashlib
    seed = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16) % 10000
    base = 50 + (seed % 200)
    prices = [base]
    for i in range(60):
        change = (hash(f"{ticker}_{i}") % 100 - 48) / 100
        prices.append(round(prices[-1] * (1 + change), 2))
    return prices
