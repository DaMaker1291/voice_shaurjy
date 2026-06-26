"""Web Automation Engine — Playwright-based browser for web apps (WhatsApp, Teams, etc.).
Manages persistent browser contexts so login sessions survive restarts.
Provides: open page, screenshot, OCR, find/click text, type, read messages.
"""

import os
import re
import json
import time
import base64
from pathlib import Path

BROWSER_DATA_DIR = os.path.join(os.path.dirname(__file__), ".browser_profiles")
PAGE_TIMEOUT = 15000

_browser = None
_context = None
_page = None
_current_app = None


def _ensure_browser():
    global _browser, _context, _page
    if _browser is None:
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        _browser = p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 900},
            no_viewport=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        _context = _browser
        _page = _context.pages[0] if _context.pages else _context.new_page()
    return _page


def _ensure_page():
    global _page, _context
    if _page is None:
        _ensure_browser()
    try:
        _page.title(timeout=1000)
    except:
        _page = _context.new_page() if _context else _ensure_browser()
    return _page


def close():
    global _browser, _context, _page, _current_app
    try:
        if _browser:
            _browser.close()
    except:
        pass
    _browser = None
    _context = None
    _page = None
    _current_app = None


def navigate(url: str, wait_until: str = "domcontentloaded") -> str:
    p = _ensure_page()
    try:
        p.goto(url, timeout=PAGE_TIMEOUT, wait_until=wait_until)
        time.sleep(1.5)
        return f"Navigated to {url}"
    except Exception as e:
        return f"Navigation error: {e}"


def screenshot(path: str = None) -> str:
    p = _ensure_page()
    if not path:
        path = f"/tmp/jv_web_{int(time.time())}.png"
    try:
        p.screenshot(path=path, full_page=False)
        return path
    except Exception as e:
        return f"Screenshot error: {e}"


def screenshot_b64() -> str:
    p = _ensure_page()
    try:
        b64 = p.screenshot(full_page=False, type="png")
        return base64.b64encode(b64).decode()
    except Exception as e:
        return ""


def get_text() -> str:
    p = _ensure_page()
    try:
        text = p.inner_text("body", timeout=3000)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return "\n".join(lines[:200])
    except Exception as e:
        return f"Get text error: {e}"


def get_visible_text() -> str:
    p = _ensure_page()
    try:
        text = p.evaluate("""() => {
            const el = document.body;
            const style = getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return '';
            return el.innerText;
        }""")
        lines = [l.strip() for l in (text or "").split("\n") if l.strip()]
        return "\n".join(lines[:200])
    except Exception as e:
        return f"Visible text error: {e}"


def find_text(text: str) -> dict:
    p = _ensure_page()
    try:
        el = p.locator(f"text={text}").first
        if el.is_visible(timeout=3000):
            box = el.bounding_box()
            if box:
                return {"text": el.inner_text()[:100], "x": box["x"], "y": box["y"],
                        "width": box["width"], "height": box["height"]}
        return {}
    except:
        return {}


def find_text_all(text: str) -> list[dict]:
    p = _ensure_page()
    results = []
    try:
        locator = p.locator(f"text={text}")
        for el in locator.all():
            if el.is_visible(timeout=1000):
                box = el.bounding_box()
                if box:
                    results.append({"text": el.inner_text()[:100], "x": box["x"], "y": box["y"],
                                    "width": box["width"], "height": box["height"]})
    except:
        pass
    return results


def click_text(text: str) -> str:
    p = _ensure_page()
    try:
        el = p.locator(f"text={text}").first
        if el.is_visible(timeout=3000):
            el.click(timeout=2000)
            time.sleep(0.5)
            return f"Clicked '{text}'"
        return f"'{text}' not visible"
    except Exception as e:
        return f"Click error: {e}"


def click(selector: str) -> str:
    p = _ensure_page()
    try:
        el = p.locator(selector).first
        if el.is_visible(timeout=3000):
            el.click(timeout=2000)
            time.sleep(0.5)
            return f"Clicked {selector}"
        return f"{selector} not visible"
    except Exception as e:
        return f"Click error: {e}"


def type_text(text: str, selector: str = None) -> str:
    p = _ensure_page()
    try:
        if selector:
            el = p.locator(selector).first
            if el.is_visible(timeout=3000):
                el.fill(text)
                return f"Typed into {selector}"
            return f"Selector '{selector}' not found"
        else:
            p.keyboard.type(text, delay=20)
            return f"Typed '{text[:50]}...'"
    except Exception as e:
        return f"Type error: {e}"


def press_key(key: str) -> str:
    p = _ensure_page()
    try:
        p.keyboard.press(key)
        return f"Pressed {key}"
    except Exception as e:
        return f"Key error: {e}"


def wait(ms: int = 1000):
    time.sleep(ms / 1000)


def get_html() -> str:
    p = _ensure_page()
    try:
        return p.content()
    except:
        return ""


def execute_js(js: str) -> str:
    p = _ensure_page()
    try:
        result = p.evaluate(js)
        return str(result)[:1000]
    except Exception as e:
        return f"JS error: {e}"


# ── High-level App Actions ──

def app_whatsapp_open() -> str:
    global _current_app
    p = _ensure_page()
    navigate("https://web.whatsapp.com")
    _current_app = "whatsapp"
    time.sleep(3)
    title = p.title()
    if "WhatsApp" in title:
        return "WhatsApp Web opened"
    return "Navigated to web.whatsapp.com — scan QR code if not logged in"


def app_whatsapp_read(limit: int = 10, unread_only: bool = False) -> str:
    p = _ensure_page()
    try:
        if "web.whatsapp.com" not in p.url:
            app_whatsapp_open()
            time.sleep(2)

        chats_data = p.evaluate(f"""() => {{
            const chats = document.querySelectorAll('[data-testid="conversation-info"]');
            const results = [];
            for (let i = 0; i < Math.min(chats.length, {limit + 5}); i++) {{
                const chat = chats[i];
                const nameEl = chat.querySelector('[data-testid="conversation-info-header"]');
                const msgEl = chat.querySelector('[data-testid="conversation-info-message"]');
                const timeEl = chat.querySelector('[data-testid="conversation-info-header"] time');
                const name = nameEl ? nameEl.innerText.trim() : 'Unknown';
                const msg = msgEl ? msgEl.innerText.trim() : '';
                const time = timeEl ? timeEl.getAttribute('datetime') : '';
                const unread = chat.querySelector('[data-testid="icon-unread-count"]') !== null;
                results.push({{ name, msg, time, unread }});
            }}
            return JSON.stringify(results);
        }}""")

        chats = json.loads(chats_data)
        if not chats:
            return "No conversations found"

        lines = []
        for i, c in enumerate(chats[:limit], 1):
            unread_tag = " [NEW]" if c.get("unread") else ""
            ts = c.get("time", "")[:16] if c.get("time") else ""
            lines.append(f"{i}. {c['name']}{unread_tag}")
            if c.get("msg"):
                lines.append(f"   \"{c['msg'][:120]}\"")
            if ts:
                lines.append(f"   {ts}")

        if unread_only:
            unread_chats = [c for c in chats if c.get("unread")]
            unread_lines = [f"{i}. {c['name']} — \"{c.get('msg','')[:120]}\"" for i, c in enumerate(unread_chats[:limit], 1)]
            if unread_lines:
                return f"Unread messages:\n" + "\n".join(unread_lines)
            return "No unread messages"

        return "Conversations:\n" + "\n".join(lines)

    except Exception as e:
        return f"WhatsApp read error: {e}"


def app_whatsapp_send(contact: str, message: str) -> str:
    p = _ensure_page()
    try:
        if "web.whatsapp.com" not in p.url:
            app_whatsapp_open()
            time.sleep(2)

        search_box = p.locator('[data-testid="chat-list-search"]')
        if search_box.is_visible(timeout=3000):
            search_box.fill(contact)
            time.sleep(1)
        else:
            p.keyboard.press("Control+Alt+n")
            time.sleep(0.5)
            p.keyboard.type(contact, delay=30)
            time.sleep(1)

        contact_el = p.locator(f'[data-testid="conversation-info-header"]:text-is("{contact}")').first
        if not contact_el.is_visible(timeout=3000):
            contact_el = p.locator(f'text={contact}').first
        if contact_el.is_visible(timeout=3000):
            contact_el.click()
            time.sleep(1)
        else:
            p.keyboard.press("Enter")
            time.sleep(1)

        msg_box = p.locator('[data-testid="conversation-compose-box-input"]')
        if not msg_box.is_visible(timeout=3000):
            msg_box = p.locator('[contenteditable="true"]').first

        if msg_box.is_visible(timeout=3000):
            msg_box.fill(message)
            time.sleep(0.3)
            p.keyboard.press("Enter")
            time.sleep(0.5)
            return f"Message sent to {contact}"
        return "Could not find message input box"

    except Exception as e:
        return f"WhatsApp send error: {e}"


def app_teams_open() -> str:
    global _current_app
    navigate("https://teams.microsoft.com")
    _current_app = "teams"
    time.sleep(3)
    return "Microsoft Teams opened"


def app_teams_assignments() -> str:
    p = _ensure_page()
    try:
        if "teams" not in p.url.lower():
            app_teams_open()
            time.sleep(3)

        text = get_visible_text()
        lines = [l for l in text.split("\n") if l.strip()][:50]

        assignment_lines = [l for l in lines if any(
            kw in l.lower() for kw in ["assignment", "due", "submit", "grade", "task", "homework", "deadline"])]

        if assignment_lines:
            return "Assignments found:\n" + "\n".join(assignment_lines[:15])
        return "Teams opened. Current view:\n" + "\n".join(lines[:20])

    except Exception as e:
        return f"Teams error: {e}"


def app_open(name: str) -> str:
    global _current_app
    name = name.lower().strip()
    apps = {
        "whatsapp": ("https://web.whatsapp.com", "WhatsApp Web"),
        "teams": ("https://teams.microsoft.com", "Microsoft Teams"),
        "gmail": ("https://mail.google.com", "Gmail"),
        "outlook": ("https://outlook.live.com", "Outlook"),
        "calendar": ("https://calendar.google.com", "Google Calendar"),
        "maps": ("https://maps.google.com", "Google Maps"),
        "youtube": ("https://youtube.com", "YouTube"),
        "chatgpt": ("https://chat.openai.com", "ChatGPT"),
        "claude": ("https://claude.ai", "Claude"),
        "github": ("https://github.com", "GitHub"),
        "notion": ("https://notion.so", "Notion"),
    }
    url, label = apps.get(name, (None, None))
    if url:
        navigate(url)
        _current_app = name
        return f"{label} opened"
    if "." in name:
        navigate(f"https://{name}")
        _current_app = name
        return f"Navigated to {name}"
    return f"Unknown app: {name}. Try: {', '.join(apps.keys())}"


def app_current() -> str:
    p = _ensure_page()
    try:
        return f"Current page: {p.title()} ({p.url})"
    except:
        return "No page open"


def app_read() -> str:
    text = get_visible_text()
    if not text or text.startswith("Get text error"):
        return "Could not read content"
    lines = text.split("\n")[:30]
    return "\n".join(lines)


def message_filter(messages_text: str, context_cutoff_hours: int = 24) -> str:
    lines = messages_text.split("\n")
    filtered = []
    for line in lines:
        if any(kw in line.lower() for kw in ["[new]", "[NEW]", "unread"]):
            filtered.append(line)
    if filtered:
        return "\n".join(filtered)
    return messages_text


# ── Cleanup ──

def __getattr__(name):
    if name == "web_app_open":
        return app_open
    raise AttributeError(f"module has no attribute {name}")
