"""JARVIS Autonomous Value-Creation Pipeline — Opportunity Scanner.

Scans digital marketplaces for high-demand, low-competition niches.
Part of the 4-stage Money-Maker Agent Engine.
"""

import os, sys, time, json, subprocess, threading, logging, re
from pathlib import Path

log = logging.getLogger("opportunity_scanner")

sys.path.insert(0, os.path.dirname(__file__))


class OpportunityScanner:
    """Scans digital marketplaces to find profitable micro-niches."""

    def __init__(self):
        self.running = False
        self.opportunities = []
        self._lock = threading.Lock()

    def scan_all(self) -> list:
        """Run all scanners and return combined opportunities."""
        self.running = True
        self.opportunities = []

        def _run():
            try:
                # Scan multiple sources
                self._scan_gumroad_trends()
                self._scan_github_trending()
                self._scan_product_hunt()
                self._scan_etsy_digital()
                self._scan_envato_market()
                self._analyze_gaps()

                log.warning(f"Scan complete: {len(self.opportunities)} opportunities found")
            except Exception as e:
                log.error(f"Scan error: {e}")
            finally:
                self.running = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return []

    def _scan_gumroad_trends(self):
        """Scan Gumroad for trending digital products."""
        log.warning("Scanning Gumroad trends...")
        try:
            from groq_agent import generate as groq_gen
            reply = groq_gen(
                "List the top 10 trending digital product niches on Gumroad in 2025-2026. "
                "For each, give: niche name, estimated monthly revenue, competition level (low/medium/high), "
                "and what format the product is (PDF, template, course, software, etc). "
                "Return as JSON array.",
                max_tokens=2000, temperature=0.3
            )
            if reply:
                m = re.search(r'\[.*\]', reply, re.DOTALL)
                if m:
                    items = json.loads(m.group())
                    for item in items:
                        item["source"] = "gumroad"
                        item["priority"] = self._calc_priority(item)
                    with self._lock:
                        self.opportunities.extend(items)
        except Exception as e:
            log.warning(f"Gumroad scan failed: {e}")

    def _scan_github_trending(self):
        """Scan GitHub trending for developer tools and scripts."""
        log.warning("Scanning GitHub trends...")
        try:
            from groq_agent import generate as groq_gen
            reply = groq_gen(
                "List the top 10 trending GitHub repositories that could be monetized as "
                "developer tools, CLI utilities, or code templates in 2025-2026. "
                "For each: name, stars, description, monetization potential (low/medium/high), "
                "suggested product format (plugin, template, course, SaaS). "
                "Return as JSON array.",
                max_tokens=2000, temperature=0.3
            )
            if reply:
                m = re.search(r'\[.*\]', reply, re.DOTALL)
                if m:
                    items = json.loads(m.group())
                    for item in items:
                        item["source"] = "github"
                        item["priority"] = self._calc_priority(item)
                    with self._lock:
                        self.opportunities.extend(items)
        except Exception as e:
            log.warning(f"GitHub scan failed: {e}")

    def _scan_product_hunt(self):
        """Scan Product Hunt for new product ideas."""
        log.warning("Scanning Product Hunt...")
        try:
            from groq_agent import generate as groq_gen
            reply = groq_gen(
                "List the top 10 Product Hunt launches in 2025-2026 that represent "
                "replicable micro-SaaS or digital product opportunities. "
                "For each: name, category, upvotes, monetization model, "
                "competition level, suggested price point. "
                "Return as JSON array.",
                max_tokens=2000, temperature=0.3
            )
            if reply:
                m = re.search(r'\[.*\]', reply, re.DOTALL)
                if m:
                    items = json.loads(m.group())
                    for item in items:
                        item["source"] = "producthunt"
                        item["priority"] = self._calc_priority(item)
                    with self._lock:
                        self.opportunities.extend(items)
        except Exception as e:
            log.warning(f"Product Hunt scan failed: {e}")

    def _scan_etsy_digital(self):
        """Scan Etsy digital downloads market."""
        log.warning("Scanning Etsy digital market...")
        try:
            from groq_agent import generate as groq_gen
            reply = groq_gen(
                "List the top 10 bestselling digital download niches on Etsy in 2025-2026. "
                "For each: niche name, estimated monthly sales, average price, "
                "competition level, product format (PDF, SVG, template, etc). "
                "Return as JSON array.",
                max_tokens=2000, temperature=0.3
            )
            if reply:
                m = re.search(r'\[.*\]', reply, re.DOTALL)
                if m:
                    items = json.loads(m.group())
                    for item in items:
                        item["source"] = "etsy"
                        item["priority"] = self._calc_priority(item)
                    with self._lock:
                        self.opportunities.extend(items)
        except Exception as e:
            log.warning(f"Etsy scan failed: {e}")

    def _scan_envato_market(self):
        """Scan Envato/ThemeForest for template opportunities."""
        log.warning("Scanning Envato market...")
        try:
            from groq_agent import generate as groq_gen
            reply = groq_gen(
                "List the top 10 digital product niches on Envato Market (ThemeForest, "
                "CodeCanyon, GraphicRiver) with low competition in 2025-2026. "
                "For each: niche name, price range, competition level, "
                "monetization potential, suggested product type. "
                "Return as JSON array.",
                max_tokens=2000, temperature=0.3
            )
            if reply:
                m = re.search(r'\[.*\]', reply, re.DOTALL)
                if m:
                    items = json.loads(m.group())
                    for item in items:
                        item["source"] = "envato"
                        item["priority"] = self._calc_priority(item)
                    with self._lock:
                        self.opportunities.extend(items)
        except Exception as e:
            log.warning(f"Envato scan failed: {e}")

    def _analyze_gaps(self):
        """Analyze gaps between high demand and low supply."""
        log.warning("Analyzing market gaps...")
        with self._lock:
            # Sort by priority
            self.opportunities.sort(key=lambda x: x.get("priority", 0), reverse=True)

    def _calc_priority(self, item: dict) -> float:
        """Calculate priority score based on demand vs competition."""
        score = 50.0

        # Revenue potential
        revenue = str(item.get("estimated_monthly_revenue", item.get("revenue", ""))).lower()
        if "high" in revenue or "$10k" in revenue or "10,000" in revenue:
            score += 20
        elif "medium" in revenue or "$5k" in revenue:
            score += 10

        # Competition (lower is better)
        competition = str(item.get("competition_level", item.get("competition", ""))).lower()
        if "low" in competition:
            score += 25
        elif "medium" in competition:
            score += 10
        elif "high" in competition:
            score -= 15

        # Monetization potential
        potential = str(item.get("monetization_potential", "")).lower()
        if "high" in potential:
            score += 15
        elif "medium" in potential:
            score += 5

        return min(score, 100)

    def get_top_opportunities(self, n: int = 10) -> list:
        """Get top N opportunities sorted by priority."""
        with self._lock:
            return sorted(self.opportunities, key=lambda x: x.get("priority", 0), reverse=True)[:n]

    def stop(self):
        self.running = False


# ── Singleton ──
_scanner = None
def get_opportunity_scanner() -> OpportunityScanner:
    global _scanner
    if _scanner is None:
        _scanner = OpportunityScanner()
    return _scanner
