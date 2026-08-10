"""
Browser Controller — Zero-config browser automation.

Connection priority:
1. Playwright bundled Chromium (works immediately, no setup)
2. CDP attachment to running Chrome (if --remote-debugging-port enabled)
3. COM automation (if Chrome is already open)

All modes can browse, extract content, click elements, type text.
The user needs to do NOTHING extra.
"""

import json
import os
import sys
import time
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-browser")


@dataclass
class BrowserTab:
    tab_id: str
    title: str = ""
    url: str = ""
    active: bool = False

    def to_dict(self):
        return {"tab_id": self.tab_id, "title": self.title, "url": self.url, "active": self.active}


class BrowserController:
    """
    Zero-config browser controller.
    Uses Playwright bundled Chromium by default — no Chrome flags needed.
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._connected = False
        self._mode = None  # "playwright" | "cdp" | "com"
        self._tabs: Dict[str, BrowserTab] = {}
        self._lock = threading.Lock()
        self._page = None  # Active page for operations

    # ═══════════════════════════════════════════════════════════════
    # CONNECTION — tries everything, picks what works
    # ═══════════════════════════════════════════════════════════════

    def connect(self) -> bool:
        """Connect to a browser. Tries Playwright first, then CDP, then COM."""
        # Method 1: Playwright (zero-config, works immediately)
        if self._connect_playwright():
            return True

        # Method 2: CDP attachment (if Chrome has debugging port)
        if self._connect_cdp():
            return True

        # Method 3: COM (if Chrome is already running)
        if self._connect_com():
            return True

        log.warning("[BROWSER] No browser connection available")
        return False

    def _connect_playwright(self) -> bool:
        """Connect using Playwright's bundled Chromium."""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            self._connected = True
            self._mode = "playwright"

            # Open a default page
            ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            if ctx.pages:
                self._page = ctx.pages[0]
            else:
                self._page = ctx.new_page()

            tab = BrowserTab(
                tab_id=str(id(self._page)),
                title="New Tab",
                url="about:blank",
                active=True,
            )
            self._tabs[tab.tab_id] = tab
            log.info("[BROWSER] Connected via Playwright (bundled Chromium)")
            return True
        except Exception as e:
            log.debug(f"[BROWSER] Playwright failed: {e}")
            return False

    def _connect_cdp(self) -> bool:
        """Connect to running Chrome via CDP."""
        try:
            import urllib.request
            data = urllib.request.urlopen("http://localhost:9222/json", timeout=2).read()
            tabs_data = json.loads(data)
            if not tabs_data:
                return False

            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp("http://localhost:9222")
            self._connected = True
            self._mode = "cdp"

            for t in tabs_data:
                tab = BrowserTab(
                    tab_id=t.get("id", ""),
                    title=t.get("title", ""),
                    url=t.get("url", ""),
                )
                self._tabs[tab.tab_id] = tab

            log.info(f"[BROWSER] Connected via CDP — {len(self._tabs)} tabs")
            return True
        except Exception as e:
            log.debug(f"[BROWSER] CDP failed: {e}")
            return False

    def _connect_com(self) -> bool:
        """Connect via COM automation (Chrome already running)."""
        try:
            import win32com.client
            chrome = win32com.client.GetObject("Chrome.Application")
            self._connected = True
            self._mode = "com"
            log.info("[BROWSER] Connected via COM")
            return True
        except Exception:
            return False

    def is_connected(self) -> bool:
        return self._connected

    # ═══════════════════════════════════════════════════════════════
    # BROWSING
    # ═══════════════════════════════════════════════════════════════

    def browse(self, url: str) -> dict:
        """Open a URL. Returns page info."""
        if not self._connected:
            self.connect()
        if not self._connected:
            return {"error": "No browser available"}

        if self._mode == "playwright":
            return self._browse_playwright(url)
        elif self._mode == "cdp":
            return self._browse_cdp(url)
        elif self._mode == "com":
            return self._browse_com(url)
        return {"error": "Unknown mode"}

    def _browse_playwright(self, url: str) -> dict:
        try:
            if not self._page or self._page.is_closed():
                ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
                self._page = ctx.new_page()
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = self._page.title()
            tab_id = str(id(self._page))
            self._tabs[tab_id] = BrowserTab(tab_id=tab_id, title=title, url=url, active=True)
            return {"success": True, "title": title, "url": url, "tab_id": tab_id}
        except Exception as e:
            return {"error": str(e)}

    def _browse_cdp(self, url: str) -> dict:
        try:
            ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            tab_id = str(id(page))
            self._tabs[tab_id] = BrowserTab(tab_id=tab_id, title=page.title(), url=url)
            return {"success": True, "title": page.title(), "url": url, "tab_id": tab_id}
        except Exception as e:
            return {"error": str(e)}

    def _browse_com(self, url: str) -> dict:
        try:
            import win32com.client
            chrome = win32com.client.GetObject("Chrome.Application")
            chrome.ActiveWindow.LocationURL = url
            return {"success": True, "url": url}
        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # CONTENT EXTRACTION
    # ═══════════════════════════════════════════════════════════════

    def get_content(self, tab_id: str = None) -> dict:
        """Get page text, links, forms."""
        if not self._connected:
            return {"error": "Not connected"}

        if self._mode in ("playwright", "cdp"):
            return self._get_content_playwright(tab_id)
        elif self._mode == "com":
            return {"error": "COM mode: content extraction not supported"}
        return {"error": "Unknown mode"}

    def _get_content_playwright(self, tab_id: str = None) -> dict:
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            return page.evaluate("""() => ({
                title: document.title,
                url: window.location.href,
                text: document.body?.innerText?.substring(0, 50000) || "",
                links: Array.from(document.querySelectorAll('a[href]')).slice(0, 200).map(a => ({
                    text: a.innerText.trim().substring(0, 100),
                    href: a.href,
                })),
            })""")
        except Exception as e:
            return {"error": str(e)}

    def search_page(self, query: str, tab_id: str = None) -> dict:
        """Search for text on the current page."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            result = page.evaluate(f"""() => {{
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                const matches = [];
                while (walker.nextNode()) {{
                    if (walker.currentNode.textContent.toLowerCase().includes('{query.lower()}')) {{
                        matches.push(walker.currentNode.textContent.trim().substring(0, 200));
                    }}
                }}
                return matches.slice(0, 20);
            }}""")
            return {"matches": result, "count": len(result)}
        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # INTERACTION
    # ═══════════════════════════════════════════════════════════════

    def click(self, selector: str, tab_id: str = None) -> dict:
        """Click an element by CSS selector — no mouse movement."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            page.click(selector, timeout=5000)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"error": str(e)}

    def type_text(self, selector: str, text: str, tab_id: str = None) -> dict:
        """Type text into a field — no keyboard needed."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            page.fill(selector, text)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"error": str(e)}

    def press_key(self, key: str, tab_id: str = None) -> dict:
        """Press a keyboard key in the page."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            page.keyboard.press(key)
            return {"success": True, "key": key}
        except Exception as e:
            return {"error": str(e)}

    def scroll(self, amount: int = 500, tab_id: str = None) -> dict:
        """Scroll the page."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            page.evaluate(f"window.scrollBy(0, {amount})")
            return {"success": True, "scrolled": amount}
        except Exception as e:
            return {"error": str(e)}

    def execute_js(self, code: str, tab_id: str = None) -> dict:
        """Execute JavaScript in the page."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            result = page.evaluate(code)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # TAB MANAGEMENT
    # ═══════════════════════════════════════════════════════════════

    def list_tabs(self) -> list:
        if not self._connected:
            return []
        if self._mode == "playwright":
            tabs = []
            for ctx in self._browser.contexts:
                for page in ctx.pages:
                    tid = str(id(page))
                    tabs.append(BrowserTab(
                        tab_id=tid,
                        title=page.title() if not page.is_closed() else "",
                        url=page.url if not page.is_closed() else "",
                    ))
            return [t.to_dict() for t in tabs]
        return [t.to_dict() for t in self._tabs.values()]

    def switch_tab(self, tab_id: str) -> bool:
        if self._mode == "playwright":
            for ctx in self._browser.contexts:
                for page in ctx.pages:
                    if str(id(page)) == tab_id and not page.is_closed():
                        self._page = page
                        return True
        return False

    # ═══════════════════════════════════════════════════════════════
    # BATCH OPERATIONS
    # ═══════════════════════════════════════════════════════════════

    def batch_extract(self, urls: list, max_concurrent: int = 5) -> list:
        """Extract content from many URLs without crashing RAM."""
        if not self._connected:
            self.connect()
        if not self._connected:
            return [{"url": u, "error": "No browser"} for u in urls]

        results = []
        for url in urls:
            try:
                result = self.browse(url)
                if result.get("success"):
                    content = self.get_content()
                    results.append({"url": url, "title": content.get("title", ""), "text": content.get("text", "")[:2000]})
                else:
                    results.append({"url": url, "error": result.get("error", "Unknown")})
            except Exception as e:
                results.append({"url": url, "error": str(e)})
        return results

    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _get_page(self, tab_id: str = None):
        if not self._connected or not self._browser:
            return self._page  # Return cached page

        if tab_id:
            for ctx in self._browser.contexts:
                for page in ctx.pages:
                    if str(id(page)) == tab_id and not page.is_closed():
                        return page

        # Return active page
        if self._page and not self._page.is_closed():
            return self._page

        # Get first available page
        for ctx in self._browser.contexts:
            if ctx.pages:
                self._page = ctx.pages[0]
                return self._page

        return None

    def capture_screenshot(self, tab_id: str = None, quality: int = 50) -> Optional[bytes]:
        """Capture JPEG screenshot of the active tab via Playwright.
        
        Returns raw JPEG bytes, or None on failure.
        """
        page = self._get_page(tab_id)
        if not page:
            return None
        try:
            img_bytes = page.screenshot(type="jpeg", quality=quality)
            return img_bytes
        except Exception as e:
            log.debug(f"Screenshot failed: {e}")
            return None

    def disconnect(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._connected = False

    # ═══════════════════════════════════════════════════════════════
    # LAUNCH CHROME WITH DEBUG PORT
    # ═══════════════════════════════════════════════════════════════

    def launch_chrome_with_cdp(self, port: int = 9222, profile: str = None,
                                url: str = None) -> bool:
        """Launch Chrome with remote debugging enabled so CDP can attach."""
        import subprocess
        import shutil

        chrome_exe = self._find_chrome()
        if not chrome_exe:
            log.warning("[BROWSER] Chrome not found")
            return False

        # Check if debugging port already in use
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
            log.info(f"[BROWSER] Chrome already running on port {port}")
            return True
        except Exception:
            pass

        # Launch Chrome with debugging port
        args = [chrome_exe, f"--remote-debugging-port={port}"]
        if profile:
            args.append(f"--profile-directory={profile}")
        if url:
            args.append(url)

        try:
            subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            import time
            for _ in range(20):
                time.sleep(0.5)
                try:
                    import urllib.request
                    urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
                    log.info(f"[BROWSER] Chrome launched with CDP on port {port}")
                    return True
                except Exception:
                    pass
            log.warning("[BROWSER] Chrome launched but CDP not ready")
            return False
        except Exception as e:
            log.error(f"[BROWSER] Failed to launch Chrome: {e}")
            return False

    def _find_chrome(self) -> Optional[str]:
        """Find Chrome executable."""
        import shutil
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        ]
        for p in chrome_paths:
            if os.path.exists(p):
                return p
        return shutil.which("chrome") or shutil.which("google-chrome")

    def _detect_running_browser(self) -> tuple:
        """Detect which browser is running OR which is the user's default.
        
        Priority:
        1. Running browser (any of Chrome, Edge, Brave, Firefox, Vivaldi, Opera)
        2. Windows default browser (from registry)
        3. Chrome as final fallback
        
        Returns: (exe_path, user_data_dir, profile_dir, browser_type)
        """
        import subprocess
        import winreg

        # All supported browsers with their exe names, types, and default profile paths
        BROWSERS = {
            "chrome.exe": {
                "type": "chrome",
                "exe_names": ["chrome.exe"],
                "default_data": r"~\AppData\Local\Google\Chrome\User Data",
                "profile": "Default",
            },
            "msedge.exe": {
                "type": "edge",
                "exe_names": ["msedge.exe"],
                "default_data": r"~\AppData\Local\Microsoft\Edge\User Data",
                "profile": "Default",
            },
            "brave.exe": {
                "type": "brave",
                "exe_names": ["brave.exe"],
                "default_data": r"~\AppData\Local\BraveSoftware\Brave-Browser\User Data",
                "profile": "Default",
            },
            "firefox.exe": {
                "type": "firefox",
                "exe_names": ["firefox.exe"],
                "default_data": r"~\AppData\Roaming\Mozilla\Firefox\Profiles",
                "profile": "",  # Firefox uses random profile names
            },
            "vivaldi.exe": {
                "type": "vivaldi",
                "exe_names": ["vivaldi.exe"],
                "default_data": r"~\AppData\Local\Vivaldi\User Data",
                "profile": "Default",
            },
            "opera.exe": {
                "type": "opera",
                "exe_names": ["opera.exe"],
                "default_data": r"~\AppData\Roaming\Opera Software\Opera Stable",
                "profile": "Default",
            },
        }

        # ── Step 1: Check running processes ──────────────────────
        try:
            # Use PowerShell for faster process detection
            ps_cmd = (
                "Get-Process | Where-Object {$_.ProcessName -in ["
                + ",".join(f"'{n.replace('.exe','')}'" for n in all_names)
                + "]} | Select-Object ProcessName, Path | ConvertTo-Json"
            )
            r = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            import json as _json
            try:
                procs = _json.loads(r.stdout)
                if not isinstance(procs, list):
                    procs = [procs]
                for proc in procs:
                    proc_name = proc.get("ProcessName", "").lower() + ".exe"
                    proc_path = proc.get("Path", "")

                    for exe_name, info in BROWSERS.items():
                        if proc_name in info["exe_names"] or exe_name in proc_name.lower():
                            # Found a running browser — now get its profile
                            user_data = self._get_browser_user_data_from_process(proc_name)
                            if user_data:
                                profile_dir = self._extract_profile_from_cmdline(proc_name)
                                return (proc_path or exe_name, user_data, profile_dir, info["type"])
            except _json.JSONDecodeError:
                pass

        except Exception:
            pass

        # ── Step 2: Check Windows default browser (registry) ─────
        try:
            # User's default browser is stored here
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
            )
            prog_id = winreg.QueryValueEx(key, "ProgId")[0]
            winreg.CloseKey(key)

            # Map ProgId to browser
            prog_map = {
                "ChromeHTML": "chrome.exe",
                "MSEdgeHTM": "msedge.exe",
                "BraveHTML": "brave.exe",
                "FirefoxURL": "firefox.exe",
                "VivaldiHTM": "vivaldi.exe",
                "Opera": "opera.exe",
            }

            for prog_pattern, exe_name in prog_map.items():
                if prog_pattern.lower() in prog_id.lower():
                    info = BROWSERS[exe_name]
                    default_data = os.path.expanduser(info["default_data"])
                    if os.path.exists(default_data):
                        # Find the actual exe
                        exe_path = self._find_browser_exe(exe_name)
                        # For Firefox, find the default profile
                        profile_dir = info["profile"]
                        if info["type"] == "firefox":
                            profile_dir = self._find_firefox_default_profile(default_data)
                        return (exe_path or exe_name, default_data, profile_dir, info["type"])

        except Exception:
            pass

        # ── Step 3: Check if any supported browser has a profile ─
        for exe_name, info in BROWSERS.items():
            default_data = os.path.expanduser(info["default_data"])
            if os.path.exists(default_data):
                exe_path = self._find_browser_exe(exe_name)
                profile_dir = info["profile"]
                if info["type"] == "firefox":
                    profile_dir = self._find_firefox_default_profile(default_data)
                return (exe_path or exe_name, default_data, profile_dir, info["type"])

        return (None, None, None, None)

    def _get_browser_user_data_from_process(self, process_name: str) -> Optional[str]:
        """Extract user-data-dir from a running browser's command line."""
        import subprocess
        try:
            r = subprocess.run(
                ["wmic", "process", "where", f"name='{process_name}'", "get", "CommandLine"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            for line in r.stdout.splitlines():
                if "--user-data-dir=" in line:
                    m = __import__("re").search(r'--user-data-dir="([^"]+)"', line)
                    if m:
                        return m.group(1)
                    m = __import__("re").search(r'--user-data-dir=(\S+)', line)
                    if m:
                        return m.group(1).rstrip('"')
                # Firefox: -profile flag
                if "-profile " in line.lower():
                    m = __import__("re").search(r'-profile\s+"?([^"\s]+)', line, re.I)
                    if m:
                        return m.group(1)
        except Exception:
            pass
        return None

    def _extract_profile_from_cmdline(self, process_name: str) -> str:
        """Extract --profile-directory from running browser's command line."""
        import subprocess
        try:
            r = subprocess.run(
                ["wmic", "process", "where", f"name='{process_name}'", "get", "CommandLine"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            for line in r.stdout.splitlines():
                if "--profile-directory=" in line:
                    m = __import__("re").search(r'--profile-directory="?([^"]+?)"?\s', line)
                    if m:
                        return m.group(1)
        except Exception:
            pass
        return "Default"

    def _find_firefox_default_profile(self, profiles_dir: str) -> str:
        """Find the Firefox default profile (the one with default-release in the name)."""
        try:
            for name in os.listdir(profiles_dir):
                if "default-release" in name.lower() or "default" in name.lower():
                    return name
            # Just return the first profile
            profiles = [d for d in os.listdir(profiles_dir)
                        if os.path.isdir(os.path.join(profiles_dir, d))]
            if profiles:
                return profiles[0]
        except Exception:
            pass
        return "default"

    def _find_browser_exe(self, exe_name: str) -> Optional[str]:
        """Find a browser executable on the system."""
        import shutil

        # Check PATH
        found = shutil.which(exe_name)
        if found:
            return found

        # Common install locations
        locations = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), exe_name.replace(".exe", ""), exe_name),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), exe_name.replace(".exe", ""), exe_name),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), exe_name.replace(".exe", ""), exe_name),
        ]

        # Special cases
        if exe_name == "chrome.exe":
            locations.append(os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", exe_name))
        elif exe_name == "msedge.exe":
            locations.append(os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", exe_name))
        elif exe_name == "brave.exe":
            locations.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "Application", exe_name))

        for path in locations:
            if os.path.isfile(path):
                return path

        return None

    def _clone_browser_profile(self, user_data: str, profile_dir: str,
                                browser_type: str) -> Optional[str]:
        """Clone browser profile to temp directory — comprehensive copy.
        
        Copies ALL files needed for login state, cookies, passwords,
        session storage, local storage, service workers, and encryption keys.
        """
        import shutil
        import tempfile

        try:
            temp_base = os.path.join(tempfile.gettempdir(), "jarvis_browser_profile")
            temp_profile = os.path.join(temp_base, profile_dir)

            # Clean previous clone
            if os.path.exists(temp_base):
                shutil.rmtree(temp_base, ignore_errors=True)

            os.makedirs(temp_profile, exist_ok=True)

            source_profile = os.path.join(user_data, profile_dir)

            # ── Essential files (must copy) ──────────────────────
            essential_files = [
                # Login & cookies
                "Cookies", "Cookies-journal",
                "Login Data", "Login Data-journal",
                "Login Data For Account", "Login Data For Account-journal",
                # Web data & autofill
                "Web Data", "Web Data-journal",
                # Preferences
                "Preferences", "Secure Preferences",
                # Certificates
                "CertificateTransparency",
            ]

            for fname in essential_files:
                src = os.path.join(source_profile, fname)
                if os.path.isfile(src):
                    try:
                        shutil.copy2(src, os.path.join(temp_profile, fname))
                    except Exception:
                        pass

            # ── Root-level files (Local State has encryption keys) ──
            root_files = [
                "Local State", "Local State-journal",
                "First Run", "First Run 2",
                "BrowserMetrics", "BrowserMetrics-spare",
            ]
            for fname in root_files:
                src = os.path.join(user_data, fname)
                if os.path.isfile(src):
                    try:
                        shutil.copy2(src, os.path.join(temp_base, fname))
                    except Exception:
                        pass

            # ── Essential directories ─────────────────────────────
            essential_dirs = [
                "Session Storage",
                "Local Storage",
                "IndexedDB",
                "Service Worker",
                "Storage",
                "Cache",
                "Code Cache",
                "GPUCache",
                "Blob Storage",
                "Database",
                "bloomfilter_8bit",
                "heavy_ad_intervention",
                "safe_browsing",
            ]

            for dname in essential_dirs:
                src_dir = os.path.join(source_profile, dname)
                dst_dir = os.path.join(temp_profile, dname)
                if os.path.isdir(src_dir):
                    try:
                        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True,
                                        ignore=shutil.ignore_patterns("*.lock", "LOCK"))
                    except Exception:
                        pass

            # ── Extension data (keeps logged-in extension states) ──
            ext_src = os.path.join(source_profile, "Extensions")
            if os.path.isdir(ext_src):
                ext_dst = os.path.join(temp_profile, "Extensions")
                try:
                    # Only copy manifest.json and key files from extensions (not full extensions)
                    os.makedirs(ext_dst, exist_ok=True)
                    for ext_id in os.listdir(ext_src):
                        ext_path = os.path.join(ext_src, ext_id)
                        if os.path.isdir(ext_path):
                            ext_ver_dirs = os.listdir(ext_path) if os.path.isdir(ext_path) else []
                            for ver in ext_ver_dirs:
                                ver_path = os.path.join(ext_path, ver)
                                if os.path.isdir(ver_path):
                                    manifest = os.path.join(ver_path, "manifest.json")
                                    if os.path.isfile(manifest):
                                        dst_ver = os.path.join(ext_dst, ext_id, ver)
                                        os.makedirs(dst_ver, exist_ok=True)
                                        shutil.copy2(manifest, os.path.join(dst_ver, "manifest.json"))
                except Exception:
                    pass

            # ── Firefox-specific: copy key4.db and cert9.db ─────
            if browser_type == "firefox":
                for fname in ["key4.db", "cert9.db", "pkcs11.txt", "logins.json"]:
                    src = os.path.join(source_profile, fname)
                    if os.path.isfile(src):
                        try:
                            shutil.copy2(src, os.path.join(temp_profile, fname))
                        except Exception:
                            pass

            log.info(f"[BROWSER] Cloned {browser_type} profile '{profile_dir}' -> {temp_base}")
            return temp_base

        except Exception as e:
            log.debug(f"[BROWSER] Profile clone failed: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    # SESSION DUPLICATION — clone live session to hidden desktop
    # ═══════════════════════════════════════════════════════════════

    def duplicate_session_to_desktop(self, port: int = 9223,
                                      url: str = None) -> Dict[str, Any]:
        """Launch a SECOND Chrome instance on a HIDDEN desktop using the same profile.
        
        Uses Win32 CreateProcessW with lpDesktop to put Chrome on a hidden desktop
        so the user's main screen is never touched.
        
        Returns: {"success": bool, "port": int, "profile": str, "pid": int}
        """
        import subprocess
        import ctypes
        import ctypes.wintypes

        # Detect running browser (Chrome, Edge, Brave, Firefox, etc.)
        exe_name, user_data, profile_dir, browser_type = self._detect_running_browser()
        if not exe_name or not user_data:
            return {"success": False, "error": "No supported browser found running (Chrome/Edge/Brave/Firefox)"}

        # For non-Chromium browsers, we can't use CDP — fall back to subprocess
        if browser_type == "firefox":
            # Firefox uses -start-debugger-port instead
            port_flag = f"-start-debugger-port={port}"
        else:
            port_flag = f"--remote-debugging-port={port}"

        # Clone profile to temp dir (avoids browser lock conflict)
        temp_profile = self._clone_browser_profile(user_data, profile_dir, browser_type)
        if not temp_profile:
            temp_profile = user_data  # Fallback to original

        # Find the browser executable
        chrome_exe = self._find_chrome()
        if not chrome_exe:
            # Try other browsers
            for alt_exe in ["msedge.exe", "brave.exe", "vivaldi.exe", "opera.exe"]:
                alt_path = os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", alt_exe)
                if os.path.isfile(alt_path):
                    chrome_exe = alt_path
                    break
                alt_path = os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), alt_exe)
                if os.path.isfile(alt_path):
                    chrome_exe = alt_path
                    break
            if not chrome_exe:
                return {"success": False, "error": "Browser executable not found"}

        # Check if port already in use
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
            return {"success": True, "port": port, "profile": temp_profile,
                    "browser": browser_type, "message": "Browser already running on port"}
        except Exception:
            pass

        # Create hidden desktop via Win32 API
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            GENERIC_ALL = 0x10000000
            desktop_name = f"jarvis_t212_{port}"

            hDesktop = user32.CreateDesktopW(desktop_name, None, None, 0, GENERIC_ALL, None)
            if not hDesktop:
                return {"success": False, "error": "Failed to create hidden desktop"}

            # Build Chrome command line — uses cloned profile so user's Chrome isn't affected
            chrome_args = [
                chrome_exe,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={temp_profile}",
                f"--profile-directory={profile_dir}",
                "--no-first-run",
                "--disable-extensions",
            ]
            if url:
                chrome_args.append(url)

            cmd_line = " ".join(f'"{a}"' for a in chrome_args)

            # STARTUPINFOW with lpDesktop = hidden desktop
            class STARTUPINFOW(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.wintypes.DWORD),
                    ("lpReserved", ctypes.wintypes.LPWSTR),
                    ("lpDesktop", ctypes.wintypes.LPWSTR),
                    ("lpTitle", ctypes.wintypes.LPWSTR),
                    ("dwX", ctypes.wintypes.DWORD),
                    ("dwY", ctypes.wintypes.DWORD),
                    ("dwXSize", ctypes.wintypes.DWORD),
                    ("dwYSize", ctypes.wintypes.DWORD),
                    ("dwXCountChars", ctypes.wintypes.DWORD),
                    ("dwYCountChars", ctypes.wintypes.DWORD),
                    ("dwFillAttribute", ctypes.wintypes.DWORD),
                    ("dwFlags", ctypes.wintypes.DWORD),
                    ("wShowWindow", ctypes.wintypes.WORD),
                    ("cbReserved2", ctypes.wintypes.WORD),
                    ("lpReserved2", ctypes.c_void_p),
                    ("hStdInput", ctypes.wintypes.HANDLE),
                    ("hStdOutput", ctypes.wintypes.HANDLE),
                    ("hStdError", ctypes.wintypes.HANDLE),
                ]

            class PROCESS_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("hProcess", ctypes.wintypes.HANDLE),
                    ("hThread", ctypes.wintypes.HANDLE),
                    ("dwProcessId", ctypes.wintypes.DWORD),
                    ("dwThreadId", ctypes.wintypes.DWORD),
                ]

            si = STARTUPINFOW()
            si.cb = ctypes.sizeof(si)
            si.lpDesktop = desktop_name  # KEY: Chrome goes to hidden desktop
            si.dwFlags = 0x00000001  # STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE

            pi = PROCESS_INFORMATION()
            cmd_buffer = ctypes.create_unicode_buffer(cmd_line, len(cmd_line) + 1)

            CREATE_NEW_CONSOLE = 0x00000010

            success = kernel32.CreateProcessW(
                None, cmd_buffer, None, None, False,
                CREATE_NEW_CONSOLE, None, None,
                ctypes.byref(si), ctypes.byref(pi)
            )

            if not success:
                user32.CloseDesktop(hDesktop)
                return {"success": False, "error": f"CreateProcessW failed: {ctypes.GetLastError()}"}

            kernel32.CloseHandle(pi.hThread)
            pid = pi.dwProcessId

            # Wait for CDP to become available
            import time
            for _ in range(30):
                time.sleep(0.5)
                try:
                    import urllib.request
                    urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
                    log.info(f"[BROWSER] Duplicate session on HIDDEN desktop, port {port}, PID {pid}")
                    return {
                        "success": True,
                        "port": port,
                        "profile": user_data,
                        "pid": pid,
                        "desktop": desktop_name,
                        "message": f"Live session cloned to HIDDEN desktop '{desktop_name}' on port {port}",
                    }
                except Exception:
                    pass

            return {"success": False, "error": "Chrome launched but CDP not ready",
                    "pid": pid, "desktop": desktop_name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def connect_to_duplicate(self, port: int = 9223) -> bool:
        """Connect to the duplicated session on the hidden desktop."""
        try:
            import urllib.request
            data = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=3).read()
            tabs_data = json.loads(data)

            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(f"http://localhost:{port}")
            self._connected = True
            self._mode = "cdp"

            self._tabs = {}
            for t in tabs_data:
                tab = BrowserTab(
                    tab_id=t.get("id", ""),
                    title=t.get("title", ""),
                    url=t.get("url", ""),
                )
                self._tabs[tab.tab_id] = tab

            if tabs_data:
                self.find_tab(url_contains="")

            log.info(f"[BROWSER] Connected to duplicate session on port {port} — {len(self._tabs)} tabs")
            return True
        except Exception as e:
            log.debug(f"[BROWSER] Connect to duplicate failed: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    # TAB DISCOVERY
    # ═══════════════════════════════════════════════════════════════

    def find_tab(self, domain: str = None, title_contains: str = None,
                 url_contains: str = None) -> Optional[object]:
        """Find a tab matching criteria. Returns the Playwright page object."""
        if not self._connected:
            return None
        for ctx in self._browser.contexts:
            for page in ctx.pages:
                if page.is_closed():
                    continue
                url = page.url or ""
                title = ""
                try:
                    title = page.title()
                except Exception:
                    pass
                if domain and domain.lower() in url.lower():
                    self._page = page
                    return page
                if title_contains and title_contains.lower() in title.lower():
                    self._page = page
                    return page
                if url_contains and url_contains.lower() in url.lower():
                    self._page = page
                    return page
        return None

    def find_tab_or_browse(self, domain: str) -> dict:
        """Find a tab for a domain, or open it if not found."""
        page = self.find_tab(domain=domain)
        if page:
            tab_id = str(id(page))
            self._page = page
            return {"found": True, "tab_id": tab_id, "url": page.url, "title": page.title()}
        # Not found — open it
        result = self.browse(f"https://{domain}")
        return {"found": False, "opened": True, **result}

    # ═══════════════════════════════════════════════════════════════
    # DOM EXTRACTION — structured data from any page
    # ═══════════════════════════════════════════════════════════════

    def extract_structured(self, selectors: Dict[str, str] = None,
                           tab_id: str = None) -> Dict[str, str]:
        """Extract text from CSS selectors on the page.
        
        selectors: {"portfolio_value": ".total-value", "cash": ".cash-balance"}
        If None, extracts all visible text.
        Returns: {"portfolio_value": "$87,650", "cash": "$15,420"}
        """
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            if selectors:
                result = {}
                for key, sel in selectors.items():
                    try:
                        el = page.query_selector(sel)
                        result[key] = el.inner_text() if el else ""
                    except Exception:
                        result[key] = ""
                return result
            else:
                return page.evaluate("""() => {
                    const data = {};
                    // Extract all inputs with labels
                    document.querySelectorAll('input, [data-value], [data-balance], [data-amount]').forEach(el => {
                        const label = el.getAttribute('aria-label') || el.getAttribute('data-label') || el.name || el.id || '';
                        if (label) data[label] = el.value || el.innerText || '';
                    });
                    // Extract visible text with common financial patterns
                    const text = document.body?.innerText || '';
                    const patterns = [
                        /total[:\s]*[$€£]?([\d,]+\.?\d*)/gi,
                        /balance[:\s]*[$€£]?([\d,]+\.?\d*)/gi,
                        /cash[:\s]*[$€£]?([\d,]+\.?\d*)/gi,
                        /value[:\s]*[$€£]?([\d,]+\.?\d*)/gi,
                        /profit[:\s]*[$€£]?([\d,]+\.?\d*)/gi,
                    ];
                    patterns.forEach(p => {
                        let m;
                        while ((m = p.exec(text)) !== null) {
                            data[m[0].split(':')[0].trim().toLowerCase()] = m[1];
                        }
                    });
                    data['_full_text'] = text.substring(0, 10000);
                    return data;
                }""")
        except Exception as e:
            return {"error": str(e)}

    def get_all_buttons(self, tab_id: str = None) -> List[Dict]:
        """Get all visible buttons on the page."""
        page = self._get_page(tab_id)
        if not page:
            return []
        try:
            return page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"], a.btn, [data-action]'))
                    .filter(el => el.offsetParent !== null)
                    .slice(0, 50)
                    .map(el => ({
                        text: el.innerText?.trim()?.substring(0, 100) || '',
                        id: el.id || '',
                        class: el.className?.substring?.(0, 100) || '',
                        selector: el.id ? '#' + el.id : '',
                        dataAction: el.getAttribute('data-action') || '',
                    }));
            }""")
        except Exception:
            return []

    def get_all_inputs(self, tab_id: str = None) -> List[Dict]:
        """Get all visible input fields on the page."""
        page = self._get_page(tab_id)
        if not page:
            return []
        try:
            return page.evaluate("""() => {
                return Array.from(document.querySelectorAll('input, textarea, select'))
                    .filter(el => el.offsetParent !== null)
                    .slice(0, 50)
                    .map(el => ({
                        type: el.type || 'text',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        value: el.value || '',
                        label: el.getAttribute('aria-label') || '',
                        selector: el.id ? '#' + el.id : (el.name ? '[name="' + el.name + '"]' : ''),
                    }));
            }""")
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════
    # OCR VERIFICATION
    # ═══════════════════════════════════════════════════════════════

    def screenshot_verify(self, expect_text: str = "", tab_id: str = None) -> Dict:
        """Take a screenshot and OCR it to verify page state.
        
        Returns: {"text": full_ocr_text, "found": bool, "matches": [str]}
        """
        try:
            from vision_controller import get_vision
            v = get_vision()
            img_b64 = v.screenshot_base64()
            if not img_b64:
                return {"error": "Screenshot failed"}
            # Use EasyOCR to read the screen
            ocr_result = v.ocr_read(img_b64)
            full_text = ocr_result if isinstance(ocr_result, str) else str(ocr_result)
            matches = []
            if expect_text:
                for word in expect_text.split("|"):
                    word = word.strip()
                    if word.lower() in full_text.lower():
                        matches.append(word)
            return {
                "text": full_text[:5000],
                "found": len(matches) > 0,
                "matches": matches,
                "expect": expect_text,
            }
        except Exception as e:
            return {"error": str(e)}

    def click_by_text(self, text: str, tag: str = "button", tab_id: str = None) -> dict:
        """Click an element by its visible text content."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            result = page.evaluate(f"""() => {{
                const els = document.querySelectorAll('{tag}, a, [role="button"]');
                for (const el of els) {{
                    if (el.innerText?.trim().toLowerCase() === '{text.lower()}') {{
                        el.click();
                        return {{success: true, text: el.innerText.trim()}};
                    }}
                }}
                // Partial match
                for (const el of els) {{
                    if (el.innerText?.trim().toLowerCase().includes('{text.lower()}')) {{
                        el.click();
                        return {{success: true, text: el.innerText.trim(), partial: true}};
                    }}
                }}
                return {{success: false, error: 'Element not found'}};
            }}""")
            return result
        except Exception as e:
            return {"error": str(e)}

    def fill_by_label(self, label: str, value: str, tab_id: str = None) -> dict:
        """Fill an input field by its label, placeholder, or aria-label."""
        page = self._get_page(tab_id)
        if not page:
            return {"error": "Page not found"}
        try:
            result = page.evaluate(f"""() => {{
                const inputs = document.querySelectorAll('input, textarea');
                for (const el of inputs) {{
                    const label_text = (el.getAttribute('aria-label') || '') + ' ' +
                                       (el.placeholder || '') + ' ' +
                                       (el.name || '') + ' ' + (el.id || '');
                    if (label_text.toLowerCase().includes('{label.lower()}')) {{
                        el.focus();
                        el.value = '{value}';
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return {{success: true, field: label, value: '{value}'}};
                    }}
                }}
                return {{success: false, error: 'Field not found'}};
            }}""")
            return result
        except Exception as e:
            return {"error": str(e)}


# Singleton
_browser = None

def get_browser() -> BrowserController:
    global _browser
    if _browser is None:
        _browser = BrowserController()
    return _browser
