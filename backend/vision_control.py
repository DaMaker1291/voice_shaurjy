"""
Vision-based computer control — screen capture, OCR, mouse, keyboard.
JARVIS sees the screen, reads text, clicks buttons, types, scrolls.
"""

import subprocess
import time
import re
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import mss
import mss.tools
import numpy as np
from PIL import Image, ImageGrab

# ── Lazy imports for heavy modules ────────────────────────────────
_ocr_engine = None
_pyautogui = None
_screeninfo = None


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        import easyocr
        _ocr_engine = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _ocr_engine


def _get_pg():
    global _pyautogui
    if _pyautogui is None:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
        _pyautogui = pyautogui
    return _pyautogui


def _get_monitors():
    global _screeninfo
    if _screeninfo is None:
        from screeninfo import get_monitors
        _screeninfo = get_monitors()
    return _screeninfo


# ── Screen Capture ────────────────────────────────────────────────

def capture_screen(region=None, save_path=None) -> np.ndarray:
    """Capture screen as numpy array. region=(x,y,w,h) or None for full."""
    with mss.mss() as sct:
        if region:
            x, y, w, h = region
            monitor = {"left": x, "top": y, "width": w, "height": h}
        else:
            monitor = sct.monitors[1]  # primary monitor
        img = sct.grab(monitor)
        arr = np.array(img)[:, :, :3]  # drop alpha
        if save_path:
            mss.tools.to_png(img.rgb, img.size, save=save_path)
        return arr


def capture_screen_pil(region=None) -> Image.Image:
    """Capture screen as PIL Image."""
    arr = capture_screen(region)
    return Image.fromarray(arr[:, :, ::-1])  # BGR -> RGB


def capture_region(x, y, w, h, save_path=None) -> np.ndarray:
    """Capture specific region."""
    return capture_screen(region=(x, y, w, h), save_path=save_path)


# ── OCR ───────────────────────────────────────────────────────────

@dataclass
class OCRResult:
    text: str
    bbox: tuple  # (x1,y1,x2,y2)
    confidence: float
    center: tuple = field(default_factory=tuple)

    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.center = ((x1 + x2) // 2, (y1 + y2) // 2)


def ocr_read(image=None, screen=True, region=None, save_path=None) -> list[OCRResult]:
    """Read text from screen or image. Returns list of OCRResult."""
    ocr = _get_ocr()

    if screen:
        img = capture_screen(region)
        if save_path:
            from PIL import Image as PILImage
            PILImage.fromarray(img[:, :, ::-1]).save(save_path)
    elif isinstance(image, str):
        img = np.array(Image.open(image))
    elif isinstance(image, np.ndarray):
        img = image
    elif isinstance(image, Image.Image):
        img = np.array(image)
    else:
        return []

    results = ocr.readtext(img)
    out = []
    for item in results:
        if len(item) == 3:
            bbox, text, conf = item
        else:
            bbox, text, conf = item[0], item[1], item[2]
        pts = bbox
        x1, y1 = int(pts[0][0]), int(pts[0][1])
        x2, y2 = int(pts[2][0]), int(pts[2][1])
        out.append(OCRResult(text=text, bbox=(x1, y1, x2, y2), confidence=conf))
    return out


def ocr_find_text(target: str, screen=True, region=None, fuzzy=True) -> Optional[OCRResult]:
    """Find specific text on screen. Returns first match or None."""
    results = ocr_read(screen=screen, region=region)
    target_lower = target.lower().strip()
    for r in results:
        text_lower = r.text.lower().strip()
        if fuzzy:
            if target_lower in text_lower or text_lower in target_lower:
                return r
            # Word overlap
            target_words = set(target_lower.split())
            text_words = set(text_lower.split())
            if target_words and text_words and len(target_words & text_words) / max(len(target_words), 1) > 0.5:
                return r
        else:
            if target_lower == text_lower:
                return r
    return None


def ocr_find_all(target: str, screen=True, region=None, fuzzy=True) -> list[OCRResult]:
    """Find all occurrences of text on screen."""
    results = ocr_read(screen=screen, region=region)
    target_lower = target.lower().strip()
    matches = []
    for r in results:
        text_lower = r.text.lower().strip()
        if fuzzy:
            if target_lower in text_lower or text_lower in target_lower:
                matches.append(r)
        else:
            if target_lower == text_lower:
                matches.append(r)
    return matches


def ocr_read_region(x, y, w, h) -> str:
    """Quick OCR read of a specific region, returns concatenated text."""
    results = ocr_read(screen=True, region=(x, y, w, h))
    return " ".join(r.text for r in results)


# ── Mouse Control ─────────────────────────────────────────────────

def mouse_move(x, y, duration=0.1):
    """Move mouse to (x, y)."""
    pg = _get_pg()
    pg.moveTo(x, y, duration=duration)


def mouse_click(x=None, y=None, button="left", clicks=1):
    """Click at position or current position."""
    pg = _get_pg()
    if x is not None and y is not None:
        pg.click(x, y, clicks=clicks, button=button)
    else:
        pg.click(clicks=clicks, button=button)


def mouse_double_click(x=None, y=None):
    """Double click."""
    pg = _get_pg()
    if x is not None and y is not None:
        pg.doubleClick(x, y)
    else:
        pg.doubleClick()


def mouse_right_click(x=None, y=None):
    """Right click."""
    mouse_click(x, y, button="right")


def mouse_scroll(amount, x=None, y=None):
    """Scroll wheel. Positive=up, negative=down."""
    pg = _get_pg()
    if x is not None and y is not None:
        pg.scroll(amount, x, y)
    else:
        pg.scroll(amount)


def mouse_drag(x1, y1, x2, y2, duration=0.3):
    """Drag from (x1,y1) to (x2,y2)."""
    pg = _get_pg()
    pg.moveTo(x1, y1)
    pg.drag(x2 - x1, y2 - y1, duration=duration)


# ── Keyboard Control ──────────────────────────────────────────────

def key_press(*keys):
    """Press keys. E.g. key_press('ctrl', 'c'), key_press('enter')."""
    pg = _get_pg()
    for k in keys:
        pg.press(k)


def key_combo(*keys):
    """Press key combination. E.g. key_combo('ctrl', 'shift', 'esc')."""
    pg = _get_pg()
    pg.hotkey(*keys)


def type_text(text, interval=0.02):
    """Type text character by character."""
    pg = _get_pg()
    pg.typewrite(text, interval=interval) if text.isascii() else pg.write(text, interval=interval)


def type_unicode(text):
    """Type unicode text using clipboard."""
    import pyperclip
    pyperclip.copy(text)
    key_combo("ctrl", "v")
    time.sleep(0.1)


def paste_text(text):
    """Paste text from clipboard."""
    import pyperclip
    pyperclip.copy(text)
    key_combo("ctrl", "v")
    time.sleep(0.1)


# ── Window Management ─────────────────────────────────────────────

def get_active_window_title() -> str:
    """Get title of active window."""
    try:
        import win32gui
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    except Exception:
        return ""


def find_window(title: str) -> Optional[int]:
    """Find window by title substring. Returns hwnd."""
    import win32gui
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if title.lower() in t.lower():
                result.append(hwnd)
    win32gui.EnumWindows(callback, None)
    return result[0] if result else None


def activate_window(hwnd: int):
    """Bring window to front."""
    import win32gui
    try:
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception:
        pass


def focus_window(title: str) -> bool:
    """Find and focus window by title."""
    hwnd = find_window(title)
    if hwnd:
        activate_window(hwnd)
        return True
    return False


def get_screen_size() -> tuple:
    """Get screen width, height."""
    monitors = _get_monitors()
    if monitors:
        m = monitors[0]
        return m.width, m.height
    return 1920, 1080


# ── Chrome Profile Handling ───────────────────────────────────────

def find_chrome_profile(profile_name: str) -> Optional[str]:
    """Find Chrome profile directory name from display name."""
    chrome_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    if not chrome_path.exists():
        return None
    for d in chrome_path.iterdir():
        if d.is_dir() and (d.name == "Default" or d.name.startswith("Profile ")):
            prefs = d / "Preferences"
            if prefs.exists():
                try:
                    with open(prefs, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                    display_name = data.get("profile", {}).get("name", "")
                    if display_name.lower() == profile_name.lower():
                        return d.name
                except Exception:
                    pass
    return None


def open_chrome_profile(profile_name: str, url: str = "") -> bool:
    """Open Chrome with specific profile. Auto-detects profile directory."""
    profile_dir = find_chrome_profile(profile_name)
    if not profile_dir:
        return False

    args = [f"--profile-directory={profile_dir}"]
    if url:
        args.append(url)

    try:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        subprocess.Popen([chrome_path, f"--profile-directory={profile_dir}"] + ([url] if url else []), shell=False)
        return True
    except Exception:
        return False


def detect_chrome_profile_picker() -> bool:
    """Detect if Chrome profile picker is showing."""
    results = ocr_read(screen=True)
    for r in results:
        t = r.text.lower()
        if "who's using" in t or "who is using" in t or "profile" in t:
            return True
    return False


def click_chrome_profile(profile_name: str) -> bool:
    """Click on a Chrome profile in the profile picker screen."""
    # Find the profile name on screen
    result = ocr_find_text(profile_name, screen=True)
    if result:
        # Click on the profile name
        mouse_click(result.center[0], result.center[1])
        time.sleep(0.5)
        return True

    # Try finding first letter avatar
    first_letter = profile_name[0].upper() if profile_name else ""
    if first_letter:
        result = ocr_find_text(first_letter, screen=True)
        if result:
            mouse_click(result.center[0], result.center[1])
            time.sleep(0.5)
            return True
    return False


# ── Web Interaction ───────────────────────────────────────────────

def navigate_to(url: str):
    """Navigate browser to URL. Focuses address bar and types."""
    pg = _get_pg()
    # Focus address bar
    key_combo("ctrl", "l")
    time.sleep(0.1)
    # Type URL
    type_text(url, interval=0.01)
    time.sleep(0.05)
    key_press("enter")
    time.sleep(1)


def click_element(text: str, screen=True, region=None) -> bool:
    """Find and click an element by its text on screen."""
    result = ocr_find_text(text, screen=screen, region=region)
    if result:
        mouse_click(result.center[0], result.center[1])
        return True
    return False


def click_element_fuzzy(text: str, screen=True, region=None) -> bool:
    """Find and click element with fuzzy matching."""
    results = ocr_find_all(text, screen=screen, region=region, fuzzy=True)
    if results:
        # Click the one with highest confidence
        best = max(results, key=lambda r: r.confidence)
        mouse_click(best.center[0], best.center[1])
        return True
    return False


def type_in_field(text: str, field_text: str = None, clear_first=True):
    """Type text into a field. If field_text given, click field first."""
    if field_text:
        if not click_element(field_text):
            return False
        time.sleep(0.2)
    if clear_first:
        key_combo("ctrl", "a")
        time.sleep(0.05)
    type_text(text, interval=0.02)
    return True


def scroll_to_find(text: str, max_scrolls=10, direction="down") -> Optional[OCRResult]:
    """Scroll screen to find text element."""
    for i in range(max_scrolls):
        result = ocr_find_text(text)
        if result:
            return result
        scroll_amount = -3 if direction == "down" else 3
        mouse_scroll(scroll_amount)
        time.sleep(0.5)
    return None


def extract_prices(region=None) -> list[dict]:
    """Extract prices from screen. Returns [{text, value, position}]."""
    results = ocr_read(screen=True, region=region)
    prices = []
    price_pattern = re.compile(r'[\$£€]\s*\d[\d,]*\.?\d*|\d[\d,]*\.?\d*\s*(?:USD|GBP|EUR|INR)')
    for r in results:
        matches = price_pattern.findall(r.text)
        for m in matches:
            try:
                val = float(re.sub(r'[^\d.]', '', m))
                prices.append({"text": r.text, "value": val, "position": r.center, "raw": m})
            except ValueError:
                pass
    return prices


# ── Composite Actions ─────────────────────────────────────────────

def open_url_in_profile(url: str, profile_name: str = None) -> dict:
    """Open URL in Chrome with profile. OCR-scans screen to click profile picker if needed."""
    result = {"success": False, "steps": []}

    # Find Chrome executable
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    chrome_exe = None
    for p in chrome_paths:
        if os.path.isfile(p):
            chrome_exe = p
            break
    if not chrome_exe:
        result["steps"].append("Chrome not found")
        return result

    if profile_name:
        # Step 1: Try to find the profile directory name
        profile_dir = find_chrome_profile(profile_name)
        result["steps"].append(f"Profile dir: {profile_dir or 'not found, using OCR'}")

        # Step 2: Launch Chrome with profile directory (DO NOT kill existing Chrome)
        if profile_dir:
            try:
                subprocess.Popen([chrome_exe, f"--profile-directory={profile_dir}"])
                result["steps"].append(f"Launched Chrome with profile dir '{profile_dir}'")
            except Exception as e:
                result["steps"].append(f"Launch failed: {e}")
                return result
        else:
            try:
                subprocess.Popen([chrome_exe])
                result["steps"].append("Launched Chrome (no profile dir, will use OCR)")
            except Exception as e:
                result["steps"].append(f"Launch failed: {e}")
                return result

        # Step 4: Wait for Chrome to appear and check for profile picker
        time.sleep(3)
        profile_picked = False

        for attempt in range(5):
            # Check if profile picker is showing
            results = ocr_read(screen=True)
            picker_visible = False
            for r in results:
                t = r.text.lower()
                if "who's using" in t or "who is using" in t or "add" in t:
                    picker_visible = True
                    break

            if not picker_visible:
                # Chrome opened directly into a profile — we're done
                result["steps"].append("Chrome opened directly (no picker)")
                profile_picked = True
                break

            # Profile picker visible — find and click our profile
            result["steps"].append(f"Profile picker visible (attempt {attempt+1})")
            for r in results:
                if r.text.strip().lower() == profile_name.lower():
                    result["steps"].append(f"Found '{r.text}' at {r.center} — clicking")
                    mouse_click(r.center[0], r.center[1])
                    time.sleep(3)
                    profile_picked = True
                    break
                # Also check if first letter matches (avatar)
                if len(r.text.strip()) == 1 and r.text.strip().upper() == profile_name[0].upper():
                    result["steps"].append(f"Found avatar '{r.text}' at {r.center} — clicking")
                    mouse_click(r.center[0], r.center[1])
                    time.sleep(3)
                    profile_picked = True
                    break

            if profile_picked:
                break
            time.sleep(1)

        if not profile_picked:
            result["steps"].append("Could not find/click profile in picker")
            # Still try to navigate
    else:
        # No profile — just open Chrome
        try:
            subprocess.Popen([chrome_exe, url])
            result["steps"].append(f"Launched Chrome with {url}")
            result["success"] = True
            return result
        except Exception as e:
            result["steps"].append(f"Failed: {e}")
            return result

    # Step 5: Navigate to URL
    time.sleep(1)
    if url:
        navigate_to(url)
        result["steps"].append(f"Navigated to {url}")
        result["success"] = True
        time.sleep(1)

    return result


def scan_and_compare(urls: list[str], target_text: str = None, price_keyword: str = None) -> dict:
    """Open multiple URLs, scan each for target text or prices, compare."""
    results = {"pages": [], "best": None}

    for url in urls:
        navigate_to(url)
        time.sleep(2)

        page_data = {"url": url, "texts": [], "prices": []}

        if target_text:
            found = ocr_find_text(target_text)
            if found:
                page_data["texts"].append(found.text)

        if price_keyword:
            prices = extract_prices()
            page_data["prices"] = prices

        results["pages"].append(page_data)

    # Find best price
    all_prices = []
    for p in results["pages"]:
        for price in p["prices"]:
            all_prices.append({"url": p["url"], **price})

    if all_prices:
        results["best"] = min(all_prices, key=lambda x: x["value"])

    return results


def multi_page_scan(urls: list[str], ocr_filter: str = None) -> list[dict]:
    """Scan multiple pages, extract all text, optionally filter."""
    all_results = []
    for url in urls:
        navigate_to(url)
        time.sleep(2)
        texts = ocr_read(screen=True)
        page_data = {
            "url": url,
            "texts": [{"text": r.text, "position": r.center, "confidence": r.confidence} for r in texts]
        }
        if ocr_filter:
            page_data["filtered"] = [r.text for r in texts if ocr_filter.lower() in r.text.lower()]
        all_results.append(page_data)
    return all_results


# ── Utility ───────────────────────────────────────────────────────

def wait_for_text(text: str, timeout=10, interval=0.5) -> Optional[OCRResult]:
    """Wait for text to appear on screen."""
    start = time.time()
    while time.time() - start < timeout:
        result = ocr_find_text(text)
        if result:
            return result
        time.sleep(interval)
    return None


def wait_and_click(text: str, timeout=10) -> bool:
    """Wait for text to appear, then click it."""
    result = wait_for_text(text, timeout=timeout)
    if result:
        mouse_click(result.center[0], result.center[1])
        return True
    return False


def screenshot(save_path=None) -> str:
    """Take screenshot, optionally save. Returns path."""
    if not save_path:
        save_path = str(Path.home() / "AppData" / "Local" / "Temp" / f"jarvis_screenshot_{int(time.time())}.png")
    capture_screen(save_path=save_path)
    return save_path


def analyze_screen() -> dict:
    """Full screen analysis: OCR all text, detect UI elements."""
    results = ocr_read(screen=True)
    return {
        "total_elements": len(results),
        "elements": [
            {
                "text": r.text,
                "position": r.center,
                "bbox": r.bbox,
                "confidence": r.confidence
            } for r in results
        ],
        "screen_size": get_screen_size(),
    }
