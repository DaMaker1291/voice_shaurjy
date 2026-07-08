#!/usr/bin/env python3
"""
Resource Governor for JARVIS
Assesses system capabilities and enforces safe limits so agents never crash the user's machine.
"""
import os
import sys
import time
import psutil
import threading
from typing import Dict, Any, Optional

class ResourceGovernor:
    """
    Monitors system resources and enforces limits:
    - Max parallel agents based on RAM
    - Browser memory cap
    - CPU throttling when under load
    - Auto-pause agents when user needs resources
    """

    # Tier definitions based on available RAM
    TIERS = {
        "potato": {"min_ram_gb": 0, "max_agents": 1, "max_browser_mb": 150, "ocr": False, "headless": False},
        "low":    {"min_ram_gb": 4, "max_agents": 1, "max_browser_mb": 300, "ocr": False, "headless": True},
        "mid":    {"min_ram_gb": 8, "max_agents": 2, "max_browser_mb": 500, "ocr": True, "headless": True},
        "high":   {"min_ram_gb": 16, "max_agents": 3, "max_browser_mb": 800, "ocr": True, "headless": True},
        "ultra":  {"min_ram_gb": 32, "max_agents": 5, "max_browser_mb": 1200, "ocr": True, "headless": True},
    }

    # Safety thresholds
    RAM_WARNING_PERCENT = 75    # Warn when RAM usage exceeds this
    RAM_DANGER_PERCENT = 85     # Pause agents when RAM exceeds this
    CPU_WARNING_PERCENT = 80    # Warn when CPU exceeds this
    CPU_DANGER_PERCENT = 90     # Throttle when CPU exceeds this
    BROWSER_IDLE_KILL_SECONDS = 120  # Kill browser if idle for 2 minutes

    def __init__(self):
        self.tier = "mid"  # Default
        self.limits = self.TIERS["mid"]
        self._monitor_thread = None
        self._running = False
        self._last_browser_use = 0
        self._agents_paused = False
        self._system_info = {}
        self._lock = threading.Lock()

    def assess(self) -> Dict[str, Any]:
        """Assess system capabilities and return tier + limits."""
        try:
            mem = psutil.virtual_memory()
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            disk = psutil.disk_usage('/')

            ram_gb = mem.total / (1024 ** 3)
            available_gb = mem.available / (1024 ** 3)

            # Determine tier
            self.tier = "potato"
            for tier_name, tier_config in sorted(self.TIERS.items(), key=lambda x: x[1]["min_ram_gb"], reverse=True):
                if ram_gb >= tier_config["min_ram_gb"]:
                    self.tier = tier_name
                    self.limits = tier_config
                    break

            self._system_info = {
                "ram_total_gb": round(ram_gb, 1),
                "ram_available_gb": round(available_gb, 1),
                "ram_used_percent": mem.percent,
                "cpu_count": cpu_count,
                "cpu_freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "disk_free_gb": round(disk.free / (1024 ** 3), 1),
                "tier": self.tier,
                "limits": self.limits,
                "platform": sys.platform,
                "pid": os.getpid(),
            }

            return self._system_info

        except Exception as e:
            # Fallback if psutil fails
            self.tier = "low"
            self.limits = self.TIERS["low"]
            return {
                "tier": "low",
                "limits": self.limits,
                "error": str(e),
                "platform": sys.platform,
            }

    def get_status(self) -> Dict[str, Any]:
        """Get current resource status."""
        try:
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.2)

            return {
                "tier": self.tier,
                "limits": self.limits,
                "ram_percent": mem.percent,
                "ram_available_mb": round(mem.available / (1024 ** 2)),
                "cpu_percent": cpu,
                "agents_paused": self._agents_paused,
                "browser_active": self._is_browser_active(),
                "warnings": self._get_warnings(mem.percent, cpu),
            }
        except:
            return {"tier": self.tier, "limits": self.limits}

    def _get_warnings(self, ram_percent: float, cpu_percent: float) -> list:
        """Get active warnings."""
        warnings = []
        if ram_percent > self.RAM_DANGER_PERCENT:
            warnings.append({"level": "danger", "message": f"RAM critical: {ram_percent}%", "action": "pausing_agents"})
        elif ram_percent > self.RAM_WARNING_PERCENT:
            warnings.append({"level": "warning", "message": f"RAM high: {ram_percent}%"})

        if cpu_percent > self.CPU_DANGER_PERCENT:
            warnings.append({"level": "danger", "message": f"CPU critical: {cpu_percent}%", "action": "throttling"})
        elif cpu_percent > self.CPU_WARNING_PERCENT:
            warnings.append({"level": "warning", "message": f"CPU high: {cpu_percent}%"})

        return warnings

    def can_start_agent(self) -> Dict[str, Any]:
        """Check if we can safely start a new agent."""
        try:
            mem = psutil.virtual_memory()
            active_agents = self._count_active_agents()

            # Check RAM
            if mem.percent > self.RAM_DANGER_PERCENT:
                return {
                    "allowed": False,
                    "reason": f"RAM too high ({mem.percent}%)",
                    "suggestion": "Wait for current agents to finish",
                }

            # Check agent count
            if active_agents >= self.limits["max_agents"]:
                return {
                    "allowed": False,
                    "reason": f"Max agents reached ({self.limits['max_agents']})",
                    "suggestion": "Stop an existing agent first",
                }

            # Check CPU
            cpu = psutil.cpu_percent(interval=0.2)
            if cpu > self.CPU_DANGER_PERCENT:
                return {
                    "allowed": False,
                    "reason": f"CPU too high ({cpu}%)",
                    "suggestion": "Wait for CPU load to decrease",
                }

            return {
                "allowed": True,
                "active_agents": active_agents,
                "max_agents": self.limits["max_agents"],
                "ram_available_mb": round(mem.available / (1024 ** 2)),
            }

        except:
            return {"allowed": True, "reason": "Could not check resources"}

    def _count_active_agents(self) -> int:
        """Count currently running agent processes."""
        try:
            count = 0
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    name = proc.info['name'] or ''
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'chrome' in name.lower() or 'chromium' in name.lower():
                        count += 1
                except:
                    continue
            return min(count, self.limits["max_agents"])
        except:
            return 0

    def _is_browser_active(self) -> bool:
        """Check if headless browser is running."""
        try:
            for proc in psutil.process_iter(['name']):
                name = (proc.info['name'] or '').lower()
                if 'chrome' in name:
                    return True
        except:
            pass
        return False

    def start_monitoring(self, interval: float = 10):
        """Start background resource monitoring."""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._running = False

    def _monitor_loop(self, interval: float):
        """Background monitoring loop."""
        while self._running:
            try:
                mem = psutil.virtual_memory()
                cpu = psutil.cpu_percent(interval=0.2)

                # Auto-pause agents if system is struggling
                if mem.percent > self.RAM_DANGER_PERCENT and not self._agents_paused:
                    self._agents_paused = True
                    self._pause_all_agents()
                elif mem.percent < self.RAM_WARNING_PERCENT and self._agents_paused:
                    self._agents_paused = False
                    self._resume_all_agents()

                # Auto-kill idle browser
                if self._is_browser_active():
                    if time.time() - self._last_browser_use > self.BROWSER_IDLE_KILL_SECONDS:
                        self._kill_idle_browser()

                time.sleep(interval)
            except:
                time.sleep(interval)

    def _pause_all_agents(self):
        """Pause all running agents to free resources."""
        # Signal to the autonomous loop to pause
        try:
            from autonomous_loop import get_task_loop
            loop = get_task_loop()
            for task_id, task in loop.active_tasks.items():
                if task["status"] == "running":
                    task["paused"] = True
        except:
            pass

    def _resume_all_agents(self):
        """Resume paused agents."""
        try:
            from autonomous_loop import get_task_loop
            loop = get_task_loop()
            for task_id, task in loop.active_tasks.items():
                if task.get("paused"):
                    task["paused"] = False
        except:
            pass

    def _kill_idle_browser(self):
        """Kill idle browser to free memory."""
        try:
            from headless_browser import get_browser
            browser = get_browser()
            if browser._is_alive():
                browser.stop()
        except:
            pass

    def mark_browser_used(self):
        """Mark that browser was just used (reset idle timer)."""
        self._last_browser_use = time.time()

    def should_use_ocr(self) -> bool:
        """Check if OCR is safe to use on this system."""
        if not self.limits.get("ocr", False):
            return False
        try:
            mem = psutil.virtual_memory()
            return mem.percent < self.RAM_WARNING_PERCENT
        except:
            return False

    def get_recommended_settings(self) -> Dict[str, Any]:
        """Get recommended settings for this system."""
        return {
            "tier": self.tier,
            "max_parallel_agents": self.limits["max_agents"],
            "headless_browser": self.limits["headless"],
            "ocr_enabled": self.limits["ocr"],
            "browser_memory_cap_mb": self.limits["max_browser_mb"],
            "auto_pause_on_high_ram": True,
            "browser_idle_kill_seconds": self.BROWSER_IDLE_KILL_SECONDS,
            "suggestions": self._get_tier_suggestions(),
        }

    def _get_tier_suggestions(self) -> list:
        """Get suggestions based on system tier."""
        suggestions = {
            "potato": [
                "Using cloud-only mode (no local browser)",
                "Chat and device control only",
                "Agents run on HF Space, not your machine",
            ],
            "low": [
                "Single agent at a time",
                "Browser auto-kills after 2 min idle",
                "OCR disabled to save memory",
            ],
            "mid": [
                "Up to 2 parallel agents",
                "Browser and basic OCR available",
                "Good balance of speed and safety",
            ],
            "high": [
                "Up to 3 parallel agents",
                "Full OCR and browser support",
                "Fast agent execution",
            ],
            "ultra": [
                "Up to 5 parallel agents",
                "All features enabled",
                "Maximum performance",
            ],
        }
        return suggestions.get(self.tier, [])


# Singleton
_governor = None

def get_governor() -> ResourceGovernor:
    global _governor
    if _governor is None:
        _governor = ResourceGovernor()
    return _governor

def assess_system() -> Dict[str, Any]:
    """Quick system assessment."""
    return get_governor().assess()
