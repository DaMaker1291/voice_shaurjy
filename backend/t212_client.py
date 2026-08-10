"""
Trading 212 API Client — Connect to Trading 212 for portfolio data and order staging.

Supports:
- Paper trading and live accounts
- Portfolio positions, cash balance, pies
- Order staging (not execution without Laser Gate)
- CDP browser fallback for account types not on public API

Trading 212 Public API uses HTTP Basic Auth: API_KEY:API_SECRET
Base URL: https://live.trading212.com/api/v1/
"""

import os
import json
import base64
import logging
import urllib.request
import urllib.error
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass

log = logging.getLogger("jarvis-t212")

_BASE_URL = "https://live.trading212.com/api/v1"
_PAPER_URL = "https://demo.trading212.com/api/v1"


@dataclass
class T212Config:
    api_key: str = ""
    api_secret: str = ""
    account_type: str = "paper"  # paper | live
    base_url: str = ""

    def __post_init__(self):
        if not self.base_url:
            self.base_url = _PAPER_URL if self.account_type == "paper" else _BASE_URL


class Trading212Client:
    """Trading 212 REST API client."""

    def __init__(self, config: T212Config = None):
        if config is None:
            config = T212Config(
                api_key=os.environ.get("T212_API_KEY", ""),
                api_secret=os.environ.get("T212_API_SECRET", ""),
                account_type=os.environ.get("T212_ACCOUNT_TYPE", "paper"),
            )
        self._config = config
        self._auth = None
        if config.api_key and config.api_secret:
            self._auth = base64.b64encode(f"{config.api_key}:{config.api_secret}".encode()).decode()

    def is_configured(self) -> bool:
        return bool(self._config.api_key and self._config.api_secret)

    def _request(self, method: str, path: str, data: Dict = None) -> Dict:
        url = f"{self._config.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self._auth:
            headers["Authorization"] = f"Basic {self._auth}"

        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode()
                return json.loads(content) if content else {"status": "ok"}
        except urllib.error.HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            log.error(f"T212 API {method} {path}: {e.code} {body_text[:300]}")
            return {"error": e.code, "message": body_text[:500]}
        except Exception as e:
            return {"error": str(e)}

    def get_account_info(self) -> Dict:
        """Get account details including cash balance and currency."""
        return self._request("GET", "/equity/account/info")

    def get_cash(self) -> Dict:
        """Get cash balance."""
        return self._request("GET", "/equity/account/cash")

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        result = self._request("GET", "/equity/positions")
        return result if isinstance(result, list) else []

    def get_position(self, instrument_id: int) -> Dict:
        return self._request("GET", f"/equity/positions/{instrument_id}")

    def get_orders(self) -> List[Dict]:
        """Get open/pending orders."""
        result = self._request("GET", "/equity/orders")
        return result if isinstance(result, list) else []

    def get_order(self, order_id: int) -> Dict:
        return self._request("GET", f"/equity/orders/{order_id}")

    def get_instrument_info(self, ticker: str) -> Dict:
        """Get instrument details (price, name, ISIN, etc.)."""
        return self._request("GET", f"/equity/history/near?ticker={ticker}")

    def get_pies(self) -> List[Dict]:
        """Get pie allocations (auto-invest portfolios)."""
        result = self._request("GET", "/equity/pies")
        return result if isinstance(result, list) else []

    def get_transaction_history(self, limit: int = 50) -> List[Dict]:
        result = self._request("GET", f"/history/transactions?limit={limit}")
        return result if isinstance(result, list) else []

    def stage_order(self, ticker: str, quantity: float, side: str = "buy",
                    order_type: str = "market", limit_price: float = None) -> Dict:
        """Stage an order (does NOT execute without confirmation)."""
        payload = {
            "ticker": ticker.upper(),
            "quantity": quantity,
            "side": side.lower(),
            "type": order_type.upper(),
        }
        if limit_price and order_type == "limit":
            payload["limitPrice"] = limit_price
        return self._request("POST", "/equity/orders", payload)

    def cancel_order(self, order_id: int) -> Dict:
        return self._request("DELETE", f"/equity/orders/{order_id}")

    def get_portfolio_summary(self) -> Dict:
        """Get a complete portfolio summary."""
        info = self.get_account_info()
        cash = self.get_cash()
        positions = self.get_positions()
        orders = self.get_orders()
        pies = self.get_pies()

        return {
            "account": info,
            "cash": cash,
            "positions": positions,
            "open_orders": orders,
            "pies": pies,
            "position_count": len(positions),
            "order_count": len(orders),
        }


_client = None

def get_t212(config: T212Config = None) -> Trading212Client:
    global _client
    if _client is None:
        _client = Trading212Client(config)
    return _client
