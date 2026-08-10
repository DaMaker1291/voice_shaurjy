"""
Universal Task Engine — 4-tier dispatch for maximum speed.

Tier 1: Python APIs (0ms) - python-pptx, openpyxl, python-docx,直接生成文件
Tier 2: IPC/CLI (<50ms) - blender --background, headless chrome, powershell COM
Tier 3: Accessibility APIs (<100ms) - pywinauto, UIAutomation, hotkey injection
Tier 4: Vision+Mouse (fallback) - screenshot + VLM + pyautogui (only for canvas/games)

Every task tries Tier 1 first. Falls back only when needed.
Results always land on the user's PRIMARY desktop.
"""

import subprocess
import os
import sys
import time
import json
import tempfile
import threading
import re
from typing import Optional, Any, Dict, List, Callable
from dataclasses import dataclass, field


@dataclass
class TaskResult:
    success: bool
    message: str
    tier_used: int = 0
    output_path: str = ""
    duration_ms: float = 0
    details: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "success": self.success,
            "message": self.message,
            "tier_used": self.tier_used,
            "output_path": self.output_path,
            "duration_ms": self.duration_ms,
            "details": self.details,
        }


def _ps(cmd: str, timeout: float = 15.0) -> str:
    """Run PowerShell command and return stdout."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _find_exe(name: str) -> Optional[str]:
    """Find executable path by name."""
    name_lower = name.lower().strip()
    known = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "word": "winword.exe",
        "excel": "excel.exe",
        "powerpoint": "powerpnt.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "pwsh.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "file manager": "explorer.exe",
    }
    if name_lower in known:
        return known[name_lower]
    # Try where command
    try:
        r = subprocess.run(["where", name_lower], capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            return r.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    # Try common paths
    for base in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), os.path.expanduser("~\\AppData\\Local\\Microsoft\\WindowsApps")]:
        full = os.path.join(base, name_lower)
        if os.path.exists(full):
            return full
    return None


def _find_browser(browser: str = "chrome") -> Optional[str]:
    """Find browser executable."""
    paths = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
    }
    for p in paths.get(browser, []):
        if os.path.exists(p):
            return p
    return None


class UniversalTaskEngine:
    """
    4-tier universal task engine.
    
    Tries the fastest tier first. Falls back only when needed.
    All results land on user's primary desktop (visible to user).
    """

    def __init__(self):
        self._browser_proc = None
        self._browser_ws = None
        self._playwright = None
        self._pw_browser = None

    # ═══════════════════════════════════════════════════════════════
    # DOCUMENT GENERATION — Tier 1 (Python APIs, 0ms)
    # ═══════════════════════════════════════════════════════════════

    def create_word(self, title: str, content: str, save_path: str = "") -> TaskResult:
        """Generate Word document directly via doc_compiler. No Word needed."""
        t0 = time.time()
        if not save_path:
            save_path = os.path.join(os.path.expanduser("~"), "Desktop", f"{title.replace(' ', '_')}.docx")

        try:
            from doc_compiler import create_docx
            # Convert simple text content into structured paragraphs
            paragraphs = []
            paragraphs.append({"type": "heading", "text": title, "level": 1})
            for para in content.split("\n"):
                if para.strip():
                    paragraphs.append({"type": "paragraph", "text": para.strip()})
            create_docx(paragraphs, save_path)
            return TaskResult(True, f"Document saved: {save_path}", tier_used=1,
                             output_path=save_path, duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return TaskResult(False, f"Word creation failed: {e}", tier_used=1)

    def create_excel(self, title: str, headers: list, rows: list, save_path: str = "") -> TaskResult:
        """Generate Excel spreadsheet directly via openpyxl. No Excel needed."""
        t0 = time.time()
        try:
            from openpyxl import Workbook
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "openpyxl"], capture_output=True)
            from openpyxl import Workbook

        if not save_path:
            save_path = os.path.join(os.path.expanduser("~"), "Desktop", f"{title.replace(' ', '_')}.xlsx")

        wb = Workbook()
        ws = wb.active
        ws.title = title[:31]
        if headers:
            ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(save_path)
        return TaskResult(True, f"Spreadsheet saved: {save_path}", tier_used=1,
                         output_path=save_path, duration_ms=(time.time()-t0)*1000)

    def create_powerpoint(self, title: str, slides: list, save_path: str = "") -> TaskResult:
        """Generate PowerPoint directly via exec_deck. No PowerPoint needed."""
        t0 = time.time()
        if not save_path:
            save_path = os.path.join(os.path.expanduser("~"), "Desktop", f"{title.replace(' ', '_')}.pptx")

        try:
            from exec_deck import create_pptx
            slides_data = []
            slides_data.append({"type": "title", "title": title, "subtitle": "Automated Report"})
            for s in slides:
                if isinstance(s, dict):
                    slides_data.append({
                        "type": s.get("type", "content"),
                        "title": s.get("title", "Slide"),
                        "content": s.get("content", s.get("text", "")),
                        "bullets": s.get("bullets", []),
                        "metrics": s.get("metrics", {}),
                        "table": s.get("table", {}),
                        "chart": s.get("chart", {})
                    })
                elif isinstance(s, str):
                    slides_data.append({"type": "content", "title": s, "content": ""})
            create_pptx(slides_data, save_path)
            return TaskResult(True, f"Presentation saved: {save_path} ({len(slides)+1} slides)", tier_used=1,
                             output_path=save_path, duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return TaskResult(False, f"PowerPoint creation failed: {e}", tier_used=1)

    # ═══════════════════════════════════════════════════════════════
    # IPC / CLI EXECUTION — Tier 2 (subprocess, <50ms)
    # ═══════════════════════════════════════════════════════════════

    def run_blender(self, python_code: str, background: bool = True) -> TaskResult:
        """Run Blender script headlessly. No GUI needed."""
        t0 = time.time()
        blender = self._find_blender()
        if not blender:
            return TaskResult(False, "Blender not found", tier_used=2)

        script = os.path.join(tempfile.gettempdir(), "jarvis_blender.py")
        with open(script, "w") as f:
            f.write(python_code)

        cmd = [blender]
        if background:
            cmd.append("--background")
        cmd.extend(["--python", script])

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            output = r.stdout + r.stderr
            return TaskResult(r.returncode == 0, output[:2000] if output else "Blender script completed",
                             tier_used=2, duration_ms=(time.time()-t0)*1000)
        except subprocess.TimeoutExpired:
            return TaskResult(False, "Blender timed out after 300s", tier_used=2)
        except Exception as e:
            return TaskResult(False, f"Blender error: {e}", tier_used=2)

    def run_powershell(self, command: str, timeout: float = 30) -> TaskResult:
        """Run PowerShell command directly."""
        t0 = time.time()
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True, text=True, timeout=timeout,
            )
            output = r.stdout + r.stderr
            return TaskResult(r.returncode == 0, output[:2000] if output else "Completed",
                             tier_used=2, duration_ms=(time.time()-t0)*1000)
        except subprocess.TimeoutExpired:
            return TaskResult(False, f"Timed out after {timeout}s", tier_used=2)
        except Exception as e:
            return TaskResult(False, f"Error: {e}", tier_used=2)

    def run_command(self, command: list, timeout: float = 300) -> TaskResult:
        """Run arbitrary command."""
        t0 = time.time()
        try:
            r = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            output = r.stdout + r.stderr
            return TaskResult(r.returncode == 0, output[:2000] if output else "Completed",
                             tier_used=2, duration_ms=(time.time()-t0)*1000)
        except subprocess.TimeoutExpired:
            return TaskResult(False, f"Timed out after {timeout}s", tier_used=2)
        except Exception as e:
            return TaskResult(False, f"Error: {e}", tier_used=2)

    def open_app(self, app_name: str, args: list = None) -> TaskResult:
        """Open app on primary desktop (visible to user)."""
        t0 = time.time()
        exe = _find_exe(app_name)
        if not exe:
            return TaskResult(False, f"App not found: {app_name}", tier_used=2)
        try:
            cmd = [exe] + (args or [])
            proc = subprocess.Popen(cmd, shell=False)
            return TaskResult(True, f"Launched {app_name} (PID {proc.pid})", tier_used=2,
                             duration_ms=(time.time()-t0)*1000, details={"pid": proc.pid})
        except Exception as e:
            return TaskResult(False, f"Failed to launch {app_name}: {e}", tier_used=2)

    # ═══════════════════════════════════════════════════════════════
    # BROWSER AUTOMATION — Tier 2 (Playwright/COM, <100ms)
    # ═══════════════════════════════════════════════════════════════

    def browse(self, url: str, browser: str = "chrome") -> TaskResult:
        """Open URL in browser on primary desktop."""
        t0 = time.time()
        # Try COM first (if Chrome already open)
        try:
            r = _ps(f'try {{ $w = [Runtime.InteropServices.Marshal]::GetActiveObject("Chrome.Application"); $w.ActiveWindow.LocationURL = "{url}"; "OK" }} catch {{ "" }}')
            if "OK" in r:
                return TaskResult(True, f"Navigated to {url}", tier_used=3,
                                 duration_ms=(time.time()-t0)*1000)
        except Exception:
            pass
        # Launch browser
        exe = _find_browser(browser)
        if not exe:
            return TaskResult(False, f"Browser not found: {browser}", tier_used=2)
        try:
            proc = subprocess.Popen([exe, url], shell=False)
            return TaskResult(True, f"Browsing {url} (PID {proc.pid})", tier_used=2,
                             duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return TaskResult(False, f"Failed to open browser: {e}", tier_used=2)

    def search_web(self, query: str) -> TaskResult:
        """Search Google for a query."""
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        return self.browse(url)

    def batch_browse(self, urls: list, headless: bool = True) -> TaskResult:
        """Process many URLs without crashing RAM. Uses headless batching."""
        t0 = time.time()
        batch_size = 10
        results = []
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i+batch_size]
            for url in batch:
                try:
                    r = self.browse(url)
                    results.append({"url": url, "success": r.success, "message": r.message})
                except Exception as e:
                    results.append({"url": url, "success": False, "message": str(e)})
        return TaskResult(True, f"Processed {len(urls)} URLs in batches", tier_used=2,
                         duration_ms=(time.time()-t0)*1000,
                         details={"results": results})

    # ═══════════════════════════════════════════════════════════════
    # TEXT/KEYBOARD INJECTION — Tier 3 (pyautogui + clipboard)
    # ═══════════════════════════════════════════════════════════════

    def type_text(self, text: str, instant: bool = True) -> TaskResult:
        """Type text. Instant paste via clipboard or character-by-character."""
        t0 = time.time()
        try:
            import pyautogui
            import pyperclip
            pyautogui.FAILSAFE = False
            if instant:
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
            else:
                pyautogui.write(text, interval=0.01)
            return TaskResult(True, f"Typed: {text[:80]}...", tier_used=3,
                             duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return TaskResult(False, f"Type failed: {e}", tier_used=3)

    def press_key(self, key: str) -> TaskResult:
        """Press a key or key combo (e.g. 'ctrl+c', 'enter', 'alt+tab')."""
        t0 = time.time()
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            if "+" in key:
                keys = [k.strip() for k in key.split("+")]
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key)
            return TaskResult(True, f"Pressed: {key}", tier_used=3,
                             duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return TaskResult(False, f"Key press failed: {e}", tier_used=3)

    def click_at(self, x: int, y: int) -> TaskResult:
        """Click at screen coordinates."""
        t0 = time.time()
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.click(x, y)
            return TaskResult(True, f"Clicked at ({x}, {y})", tier_used=4,
                             duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return TaskResult(False, f"Click failed: {e}", tier_used=4)

    def screenshot(self, path: str = "") -> TaskResult:
        """Take screenshot."""
        t0 = time.time()
        if not path:
            path = os.path.join(tempfile.gettempdir(), "jarvis_screenshot.png")
        try:
            import pyautogui
            pyautogui.screenshot(path)
            return TaskResult(True, f"Screenshot saved: {path}", tier_used=4,
                             output_path=path, duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return TaskResult(False, f"Screenshot failed: {e}", tier_used=4)

    def get_clipboard(self) -> TaskResult:
        """Get clipboard content."""
        try:
            import pyperclip
            text = pyperclip.paste()
            return TaskResult(True, text[:5000], tier_used=3)
        except Exception as e:
            return TaskResult(False, f"Clipboard error: {e}", tier_used=3)

    def set_clipboard(self, text: str) -> TaskResult:
        """Set clipboard content."""
        try:
            import pyperclip
            pyperclip.copy(text)
            return TaskResult(True, "Clipboard set", tier_used=3)
        except Exception as e:
            return TaskResult(False, f"Clipboard error: {e}", tier_used=3)

    # ═══════════════════════════════════════════════════════════════
    # WINDOW MANAGEMENT — Tier 3 (pywinauto / UIAutomation)
    # ═══════════════════════════════════════════════════════════════

    def focus_window(self, title_substr: str) -> TaskResult:
        """Focus a window by title substring."""
        t0 = time.time()
        try:
            import pywinauto
            app = pywinauto.Desktop(backend="uia")
            windows = app.windows()
            for w in windows:
                if title_substr.lower() in w.window_text().lower():
                    w.set_focus()
                    return TaskResult(True, f"Focused: {w.window_text()}", tier_used=3,
                                     duration_ms=(time.time()-t0)*1000)
            return TaskResult(False, f"Window not found: {title_substr}", tier_used=3)
        except ImportError:
            # Fallback to PowerShell
            r = _ps(f'(Get-Process | Where-Object {{$_.MainWindowTitle -like "*{title_substr}*"}}).MainWindowHandle | ForEach-Object {{ Add-Type -Name Win -Namespace Native -MemberDefinition \'[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);\'; [Native.Win]::SetForegroundWindow($_) }}')
            return TaskResult(True, f"Focused via PowerShell: {title_substr}", tier_used=3,
                             duration_ms=(time.time()-t0)*1000)

    def list_windows(self) -> TaskResult:
        """List all visible windows."""
        try:
            import pywinauto
            app = pywinauto.Desktop(backend="uia")
            windows = app.windows()
            titles = [(w.window_text(), w.process_id()) for w in windows if w.window_text().strip()]
            return TaskResult(True, json.dumps(titles[:50], indent=1), tier_used=3,
                             details={"windows": titles})
        except ImportError:
            r = _ps('Get-Process | Where-Object {$_.MainWindowTitle -ne ""} | Select-Object ProcessName, Id, MainWindowTitle | ConvertTo-Json')
            return TaskResult(True, r[:2000], tier_used=3)

    def close_window(self, title_substr: str) -> TaskResult:
        """Close a window by title substring."""
        t0 = time.time()
        try:
            import pywinauto
            app = pywinauto.Desktop(backend="uia")
            for w in app.windows():
                if title_substr.lower() in w.window_text().lower():
                    w.close()
                    return TaskResult(True, f"Closed: {w.window_text()}", tier_used=3,
                                     duration_ms=(time.time()-t0)*1000)
            return TaskResult(False, f"Window not found: {title_substr}", tier_used=3)
        except ImportError:
            _ps(f'Get-Process | Where-Object {{$_.MainWindowTitle -like "*{title_substr}*"}} | Stop-Process -Force')
            return TaskResult(True, f"Closed via PowerShell: {title_substr}", tier_used=3,
                             duration_ms=(time.time()-t0)*1000)

    # ═══════════════════════════════════════════════════════════════
    # EMAIL — Tier 2 (COM automation)
    # ═══════════════════════════════════════════════════════════════

    def send_email(self, to: str, subject: str, body: str) -> TaskResult:
        """Send email via Outlook COM automation."""
        t0 = time.time()
        t = to.replace('"', '""')
        s = subject.replace('"', '""')
        b = body.replace('"', '""').replace("\n", "\\n")
        r = _ps(f'try {{ $o = New-Object -ComObject Outlook.Application; $m = $o.CreateItem(0); $m.To = "{t}"; $m.Subject = "{s}"; $m.Body = "{b}"; $m.Send(); "OK" }} catch {{ "FAIL:$_" }}')
        success = "OK" in r
        return TaskResult(success, f"Email sent to {to}" if success else f"Failed: {r}",
                         tier_used=2, duration_ms=(time.time()-t0)*1000)

    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _find_blender(self) -> Optional[str]:
        paths = [
            r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        try:
            r = subprocess.run(["where", "blender"], capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                return r.stdout.strip().split("\n")[0].strip()
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════════════════════
    # UNIVERSAL DISPATCH — Routes any task to fastest tier
    # ═══════════════════════════════════════════════════════════════

    def do_task(self, task_description: str) -> TaskResult:
        """Universal task dispatcher. Routes to fastest tier automatically."""
        desc = task_description.lower()

        # Tier 1: Document generation (Python APIs, instant)
        if any(w in desc for w in ["create document", "word", "essay", "report", "write document"]):
            title = re.search(r"(?:create|write|make)\s+(?:a\s+)?(?:document|doc|word|essay|report)\s+(?:about|on|titled|called)?\s*(.+?)$", task_description, re.I)
            t = title.group(1).strip() if title else "Document"
            content = re.search(r"(?:about|on|containing|with)\s+(.+)$", task_description, re.I)
            c = content.group(1).strip() if content else ""
            return self.create_word(t, c)

        if any(w in desc for w in ["excel", "spreadsheet", "table", "budget"]):
            title = re.search(r"(?:create|make|new)\s+(?:excel|spreadsheet|table)\s+(?:called|named)?\s*(.+?)$", task_description, re.I)
            t = title.group(1).strip() if title else "Spreadsheet"
            return self.create_excel(t, [], [])

        if any(w in desc for w in ["powerpoint", "presentation", "ppt", "slides"]):
            title = re.search(r"(?:create|make|new)\s+(?:presentation|ppt|powerpoint)\s+(?:called|named)?\s*(.+?)$", task_description, re.I)
            t = title.group(1).strip() if title else "Presentation"
            return self.create_powerpoint(t, [{"title": "Slide 1", "content": "Content"}])

        # Tier 2: IPC execution
        if any(w in desc for w in ["blender", "3d model", "render"]):
            code = 'import bpy; bpy.ops.mesh.primitive_cube_add(); print("Cube created")'
            return self.run_blender(code)

        # Tier 2/3: Browser
        if any(w in desc for w in ["browse", "open website", "go to http", "open http", "open google", "open youtube"]):
            url_match = re.search(r"(https?://\S+|www\.\S+)", task_description)
            if url_match:
                return self.browse(url_match.group(0))
            q = re.sub(r".*?(?:browse|open|go to)\s+", "", task_description, flags=re.I).strip()
            if q:
                return self.search_web(q)
            return TaskResult(False, "What should I browse?")

        if any(w in desc for w in ["research", "search", "find", "look up", "investigate"]):
            query = re.sub(r".*?(?:research|search|find|look up|investigate)\s+", "", task_description, flags=re.I).strip()
            if query:
                return self.search_web(query)
            return TaskResult(False, "What should I research?")

        if any(w in desc for w in ["email", "send mail", "compose"]):
            to_match = re.search(r"(\S+@\S+)", task_description)
            to = to_match.group(1) if to_match else ""
            body = re.search(r"(?:saying|body|content|message)\s+(.+)$", task_description, re.I)
            b = body.group(1).strip() if body else ""
            if to:
                return self.send_email(to, "Message from JARVIS", b)
            return TaskResult(False, "Who should I email?")

        # Tier 3: App launch
        if any(w in desc for w in ["open ", "launch ", "start "]):
            app = re.sub(r".*?(?:open|launch|start)\s+", "", task_description, flags=re.I).strip()
            if app:
                return self.open_app(app.split()[0])

        # Tier 3: Text input
        if any(w in desc for w in ["type ", "write ", "input "]):
            text = re.sub(r".*?(?:type|write|input)\s+", "", task_description, flags=re.I).strip()
            if text:
                return self.type_text(text)

        # Fallback: try as app name
        words = task_description.split()
        if words:
            return self.open_app(words[0])

        return TaskResult(False, f"I don't know how to do: {task_description}")


# Singleton
_engine = None

def get_engine() -> UniversalTaskEngine:
    global _engine
    if _engine is None:
        _engine = UniversalTaskEngine()
    return _engine
