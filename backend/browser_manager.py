#!/usr/bin/env python3
"""
Smart Browser Manager for JARVIS
Pools headless browser instances, enforces limits based on system tier,
auto-kills idle browsers, and manages memory per browser.
"""
import os
import time
import threading
import psutil
from typing import Dict, Any, Optional

class SmartBrowserManager:
    """
    Manages headless browser instances with resource awareness:
    - Max browsers based on system tier
    - Auto-kill after idle timeout
    - Memory cap per browser
    - Graceful shutdown on high memory
    """

    IDLE_KILL_SECONDS = 120  # Kill browser after 2 min idle
    MEMORY_CHECK_INTERVAL = 15  # Check memory every 15s

    def __init__(self):
        self._browsers: Dict[str, dict] = {}  # browser_id -> info
        self._lock = threading.Lock()
        self._last_use: Dict[str, float] = {}
        self._monitor_thread = None
        self._running = False

    def get_max_browsers(self) -> int:
        """Get max browsers allowed based on system tier."""
        try:
            from resource_governor import get_governor
            return get_governor().limits.get("max_browser_mb", 300) // 300  # rough count
        except:
            # Fallback: check RAM
            try:
                mem = psutil.virtual_memory()
                gb = mem.total / (1024 ** 3)
                if gb >= 16: return 3
                if gb >= 8: return 2
                if gb >= 4: return 1
                return 0  # No browser on potato tier
            except:
                return 1

    def can_start_browser(self) -> Dict[str, Any]:
        """Check if we can safely start a new browser."""
        max_b = self.get_max_browsers()
        active = self._count_active()

        if active >= max_b:
            return {"allowed": False, "reason": f"Max browsers ({max_b}) reached", "active": active}

        try:
            mem = psutil.virtual_memory()
            if mem.percent > 85:
                return {"allowed": False, "reason": f"RAM too high ({mem.percent}%)", "active": active}
        except:
            pass

        return {"allowed": True, "active": active, "max": max_b}

    def register_browser(self, browser_id: str, info: dict = None):
        """Register a browser as active."""
        with self._lock:
            self._browsers[browser_id] = {
                "started_at": time.time(),
                "info": info or {},
            }
            self._last_use[browser_id] = time.time()

    def mark_used(self, browser_id: str):
        """Mark browser as recently used."""
        self._last_use[browser_id] = time.time()

    def unregister_browser(self, browser_id: str):
        """Remove browser from tracking."""
        with self._lock:
            self._browsers.pop(browser_id, None)
            self._last_use.pop(browser_id, None)

    def _count_active(self) -> int:
        with self._lock:
            return len(self._browsers)

    def start_monitoring(self, interval: float = None):
        """Start background monitoring of browser idle times."""
        if interval is None:
            interval = self.MEMORY_CHECK_INTERVAL
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        self._running = False

    def _monitor_loop(self, interval: float):
        """Auto-kill idle browsers."""
        while self._running:
            try:
                now = time.time()
                to_kill = []

                with self._lock:
                    for bid, last_used in list(self._last_use.items()):
                        idle_time = now - last_used
                        if idle_time > self.IDLE_KILL_SECONDS:
                            to_kill.append(bid)

                for bid in to_kill:
                    self._kill_browser(bid)

                # Also check total browser memory
                self._check_browser_memory()

                time.sleep(interval)
            except:
                time.sleep(interval)

    def _kill_browser(self, browser_id: str):
        """Kill a specific browser instance."""
        try:
            from headless_browser import get_browser
            browser = get_browser()
            if browser._is_alive():
                browser.stop()
            self.unregister_browser(browser_id)
        except:
            self.unregister_browser(browser_id)

    def _check_browser_memory(self):
        """Kill browsers if total memory is too high."""
        try:
            from resource_governor import get_governor
            governor = get_governor()
            max_mb = governor.limits.get("max_browser_mb", 300)

            total_browser_mb = 0
            for proc in psutil.process_iter(['name', 'memory_info']):
                try:
                    name = (proc.info['name'] or '').lower()
                    if 'chrome' in name or 'chromium' in name:
                        total_browser_mb += proc.info['memory_info'].rss / (1024 ** 2)
                except:
                    continue

            if total_browser_mb > max_mb:
                # Kill oldest browser
                with self._lock:
                    oldest = min(self._last_use.items(), key=lambda x: x[1]) if self._last_use else None
                if oldest:
                    self._kill_browser(oldest[0])
        except:
            pass

    def kill_all(self):
        """Kill all tracked browsers."""
        with self._lock:
            for bid in list(self._browsers.keys()):
                self._kill_browser(bid)

    def get_status(self) -> Dict[str, Any]:
        """Get browser manager status."""
        with self._lock:
            browsers = dict(self._browsers)

        browser_mem = 0
        for proc in psutil.process_iter(['name', 'memory_info']):
            try:
                name = (proc.info['name'] or '').lower()
                if 'chrome' in name or 'chromium' in name:
                    browser_mem += proc.info['memory_info'].rss / (1024 ** 2)
            except:
                continue

        return {
            "active_browsers": len(browsers),
            "max_browsers": self.get_max_browsers(),
            "browser_memory_mb": round(browser_mem, 1),
            "idle_kill_seconds": self.IDLE_KILL_SECONDS,
            "oldest_idle": self._get_oldest_idle(),
        }

    def _get_oldest_idle(self) -> Optional[float]:
        """Get seconds since oldest browser was last used."""
        if not self._last_use:
            return None
        oldest = min(self._last_use.values())
        return round(time.time() - oldest, 1)


# Singleton
_manager = None

def get_browser_manager() -> SmartBrowserManager:
    global _manager
    if _manager is None:
        _manager = SmartBrowserManager()
    return _manager
