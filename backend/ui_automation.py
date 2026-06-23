"""UI Automation Engine — computer vision, screen analysis, mouse/keyboard control, handwriting emulation, element detection."""

import os
import re
import json
import time
import math
import random
import subprocess
import platform
import base64

# ── Screen Capture ───────────────────────────────────────────────

def screenshot(path: str = None) -> tuple[str, int, int]:
    """Take screenshot. Returns (path, width, height) or raises."""
    if not path:
        path = f"/tmp/jarvis_screen_{int(time.time())}.png"
    subprocess.run(["screencapture", "-x", path], capture_output=True, timeout=10)
    if not os.path.isfile(path):
        raise RuntimeError("Screenshot failed")
    w, h = _get_image_size(path)
    return path, w, h

def screenshot_b64() -> str:
    """Take screenshot and return base64 string."""
    path, _, _ = screenshot()
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
    finally:
        try: os.remove(path)
        except: pass

def _get_image_size(path: str) -> tuple[int, int]:
    """Quick image size using sips on macOS."""
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                       capture_output=True, text=True, timeout=5)
    w = h = 0
    for line in r.stdout.split("\n"):
        if "pixelWidth" in line:
            w = int(line.split(":")[-1].strip())
        elif "pixelHeight" in line:
            h = int(line.split(":")[-1].strip())
    return w, h


# ── OCR — Screen Text Detection ─────────────────────────────────

_OCR_AVAILABLE = False

def ocr_available() -> bool:
    global _OCR_AVAILABLE
    if not _OCR_AVAILABLE:
        try:
            subprocess.run(["which", "tesseract"], capture_output=True, timeout=3, check=True)
            _OCR_AVAILABLE = True
        except:
            try:
                import pytesseract
                _OCR_AVAILABLE = True
            except:
                _OCR_AVAILABLE = False
    return _OCR_AVAILABLE


def ocr_image(path: str) -> list[dict]:
    """OCR an image. Returns list of {text, x, y, width, height, confidence}."""
    if not ocr_available():
        return _ocr_vision_framework(path)

    try:
        import pytesseract
        from PIL import Image
        img = Image.open(path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        results = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = int(data["conf"][i]) if data["conf"][i] != "-1" else 0
            if text and conf > 30:
                results.append({
                    "text": text,
                    "x": data["left"][i], "y": data["top"][i],
                    "width": data["width"][i], "height": data["height"][i],
                    "confidence": conf,
                })
        return results
    except Exception:
        return _ocr_vision_framework(path)


def _ocr_vision_framework(path: str) -> list[dict]:
    """Fallback: use macOS Vision framework via Swift script."""
    script = f"""
import Vision
import Cocoa

let img = NSImage(byReferencingFile: "{path}")!
let cgImg = img.cgImage(forProposedRect: nil, context: nil, hints: nil)!
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
try? VNImageRequestHandler(cgImage: cgImg, options: [:]).perform([request])
let results = request.results ?? []
let output = results.map {{ r in
    let box = r.boundingBox
    return ["text": r.topCandidates(1).first!.string, "x": box.origin.x, "y": box.origin.y, "w": box.size.width, "h": box.size.height]
}}
print(try! JSONSerialization.data(withJSONObject: output).base64EncodedString())
"""
    b64 = "/tmp/ocr_script_swift"
    with open(b64 + ".swift", "w") as f:
        f.write(script)
    r = subprocess.run(["swift", b64 + ".swift"], capture_output=True, text=True, timeout=30)
    try: os.remove(b64 + ".swift")
    except: pass
    if r.stdout.strip():
        try:
            data = json.loads(base64.b64decode(r.stdout.strip()))
            return [{"text": d["text"], "x": int(d["x"]*1920), "y": int(d["y"]*1080),
                     "width": int(d["w"]*1920), "height": int(d["h"]*1080), "confidence": 80}
                    for d in data]
        except: pass
    return []


def find_text_on_screen(target: str, screenshot_path: str = None) -> dict | None:
    """Find text on screen. Returns {x, y, width, height, text} or None."""
    path, sw, sh = screenshot_path or screenshot()
    try:
        elements = ocr_image(path)
        target_lower = target.lower()
        for el in elements:
            if target_lower in el["text"].lower():
                el["screen_width"] = sw
                el["screen_height"] = sh
                return el
        return None
    finally:
        if not screenshot_path and path:
            try: os.remove(path)
            except: pass


def find_all_matching(targets: list[str], screenshot_path: str = None) -> list[dict]:
    """Find multiple text targets in one screen pass."""
    path, sw, sh = screenshot_path or screenshot()
    try:
        elements = ocr_image(path)
        results = []
        target_set = {t.lower(): t for t in targets}
        for el in elements:
            tl = el["text"].lower()
            for k, v in target_set.items():
                if k in tl:
                    el["screen_width"] = sw
                    el["screen_height"] = sh
                    el["matched"] = v
                    results.append(el)
                    break
        return results
    finally:
        if not screenshot_path and path:
            try: os.remove(path)
            except: pass


# ── Mouse & Keyboard Control ────────────────────────────────────

def mouse_move(x: int, y: int):
    """Move mouse to absolute screen coordinates."""
    subprocess.run(["osascript", "-e",
        f'tell application "System Events" to set position of first mouse to {{{x}, {y}}}'],
        capture_output=True, timeout=5)

def mouse_click(x: int = None, y: int = None):
    """Click at current position or specified coordinates."""
    if x is not None and y is not None:
        mouse_move(x, y)
        time.sleep(0.05)
    subprocess.run(["osascript", "-e",
        'tell application "System Events" to click'],
        capture_output=True, timeout=5)

def mouse_double_click(x: int = None, y: int = None):
    """Double-click at position."""
    if x is not None and y is not None:
        mouse_move(x, y)
        time.sleep(0.05)
    subprocess.run(["osascript", "-e",
        'tell application "System Events" to double click'],
        capture_output=True, timeout=5)

def mouse_right_click(x: int = None, y: int = None):
    """Right-click at position."""
    if x is not None and y is not None:
        mouse_move(x, y)
        time.sleep(0.05)
    subprocess.run(["osascript", "-e",
        'tell application "System Events" to click button 2'],
        capture_output=True, timeout=5)

def mouse_drag(x1: int, y1: int, x2: int, y2: int, steps: int = 20):
    """Drag mouse from (x1,y1) to (x2,y2) in natural steps."""
    mouse_move(x1, y1)
    time.sleep(0.1)
    subprocess.run(["osascript", "-e",
        f'tell application "System Events" to drag from {{{x1}, {y1}}} to {{{x2}, {y2}}}'],
        capture_output=True, timeout=10)

def type_text(text: str):
    """Type text using keyboard."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    subprocess.run(["osascript", "-e",
        f'tell application "System Events" to keystroke "{escaped[:500]}"'],
        capture_output=True, timeout=10)

def key_press(key: str):
    """Press a special key. Keys: return, tab, escape, delete, etc."""
    subprocess.run(["osascript", "-e",
        f'tell application "System Events" to key code {_key_code(key)}'],
        capture_output=True, timeout=5)

def _key_code(key: str) -> int:
    """Convert key name to macOS key code."""
    codes = {
        "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
        "escape": 53, "esc": 53, "left": 123, "right": 124, "down": 125,
        "up": 126, "cmd": 55, "shift": 56, "option": 58, "ctrl": 59,
        "caps": 57, "f1": 122, "f2": 120, "f3": 99, "f4": 118,
        "f5": 96, "f6": 97, "f7": 98, "f8": 100, "f9": 101,
        "f10": 109, "f11": 103, "f12": 111, "home": 115, "end": 119,
        "pageup": 116, "pagedown": 121,
    }
    return codes.get(key.lower(), 36)


def open_app(app_name: str) -> bool:
    """Open a macOS application by name."""
    r = subprocess.run(["open", "-a", app_name], capture_output=True, timeout=10)
    time.sleep(2)
    return r.returncode == 0

def activate_app(app_name: str):
    """Bring an application to the foreground."""
    subprocess.run(["osascript", "-e",
        f'tell application "{app_name}" to activate'],
        capture_output=True, timeout=5)
    time.sleep(1)

def app_is_running(app_name: str) -> bool:
    """Check if an application is running."""
    r = subprocess.run(["osascript", "-e",
        f'tell application "System Events" to exists process "{app_name}"'],
        capture_output=True, text=True, timeout=5)
    return "true" in r.stdout.lower()


# ── Natural Handwriting Emulation ───────────────────────────────

def handwrite_text(text: str, start_x: int, start_y: int, line_height: int = 40,
                  char_width: int = 12, speed_variation: float = 0.3):
    """Write text in natural handwriting style using variable-velocity strokes.
    
    Generates smoothed bezier-like paths with natural jitter, mimicking human handwriting.
    """
    random.seed()
    x, y = start_x, start_y
    baseline_jitter = lambda: random.uniform(-3, 3)
    speed_jitter = lambda: random.uniform(1 - speed_variation, 1 + speed_variation)

    for char in text:
        if char == "\n":
            x = start_x
            y += line_height
            continue
        elif char == " ":
            x += char_width * 3 + baseline_jitter()
            continue

        char_width_px = char_width + random.uniform(-2, 5)
        end_x = x + char_width_px
        end_y = y + baseline_jitter()

        # Generate natural stroke path with bezier-like smoothing
        _natural_stroke(x, y, end_x, end_y, char)

        x = end_x + random.uniform(1, 4)

def _natural_stroke(x1: float, y1: float, x2: float, y2: float, char: str):
    """Draw a natural stroke from (x1,y1) to (x2,y2) with human-like variation."""
    steps = max(5, int(math.sqrt((x2-x1)**2 + (y2-y1)**2) / 3))
    steps = int(steps * random.uniform(0.8, 1.5))

    control = (
        (x1 + x2) / 2 + random.uniform(-10, 10),
        (y1 + y2) / 2 + random.uniform(-15, 15)
    )

    for i in range(steps + 1):
        t = i / steps
        t = t ** 0.9 if random.random() < 0.3 else t ** 1.1

        # Quadratic bezier
        px = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * control[0] + t ** 2 * x2
        py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * control[1] + t ** 2 * y2

        # Natural jitter
        px += random.uniform(-1.5, 1.5)
        py += random.uniform(-2, 2)

        subprocess.run(["osascript", "-e",
            f'tell application "System Events" to set position of first mouse to {{{int(px)}, {int(py)}}}'],
            capture_output=True, timeout=2)
        time.sleep(random.uniform(0.005, 0.025))


# ── Element Clicking (Find + Click) ─────────────────────────────

def click_text(label: str, timeout: float = 10) -> bool:
    """Find a text label on screen and click it. Returns True if found."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            el = find_text_on_screen(label)
            if el:
                cx = el["x"] + el["width"] // 2
                cy = el["y"] + el["height"] // 2
                mouse_click(cx, cy)
                return True
        except:
            pass
        time.sleep(1)
    return False

def wait_for_text(text: str, timeout: float = 30) -> bool:
    """Wait for text to appear on screen. Returns True if found."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        el = find_text_on_screen(text)
        if el:
            return True
        time.sleep(1)
    return False


# ── Full Page / Region Crawl ────────────────────────────────────

def get_screen_text() -> str:
    """Get all text currently visible on screen."""
    path, _, _ = screenshot()
    try:
        elements = ocr_image(path)
        return "\n".join(el["text"] for el in elements)
    finally:
        try: os.remove(path)
        except: pass


def locate_and_click_ui(parent_app: str, menu_path: list[str]) -> bool:
    """Navigate a menu hierarchy by clicking labels sequentially.
    
    Example: locate_and_click_ui("Microsoft Teams", ["File", "Open"])
    """
    activate_app(parent_app)
    time.sleep(1)
    for label in menu_path:
        if not click_text(label, timeout=5):
            return False
        time.sleep(0.5)
    return True
