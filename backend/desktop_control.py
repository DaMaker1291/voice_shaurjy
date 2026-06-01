"""Desktop control — windows, mouse, keyboard, screen, UI automation via PowerShell. Controls ANY app on the system."""

from ps_executor import ps, ps_batch


# ── Window Management ──────────────────────────────────────────────

def list_windows() -> list[dict]:
    """List all visible windows with title, class, handle, position."""
    raw = ps("""
        Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            using System.Text;
            using System.Collections.Generic;
            public class WinAPI {
                [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
                [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
                [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
                [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
                [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
                [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
                [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
                [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int x, int y, int w, int h, bool repaint);
                public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
                public static List<string> EnumAll() {
                    var list = new List<string>();
                    EnumWindows((hWnd, lp) => {
                        if (IsWindowVisible(hWnd)) {
                            var sb = new StringBuilder(256);
                            GetWindowText(hWnd, sb, 256);
                            if (sb.Length > 0) {
                                GetWindowThreadProcessId(hWnd, out uint pid);
                                RECT r; GetWindowRect(hWnd, out r);
                                list.Add($"{hWnd}|{sb}|{pid}|{r.Left}|{r.Top}|{r.Right - r.Left}|{r.Bottom - r.Top}");
                            }
                        }
                        return true;
                    }, IntPtr.Zero);
                    return list;
                }
            }
        "@
        $wins = [WinAPI]::EnumAll()
        $wins -join ";;"
    """)
    windows = []
    for line in (raw or "").split(";;"):
        parts = line.strip().split("|")
        if len(parts) >= 5:
            windows.append({
                "handle": parts[0], "title": parts[1], "pid": parts[2],
                "x": int(parts[3]), "y": int(parts[4]),
                "w": int(parts[5]), "h": int(parts[6]) if len(parts) > 6 else 0,
            })
    return windows


def focus_window(title: str) -> bool:
    """Focus a window by title substring. Returns True if found."""
    r = ps(f"""
        Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            using System.Text;
            public class W {{
                [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
                [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
                [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
                [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
                [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                public static bool Focus(string t) {{
                    bool found = false;
                    EnumWindows((hWnd, lp) => {{
                        if (!found && IsWindowVisible(hWnd)) {{
                            var sb = new StringBuilder(256);
                            GetWindowText(hWnd, sb, 256);
                            if (sb.ToString().ToLower().Contains(t.ToLower())) {{
                                SetForegroundWindow(hWnd); ShowWindow(hWnd, 9);
                                found = true;
                            }}
                        }}
                        return !found;
                    }}, IntPtr.Zero);
                    return found;
                }}
            }}
        "@
        [W]::Focus('{title}')
    """)
    return r.strip().lower() == "true"


def close_window(title: str) -> bool:
    """Close a window by title substring."""
    r = ps(f"""
        Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            using System.Text;
            public class W {{
                [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
                [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
                [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
                [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
                public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                const uint WM_CLOSE = 0x0010;
                public static bool Close(string t) {{
                    bool found = false;
                    EnumWindows((hWnd, lp) => {{
                        if (!found && IsWindowVisible(hWnd)) {{
                            var sb = new StringBuilder(256);
                            GetWindowText(hWnd, sb, 256);
                            if (sb.ToString().ToLower().Contains(t.ToLower())) {{
                                SendMessage(hWnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
                                found = true;
                            }}
                        }}
                        return !found;
                    }}, IntPtr.Zero);
                    return found;
                }}
            }}
        "@
        [W]::Close('{title}')
    """)
    return r.strip().lower() == "true"


def minimize_window(title: str) -> bool:
    """Minimize a window by title substring."""
    r = ps(f"""
        Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            using System.Text;
            public class W {{
                [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
                [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
                [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
                [DllImport("user32.dll")] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                const int SW_MINIMIZE = 6;
                public static bool Minimize(string t) {{
                    bool found = false;
                    EnumWindows((hWnd, lp) => {{
                        if (!found && IsWindowVisible(hWnd)) {{
                            var sb = new StringBuilder(256);
                            GetWindowText(hWnd, sb, 256);
                            if (sb.ToString().ToLower().Contains(t.ToLower())) {{
                                ShowWindow(hWnd, SW_MINIMIZE);
                                found = true;
                            }}
                        }}
                        return !found;
                    }}, IntPtr.Zero);
                    return found;
                }}
            }}
        "@
        [W]::Minimize('{title}')
    """)
    return r.strip().lower() == "true"


def maximize_window(title: str) -> bool:
    """Maximize a window by title substring."""
    r = ps(f"""
        Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            using System.Text;
            public class W {{
                [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
                [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
                [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
                [DllImport("user32.dll")] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
                const int SW_MAXIMIZE = 3;
                public static bool Maximize(string t) {{
                    bool found = false;
                    EnumWindows((hWnd, lp) => {{
                        if (!found && IsWindowVisible(hWnd)) {{
                            var sb = new StringBuilder(256);
                            GetWindowText(hWnd, sb, 256);
                            if (sb.ToString().ToLower().Contains(t.ToLower())) {{
                                ShowWindow(hWnd, SW_MAXIMIZE);
                                found = true;
                            }}
                        }}
                        return !found;
                    }}, IntPtr.Zero);
                    return found;
                }}
            }}
        "@
        [W]::Maximize('{title}')
    """)
    return r.strip().lower() == "true"


# ── Mouse Control ─────────────────────────────────────────────────

def mouse_move(x: int, y: int):
    """Move mouse to absolute screen position."""
    ps(f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x},{y})")


def mouse_click(x: int = -1, y: int = -1, button: str = "left"):
    """Click at position (or current position if -1)."""
    b = "[System.Windows.Forms.MouseButtons]::Left" if button == "left" else "[System.Windows.Forms.MouseButtons]::Right"
    if x >= 0: mouse_move(x, y)
    ps(f"""
        Add-Type -AssemblyName System.Windows.Forms;
        [System.Windows.Forms.Mouse]::Click({b})
    """)


def mouse_double_click(x: int = -1, y: int = -1):
    if x >= 0: mouse_move(x, y)
    ps("""
        Add-Type -AssemblyName System.Windows.Forms;
        [System.Windows.Forms.Mouse]::DoubleClick([System.Windows.Forms.MouseButtons]::Left)
    """)


def mouse_drag(x1: int, y1: int, x2: int, y2: int):
    """Drag mouse from (x1,y1) to (x2,y2)."""
    ps(f"""
        Add-Type -AssemblyName System.Windows.Forms;
        [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x1},{y1});
        [System.Windows.Forms.Mouse]::Down([System.Windows.Forms.MouseButtons]::Left);
        Start-Sleep -Milliseconds 50;
        [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x2},{y2});
        Start-Sleep -Milliseconds 50;
        [System.Windows.Forms.Mouse]::Up([System.Windows.Forms.MouseButtons]::Left)
    """)


def mouse_scroll(amount: int):
    """Scroll mouse wheel (positive=up, negative=down)."""
    ps(f"""
        Add-Type -AssemblyName System.Windows.Forms;
        [System.Windows.Forms.Mouse]::Wheel({amount})
    """)


def get_cursor_pos() -> tuple:
    """Get current cursor position (x, y)."""
    r = ps("[System.Windows.Forms.Cursor]::Position.ToString()")
    parts = r.strip("{ }").split(",")
    if len(parts) == 2:
        return (int(parts[0].split("=")[-1]), int(parts[1].split("=")[-1]))
    return (0, 0)


# ── Keyboard Control ──────────────────────────────────────────────

def type_text(text: str):
    """Type text into the active window. Handles special chars."""
    escaped = text.replace('"', '\\"').replace("'", "''").replace("`", "``")
    ps(f"""
        Add-Type -AssemblyName System.Windows.Forms;
        [System.Windows.Forms.SendKeys]::SendWait("{escaped}")
    """)


def send_keys(keys: str):
    """Send keyboard shortcuts. Use {ENTER}, {TAB}, ^C, %F4, etc."""
    ps(f"""
        $k = New-Object -ComObject WScript.Shell;
        $k.SendKeys("{keys}")
    """)


def hotkey(*keys: str):
    """Send a hotkey combination. e.g. hotkey('Ctrl','Alt','Del')"""
    mapping = {"ctrl": "^", "alt": "%", "shift": "+", "win": "^{ESC}"}
    combo = ""
    for k in keys:
        k_lower = k.lower()
        if k_lower in mapping:
            combo += mapping[k_lower]
        else:
            combo += "{" + k.upper() + "}"
    send_keys(combo)


# ── Screen Capture ────────────────────────────────────────────────

def screenshot_save(path: str = ""):
    """Take screenshot of entire screen, save to path or desktop."""
    if not path:
        import os
        path = os.path.expanduser("~/Desktop/screenshot.png")
    ps(f"""
        Add-Type -AssemblyName System.Windows.Forms;
        $b = [System.Drawing.Bitmap]::new(
            [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,
            [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
        );
        $g = [System.Drawing.Graphics]::FromImage($b);
        $g.CopyFromScreen(0, 0, 0, 0, $b.Size);
        $b.Save("{path}");
        $g.Dispose(); $b.Dispose();
        "{path}"
    """)
    return path


def screenshot_region(x: int, y: int, w: int, h: int, path: str = "") -> str:
    """Take screenshot of a region, save to path."""
    if not path:
        import os
        path = os.path.expanduser("~/Desktop/region.png")
    ps(f"""
        Add-Type -AssemblyName System.Windows.Forms;
        $b = [System.Drawing.Bitmap]::new({w}, {h});
        $g = [System.Drawing.Graphics]::FromImage($b);
        $g.CopyFromScreen({x}, {y}, 0, 0, $b.Size);
        $b.Save("{path}");
        $g.Dispose(); $b.Dispose();
        "{path}"
    """)
    return path


# ── UI Element Finder (simple) ────────────────────────────────────

def find_ui_element(window_title: str, automation_id: str = "") -> dict | None:
    """Find a UI element in a window by automation ID or class name."""
    raw = ps(f"""
        Add-Type -AssemblyName UIAutomationClient;
        $cond = New-Object System.Windows.Automation.Condition(1, 1);  # true condition
        $root = [System.Windows.Automation.AutomationElement]::RootElement;
        $wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond);

        $result = $null;
        foreach ($w in $wins) {{
            if ($w.Current.Name.ToLower().Contains('{window_title.lower()}')) {{
                $result = $w;
                break;
            }}
        }}
        if ($result -eq $null) {{ ""not found""; return }}

        $elems = $result.FindAll([System.Windows.Automation.TreeScope]::Subtree, $cond);
        $output = @();
        foreach ($e in $elems) {{
            $output += "$($e.Current.AutomationId)|$($e.Current.Name)|$($e.Current.ControlType.ProgrammaticName)|$($e.Current.BoundingRectangle.Left),$($e.Current.BoundingRectangle.Top),$($e.Current.BoundingRectangle.Width),$($e.Current.BoundingRectangle.Height)";
        }}
        $output -join ";;"
    """)
    if "not found" in raw:
        return None
    elements = []
    for line in (raw or "").split(";;"):
        parts = line.strip().split("|")
        if len(parts) >= 3:
            elements.append({
                "id": parts[0], "name": parts[1], "type": parts[2],
                "rect": parts[3] if len(parts) > 3 else "",
            })
    return {"window": window_title, "elements": elements[:50]} if elements else None
