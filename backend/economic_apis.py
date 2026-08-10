"""
Economic APIs — Real transaction integrations for the autonomous web agent.
============================================================================
Provides flight, hotel, payment, domain, and price monitoring APIs with
automatic fallback to Playwright web scraping when API keys are absent.

PCI DSS Compliance Notes
------------------------
- PaymentAPI NEVER stores raw card numbers, CVVs, or磁条 data.
- All payment flows delegate to Stripe's tokenized checkout (PCI SAQ-A).
- Audit logs redact sensitive fields before persistence.
- Environment variables for secrets are never logged or returned.
"""

import os
import re
import json
import time
import logging
import hashlib
import threading
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("economic_apis")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s"))
    logger.addHandler(_h)

# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------
_AUDIT_DIR = os.path.join(os.path.dirname(__file__), ".workflow_data")
os.makedirs(_AUDIT_DIR, exist_ok=True)
_AUDIT_FILE = os.path.join(_AUDIT_DIR, "economic_audit.jsonl")
_AUDIT_LOCK = threading.Lock()


def _audit_log(entry: dict):
    entry["timestamp"] = datetime.now().isoformat()
    with _AUDIT_LOCK:
        try:
            with open(_AUDIT_FILE, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.warning("Audit write failed: %s", e)


def _redact(obj: Any) -> Any:
    """Redact sensitive fields for audit logging."""
    if isinstance(obj, dict):
        return {k: ("***REDACTED***" if any(s in k.lower() for s in
                ("key", "secret", "token", "password", "cvv", "card", "ssn")) else _redact(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# Environment helper
# ---------------------------------------------------------------------------

def _env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# HTTP helper — uses requests if available, else urllib
# ---------------------------------------------------------------------------
try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    import urllib.request as _urllib_req
    import urllib.error as _urllib_err
    _HAS_REQUESTS = False


def _http_get(url: str, headers: dict | None = None, params: dict | None = None,
              timeout: int = 30) -> dict:
    """GET request returning parsed JSON or error dict."""
    if _HAS_REQUESTS:
        try:
            r = _req.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return {"ok": True, "data": r.json()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    else:
        try:
            from urllib.parse import urlencode
            if params:
                url = f"{url}?{urlencode(params)}"
            req = _urllib_req.Request(url, headers=headers or {})
            with _urllib_req.urlopen(req, timeout=timeout) as resp:
                return {"ok": True, "data": json.loads(resp.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def _http_post(url: str, headers: dict | None = None, json_body: dict | None = None,
               timeout: int = 30) -> dict:
    if _HAS_REQUESTS:
        try:
            r = _req.post(url, headers=headers, json=json_body, timeout=timeout)
            r.raise_for_status()
            return {"ok": True, "data": r.json()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    else:
        try:
            data = json.dumps(json_body).encode() if json_body else None
            req = _urllib_req.Request(url, data=data, headers=headers or {}, method="POST")
            with _urllib_req.urlopen(req, timeout=timeout) as resp:
                return {"ok": True, "data": json.loads(resp.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ============================================================================
# Flight API
# ============================================================================

class FlightAPI:
    """Flight search and booking via Amadeus / Skyscanner, with Playwright fallback.

    Environment variables:
        AMADEUS_API_KEY, AMADEUS_API_SECRET — Amadeus Self-Service API
        SKYSCANNER_API_KEY — Skyscanner Flights API
    """

    AMADEUS_BASE = "https://api.amadeus.com/v2"
    AMADEUS_TOKEN_URL = "https://api.amadeus.com/v1/security/oauth2/token"
    SKYSCANNER_BASE = "https://partners.api.skyscanner.net/apiservices/v3"

    def __init__(self):
        self._amadeus_key = _env("AMADEUS_API_KEY")
        self._amadeus_secret = _env("AMADEUS_API_SECRET")
        self._skyscanner_key = _env("SKYSCANNER_API_KEY")
        self._amadeus_token: str | None = None
        self._amadeus_token_expires: float = 0
        self._lock = threading.Lock()

    # -- Amadeus OAuth token ------------------------------------------------

    def _get_amadeus_token(self) -> str | None:
        if not self._amadeus_key or not self._amadeus_secret:
            return None
        with self._lock:
            if self._amadeus_token and time.time() < self._amadeus_token_expires:
                return self._amadeus_token
            resp = _http_post(self.AMADEUS_TOKEN_URL, headers={
                "Content-Type": "application/x-www-form-urlencoded"
            }, json_body={
                "grant_type": "client_credentials",
                "client_id": self._amadeus_key,
                "client_secret": self._amadeus_secret,
            })
            if resp.get("ok"):
                data = resp["data"]
                self._amadeus_token = data.get("access_token")
                self._amadeus_token_expires = time.time() + data.get("expires_in", 1799) - 60
                return self._amadeus_token
            logger.warning("Amadeus token fetch failed: %s", resp.get("error"))
            return None

    # -- Public API ---------------------------------------------------------

    def search_flights(
        self,
        origin: str,
        destination: str,
        date: str,
        return_date: str | None = None,
        passengers: int = 1,
    ) -> list[dict]:
        """Search one-way or round-trip flights.

        Args:
            origin: IATA airport code (e.g. "JFK").
            destination: IATA airport code (e.g. "LHR").
            date: Departure date YYYY-MM-DD.
            return_date: Optional return date YYYY-MM-DD.
            passengers: Number of adult passengers.

        Returns:
            List of flight offer dicts with keys:
                id, airline, flight_number, origin, destination,
                departure, arrival, price, currency, stops, duration
        """
        token = self._get_amadeus_token()
        if token:
            return self._search_amadeus(token, origin, destination, date,
                                        return_date, passengers)
        if self._skyscanner_key:
            return self._search_skyscanner(origin, destination, date,
                                           return_date, passengers)
        return self._search_fallback(origin, destination, date,
                                     return_date, passengers)

    def _search_amadeus(self, token: str, origin: str, dest: str,
                        date: str, ret: str | None, pax: int) -> list[dict]:
        params: dict[str, Any] = {
            "originLocationCode": origin,
            "destinationLocationCode": dest,
            "departureDate": date,
            "adults": pax,
            "max": 10,
            "currencyCode": "USD",
        }
        if ret:
            params["returnDate"] = ret
        resp = _http_get(f"{self.AMADEUS_BASE}/shopping/flight-offers",
                         headers={"Authorization": f"Bearer {token}"},
                         params=params)
        if not resp.get("ok"):
            logger.warning("Amadeus search failed: %s", resp.get("error"))
            return self._search_fallback(origin, dest, date, ret, pax)
        offers = resp.get("data", [])
        results = []
        for o in offers:
            itineraries = o.get("itineraries", [])
            dep_seg = itineraries[0]["segments"][0] if itineraries else {}
            arr_seg = itineraries[-1]["segments"][-1] if itineraries else {}
            results.append({
                "id": o.get("id", ""),
                "airline": dep_seg.get("carrierCode", ""),
                "flight_number": dep_seg.get("number", ""),
                "origin": dep_seg.get("departure", {}).get("iataCode", origin),
                "destination": arr_seg.get("arrival", {}).get("iataCode", dest),
                "departure": dep_seg.get("departure", {}).get("at", ""),
                "arrival": arr_seg.get("arrival", {}).get("at", ""),
                "price": float(o.get("price", {}).get("total", 0)),
                "currency": o.get("price", {}).get("currency", "USD"),
                "stops": len(itineraries[0].get("segments", [])) - 1 if itineraries else 0,
                "duration": itineraries[0].get("duration", "") if itineraries else "",
            })
        return results

    def _search_skyscanner(self, origin: str, dest: str, date: str,
                           ret: str | None, pax: int) -> list[dict]:
        body: dict[str, Any] = {
            "query": {
                "market": "US",
                "locale": "en-US",
                "currency": "USD",
                "queryLegs": [
                    {"originPlaceId": {"iata": origin},
                     "destinationPlaceId": {"iata": dest},
                     "date": {"year": int(date[:4]), "month": int(date[5:7]),
                              "day": int(date[8:10])}},
                ],
            }
        }
        if ret:
            body["query"]["queryLegs"].append({
                "originPlaceId": {"iata": dest},
                "destinationPlaceId": {"iata": origin},
                "date": {"year": int(ret[:4]), "month": int(ret[5:7]),
                         "day": int(ret[8:10])},
            })
        resp = _http_post(
            f"{self.SKYSCANNER_BASE}/flights/live/search/create",
            headers={"x-api-key": self._skyscanner_key,
                     "Content-Type": "application/json"},
            json_body=body)
        if not resp.get("ok"):
            logger.warning("Skyscanner search failed: %s", resp.get("error"))
            return self._search_fallback(origin, dest, date, ret, pax)
        data = resp.get("data", {})
        itineraries = data.get("itineraries", {})
        results = []
        for itin_id, itin in itineraries.items():
            leg = itin.get("legs", [{}])[0]
            price_val = itin.get("price", {}).get("raw", 0)
            results.append({
                "id": itin_id,
                "airline": leg.get("carriersInOperation", [""])[0] if leg.get("carriersInOperation") else "",
                "flight_number": "",
                "origin": origin,
                "destination": dest,
                "departure": leg.get("departure", ""),
                "arrival": leg.get("arrival", ""),
                "price": float(price_val),
                "currency": "USD",
                "stops": leg.get("stopCount", 0),
                "duration": leg.get("durationInMinutes", ""),
            })
        return results

    def _search_fallback(self, origin: str, dest: str, date: str,
                         ret: str | None, pax: int) -> list[dict]:
        """Scrape Google Flights via Playwright as last resort."""
        try:
            from web_automation import _ensure_page, navigate, get_text
            url = (f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{dest}"
                   f"+on+{date}")
            if ret:
                url += f"+return+{ret}"
            navigate(url)
            time.sleep(3)
            text = get_text()
            return [{"id": "scraped_0", "airline": "", "flight_number": "",
                      "origin": origin, "destination": dest,
                      "departure": date, "arrival": "",
                      "price": 0, "currency": "USD", "stops": 0,
                      "duration": "", "raw_text": text[:500]}]
        except Exception as e:
            logger.error("Flight fallback scrape failed: %s", e)
            return [{"id": "unavailable", "error": str(e)}]

    def get_flight_details(self, flight_id: str) -> dict:
        token = self._get_amadeus_token()
        if token:
            resp = _http_get(f"{self.AMADEUS_BASE}/shopping/flight-offers/{flight_id}",
                             headers={"Authorization": f"Bearer {token}"})
            if resp.get("ok"):
                return resp["data"]
        return {"id": flight_id, "details": "unavailable",
                "message": "No API key or flight not found"}

    def estimate_price(self, origin: str, destination: str, date: str) -> dict:
        """Quick price estimate without full search."""
        results = self.search_flights(origin, destination, date, passengers=1)
        valid = [r for r in results if r.get("price", 0) > 0]
        if not valid:
            return {"estimated_price": 0, "currency": "USD",
                    "confidence": "low", "source": "none"}
        prices = [r["price"] for r in valid]
        return {
            "estimated_price": sum(prices) / len(prices),
            "min_price": min(prices),
            "max_price": max(prices),
            "currency": valid[0].get("currency", "USD"),
            "confidence": "high" if len(valid) >= 3 else "medium",
            "source": "api",
            "offers_count": len(valid),
        }


# ============================================================================
# Hotel API
# ============================================================================

class HotelAPI:
    """Hotel search and booking via web scraping (Booking.com/Hotels.com).

    Environment variables:
        AMADEUS_API_KEY / AMADEUS_API_SECRET — for Amadeus Hotel Shopping
    """

    def __init__(self):
        self._amadeus_key = _env("AMADEUS_API_KEY")
        self._amadeus_secret = _env("AMADEUS_API_SECRET")
        self._amadeus_token: str | None = None
        self._amadeus_token_expires: float = 0
        self._lock = threading.Lock()

    def _get_amadeus_token(self) -> str | None:
        if not self._amadeus_key or not self._amadeus_secret:
            return None
        with self._lock:
            if self._amadeus_token and time.time() < self._amadeus_token_expires:
                return self._amadeus_token
            resp = _http_post("https://api.amadeus.com/v1/security/oauth2/token",
                              headers={"Content-Type": "application/x-www-form-urlencoded"},
                              json_body={"grant_type": "client_credentials",
                                         "client_id": self._amadeus_key,
                                         "client_secret": self._amadeus_secret})
            if resp.get("ok"):
                d = resp["data"]
                self._amadeus_token = d.get("access_token")
                self._amadeus_token_expires = time.time() + d.get("expires_in", 1799) - 60
                return self._amadeus_token
            return None

    def search_hotels(
        self,
        location: str,
        checkin: str,
        checkout: str,
        guests: int = 1,
    ) -> list[dict]:
        """Search hotels by location.

        Args:
            location: City name, address, or coordinates.
            checkin: Check-in date YYYY-MM-DD.
            checkout: Check-out date YYYY-MM-DD.
            guests: Number of guests.

        Returns:
            List of hotel dicts with keys:
                id, name, address, rating, price_per_night, currency,
                amenities, checkin, checkout
        """
        token = self._get_amadeus_token()
        if token:
            return self._search_amadeus_hotels(token, location, checkin, checkout, guests)
        return self._search_hotel_fallback(location, checkin, checkout, guests)

    def _search_amadeus_hotels(self, token: str, location: str,
                                checkin: str, checkout: str, guests: int) -> list[dict]:
        geo_resp = _http_get(
            "https://api.amadeus.com/v1/reference-data/locations",
            headers={"Authorization": f"Bearer {token}"},
            params={"keyword": location, "subType": "CITY,AIRPORT"})
        if not geo_resp.get("ok"):
            return self._search_hotel_fallback(location, checkin, checkout, guests)
        locations = geo_resp.get("data", [])
        if not locations:
            return self._search_hotel_fallback(location, checkin, checkout, guests)
        lat = locations[0].get("geoCode", {}).get("latitude", 0)
        lon = locations[0].get("geoCode", {}).get("longitude", 0)

        resp = _http_get(
            "https://api.amadeus.com/v3/shopping/hotel-offers",
            headers={"Authorization": f"Bearer {token}"},
            params={"latitude": lat, "longitude": lon,
                    "checkInDate": checkin, "checkOutDate": checkout,
                    "adults": guests, "radius": 10, "radiusUnit": "KM",
                    "hotelSource": "ALL"})
        if not resp.get("ok"):
            return self._search_hotel_fallback(location, checkin, checkout, guests)

        results = []
        for item in resp.get("data", []):
            h = item.get("hotel", {})
            offer = item.get("offers", [{}])[0] if item.get("offers") else {}
            price = offer.get("price", {})
            results.append({
                "id": h.get("hotelId", ""),
                "name": h.get("name", ""),
                "address": ", ".join(filter(None, [
                    h.get("address", {}).get("lines", [""])[0],
                    h.get("address", {}).get("cityName", ""),
                    h.get("address", {}).get("countryCode", "")])),
                "rating": h.get("rating", ""),
                "price_per_night": float(price.get("base", 0)),
                "currency": price.get("currency", "USD"),
                "amenities": h.get("amenities", []),
                "checkin": checkin,
                "checkout": checkout,
            })
        return results

    def _search_hotel_fallback(self, location: str, checkin: str,
                                checkout: str, guests: int) -> list[dict]:
        """Scrape Booking.com via Playwright."""
        try:
            from web_automation import _ensure_page, navigate, get_text
            url = (f"https://www.booking.com/searchresults.html"
                   f"?ss={quote_plus(location)}&checkin={checkin}"
                   f"&checkout={checkout}&group_adults={guests}")
            navigate(url)
            time.sleep(4)
            text = get_text()
            return [{"id": "scraped_0", "name": "See browser",
                     "address": location, "rating": "",
                     "price_per_night": 0, "currency": "USD",
                     "amenities": [], "checkin": checkin,
                     "checkout": checkout, "raw_text": text[:500]}]
        except Exception as e:
            logger.error("Hotel fallback scrape failed: %s", e)
            return [{"id": "unavailable", "error": str(e)}]

    def get_hotel_details(self, hotel_id: str) -> dict:
        token = self._get_amadeus_token()
        if token:
            resp = _http_get(
                f"https://api.amadeus.com/v3/shopping/hotel-offers/{hotel_id}",
                headers={"Authorization": f"Bearer {token}"})
            if resp.get("ok"):
                return resp["data"]
        return {"id": hotel_id, "details": "unavailable",
                "message": "No API key or hotel not found"}


# ============================================================================
# Payment API
# ============================================================================

class PaymentAPI:
    """Stripe-based payment processing.

    Environment variables:
        STRIPE_SECRET_KEY — sk_live_... or sk_test_...
        STRIPE_PUBLISHABLE_KEY — pk_live_... or pk_test_...

    PCI DSS Notes:
    - This API never touches raw card data. All card entry is handled by
      Stripe.js / Stripe Checkout (PCI SAQ-A scope).
    - Only tokenized payment_method IDs and PaymentIntent objects flow
      through this layer.
    - The stripe_secret_key is loaded from env and never persisted.
    - Audit logs redact the key before writing.
    """

    STRIPE_BASE = "https://api.stripe.com/v1"

    def __init__(self):
        self._key = _env("STRIPE_SECRET_KEY")

    def _stripe_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _stripe_post(self, endpoint: str, params: dict) -> dict:
        if not self._key:
            return {"ok": False, "error": "STRIPE_SECRET_KEY not configured"}
        if _HAS_REQUESTS:
            try:
                r = _req.post(f"{self.STRIPE_BASE}/{endpoint}",
                              headers=self._stripe_headers(),
                              data=params, timeout=30)
                if r.status_code >= 400:
                    return {"ok": False, "error": r.json().get("error", {}).get("message", str(r.status_code))}
                return {"ok": True, "data": r.json()}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        else:
            from urllib.parse import urlencode
            data = urlencode(params).encode()
            req = _urllib_req.Request(f"{self.STRIPE_BASE}/{endpoint}",
                                      data=data,
                                      headers=self._stripe_headers(),
                                      method="POST")
            try:
                with _urllib_req.urlopen(req, timeout=30) as resp:
                    return {"ok": True, "data": json.loads(resp.read())}
            except _urllib_err.HTTPError as e:
                body = json.loads(e.read()) if e.fp else {}
                return {"ok": False, "error": body.get("error", {}).get("message", str(e.code))}
            except Exception as e:
                return {"ok": False, "error": str(e)}

    def create_payment_intent(
        self,
        amount: float,
        currency: str = "usd",
        description: str = "",
    ) -> dict:
        """Create a Stripe PaymentIntent.

        Args:
            amount: Amount in dollars (will be converted to cents).
            currency: ISO 4217 currency code.
            description: Human-readable description.

        Returns:
            Dict with payment_intent id, client_secret, status, amount.
        """
        cents = int(round(amount * 100))
        resp = self._stripe_post("payment_intents", {
            "amount": cents,
            "currency": currency,
            "description": description,
            "payment_method_types[]": "card",
        })
        if resp.get("ok"):
            d = resp["data"]
            _audit_log({"action": "payment_intent_created",
                        "payment_id": d.get("id"), "amount": amount,
                        "currency": currency, "description": description})
            return {
                "ok": True,
                "payment_id": d.get("id"),
                "client_secret": d.get("client_secret"),
                "status": d.get("status"),
                "amount": amount,
                "currency": currency,
            }
        _audit_log({"action": "payment_intent_failed", "error": resp.get("error"),
                     "amount": amount, "currency": currency})
        return {"ok": False, "error": resp.get("error", "Unknown Stripe error")}

    def confirm_payment(self, payment_id: str) -> dict:
        """Confirm a PaymentIntent (auto-confirm for basic flows).

        Returns:
            Dict with updated status.
        """
        resp = self._stripe_post(f"payment_intents/{payment_id}/confirm", {})
        if resp.get("ok"):
            d = resp["data"]
            _audit_log({"action": "payment_confirmed", "payment_id": payment_id,
                        "status": d.get("status")})
            return {"ok": True, "payment_id": payment_id,
                    "status": d.get("status")}
        _audit_log({"action": "payment_confirm_failed", "payment_id": payment_id,
                    "error": resp.get("error")})
        return {"ok": False, "error": resp.get("error")}

    def get_payment_status(self, payment_id: str) -> dict:
        """Retrieve current status of a PaymentIntent."""
        resp = _http_get(f"{self.STRIPE_BASE}/payment_intents/{payment_id}",
                         headers=self._stripe_headers())
        if resp.get("ok"):
            d = resp["data"]
            return {"ok": True, "payment_id": payment_id,
                    "status": d.get("status"),
                    "amount": d.get("amount", 0) / 100,
                    "currency": d.get("currency"),
                    "created": d.get("created")}
        return {"ok": False, "error": resp.get("error")}


# ============================================================================
# Travel Booking API
# ============================================================================

class TravelBookingAPI:
    """End-to-end travel booking combining flights + hotels with budget optimization."""

    def __init__(self, flight_api: FlightAPI, hotel_api: HotelAPI):
        self._flights = flight_api
        self._hotels = hotel_api

    def book_trip(
        self,
        origin: str,
        destination: str,
        dates: dict,
        budget: float,
    ) -> dict:
        """Plan and price a complete trip within budget.

        Args:
            origin: Departure airport/city.
            destination: Arrival airport/city.
            dates: Dict with keys:
                departure (YYYY-MM-DD), return (YYYY-MM-DD),
                checkin (YYYY-MM-DD), checkout (YYYY-MM-DD).
            budget: Maximum total budget in USD.

        Returns:
            Dict with flight options, hotel options, total cost,
            within_budget flag, and itemized breakdown.
        """
        departure = dates.get("departure", "")
        ret = dates.get("return")
        checkin = dates.get("checkin", departure)
        checkout = dates.get("checkout", ret or departure)
        days = max(1, (datetime.strptime(checkout, "%Y-%m-%d") -
                        datetime.strptime(checkin, "%Y-%m-%d")).days)

        flights = self._flights.search_flights(origin, destination,
                                               departure, ret)
        hotels = self._hotels.search_hotels(destination, checkin, checkout)

        valid_flights = [f for f in flights if f.get("price", 0) > 0]
        valid_hotels = [h for h in hotels if h.get("price_per_night", 0) > 0]

        best_flight = min(valid_flights, key=lambda x: x["price"]) if valid_flights else None
        best_hotel = min(valid_hotels, key=lambda x: x["price_per_night"]) if valid_hotels else None

        flight_cost = best_flight["price"] if best_flight else 0
        hotel_cost = (best_hotel["price_per_night"] * days) if best_hotel else 0
        total = flight_cost + hotel_cost

        return {
            "destination": destination,
            "departure_date": departure,
            "return_date": ret,
            "nights": days,
            "flights_found": len(valid_flights),
            "hotels_found": len(valid_hotels),
            "selected_flight": best_flight,
            "selected_hotel": best_hotel,
            "breakdown": {
                "flights": flight_cost,
                "hotel": hotel_cost,
                "estimated_taxes": round(total * 0.12, 2),
                "total": round(total * 1.12, 2),
            },
            "budget": budget,
            "within_budget": (total * 1.12) <= budget,
            "all_flight_options": valid_flights[:5],
            "all_hotel_options": valid_hotels[:5],
        }


# ============================================================================
# Domain Registration API
# ============================================================================

class DomainRegistrationAPI:
    """Domain availability check and registration.

    Environment variables:
        NAMECHEAP_API_USER — Namecheap API username
        NAMECHEAP_API_KEY — Namecheap API key
    """

    def __init__(self):
        self._user = _env("NAMECHEAP_API_USER")
        self._key = _env("NAMECHEAP_API_KEY")
        self._base = "https://api.namecheap.com/xml.response"

    def check_domain(self, domain: str) -> dict:
        """Check domain availability.

        Returns:
            Dict with domain, available (bool), price, registrar.
        """
        if self._user and self._key:
            return self._check_namecheap(domain)
        return self._check_whois(domain)

    def _check_namecheap(self, domain: str) -> dict:
        resp = _http_get(self._base, params={
            "ApiUser": self._user, "ApiKey": self._key,
            "UserName": self._user, "Command": "namecheap.domains.check",
            "DomainList": domain})
        if not resp.get("ok"):
            return {"domain": domain, "available": False, "error": resp.get("error")}
        data = resp.get("data", {})
        try:
            result = data.get("CommandResponse", {}).get(
                "DomainCheckResult", {"Domain": domain, "Available": "false"})
            available = result.get("@Available", "false") == "true"
            return {"domain": domain, "available": available,
                    "registrar": "namecheap"}
        except (KeyError, TypeError):
            return {"domain": domain, "available": False, "error": "Parse error"}

    def _check_whois(self, domain: str) -> dict:
        """Simple DNS-based availability check as fallback."""
        import socket
        try:
            socket.getaddrinfo(domain, None)
            return {"domain": domain, "available": False,
                    "registrar": "unknown", "method": "dns_lookup"}
        except socket.gaierror:
            return {"domain": domain, "available": True,
                    "registrar": "unknown", "method": "dns_lookup"}

    def register_domain(self, domain: str, years: int = 1) -> dict:
        """Register a domain via Namecheap.

        Returns:
            Dict with domain, registered, order_id, expiration.
        """
        if not (self._user and self._key):
            return {"domain": domain, "registered": False,
                    "error": "NAMECHEAP_API_USER and NAMECHEAP_API_KEY not configured"}
        resp = _http_post(self._base, json_body={
            "ApiUser": self._user, "ApiKey": self._key,
            "UserName": self._user, "Command": "namecheap.domains.create",
            "DomainName": domain, "Years": years,
            "RegistrantFirstName": "Autonomous",
            "RegistrantLastName": "Agent",
            "RegistrantEmailAddress": "agent@placeholder.local",
        })
        if resp.get("ok"):
            data = resp["data"]
            _audit_log({"action": "domain_registered", "domain": domain,
                        "years": years})
            return {"domain": domain, "registered": True,
                    "registrar": "namecheap", "years": years,
                    "details": data}
        _audit_log({"action": "domain_register_failed", "domain": domain,
                    "error": resp.get("error")})
        return {"domain": domain, "registered": False,
                "error": resp.get("error")}


# ============================================================================
# Price Monitor API
# ============================================================================

class PriceMonitorAPI:
    """Price tracking and alert system for products."""

    def __init__(self):
        self._tracking: dict[str, dict] = {}
        self._history: dict[str, list[dict]] = {}
        self._lock = threading.Lock()
        self._load_state()

    _STATE_DIR = os.path.join(os.path.dirname(__file__), ".workflow_data")
    _STATE_FILE = os.path.join(_STATE_DIR, "price_monitor.json")

    def _load_state(self):
        try:
            if os.path.exists(self._STATE_FILE):
                with open(self._STATE_FILE) as f:
                    state = json.load(f)
                self._tracking = state.get("tracking", {})
                self._history = state.get("history", {})
        except Exception:
            pass

    def _save_state(self):
        os.makedirs(self._STATE_DIR, exist_ok=True)
        with open(self._STATE_FILE, "w") as f:
            json.dump({"tracking": self._tracking,
                        "history": self._history}, f, indent=2, default=str)

    def track_price(self, product_url: str, target_price: float) -> dict:
        """Start tracking a product URL.

        Args:
            product_url: URL of the product to monitor.
            target_price: Desired price to trigger alert.

        Returns:
            Dict with tracking_id, product_url, target_price, status.
        """
        tracking_id = hashlib.md5(product_url.encode()).hexdigest()[:12]
        with self._lock:
            self._tracking[tracking_id] = {
                "url": product_url,
                "target_price": target_price,
                "created": datetime.now().isoformat(),
                "status": "active",
                "last_check": None,
                "last_price": None,
            }
            self._history.setdefault(tracking_id, [])
            self._save_state()
        _audit_log({"action": "price_tracking_started",
                     "tracking_id": tracking_id, "url": product_url,
                     "target": target_price})
        return {"tracking_id": tracking_id, "product_url": product_url,
                "target_price": target_price, "status": "active"}

    def get_price_history(self, product_url: str) -> list[dict]:
        """Return price history for a tracked product.

        Returns:
            List of dicts with timestamp, price, source.
        """
        tracking_id = hashlib.md5(product_url.encode()).hexdigest()[:12]
        return self._history.get(tracking_id, [])

    def check_prices(self) -> list[dict]:
        """Check all tracked products and update history.

        Returns:
            List of dicts for products that hit target price.
        """
        alerts = []
        for tid, info in self._tracking.items():
            if info.get("status") != "active":
                continue
            price = self._fetch_current_price(info["url"])
            if price is not None:
                entry = {"timestamp": datetime.now().isoformat(),
                         "price": price, "source": "live"}
                with self._lock:
                    self._history.setdefault(tid, []).append(entry)
                    info["last_check"] = entry["timestamp"]
                    info["last_price"] = price
                    self._save_state()
                if price <= info.get("target_price", float("inf")):
                    alerts.append({"tracking_id": tid, "url": info["url"],
                                   "current_price": price,
                                   "target_price": info["target_price"]})
        return alerts

    def _fetch_current_price(self, url: str) -> float | None:
        """Attempt to scrape current price from URL."""
        try:
            from web_automation import navigate, get_text
            navigate(url)
            time.sleep(2)
            text = get_text()
            price_match = re.search(r'\$[\d,]+\.?\d{0,2}', text)
            if price_match:
                return float(price_match.group().replace("$", "").replace(",", ""))
        except Exception as e:
            logger.warning("Price fetch failed for %s: %s", url, e)
        return None


# ============================================================================
# Transaction Confirmation Types
# ============================================================================

class TransactionType(str, Enum):
    FLIGHT_SEARCH = "flight_search"
    FLIGHT_BOOK = "flight_book"
    HOTEL_SEARCH = "hotel_search"
    HOTEL_BOOK = "hotel_book"
    PAYMENT_CREATE = "payment_create"
    PAYMENT_CONFIRM = "payment_confirm"
    DOMAIN_CHECK = "domain_check"
    DOMAIN_REGISTER = "domain_register"
    PRICE_TRACK = "price_track"
    TRIP_BOOK = "trip_book"


# Transactions that modify financial state and need user confirmation
FINANCIAL_TRANSACTIONS = {
    TransactionType.FLIGHT_BOOK,
    TransactionType.HOTEL_BOOK,
    TransactionType.PAYMENT_CREATE,
    TransactionType.PAYMENT_CONFIRM,
    TransactionType.DOMAIN_REGISTER,
    TransactionType.TRIP_BOOK,
}


# ============================================================================
# Economic Engine — Unified Orchestrator
# ============================================================================

class EconomicEngine:
    """Central coordinator for all economic API operations.

    Features:
    - Manages API instances and lazy initialization
    - Unified execute_transaction() entry point
    - Financial confirmation gating
    - Full audit trail logging
    - Graceful API key management
    """

    def __init__(self):
        self._flight_api: FlightAPI | None = None
        self._hotel_api: HotelAPI | None = None
        self._payment_api: PaymentAPI | None = None
        self._travel_api: TravelBookingAPI | None = None
        self._domain_api: DomainRegistrationAPI | None = None
        self._price_api: PriceMonitorAPI | None = None
        self._lock = threading.Lock()

    # -- Lazy singletons ----------------------------------------------------

    @property
    def flights(self) -> FlightAPI:
        if self._flight_api is None:
            with self._lock:
                if self._flight_api is None:
                    self._flight_api = FlightAPI()
        return self._flight_api

    @property
    def hotels(self) -> HotelAPI:
        if self._hotel_api is None:
            with self._lock:
                if self._hotel_api is None:
                    self._hotel_api = HotelAPI()
        return self._hotel_api

    @property
    def payments(self) -> PaymentAPI:
        if self._payment_api is None:
            with self._lock:
                if self._payment_api is None:
                    self._payment_api = PaymentAPI()
        return self._payment_api

    @property
    def travel(self) -> TravelBookingAPI:
        if self._travel_api is None:
            with self._lock:
                if self._travel_api is None:
                    self._travel_api = TravelBookingAPI(self.flights, self.hotels)
        return self._travel_api

    @property
    def domains(self) -> DomainRegistrationAPI:
        if self._domain_api is None:
            with self._lock:
                if self._domain_api is None:
                    self._domain_api = DomainRegistrationAPI()
        return self._domain_api

    @property
    def prices(self) -> PriceMonitorAPI:
        if self._price_api is None:
            with self._lock:
                if self._price_api is None:
                    self._price_api = PriceMonitorAPI()
        return self._price_api

    # -- API key status ------------------------------------------------------

    def api_status(self) -> dict:
        """Return which API integrations are configured."""
        return {
            "amadeus": bool(_env("AMADEUS_API_KEY") and _env("AMADEUS_API_SECRET")),
            "skyscanner": bool(_env("SKYSCANNER_API_KEY")),
            "stripe": bool(_env("STRIPE_SECRET_KEY")),
            "namecheap": bool(_env("NAMECHEAP_API_USER") and _env("NAMECHEAP_API_KEY")),
            "playwright_fallback": True,
        }

    # -- Confirmation check --------------------------------------------------

    @staticmethod
    def confirmation_required(txn_type: str) -> bool:
        """Check if a transaction type requires user confirmation before execution."""
        try:
            return TransactionType(txn_type) in FINANCIAL_TRANSACTIONS
        except ValueError:
            return False

    # -- Unified entry point -------------------------------------------------

    def execute_transaction(self, type: str, params: dict) -> dict:
        """Execute a transaction by type with unified error handling and audit.

        Args:
            type: Transaction type string (see TransactionType enum).
            params: Parameters specific to the transaction type.

        Returns:
            Result dict with 'ok' bool and type-specific data.
        """
        txn_type = type.lower().strip()
        _audit_log({"action": "transaction_attempt", "type": txn_type,
                     "params": _redact(params)})

        if self.confirmation_required(txn_type):
            _audit_log({"action": "confirmation_required", "type": txn_type})
            return {"ok": False, "requires_confirmation": True,
                    "message": f"Transaction '{txn_type}' requires explicit user confirmation",
                    "type": txn_type}

        dispatch = {
            "flight_search": self._exec_flight_search,
            "flight_book": self._exec_flight_book,
            "hotel_search": self._exec_hotel_search,
            "hotel_book": self._exec_hotel_book,
            "payment_create": self._exec_payment_create,
            "payment_confirm": self._exec_payment_confirm,
            "domain_check": self._exec_domain_check,
            "domain_register": self._exec_domain_register,
            "price_track": self._exec_price_track,
            "price_check": self._exec_price_check,
            "trip_book": self._exec_trip_book,
        }

        handler = dispatch.get(txn_type)
        if not handler:
            return {"ok": False, "error": f"Unknown transaction type: {txn_type}"}

        try:
            result = handler(params)
            _audit_log({"action": "transaction_completed", "type": txn_type,
                         "result_keys": list(result.keys()) if isinstance(result, dict) else []})
            return result
        except Exception as e:
            logger.error("Transaction %s failed: %s", txn_type, e)
            _audit_log({"action": "transaction_error", "type": txn_type, "error": str(e)})
            return {"ok": False, "error": str(e), "type": txn_type}

    # -- Individual handlers -------------------------------------------------

    def _exec_flight_search(self, p: dict) -> dict:
        flights = self.flights.search_flights(
            p["origin"], p["destination"], p["date"],
            p.get("return_date"), p.get("passengers", 1))
        return {"ok": True, "flights": flights, "count": len(flights)}

    def _exec_flight_book(self, p: dict) -> dict:
        details = self.flights.get_flight_details(p["flight_id"])
        return {"ok": True, "booking": details,
                "message": "Flight selected — proceed to payment to complete booking"}

    def _exec_hotel_search(self, p: dict) -> dict:
        hotels = self.hotels.search_hotels(
            p["location"], p["checkin"], p["checkout"],
            p.get("guests", 1))
        return {"ok": True, "hotels": hotels, "count": len(hotels)}

    def _exec_hotel_book(self, p: dict) -> dict:
        details = self.hotels.get_hotel_details(p["hotel_id"])
        return {"ok": True, "booking": details,
                "message": "Hotel selected — proceed to payment to complete booking"}

    def _exec_payment_create(self, p: dict) -> dict:
        return self.payments.create_payment_intent(
            p["amount"], p.get("currency", "usd"), p.get("description", ""))

    def _exec_payment_confirm(self, p: dict) -> dict:
        return self.payments.confirm_payment(p["payment_id"])

    def _exec_domain_check(self, p: dict) -> dict:
        return self.domains.check_domain(p["domain"])

    def _exec_domain_register(self, p: dict) -> dict:
        return self.domains.register_domain(p["domain"], p.get("years", 1))

    def _exec_price_track(self, p: dict) -> dict:
        return self.prices.track_price(p["product_url"], p["target_price"])

    def _exec_price_check(self, p: dict) -> dict:
        alerts = self.prices.check_prices()
        return {"ok": True, "alerts": alerts, "alert_count": len(alerts)}

    def _exec_trip_book(self, p: dict) -> dict:
        result = self.travel.book_trip(
            p["origin"], p["destination"], p["dates"], p["budget"])
        return {"ok": True, **result}


# ============================================================================
# Module-level singleton
# ============================================================================

engine = EconomicEngine()
