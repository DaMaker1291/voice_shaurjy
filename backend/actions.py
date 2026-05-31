"""Universal automation engine — controls anything & everything on Windows via voice."""

import re, os, socket, struct, threading, time, json
from datetime import datetime
from ps_executor import ps as _ps_fast, ps_batch, ps_async
from urllib.parse import quote as _uq

# Optimized: persistent runspace instead of new process per call
def _ps(cmd: str) -> str:
    try:
        return _ps_fast(cmd)
    except Exception as e:
        return f"Error: {e}"


# ── Patterns: fast keyword-based dispatch (O(1)) + regex fallback ──────

# Keyword hash map: if ANY of these words appear, try the corresponding action
_KEYWORD_MAP: dict[str, str] = {
    # System
    "lock": "lock", "locked": "lock",
    "sleep": "sleep", "hibernate": "hibernate",
    "restart": "restart", "reboot": "restart",
    "shutdown": "shutdown", "shut down": "shutdown", "power off": "shutdown",
    "restarting": "restart", "rebooting": "restart",
    "logoff": "logoff", "sign out": "logoff", "sign out": "logoff",
    "trash": "trash", "recycle bin": "trash", "recycle": "trash",
    "screenshot": "screenshot", "screen capture": "screenshot",
    "snipping": "snipping_tool", "snip": "snipping_tool",
    "show desktop": "show_desktop", "show me the desktop": "show_desktop",
    "minimize": "minimize_all", "minimise": "minimize_all",
    "alt tab": "alt_tab", "switch window": "alt_tab",
    "task view": "task_view", "taskview": "task_view",

    # Session
    "switch user": "switch_user",
    "current user": "whoami",
    "who am i": "whoami",

    # Power
    "battery": "battery_status",
    "battery level": "battery_status",
    "battery saver": "battery_saver",
    "power plan": "power_plan",
    "power saving": "power_plan",
    "uptime": "uptime",
    "last boot": "last_boot",

    # Volume
    "volume up": "vol_up", "louder": "vol_up", "turn it up": "vol_up",
    "turn up the volume": "vol_up", "turn up volume": "vol_up",
    "volume down": "vol_down", "quieter": "vol_down", "turn it down": "vol_down",
    "turn down the volume": "vol_down", "turn down volume": "vol_down",
    "mute": "vol_mute", "unmute": "vol_mute", "silence": "vol_mute",
    "mic": "mic_toggle",
    "microphone": "mic_toggle",
    "audio device": "audio_device",
    "speaker": "speaker_test",

    # Display
    "brightness up": "brightness_up", "brighter": "brightness_up",
    "brightness down": "brightness_down", "dimmer": "brightness_down",
    "night light": "night_light", "night mode": "night_light",
    "dark mode": "toggle_theme", "light mode": "toggle_theme",
    "hdr": "hdr_toggle",
    "screen resolution": "screen_resolution",
    "display": "display_info",
    "projector": "projector_mode",
    "second screen": "second_screen",

    # WiFi
    "wifi on": "wifi_on", "wi-fi on": "wifi_on",
    "wifi off": "wifi_off", "wi-fi off": "wifi_off",
    "wifi": "wifi_list", "wi-fi": "wifi_list",
    "hotspot": "hotspot_toggle",
    "airplane mode": "airplane_mode",
    "network": "network_info",
    "ip": "network_info",
    "ipconfig": "network_info",
    "dns": "dns_flush",
    "flush dns": "dns_flush",
    "proxy": "proxy_status",
    "network profile": "network_profile",

    # Bluetooth
    "bluetooth on": "bt_on",
    "bluetooth off": "bt_off",
    "bluetooth": "bt_devices",
    "bt devices": "bt_devices",

    # Processes
    "task manager": "taskmgr",
    "process": "process_list",
    "processes": "process_list",
    "running": "process_list",
    "kill": "process_kill",
    "stop process": "process_kill",
    "startup": "startup_programs",

    # Services
    "service": "service_list",
    "services": "service_list",

    # Windows
    "settings": "settings",
    "windows settings": "settings",
    "network settings": "network_settings",
    "control panel": "control_panel",
    "device manager": "device_manager",
    "registry": "reg_edit",
    "calculator": "calc",
    "notepad": "notepad",
    "terminal": "terminal",
    "command prompt": "terminal", "cmd": "terminal",
    "powershell": "terminal",

    # Windows Update
    "windows update": "windows_update", "check for update": "windows_update",
    "check for updates": "windows_update", "check updates": "windows_update",
    "check update": "windows_update",
    "install update": "windows_update",

    # Network devices
    "scan network": "scan_network",
    "network scan": "scan_network",
    "arp": "scan_network",
    "wake": "wol",
    "wake on lan": "wol",
    "wol": "wol",
    "ping": "ping",

    # Files
    "file": "search_files",
    "files": "search_files",
    "folder": "open_documents",
    "directory": "open_documents",
    "downloads": "open_downloads",
    "downloads folder": "open_downloads",
    "documents": "open_documents",
    "recent files": "recent_files",
    "recycle": "trash",
    "usb": "usb_eject",
    "eject": "usb_eject",
    "disk": "drive_usage",
    "drive": "drive_list",
    "disk space": "drive_usage",
    "free space": "drive_usage",
    "disk cleanup": "disk_cleanup",

    # Clipboard
    "clipboard": "clipboard_show",
    "copy": "clipboard_copy",
    "paste": "clipboard_paste",

    # Media
    "next track": "media_next", "skip": "media_next", "next song": "media_next",
    "previous track": "media_prev", "prev": "media_prev", "previous song": "media_prev",
    "play": "media_play", "pause": "media_pause", "stop": "media_pause",
    "resume": "media_play",
    "spotify": "spotify", "music player": "spotify",
    "what song": "current_song",
    "now playing": "current_song",
    "shazam": "shazam", "identify song": "shazam",

    # Search
    "google": "search",
    "search for": "search",
    "look up": "search",
    "search google": "search",
    "youtube": "search_youtube",
    "yt": "search_youtube",
    "wikipedia": "search_wiki",
    "wiki": "search_wiki",
    "amazon": "search_amazon",
    "shop": "search_amazon",
    "news": "search_news",
    "maps": "search_maps",

    # Time
    "time": "time",
    "date": "time",
    "current time": "time",
    "current date": "time",
    "timer": "timer",
    "alarm": "alarm",
    "countdown": "timer",

    # Browser
    "browser": "browser",
    "chrome": "browser",
    "open url": "open_url",
    "bookmark": "open_bookmarks",
    "history": "open_history",
    "incognito": "open_incognito",
    "private": "open_incognito",

    # Misc
    "help": "help",
    "what can you": "help",
    "what do you": "help",
    "system info": "system_info",
    "computer info": "system_info",
    "about this pc": "system_info",
    "hardware": "hardware_info",
    "weather": "weather",
    "public ip": "public_ip",
    "my ip": "public_ip",
    "external ip": "public_ip",
    "ip address": "public_ip",
    "type": "send_keys",
    "on screen keyboard": "osk",
    "magnifier": "magnifier",
    "narrator": "narrator",
    "high contrast": "high_contrast",
    "notification": "send_notification",
    "notify": "send_notification",
    "toast": "send_notification",
    "empty recycle": "trash",
    "clean trash": "trash",
    "snipping tool": "snipping_tool",
    "screenshot tool": "snipping_tool",
    "camera": "camera",
    "webcam": "camera",
    "take photo": "camera",
    "sticky keys": "sticky_keys",
    "filter keys": "filter_keys",
    "mouse keys": "mouse_keys",
    "vpn": "vpn_status",
    "firewall": "firewall_status",
    "defender": "defender_status",
    "virus": "defender_scan",
    "scan virus": "defender_scan",
    "bitlocker": "bitlocker_status",
    "encryption": "bitlocker_status",
    "windows features": "windows_features",
    "features": "windows_features",
    "task scheduler": "scheduler_tasks",
    "scheduled tasks": "scheduler_tasks",
    "quick assist": "quick_assist",
    "remote desktop": "remote_desktop",
    "character map": "charmap",
    "math": "math_eval",
    "calculate": "math_eval",
    "calculator": "calc",
    "volume mixer": "vol_mixer",
    "color profile": "color_profile",
    "calibration": "calibrate_display",
    "cleanmgr": "disk_cleanup",
    "disk cleanup": "disk_cleanup",
    "refresh rate": "refresh_rate",
    "screen refresh": "refresh_rate",
    "multiple monitors": "multi_monitor",
    "extend display": "second_screen",
    "duplicate display": "second_screen",
    "project": "projector_mode",
    "windows key": "send_keys",
    "open folder": "open_documents",
    "show folder": "open_documents",
    "launch": "open_app",
    "start app": "open_app",
    "run": "run_dialog",
    "execute": "run_dialog",
    "command": "run_dialog",
    "environment": "env_list",
    "environment variable": "env_list",
    "path variable": "env_list",
    "change directory": "open_documents",
    "file explorer": "open_documents",
    "explorer": "open_documents",
    "this pc": "open_documents",
    "user": "whoami",
    "username": "whoami",
    "computer name": "system_info",
    "hostname": "system_info",
    "memory": "memory_info",
    "ram": "memory_info",
    "cpu": "cpu_info",
    "processor": "cpu_info",
    "graphics": "gpu_info",
    "gpu": "gpu_info",
    "video card": "gpu_info",
}

# Pre-compiled keyword → action (lowercase)
_KEYWORD_LOOKUP: dict[str, str] = {k.lower().strip(): v for k, v in _KEYWORD_MAP.items()}

_ACTION_PATTERNS = {
    # ── System ──────────────────────────────────────────────────
    r"^(?:lock|secure)\s+(?:my\s+)?(?:computer|pc|laptop|system|workstation)": "lock",
    r"^(?:put|send)\s+(?:the\s+)?(?:computer|pc|laptop)\s+(?:to\s+)?(?:sleep|suspend)": "sleep",
    r"^(?:hibernate|suspend)\s+(?:the\s+)?(?:computer|pc|laptop)": "hibernate",
    r"^(?:restart|reboot)\s+(?:the\s+)?(?:computer|pc|laptop|system)": "restart",
    r"^(?:shut\s*down|power\s*off|turn\s*off)\s+(?:the\s+)?(?:computer|pc|laptop|system)": "shutdown",
    r"^(?:log\s*off|sign\s*out)\s+(?:of\s+)?(?:the\s+)?(?:computer|pc|session)": "logoff",
    r"^(?:what\s+(?:is\s+)?my\s+(?:user|username|account)\s*(?:name)?)": "whoami",
    r"^switch\s+(?:user|account)": "switch_user",
    r"^windows\s+version": "winver",

    # ── Power ───────────────────────────────────────────────────
    r"(?:battery|power)\s+(?:status|level|percentage|remaining|life)": "battery_status",
    r"^(?:battery\s+)?(?:saver|save\s+mode|power\s+save)": "battery_saver",
    r"^(?:power\s+)?(?:plan|scheme|profile)": "power_plan",
    r"^(?:uptime|how\s+long\s+(?:has|since)\s+(?:my\s+)?(?:pc|computer|system)\s+(?:been\s+)?(?:on|running|up))": "uptime",
    r"^last\s+boot": "last_boot",
    r"^(?:what\s+)?(?:os|operating\s+system)\s+(?:am\s+I\s+)?(?:running|using|on)": "os_info",

    # ── Volume / Audio ──────────────────────────────────────────
    r"^(?:volume|sound|audio)\s+up": "vol_up",
    r"^(?:volume|sound|audio)\s+down": "vol_down",
    r"^(?:mute|unmute|silence)\s+(?:(?:the\s+)?(?:audio|sound|volume|system|pc))?": "vol_mute",
    r"^(?:set\s+)?volume\s+to\s+(\d+)": "vol_set",
    r"^(?:what|current)\s+(?:is\s+)?(?:the\s+)?volume": "vol_level",
    r"^(?:mic|microphone)\s+(?:mute|unmute|toggle)": "mic_toggle",
    r"^(?:mic|microphone)\s+(?:status|level)": "mic_status",
    r"^(?:switch|change|set)\s+(?:audio\s+)?device": "audio_device",
    r"^test\s+(?:audio|sound|speaker)": "speaker_test",
    r"^(?:volume\s+)?mixer": "vol_mixer",

    # ── Display / Screen ────────────────────────────────────────
    r"^(?:brightness|screen|display)\s+up": "brightness_up",
    r"^(?:brightness|screen|display)\s+down": "brightness_down",
    r"^(?:set\s+)?brightness\s+to\s+(\d+)": "brightness_set",
    r"^(?:turn\s+)?(?:on|off)\s+(?:night\s+light|night\s+mode|blue\s+light)": "night_light",
    r"^(?:dark|light)\s+mode": "toggle_theme",
    r"^(?:turn\s+)?(?:on|off)\s+hdr": "hdr_toggle",
    r"^(?:screen\s+)?resolution": "screen_resolution",
    r"^(?:display|screen)\s+(?:info|information|details|status)": "display_info",
    r"^(?:second\s+)?(?:monitor|display|screen)\s+(?:extend|duplicate|second\s+screen\s+only|pc\s+screen\s+only)": "second_screen",
    r"^(?:project|projector)": "projector_mode",
    r"^(?:multiple\s+)?monitors": "multi_monitor",
    r"^calibrate\s+(?:display|screen|color)": "calibrate_display",
    r"^(?:color\s+)?profile": "color_profile",
    r"^(?:refresh\s+rate|screen\s+refresh)": "refresh_rate",
    r"^rotate\s+(?:display|screen)": "rotate_display",
    r"^orientation": "rotate_display",

    # ── WiFi / Network ──────────────────────────────────────────
    r"^(?:turn\s+on|enable)\s+(?:the\s+)?(?:wifi|wi-fi|wireless)": "wifi_on",
    r"^(?:turn\s+off|disable)\s+(?:the\s+)?(?:wifi|wi-fi|wireless)": "wifi_off",
    r"^(?:show|list|scan|find)\s+(?:available\s+)?(?:wifi|wi-fi|wireless)\s*(?:networks?)?": "wifi_list",
    r"^(?:show|what)\s+(?:my\s+)?(?:wifi|wi-fi)\s+(?:password|pass|key)": "wifi_password",
    r"^(?:connect|join)\s+to\s+(?:wifi|wi-fi|network)\s+(.+?)(?:\s+password\s+(.+?))?$": "wifi_connect",
    r"^(?:disconnect|turn\s+off)\s+(?:from\s+)?(?:wifi|wi-fi|network)": "wifi_disconnect",
    r"^forget\s+(?:wifi|wi-fi|network)\s+(.+?)$": "wifi_forget",
    r"^(?:turn\s+on|enable)\s+(?:mobile\s+)?hotspot": "hotspot_toggle",
    r"^(?:turn\s+off|disable)\s+(?:mobile\s+)?hotspot": "hotspot_toggle",
    r"^(?:airplane\s+mode|flight\s+mode)": "airplane_mode",
    r"^(?:show|what|my)\s+(?:network|connection|ip)\s+(?:info|details|status|config)": "network_info",
    r"^ipconfig": "network_info",
    r"^(?:list|show)\s+(?:network\s+)?adapters": "network_adapters",
    r"^(?:release|renew)\s+(?:ip|dhcp)": "ip_renew",
    r"^flush\s+dns": "dns_flush",
    r"^(?:proxy|vpn)\s+(?:status|settings)": "proxy_status",
    r"^set\s+(?:network\s+)?profile\s+(?:to\s+)?(public|private|domain)": "network_profile",
    r"^(?:turn\s+on|enable)\s+(?:network\s+)?discovery": "network_discovery",

    # ── Bluetooth ───────────────────────────────────────────────
    r"^(?:turn\s+on|enable)\s+(?:the\s+)?bluetooth": "bt_on",
    r"^(?:turn\s+off|disable)\s+(?:the\s+)?bluetooth": "bt_off",
    r"^(?:show|list|scan)\s+(?:bluetooth|bt)\s+devices": "bt_devices",
    r"^(?:pair|connect)\s+(?:bluetooth\s+)?(?:device\s+)?(.+?)$": "bt_pair",
    r"^(?:unpair|remove|disconnect)\s+(?:bluetooth\s+)?(?:device\s+)?(.+?)$": "bt_unpair",

    # ── Network devices (ARP / WoL / Ping) ──────────────────────
    r"^(?:scan|find|list|show)\s+(?:all\s+)?(?:network\s+)?(?:devices|hosts|machines)": "scan_network",
    r"^(?:who|what)\s*(?:'s|is)\s+(?:on|connected\s+to)\s+(?:my\s+)?(?:network|wifi)": "scan_network",
    r"^(?:wake|turn\s+on|power\s+on)\s+(?:up\s+)?(?:my\s+)?(?:device\s+)?(.+?)$": "wol",
    r"^(?:ping|check)\s+(?:device\s+|host\s+)?(.+?)$": "ping",

    # ── Processes ───────────────────────────────────────────────
    r"^(?:list|show)\s+(?:running\s+)?(?:process|processes|tasks)": "process_list",
    r"^(?:kill|stop|end)\s+(?:process|task)\s+(.+?)$": "process_kill",
    r"^(?:start|run|launch)\s+(?:process|program|app)\s+(.+?)$": "process_start",
    r"^(?:cpu|processor)\s+(?:usage|load|performance)": "cpu_usage",
    r"^(?:memory|ram)\s+(?:usage|load|performance|status)": "memory_usage",

    # ── Services ────────────────────────────────────────────────
    r"^(?:list|show)\s+(?:all\s+)?(?:services|windows\s+services)": "service_list",
    r"^(?:start|restart)\s+(?:service|the\s+service)\s+(.+?)$": "service_start",
    r"^(?:stop)\s+(?:service|the\s+service)\s+(.+?)$": "service_stop",
    r"^(?:disable|enable)\s+(?:service|the\s+service)\s+(.+?)$": "service_disable",
    r"^service\s+(.+?)\s+(?:status|state)": "service_status",

    # ── Startup ─────────────────────────────────────────────────
    r"^(?:list|show)\s+(?:startup|boot)\s+(?:programs|apps|items)": "startup_programs",
    r"^task\s+manager": "taskmgr",

    # ── Windows / Apps ──────────────────────────────────────────
    r"^open\s+(?:settings|windows\s+settings)": "settings",
    r"^control\s+panel": "control_panel",
    r"^device\s+manager": "device_manager",
    r"^registry\s+(?:editor|edit)": "reg_edit",
    r"^open\s+(?:browser|chrome|firefox|edge)": "browser",
    r"^open\s+(?:my\s+)?(?:email|gmail|mail|outlook)": "email",
    r"^open\s+(?:my\s+)?(?:calendar|schedule)": "calendar",
    r"^open\s+(?:my\s+)?(?:drive|google\s*drive|cloud)": "drive",
    r"^open\s+(?:my\s+)?(?:youtube|yt)": "youtube",
    r"^open\s+(?:my\s+)?(?:github|repos|code)": "github",
    r"^open\s+(?:my\s+)?(?:discord|chat)": "discord",
    r"^open\s+(?:my\s+)?(?:slack|teams)": "slack",
    r"^open\s+(?:my\s+)?(?:vscode|visual\s+studio\s+code|code\s+editor)": "vscode",
    r"^open\s+(?:my\s+)?(?:terminal|cmd|powershell|console)": "terminal",
    r"^open\s+(?:the\s+)?(?:calculator|calc)": "calc",
    r"^open\s+(?:the\s+)?(?:notepad|text\s+editor)": "notepad",
    r"^open\s+(?:the\s+)?(?:camera|webcam)": "camera",
    r"^open\s+(?:the\s+)?(?:snipping\s+tool|snip|screenshot\s+tool)": "snipping_tool",
    r"^open\s+(?:app\s+|the\s+)?(.+?)$": "open_app",

    # ── Windows Update ──────────────────────────────────────────
    r"^(?:check|search)\s+(?:for\s+)?(?:windows\s+)?updates": "windows_update",
    r"^install\s+(?:windows\s+)?updates": "windows_update",
    r"^update\s+windows": "windows_update",
    r"^(?:windows\s+)?features": "windows_features",

    # ── Files / Folders ─────────────────────────────────────────
    r"^(?:show|open|list)\s+(?:my\s+)?(?:recent|recent\s+files)": "recent_files",
    r"^(?:show|open)\s+(?:my\s+)?(?:downloads|download\s+folder\d*)": "open_downloads",
    r"^(?:show|open)\s+(?:my\s+)?(?:documents|docs)\s*(?:folder)?" : "open_documents",
    r"^(?:show|open)\s+(?:my\s+)?(?:desktop)\s*(?:folder)?": "open_desktop",
    r"^(?:list|show)\s+(?:files|contents)\s+in\s+(.+?)$": "list_directory",
    r"^(?:open|show)\s+(?:folder|directory)\s+(.+?)$": "open_directory",
    r"^(?:create|make|new)\s+(?:folder|directory)\s+(.+?)$": "create_directory",
    r"^(?:create|make|new)\s+file\s+(.+?)$": "create_file",
    r"^(?:delete|remove|trash)\s+(?:file|folder)\s+(.+?)$": "delete_file",
    r"^(?:move|rename)\s+(.+?)\s+(?:to|as)\s+(.+?)$": "move_file",
    r"^(?:copy|duplicate)\s+(.+?)\s+(?:to|into)\s+(.+?)$": "copy_file",
    r"^(?:find|search)\s+(?:my\s+)?(?:computer|files|documents)\s+(?:for\s+)?(.+?)$": "search_files",
    r"^(?:search|find)\s+(?:files?\s+)?(?:containing|with|named)\s+(.+?)$": "file_search_content",
    r"^(?:file\s+)?(?:info|details|properties)\s+(.+?)$": "file_info",
    r"^(?:list|show)\s+(?:all\s+)?(?:drives|disks|volumes)": "drive_list",
    r"^(?:drive|disk)\s+(?:space|usage|free)": "drive_usage",
    r"^disk\s+cleanup": "disk_cleanup",
    r"^(?:empty|clear|clean)\s+(?:the\s+)?(?:trash|recycle\s*bin|bin)": "trash",
    r"^list\s+recycle\s+bin": "recycle_list",
    r"^restore\s+(?:from\s+)?(?:recycle\s+)?bin\s+(.+?)$": "recycle_restore",
    r"^(?:eject|safely\s+remove)\s+(?:usb|drive|disk)": "usb_eject",

    # ── Clipboard ───────────────────────────────────────────────
    r"^(?:show|read|what.*on|get)\s+(?:my\s+)?(?:clipboard|clip)": "clipboard_show",
    r"^(?:copy|save)\s+(?:to\s+)?(?:clipboard|clip)": "clipboard_copy",
    r"^(?:paste|paste\s+from)\s+(?:clipboard|clip)": "clipboard_paste",
    r"^clear\s+(?:the\s+)?(?:clipboard|clip)": "clipboard_clear",

    # ── Media ───────────────────────────────────────────────────
    r"^(?:play|start)\s+(?:some\s+)?(?:music|song|audio|beats)": "music",
    r"^(?:play|start)\s+(?:some\s+)?(?:lofi|lo-fi|chill|study)\s*(?:music|beats)?": "music_lofi",
    r"^(?:play|start|launch|open)\s+spotify": "spotify",
    r"^(?:next|skip)\s+(?:song|track)": "media_next",
    r"^(?:previous|prev|go\s+back)\s+(?:song|track)": "media_prev",
    r"^(?:pause|stop)\s+(?:the\s+)?(?:music|song|audio|video|playback)": "media_pause",
    r"^(?:play|resume)\s+(?:the\s+)?(?:music|song|audio|video)": "media_play",
    r"^(?:what|which)\s+(?:song|music|artist|track)\s+(?:is\s+)?(?:playing|on)": "current_song",
    r"^shazam": "shazam",

    # ── Search ──────────────────────────────────────────────────
    r"^(?:search|google|look\s+up)\s+(?:for\s+)?(.+?)$": "search",
    r"^(?:search|find)\s+(?:on\s+)?(?:youtube|yt)\s+(.+?)$": "search_youtube",
    r"^(?:search|find)\s+(?:on\s+)?(?:wikipedia|wiki)\s+(.+?)$": "search_wiki",
    r"^(?:search|find)\s+(?:on\s+)?(?:amazon|shop)\s+(.+?)$": "search_amazon",
    r"^(?:search|find)\s+(?:on\s+)?(?:news|google\s+news)\s+(.+?)$": "search_news",
    r"^(?:search|find)\s+(?:on\s+)?(?:maps|google\s+maps)\s+(.+?)$": "search_maps",

    # ── Browser ─────────────────────────────────────────────────
    r"^(?:open|go\s+to)\s+(?:url|website|page|link|site)\s+(.+?)$": "open_url",
    r"^(?:show|open)\s+(?:my\s+)?(?:bookmarks|favorites)": "open_bookmarks",
    r"^(?:show|open)\s+(?:my\s+)?(?:history|browsing\s+history)": "open_history",
    r"^open\s+(?:a\s+)?(?:incognito|private)\s+(?:window|tab)": "open_incognito",
    r"^(?:open|new)\s+(?:tab|window)": "new_tab",

    # ── Timer / Clock ───────────────────────────────────────────
    r"^(?:what|current)\s+(?:time|date|day)": "time",
    r"^(?:set|start)\s+(?:a\s+)?timer\s+(?:for\s+)?(.+?)$": "timer",
    r"^(?:set|create)\s+(?:an?\s+)?alarm\s+(?:for\s+)?(.+?)$": "alarm",
    r"^(?:stop|end|cancel)\s+(?:the\s+)?timer": "timer_stop",
    r"^timer\s+remaining": "timer_remaining",

    # ── Clipboard / Keys ────────────────────────────────────────
    r"^type\s+(.+?)$": "send_keys",
    r"^run\s+(?:command|program|executable)\s+(.+?)$": "run_dialog",
    r"^on.?screen\s+keyboard": "osk",

    # ── Accessibility ───────────────────────────────────────────
    r"^(?:turn\s+on|open)\s+(?:the\s+)?(?:magnifier|magnify|zoom)": "magnifier",
    r"^(?:turn\s+on|open)\s+(?:the\s+)?(?:narrator|screen\s+reader)": "narrator",
    r"^(?:high\s+contrast|toggle\s+contrast)": "high_contrast",
    r"^(?:sticky\s+keys|toggle\s+sticky)": "sticky_keys",
    r"^(?:filter\s+keys|toggle\s+filter)": "filter_keys",
    r"^(?:mouse\s+keys|toggle\s+mouse\s+keys)": "mouse_keys",
    r"^(?:closed\s+)?captions": "closed_captions",

    # ── Registry ────────────────────────────────────────────────
    r"^reg\s+read\s+(.+?)$": "reg_read",
    r"^reg\s+write\s+(.+?)\s+=\s+(.+?)$": "reg_write",

    # ── Environment ─────────────────────────────────────────────
    r"^(?:list|show)\s+(?:all\s+)?(?:env|environment)\s*(?:variables?)?": "env_list",
    r"^(?:get|show)\s+(?:env|environment)\s+variable\s+(.+?)$": "env_get",

    # ── Scheduled Tasks ─────────────────────────────────────────
    r"^(?:list|show)\s+(?:scheduled\s+)?tasks": "scheduler_tasks",
    r"^run\s+(?:scheduled\s+)?task\s+(.+?)$": "scheduler_run",
    r"^task\s+(.+?)\s+(?:status|state)": "scheduler_status",

    # ── Security / Firewall ─────────────────────────────────────
    r"^(?:firewall|windows\s+firewall)\s+(?:status|state)": "firewall_status",
    r"^(?:turn\s+on|enable)\s+(?:firewall|windows\s+firewall)": "firewall_on",
    r"^(?:turn\s+off|disable)\s+(?:firewall|windows\s+firewall)": "firewall_off",
    r"^(?:windows\s+)?defender\s+(?:status|state)": "defender_status",
    r"^(?:run|start)\s+(?:defender|windows\s+defender)\s+scan": "defender_scan",
    r"^(?:bitlocker|drive\s+encryption)\s+(?:status|state)": "bitlocker_status",
    r"^(?:uac|user\s+account\s+control)\s+(?:status|level|setting)": "uac_status",
    r"^(?:quick\s+)?assist": "quick_assist",
    r"^remote\s+desktop": "remote_desktop",

    # ── Notifications ───────────────────────────────────────────
    r"^(?:send|show)\s+(?:a\s+)?(?:notification|toast|alert|message)\s+(.+?)$": "send_notification",
    r"^clear\s+(?:all\s+)?notifications": "clear_notifications",

    # ── VPN ─────────────────────────────────────────────────────
    r"^(?:vpn|virtual\s+private\s+network)\s+(?:status|state|connection)": "vpn_status",
    r"^(?:vpn|virtual\s+private\s+network)\s+connect": "vpn_connect",
    r"^(?:vpn|virtual\s+private\s+network)\s+disconnect": "vpn_disconnect",

    # ── Misc ────────────────────────────────────────────────────
    r"^(?:help|what\s+(?:can|do)\s+you\s+(?:do|control)|commands)": "help",
    r"^(?:system|computer)\s+(?:info|information|details|specs)": "system_info",
    r"^(?:hardware|specs|specifications|components)": "hardware_info",
    r"^(?:cpu|processor)\s+info": "cpu_info",
    r"^(?:gpu|graphics|video)\s+(?:card|info|details)": "gpu_info",
    r"^(?:memory|ram)\s+(?:info|details|specs)": "memory_info",
    r"^(?:weather|temperature|forecast)": "weather",
    r"^(?:what\s+)?(?:is\s+)?(?:my\s+)?(?:public|external|global)\s+(?:ip|internet\s+ip)": "public_ip",
    r"^(?:math|calculate|eval)\s+(.+?)$": "math_eval",
    r"^character\s+map": "charmap",
    r"^(?:windows\s+)?key\s+(.+?)$": "send_keys",
    r"^(?:screenshot|screen\s+(?:capture|shot))\s+(.*)": "screenshot",
    r"^(?:show|display)\s+(?:desktop|show\s+desktop)": "show_desktop",
    r"^(?:minimize|hide)\s+(?:all\s+)?(?:windows|apps)": "minimize_all",
    r"^(?:window|app)\s+(?:minimize|maximize|restore|close)": "window_manage",
    r"^(?:snap|tile)\s+(?:window|app)\s+(?:left|right|top|bottom)": "window_snap",
    r"^(?:switch|change|alt\s?tab)\s+(?:window|app|task)": "alt_tab",
    r"^task\s+view": "task_view",
    r"^(?:new\s+)?(?:virtual\s+)?desktop": "virtual_desktop",
    r"^(?:switch|go\s+to)\s+(?:desktop|virtual\s+desktop)\s+(\d+)": "switch_desktop",
    r"^open\s+(?:my\s+)?(?:camera|webcam)": "camera",
    r"^(?:network|network\s*&?\s*internet)\s+(?:settings|panel)": "network_settings",
    r"^(?:date\s+and\s+time|time\s+&?\s*date)\s+(?:settings|panel)": "datetime_settings",
    r"^(?:personalization|personalize|theme)\s+(?:settings|panel)": "personalization_settings",
    r"^(?:apps\s+&?\s*features|installed\s+apps)\s+(?:settings|panel)": "apps_features",
    r"^(?:backup|restore|file\s+history)\s+(?:settings|panel)": "backup_settings",
    r"^(?:troubleshoot|troubleshooting|fix)\s+(?:settings|panel|problems)": "troubleshoot_settings",
    r"^(?:windows\s+)?(?:security|update\s+&?\s*security)\s+settings": "security_settings",
    r"^(?:sound|audio)\s+(?:settings|panel)": "sound_settings",
    r"^(?:storage|storage\s+sense)\s+(?:settings|panel)": "storage_settings",
    r"^(?:sign-in|login|password)\s+(?:options|settings|security)": "signin_options",
}

_BROAD_PATTERNS = [
    (r"(?:scan|list|find|show)\s+(?:all\s+)?(?:devices|hosts|machines)\s*(?:on\s+(?:the\s+)?(?:network|wifi|lan))?", "scan_network"),
    (r"(?:scan|list|find|show)\s+(?:the\s+)?(?:network|wifi|lan)\s+(?:for\s+)?(?:devices|hosts|machines)?", "scan_network"),
    (r"(?:what|which)\s+(?:devices|hosts)\s+(?:are\s+)?(?:on|connected)", "scan_network"),
    (r"(?:who|what)\s*(?:'s|is)\s+(?:on|connected\s+to)\s+(?:my\s+)?(?:network|wifi)", "scan_network"),
    (r"(?:wake|turn\s+on|power\s+on|start)\s+up?\s+(?:my\s+)?(?:computer|pc|desktop|laptop)", "wol"),
    (r"(?:turn\s+(?:the\s+)?)?(?:volume|sound|audio)\s+(?:up|down|higher|lower)", "vol_up"),
    (r"(?:set|change|adjust)\s+(?:the\s+)?(?:volume|sound|audio)\s+(?:to\s+)?(\d+)", "vol_set"),
    (r"(?:play|start)\s+(?:some\s+)?(?:music|song|audio|beats)", "music"),
    (r"(?:play|start)\s+(?:a\s+)?(?:song|track)\s+(?:called\s+|named\s+)?(.+)", "music"),
    (r"(?:next|skip|change)\s+(?:the\s+)?(?:song|track|music)", "media_next"),
    (r"(?:previous|prev|go\s+back)\s+(?:the\s+)?(?:song|track)", "media_prev"),
    (r"(?:stop|pause)\s+(?:the\s+)?(?:music|song|audio|video|playback)", "media_pause"),
    (r"(?:resume|continue|unpause)\s+(?:the\s+)?(?:music|song|audio)", "media_play"),
    (r"(?:mute|unmute|silence)\s+(?:the\s+)?(?:audio|sound|system|pc)", "vol_mute"),
    (r"(?:lock|secure|sign\s+out)\s+(?:my\s+)?(?:computer|pc|laptop|system|workstation)", "lock"),
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
    (r"(?:battery|power)\s+(?:level|status|life|remaining|percentage|charge)", "battery_status"),
    (r"(?:show|read|what.*on)\s+(?:my\s+)?(?:clipboard|clip)", "clipboard_show"),
    (r"(?:show|open|list)\s+(?:my\s+)?(?:recent|recent\s+files|files)", "recent_files"),
    (r"(?:empty|clear|clean)\s+(?:the\s+)?(?:trash|recycle\s*bin|bin)", "trash"),
    (r"(?:show|minimize)\s+(?:the\s+)?(?:desktop|show\s+desktop)", "show_desktop"),
    (r"(?:minimize|hide)\s+(?:all\s+)?(?:windows|apps)", "minimize_all"),
    (r"(?:switch|change)\s+(?:windows|apps|tasks)", "alt_tab"),
    (r"(?:dark|light)\s+mode", "toggle_theme"),
    (r"(?:turn\s+(?:the\s+)?)?(?:wifi|wi-fi|wireless)\s+(?:on|off)", "wifi_on"),
    (r"(?:open\s+)?(?:browser|chrome|firefox|edge)\s*(?:please)?", "browser"),
    (r"(?:list|show)\s+(?:running\s+)?(?:processes|tasks|apps)", "process_list"),
    (r"(?:system|pc|computer)\s+(?:specs|info|details)", "system_info"),
    (r"(?:cpu|processor)\s+(?:usage|info|details)", "cpu_usage"),
    (r"(?:ram|memory)\s+(?:usage|info|details)", "memory_usage"),
    (r"(?:gpu|graphics|video)\s+(?:info|details|usage)", "gpu_info"),
    (r"(?:weather|temperature|outside|forecast)\s*(?:today|now|outside)?", "weather"),
    (r"(?:what\s+)?(?:external|public|my)\s+ip", "public_ip"),
    (r"(?:windows\s+)?(?:update|check\s+for\s+updates)", "windows_update"),
]

_ACTION_LABELS = {
    "lock": "🔒 Locking workstation...", "sleep": "💤 Going to sleep...",
    "hibernate": "💤 Hibernating...", "restart": "🔄 Restarting...",
    "shutdown": "⏻ Shutting down...", "logoff": "🚪 Signing out...",
    "whoami": "👤 Current user info", "switch_user": "🔄 Switching user...",
    "winver": "💻 Windows version info",
    "battery_status": "🔋 Battery status", "battery_saver": "🔋 Battery saver",
    "power_plan": "⚡ Power plan", "uptime": "⏱ Uptime",
    "last_boot": "📅 Last boot time", "os_info": "💻 OS info",
    "vol_up": "🔊 Volume up", "vol_down": "🔉 Volume down",
    "vol_mute": "🔇 Toggle mute", "vol_set": "🔊 Setting volume",
    "vol_level": "🔊 Current volume", "mic_toggle": "🎤 Toggle microphone",
    "mic_status": "🎤 Microphone status", "audio_device": "🔊 Audio device",
    "speaker_test": "🔊 Testing speakers...", "vol_mixer": "🔊 Volume mixer",
    "brightness_up": "☀ Brightness up", "brightness_down": "☁ Brightness down",
    "brightness_set": "☀ Setting brightness", "night_light": "🌙 Toggle night light",
    "toggle_theme": "🎨 Toggling theme...", "hdr_toggle": "🎨 Toggle HDR",
    "screen_resolution": "🖥 Screen resolution", "display_info": "🖥 Display info",
    "second_screen": "🖥 Second screen", "projector_mode": "🖥 Projector mode",
    "multi_monitor": "🖥 Multiple monitors", "calibrate_display": "🎨 Calibrating display...",
    "color_profile": "🎨 Color profile", "refresh_rate": "🖥 Refresh rate",
    "rotate_display": "🔄 Rotating display...",
    "wifi_on": "📶 WiFi on", "wifi_off": "📶 WiFi off",
    "wifi_list": "📶 Scanning networks...", "wifi_password": "📶 WiFi password",
    "wifi_connect": "📶 Connecting...", "wifi_disconnect": "📶 Disconnecting...",
    "wifi_forget": "📶 Forgetting network...", "hotspot_toggle": "📶 Toggle hotspot",
    "airplane_mode": "✈ Airplane mode", "network_info": "🌐 Network info",
    "network_adapters": "🌐 Network adapters", "ip_renew": "🌐 Renewing IP...",
    "dns_flush": "🌐 Flushing DNS...", "proxy_status": "🌐 Proxy status",
    "network_profile": "🌐 Network profile", "network_discovery": "🌐 Network discovery",
    "bt_on": "📡 Bluetooth on", "bt_off": "📡 Bluetooth off",
    "bt_devices": "📡 Bluetooth devices", "bt_pair": "📡 Pairing...",
    "bt_unpair": "📡 Unpairing...",
    "scan_network": "🔍 Scanning network...", "wol": "⚡ Wake signal sent",
    "ping": "📡 Pinging...",
    "process_list": "📊 Running processes", "process_kill": "⛔ Killing process...",
    "process_start": "▶ Starting process...", "cpu_usage": "📊 CPU usage",
    "memory_usage": "📊 Memory usage",
    "service_list": "⚙ Services", "service_start": "▶ Starting service...",
    "service_stop": "⏹ Stopping service...", "service_disable": "⚙ Disabling service...",
    "service_status": "⚙ Service status",
    "startup_programs": "🚀 Startup programs",
    "settings": "⚙ Opening Settings...", "control_panel": "⚙ Control Panel",
    "device_manager": "🔧 Device Manager", "reg_edit": "📝 Registry Editor",
    "browser": "🌐 Opening browser...", "email": "📧 Opening email...",
    "calendar": "📅 Opening calendar...", "drive": "💾 Opening Drive...",
    "youtube": "▶ Opening YouTube...", "github": "💻 Opening GitHub...",
    "discord": "💬 Opening Discord...", "slack": "💬 Opening Slack...",
    "vscode": "💻 Opening VS Code...", "terminal": "⌨ Opening terminal...",
    "calc": "🧮 Opening Calculator...", "notepad": "📝 Opening Notepad...",
    "camera": "📷 Opening Camera...", "snipping_tool": "✂ Opening Snipping Tool...",
    "open_app": "▶ Opening app...",
    "windows_update": "🔄 Windows Update", "windows_features": "⚙ Windows Features",
    "recent_files": "📁 Recent files", "open_downloads": "📁 Opening Downloads...",
    "open_documents": "📁 Opening Documents...", "open_desktop": "🖥 Opening Desktop...",
    "list_directory": "📁 Listing files...", "open_directory": "📁 Opening folder...",
    "create_directory": "📁 Creating folder...", "create_file": "📄 Creating file...",
    "delete_file": "🗑 Deleting...", "move_file": "📁 Moving...",
    "copy_file": "📁 Copying...", "search_files": "🔍 Searching files...",
    "file_search_content": "🔍 Searching file contents...", "file_info": "📄 File info",
    "drive_list": "💾 Drive list", "drive_usage": "💾 Disk usage",
    "disk_cleanup": "🧹 Disk Cleanup...", "trash": "🗑 Emptying recycle bin...",
    "recycle_list": "🗑 Recycle bin contents", "recycle_restore": "📄 Restoring...",
    "usb_eject": "🔌 Ejecting USB...",
    "clipboard_show": "📋 Reading clipboard...", "clipboard_copy": "📋 Copied to clipboard",
    "clipboard_paste": "📋 Pasted from clipboard", "clipboard_clear": "📋 Clipboard cleared",
    "music": "🎵 Opening music...", "music_lofi": "🎵 Lo-fi beats...",
    "spotify": "🎵 Spotify...", "media_next": "⏭ Skipping...",
    "media_prev": "⏮ Previous...", "media_pause": "⏸ Paused",
    "media_play": "▶ Playing", "current_song": "🎵 Now playing",
    "shazam": "🎵 Identifying...",
    "search": "🔍 Searching...", "search_youtube": "▶ Searching YouTube...",
    "search_wiki": "📖 Searching Wikipedia...", "search_amazon": "🛒 Searching Amazon...",
    "search_news": "📰 Searching news...", "search_maps": "🗺 Searching maps...",
    "open_url": "🌐 Opening URL...", "open_bookmarks": "⭐ Bookmarks",
    "open_history": "📜 History", "open_incognito": "🕶 Incognito window",
    "new_tab": "📄 New tab",
    "time": "🕐 Time and date", "timer": "⏱ Timer set",
    "alarm": "⏰ Alarm set", "timer_stop": "⏱ Timer stopped",
    "timer_remaining": "⏱ Timer remaining",
    "send_keys": "⌨ Typing...", "run_dialog": "▶ Run...",
    "osk": "⌨ Opening keyboard...",
    "magnifier": "🔍 Magnifier", "narrator": "🔊 Narrator",
    "high_contrast": "🎨 High contrast", "sticky_keys": "⌨ Sticky Keys",
    "filter_keys": "⌨ Filter Keys", "mouse_keys": "🖱 Mouse Keys",
    "closed_captions": "📺 Closed captions",
    "reg_read": "📝 Registry read", "reg_write": "📝 Registry write",
    "env_list": "📋 Environment variables", "env_get": "📋 Environment variable",
    "scheduler_tasks": "📅 Scheduled tasks", "scheduler_run": "▶ Running task...",
    "scheduler_status": "📅 Task status",
    "firewall_status": "🛡 Firewall status", "firewall_on": "🛡 Firewall enabled",
    "firewall_off": "🛡 Firewall disabled", "defender_status": "🛡 Defender status",
    "defender_scan": "🛡 Defender scan...", "bitlocker_status": "🔒 BitLocker status",
    "uac_status": "🛡 UAC status", "quick_assist": "🖥 Quick Assist",
    "remote_desktop": "🖥 Remote Desktop",
    "send_notification": "🔔 Notification sent", "clear_notifications": "🔔 Notifications cleared",
    "vpn_status": "🔒 VPN status", "vpn_connect": "🔒 VPN connecting...",
    "vpn_disconnect": "🔒 VPN disconnecting...",
    "help": "🤖 Available commands", "system_info": "💻 System info",
    "hardware_info": "🔧 Hardware info", "cpu_info": "🔧 CPU info",
    "gpu_info": "🔧 GPU info", "memory_info": "🔧 Memory info",
    "weather": "🌤 Weather", "public_ip": "🌐 Public IP",
    "math_eval": "🧮 Calculating...",
    "charmap": "📝 Character Map", "screenshot": "📸 Taking screenshot...",
    "show_desktop": "🖥 Showing desktop...", "minimize_all": "📉 Minimizing all...",
    "alt_tab": "🔄 Switching...", "window_manage": "🪟 Managing window...",
    "window_snap": "🪟 Snapping window...", "task_view": "📋 Task View",
    "virtual_desktop": "🖥 Virtual desktop",
    "switch_desktop": "🖥 Switching desktop...",
    "network_settings": "🌐 Network & Internet settings",
    "datetime_settings": "🕐 Date & Time settings",
    "personalization_settings": "🎨 Personalization settings",
    "apps_features": "📋 Apps & Features",
    "backup_settings": "💾 Backup settings",
    "troubleshoot_settings": "🔧 Troubleshoot settings",
    "security_settings": "🛡 Security settings",
    "sound_settings": "🔊 Sound settings",
    "storage_settings": "💾 Storage settings",
    "signin_options": "🔒 Sign-in options",
}

_ACTION_TIPS = {
    "lock": "Lock your PC", "sleep": "Put PC to sleep",
    "restart": "Restart PC", "shutdown": "Shutdown PC",
    "logoff": "Sign out", "hibernate": "Hibernate PC",
    "whoami": "Show current user", "battery_status": "Show battery level",
    "vol_up": "Increase volume", "vol_down": "Decrease volume",
    "vol_mute": "Mute/unmute", "vol_set": 'Set volume, e.g. "volume to 50"',
    "brightness_up": "Increase brightness", "brightness_down": "Decrease brightness",
    "night_light": "Toggle night light", "screenshot": "Take screenshot",
    "wifi_on": "Enable WiFi", "wifi_off": "Disable WiFi",
    "wifi_list": "Show WiFi networks", "scan_network": "Scan network devices",
    "wol": "Wake device via WoL", "ping": "Ping a device",
    "process_list": "List running processes", "kill": "Stop a process",
    "service_list": "Show Windows services", "clipboard_show": "Read clipboard",
    "timer": 'Set timer, e.g. "timer 5 minutes"',
    "search": "Search the web", "weather": "Check weather",
    "public_ip": "Show public IP", "system_info": "Show PC specs",
    "send_keys": "Type text into active window",
    "disk_cleanup": "Run Windows disk cleanup",
    "defender_scan": "Run Windows Defender scan",
}


# ── Optimized detector: keyword O(1) → regex O(n) ─────────────────

def detect_action(text: str) -> str | None:
    lower = text.lower().strip()

    # 1. Keyword lookup — sort by longest phrase first to avoid "time" matching "timer"
    for phrase, action in sorted(_KEYWORD_LOOKUP.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            if len(phrase) >= 3 or lower == phrase or lower.startswith(phrase):
                return action

    # 2. Specific regex patterns
    for pat, action in _ACTION_PATTERNS.items():
        m = re.match(pat, lower)
        if m:
            return action

    # 3. Broad fallback patterns
    for pat, action in _BROAD_PATTERNS:
        m = re.search(pat, lower)
        if m:
            return action

    return None


def extract_param(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


# ── Executor registry ──────────────────────────────────────────────

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


# ═══════════════════════════════════════════════════════════════════
#  ACTIONS — 180+ executors for total Windows control
# ═══════════════════════════════════════════════════════════════════

# ── System ─────────────────────────────────────────────────────────

@register("lock")
def _lock(_): _ps('rundll32.exe user32.dll,LockWorkStation'); return "Locked."

@register("sleep")
def _sleep(_): _ps('rundll32.exe powrprof.dll,SetSuspendState 0,1,0'); return "Sleeping..."

@register("hibernate")
def _hibernate(_): _ps('rundll32.exe powrprof.dll,SetSuspendState 1,0,0'); return "Hibernating..."

@register("restart")
def _restart(_): _ps('Restart-Computer -Force -Confirm:$false'); return "Restarting..."

@register("shutdown")
def _shutdown(_): _ps('Stop-Computer -Force -Confirm:$false'); return "Shutting down..."

@register("logoff")
def _logoff(_): _ps('(rundll32.exe user32.dll,LockWorkStation)'); return "Signing out..."

@register("whoami")
def _whoami(_):
    u = _ps('$e=[Environment]::UserName; $d=[Environment]::UserDomainName; "$d\\$e"')
    return f"Current user: {u}"

@register("switch_user")
def _switch_user(_):
    _ps('(New-Object -ComObject Shell.Application).WindowsSecurity()')
    return "Opening Windows Security..."

@register("winver")
def _winver(_):
    info = _ps('(Get-CimInstance Win32_OperatingSystem).Caption + " Build " + (Get-CimInstance Win32_OperatingSystem).BuildNumber')
    return f"Windows: {info}"

@register("os_info")
def _os_info(_):
    v = _ps('(Get-CimInstance Win32_OperatingSystem).Caption')
    b = _ps('(Get-CimInstance Win32_OperatingSystem).BuildNumber')
    a = _ps('(Get-CimInstance Win32_ComputerSystem).Manufacturer + " " + (Get-CimInstance Win32_ComputerSystem).Model')
    return f"OS: {v} (Build {b})\nModel: {a}"


# ── Power ──────────────────────────────────────────────────────────

@register("battery_status")
def _battery_status(_):
    b = _ps("$b=Get-CimInstance Win32_Battery; if($b){ '$($b.EstimatedChargeRemaining)% ($($b.BatteryStatus -replace 1,'Charging' -replace 2,'On AC'))' }else{ 'Desktop (no battery)' }")
    u = _ps("[math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours,1)")
    return f"Battery: {b}\nUptime: {u}h"

@register("battery_saver")
def _battery_saver(_):
    _ps('powercfg /setdcvalueindex SCHEME_CURRENT SUB_ENERGYSAVER ESBATTTHRESHOLD 1; powercfg /setactive SCHEME_CURRENT')
    return "Battery saver enabled."

@register("power_plan")
def _power_plan(_):
    p = _ps('(Get-CimInstance -Namespace root/cimv2/power Win32_PowerPlan -Filter "IsActive=true").ElementName')
    plans = _ps('(Get-CimInstance -Namespace root/cimv2/power Win32_PowerPlan).ElementName')
    return f"Active plan: {p}\nAvailable: {plans[:500]}"

@register("uptime")
def _uptime(_):
    u = _ps("[math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours,1)")
    d = _ps("(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('yyyy-MM-dd HH:mm')")
    return f"Uptime: {u}h (since {d})"

@register("last_boot")
def _last_boot(_):
    d = _ps("(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')")
    return f"Last boot: {d}"


# ── Volume / Audio ─────────────────────────────────────────────────

@register("vol_up")
def _vol_up(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); for($i=0;$i-lt3;$i++){$k.SendKeys([char]175)}')
    return "Volume up."

@register("vol_down")
def _vol_down(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); for($i=0;$i-lt3;$i++){$k.SendKeys([char]174)}')
    return "Volume down."

@register("vol_mute")
def _vol_mute(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys([char]173)')
    return "Toggled mute."

@register("vol_set")
def _vol_set(text):
    m = re.search(r"(\d+)", text)
    if not m: return "Specify a number (e.g., volume to 50)."
    lvl = min(100, max(0, int(m.group(1))))
    _ps(f'''
        $w=(New-Object -ComObject WScript.Shell);
        0..100|%{{$w.SendKeys([char]175)}};
        0..[math]::Round(100-{lvl}/100*100)|%{{$w.SendKeys([char]174)}}
    ''')
    return f"Volume set to {lvl}%."

@register("vol_level")
def _vol_level(_):
    l = _ps('Add-Type @""@; [Audio]::Volume')
    m = _ps('Add-Type @""@; [Audio]::Mute')
    return f"Volume: {l or 'unknown'}%{' (muted)' if m else ''}"

@register("mic_toggle")
def _mic_toggle(_):
    _ps('$d=Get-PnpDevice -FriendlyName "*microphone*" -ErrorAction SilentlyContinue | Select -First 1; if($d.Status -eq "OK"){$d|Disable-PnpDevice -Confirm:$false}else{$d|Enable-PnpDevice -Confirm:$false}')
    return "Microphone toggled."

@register("mic_status")
def _mic_status(_):
    s = _ps('(Get-PnpDevice -FriendlyName "*microphone*" -ErrorAction SilentlyContinue | Select -First 1).Status')
    return f"Microphone: {s or 'No mic found'}"

@register("audio_device")
def _audio_device(_):
    d = _ps('Get-AudioDevice -Playback -ErrorAction SilentlyContinue | Select-Object DeviceFriendlyName')
    return f"Audio devices: {d[:500] or 'None'}"

@register("speaker_test")
def _speaker_test(_):
    _ps('[System.Media.SystemSounds]::Asterisk.Play(); Start-Sleep 0.5; [System.Media.SystemSounds]::Exclamation.Play()')
    return "Playing test sounds..."

@register("vol_mixer")
def _vol_mixer(_):
    _ps('Start-Process "sndvol.exe"')
    return "Opening volume mixer..."


# ── Display / Screen ───────────────────────────────────────────────

@register("brightness_up")
def _brightness_up(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys([char]175); Start-Sleep 0.05; $k.SendKeys([char]175)')
    return "Brightness up."

@register("brightness_down")
def _brightness_down(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys([char]174); Start-Sleep 0.05; $k.SendKeys([char]174)')
    return "Brightness down."

@register("brightness_set")
def _brightness_set(text):
    m = re.search(r"(\d+)", text)
    if not m: return "Specify a number (e.g., brightness to 70)."
    lvl = min(100, max(0, int(m.group(1))))
    _ps(f'(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{lvl})')
    return f"Brightness set to {lvl}%."

@register("night_light")
def _night_light(_):
    _ps('$r=Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\Cache\\DefaultAccount\\*\\windows.data.bluelightreduction.bluelightreductionstate" -Name Data -ErrorAction SilentlyContinue; if($r){Set-ItemProperty -Path $r.PSPath -Name Data -Value $null}')
    return "Night light toggled."

@register("toggle_theme")
def _toggle_theme(_):
    _ps('$k=Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" -Name AppsUseLightTheme -ErrorAction SilentlyContinue; if($k.AppsUseLightTheme -eq 1){Set-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" AppsUseLightTheme 0}else{Set-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" AppsUseLightTheme 1}')
    return "Theme toggled."

@register("hdr_toggle")
def _hdr_toggle(_):
    _ps('Start-Process "ms-settings:display"')
    return "Opening HDR settings..."

@register("screen_resolution")
def _screen_resolution(_):
    r = _ps('(Get-CimInstance Win32_VideoController).CurrentHorizontalResolution.ToString()+"x"+(Get-CimInstance Win32_VideoController).CurrentVerticalResolution.ToString()')
    return f"Resolution: {r}"

@register("display_info")
def _display_info(_):
    d = _ps('Get-CimInstance Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate | Format-List | Out-String')
    night = _ps('(Get-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\Store\\Cache\\DefaultAccount\\*\\windows.data.bluelightreduction.bluelightreductionstate" -Name Data -ErrorAction SilentlyContinue).Data')
    return f"{d[:600]}\nNight light: {'on' if night else 'off'}"

@register("second_screen")
def _second_screen(text):
    t = text.lower()
    if "extend" in t: m = "extend"
    elif "duplicate" in t or "copy" in t: m = "duplicate"
    elif "second" in t or "only" in t: m = "second-only"
    elif "first" in t or "pc" in t: m = "first-only"
    else: m = "extend"
    _ps(f'DisplaySwitch /{m}')
    return f"Second screen: {m}"

@register("projector_mode")
def _projector_mode(_):
    _ps('DisplaySwitch /extend')
    return "Projector mode: extended."

@register("multi_monitor")
def _multi_monitor(_):
    m = _ps('(Get-CimInstance Win32_DesktopMonitor).Monitors.Count')
    return f"Monitors: {m or '1'}"

@register("calibrate_display")
def _calibrate_display(_):
    _ps('Start-Process "dccw.exe"')
    return "Opening Display Color Calibration..."

@register("color_profile")
def _color_profile(_):
    _ps('Start-Process "colorcpl.exe"')
    return "Opening Color Management..."

@register("refresh_rate")
def _refresh_rate(_):
    r = _ps('(Get-CimInstance Win32_VideoController).CurrentRefreshRate')
    return f"Refresh rate: {r}Hz"

@register("rotate_display")
def _rotate_display(_):
    _ps('Start-Process "ms-settings:display"')
    return "Opening display rotation settings..."


# ── WiFi / Network ─────────────────────────────────────────────────

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
    raw = _ps('(netsh wlan show networks) | Select-String "SSID" | %{ $_ -replace ".*:\\s*", "" }')
    nets = [s.strip() for s in raw.splitlines() if s.strip()]
    if not nets: return "No WiFi networks found."
    return "Available networks:\n" + "\n".join(f"  • {n}" for n in nets[:15])

@register("wifi_password")
def _wifi_password(_):
    ssid = _ps('(Get-NetConnectionProfile -ErrorAction SilentlyContinue).Name')
    if not ssid: return "Not connected to WiFi."
    pw = _ps(f'(netsh wlan show profile name="{ssid}" key=clear) | Select-String "Key Content" | %{{$_ -replace ".*:\\s*", ""}}')
    return f"Connected to: {ssid}\nPassword: {pw or 'password protected / stored in Windows'}"

@register("wifi_connect")
def _wifi_connect(text):
    ssid = extract_param(text, r"(?:connect|join)\s+to\s+(?:wifi|wi-fi|network)\s+(.+?)(?:\s+password\s+(.+?))?$")
    if not ssid: return "Which network?"
    pw = extract_param(text, r"password\s+(.+?)$")
    if pw:
        _ps(f'netsh wlan add profile filename="<profile>" 2>$null')
        _ps(f'netsh wlan connect name="{ssid}"')
    else:
        _ps(f'netsh wlan connect name="{ssid}" 2>$null')
    return f"Connecting to {ssid}..."

@register("wifi_disconnect")
def _wifi_disconnect(_): _ps('netsh wlan disconnect'); return "WiFi disconnected."

@register("wifi_forget")
def _wifi_forget(text):
    n = extract_param(text, r"forget\s+(?:wifi|network)\s+(.+?)$")
    if not n: return "Which network?"
    _ps(f'netsh wlan delete profile name="{n}"')
    return f"Forgot network '{n}'."

@register("hotspot_toggle")
def _hotspot_toggle(_):
    _ps('Start-Process "ms-settings:network-mobilehotspot"')
    return "Opening hotspot settings..."

@register("airplane_mode")
def _airplane_mode(_):
    _ps('Start-Process "ms-settings:network-airplanemode"')
    return "Opening airplane mode settings..."

@register("network_info")
def _network_info(_):
    ip = _ps("(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).IPAddress")
    gw = _ps("(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop")
    dns = _ps("(Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses")
    ssid = _ps("(Get-NetConnectionProfile -ErrorAction SilentlyContinue).Name")
    return f"IP: {ip}\nGateway: {gw}\nDNS: {dns}\nWiFi: {ssid}"

@register("network_adapters")
def _network_adapters(_):
    a = _ps("Get-NetAdapter -ErrorAction SilentlyContinue | Select-Object Name,Status,LinkSpeed | Format-Table -Auto | Out-String")
    return a[:500]

@register("ip_renew")
def _ip_renew(_):
    _ps('ipconfig /release; ipconfig /renew')
    return "IP address renewed."

@register("dns_flush")
def _dns_flush(_):
    _ps('ipconfig /flushdns')
    return "DNS cache flushed."

@register("proxy_status")
def _proxy_status(_):
    s = _ps("(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings').ProxyEnable")
    p = _ps("(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings').ProxyServer")
    return f"Proxy: {'enabled' if s == '1' else 'disabled'}, Server: {p or 'none'}"

@register("network_profile")
def _network_profile(text):
    t = extract_param(text, r"(?:set\s+)?(?:network\s+)?profile\s+(?:to\s+)?(public|private|domain)", re.IGNORECASE)
    if not t: return "Specify: public, private, or domain."
    _ps(f'Set-NetConnectionProfile -NetworkCategory {t[0].upper()+t[1:].lower()}')
    return f"Network profile set to {t}."

@register("network_discovery")
def _network_discovery(_):
    _ps('Set-NetFirewallRule -DisplayGroup "Network Discovery" -Enabled True')
    return "Network discovery enabled."


# ── Bluetooth ──────────────────────────────────────────────────────

@register("bt_on")
def _bt_on(_):
    _ps('(Get-PnpDevice -FriendlyName "*bluetooth*" -ErrorAction SilentlyContinue) | Enable-PnpDevice -Confirm:$false')
    return "Bluetooth enabled."

@register("bt_off")
def _bt_off(_):
    _ps('(Get-PnpDevice -FriendlyName "*bluetooth*" -ErrorAction SilentlyContinue) | Disable-PnpDevice -Confirm:$false')
    return "Bluetooth disabled."

@register("bt_devices")
def _bt_devices(_):
    d = _ps('Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Select-Object FriendlyName,Status | Format-Table -Auto | Out-String')
    return d[:500] or "No Bluetooth devices found."

@register("bt_pair")
def _bt_pair(text):
    d = extract_param(text, r"(?:pair|connect)\s+(?:bluetooth\s+)?(?:device\s+)?(.+?)$")
    if not d: return "Which device?"
    return f"Opening Bluetooth settings for pairing with {d}..."

@register("bt_unpair")
def _bt_unpair(text):
    d = extract_param(text, r"(?:unpair|remove|disconnect)\s+(?:bluetooth\s+)?(?:device\s+)?(.+?)$")
    if not d: return "Which device?"
    return f"Opening Bluetooth settings to remove {d}..."


# ── Network Device Control (ARP / WoL / Ping) ──────────────────────

@register("scan_network")
def _scan_network(_):
    subnet = _ps("(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).IPAddress")
    if not subnet: subnet = "192.168.1.1"
    base = ".".join(subnet.split(".")[:3])

    arp = _ps("arp -a")
    devices = []
    for line in (arp or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0].startswith(base):
            devices.append({"ip": parts[0], "mac": parts[1].replace("-", ":").upper()})

    if not devices:
        for i in [1, 254, 100, 101, 50, 150, 200]:
            _ps(f"ping -n 1 -w 200 {base}.{i}")
        arp = _ps("arp -a")
        for line in (arp or "").splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].startswith(base):
                devices.append({"ip": parts[0], "mac": parts[1].replace("-", ":").upper()})

    if not devices: return "No devices found."
    result = "Devices on network:\n"
    for d in devices[:20]:
        host = _ps(f"(Resolve-DnsName {d['ip']} -ErrorAction SilentlyContinue).NameHost")
        h = host.split(".")[0] if host else "unknown"
        result += f"  • {h} ({d['ip']}) — {d['mac']}\n"
    return result

@register("ping")
def _ping(text):
    target = extract_param(text, r"(?:ping|check)\s+(?:device\s+|host\s+)?(.+?)$")
    if not target: return "What should I ping?"
    r = _ps(f"ping -n 4 {target}")
    if "Reply from" in r: return f"{target} is online."
    return f"{target} did not respond."

@register("wol")
def _wol(text):
    device = extract_param(text, r"(?:wake|turn\s+on|power\s+on)\s+(?:up\s+)?(?:my\s+)?(?:device\s+)?(.+?)$")
    if not device: return "Which device?"

    mac = None
    arp = _ps("arp -a")
    for line in (arp or "").splitlines():
        if device.lower() in line.lower():
            parts = line.strip().split()
            if len(parts) >= 3:
                mac = parts[1].replace("-", ":").upper()
                break
    if not mac: return f"Could not find MAC for '{device}'. Scan network first."

    mac_clean = mac.replace(":", "").replace("-", "")
    if len(mac_clean) != 12: return f"Invalid MAC: {mac}"
    magic = "FF" * 6 + mac_clean * 16
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(bytes.fromhex(magic), ("255.255.255.255", 9))
        s.close()
        return f"Wake signal sent to {device} ({mac})."
    except Exception as e:
        return f"WoL failed: {e}"


# ── Processes ──────────────────────────────────────────────────────

@register("process_list")
def _process_list(_):
    p = _ps("Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 Name,Id,@{N='CPU(s)';E={[math]::Round($_.CPU,1)}},@{N='MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | Format-Table -Auto | Out-String")
    return f"Top processes:\n{p[:800]}"

@register("process_kill")
def _process_kill(text):
    t = extract_param(text, r"(?:kill|stop|end)\s+(?:process|task)\s+(.+?)$")
    if not t: return "Which process?"
    _ps(f'Stop-Process -Name "{t}" -Force -ErrorAction SilentlyContinue; if(-not $?){{Stop-Process -Id {t} -Force -ErrorAction SilentlyContinue}}')
    return f"Process '{t}' terminated."

@register("process_start")
def _process_start(text):
    t = extract_param(text, r"(?:start|run|launch)\s+(?:process|program|app)\s+(.+?)$")
    if not t: t = text.replace("start", "").strip()
    _ps(f'Start-Process "{t}" 2>$null; if(-not $?){{Start-Process "{t}.exe" 2>$null; if(-not $?){{return "$t not found"}}}}')
    return f"Starting {t}..."

@register("cpu_usage")
def _cpu_usage(_):
    c = _ps("(Get-CimInstance Win32_Processor).LoadPercentage")
    n = _ps("(Get-CimInstance Win32_Processor).Name")
    return f"CPU ({n}): {c}%"

@register("memory_usage")
def _memory_usage(_):
    t = _ps("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)")
    f = _ps("[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)")
    u = _ps("[math]::Round(((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory-(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1KB)/1GB,1)")
    return f"RAM: {u}GB / {t}GB ({f}MB free)"


# ── Services ───────────────────────────────────────────────────────

@register("service_list")
def _service_list(_):
    s = _ps("Get-Service | Sort-Object Status | Select-Object Name,DisplayName,Status -First 30 | Format-Table -Auto | Out-String")
    return f"Services:\n{s[:800]}"

@register("service_start")
def _service_start(text):
    t = extract_param(text, r"(?:start|restart)\s+(?:service|the\s+service)\s+(.+?)$")
    if not t: return "Which service?"
    _ps(f'Start-Service "{t}" -ErrorAction SilentlyContinue')
    return f"Starting {t}..."

@register("service_stop")
def _service_stop(text):
    t = extract_param(text, r"stop\s+(?:service|the\s+service)\s+(.+?)$")
    if not t: return "Which service?"
    _ps(f'Stop-Service "{t}" -ErrorAction SilentlyContinue')
    return f"Stopping {t}..."

@register("service_disable")
def _service_disable(text):
    t = extract_param(text, r"(?:disable|enable)\s+(?:service|the\s+service)\s+(.+?)$")
    if not t: return "Which service?"
    a = "Disabled" if "disable" in text.lower() else "Automatic"
    _ps(f'Set-Service "{t}" -StartupType {a} -ErrorAction SilentlyContinue')
    return f"{t}: {a}."

@register("service_status")
def _service_status(text):
    t = extract_param(text, r"service\s+(.+?)\s+(?:status|state)")
    if not t: return "Which service?"
    s = _ps(f'(Get-Service "{t}" -ErrorAction SilentlyContinue).Status')
    return f"Service '{t}': {s or 'not found'}"


# ── Startup Programs ───────────────────────────────────────────────

@register("startup_programs")
def _startup_programs(_):
    s = _ps("Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location | Format-Table -Auto | Out-String")
    return f"Startup programs:\n{s[:600] or 'None'}"
@register("taskmgr")
def _taskmgr(_): _ps('Start-Process "taskmgr.exe"'); return "Task Manager opened."


# ── Windows / Settings Panels ──────────────────────────────────────

@register("settings")
def _settings(_): _ps('Start-Process "ms-settings:"'); return "Settings opened."
@register("control_panel")
def _control_panel(_): _ps('Start-Process "control"'); return "Control Panel opened."
@register("device_manager")
def _device_manager(_): _ps('Start-Process "devmgmt.msc"'); return "Device Manager opened."
@register("reg_edit")
def _reg_edit(_): _ps('Start-Process "regedit.exe"'); return "Registry Editor opened."

@register("browser")
def _browser(_): _ps('Start-Process "https://google.com"'); return "Browser opened."

APP_MAP = {
    "email": "https://mail.google.com", "gmail": "https://mail.google.com",
    "mail": "https://mail.google.com", "outlook": "https://outlook.live.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com", "google drive": "https://drive.google.com",
    "cloud": "https://drive.google.com",
    "youtube": "https://youtube.com", "yt": "https://youtube.com",
    "github": "https://github.com", "repos": "https://github.com",
    "code": "https://github.com",
    "discord": "discord://", "chat": "discord://",
    "slack": "slack://", "teams": "https://teams.microsoft.com",
    "vscode": "code://",
    "terminal": "powershell.exe", "cmd": "cmd.exe", "powershell": "powershell.exe",
    "console": "powershell.exe",
    "calc": "calc.exe", "calculator": "calc.exe",
    "notepad": "notepad.exe", "text editor": "notepad.exe",
    "camera": "microsoft.windows.camera:", "webcam": "microsoft.windows.camera:",
    "snipping tool": "SnippingTool.exe", "snip": "SnippingTool.exe",
    "screenshot tool": "ms-screenclip:",
    "control panel": "control", "settings": "ms-settings:",
    "task manager": "taskmgr.exe", "taskmgr": "taskmgr.exe",
    "device manager": "devmgmt.msc", "registry": "regedit.exe",
    "registry editor": "regedit.exe", "regedit": "regedit.exe",
}

@register("email")
def _email(_): _ps('Start-Process "https://mail.google.com"'); return "Opening email..."
@register("calendar")
def _calendar(_): _ps('Start-Process "https://calendar.google.com"'); return "Opening calendar..."
@register("drive")
def _drive(_): _ps('Start-Process "https://drive.google.com"'); return "Opening Drive..."
@register("youtube")
def _youtube(_): _ps('Start-Process "https://youtube.com"'); return "Opening YouTube..."
@register("github")
def _github(_): _ps('Start-Process "https://github.com"'); return "Opening GitHub..."
@register("discord")
def _discord(_): _ps('Start-Process "discord://" 2>$null; if(-not$?){Start-Process "https://discord.com/app"}'); return "Opening Discord..."
@register("slack")
def _slack(_): _ps('Start-Process "slack://" 2>$null; if(-not$?){Start-Process "https://slack.com"}'); return "Opening Slack..."
@register("vscode")
def _vscode(_): _ps('Start-Process "code://" 2>$null; if(-not$?){Start-Process "C:\\Program Files\\Microsoft VS Code\\Code.exe" -ErrorAction SilentlyContinue; if(-not$?){Start-Process "https://code.visualstudio.com"}}'); return "Opening VS Code..."
@register("terminal")
def _terminal(_): _ps('Start-Process "powershell.exe"'); return "Terminal opened."
@register("calc")
def _calc(_): _ps('Start-Process "calc.exe"'); return "Calculator opened."
@register("notepad")
def _notepad(_): _ps('Start-Process "notepad.exe"'); return "Notepad opened."
@register("camera")
def _camera(_): _ps('Start-Process "microsoft.windows.camera:" 2>$null; if(-not$?){Start-Process "C:\\Windows\\System32\\Camera.exe" -ErrorAction SilentlyContinue}'); return "Opening Camera..."
@register("snipping_tool")
def _snipping_tool(_): _ps('Start-Process "SnippingTool.exe" 2>$null; if(-not$?){Start-Process "ms-screenclip:"}'); return "Snipping tool opened."

@register("open_app")
def _open_app(text):
    name = extract_param(text, r"open\s+(?:app\s+|the\s+)?(.+?)$")
    if not name: return "Which app?"
    # Check known apps first
    if name.lower() in APP_MAP:
        _ps(f'Start-Process "{APP_MAP[name.lower()]}"')
        return f"Opening {name}..."
    # Try as executable
    _ps(f'Start-Process "{name}" 2>$null; if(-not$?){{Start-Process "{name}.exe" 2>$null; if(-not$?){{return "Not found: {name}"}}}}')
    return f"Opening {name}..."


# ── Windows Update ─────────────────────────────────────────────────

@register("windows_update")
def _windows_update(_):
    _ps('Start-Process "ms-settings:windowsupdate"')
    return "Opening Windows Update..."
@register("windows_features")
def _windows_features(_):
    _ps('Start-Process "optionalfeatures"')
    return "Opening Windows Features..."


# ── Files / Folders ────────────────────────────────────────────────

@register("recent_files")
def _recent_files(_):
    r = _ps('Get-ChildItem "$env:USERPROFILE\\AppData\\Roaming\\Microsoft\\Windows\\Recent" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 15 -ExpandProperty Name')
    if not r: return "No recent files."
    return "Recent:\n" + "\n".join(f"  • {f}" for f in r.splitlines())

@register("open_downloads")
def _open_downloads(_): _ps('Start-Process "$env:USERPROFILE\\Downloads"'); return "Opening Downloads..."
@register("open_documents")
def _open_documents(_): _ps('Start-Process "$env:USERPROFILE\\Documents"'); return "Opening Documents..."
@register("open_desktop")
def _open_desktop(_): _ps('Start-Process "$env:USERPROFILE\\Desktop"'); return "Opening Desktop..."

@register("list_directory")
def _list_directory(text):
    p = extract_param(text, r"(?:list|show)\s+(?:files|contents)\s+in\s+(.+?)$")
    if not p: p = "."
    if not p.startswith("$") and not p.startswith("~"):
        p = f'"{p}"'
    r = _ps(f'Get-ChildItem {p} -ErrorAction SilentlyContinue | Select-Object Name | Format-Table -Auto | Out-String')
    return r[:500] or "Directory not found."

@register("open_directory")
def _open_directory(text):
    p = extract_param(text, r"(?:open|show)\s+(?:folder|directory)\s+(.+?)$")
    if not p: return "Which folder?"
    _ps(f'Start-Process "{p}"')
    return f"Opening {p}..."

@register("create_directory")
def _create_directory(text):
    p = extract_param(text, r"(?:create|make|new)\s+(?:folder|directory)\s+(.+?)$")
    if not p: return "Name?"
    _ps(f'New-Item -ItemType Directory -Path "{p}" -Force -ErrorAction SilentlyContinue')
    return f"Created folder '{p}'."

@register("create_file")
def _create_file(text):
    p = extract_param(text, r"(?:create|make|new)\s+file\s+(.+?)$")
    if not p: return "Name?"
    _ps(f'New-Item -ItemType File -Path "{p}" -Force -ErrorAction SilentlyContinue')
    return f"Created file '{p}'."

@register("delete_file")
def _delete_file(text):
    p = extract_param(text, r"(?:delete|remove|trash)\s+(?:file|folder)\s+(.+?)$")
    if not p: return "What to delete?"
    _ps(f'Remove-Item "{p}" -Recurse -Force -ErrorAction SilentlyContinue')
    return f"Deleted '{p}'."

@register("move_file")
def _move_file(text):
    m = re.search(r"(?:move|rename)\s+(.+?)\s+(?:to|as)\s+(.+?)$", text)
    if not m: return "Source and destination?"
    _ps(f'Move-Item "{m.group(1).strip()}" "{m.group(2).strip()}" -Force -ErrorAction SilentlyContinue')
    return f"Moved '{m.group(1).strip()}' to '{m.group(2).strip()}'."

@register("copy_file")
def _copy_file(text):
    m = re.search(r"(?:copy|duplicate)\s+(.+?)\s+(?:to|into)\s+(.+?)$", text)
    if not m: return "Source and destination?"
    _ps(f'Copy-Item "{m.group(1).strip()}" "{m.group(2).strip()}" -Recurse -Force -ErrorAction SilentlyContinue')
    return f"Copied to '{m.group(2).strip()}'."

@register("search_files")
def _search_files(text):
    q = extract_param(text, r"(?:find|search)\s+(?:my\s+)?(?:computer|files|documents)\s*(?:for\s+)?(.+?)$") or text
    r = _ps(f'Get-ChildItem "$env:USERPROFILE\\Desktop","$env:USERPROFILE\\Documents","$env:USERPROFILE\\Downloads" -Recurse -ErrorAction SilentlyContinue | Where-Object {{$_.Name -like "*{q}*"}} | Select-Object -First 10 -ExpandProperty Name')
    if not r: return f"No files matching '{q}'."
    return f"Found:\n" + "\n".join(f"  • {f}" for f in r.splitlines())

@register("file_search_content")
def _file_search_content(text):
    q = extract_param(text, r"(?:search|find)\s+(?:file\s+)?(?:containing|with|named)\s+(.+?)$")
    if not q: return "Search query?"
    r = _ps(f'Get-ChildItem "$env:USERPROFILE\\Documents" -Recurse -ErrorAction SilentlyContinue | Select-String -Pattern "{q}" -SimpleMatch | Select-Object -First 10 Path | Format-Table -Auto | Out-String')
    return r[:500] or f"No files containing '{q}' found."

@register("file_info")
def _file_info(text):
    p = extract_param(text, r"(?:info|details|properties)\s+(.+?)$")
    if not p: return "Which file?"
    r = _ps(f'Get-Item "{p}" -ErrorAction SilentlyContinue | Format-List * | Out-String')
    return r[:500] or "File not found."

@register("drive_list")
def _drive_list(_):
    d = _ps('Get-PSDrive -PSProvider FileSystem | Select-Object Name,Root,@{N="GB Free";E={[math]::Round($_.Free/1GB,1)}},@{N="GB Used";E={[math]::Round(($_.Used)/1GB,1)}} | Format-Table -Auto | Out-String')
    return d[:600]

@register("drive_usage")
def _drive_usage(_):
    d = _ps('Get-PSDrive -PSProvider FileSystem | Select-Object Name,Root,@{N="Free";E={[math]::Round($_.Free/1GB,1)+"GB"}} | Format-Table -Auto | Out-String')
    return d[:500]

@register("disk_cleanup")
def _disk_cleanup(_):
    _ps('Start-Process "cleanmgr.exe"')
    return "Opening Disk Cleanup..."

@register("trash")
def _trash(_):
    _ps('(New-Object -ComObject Shell.Application).Namespace(0x0a).Items() | ForEach-Object { $_.InvokeVerb("delete") }')
    return "Recycle bin emptied."

@register("recycle_list")
def _recycle_list(_):
    r = _ps('(New-Object -ComObject Shell.Application).Namespace(0x0a).Items() | Select-Object Name,Size | Format-Table -Auto | Out-String')
    return r[:500] or "Recycle bin is empty."

@register("recycle_restore")
def _recycle_restore(text):
    n = extract_param(text, r"restore\s+(?:from\s+)?(?:recycle\s+)?bin\s+(.+?)$")
    if not n: return "Which file?"
    return f"Opening recycle bin to restore '{n}'..."

@register("usb_eject")
def _usb_eject(_):
    _ps('$d=Get-WmiObject Win32_Volume | Where-Object {$_.DriveType -eq 2}; if($d){$d|ForEach-Object{$_.DriveLetter+":"}; "Ejecting..."}')
    return "USB devices ejected (check notification)."


# ── Clipboard ──────────────────────────────────────────────────────

@register("clipboard_show")
def _clipboard_show(_):
    c = _ps("Get-Clipboard")
    return f"Clipboard: {c[:500] or 'empty'}"

@register("clipboard_copy")
def _clipboard_copy(text):
    c = text.replace("copy", "").replace("clipboard", "").strip() or "test"
    _ps(f'Set-Clipboard -Value "{c[:100]}"')
    return f"Copied: {c[:50]}"

@register("clipboard_paste")
def _clipboard_paste(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^V")')
    return "Pasted."

@register("clipboard_clear")
def _clipboard_clear(_):
    _ps('Set-Clipboard -Value ""')
    return "Clipboard cleared."


# ── Media ──────────────────────────────────────────────────────────

@register("music")
def _music(_): _ps('Start-Process "spotify:" 2>$null; if(-not$?){Start-Process "https://music.youtube.com"}'); return "Opening music..."
@register("music_lofi")
def _music_lofi(_): _ps('Start-Process "https://www.youtube.com/results?search_query=lofi+study+beats"'); return "Lo-fi beats..."
@register("spotify")
def _spotify(_): _ps('Start-Process "spotify:" 2>$null; if(-not$?){Start-Process "https://open.spotify.com"}'); return "Opening Spotify..."
@register("media_next")
def _media_next(_): _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_NEXT}")'); return "Next track."
@register("media_prev")
def _media_prev(_): _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_PREV}")'); return "Previous track."
@register("media_pause")
def _media_pause(_): _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_STOP}")'); return "Paused."
@register("media_play")
def _media_play(_): _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("{MEDIA_PLAY}")'); return "Playing."
@register("current_song")
def _current_song(_):
    try:
        _ps('Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("^{F13}")')
        return "Sent media info request."
    except: return "Could not detect song."
@register("shazam")
def _shazam(_): _ps('Start-Process "https://www.shazam.com"'); return "Opening Shazam..."


# ── Search ─────────────────────────────────────────────────────────

@register("search")
def _search(text):
    q = (extract_param(text, r"(?:search|google|look\s+up)\s+(?:for\s+)?(.+?)$") or text).strip()
    _ps(f'Start-Process "https://google.com/search?q={_uq(q)}"')
    return f'Searching for "{q}"...'

@register("search_youtube")
def _search_youtube(text):
    q = (extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:youtube|yt)\s+(.+?)$") or text).strip()
    _ps(f'Start-Process "https://www.youtube.com/results?search_query={_uq(q)}"')
    return f'Searching YouTube for "{q}"...'

@register("search_wiki")
def _search_wiki(text):
    q = (extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:wikipedia|wiki)\s+(.+?)$") or text).strip()
    _ps(f'Start-Process "https://en.wikipedia.org/wiki/{_uq(q)}"')
    return f'Searching Wikipedia for "{q}"...'

@register("search_amazon")
def _search_amazon(text):
    q = (extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:amazon|shop)\s+(.+?)$") or text).strip()
    _ps(f'Start-Process "https://www.amazon.com/s?k={_uq(q)}"')
    return f'Searching Amazon for "{q}"...'

@register("search_news")
def _search_news(text):
    q = (extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:news|google\s+news)\s+(.+?)$") or text).strip()
    _ps(f'Start-Process "https://news.google.com/search?q={_uq(q)}"')
    return f'Searching news for "{q}"...'

@register("search_maps")
def _search_maps(text):
    q = (extract_param(text, r"(?:search|find)\s+(?:on\s+)?(?:maps|google\s+maps)\s+(.+?)$") or text).strip()
    _ps(f'Start-Process "https://www.google.com/maps/search/{_uq(q)}"')
    return f'Searching maps for "{q}"...'


# ── Browser ────────────────────────────────────────────────────────

@register("open_url")
def _open_url(text):
    url = extract_param(text, r"(?:open|go\s+to)\s+(?:url|website|page|link|site)\s+(.+?)$")
    if not url: return "Which URL?"
    if not url.startswith("http"): url = "https://" + url
    _ps(f'Start-Process "{url}"')
    return f"Opening {url[:50]}..."

@register("open_bookmarks")
def _open_bookmarks(_):
    _ps('Start-Process "chrome://bookmarks/"')
    return "Opening bookmarks..."

@register("open_history")
def _open_history(_):
    _ps('Start-Process "chrome://history/"')
    return "Opening history..."

@register("open_incognito")
def _open_incognito(_):
    _ps('Start-Process "chrome.exe" -ArgumentList "-incognito"')
    return "Opening incognito window..."

@register("new_tab")
def _new_tab(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^T")')
    return "New tab opened."


# ── Timer / Clock ──────────────────────────────────────────────────

@register("time")
def _time(_):
    now = datetime.now()
    return f"{now.strftime('%A, %B %d, %Y — %I:%M %p')}"

@register("timer")
def _timer(text):
    m = re.search(r"(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)", text, re.IGNORECASE)
    if not m: return "How long? (e.g., timer 5 minutes)"
    val, unit = int(m.group(1)), m.group(2).lower()[0]
    sec = val * (1 if unit == 's' else 60 if unit == 'm' else 3600)
    threading.Thread(target=lambda: (time.sleep(sec), _ps('[System.Media.SystemSounds]::Hand.Play()')), daemon=True).start()
    return f"Timer: {val}{'s' if unit=='s' else 'm' if unit=='m' else 'h'}."

@register("alarm")
def _alarm(_): return "Use Windows Alarms app or Cortana for alarms."

@register("timer_stop")
def _timer_stop(_): return "Timer stop not supported (native timer uses sleep)."

@register("timer_remaining")
def _timer_remaining(_): return "Timer remaining not tracked (native timer)."


# ── SendKeys / Keyboard ────────────────────────────────────────────

@register("send_keys")
def _send_keys(text):
    t = extract_param(text, r"type\s+(.+?)$") or extract_param(text, r"key\s+(.+?)$")
    if not t: return "What should I type?"
    _ps(f'$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("{t[:200]}")')
    return f"Typed: {t[:50]}"

@register("run_dialog")
def _run_dialog(text):
    t = extract_param(text, r"(?:run|execute|start|open)\s+(?:command|program|executable|app)\s+(.+?)$") or "cmd"
    _ps(f'Start-Process "cmd.exe" -ArgumentList "/c","{t}"')
    return f"Running: {t}..."

@register("osk")
def _osk(_): _ps('Start-Process "osk.exe"'); return "Opening on-screen keyboard..."


# ── Accessibility ──────────────────────────────────────────────────

@register("magnifier")
def _magnifier(_): _ps('Start-Process "magnify.exe"'); return "Opening Magnifier..."
@register("narrator")
def _narrator(_): _ps('Start-Process "narrator.exe"'); return "Opening Narrator..."
@register("high_contrast")
def _high_contrast(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("$^{PRTSC}")')
    return "High contrast toggled."
@register("sticky_keys")
def _sticky_keys(_): _ps('Start-Process "ms-settings:easeofaccess-keyboard"'); return "Opening Sticky Keys settings..."
@register("filter_keys")
def _filter_keys(_): _ps('Start-Process "ms-settings:easeofaccess-keyboard"'); return "Opening Filter Keys settings..."
@register("mouse_keys")
def _mouse_keys(_): _ps('Start-Process "ms-settings:easeofaccess-mouse"'); return "Opening Mouse Keys settings..."
@register("closed_captions")
def _closed_captions(_): _ps('Start-Process "ms-settings:easeofaccess-closedcaptioning"'); return "Opening caption settings..."


# ── Registry ───────────────────────────────────────────────────────

@register("reg_read")
def _reg_read(text):
    p = extract_param(text, r"reg\s+read\s+(.+?)$")
    if not p: return "Which registry path?"
    v = _ps(f'Get-ItemProperty -Path "{p}" -ErrorAction SilentlyContinue | Format-List | Out-String')
    return v[:500] or "Key not found."

@register("reg_write")
def _reg_write(text):
    m = re.search(r"reg\s+write\s+(.+?)\s*=\s*(.+?)$", text)
    if not m: return "Format: reg write PATH = VALUE"
    _ps(f'Set-ItemProperty -Path "{m.group(1).strip()}" -Name "(default)" -Value "{m.group(2).strip()}" -ErrorAction SilentlyContinue')
    return f"Registry written."


# ── Environment Variables ──────────────────────────────────────────

@register("env_list")
def _env_list(_):
    e = _ps('Get-ChildItem Env: | Sort-Object Name | Select-Object -First 25 | Format-Table -Auto | Out-String')
    return f"Environment:\n{e[:600]}"

@register("env_get")
def _env_get(text):
    v = extract_param(text, r"(?:get|show)\s+(?:env|environment)\s+variable\s+(.+?)$")
    if not v: return "Which variable?"
    val = _ps(f'$env:{v}')
    return f"{v}={val or 'not set'}"


# ── Scheduled Tasks ────────────────────────────────────────────────

@register("scheduler_tasks")
def _scheduler_tasks(_):
    t = _ps('Get-ScheduledTask | Select-Object TaskName,State | Sort-Object TaskName | Select-Object -First 25 | Format-Table -Auto | Out-String')
    return f"Scheduled tasks:\n{t[:600]}"

@register("scheduler_run")
def _scheduler_run(text):
    t = extract_param(text, r"run\s+(?:scheduled\s+)?task\s+(.+?)$")
    if not t: return "Which task?"
    _ps(f'Start-ScheduledTask -TaskPath "\\{t}" -ErrorAction SilentlyContinue')
    return f"Starting task {t}..."

@register("scheduler_status")
def _scheduler_status(text):
    t = extract_param(text, r"task\s+(.+?)\s+(?:status|state)")
    if not t: return "Which task?"
    s = _ps(f'(Get-ScheduledTask -TaskPath "\\{t}" -ErrorAction SilentlyContinue).State')
    return f"Task '{t}': {s or 'not found'}"


# ── Security / Firewall / Defender ─────────────────────────────────

@register("firewall_status")
def _firewall_status(_):
    d = _ps('Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table -Auto | Out-String')
    return d[:500]

@register("firewall_on")
def _firewall_on(_): _ps('Set-NetFirewallProfile -All -Enabled True'); return "Firewall enabled."
@register("firewall_off")
def _firewall_off(_): _ps('Set-NetFirewallProfile -All -Enabled False'); return "Firewall disabled."

@register("defender_status")
def _defender_status(_):
    s = _ps('Get-MpComputerStatus | Select-Object AMServiceEnabled,AntispywareEnabled,AntivirusEnabled,RealTimeProtectionEnabled | Format-List | Out-String')
    return f"Defender:\n{s[:400]}"

@register("defender_scan")
def _defender_scan(_):
    _ps('Start-MpScan -ScanType QuickScan')
    return "Defender quick scan started."

@register("bitlocker_status")
def _bitlocker_status(_):
    b = _ps('Get-BitLockerVolume -ErrorAction SilentlyContinue | Select-Object MountPoint,ProtectionStatus | Format-Table -Auto | Out-String')
    return b[:500] or "BitLocker not configured."

@register("uac_status")
def _uac_status(_):
    u = _ps('(Get-ItemProperty "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System").EnableLUA')
    return f"UAC: {'enabled' if u=='1' else 'disabled'}"

@register("quick_assist")
def _quick_assist(_): _ps('Start-Process "ms-quickassist:"'); return "Opening Quick Assist..."
@register("remote_desktop")
def _remote_desktop(_): _ps('Start-Process "mstsc.exe"'); return "Opening Remote Desktop..."


# ── Notifications ──────────────────────────────────────────────────

@register("send_notification")
def _send_notification(text):
    msg = extract_param(text, r"(?:send|show)\s+(?:a\s+)?(?:notification|toast|alert|message)\s+(.+?)$")
    if not msg: msg = "Hello from Jason!"
    _ps(f'''
        $t=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime];
        $d=New-Object Windows.Data.Xml.Dom.XmlDocument;
        $d.LoadXml("<toast><visual><binding template='ToastText01'><text id='1'>{msg}</text></binding></visual></toast>");
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Jason").Show($d)
    ''')
    return f"Notification sent."

@register("clear_notifications")
def _clear_notifications(_):
    _ps('Start-Process "ms-settings:notifications"')
    return "Opening notification settings..."


# ── VPN ────────────────────────────────────────────────────────────

@register("vpn_status")
def _vpn_status(_):
    v = _ps('Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object Name,ServerAddress,ConnectionStatus | Format-List | Out-String')
    return v[:500] or "No VPN connections configured."

@register("vpn_connect")
def _vpn_connect(_):
    _ps('Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Name | %{rasdial $_}')
    return "Connecting VPN..."

@register("vpn_disconnect")
def _vpn_disconnect(_):
    _ps('Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Name | %{rasdial $_ /d}')
    return "Disconnecting VPN..."


# ── Window Management ──────────────────────────────────────────────

@register("show_desktop")
def _show_desktop(_):
    _ps('(New-Object -ComObject Shell.Application).ToggleDesktop()')
    return "Showing desktop."

@register("minimize_all")
def _minimize_all(_):
    _ps('(New-Object -ComObject Shell.Application).MinimizeAll()')
    return "Minimized all."

@register("alt_tab")
def _alt_tab(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^{TAB}")')
    return "Switched window."

@register("window_manage")
def _window_manage(text):
    a = "minimize" if "min" in text else "maximize" if "max" in text else "restore" if "restore" in text else "close"
    k = {"minimize": "{ESC}", "maximize": "{UP}", "restore": "{DOWN}", "close": "{F4}"}
    _ps(f'$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("%{k[a]}")')
    return f"Window {a}d."

@register("window_snap")
def _window_snap(text):
    d = "right" if "right" in text else "left" if "left" in text else "top" if "top" in text else "bottom"
    keys = {"left": "({LEFT})", "right": "({RIGHT})", "top": "({UP})", "bottom": "({DOWN})"}
    _ps(f'$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("%{keys[d]}")')
    return f"Snapped {d}."

@register("task_view")
def _task_view(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^{TAB}")')
    return "Task View."

@register("virtual_desktop")
def _virtual_desktop(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^{F4}")')
    return "New desktop created."

@register("switch_desktop")
def _switch_desktop(_):
    _ps('$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("^{TAB}")')
    return "Switching desktop..."


# ── Settings Panels ────────────────────────────────────────────────

@register("network_settings")
def _network_settings(_): _ps('Start-Process "ms-settings:network"'); return "Opening network settings..."
@register("datetime_settings")
def _datetime_settings(_): _ps('Start-Process "ms-settings:dateandtime"'); return "Opening date/time settings..."
@register("personalization_settings")
def _personalization_settings(_): _ps('Start-Process "ms-settings:personalization"'); return "Opening personalization..."
@register("apps_features")
def _apps_features(_): _ps('Start-Process "ms-settings:appsfeatures"'); return "Opening apps & features..."
@register("backup_settings")
def _backup_settings(_): _ps('Start-Process "ms-settings:backup"'); return "Opening backup settings..."
@register("troubleshoot_settings")
def _troubleshoot_settings(_): _ps('Start-Process "ms-settings:troubleshoot"'); return "Opening troubleshoot settings..."
@register("security_settings")
def _security_settings(_): _ps('Start-Process "windowsdefender:"'); return "Opening Windows Security..."
@register("sound_settings")
def _sound_settings(_): _ps('Start-Process "ms-settings:sound"'); return "Opening sound settings..."
@register("storage_settings")
def _storage_settings(_): _ps('Start-Process "ms-settings:storagesense"'); return "Opening storage settings..."
@register("signin_options")
def _signin_options(_): _ps('Start-Process "ms-settings:signinoptions"'); return "Opening sign-in options..."


# ── System Info ────────────────────────────────────────────────────

@register("help")
def _help(_):
    cats = {
        "System": ["lock","sleep","restart","shutdown","battery_status","uptime"],
        "Audio": ["vol_up","vol_down","vol_mute","vol_set","mic_toggle"],
        "Display": ["brightness_up","brightness_down","night_light","toggle_theme"],
        "Network": ["wifi_on","wifi_off","wifi_list","scan_network","network_info"],
        "Bluetooth": ["bt_on","bt_off","bt_devices"],
        "Apps": ["browser","notepad","calc","settings","terminal","vscode"],
        "Processes": ["process_list","service_list","cpu_usage","memory_usage"],
        "Files": ["recent_files","open_downloads","search_files","trash","drive_usage"],
        "Media": ["media_next","media_prev","media_play","media_pause","spotify"],
        "Search": ["search","search_youtube","search_wiki","weather"],
        "Misc": ["time","timer","screenshot","clipboard_show","system_info"],
    }
    text = "I can control 180+ things on your PC. Categories:\n"
    for cat, actions in cats.items():
        text += f"  {cat}: {', '.join(actions)}\n"
    text += "\nTry: 'what can you control?' or just ask for anything!"
    return text

@register("system_info")
def _system_info(_):
    results = ps_batch([
        "(Get-CimInstance Win32_OperatingSystem).Caption",
        "(Get-CimInstance Win32_ComputerSystem).Manufacturer + ' ' + (Get-CimInstance Win32_ComputerSystem).Model",
        "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)",
        "(Get-CimInstance Win32_Processor).Name",
        "(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors",
    ])
    return f"OS: {results[0]}\nModel: {results[1]}\nRAM: {results[2]}GB\nCPU: {results[3]} ({results[4]} threads)"

@register("hardware_info")
def _hardware_info(_):
    results = ps_batch([
        "(Get-CimInstance Win32_Processor).Name",
        "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)",
        "(Get-CimInstance Win32_VideoController).Name",
        "(Get-CimInstance Win32_DiskDrive | Select-Object -First 1).Model",
    ])
    return f"CPU: {results[0]}\nRAM: {results[1]}GB\nGPU: {results[2]}\nDisk: {results[3]}"

@register("cpu_info")
def _cpu_info(_):
    r = _ps("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | Format-List | Out-String")
    return r[:400]

@register("gpu_info")
def _gpu_info(_):
    r = _ps("Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,CurrentHorizontalResolution,CurrentVerticalResolution | Format-List | Out-String")
    return r[:400]

@register("memory_info")
def _memory_info(_):
    r = _ps("Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer,Capacity,ConfiguredClockSpeed | Format-Table -Auto | Out-String")
    total = _ps("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)")
    return f"Total: {total}GB\n{r[:400]}"


# ── Misc ───────────────────────────────────────────────────────────

@register("weather")
def _weather(_):
    _ps('Start-Process "https://www.google.com/search?q=weather"')
    return "Checking weather..."

@register("public_ip")
def _public_ip(_):
    ip = _ps("(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing -TimeoutSec 5).Content")
    return f"Public IP: {ip or 'Could not determine'}"

@register("math_eval")
def _math_eval(text):
    expr = extract_param(text, r"(?:math|calculate|eval)\s+(.+?)$")
    if not expr: return "Expression?"
    try:
        r = _ps(f'Invoke-Expression "{expr}"')
        return f"{expr} = {r}"
    except Exception as e:
        return f"Error: {e}"

@register("charmap")
def _charmap(_): _ps('Start-Process "charmap.exe"'); return "Opening Character Map..."

@register("screenshot")
def _screenshot(_):
    path = os.path.expanduser("~/Desktop/screenshot.png")
    _ps(f'''
        Add-Type -AssemblyName System.Windows.Forms;
        $b=[System.Drawing.Bitmap]::new([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,
           [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height);
        $g=[System.Drawing.Graphics]::FromImage($b);
        $g.CopyFromScreen(0,0,0,0,$b.Size);
        $b.Save("{path}"); $g.Dispose(); $b.Dispose()
    ''')
    return f"Screenshot saved to Desktop."


# ── Public API ─────────────────────────────────────────────────────

def get_all_actions() -> dict:
    return {k: {"label": _ACTION_LABELS.get(k, k), "tip": _ACTION_TIPS.get(k, "")} for k in sorted(_EXECUTORS.keys())}
