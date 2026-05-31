"""Cross-app automation engine — PowerShell + browser actions for Windows."""

import subprocess
import re
import time

_ACTION_PATTERNS = {
    r"(?:play|start|launch|open)\s+(some\s+)?music": "music",
    r"(?:play|start|launch|open)\s+(some\s+)?(?:lofi|lo-fi|chill|study)\s*(?:music|beats)?": "music_lofi",
    r"(?:play|start|launch|open)\s+spotify": "spotify",
    r"(?:open|launch|start)\s+(?:the\s+)?(?:browser|chrome|firefox|edge)": "browser",
    r"(?:open|launch|start)\s+(?:the\s+)?(?:calculator|calc)": "calc",
    r"(?:open|launch|start)\s+(?:the\s+)?(?:notepad|text\s*editor)": "notepad",
    r"(?:search|google|look\s+up)\s+(.+?)(?:\s+for\s+me)?$": "search",
    r"(?:what|which)\s+(?:song|music|artist|track)\s+(?:is\s+)?(?:playing|on)": "current_song",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:email|gmail|outlook|mail)": "email",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:calendar|schedule)": "calendar",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:drive|google\s*drive|cloud)": "drive",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:youtube|yt)": "youtube",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:github|repos|code)": "github",
    r"(?:take|make|open)\s+(?:a\s+)?(?:note|notes|memo)": "notes",
    r"(?:lock|shut\s*down|turn\s*off)\s+(?:the\s+)?(?:computer|pc|laptop|system)": "lock",
    r"(?:empty|clear|clean)\s+(?:the\s+)?(?:trash|recycle\s*bin|bin)": "trash",
}

_ACTION_LABELS = {
    "music": "Opening music player...",
    "music_lofi": "Starting lo-fi beats...",
    "spotify": "Launching Spotify...",
    "browser": "Opening browser...",
    "calc": "Opening Calculator...",
    "notepad": "Opening Notepad...",
    "search": "Searching the web...",
    "current_song": "Checking what's playing...",
    "email": "Opening email...",
    "calendar": "Opening calendar...",
    "drive": "Opening Google Drive...",
    "youtube": "Opening YouTube...",
    "github": "Opening GitHub...",
    "notes": "Opening notes...",
    "lock": "Locking workstation...",
    "trash": "Emptying recycle bin...",
}


def detect_action(text: str) -> str | None:
    lower = text.lower().strip()
    for pat, action in _ACTION_PATTERNS.items():
        if re.search(pat, lower):
            return action
    return None


def execute_action(action: str, user_text: str = "") -> str:
    try:
        return _EXECUTORS.get(action, lambda _: "unknown action")(user_text)
    except Exception as e:
        return f"Failed: {e}"


def _ps(cmd: str) -> str:
    r = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=15)
    return r.stdout.strip() or r.stderr.strip()


def _music(_):
    _ps('Start-Process "spotify:" 2>$null; if (-not $?) { Start-Process "https://music.youtube.com" }')
    return "Opened Spotify or YouTube Music in browser."


def _music_lofi(_):
    _ps('Start-Process "https://www.youtube.com/results?search_query=lofi+study+beats"')
    return "Opening lo-fi study beats on YouTube..."


def _spotify(_):
    _ps('Start-Process "spotify:" 2>$null; if (-not $?) { Start-Process "https://open.spotify.com" }')
    return "Launching Spotify..."


def _browser(_):
    _ps('Start-Process "https://google.com"')
    return "Browser opening..."


def _calc(_):
    _ps('Start-Process "calc.exe"')
    return "Calculator opened."


def _notepad(_):
    _ps('Start-Process "notepad.exe"')
    return "Notepad opened."


def _search(text: str):
    m = re.search(r"(?:search|google|look\s+up)\s+(.+?)(?:\s+for\s+me)?$", text, re.IGNORECASE)
    query = m.group(1).strip() if m else text
    _ps(f'Start-Process "https://google.com/search?q={__import__("urllib").parse.quote(query)}"')
    return f'Searching for "{query}"...'


def _email(_):
    _ps('Start-Process "https://mail.google.com"')
    return "Opening Gmail..."


def _calendar(_):
    _ps('Start-Process "https://calendar.google.com"')
    return "Opening Google Calendar..."


def _drive(_):
    _ps('Start-Process "https://drive.google.com"')
    return "Opening Google Drive..."


def _youtube(_):
    _ps('Start-Process "https://youtube.com"')
    return "Opening YouTube..."


def _github(_):
    _ps('Start-Process "https://github.com"')
    return "Opening GitHub..."


def _notes(_):
    _ps('Start-Process "notepad.exe"')
    return "Notepad opened for notes."


def _lock(_):
    _ps('(rundll32.exe user32.dll,LockWorkStation) 2>$null')
    return "Locking workstation..."


def _trash(_):
    _ps('(New-Object -ComObject Shell.Application).Namespace(0x0a).Items() | ForEach-Object { $_.InvokeVerb("delete") }')
    return "Emptying recycle bin..."


def _current_song(_):
    try:
        r = _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("^{{F13}}") 2>$null; "sent"')
        return "Sent media key to check current song."
    except:
        return "Could not detect current song."


_EXECUTORS = {
    "music": _music,
    "music_lofi": _music_lofi,
    "spotify": _spotify,
    "browser": _browser,
    "calc": _calc,
    "notepad": _notepad,
    "search": _search,
    "current_song": _current_song,
    "email": _email,
    "calendar": _calendar,
    "drive": _drive,
    "youtube": _youtube,
    "github": _github,
    "notes": _notes,
    "lock": _lock,
    "trash": _trash,
}
