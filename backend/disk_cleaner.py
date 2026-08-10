#!/usr/bin/env python3
"""
Disk Cleaner for JARVIS
Scans for unnecessary files, shows what can be cleaned,
asks user before deleting anything.
"""
import os
import shutil
import subprocess
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List

log = logging.getLogger("jarvis-disk-cleaner")


class DiskCleaner:
    """
    Scans system for:
    - Browser cache files (Chrome, Firefox, Safari, Edge)
    - System and app caches
    - Log files
    - Old downloads (age-based filtering)
    - Empty folders
    - Large temp files
    - npm/pip/yarn caches
    Shows sizes, asks before cleaning.
    """

    CACHE_DIRS = {
        "~/Library/Caches": "macOS System Caches",
        "~/.cache": "User Cache",
        "~/.npm/_cacache": "npm Cache",
        "~/.yarn/cache": "Yarn Cache",
        "~/.pip/cache": "pip Cache",
        "~/.gradle/caches": "Gradle Cache",
        "~/.m2/repository": "Maven Cache",
        "~/.nuget/packages": "NuGet Cache",
        "~/.cargo/registry/cache": "Cargo Cache",
        "~/.pub-cache": "Dart/Flutter Cache",
        "Library/Caches": "App Caches (cwd)",
    }

    LOG_DIRS = {
        "~/Library/Logs": "macOS System Logs",
        "/var/log": "System Logs",
        "~/.npm/_logs": "npm Logs",
        "~/Library/Logs/DiagnosticReports": "Crash Reports",
        "~/Library/Logs/CrashReporter": "Crash Reporter",
    }

    TEMP_DIRS = {
        "/tmp": "System Temp",
        "~/Library/TemporaryFiles": "App Temp",
    }

    def __init__(self):
        self._pending_clean = {}  # scan_id -> pending items

    def scan_all(self) -> Dict[str, Any]:
        """Full system scan. Returns categories with sizes."""
        results = {
            "caches": self._scan_dirs(self.CACHE_DIRS),
            "browser_caches": self._scan_browser_caches(),
            "logs": self._scan_dirs(self.LOG_DIRS),
            "temp": self._scan_dirs(self.TEMP_DIRS),
            "large_downloads": self._scan_large_downloads(),
            "old_downloads": self._scan_old_downloads(days=30),
            "old_docker": self._scan_docker(),
            "empty_folders": self._scan_empty_folders(),
        }

        total_bytes = sum(cat.get("total_bytes", 0) for cat in results.values() if isinstance(cat, dict))
        results["total_bytes"] = total_bytes
        results["total_human"] = self._human_size(total_bytes)
        results["scan_id"] = str(int(time.time()))

        # Store for confirmation
        self._pending_clean[results["scan_id"]] = results

        return results

    def _scan_browser_caches(self) -> Dict[str, Any]:
        """Scan browser-specific cache directories."""
        import sys
        items = []
        total_bytes = 0
        home = os.path.expanduser("~")

        if sys.platform == "darwin":
            browser_paths = {
                f"{home}/Library/Caches/Google/Chrome": "Chrome Cache",
                f"{home}/Library/Caches/Firefox": "Firefox Cache",
                f"{home}/Library/Caches/com.apple.Safari": "Safari Cache",
                f"{home}/Library/Caches/com.microsoft.edgemac": "Edge Cache",
                f"{home}/Library/Caches/BraveSoftware": "Brave Cache",
            }
        elif sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA", "")
            browser_paths = {
                f"{local}/Google/Chrome/User Data/Default/Cache": "Chrome Cache",
                f"{local}/Google/Chrome/User Data/Default/Code Cache": "Chrome Code Cache",
                f"{local}/Mozilla/Firefox": "Firefox Cache",
                f"{local}/Microsoft/Edge/User Data/Default/Cache": "Edge Cache",
                f"{local}/BraveSoftware/Brave-Browser/User Data/Default/Cache": "Brave Cache",
            }
        else:
            browser_paths = {
                f"{home}/.cache/google-chrome": "Chrome Cache",
                f"{home}/.cache/mozilla/firefox": "Firefox Cache",
                f"{home}/.cache/microsoft-edge": "Edge Cache",
                f"{home}/.cache/BraveSoftware": "Brave Cache",
            }

        for path, label in browser_paths.items():
            if not os.path.exists(path):
                continue
            try:
                size = self._get_dir_size(path)
                file_count = self._count_files_recursive(path)
                items.append({
                    "path": path,
                    "label": label,
                    "bytes": size,
                    "human": self._human_size(size),
                    "files": file_count,
                })
                total_bytes += size
            except (OSError, PermissionError):
                continue

        return {
            "items": sorted(items, key=lambda x: x["bytes"], reverse=True),
            "total_bytes": total_bytes,
            "total_human": self._human_size(total_bytes),
        }

    def _scan_dirs(self, dir_map: Dict[str, str]) -> Dict[str, Any]:
        """Scan a map of directories and return sizes."""
        items = []
        total_bytes = 0

        for path_template, label in dir_map.items():
            path = os.path.expanduser(path_template)
            if not os.path.exists(path):
                continue

            try:
                size = self._get_dir_size(path)
                file_count = self._count_files_recursive(path)
                items.append({
                    "path": path,
                    "label": label,
                    "bytes": size,
                    "human": self._human_size(size),
                    "files": file_count,
                })
                total_bytes += size
            except (OSError, PermissionError):
                continue

        return {"items": sorted(items, key=lambda x: x["bytes"], reverse=True), "total_bytes": total_bytes, "total_human": self._human_size(total_bytes)}

    def _scan_large_downloads(self, min_size_mb: int = 100) -> Dict[str, Any]:
        """Scan for large files in ~/Downloads."""
        downloads = os.path.expanduser("~/Downloads")
        items = []

        if os.path.exists(downloads):
            for entry in os.scandir(downloads):
                if entry.is_file():
                    try:
                        size = entry.stat().st_size
                        if size > min_size_mb * 1024 * 1024:
                            items.append({
                                "path": entry.path,
                                "name": entry.name,
                                "bytes": size,
                                "human": self._human_size(size),
                                "modified": entry.stat().st_mtime,
                            })
                    except (OSError, PermissionError):
                        continue

        items.sort(key=lambda x: x["bytes"], reverse=True)
        total = sum(i["bytes"] for i in items)
        return {"items": items[:20], "total_bytes": total, "total_human": self._human_size(total)}

    def _scan_old_downloads(self, days: int = 30) -> Dict[str, Any]:
        """Scan for downloads older than N days."""
        import time as _time
        downloads = os.path.expanduser("~/Downloads")
        items = []
        now = _time.time()
        cutoff = now - (days * 86400)

        if os.path.exists(downloads):
            for entry in os.scandir(downloads):
                if entry.is_file():
                    try:
                        mtime = entry.stat().st_mtime
                        if mtime < cutoff:
                            size = entry.stat().st_size
                            age_days = int((now - mtime) / 86400)
                            items.append({
                                "path": entry.path,
                                "name": entry.name,
                                "bytes": size,
                                "human": self._human_size(size),
                                "age_days": age_days,
                                "modified": mtime,
                            })
                    except (OSError, PermissionError):
                        continue

        items.sort(key=lambda x: x["bytes"], reverse=True)
        total = sum(i["bytes"] for i in items)
        return {"items": items[:30], "total_bytes": total, "total_human": self._human_size(total), "days_threshold": days}

    def _scan_docker(self) -> Dict[str, Any]:
        """Scan Docker images/containers."""
        try:
            result = subprocess.run(
                ["docker", "system", "df", "--format", "{{.Reclaimable}}\t{{.Size}}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return {"status": "available", "output": result.stdout.strip()}
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return {"status": "unavailable"}

    def _scan_empty_folders(self) -> Dict[str, Any]:
        """Scan common locations for empty folders."""
        scan_paths = [
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Downloads"),
        ]

        empty = []
        for base in scan_paths:
            if not os.path.exists(base):
                continue
            try:
                for root, dirs, files in os.walk(base):
                    if not dirs and not files:
                        empty.append(root)
                    if len(empty) > 50:
                        break
            except (OSError, PermissionError):
                continue

        return {"items": empty[:50], "count": len(empty)}

    def clean_category(self, scan_id: str, category: str, confirm: bool = False) -> Dict[str, Any]:
        """Clean a specific category. Requires confirm=True."""
        if not confirm:
            return {"error": "Set confirm=true to proceed with cleaning"}

        if scan_id not in self._pending_clean:
            return {"error": "Scan expired. Run scan again."}

        scan = self._pending_clean[scan_id]
        if category not in scan:
            return {"error": f"Unknown category: {category}"}

        items = scan[category].get("items", [])
        cleaned = []
        errors = []
        total_freed = 0

        for item in items:
            path = item.get("path", "")
            if not path or not os.path.exists(path):
                continue

            try:
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    os.remove(path)
                    total_freed += size
                    cleaned.append({"path": path, "freed": self._human_size(size)})
                elif os.path.isdir(path):
                    size = self._get_dir_size(path)
                    shutil.rmtree(path)
                    total_freed += size
                    cleaned.append({"path": path, "freed": self._human_size(size)})
            except Exception as e:
                errors.append({"path": path, "error": str(e)})

        # Clean pending
        del self._pending_clean[scan_id]

        return {
            "cleaned": len(cleaned),
            "errors": len(errors),
            "freed": self._human_size(total_freed),
            "details": cleaned[:10],
            "error_details": errors[:5],
        }

    def clean_cache(self, path: str, confirm: bool = False) -> Dict[str, Any]:
        """Clean a specific cache directory."""
        if not confirm:
            return {"error": "Set confirm=true to proceed", "path": path}

        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return {"error": "Path not found"}

        try:
            size = self._get_dir_size(path)
            shutil.rmtree(path)
            return {"status": "cleaned", "path": path, "freed": self._human_size(size)}
        except Exception as e:
            return {"error": str(e)}

    def get_disk_usage(self) -> Dict[str, Any]:
        """Get overall disk usage."""
        try:
            usage = shutil.disk_usage("/")
            return {
                "total": self._human_size(usage.total),
                "used": self._human_size(usage.used),
                "free": self._human_size(usage.free),
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception as e:
            return {"error": str(e)}

    def suggest_cleaning(self) -> List[Dict[str, Any]]:
        """Suggest what to clean based on size."""
        suggestions = []
        scan = self.scan_all()

        for category in ["caches", "browser_caches", "logs", "temp"]:
            data = scan.get(category, {})
            if isinstance(data, dict) and data.get("total_bytes", 0) > 50 * 1024 * 1024:  # > 50MB
                suggestions.append({
                    "category": category,
                    "size": data["total_human"],
                    "items": len(data.get("items", [])),
                    "recommendation": f"Clean {category} — {data['total_human']} used",
                })

        if scan.get("large_downloads", {}).get("total_bytes", 0) > 500 * 1024 * 1024:
            suggestions.append({
                "category": "large_downloads",
                "size": scan["large_downloads"]["total_human"],
                "items": len(scan["large_downloads"].get("items", [])),
                "recommendation": f"Review large downloads — {scan['large_downloads']['total_human']}",
            })

        old_downloads = scan.get("old_downloads", {})
        if old_downloads.get("total_bytes", 0) > 100 * 1024 * 1024:
            suggestions.append({
                "category": "old_downloads",
                "size": old_downloads["total_human"],
                "items": len(old_downloads.get("items", [])),
                "recommendation": f"Review old downloads (>{old_downloads.get('days_threshold', 30)} days) — {old_downloads['total_human']}",
            })

        return suggestions

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_dir_size(self, path: str) -> int:
        """Get total size of a directory."""
        total = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += self._get_dir_size(entry.path)
        except (OSError, PermissionError):
            pass
        return total

    def _count_files_recursive(self, path: str) -> int:
        """Count files recursively in a directory."""
        count = 0
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    count += 1
                elif entry.is_dir(follow_symlinks=False):
                    count += self._count_files_recursive(entry.path)
        except (OSError, PermissionError):
            pass
        return count

    def _human_size(self, size_bytes: int) -> str:
        """Convert bytes to human readable."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"


# Singleton
_cleaner = None

def get_cleaner() -> DiskCleaner:
    global _cleaner
    if _cleaner is None:
        _cleaner = DiskCleaner()
    return _cleaner
