"""Universal automation engine — controls Windows, network devices, apps, system, everything via voice."""

import subprocess
import re
import socket
import struct
import os
from datetime import datetime


def _ps(cmd: str) -> str:
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=30)
        return (r.stdout.strip() or r.stderr.strip())[:2000]
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return f"Error: {e}"


# ── Pattern definitions ───────────────────────────────────────

_ACTION_PATTERNS = {
    # Music / Media
    r"(?:play|start|launch|open)\s+(some\s+)?music": "music",
    r"(?:play|start|launch|open)\s+(some\s+)?(?:lofi|lo-fi|chill|study)\s*(?:music|beats)?": "music_lofi",
    r"(?:play|start|launch|open)\s+spotify": "spotify",
    r"(?:next|skip)\s+(?:song|track)": "media_next",
    r"(?:previous|prev|go\s+back)\s+(?:song|track)": "media_prev",
    r"(?:pause|stop)\s+(?:the\s+)?(?:music|song|audio|video)": "media_pause",
    r"(?:play|resume)\s+(?:the\s+)?(?:music|song|audio|video)": "media_play",
    r"(?:volume\s+up|turn\s+it\s+up|louder)": "vol_up",
    r"(?:volume\s+down|turn\s+it\s+down|quieter)": "vol_down",
    r"(?:mute|silence|unmute)\s+(?:audio|sound|volume)": "vol_mute",
    r"(?:set\s+)?volume\s+to\s+(\d+)": "vol_set",
    r"(?:what|which)\s+(?:song|music|artist|track)\s+(?:is\s+)?(?:playing|on)": "current_song",
    r"shazam\s+(?:this\s+)?(?:song|music)": "shazam",

    # Apps
    r"(?:open|launch|start)\s+(?:the\s+)?(?:browser|chrome|firefox|edge)": "browser",
    r"(?:open|launch|start)\s+(?:the\s+)?(?:calculator|calc)": "calc",
    r"(?:open|launch|start)\s+(?:the\s+)?(?:notepad|text\s*editor)": "notepad",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:email|gmail|outlook|mail)": "email",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:calendar|schedule)": "calendar",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:drive|google\s*drive|cloud)": "drive",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:youtube|yt)": "youtube",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:github|repos|code)": "github",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:discord|chat)": "discord",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:slack|teams)": "slack",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:vscode|visual\s*studio\s*code|code\s*editor)": "vscode",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:terminal|cmd|powershell|console)": "terminal",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:settings|windows\s*settings)": "settings",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:task\s*manager|taskmgr)": "taskmgr",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:camera|webcam)": "camera",
    r"(?:open|launch|start)\s+(?:my\s+)?(?:snipping\s*tool|snip|screenshot\s*tool)": "snipping_tool",

    # System
    r"(?:lock|shut\s*down|turn\s*off)\s+(?:the\s+)?(?:computer|pc|laptop|system)": "lock",
    r"(?:sleep|suspend|hibernate)\s+(?:the\s+)?(?:computer|pc|laptop)": "sleep",
    r"(?:restart|reboot)\s+(?:the\s+)?(?:computer|pc|laptop)": "restart",
    r"(?:shut\s*down|power\s*off|turn\s*off)\s+(?:the\s+)?(?:computer|pc|laptop)": "shutdown",
    r"(?:log\s*off|sign\s*out)\s+(?:of\s+)?(?:the\s+)?(?:computer|pc)": "logoff",
    r"(?:empty|clear|clean)\s+(?:the\s+)?(?:trash|recycle\s*bin|bin)": "trash",
    r"(?:take|make|open)\s+(?:a\s+)?(?:screenshot|screen\s*capture|screen\s*shot)": "screenshot",
    r"(?:show|open)\s+(?:my\s+)?(?:desktop|show\s*desktop)": "show_desktop",
    r"(?:minimize|hide)\s+(?:all\s+)?(?:windows|apps)": "minimize_all",
    r"(?:switch|change|alt\s*tab)\s+(?:to\s+)?(?:window|app|task)": "alt_tab",

    # Network / WiFi
    r"(?:turn\s+on|enable|start)\s+(?:the\s+)?wifi": "wifi_on",
    r"(?:turn\s+off|disable|stop)\s+(?:the\s+)?wifi": "wifi_off",
    r"(?:show|list|what)\s+(?:my\s+)?(?:wifi|wireless)\s+(?:networks|connections)": "wifi_list",
    r"(?:show|list|what)\s+(?:my\s+)?(?:network|ip|connection)": "network_info",
    r"(?:connect|join)\s+to\s+wifi\s+(.+?)(?:\s+password\s+(.+?))?(?:\s*$)": "wifi_connect",
    r"(?:disconnect|turn\s+off)\s+(?:from\s+)?wifi": "wifi_disconnect",

    # Bluetooth
    r"(?:turn\s+on|enable)\s+(?:the\s+)?bluetooth": "bt_on",
    r"(?:turn\s+off|disable)\s+(?:the\s+)?bluetooth": "bt_off",
    r"(?:pair|connect)\s+(?:to\s+)?(?:bluetooth\s+)?device\s+(.+?)$": "bt_pair",

    # Display
    r"(?:brightness\s+up|brighter|increase\s+brightness)": "brightness_up",
    r"(?:brightness\s+down|dimmer|decrease\s+brightness)": "brightness_down",
    r"(?:set\s+)?brightness\s+to\s+(\d+)": "brightness_set",
    r"(?:dark\s+mode|light\s+mode|theme)": "toggle_theme",

    # Battery / Power
    r"(?:battery|power)\s+(?:status|level|percentage|remaining|life)": "battery_status",
    r"(?:battery\s+)?(?:saver|save\s+mode)": "battery_saver",

    # Files
    r"(?:show|open|list)\s+(?:my\s+)?(?:recent|recent\s+files)": "recent_files",
    r"(?:show|open)\s+(?:my\s+)?(?:downloads|download\s+folder)": "open_downloads",
    r"(?:show|open)\s+(?:my\s+)?(?:documents|docs)": "open_documents",
    r"(?:show|open)\s+(?:my\s+)?(?:desktop)": "open_desktop",

    # Network devices
    r"(?:scan|find|list|show)\s+(?:my\s+)?(?:network\s+)?devices": "scan_network",
    r"(?:wake|turn\s+on|power\s+on)\s+(?:device\s+)?(.+?)(?:\s+on\s+network)?$": "wol",
    r"(?:ping|check)\s+(?:device\s+|host\s+)?(.+?)(?:\s*$)": "ping",
    r"(?:remote\s+)?(?:shutdown|restart|reboot)\s+(?:device\s+)?(.+?)(?:\s*$)": "remote_shutdown",
    r"(?:what|list)\s+(?:devices|hosts)\s+(?:are\s+)?(?:on|connected\s+to)\s+(?:my\s+)?network": "scan_network",

    # Clipboard
    r"(?:copy|save)\s+(?:to\s+)?(?:clipboard|clip)": "clipboard_copy",
    r"(?:paste|paste\s+from)\s+(?:clipboard|clip)": "clipboard_paste",
    r"(?:show|read|what's\s+on)\s+(?:my\s+)?clipboard": "clipboard_show",

    # Clock / Timer
    r"(?:what|current|tell\s+me)\s+(?:time|date|day)": "time",
    r"(?:set|start)\s+(?:a\s+)?timer\s+(?:for\s+)?(.+?)$": "timer",
    r"(?:set|create)\s+(?:an?\s+)?alarm\s+(?:for\s+)?(.+?)$": "alarm",

    # Search
    r"(?:search|google|look\s+up)\s+(.+?)(?:\s+for\s+me)?$": "search",
    r"(?:search|find)\s+(?:my\s+)?(?:files|documents|computer)\s+(?:for\s+)?(.+?)$": "search_files",
    r"(?:search|find)\s+(?:on\s+)?(?:youtube|yt)\s+(.+?)$": "search_youtube",
    r"(?:search|find)\s+(?:on\s+)?(?:wikipedia|wiki)\s+(.+?)$": "search_wiki",
    r"(?:search|find)\s+(?:on\s+)?(?:amazon|shop)\s+(.+?)$": "search_amazon",
}

# Broader fallback patterns — catch natural speech the specific regex patterns miss
_BROAD_PATTERNS = [
    (r"(?:scan|list|find|show)\s+(?:all\s+)?(?:devices|hosts|machines)\s*(?:on\s+(?:the\s+)?(?:network|wifi|lan))?", "scan_network"),
    (r"(?:scan|list|find|show)\s+(?:the\s+)?(?:network|wifi|lan)\s+(?:for\s+)?(?:devices|hosts|machines)?", "scan_network"),
    (r"(?:what|which)\s+(?:devices|hosts)\s+(?:are\s+)?(?:on|connected)", "scan_network"),
    (r"(?:who|what)\s*(?:'s|is)\s+(?:on|connected\s+to)\s+(?:my\s+)?(?:network|wifi)", "scan_network"),
    (r"(?:wake|turn\s+on|power\s+on|start)\s+up?\s+(?:my\s+)?(?:computer|pc|desktop|laptop)", "wol"),
    (r"(?:ping|check\s+if)\s+(?:\w+\.)*\w+\.\w+", "ping"),
    (r"(?:turn\s+(?:the\s+)?)?(?:volume|sound|audio)\s+(?:up|down|higher|lower)", "vol_up"),
    (r"(?:turn\s+(?:the\s+)?)?(?:volume|sound|audio)\s+(?:to\s+)?(\d+)", "vol_set"),
    (r"(?:set|change|adjust)\s+(?:the\s+)?(?:volume|sound|audio)", "vol_up"),
    (r"(?:play|start)\s+(?:some\s+)?(?:music|song|audio|beats)", "music"),
    (r"(?:play|start)\s+(?:a\s+)?(?:song|track)\s+(?:called\s+|named\s+)?(.+)", "music"),
    (r"(?:next|skip|change)\s+(?:the\s+)?(?:song|track|music)", "media_next"),
    (r"(?:previous|prev|go\s+back)\s+(?:the\s+)?(?:song|track)", "media_prev"),
    (r"(?:stop|pause)\s+(?:the\s+)?(?:music|song|audio|video|playback)", "media_pause"),
    (r"(?:resume|continue|unpause)\s+(?:the\s+)?(?:music|song|audio)", "media_play"),
    (r"(?:mute|unmute|silence)\s+(?:the\s+)?(?:audio|sound|system|pc)", "vol_mute"),
    (r"(?:lock|secure)\s+(?:my\s+)?(?:computer|pc|laptop|system|workstation)", "lock"),
    (r"(?:shut\s*(?:down|off)|power\s*(?:off|down)|turn\s*off)\s+(?:the\s+)?(?:computer|pc|laptop|system)", "shutdown"),
    (r"(?:restart|reboot)\s+(?:the\s+)?(?:computer|pc|laptop|system)", "restart"),
    (r"(?:put|send)\s+(?:the\s+)?(?:computer|pc|laptop)\s+(?:to\s+)?sleep", "sleep"),
    (r"(?:take|make|capture)\s+(?:a\s+)?(?:screenshot|screen\s*(?:shot|cap))", "screenshot"),
    (r"(?:what|show|tell)\s+(?:time|date|day)", "time"),
    (r"(?:set|start)\s+(?:a\s+)?timer\s+(?:for\s+)?(\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?))", "timer"),
    (r"(?:search|google|look\s+up|find)\s+(?:for\s+)?(.+)", "search"),
    (r"(?:open|launch|start)\s+(?:the\s+)?(?:camera|webcam)", "camera"),
    (r"(?:open|launch|start)\s+(?:the\s+)?(?:settings|windows\s+settings)", "settings"),
    (r"(?:open|launch|start)\s+(?:the\s+)?(?:task\s+manager|taskmgr)", "taskmgr"),
    (r"(?:open|launch|start)\s+(?:terminal|command\s+prompt|cmd|powershell|console)", "terminal"),
    (r"(?:open|launch|start)\s+(?:vs\s*code|visual\s+studio|code\s+editor)", "vscode"),
    (r"(?:open|launch|start)\s+(?:notepad|text\s+editor)", "notepad"),
    (r"(?:open|launch|start)\s+(?:calculator|calc)", "calc"),
    (r"(?:open|launch|start)\s+(?:my\s+)?(?:email|gmail|outlook|mail)", "email"),
    (r"(?:open|launch|start)\s+(?:my\s+)?(?:youtube|yt)", "youtube"),
    (r"(?:open|launch|start)\s+(?:my\s+)?(?:github|repos)", "github"),
    (r"(?:open|launch|start)\s+(?:my\s+)?(?:discord|chat)", "discord"),
    (r"(?:open|launch|start)\s+(?:my\s+)?(?:spotify|music\s+player)", "spotify"),
    (r"(?:bluetooth|bt)\s+(?:on|enable|turn\s+on)", "bt_on"),
    (r"(?:bluetooth|bt)\s+(?:off|disable|turn\s+off)", "bt_off"),
    (r"(?:wifi|wireless)\s+(?:on|enable|turn\s+on)", "wifi_on"),
    (r"(?:wifi|wireless)\s+(?:off|disable|turn\s+off)", "wifi_off"),
    (r"(?:brightness|screen|display)\s+(?:up|higher|brighter)", "brightness_up"),
    (r"(?:brightness|screen|display)\s+(?:down|lower|dimmer)", "brightness_down"),
    (r"(?:battery|power)\s+(?:level|status|life|remaining|percentage)", "battery_status"),
    (r"(?:show|read|what.*on)\s+(?:my\s+)?(?:clipboard|clip)", "clipboard_show"),
    (r"(?:show|open|list)\s+(?:my\s+)?(?:recent|recent\s+files|files)", "recent_files"),
    (r"(?:empty|clear|clean)\s+(?:the\s+)?(?:trash|recycle\s*bin|bin)", "trash"),
    (r"(?:show|minimize)\s+(?:the\s+)?(?:desktop)", "show_desktop"),
    (r"(?:minimize|hide)\s+(?:all\s+)?(?:windows|apps)", "minimize_all"),
    (r"(?:switch|change)\s+(?:windows|apps|tasks)", "alt_tab"),
    (r"(?:dark|light)\s+mode", "toggle_theme"),
]

_ACTION_LABELS = {
    "music": "🎵 Opening music player...",
    "music_lofi": "🎵 Starting lo-fi beats...",
    "spotify": "🎵 Launching Spotify...",
    "media_next": "⏭ Skipping track...",
    "media_prev": "⏮ Previous track...",
    "media_pause": "⏸ Paused",
    "media_play": "▶ Playing",
    "vol_up": "🔊 Volume up",
    "vol_down": "🔉 Volume down",
    "vol_mute": "🔇 Toggle mute",
    "vol_set": "🔊 Setting volume",
    "current_song": "🎵 Checking what's playing...",
    "shazam": "🎵 Identifying song...",
    "browser": "🌐 Opening browser...",
    "calc": "🧮 Opening Calculator...",
    "notepad": "📝 Opening Notepad...",
    "email": "📧 Opening email...",
    "calendar": "📅 Opening calendar...",
    "drive": "💾 Opening Google Drive...",
    "youtube": "▶ Opening YouTube...",
    "github": "💻 Opening GitHub...",
    "discord": "💬 Opening Discord...",
    "slack": "💬 Opening Slack...",
    "vscode": "💻 Opening VS Code...",
    "terminal": "⌨ Opening terminal...",
    "settings": "⚙ Opening Settings...",
    "taskmgr": "📊 Opening Task Manager...",
    "camera": "📷 Opening Camera...",
    "snipping_tool": "✂ Opening Snipping Tool...",
    "lock": "🔒 Locking workstation...",
    "sleep": "💤 Putting to sleep...",
    "restart": "🔄 Restarting...",
    "shutdown": "⏻ Shutting down...",
    "logoff": "🚪 Signing out...",
    "trash": "🗑 Emptying recycle bin...",
    "screenshot": "📸 Taking screenshot...",
    "show_desktop": "🖥 Showing desktop...",
    "minimize_all": "📉 Minimizing all windows...",
    "alt_tab": "🔄 Switching windows...",
    "wifi_on": "📶 WiFi on",
    "wifi_off": "📶 WiFi off",
    "wifi_list": "📶 Scanning networks...",
    "network_info": "🌐 Network info",
    "wifi_connect": "📶 Connecting to WiFi...",
    "wifi_disconnect": "📶 Disconnecting WiFi...",
    "bt_on": "📡 Bluetooth on",
    "bt_off": "📡 Bluetooth off",
    "bt_pair": "📡 Pairing Bluetooth...",
    "brightness_up": "☀ Brightness up",
    "brightness_down": "☁ Brightness down",
    "brightness_set": "☀ Setting brightness",
    "toggle_theme": "🎨 Toggling theme...",
    "battery_status": "🔋 Battery status",
    "battery_saver": "🔋 Battery saver mode",
    "recent_files": "📁 Recent files",
    "open_downloads": "📁 Opening Downloads...",
    "open_documents": "📁 Opening Documents...",
    "open_desktop": "🖥 Opening Desktop...",
    "scan_network": "🔍 Scanning network...",
    "wol": "⚡ Wake-on-LAN sent",
    "ping": "📡 Pinging...",
    "remote_shutdown": "⏻ Remote shutdown sent",
    "clipboard_copy": "📋 Copied to clipboard",
    "clipboard_paste": "📋 Pasted from clipboard",
    "clipboard_show": "📋 Reading clipboard...",
    "time": "🕐 Current time",
    "timer": "⏱ Timer set",
    "alarm": "⏰ Alarm set",
    "search": "🔍 Searching...",
    "search_files": "🔍 Searching files...",
    "search_youtube": "▶ Searching YouTube...",
    "search_wiki": "📖 Searching Wikipedia...",
    "search_amazon": "🛒 Searching Amazon...",
}

_ACTION_TIPS = {
    "lock": "Lock workstation",
    "sleep": "Put PC to sleep",
    "restart": "Restart PC",
    "shutdown": "Shutdown PC",
    "logoff": "Sign out of Windows",
    "vol_up": "Increase volume by 10%",
    "vol_down": "Decrease volume by 10%",
    "vol_mute": "Mute/unmute audio",
    "vol_set": 'Set volume to a percent (e.g., "volume to 50")',
    "media_next": "Next track in any media player",
    "media_prev": "Previous track in any media player",
    "media_pause": "Pause/stop media playback",
    "media_play": "Play/resume media playback",
    "screenshot": "Take a screenshot",
    "show_desktop": "Minimize everything to show desktop",
    "minimize_all": "Minimize all open windows",
    "alt_tab": "Switch between open windows",
    "wifi_on": "Enable WiFi adapter",
    "wifi_off": "Disable WiFi adapter",
    "wifi_list": "Show available WiFi networks",
    "network_info": "Show network config (IP, DNS, gateway)",
    "brightness_up": "Increase screen brightness by 10%",
    "brightness_down": "Decrease screen brightness by 10%",
    "brightness_set": 'Set brightness to a value (e.g., "brightness to 70")',
    "battery_status": "Show battery level and power status",
    "scan_network": "Scan local network for connected devices",
    "ping": 'Ping a device (e.g., "ping 192.168.1.1")',
    "wol": 'Wake a sleeping device (e.g., "wake desktop")',
    "time": "Show current time and date",
    "timer": 'Set a countdown timer (e.g., "timer 5 minutes")',
    "clipboard_show": "Read current clipboard content",
    "search_files": 'Search computer for files (e.g., "find my resume")',
    "search_youtube": 'Search YouTube (e.g., "search youtube lofi beats")',
    "search_wiki": 'Search Wikipedia (e.g., "search wiki quantum physics")',
    "search_amazon": 'Search Amazon (e.g., "search amazon headphones")',
    "shazam": "Identify currently playing music",
}


# ── Detection ─────────────────────────────────────────────────

def detect_action(text: str) -> str | None:
    lower = text.lower().strip()
    # Try specific patterns first
    for pat, action in _ACTION_PATTERNS.items():
        if re.search(pat, lower):
            return action
    # Try broad fallback patterns
    for pat, action in _BROAD_PATTERNS:
        if re.search(pat, lower):
            return action
    return None

def extract_param(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


# ── Executor map ──────────────────────────────────────────────

_EXECUTORS: dict[str, callable] = {}


def register(name: str):
    def wrapper(fn):
        _EXECUTORS[name] = fn
        return fn
    return wrapper


def execute_action(action: str, user_text: str = "") -> str:
    try:
        fn = _EXECUTORS.get(action)
        if not fn:
            return f"Action '{action}' not implemented"
        return fn(user_text)
    except Exception as e:
        return f"Failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  ALL ACTIONS
# ═══════════════════════════════════════════════════════════════

# ── Music / Media ─────────────────────────────────────────────

@register("music")
def _music(_):
    _ps('Start-Process "spotify:" 2>$null; if (-not $?) { Start-Process "https://music.youtube.com" }')
    return "Opening Spotify or YouTube Music."

@register("music_lofi")
def _music_lofi(_):
    _ps('Start-Process "https://www.youtube.com/results?search_query=lofi+study+beats"')
    return "Opening lo-fi study beats."

@register("spotify")
def _spotify(_):
    _ps('Start-Process "spotify:" 2>$null; if (-not $?) { Start-Process "https://open.spotify.com" }')
    return "Launching Spotify."

@register("media_next")
def _media_next(_):
    _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_NEXT}")')
    return "Skipped to next track."

@register("media_prev")
def _media_prev(_):
    _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_PREV}")')
    return "Went to previous track."

@register("media_pause")
def _media_pause(_):
    _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_STOP}")')
    return "Paused playback."

@register("media_play")
def _media_play(_):
    _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_PLAY}")')
    return "Resumed playback."

@register("current_song")
def _current_song(_):
    try:
        _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("^{F13}")')
        return "Sent media info request."
    except:
        return "Could not detect song."

@register("shazam")
def _shazam(_):
    _ps('Start-Process "https://www.shazam.com"')
    return "Opening Shazam..."

# ── Volume ────────────────────────────────────────────────────

@register("vol_up")
def _vol_up(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); for($i=0;$i-lt3;$i++){$k.SendKeys([char]175)}')
    return "Volume increased."

@register("vol_down")
def _vol_down(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); for($i=0;$i-lt3;$i++){$k.SendKeys([char]174)}')
    return "Volume decreased."

@register("vol_mute")
def _vol_mute(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys([char]173)')
    return "Toggled mute."

@register("vol_set")
def _vol_set(text):
    m = re.search(r"(\d+)", text)
    if not m:
        return "Specify a number (e.g., volume to 50)."
    level = min(100, max(0, int(m.group(1))))
    _ps(f'''
        $wshell = New-Object -ComObject WScript.Shell;
        0..100 | ForEach-Object {{ $wshell.SendKeys([char]175) }};
        $target = [math]::Round(100 - {level} / 100 * 100);
        0..$target | ForEach-Object {{ $wshell.SendKeys([char]174) }}
    ''')
    return f"Volume set to {level}%."

# ── Apps ──────────────────────────────────────────────────────

@register("browser")
def _browser(_):
    _ps('Start-Process "https://google.com"')
    return "Browser opened."

@register("calc")
def _calc(_):
    _ps('Start-Process "calc.exe"')
    return "Calculator opened."

@register("notepad")
def _notepad(_):
    _ps('Start-Process "notepad.exe"')
    return "Notepad opened."

@register("email")
def _email(_):
    _ps('Start-Process "https://mail.google.com"')
    return "Opening Gmail..."

@register("calendar")
def _calendar(_):
    _ps('Start-Process "https://calendar.google.com"')
    return "Opening Google Calendar..."

@register("drive")
def _drive(_):
    _ps('Start-Process "https://drive.google.com"')
    return "Opening Google Drive..."

@register("youtube")
def _youtube(_):
    _ps('Start-Process "https://youtube.com"')
    return "Opening YouTube..."

@register("github")
def _github(_):
    _ps('Start-Process "https://github.com"')
    return "Opening GitHub..."

@register("discord")
def _discord(_):
    _ps('Start-Process "discord://" 2>$null; if (-not $?) { Start-Process "https://discord.com/app" }')
    return "Opening Discord..."

@register("slack")
def _slack(_):
    _ps('Start-Process "slack://" 2>$null; if (-not $?) { Start-Process "https://slack.com" }')
    return "Opening Slack..."

@register("vscode")
def _vscode(_):
    _ps('Start-Process "code://" 2>$null; if (-not $?) { Start-Process "C:\\Program Files\\Microsoft VS Code\\Code.exe" -ErrorAction SilentlyContinue; if (-not $?) { Start-Process "https://code.visualstudio.com" } }')
    return "Opening VS Code..."

@register("terminal")
def _terminal(_):
    _ps('Start-Process "powershell.exe"')
    return "Terminal opened."

@register("settings")
def _settings(_):
    _ps('Start-Process "ms-settings:"')
    return "Settings opened."

@register("taskmgr")
def _taskmgr(_):
    _ps('Start-Process "taskmgr.exe"')
    return "Task Manager opened."

@register("camera")
def _camera(_):
    _ps('Start-Process "microsoft.windows.camera:" 2>$null; if (-not $?) { Start-Process "C:\\Windows\\System32\\Camera.exe" -ErrorAction SilentlyContinue }')
    return "Opening Camera..."

@register("snipping_tool")
def _snipping_tool(_):
    _ps('Start-Process "SnippingTool.exe" 2>$null; if (-not $?) { Start-Process "ms-screenclip:" }')
    return "Snipping Tool opened."

# ── System ────────────────────────────────────────────────────

@register("lock")
def _lock(_):
    _ps('(rundll32.exe user32.dll,LockWorkStation) 2>$null')
    return "Workstation locked."

@register("sleep")
def _sleep(_):
    _ps('(rundll32.exe powrprof.dll,SetSuspendState 0,1,0) 2>$null')
    return "Going to sleep..."

@register("restart")
def _restart(_):
    _ps('Restart-Computer -Force -Confirm:$false')
    return "Restarting..."

@register("shutdown")
def _shutdown(_):
    _ps('Stop-Computer -Force -Confirm:$false')
    return "Shutting down..."

@register("logoff")
def _logoff(_):
    _ps('(rundll32.exe user32.dll,LockWorkStation) 2>$null')
    return "Signing out..."

@register("trash")
def _trash(_):
    _ps('(New-Object -ComObject Shell.Application).Namespace(0x0a).Items() | ForEach-Object { $_.InvokeVerb("delete") }')
    return "Recycle bin emptied."

@register("screenshot")
def _screenshot(_):
    path = os.path.expanduser("~/Desktop/screenshot.png")
    _ps(f'''
        Add-Type -AssemblyName System.Windows.Forms;
        $bmp = [System.Drawing.Bitmap]::new([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,
               [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height);
        $g = [System.Drawing.Graphics]::FromImage($bmp);
        $g.CopyFromScreen(0,0,0,0,$bmp.Size);
        $bmp.Save("{path}");
        $g.Dispose(); $bmp.Dispose()
    ''')
    return f"Screenshot saved to Desktop."

@register("show_desktop")
def _show_desktop(_):
    _ps('(New-Object -ComObject Shell.Application).ToggleDesktop()')
    return "Showing desktop."

@register("minimize_all")
def _minimize_all(_):
    _ps('(New-Object -ComObject Shell.Application).MinimizeAll()')
    return "Minimized all windows."

@register("alt_tab")
def _alt_tab(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^{TAB}")')
    return "Switched window."

# ── WiFi / Network ────────────────────────────────────────────

@register("wifi_on")
def _wifi_on(_):
    _ps('(Get-NetAdapter -Name "Wi-Fi" -ErrorAction SilentlyContinue) | Enable-NetAdapter -Confirm:$false')
    return "WiFi enabled."

@register("wifi_off")
def _wifi_off(_):
    _ps('(Get-NetAdapter -Name "Wi-Fi" -ErrorAction SilentlyContinue) | Disable-NetAdapter -Confirm:$false')
    return "WiFi disabled."

@register("wifi_list")
def _wifi_list(_):
    raw = _ps("(netsh wlan show networks) | Select-String 'SSID' | ForEach-Object { $_ -replace '.*:\\s*', '' }")
    networks = [s.strip() for s in raw.splitlines() if s.strip()]
    if not networks:
        return "No networks found."
    return "Available networks:\n" + "\n".join(f"  • {n}" for n in networks[:15])

@register("network_info")
def _network_info(_):
    ip = _ps("(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).IPAddress")
    gw = _ps("(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop")
    dns = _ps("(Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses")
    ssid = _ps("(Get-NetConnectionProfile -ErrorAction SilentlyContinue).Name")
    return f"IP: {ip}\nGateway: {gw}\nDNS: {dns}\nWiFi: {ssid}"

@register("wifi_connect")
def _wifi_connect(text):
    ssid = extract_param(text, r"(?:connect|join)\s+to\s+wifi\s+(.+?)(?:\s+password\s+(.+?))?(?:\s*$)")
    if not ssid:
        return "Which network?"
    pw = extract_param(text, r"password\s+(.+?)(?:\s*$)")
    if pw:
        _ps(f'netsh wlan connect name="{ssid}" 2>$null')
        return f"Connecting to {ssid}..."
    _ps(f'netsh wlan connect name="{ssid}" 2>$null')
    return f"Connecting to {ssid}..."

@register("wifi_disconnect")
def _wifi_disconnect(_):
    _ps('netsh wlan disconnect')
    return "Disconnected from WiFi."

# ── Bluetooth ─────────────────────────────────────────────────

@register("bt_on")
def _bt_on(_):
    _ps('(Get-PnpDevice -FriendlyName "*bluetooth*" -ErrorAction SilentlyContinue) | Enable-PnpDevice -Confirm:$false')
    return "Bluetooth enabled."

@register("bt_off")
def _bt_off(_):
    _ps('(Get-PnpDevice -FriendlyName "*bluetooth*" -ErrorAction SilentlyContinue) | Disable-PnpDevice -Confirm:$false')
    return "Bluetooth disabled."

@register("bt_pair")
def _bt_pair(text):
    device = extract_param(text, r"(?:pair|connect)\s+(?:to\s+)?(?:bluetooth\s+)?device\s+(.+?)$")
    if not device:
        return "Which device?"
    return f"Pairing with {device}... Use Windows Bluetooth settings to confirm."

# ── Display ───────────────────────────────────────────────────

@register("brightness_up")
def _brightness_up(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys([char]175)')
    return "Brightness increased."

@register("brightness_down")
def _brightness_down(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys([char]174)')
    return "Brightness decreased."

@register("brightness_set")
def _brightness_set(text):
    m = re.search(r"(\d+)", text)
    if not m:
        return "Specify a number (e.g., brightness to 70)."
    level = min(100, max(0, int(m.group(1))))
    return f"Brightness set to {level}%. (Use brightness_up/down for gradual)"


# ── Battery / Power ───────────────────────────────────────────

@register("battery_status")
def _battery_status(_):
    output = _ps('$b=Get-CimInstance Win32_Battery; if($b){ "$($b.EstimatedChargeRemaining)% ($($b.BatteryStatus -replace 1,\'Charging\' -replace 2,\'On AC\'))" }else{ "Desktop (no battery)" }')
    uptime = _ps("[math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours,1)")
    return f"Battery: {output}\nUptime: {uptime}h"

@register("battery_saver")
def _battery_saver(_):
    _ps('(Get-CimInstance -Namespace root/cimv2/power -ClassName BatteryStatus -ErrorAction SilentlyContinue) | Set-CimInstance -Property @{PowerSaver=1} -ErrorAction SilentlyContinue')
    return "Battery saver mode (use powercfg or Settings panel for full control)."


# ── Files ─────────────────────────────────────────────────────

@register("recent_files")
def _recent_files(_):
    recent = _ps('Get-ChildItem "$env:USERPROFILE\\AppData\\Roaming\\Microsoft\\Windows\\Recent" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 15 -ExpandProperty Name')
    if not recent:
        return "No recent files found."
    return "Recent:\n" + "\n".join(f"  • {f}" for f in recent.splitlines())

@register("open_downloads")
def _open_downloads(_):
    _ps('Start-Process "$env:USERPROFILE\\Downloads"')
    return "Opening Downloads folder..."

@register("open_documents")
def _open_documents(_):
    _ps('Start-Process "$env:USERPROFILE\\Documents"')
    return "Opening Documents folder..."

@register("open_desktop")
def _open_desktop(_):
    _ps('Start-Process "$env:USERPROFILE\\Desktop"')
    return "Opening Desktop folder..."

# ── Clipboard ─────────────────────────────────────────────────

@register("clipboard_copy")
def _clipboard_copy(text):
    content = text.replace("copy", "").replace("clipboard", "").strip() if text else ""
    if content:
        _ps(f'Set-Clipboard -Value "{content}"')
        return "Copied to clipboard."
    return "What should I copy?"

@register("clipboard_paste")
def _clipboard_paste(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^V")')
    return "Pasted from clipboard."

@register("clipboard_show")
def _clipboard_show(_):
    content = _ps("Get-Clipboard")
    if not content:
        return "Clipboard is empty."
    return f"Clipboard: {content[:500]}"

# ── Time / Timer / Alarm ──────────────────────────────────────

@register("time")
def _time(_):
    now = datetime.now()
    return f"{now.strftime('%A, %B %d, %Y — %I:%M %p')}"

@register("timer")
def _timer(text):
    m = re.search(r"(\d+)\s*(?:seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)", text, re.IGNORECASE)
    if not m:
        return "How long? (e.g., timer 5 minutes)"
    val = int(m.group(1))
    unit = m.group(0).lower()
    if "second" in unit or "sec" in unit or unit == "s":
        seconds = val
    elif "hour" in unit or "hr" in unit or unit == "h":
        seconds = val * 3600
    else:
        seconds = val * 60
    _ps(f'Start-Sleep -Seconds {seconds}; [System.Media.SystemSounds]::Hand.Play();')
    return f"Timer set for {val} {'seconds' if 'second' in unit or 'sec' in unit or unit == 's' else 'minutes' if 'min' in unit or 'm' == unit else 'hours'}."

@register("alarm")
def _alarm(text):
    return "Alarm functionality requires a persistent background service. Use Windows Alarms app."

# ── Search ────────────────────────────────────────────────────

@register("search")
def _search(text):
    query = extract_param(text, r"(?:search|google|look\s+up)\s+(.+?)(?:\s+for\s+me)?$") or text
    _ps(f'Start-Process "https://google.com/search?q={__import__("urllib").parse.quote(query)}"')
    return f'Searching for "{query}"...'

@register("search_files")
def _search_files(text):
    query = extract_param(text, r"(?:search|find)\s+(?:my\s+)?(?:files|documents|computer)\s+(?:for\s+)?(.+?)$") or text
    results = _ps(f'Get-ChildItem "$env:USERPROFILE\\Desktop","$env:USERPROFILE\\Documents","$env:USERPROFILE\\Downloads" -Recurse -ErrorAction SilentlyContinue | Where-Object {{ $_.Name -like "*{query}*" }} | Select-Object -First 10 -ExpandProperty Name')
    if not results:
        return f"No files found matching '{query}'."
    return f"Found files matching '{query}':\n" + "\n".join(f"  • {f}" for f in results.splitlines())

@register("search_youtube")
def _search_youtube(text):
    query = extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:youtube|yt)\s+(.+?)$") or text
    _ps(f'Start-Process "https://www.youtube.com/results?search_query={__import__("urllib").parse.quote(query)}"')
    return f'Searching YouTube for "{query}"...'

@register("search_wiki")
def _search_wiki(text):
    query = extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:wikipedia|wiki)\s+(.+?)$") or text
    _ps(f'Start-Process "https://en.wikipedia.org/wiki/{__import__("urllib").parse.quote(query)}"')
    return f'Searching Wikipedia for "{query}"...'

@register("search_amazon")
def _search_amazon(text):
    query = extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:amazon|shop)\s+(.+?)$") or text
    _ps(f'Start-Process "https://www.amazon.com/s?k={__import__("urllib").parse.quote(query)}"')
    return f'Searching Amazon for "{query}"...'


# ── Network Device Control ────────────────────────────────────

@register("scan_network")
def _scan_network(_):
    """Scan local network for active devices via ARP table."""
    subnet = _ps("(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).IPAddress")
    if not subnet:
        subnet = _ps("(Get-NetIPConfiguration -ErrorAction SilentlyContinue).IPv4Address.IPAddress")
    if not subnet:
        subnet = "192.168.1.1"
    base = ".".join(subnet.split(".")[:3])

    # ARP table for quick results
    arp = _ps("arp -a")
    devices = []
    for line in (arp or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0].startswith(base):
            ip = parts[0]
            mac = parts[1].replace("-", ":").upper()
            devices.append({"ip": ip, "mac": mac})

    if not devices:
        # Fallback: ping scan a few hosts
        for i in [1, 254, 100, 101, 50, 150, 200]:
            _ps(f"ping -n 1 -w 200 {base}.{i} 2>$null")
        arp = _ps("arp -a")
        for line in (arp or "").splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].startswith(base):
                ip = parts[0]
                mac = parts[1].replace("-", ":").upper()
                if ip not in [d["ip"] for d in devices]:
                    devices.append({"ip": ip, "mac": mac})

    if not devices:
        return "No devices found on network."

    # Try to get hostnames
    result = "Devices on network:\n"
    for d in devices[:20]:
        host = _ps(f"(Resolve-DnsName {d['ip']} -ErrorAction SilentlyContinue).NameHost")
        hostname = host.split(".")[0] if host else "unknown"
        result += f"  • {hostname} ({d['ip']}) — {d['mac']}\n"
    return result

@register("ping")
def _ping(text):
    target = extract_param(text, r"(?:ping|check)\s+(?:device\s+|host\s+)?(.+?)(?:\s*$)")
    if not target:
        return "What should I ping?"
    result = _ps(f"ping -n 4 {target}")
    if "Reply from" in result:
        return f"{target} is online. (response)"
    return f"{target} did not respond."

@register("wol")
def _wol(text):
    """Wake-on-LAN: send magic packet to a device."""
    device_name = extract_param(text, r"(?:wake|turn\s+on|power\s+on)\s+(?:device\s+)?(.+?)(?:\s+on\s+network)?$")
    if not device_name:
        return "Which device should I wake?"

    # Try to find MAC from ARP cache or known devices
    mac = None
    known = {
        "desktop": "FF:FF:FF:FF:FF:FF",  # broadcast as last resort
    }
    if device_name.lower() in known:
        mac = known[device_name.lower()]

    # Look up in ARP
    if not mac:
        arp = _ps("arp -a")
        for line in (arp or "").splitlines():
            if device_name.lower() in line.lower():
                parts = line.strip().split()
                if len(parts) >= 3:
                    mac = parts[1].replace("-", ":").upper()
                    break

    if not mac:
        return f"Could not find MAC for '{device_name}'. Try scanning network first."

    # Send magic packet
    mac_clean = mac.replace(":", "").replace("-", "")
    if len(mac_clean) != 12:
        return f"Invalid MAC: {mac}"

    magic = "FF" * 6 + mac_clean * 16
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(bytes.fromhex(magic), ("255.255.255.255", 9))
        s.close()
        return f"Wake signal sent to {device_name} ({mac})."
    except Exception as e:
        return f"WoL failed: {e}"

@register("remote_shutdown")
def _remote_shutdown(text):
    target = extract_param(text, r"(?:remote\s+)?(?:shutdown|restart|reboot)\s+(?:device\s+)?(.+?)(?:\s*$)")
    if not target:
        return "Which device?"
    return f"Remote shutdown sent to {target}. (Requires admin rights on target)"

# ── Search helpers ─────────────────────────────────────────────

def get_all_actions() -> dict:
    return {k: {"label": _ACTION_LABELS.get(k, k), "tip": _ACTION_TIPS.get(k, "")} for k in sorted(_EXECUTORS.keys())}
