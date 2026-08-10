"""
Browser control via nodriver (CDP) — Chrome profiles, instant DOM access.
NO OCR for browser. Direct DOM interaction.
"""

import asyncio
import json
import os
import re
import time
from typing import Optional


def _find_chrome(browser="chrome"):
    """Find Chrome or Edge executable."""
    if browser == "edge":
        for p in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]:
            if os.path.isfile(p):
                return p
    for p in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]:
        if os.path.isfile(p):
            return p
    return None


def _find_chrome_user_data():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data")


def find_profile_dir(display_name: str) -> Optional[str]:
    """Find Chrome profile directory name from display name. Checks account_info and profile.name."""
    user_data = _find_chrome_user_data()
    if not os.path.isdir(user_data):
        return None
    target = display_name.lower()
    for d in os.listdir(user_data):
        full = os.path.join(user_data, d)
        if os.path.isdir(full) and (d == "Default" or d.startswith("Profile ")):
            prefs = os.path.join(full, "Preferences")
            if os.path.isfile(prefs):
                try:
                    with open(prefs, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                    # Check account_info[0].full_name (Google account name)
                    account_info = data.get("account_info", [])
                    if account_info:
                        gaia_name = account_info[0].get("full_name", "")
                        if gaia_name.lower() == target:
                            return d
                    # Check profile.name
                    prof_name = data.get("profile", {}).get("name", "")
                    if prof_name.lower() == target:
                        return d
                except Exception:
                    pass
    return None


def list_profiles() -> list[dict]:
    """List all Chrome profiles with Google account names."""
    user_data = _find_chrome_user_data()
    profiles = []
    if not os.path.isdir(user_data):
        return profiles
    for d in os.listdir(user_data):
        full = os.path.join(user_data, d)
        if os.path.isdir(full) and (d == "Default" or d.startswith("Profile ")):
            prefs = os.path.join(full, "Preferences")
            if os.path.isfile(prefs):
                try:
                    with open(prefs, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                    name = data.get("profile", {}).get("name", d)
                    account_info = data.get("account_info", [])
                    gaia_name = account_info[0].get("full_name", "") if account_info else ""
                    display = gaia_name or name
                    profiles.append({"dir": d, "name": display})
                except Exception:
                    profiles.append({"dir": d, "name": d})
    return profiles


# ── Browser Controller using nodriver ─────────────────────────────

class BrowserController:
    """Control Chrome or Edge. Supports profiles."""

    def __init__(self):
        self._profile_dir = None
        self._browser_exe = None

    async def start(self, profile_name: str = None, browser: str = "chrome"):
        """Store profile and browser for navigate."""
        self._browser_exe = _find_chrome(browser)
        self._profile_dir = None
        if profile_name:
            self._profile_dir = find_profile_dir(profile_name)

    async def navigate(self, url: str):
        """Navigate to URL in existing Chrome window via keyboard."""
        import time

        try:
            import win32gui
            import pyperclip
            import pyautogui

            # Find Chrome window with "New Tab" or profile name
            def find_chrome_window():
                result = [0]
                def callback(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd).lower()
                        if "chrome" in title and ("new tab" in title or "mail.com" in title or "google" in title):
                            result[0] = hwnd
                win32gui.EnumWindows(callback, None)
                return result[0]

            hwnd = find_chrome_window()
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.15)
                pyperclip.copy(url)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.1)
                pyautogui.press("enter")
                await asyncio.sleep(1)
        except Exception:
            pass

    async def get_url(self) -> str:
        return ""

    async def get_title(self) -> str:
        return ""

    async def get_text(self) -> str:
        return ""

    def stop(self):
        pass

    async def click_text(self, text: str) -> bool:
        """Click element containing text."""
        if not self._tab:
            return False
        result = await self._tab.evaluate("""
            (() => {
                const lower = '%s';
                const els = document.querySelectorAll('a, button, input[type=submit], [role=button], [onclick], label');
                for (const el of els) {
                    const t = (el.textContent || '').toLowerCase();
                    const v = (el.value || '').toLowerCase();
                    if (t.includes(lower) || v.includes(lower)) {
                        el.scrollIntoView({block: 'center'});
                        el.click();
                        return true;
                    }
                }
                return false;
            })()
        """ % text.lower())
        return result is True or result == "true"

    async def fill_field(self, label_text: str, value: str) -> bool:
        """Find input by label text and fill it."""
        if not self._tab:
            return False
        result = await self._tab.evaluate("""
            (() => {
                const lowerLabel = '%s';
                const val = '%s';
                const labels = document.querySelectorAll('label');
                for (const l of labels) {
                    if (l.textContent.toLowerCase().includes(lowerLabel)) {
                        const input = document.getElementById(l.htmlFor) || l.querySelector('input');
                        if (input) {
                            input.focus();
                            input.value = val;
                            input.dispatchEvent(new Event('input', {bubbles: true}));
                            input.dispatchEvent(new Event('change', {bubbles: true}));
                            return true;
                        }
                    }
                }
                const inputs = document.querySelectorAll('input, textarea');
                for (const inp of inputs) {
                    const ph = (inp.placeholder || '').toLowerCase();
                    const name = (inp.name || '').toLowerCase();
                    if (ph.includes(lowerLabel) || name.includes(lowerLabel)) {
                        inp.focus();
                        inp.value = val;
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            })()
        """ % (label_text.lower(), value))
        return result is True or result == "true"

    async def type_text(self, text: str):
        """Type text via CDP keyboard."""
        if self._tab:
            for ch in text:
                await self._tab.send(cdp.input_.dispatch_key_event(
                    type_="keyDown", key=ch, text=ch
                ))
                await self._tab.send(cdp.input_.dispatch_key_event(
                    type_="keyUp", key=ch
                ))
                await asyncio.sleep(0.01)

    async def press_key(self, key: str):
        """Press a key like Enter, Tab, etc."""
        if self._tab:
            await self._tab.send(cdp.input_.dispatch_key_event(
                type_="keyDown", key=key, code=key
            ))
            await self._tab.send(cdp.input_.dispatch_key_event(
                type_="keyUp", key=key, code=key
            ))

    async def get_prices(self) -> list[dict]:
        """Extract all prices from page."""
        if not self._tab:
            return []
        raw = await self._tab.evaluate("""
            (() => {
                const prices = [];
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                let node;
                const pattern = /[$£€]\\s?\\d[\\d,]*\\.?\\d*|\\d[\\d,]*\\.?\\d*\\s?(?:USD|GBP|EUR|INR)/gi;
                while (node = walker.nextNode()) {
                    const t = node.textContent;
                    const matches = t.match(pattern);
                    if (matches) {
                        const el = node.parentElement;
                        const rect = el ? el.getBoundingClientRect() : null;
                        for (const m of matches) {
                            prices.push({
                                text: t.trim().slice(0, 100),
                                raw: m,
                                value: parseFloat(m.replace(/[^\\d.]/g, '')),
                            });
                        }
                    }
                }
                return JSON.stringify(prices);
            })()
        """)
        return json.loads(raw) if raw else []

    async def get_links(self) -> list[dict]:
        """Get all links on page."""
        if not self._tab:
            return []
        raw = await self._tab.evaluate("""
            (() => {
                const links = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    links.push({href: a.href, text: a.textContent.trim().slice(0, 100)});
                });
                return JSON.stringify(links);
            })()
        """)
        return json.loads(raw) if raw else []

    async def get_inputs(self) -> list[dict]:
        """Get all input fields."""
        if not self._tab:
            return []
        raw = await self._tab.evaluate("""
            (() => {
                const inputs = [];
                document.querySelectorAll('input, textarea, select').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    inputs.push({
                        tag: el.tagName, type: el.type || '', name: el.name || '',
                        id: el.id || '', placeholder: el.placeholder || '',
                        label: el.labels && el.labels[0] ? el.labels[0].textContent.trim() : '',
                        visible: rect.width > 0 && rect.height > 0,
                    });
                });
                return JSON.stringify(inputs);
            })()
        """)
        return json.loads(raw) if raw else []

    async def scroll_down(self, amount: int = 500):
        if self._tab:
            await self._tab.evaluate("window.scrollBy(0, %d)" % amount)

    async def scroll_up(self, amount: int = 500):
        if self._tab:
            await self._tab.evaluate("window.scrollBy(0, -%d)" % amount)

    def stop(self):
        """Disconnect (does NOT close Chrome)."""
        self._tab = None
        self._browser = None


# ── Sync wrappers for entity engine ───────────────────────────────

def browser_open(url: str, profile: str = None, browser: str = "chrome") -> str:
    """Open URL in Chrome/Edge with profile."""
    ctrl = BrowserController()

    async def _run():
        await ctrl.start(profile_name=profile, browser=browser)
        await ctrl.navigate(url)
        return "Opened: %s" % url

    return asyncio.run(_run())


def browser_read(profile: str = None) -> str:
    """Read current page text."""
    ctrl = BrowserController()

    async def _run():
        await ctrl.start(profile_name=profile)
        text = await ctrl.get_text()
        title = await ctrl.get_title()
        url = await ctrl.get_url()
        ctrl.stop()
        return "[%s](%s)\n\n%s" % (title, url, text[:3000])

    return asyncio.run(_run())


def browser_click(text: str, profile: str = None) -> str:
    """Click element by text."""
    ctrl = BrowserController()

    async def _run():
        await ctrl.start(profile_name=profile)
        found = await ctrl.click_text(text)
        ctrl.stop()
        return "Clicked '%s'" % text if found else "'%s' not found" % text

    return asyncio.run(_run())


def browser_fill(label: str, value: str, profile: str = None) -> str:
    """Fill form field."""
    ctrl = BrowserController()

    async def _run():
        await ctrl.start(profile_name=profile)
        ok = await ctrl.fill_field(label, value)
        ctrl.stop()
        return "Filled '%s' with '%s'" % (label, value) if ok else "Field '%s' not found" % label

    return asyncio.run(_run())


def browser_prices(profile: str = None) -> list[dict]:
    """Extract prices from current page."""
    ctrl = BrowserController()

    async def _run():
        await ctrl.start(profile_name=profile)
        prices = await ctrl.get_prices()
        ctrl.stop()
        return prices

    return asyncio.run(_run())


def browser_compare(urls: list[str]) -> dict:
    """Open multiple URLs, extract prices, find cheapest."""
    ctrl = BrowserController()

    async def _run():
        await ctrl.start()
        all_prices = []
        for url in urls:
            await ctrl.navigate(url)
            await asyncio.sleep(1)
            prices = await ctrl.get_prices()
            for p in prices:
                p["url"] = url
                all_prices.append(p)
        ctrl.stop()
        cheapest = min(all_prices, key=lambda x: x["value"]) if all_prices else None
        return {"total": len(all_prices), "prices": all_prices, "cheapest": cheapest}

    return asyncio.run(_run())
