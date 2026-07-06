"""Universal automation engine — controls anything & everything on Windows via voice."""

import re, os, socket, struct, sys, threading, time, json
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
    # Autonomous / Complex
    "read file": "read_file", "read the file": "read_file",
    "write file": "write_file", "create file": "write_file", "save file": "write_file",
    "list directory": "list_dir", "list files": "list_dir", "show files": "list_dir",
    "run python": "run_python", "execute python": "run_python",
    "run shell": "run_shell", "run command": "run_shell", "execute command": "run_shell",
    "run code": "run_python",
    "open app": "open_app", "launch app": "open_app", "start app": "open_app",
    "go to": "open_app", "navigate to": "open_app", "browse to": "open_app",
    "research": "fetch_search", "investigate": "fetch_search",
    "scrape": "fetch_search", "read the web": "fetch_search",
    "fetch": "fetch_search",
    # Network & Smart Home
    "scan network": "network_scan_deep", "deep scan": "network_scan_deep",
    "scan my network": "network_scan_deep", "network scan": "network_scan_deep",
    "scan all devices": "network_scan_deep", "find all devices": "network_scan_deep",
    "scan wifi": "network_scan_deep", "what devices": "network_scan_deep",
    "what's on my network": "network_scan_deep", "scan everything": "network_scan_deep",
    "quick scan": "network_scan_quick", "arp scan": "network_scan_quick",
    "who is on the network": "network_scan_quick",
    "what devices": "network_scan_quick",
    "wake": "wake_on_lan", "wake up": "wake_on_lan", "wol": "wake_on_lan",
    "wake on lan": "wake_on_lan",
    "smart home": "smart_home_discover", "smart devices": "smart_home_discover",
    "discover devices": "smart_home_discover",
    "turn on": "smart_home_control", "turn off": "smart_home_control",
    "toggle": "smart_home_control", "lights": "smart_home_control",
    "light on": "smart_home_control", "light off": "smart_home_control",
    "set credentials": "set_device_credentials", "set tapo credentials": "set_device_credentials",
    "device credentials": "set_device_credentials", "tapo login": "set_device_credentials",
    "alexa": "alexa_speak", "echo": "alexa_speak", "alexa speak": "alexa_speak",
    "alexa say": "alexa_speak", "alexa announce": "alexa_speak",
    "alexa play": "alexa_play", "alexa pause": "alexa_pause", "alexa stop": "alexa_stop",
    "alexa next": "alexa_next", "alexa previous": "alexa_prev",
    "alexa volume": "alexa_volume", "alexa discover": "alexa_discover",
    "find echo": "alexa_discover", "find alexa": "alexa_discover",
    "alexa timer": "alexa_timer", "alexa routine": "alexa_routine",
    "alexa dnd": "alexa_dnd", "alexa do not disturb": "alexa_dnd",
    "camera": "camera_snap", "take a photo": "camera_snap",
    "take photo": "camera_snap", "snap": "camera_snap",
    "notify phone": "phone_notify", "push notification": "phone_notify",
    "send notification": "phone_notify", "text me": "phone_notify",
    "who is online": "who_is_online", "network users": "who_is_online",
    "system load": "system_load", "system status": "system_load",
    "load": "system_load",
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
    "whoami": "whoami",

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

    # Browser (keyword matching too greedy — simple open commands use _ACTION_PATTERNS instead)
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
    "installed apps": "app_list", "installed programs": "app_list",
    "list apps": "app_list", "list programs": "app_list", "list software": "app_list",
    "show apps": "app_list", "show programs": "app_list",
    "uninstall": "app_uninstall", "remove program": "app_uninstall",
    "force quit": "app_quit", "close app": "app_quit",
    "running apps": "app_running", "open windows": "app_running",
    "which apps are running": "app_running", "what is running": "app_running",
    "what apps are open": "app_running", "what programs are open": "app_running",
    "deep scan": "net_scan_deep", "full network scan": "net_scan_deep",
    "scan all devices": "net_scan_deep", "port scan": "net_port_scan",
    "open ports": "net_port_scan",
    "network shares": "net_shares", "shared folders": "net_shares",
    "device info": "net_device_info", "device details": "net_device_info",
    "scan my computer": "device_scan",
    "scan my device": "device_scan",
    "scan my system": "device_scan",
    "scan my laptop": "device_scan",
    "scan my pc": "device_scan",
    "device scan": "device_scan",
    "full scan": "device_scan",
    "profile my computer": "device_scan",
    "profile my device": "device_scan",
    "free up memory": "memory_cleanup",
    "free up ram": "memory_cleanup",
    "clean up memory": "memory_cleanup",
    "clean up ram": "memory_cleanup",
    "memory is full": "memory_cleanup",
    "memory too high": "memory_cleanup",
    "ram is full": "memory_cleanup",
    "ram too high": "memory_cleanup",
    "low on memory": "memory_cleanup",
    "out of memory": "memory_cleanup",
    "close unnecessary apps": "memory_cleanup",
    "close unused apps": "memory_cleanup",
    "reduce memory usage": "memory_cleanup",
    "reduce ram usage": "memory_cleanup",
    "too many apps running": "memory_cleanup",
    "too many programs running": "memory_cleanup",
    "too many processes running": "memory_cleanup",
    "why is my computer so slow": "memory_cleanup",
    "computer is very slow": "memory_cleanup",
    "pc is lagging": "memory_cleanup",
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

    # Real-world task keywords
    "flight": "search_flights", "flights": "search_flights", "fly": "search_flights", "travel": "search_flights",
    "hotel": "search_hotels", "hotels": "search_hotels", "booking": "search_hotels", "stay": "search_hotels",
    "accommodation": "search_hotels", "vacation": "search_flights", "holiday": "search_flights",
    "calendar": "calendar_events", "schedule": "calendar_events", "appointment": "calendar_events",
    "event": "calendar_events", "meeting": "calendar_events", "cal": "calendar_events",
    "onenote": "onenote_tasks", "notes": "onenote_tasks", "notebook": "onenote_tasks",
    "arbitrage": "arbitrage_check", "deal": "compare_prices", "cheap": "compare_prices",
    "price": "compare_prices", "compare": "compare_prices", "discount": "compare_prices",
    "teams": "teams_status", "microsoft teams": "teams_status",
    "my assignments": "teams_assignments", "teams assignments": "teams_assignments",
    "remaining assignments": "teams_assignments", "due assignments": "teams_assignments",
    "assignments on teams": "teams_assignments", "teams homework": "teams_assignments",
    "assignments on microsoft teams": "teams_assignments",

    # WhatsApp Web
    "whatsapp": "whatsapp_open", "web whatsapp": "whatsapp_open", "open whatsapp": "whatsapp_open",
    "whatsapp messages": "whatsapp_read", "read whatsapp": "whatsapp_read",
    "check whatsapp": "whatsapp_unread", "unread messages": "whatsapp_unread",
    "send whatsapp": "whatsapp_send", "whatsapp message": "whatsapp_send",
    "schedule whatsapp": "whatsapp_schedule", "whatsapp later": "whatsapp_schedule",
    "sms from": "whatsapp_read", "message from": "whatsapp_read",
    "my sister": "whatsapp_read", "messages from": "whatsapp_read",
    "skyscanner": "search_flights", "kayak": "search_flights",

    # Computer use agent
    "computer use": "ai_computer_task", "computer": "ai_computer_task",
    "control": "ai_computer_task", "automate": "ai_computer_task",
    "screen": "screen_analyze", "what's on screen": "screen_analyze",
    "what do you see": "screen_analyze", "look at screen": "screen_analyze",

    # UI Automation
    "click there": "ui_click", "click at": "ui_click", "click on": "ui_click_text",
    "tap that": "ui_click", "tap on": "ui_click_text", "press that": "ui_click",
    "type this": "ui_type", "type text": "ui_type", "enter text": "ui_type",
    "keyboard": "ui_type", "keystroke": "ui_type",
    "handwrite": "ui_handwrite", "hand writing": "ui_handwrite",
    "handwrite this": "ui_handwrite", "write naturally": "ui_handwrite",
    "drag mouse": "ui_drag", "drag from": "ui_drag",
    "what's on screen": "ui_get_text", "what do you see on screen": "ui_get_text",
    "read screen": "ui_get_text", "screen text": "ui_get_text",
    "find text": "ui_find", "locate text": "ui_find", "find on screen": "ui_find",
    "app running": "ui_app_running", "activate app": "ui_activate_app",
    "bring app": "ui_activate_app", "focus app": "ui_activate_app",
    "screenshot ui": "ui_screenshot", "capture screen": "ui_screenshot",

    # Phone Bridge
    "read my texts": "phone_read_sms", "read my sms": "phone_read_sms",
    "show texts": "phone_read_sms", "read messages": "phone_read_sms",
    "check messages": "phone_read_sms", "any new messages": "phone_read_sms",
    "phone notifications": "phone_get_notifications", "read notifications": "phone_get_notifications",
    "check notifications": "phone_get_notifications",
    "call log": "phone_call_log", "recent calls": "phone_call_log",
    "phone battery": "phone_battery", "phone charge": "phone_battery",
    "connect phone": "phone_adb_connect", "adb connect": "phone_adb_connect",
    "phone contacts": "phone_contacts", "my contacts": "phone_contacts",
    "phone location": "phone_location", "where is my phone": "phone_location",
    "find my phone": "phone_location",

    # Home Assistant
    "home assistant": "ha_status", "ha status": "ha_status",
    "smart home status": "ha_status",
    "discover ha": "ha_discover", "find home assistant": "ha_discover",
    "ha sensors": "ha_sensors", "read sensors": "ha_sensors",
    "turn on": "smart_home_control", "turn off": "smart_home_control",
    "toggle light": "smart_home_control", "dim light": "smart_home_control",

    # Cognitive Surveillance
    "scan environment": "cognitive_scan", "survey environment": "cognitive_scan",
    "what's happening": "cognitive_scan", "status report": "cognitive_scan",
    "insight": "cognitive_insight", "analyze environment": "cognitive_insight",
    "cognitive insight": "cognitive_insight",
    "monitor environment": "cognitive_monitor", "start monitoring": "cognitive_monitor",
    "stop monitoring": "cognitive_monitor",
    "alert me": "cognitive_alert", "set alert": "cognitive_alert",
    "warn me": "cognitive_alert",

    # Persistent Notifications
    "remind me": "notify_persistent", "set a reminder": "notify_persistent",
    "remind me to": "notify_persistent", "don't forget": "notify_persistent",
    "persistent notification": "notify_persistent", "pop up": "notify_persistent",
    "notification center": "notify_center", "center notification": "notify_center",
    "show notification": "notify_persistent", "sticky note": "notify_persistent",
    "sticky notification": "notify_persistent",

    # Network scanning
    "network scan": "network_scan_deep", "deep scan": "network_scan_deep",
    "scan network": "network_scan_deep", "scan my network": "network_scan_deep",
    "quick scan": "network_scan_quick", "arp scan": "network_scan_quick",
    "who is on the network": "network_scan_quick",
    "what devices": "network_scan_quick",
}

# Keyword phrase → action ID lookup (longest-first for specificity)
# Complex multi-step queries fall through to action-verb fallback → ai_computer_task
# _route_action() in entity_engine.py handles the fallback routing
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
    r"^(?:scan|inspect|profile|analyze)\s+(?:my\s+)?(?:computer|pc|system|device|machine|laptop|workstation)": "device_scan",
    r"^(?:full|deep)\s+(?:scan|profile|inspect)\s+(?:of\s+)?(?:my\s+)?(?:computer|pc|system|device)": "device_scan",

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
    r"^(?:free|clean|clear|reduce|lower)\s+(?:up\s+)?(?:memory|ram)": "memory_cleanup",
    r"^(?:memory|ram)\s+(?:is\s+)?(?:full|high|low|critical|maxed)": "memory_cleanup",
    r"^(?:close|kill|stop)\s+(?:unnecessary|unused|extra|all)\s+(?:apps|programs|processes|tasks)": "memory_cleanup",
    r"^(?:too\s+many\s+(?:apps|programs|processes|tasks)\s+(?:running|open))": "memory_cleanup",
    r"^(?:why\s+(?:is\s+)?(?:my\s+)?(?:computer|pc|laptop)\s+(?:so\s+)?(?:slow|laggy))": "memory_cleanup",
    r"^(?:speed\s+up|optimize|boost)\s+(?:my\s+)?(?:computer|pc|laptop|system)": "memory_cleanup",

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
    r"^(?:list|show|find|what)\s+(?:all\s+)?(?:installed\s+)?(?:apps|programs|software)": "app_list",
    r"^(?:list|show)\s+(?:all\s+)?(?:installed\s+)?(?:apps|programs|software)\s+(?:matching|like|for|named)\s+(.+?)$": "app_list",
    r"^(?:app|program|software)\s+(?:info|details|about)\s+(.+?)$": "app_info",
    r"^info\s+(?:about|on|for)\s+(?:app|program|software)\s+(.+?)$": "app_info",
    r"^(?:uninstall|remove)\s+(?:app|program|software)\s+(.+?)$": "app_uninstall",
    r"^(?:quit|close|exit|kill|stop)\s+(?:app|program)\s+(.+?)$": "app_quit",
    r"^force\s+(?:quit|close)\s+(.+?)$": "app_quit",
    r"^(?:list|show)\s+(?:running|open)\s+(?:apps|programs|windows|tasks)": "app_running",
    r"^(?:what|which)\s+(?:apps|programs)\s+(?:are\s+)?(?:running|open)": "app_running",
    r"^open\s+(?:the\s+)?(?:notepad|text\s+editor)": "notepad",
    r"^open\s+(?:the\s+)?(?:camera|webcam)": "camera",
    r"^open\s+(?:the\s+)?(?:snipping\s+tool|snip|screenshot\s+tool)": "snipping_tool",
    r"^open\s+(?:app\s+|the\s+)?(.+?)$": "open_app",
    r"^(?:go\s+to|launch|start)\s+(?:the\s+|app\s+)?(.+?)$": "open_app",

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
    r"^(?:deep\s+)?(?:scan|list|find)\s+(?:all\s+)?(?:network\s+)?(?:devices|hosts)\s+(?:in\s+)?(?:detail|deep|full)": "net_scan_deep",
    r"^(?:scan|check|list)\s+(?:open\s+)?ports\s+(?:on|of|for)\s+(.+?)$": "net_port_scan",
    r"^(?:network\s+)?(?:shares|shared\s+(?:folders|drives))": "net_shares",
    r"^(?:device|network\s+device)\s+(?:info|details|about)\s+(.+?)$": "net_device_info",
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
    (r"^(?:(?:open|launch|start)\s+(?:the\s+)?)?(?:google\s+|microsoft\s+)?(?:browser|chrome|firefox|edge)\s*(?:please)?$", "browser"),
    (r"(?:list|show)\s+(?:running\s+)?(?:processes|tasks|apps)", "process_list"),
    (r"(?:system|pc|computer)\s+(?:specs|info|details)", "system_info"),
    (r"(?:cpu|processor)\s+(?:usage|info|details)", "cpu_usage"),
    (r"(?:ram|memory)\s+(?:usage|info|details)", "memory_usage"),
    (r"(?:gpu|graphics|video)\s+(?:info|details|usage)", "gpu_info"),
    (r"(?:weather|temperature|outside|forecast)\s*(?:today|now|outside)?", "weather"),
    (r"(?:what\s+)?(?:external|public|my)\s+ip", "public_ip"),
    (    r"(?:windows\s+)?(?:update|check\s+for\s+updates)", "windows_update"),

    # Real-world task patterns
    (r"(?:search|find|look|book)\s+(?:for\s+)?(?:flights?|airfare|plane)\s+(?:to|from|in)\s+(.+)", "search_flights"),
    (r"(?:book|plan|organize)\s+(?:a\s+)?(?:holiday|vacation|trip|travel)\s+(?:to|in|for)\s+(.+)", "search_flights"),
    (r"(?:search|find|look|book)\s+(?:for\s+)?(?:hotels?|accommodation|stay|room)\s+(?:in|at|near)\s+(.+)", "search_hotels"),
    (r"(?:compare|find\s+cheap|best\s+price|price\s+compare)\s+(?:for\s+)?(.+)", "compare_prices"),
    (r"(?:check|find|look)\s+(?:for\s+)?(?:arbitrage|deal|price\s+gap)\s+(?:in\s+|for\s+)?(.+)", "arbitrage_check"),
    (r"(?:show|list|check|read)\s+(?:my\s+)?(?:calendar|schedule|events?|appointments?|meetings?)", "calendar_events"),
    (r"(?:add|create|schedule)\s+(?:a\s+)?(?:calendar\s+)?(?:event|meeting|appointment)", "calendar_add"),
    (r"(?:show|list|open)\s+(?:my\s+)?(?:onenote|notes|notebooks?)", "onenote_tasks"),
    (r"(?:add|write|create)\s+(?:a\s+)?(?:note|page)\s+(?:to|in)\s+(?:onenote|notes)", "onenote_add_note"),
    (r"(?:open|launch|start)\s+(?:microsoft\s+)?(?:teams|ms\s+teams)", "teams_status"),
    (r"(?:screenshot|capture)\s+(?:the\s+)?(?:page|website|url|browser|tab|screen)", "browser_tab_screenshot"),
    (r"(?:my\s+)?(?:remaining|due|pending|upcoming)\s+(?:assignments?|homework|tasks|work)\s*(?:\S+\s*){0,5}?(?:microsoft\s+)?(?:teams|ms\s+teams)?", "teams_assignments"),
    (r"(?:what|show|list|tell|find|get|check)\s+(?:my\s+)?(?:assignments?|homework|tasks|work)\s*(?:\S+\s*){0,5}?(?:microsoft\s+)?(?:teams|ms\s+teams)?", "teams_assignments"),

    # Computer use / AI vision patterns
    (r"(?:use|let|make|have|tell|get)\s+(?:the\s+)?(?:ai|computer|agent)\s+(?:to\s+)?(.+)", "ai_computer_task"),
    (r"(?:do|complete|finish|handle|take\s+care\s+of)\s+(?:my\s+)?(.+?\b(?:homework|assignment|task|work|note|form|document|report)s?)", "ai_computer_task"),
    (r"(?:look\s+at|analyze|describe|what'?s\s+on|read)\s+(?:the\s+)?(?:screen|display|desktop)", "screen_analyze"),
    (r"(?:ai|computer|agent)\s+(?:see|look|watch|control|manage|do)\s+(?:the\s+)?(?:screen|computer|pc)", "ai_computer_task"),

    # WhatsApp Web automation
    (r"(?:open|launch|start)\s+(?:web\s+)?(?:whatsapp|wa)", "whatsapp_open"),
    (r"(?:read|check|show|get|list|view)\s+(?:my\s+)?(?:whatsapp|wa)\s*(?:messages?)?", "whatsapp_read"),
    (r"(?:what'?s\s+new|unread|new\s+messages?)\s+(?:on\s+)?(?:whatsapp|wa)", "whatsapp_unread"),
    (r"(?:send|post)\s+(?:a\s+)?(?:whatsapp|wa)\s+(?:message\s+)?(?:to\s+)?(.+?)(?:\s+(?:saying|that|the|with|about))?\s*(.+)?", "whatsapp_send"),
    (r"(?:schedule|plan|set)\s+(?:a\s+)?(?:whatsapp|wa)\s*(?:message)?\s*(?:to\s+)?(.+?)(?:\s+(?:saying|that|about|with))?\s*(.+?)(?:\s+(?:at|for|in)\s+(.+))?", "whatsapp_schedule"),
    (r"(?:message|msg|text|sms)\s+(?:from|by)\s+(.+?)(?:\s+(?:on|in)\s+)?(?:whatsapp|wa)?", "whatsapp_read"),
    (r"(?:tell|show|gimme)\s+(?:me\s+)?(?:about|my|the)\s*(?:sister|mom|brother|friend|family|contact)", "whatsapp_read"),

    # Web automation
    (r"(?:open|launch|start)\s+(?:the\s+)?(?:web\s+)?(?:app\s+)?(?:gmail|outlook|calendar|maps|youtube|github|notion|chatgpt|claude|drive|docs)", "web_app_open"),
    (r"(?:navigate|go\s+to|browse|open)\s+(?:https?://)?([a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?)", "web_navigate"),
    (r"(?:read|show|get|extract)\s+(?:the\s+)?(?:page|content|text|website|site)", "web_page_read"),
    (r"(?:screenshot|screencap|capture)\s+(?:the\s+)?(?:page|web|browser|screen)", "web_screenshot"),
    (r"(?:click|press|tap)\s+(?:on\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s+(?:button|link|text)?\s*(?:on\s+)?(?:the\s+)?(?:page|web)?", "web_click_text"),
    (r"(?:type|enter|input|fill)\s+['\"]?(.+?)['\"]?\s*(?:into|in|on)\s+(?:the\s+)?(?:search|input|field|box|text)", "web_type"),
    (r"(?:find|search|look\s+for)\s+(?:the\s+)?(?:text\s+)?['\"]?(.+?)['\"]?\s*(?:on\s+)?(?:the\s+)?(?:page|web)", "web_find"),
]

_ACTION_LABELS = {
    "memory_cleanup": "🧹 Freeing up memory...",
    "device_scan": "🔍 Deep scanning your device...",
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
    "net_scan_deep": "🔍 Deep network scan...",
    "net_device_info": "📡 Device details",
    "net_port_scan": "🔍 Port scanning...",
    "net_shares": "📂 Discovering shares...",
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
    "app_list": "📋 Listing installed apps...",
    "app_info": "📋 App details",
    "app_uninstall": "🗑 Uninstalling...",
    "app_quit": "⛔ Forcing quit...",
    "app_running": "🪟 Running apps",
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

    # Real-world task labels
    "search_flights": "✈ Searching flights...",
    "search_hotels": "🏨 Searching hotels...",
    "compare_prices": "💰 Comparing prices...",
    "arbitrage_check": "💎 Checking arbitrage...",
    "calendar_events": "📅 Reading calendar...",
    "calendar_add": "📅 Adding to calendar...",
    "onenote_tasks": "📓 Opening OneNote...",
    "onenote_add_note": "📓 Adding note...",
    "teams_status": "💬 Opening Teams...",
    "teams_assignments": "📋 Fetching your Teams assignments...",
    "browser_tab_screenshot": "📸 Capturing page...",
    "ai_computer_task": "🤖 AI doing computer task...",
    "screen_analyze": "👁 Analyzing screen...",
    "read_file": "📄 Read a file", "write_file": "📝 Write content to a file",
    "list_dir": "📁 List directory contents", "run_python": "🐍 Execute Python code",
    "run_shell": "💻 Execute a shell command", "take_screenshot": "📸 Take a screenshot",
    "network_scan_quick": "📡 Quick network scan...", "network_scan_deep": "📡 Deep network scan...",
    "network_device_info": "🔍 Profiling device...", "wake_on_lan": "⚡ Sending WoL...",
    "smart_home_discover": "🏠 Discovering smart home devices...",
    "smart_home_control": "🏠 Controlling device...", "camera_snap": "📸 Taking photo...",
    "alexa_speak": "🔊 Alexa speaking...", "alexa_play": "▶ Alexa playing...", "alexa_pause": "⏸ Alexa paused...",
    "alexa_volume": "🔊 Alexa volume...", "alexa_discover": "🔍 Scanning for Echo devices...",
    "alexa_timer": "⏰ Alexa timer...", "alexa_routine": "⚡ Alexa routine...",
    "phone_notify": "📱 Sending notification...", "who_is_online": "👥 Who's online...",
    "system_load": "📊 System load...",
    "fetch_search": "🔍 Search the web and return results",
    "open_app": "🚀 Open a macOS application",

    # UI Automation
    "ui_screenshot": "📸 Screen capture...", "ui_get_text": "🔍 Reading screen text...",
    "ui_find": "🔎 Finding text on screen...", "ui_click": "🖱 Clicking at position...",
    "ui_click_text": "🖱 Clicking text...", "ui_type": "⌨ Typing text...",
    "ui_handwrite": "✍️ Handwriting text...", "ui_drag": "↗️ Dragging mouse...",
    "ui_activate_app": "🚀 Activating app...", "ui_app_running": "🔍 Checking app...",

    # Phone Bridge
    "phone_adb_connect": "📱 Connecting to phone...", "phone_read_sms": "📱 Reading SMS...",
    "phone_get_notifications": "📱 Reading notifications...", "phone_call_log": "📱 Reading call log...",
    "phone_battery": "📱 Phone battery...", "phone_contacts": "📱 Reading contacts...",
    "phone_location": "📍 Phone location...",

    # Home Assistant
    "ha_discover": "🏠 Discovering Home Assistant...", "ha_status": "🏠 Home Assistant status...",
    "ha_sensors": "🏠 Reading sensors...", "ha_control": "🏠 Controlling entity...",

    # Cognitive Surveillance
    "cognitive_scan": "🧠 Scanning environment...", "cognitive_insight": "🧠 Generating insight...",
    "cognitive_monitor": "🧠 Starting monitor...", "cognitive_alert": "⚠️ Setting alert...",

    # Persistent Notifications
    "notify_persistent": "📌 Persistent reminder...", "notify_center": "📌 Center notification...",

    # Web Automation
    "whatsapp_open": "💬 Opening WhatsApp Web...",
    "whatsapp_read": "💬 Reading WhatsApp messages...",
    "whatsapp_unread": "💬 Checking unread messages...",
    "whatsapp_send": "💬 Sending WhatsApp message...",
    "whatsapp_schedule": "⏰ Scheduling WhatsApp message...",
    "web_navigate": "🌐 Navigating browser...",
    "web_app_open": "🌐 Opening web app...",
    "web_page_read": "📖 Reading page content...",
    "web_screenshot": "📸 Capturing web page...",
    "web_click_text": "🖱 Clicking text on page...",
    "web_type": "⌨ Typing on page...",
    "web_find": "🔎 Finding text on page...",
    "web_current": "📄 Current page info",
    "web_close": "❌ Closing browser...",
}
_ACTION_TIPS = {
    "memory_cleanup": "Kill memory-hogging apps and free RAM",
    "device_scan": "Deep scan of your Windows device (apps, system, network, files)",
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
    "net_scan_deep": "Deep scan: ARP + ports + vendor + OS",
    "net_device_info": "Detailed info on a network device",
    "net_port_scan": "Scan for open ports on a device",
    "net_shares": "Discover SMB shares on the network",
    "wol": "Wake device via WoL", "ping": "Ping a device",
    "process_list": "List running processes", "kill": "Stop a process",
    "service_list": "Show Windows services", "clipboard_show": "Read clipboard",
    "timer": 'Set timer, e.g. "timer 5 minutes"',
    "search": "Search the web", "weather": "Check weather",
    "public_ip": "Show public IP", "system_info": "Show PC specs",
    "send_keys": "Type text into active window",
    "disk_cleanup": "Run Windows disk cleanup",
    "defender_scan": "Run Windows Defender scan",

    # Web Automation tips
    "whatsapp_open": "Open WhatsApp Web in browser",
    "whatsapp_read": "Read recent WhatsApp messages with context",
    "whatsapp_unread": "Check for new unread WhatsApp messages only",
    "whatsapp_send": 'Send a WhatsApp message, e.g. "send whatsapp to Mom|Coming home late"',
    "whatsapp_schedule": 'Schedule a WhatsApp message, e.g. "schedule whatsapp to Sister|Good night|9pm"',
    "web_navigate": "Navigate browser to a URL",
    "web_app_open": 'Open a web app, e.g. "open gmail" or "open teams"',
    "web_page_read": "Read text content from the current web page",
    "web_screenshot": "Take screenshot of current web page",
    "web_click_text": 'Click text on the page, e.g. "click_text Send"',
    "web_type": 'Type text into a field on the page',
    "web_find": 'Find text on the page, e.g. "find John"',
    "web_current": "Show current web page URL and title",
    "web_close": "Close the web browser",

    # Real-world task tips
    "search_flights": "Search and compare flight prices",
    "search_hotels": "Find hotels and accommodation",
    "compare_prices": "Compare prices across multiple sites",
    "arbitrage_check": "Find price arbitrage opportunities",
    "calendar_events": "Check calendar events",
    "calendar_add": "Add event to calendar",
    "onenote_tasks": "Open OneNote and list notes",
    "onenote_add_note": "Add a note in OneNote",
    "teams_status": "Open Microsoft Teams",
    "teams_assignments": "Find and read your remaining Teams assignments",
    "browser_tab_screenshot": "Take screenshot of a webpage",
    "ai_computer_task": "AI uses vision + mouse/keyboard to complete any task on screen",
    "screen_analyze": "Take screenshot and describe what's on the screen",
}


# ── Optimized detector: keyword O(1) → regex O(n) ─────────────────

def detect_action(text: str) -> str | None:
    lower = text.lower().strip()

    # 1. Keyword lookup — sort by longest phrase first to avoid "time" matching "timer"
    word_count = len(text.split())
    is_complex = word_count > 4  # multi-word query likely describes a task, not a simple command
    for phrase, action in sorted(_KEYWORD_LOOKUP.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            # On complex multi-word queries, only match short keywords if they appear at the start
            # Prevents "chrome" in "open the shaurjesh chrome profile..." from hijacking routing
            if is_complex and len(phrase) <= 10 and not lower.startswith(phrase):
                continue
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


RELAY_INSTRUCTIONS = """I need your computer's relay agent to execute that command.

**Quick setup (takes 30 seconds):**

Open your terminal and run:
```bash
python3 relay.py --user $USER
```

Or install fresh:
```bash
curl -sL 'https://dgfhgjhj-jarvis-ai-brain.hf.space/relay' -o /tmp/relay.py && python3 /tmp/relay.py --user $USER
```

Keep the terminal open — I'll auto-discover your devices and you can control them by voice.

**What I can control once connected:**
  • Smart plugs (TP-Link Tapo, etc.)
  • Lights (Philips Hue, WLED, smart bulbs)
  • Your phone (Samsung, Android)
  • Printers (HP, etc.)
  • Any device on your network"""

def relay_action(action: str, params: str = "", user_id: str = "local") -> str:
    """Queue a desktop action and return relay_id. Frontend polls for result."""
    try:
        from relay import is_relay_alive, queue_action
    except Exception:
        return f"__NEEDS_RELAY__:Relay bridge not available on this server.\n\n{RELAY_INSTRUCTIONS}"
    try:
        if not is_relay_alive(user_id):
            return f"__NEEDS_RELAY__:Action '{action}' needs your computer.\n\n{RELAY_INSTRUCTIONS}"
        relay_id = queue_action(action, params, user_id=user_id)
        return f"__RELAY__:{relay_id}:{action}"
    except Exception as e:
        return f"__NEEDS_RELAY__:Cannot execute '{action}' on server.\n\n{RELAY_INSTRUCTIONS}\n\n(Error: {e})"


# Cloud-safe actions — ones that work on Linux without needing a relay agent
_CLOUD_SAFE_ACTIONS = {
    "weather", "public_ip", "math_eval", "timer", "alarm",
    "timer_stop", "timer_remaining",

    # Web-able actions — run via Playwright on server, relay if available
    "spotify",
    "whatsapp_open", "whatsapp_read", "whatsapp_unread", "whatsapp_send", "whatsapp_schedule",
    "web_app_open", "web_navigate", "web_page_read", "web_screenshot", "web_click_text", "web_type", "web_find",
    "web_current", "web_close", "teams_open", "teams_status", "teams_assignments",
}


def cloud_safe_execute(action: str, user_text: str = "", user_id: str = "local") -> str:
    """Execute action. If on cloud (non-Windows), relay Windows actions."""
    if os.name == "nt":
        return execute_action(action, user_text)
    if action in _CLOUD_SAFE_ACTIONS:
        return execute_action(action, user_text)
    return relay_action(action, user_text, user_id=user_id)


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
    import psutil
    bat = psutil.sensors_battery()
    uptime_h = round((__import__("time").time() - psutil.boot_time()) / 3600, 1)
    if bat:
        pct = int(bat.percent)
        status = "Charging" if bat.power_plugged else "On battery"
        return f"Battery: {pct}% ({status})\nUptime: {uptime_h}h"
    return f"Battery: Desktop (no battery)\nUptime: {uptime_h}h"

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

# ── Volume control via pycaw (direct CoreAudio API from Python) ──
@register("vol_up")
def _vol_up(_):
    try:
        from audio_control import volume_up
        lvl = volume_up(10)
        return f"Volume up to {lvl}%."
    except Exception as e:
        return f"Could not access audio: {e}"

@register("vol_down")
def _vol_down(_):
    try:
        from audio_control import volume_down
        lvl = volume_down(10)
        return f"Volume down to {lvl}%."
    except Exception as e:
        return f"Could not access audio: {e}"

@register("vol_mute")
def _vol_mute(_):
    try:
        from audio_control import toggle_mute, get_mute
        muted = toggle_mute()
        return "Muted." if muted else "Unmuted."
    except Exception as e:
        return f"Could not access audio: {e}"

@register("vol_set")
def _vol_set(text):
    m = re.search(r"(\d+)", text)
    if not m: return "Specify a number (e.g., volume to 50)."
    lvl = min(100, max(0, int(m.group(1))))
    try:
        from audio_control import set_volume
        set_volume(lvl)
        return f"Volume set to {lvl}%."
    except Exception as e:
        return f"Could not access audio: {e}"

@register("vol_level")
def _vol_level(_):
    try:
        from audio_control import get_volume, get_mute
        vol = get_volume()
        muted = get_mute()
        return f"Volume: {vol:.0f}%{' (muted)' if muted else ''}"
    except:
        return "Volume: unknown"

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
    r = _ps('$m=Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness -ErrorAction SilentlyContinue; if($m){$m.CurrentBrightness+10}else{50}')
    try:
        lvl = min(100, int(float(r.strip())) + 10)
        _ps(f'(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue).WmiSetBrightness(1,{lvl})')
        return f"Brightness up to {lvl}%."
    except:
        return "Could not adjust brightness."

@register("brightness_down")
def _brightness_down(_):
    r = _ps('$m=Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness -ErrorAction SilentlyContinue; if($m){$m.CurrentBrightness-10}else{50}')
    try:
        lvl = max(0, int(float(r.strip())) - 10)
        _ps(f'(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue).WmiSetBrightness(1,{lvl})')
        return f"Brightness down to {lvl}%."
    except:
        return "Could not adjust brightness."

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


_MAC_VENDORS: dict[str, str] | None = None

def _mac_vendor(mac: str) -> str:
    """Look up MAC prefix vendor from a built-in prefix database."""
    global _MAC_VENDORS
    if _MAC_VENDORS is None:
        # Compact prefix list: first 3 bytes → known manufacturers
        _MAC_VENDORS = {
            "00:00:0C": "Cisco", "00:01:42": "Google", "00:03:93": "Apple",
            "00:05:02": "Intel", "00:09:0F": "Nokia", "00:0A:27": "D-Link",
            "00:0C:29": "VMware", "00:0E:35": "Huawei", "00:11:24": "Netgear",
            "00:11:50": "Samsung", "00:12:17": "Apple", "00:12:3F": "Dell",
            "00:12:56": "Amazon", "00:13:A9": "ASUS", "00:14:22": "Dell",
            "00:14:51": "Apple", "00:15:5D": "Microsoft", "00:15:E9": "HP",
            "00:16:32": "HTC", "00:16:EA": "TP-Link", "00:17:88": "Nintendo",
            "00:18:0A": "Intel", "00:18:42": "Apple", "00:18:4D": "Apple",
            "00:18:71": "Cisco", "00:19:D1": "Raspberry Pi", "00:1A:11": "Google",
            "00:1B:63": "Linksys", "00:1C:42": "Sony", "00:1C:B3": "Broadcom",
            "00:1D:43": "Sony", "00:1E:58": "LG", "00:1F:01": "Panasonic",
            "00:1F:5B": "Microsoft", "00:1F:81": "Samsung", "00:1F:C6": "Hon Hai",
            "00:21:5A": "RIM", "00:21:6B": "Apple", "00:21:CC": "Apple",
            "00:22:41": "Cisco", "00:22:4D": "LG", "00:22:69": "Alcatel",
            "00:22:6D": "Google", "00:23:5A": "HP", "00:23:DF": "ASUS",
            "00:23:F8": "Sony", "00:24:2C": "Samsung", "00:24:D6": "Nest Labs",
            "00:25:00": "Apple", "00:25:4B": "Apple", "00:25:9C": "ZTE",
            "00:25:D3": "Ruckus", "00:26:08": "T-Mobile", "00:26:55": "TP-Link",
            "00:26:6C": "Dell", "00:26:BB": "Dell", "00:26:F2": "Microsoft",
            "00:27:22": "ASUS", "00:27:51": "LG", "00:27:CB": "Fitbit",
            "00:28:F8": "Netgear", "00:2A:6B": "Sony",
            "04:4B:ED": "Dell", "04:92:26": "Raspberry Pi", "08:00:27": "Oracle",
            "08:00:46": "Sony", "08:05:1B": "Emerson", "08:74:02": "Intel",
            "08:96:D7": "Apple", "0C:4E:C9": "HTC", "0C:74:C2": "Realtek",
            "10:08:B1": "Intel", "10:13:EE": "Canon", "10:2C:6B": "Samsung",
            "10:68:38": "QNAP", "14:10:9F": "Oculus", "14:59:C0": "Apple",
            "14:7D:DA": "Dell", "18:31:BF": "Apple", "1C:1B:0D": "Samsung",
            "1C:69:7A": "Intel", "20:65:8E": "Linksys", "24:06:5A": "Nest Labs",
            "24:65:11": "Apple", "24:AB:81": "Dell", "28:16:2E": "Cisco",
            "28:25:7F": "HTC", "28:C0:DA": "Synology", "2C:30:33": "Apple",
            "2C:54:91": "HP", "2C:56:DC": "LG", "30:D1:A4": "Samsung",
            "34:02:86": "Apple", "34:08:BC": "Google", "34:15:9E": "Netgear",
            "34:3C:0A": "Dell", "34:95:DB": "ASUS", "38:2C:4A": "HTC",
            "38:87:D5": "Dell", "3C:07:54": "Intel", "3C:22:FB": "Dell",
            "3C:5A:37": "Intel", "3C:A6:F6": "HP", "40:1C:83": "Synaptics",
            "40:4D:7F": "Apple", "40:E2:30": "LG", "44:00:BA": "HTC",
            "44:07:0B": "Google", "44:38:39": "HP", "44:8A:5B": "Intel",
            "44:D1:FA": "Amazon", "4C:0B:BE": "HP", "4C:09:D4": "Xerox",
            "4C:77:6B": "Canon", "4C:E6:76": "HTC", "50:2B:73": "Intel",
            "50:76:AF": "Google", "50:F5:DA": "HP", "54:04:A6": "Palmer",
            "54:33:CB": "Intel", "54:9F:13": "HP", "58:55:CA": "Intel",
            "58:8A:5A": "Intel", "5C:51:88": "Intel", "5C:95:AE": "Intel",
            "60:30:41": "LG", "60:6B:BD": "Samsung", "60:92:17": "Synaptics",
            "60:A4:4C": "Intel", "60:E7:01": "TP-Link", "64:00:6A": "Samsung",
            "64:09:22": "Samsung", "64:51:06": "Microsoft", "64:6E:69": "Intel",
            "64:9A:18": "ASUS", "68:3E:34": "D-Link", "68:72:51": "HP",
            "68:94:23": "Samsung", "68:DB:CA": "Intel", "6C:0B:84": "LG",
            "6C:3E:6D": "Raspberry Pi", "6C:83:36": "Samsung", "6C:96:C9": "HP",
            "6C:9C:ED": "Intel", "70:14:A6": "LG", "70:5A:6E": "Samsung",
            "70:62:B8": "Google", "70:66:55": "TCL", "70:A8:D3": "Amazon",
            "74:D0:2B": "Netgear", "74:E5:0B": "ASRock", "78:24:AF": "Intel",
            "78:31:C1": "Cisco", "78:45:61": "Apple", "78:46:85": "HP",
            "7C:05:07": "Intel", "7C:10:C9": "Samsung", "7C:50:79": "Synaptics",
            "80:38:BC": "Google", "80:4A:14": "Sony", "84:16:F9": "HP",
            "84:7B:3B": "LG", "88:03:55": "Google", "88:08:1B": "Samsung",
            "88:1F:A1": "Intel", "88:4A:EA": "Dell", "88:66:5A": "NVIDIA",
            "88:C6:26": "Netgear", "8C:04:BA": "Intel", "8C:8C:AA": "Apple",
            "8C:AE:4C": "Intel", "90:17:AC": "Intel", "90:2B:34": "Dell",
            "90:9A:4A": "Intel", "94:65:2D": "Intel", "94:DB:DA": "LG",
            "98:01:A7": "Apple", "98:90:96": "Intel", "9C:2E:A1": "Dell",
            "9C:4E:36": "Intel", "9C:B6:54": "Intel", "A0:36:9F": "Intel",
            "A0:40:41": "Intel", "A0:45:36": "Samsung", "A0:8C:15": "D-Link",
            "A0:CE:C8": "Intel", "A4:34:D9": "HP", "A4:5E:60": "Apple",
            "A4:77:33": "Dell", "A8:20:66": "Apple", "A8:5E:45": "Microsoft",
            "AC:3A:68": "Intel", "B0:48:7A": "Intel", "B0:7D:64": "Dell",
            "B4:2E:99": "Intel", "B4:B6:76": "Intel", "B8:38:61": "Intel",
            "B8:8D:12": "Apple", "BC:5F:F4": "Intel", "BC:6E:64": "ASUS",
            "BC:AE:C5": "Dell", "BC:92:6B": "Intel", "C0:3F:0E": "Netgear",
            "C0:51:7E": "Intel", "C0:6C:6D": "Netgear", "C0:7B:BC": "Dell",
            "C0:B3:21": "Dell", "C4:65:16": "Intel", "C4:75:95": "Google",
            "C4:85:E1": "Intel", "C8:1E:E7": "Intel", "C8:34:8E": "Dell",
            "C8:5B:76": "LG", "C8:D9:D4": "Intel", "CC:2D:8C": "Intel",
            "CC:3D:AF": "Dell", "CC:96:A0": "Intel", "D0:22:BE": "Dell",
            "D0:37:45": "Intel", "D0:50:99": "Dell", "D0:57:4B": "Cisco",
            "D0:67:E5": "Dell", "D0:95:A6": "Dell", "D4:81:D7": "Google",
            "D4:AE:52": "Dell", "D8:12:65": "Intel", "D8:1C:79": "Samsung",
            "D8:3A:DD": "Intel", "D8:5C:79": "LG", "D8:B3:77": "Intel",
            "DC:A6:32": "Intel", "DC:D9:16": "LG", "E0:2A:82": "Intel",
            "E0:3E:45": "Intel", "E0:55:3D": "Intel", "E0:AC:CB": "Apple",
            "E0:D4:62": "ASUS", "E0:D5:5E": "Intel", "E4:11:5B": "Intel",
            "E4:22:A5": "Google", "E4:A4:71": "Cisco", "E8:50:8B": "Intel",
            "E8:9E:0C": "Intel", "EC:0E:C4": "Intel", "EC:8C:A2": "Intel",
            "EC:B1:D7": "Intel", "EC:DC:E6": "Dell", "F0:18:98": "Intel",
            "F0:4D:A2": "Intel", "F0:7B:CB": "Samsung", "F0:7D:68": "Intel",
            "F0:BD:89": "HP", "F4:0E:22": "Intel", "F4:4D:30": "Dell",
            "F4:6D:04": "Dell", "F4:B5:20": "Intel", "F8:1E:DF": "Intel",
            "F8:2F:A8": "Intel", "F8:5C:7D": "HTC", "F8:8E:85": "Intel",
            "F8:D1:11": "Intel", "FC:15:B4": "Intel", "FC:3F:7C": "Apple",
            "FC:AA:14": "Intel", "FC:F8:AE": "Intel",
        }
    prefix = mac.upper()[:8]  # "XX:XX:XX"
    return _MAC_VENDORS.get(prefix, "Unknown")


@register("network_scan_quick")
def _network_scan_quick(_):
    """Cross-platform: ARP scan to find LAN devices. Works on macOS/Linux/Windows."""
    import subprocess, platform, re
    os_name = platform.system()
    devices = []
    try:
        if os_name == "Windows":
            out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout or ""
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and re.match(r'\d+\.\d+\.\d+\.\d+', parts[0]):
                    devices.append({"ip": parts[0], "mac": parts[1].replace("-", ":").upper()})
        elif os_name == "Darwin":
            out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout or ""
            for line in out.splitlines():
                m = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([a-f0-9:]+)', line.lower())
                if m:
                    devices.append({"ip": m.group(1), "mac": m.group(2).upper()})
        else:  # Linux
            out = subprocess.run(["arp", "-n"], capture_output=True, text=True, timeout=10).stdout or ""
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and re.match(r'\d+\.\d+\.\d+\.\d+', parts[0]) and parts[1] != "<incomplete>":
                    devices.append({"ip": parts[0], "mac": parts[2].strip("()")})
    except: pass

    if not devices:
        # Ping sweep fallback (limited to a few hosts)
        try:
            import socket
            local_ip = "192.168.1.1"
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            base = ".".join(local_ip.split(".")[:3])
            for i in [1, 254, 100, 101, 50, 150, 200]:
                subprocess.run(["ping", "-c", "1", "-W", "1", f"{base}.{i}"],
                               capture_output=True, timeout=2)
        except: pass
        try:
            if os_name == "Darwin":
                out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10).stdout or ""
                for line in out.splitlines():
                    m = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([a-f0-9:]+)', line.lower())
                    if m:
                        devices.append({"ip": m.group(1), "mac": m.group(2).upper()})
        except: pass

    if not devices:
        return "No devices found on network."

    result = f"📡 Network scan — {len(devices)} devices:\n"
    for d in devices[:20]:
        try:
            host = socket.gethostbyaddr(d["ip"])[0].split(".")[0]
        except:
            host = "unknown"
        result += f"  • {host} ({d['ip']}) — {d['mac']}\n"
    return result


@register("network_scan_deep")
def _network_scan_deep(_):
    """Cross-platform deep scan: ARP + hostname + MAC vendor lookup."""
    result = _network_scan_quick(_)
    if result.startswith("No devices"):
        return result
    return result + "\nRun scan_network on Windows for detailed port info."


@register("net_scan_deep")
def _net_scan_deep(_):
    """Deep network scan: ARP + hostname + MAC vendor + port scan common ports + OS guess."""
    subnet = _ps("(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).IPAddress")
    if not subnet: subnet = "192.168.1.1"
    base = ".".join(subnet.split(".")[:3])

    arp = _ps("arp -a")
    raw_devices = []
    for line in (arp or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0].startswith(base):
            ip = parts[0]
            mac = parts[1].replace("-", ":").upper()
            if ip not in [d["ip"] for d in raw_devices]:
                raw_devices.append({"ip": ip, "mac": mac})

    if not raw_devices:
        for i in [1, 254, 100, 101, 50, 150, 200]:
            _ps(f"ping -n 1 -w 200 {base}.{i}")
        arp = _ps("arp -a")
        for line in (arp or "").splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].startswith(base):
                ip = parts[0]
                mac = parts[1].replace("-", ":").upper()
                if ip not in [d["ip"] for d in raw_devices]:
                    raw_devices.append({"ip": ip, "mac": mac})

    if not raw_devices:
        return "No devices found on network."

    # Batch resolve hostnames + port scan common ports on a subset
    result = "Network scan — devices:\n"
    for d in raw_devices[:15]:
        vendor = _mac_vendor(d["mac"])
        host = _ps(f"(Resolve-DnsName {d['ip']} -ErrorAction SilentlyContinue).NameHost")
        hostname = host.split(".")[0] if host else "unknown"

        # Quick port check: common web/admin ports
        http = _ps(f"Test-NetConnection {d['ip']} -Port 80 -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null")
        https = _ps(f"Test-NetConnection {d['ip']} -Port 443 -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null")
        rdp = _ps(f"Test-NetConnection {d['ip']} -Port 3389 -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null")
        ssh = _ps(f"Test-NetConnection {d['ip']} -Port 22 -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null")
        smb = _ps(f"Test-NetConnection {d['ip']} -Port 445 -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null")

        ports_open = []
        if http == "True": ports_open.append("80/http")
        if https == "True": ports_open.append("443/https")
        if rdp == "True": ports_open.append("3389/RDP")
        if ssh == "True": ports_open.append("22/SSH")
        if smb == "True": ports_open.append("445/SMB")
        port_str = f" [{', '.join(ports_open)}]" if ports_open else ""

        result += f"  • {hostname} ({d['ip']}) — {vendor} — {d['mac']}{port_str}\n"
    return result


@register("net_device_info")
def _net_device_info(text):
    """Get detailed info on a specific network device."""
    target = extract_param(text, r"(?:info|details|about)\s+(?:device\s+)?(.+?)$")
    if not target: target = text.replace("device info", "").replace("details", "").strip()
    if not target: return "Which device?"

    arp = _ps("arp -a")
    mac = None; ip = None
    for line in (arp or "").splitlines():
        if target.lower() in line.lower():
            parts = line.strip().split()
            if len(parts) >= 3:
                ip = parts[0]; mac = parts[1].replace("-", ":").upper()
                break

    if not ip:
        return f"Device '{target}' not found in ARP cache. Try 'scan network' first."

    vendor = _mac_vendor(mac)
    host = _ps(f"(Resolve-DnsName {ip} -ErrorAction SilentlyContinue).NameHost")
    hostname = host.split(".")[0] if host else "unknown"
    ping = _ps(f"ping -n 2 {ip} | Select-String 'TTL='")
    ttl_val = re.search(r"TTL=(\d+)", ping)
    os_guess = ""
    if ttl_val:
        ttl = int(ttl_val.group(1))
        if ttl <= 64: os_guess = "(likely Linux/Unix/Android)"
        elif ttl <= 128: os_guess = "(likely Windows)"
        else: os_guess = "(likely Cisco/network device)"

    # Scan common ports
    ports = []
    for p, name in [(22, "SSH"), (80, "HTTP"), (443, "HTTPS"), (3389, "RDP"), (445, "SMB"),
                     (139, "NetBIOS"), (53, "DNS"), (8080, "HTTP-alt"), (8443, "HTTPS-alt")]:
        r = _ps(f"Test-NetConnection {ip} -Port {p} -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null")
        if r == "True": ports.append(f"{p}/{name}")

    result = f"Device: {hostname}\nIP: {ip}\nMAC: {mac}\nVendor: {vendor}\nOS: {os_guess or 'unknown'}"
    if ports: result += f"\nOpen ports: {', '.join(ports)}"
    return result


@register("net_port_scan")
def _net_port_scan(text):
    """Scan common ports on a specific device."""
    target = extract_param(text, r"(?:scan|check|list)\s+(?:ports\s+(?:on|of)\s+)?(.+?)$")
    if not target: return "Which device?"
    p = _ps(f'$ip="{target}"; $ports=@(22,23,25,53,80,110,135,139,143,443,445,993,995,1433,1521,2049,3306,3389,5432,5900,6379,8080,8443,27017); $r=@(); foreach($p in $ports){{$t=Test-NetConnection $ip -Port $p -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null; if($t -eq "True"){{$r+=$p}}; $r -join ","')
    if not p: return f"{target} has no open ports on common ports (or is offline)."
    port_nums = [int(x) for x in p.split(",") if x.strip().isdigit()]
    names = {22:"SSH",23:"Telnet",25:"SMTP",53:"DNS",80:"HTTP",110:"POP3",135:"RPC",139:"NetBIOS",
             143:"IMAP",443:"HTTPS",445:"SMB",993:"IMAPS",995:"POP3S",1433:"MSSQL",1521:"Oracle",
             2049:"NFS",3306:"MySQL",3389:"RDP",5432:"PostgreSQL",5900:"VNC",6379:"Redis",
             8080:"HTTP-alt",8443:"HTTPS-alt",27017:"MongoDB"}
    descs = [f"{n}/{names.get(n,'?')}" for n in port_nums]
    return f"Open ports on {target}: {', '.join(descs)}"


@register("net_shares")
def _net_shares(_):
    """Discover SMB shares on the network."""
    subnet = _ps("(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).IPAddress")
    if not subnet: subnet = "192.168.1.1"
    base = ".".join(subnet.split(".")[:3])

    arp = _ps("arp -a")
    ips = []
    for line in (arp or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0].startswith(base):
            ips.append(parts[0])

    # Check SMB (port 445) on each device
    result = "Network shares discovered:\n"
    found = False
    for ip in ips[:10]:
        smb_check = _ps(f"Test-NetConnection {ip} -Port 445 -WarningAction SilentlyContinue -InformationLevel Quiet 2>$null")
        if smb_check == "True":
            shares = _ps(f'net view \\\\{ip} 2>$null | Select-String "Disk" | Out-String')
            host = _ps(f"(Resolve-DnsName {ip} -ErrorAction SilentlyContinue).NameHost")
            h = host.split(".")[0] if host else ip
            if shares:
                found = True
                result += f"\n  {h} ({ip}):\n"
                for s in shares.splitlines():
                    s = s.strip()
                    if s: result += f"    \\\\{ip}\\{s.split()[0]}\n"
    if not found:
        result += "  No SMB shares found on local network."
    return result


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


@register("memory_cleanup")
def _memory_cleanup(text):
    """Find and kill non-critical memory-hungry processes. Report memory freed."""
    before = _ps("[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)")
    total = _ps("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)")

    # Get top 15 processes by working set, filter out critical system processes
    script = '''
    $procs = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 Name,Id,@{N="MB";E={[math]::Round($_.WorkingSet64/1MB,1)}}
    $critical = @("System","Idle","Registry","smss","csrss","wininit","winlogon","services","lsass","svchost","conhost","fontdrvhost","sihost","taskhostw","RuntimeBroker","SecurityHealth","SecurityHealthSystray","ShellExperienceHost","SearchApp","SearchIndexer","TextInputHost","StartMenuExperienceHost","LockApp","Widgets","WidgetService","ntoskrnl","dwm","explorer")
    $killed = @()
    foreach ($p in $procs) {
        if ($p.Name -notin $critical -and $p.MB -gt 50) {
            try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue; $killed += $p } catch {}
        }
    }
    return @{killed=($killed | ConvertTo-Json -Compress); killed_count=@($killed).Count}
    '''
    import json as _json
    try:
        result = _ps(script)
        data = _json.loads(result) if result else {"killed": [], "killed_count": 0}
    except:
        data = {"killed": [], "killed_count": 0}

    after = _ps("[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,1)")

    try:
        before_f = float(before or 0)
        after_f = float(after or 0)
        freed = round(after_f - before_f, 1)
    except:
        freed = 0

    killed_list = data.get("killed", [])
    killed_count = data.get("killed_count", 0) if isinstance(data.get("killed_count"), int) else len(killed_list)

    lines = [f"── Memory Cleanup ──"]
    lines.append(f"Before: {before} MB free")
    lines.append(f"After:  {after} MB free")
    lines.append(f"Freed:  {freed} MB")
    lines.append(f"Total:  {total} GB")

    if killed_list:
        lines.append(f"Killed {killed_count} process(es):")
        for p in killed_list:
            name = p.get("Name", p.get("name", "?"))
            mb = p.get("MB", p.get("mb", "?"))
            lines.append(f"  • {name} ({mb} MB)")
    else:
        lines.append("No non-critical memory-hungry processes found to kill.")

    return "\n".join(lines)

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

# ── Web App Launcher (PWA-first approach) ─────────────────────
WEB_APPS = {
    "spotify": "https://open.spotify.com",
    "music": "https://open.spotify.com",
    "word": "https://word.office.com",
    "excel": "https://excel.office.com",
    "powerpoint": "https://powerpoint.office.com",
    "onenote": "https://onenote.com",
    "outlook": "https://outlook.live.com",
    "email": "https://mail.google.com", "gmail": "https://mail.google.com",
    "mail": "https://mail.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com", "google drive": "https://drive.google.com",
    "cloud": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "slides": "https://slides.google.com",
    "youtube": "https://youtube.com", "yt": "https://youtube.com",
    "github": "https://github.com", "repos": "https://github.com",
    "code": "https://github.com",
    "discord": "https://discord.com/app", "chat": "https://discord.com/app",
    "slack": "https://slack.com",
    "teams": "https://teams.microsoft.com",
    "vscode": "https://vscode.dev",
    "browser": "https://google.com",
    "chrome": "https://google.com",
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "perplexity": "https://perplexity.ai",
    "notion": "https://notion.so",
    "trello": "https://trello.com",
    "figma": "https://figma.com",
    "canva": "https://canva.com",
    "copilot": "https://copilot.microsoft.com",
    "gemini": "https://gemini.google.com",
    "maps": "https://maps.google.com",
    "news": "https://news.google.com",
    "translate": "https://translate.google.com",
    "meet": "https://meet.google.com",
    "zoom": "https://zoom.us",
    "netflix": "https://netflix.com",
    "youtube music": "https://music.youtube.com",
}

def _launch_web_app(name: str) -> str:
    """Launch any app as a PWA — tries native protocol, Chrome app mode, then browser."""
    url = WEB_APPS.get(name.lower())
    if url:
        _ps(f'Start-Process "chrome.exe" -ArgumentList "--app={url}" 2>$null; if(-not$?){{Start-Process "microsoft-edge:{url}" 2>$null; if(-not$?){{Start-Process "{url}"}}}}')
        return f"Opening {name} web app..."
    # Try native
    native_cmd = APP_MAP_LEGACY.get(name.lower(), "")
    qname = name.replace(" ", "+")
    if native_cmd:
        _ps(f'Start-Process "{native_cmd}" 2>$null; if(-not$?){{Start-Process "https://google.com/search?q={qname}+web"}}')
        return f"Opening {name}..."
    _ps(f'Start-Process "https://google.com/search?q={qname}"')
    return f"Searching for {name}..."

APP_MAP_LEGACY = {
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

@register("settings")
def _settings(_): _ps('Start-Process "ms-settings:"'); return "Settings opened."
@register("control_panel")
def _control_panel(_): _ps('Start-Process "control"'); return "Control Panel opened."
@register("device_manager")
def _device_manager(_): _ps('Start-Process "devmgmt.msc"'); return "Device Manager opened."
@register("reg_edit")
def _reg_edit(_): _ps('Start-Process "regedit.exe"'); return "Registry Editor opened."

@register("browser")
def _browser(_): _launch_web_app("browser"); return "Browser opened."

@register("email")
def _email(_): _launch_web_app("email"); return "Opening email..."
@register("calendar")
def _calendar(_): _launch_web_app("calendar"); return "Opening calendar..."
@register("drive")
def _drive(_): _launch_web_app("drive"); return "Opening Drive..."
@register("youtube")
def _youtube(_): _launch_web_app("youtube"); return "Opening YouTube..."
@register("github")
def _github(_): _launch_web_app("github"); return "Opening GitHub..."
@register("discord")
def _discord(_): _launch_web_app("discord"); return "Opening Discord..."
@register("slack")
def _slack(_): _launch_web_app("slack"); return "Opening Slack..."
@register("vscode")
def _vscode(_): _launch_web_app("vscode"); return "Opening VS Code..."
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
    # PWA-first: try web version
    if name.lower() in WEB_APPS:
        return _launch_web_app(name.lower())
    # Check known native apps
    if name.lower() in APP_MAP_LEGACY:
        _ps(f'Start-Process "{APP_MAP_LEGACY[name.lower()]}"')
        return f"Opening {name}..."
    # Search installed apps by name (fuzzy match)
    found = _ps(f'$n="{name}"; $r=Get-ChildItem "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths" -ErrorAction SilentlyContinue | Where-Object {{$_.PSChildName -like "*$n*"}} | Select-Object -First 1; if($r){{(Get-ItemProperty $r.PSPath)."(default)"}}; if(-not$r){{$r=Get-ChildItem "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\App Paths" -ErrorAction SilentlyContinue | Where-Object {{$_.PSChildName -like "*$n*"}} | Select-Object -First 1; if($r){{(Get-ItemProperty $r.PSPath)."(default)"}}}}')
    if found and found != "Not found":
        _ps(f'Start-Process "{found}"')
        return f"Opening {name}..."
    # Try as executable with web fallback
    qname2 = name.replace(" ", "+")
    _ps(f'Start-Process "{name}" 2>$null; if(-not$?){{Start-Process "{name}.exe" 2>$null; if(-not$?){{Start-Process "https://google.com/search?q={qname2}+web"}}}}')
    return f"Opening {name}..."

@register("app_list")
def _app_list(text):
    q = extract_param(text, r"(?:list|find|search)\s+(?:all\s+)?(?:installed\s+)?(?:apps|programs|software)\s*(?:matching|for|named)?\s*(.+?)$")
    results = _ps(f'''
        $apps = @();
        $regPaths = @(
            "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
            "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
            "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*"
        );
        foreach($p in $regPaths) {{ $apps += Get-ItemProperty $p -ErrorAction SilentlyContinue | Where-Object {{$_.DisplayName}} }};
        $apps = $apps | Sort-Object DisplayName -Unique;
        if("{q}") {{ $apps = $apps | Where-Object {{$_.DisplayName -like "*{q}*"}} }};
        $apps | Select-Object -First 50 @{{N="App";E={{$_.DisplayName}}}},@{{N="Version";E={{$_.DisplayVersion}}}} | Format-Table -Auto | Out-String
    ''')
    if not results or results == "timed_out":
        results = _ps(f'winget list --accept-source-agreements 2>$null | Select-String -Pattern "{q or "."}" | Select-Object -First 30 | Out-String')
    if not results: return "No apps found."
    return f"Installed apps:\n{results[:800]}"

@register("app_info")
def _app_info(text):
    name = extract_param(text, r"(?:app|program|software)\s+(?:info|details|about|properties)\s+(.+?)$")
    if not name: name = extract_param(text, r"info\s+(?:about|on|for)\s+(.+?)$")
    if not name: return "Which app?"
    info = _ps(f'''
        $apps = @();
        $regPaths = @(
            "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
            "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*"
        );
        foreach($p in $regPaths) {{ $apps += Get-ItemProperty $p -ErrorAction SilentlyContinue | Where-Object {{$_.DisplayName -like "*{name}*"}} }};
        $apps[0] | Select-Object DisplayName,DisplayVersion,Publisher,InstallDate,InstallLocation,UninstallString | Format-List | Out-String
    ''')
    return info[:500] or f"App '{name}' not found."

@register("app_uninstall")
def _app_uninstall(text):
    name = extract_param(text, r"(?:uninstall|remove)\s+(?:app|program|software)\s+(.+?)$")
    if not name: return "Which app?"
    _ps(f'winget uninstall "{name}" --accept-source-agreements 2>$null')
    return f"Uninstalling {name}... Check winget for progress."

@register("app_quit")
def _app_quit(text):
    name = extract_param(text, r"(?:quit|close|exit|kill|stop)\s+(?:app|program)\s+(.+?)$")
    if not name: name = extract_param(text, r"force\s+(?:quit|close)\s+(.+?)$")
    if not name: return "Which app?"
    r = _ps(f'(Get-Process -Name "{name}" -ErrorAction SilentlyContinue) | Stop-Process -Force; if(-not$?){{(Get-Process | Where-Object {{$_.MainWindowTitle -like "*{name}*"}}) | Stop-Process -Force}}; "done"')
    return f"Forced quit {name}."

@register("app_running")
def _app_running(_):
    r = _ps('Get-Process | Where-Object {$_.MainWindowTitle -ne ""} | Select-Object Name,@{N="Window";E={$_.MainWindowTitle}},Id | Sort-Object Name | Format-Table -Auto | Out-String')
    return f"Running apps:\n{r[:800] or 'No windowed apps running.'}"


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
def _spotify(_):
    if os.name == "nt":
        _ps('Start-Process "spotify:" 2>$null; if(-not$?){Start-Process "https://open.spotify.com"}')
        return "Opening Spotify..."
    return "Opening Spotify Web Player at https://open.spotify.com"
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

@register("fetch_search")
def _fetch(text):
    """Fetch REAL web search results using DuckDuckGo (returns actual data, not just opens browser)."""
    from duckduckgo_search import DDGS
    q = (extract_param(text, r"(?:fetch|get|read|search)\s+(?:search\s+)?(?:results\s+)?(?:for\s+)?(.+?)$") or text).strip()
    if not q or q.lower() in ["search", "fetch", "get", ""]:
        q = text.replace("fetch", "").replace("search", "").replace("get", "").strip()
    if not q: return "What should I search for?"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(q, max_results=8))
        if results:
            lines = [f"📌 {r['title']}\n   {r['body'][:200]}\n   {r['href']}" for r in results]
            return f"Search results for '{q}':\n\n" + "\n\n".join(lines)
        return f"No results found for '{q}'."
    except ImportError:
        return "DuckDuckGo search library not installed."
    except Exception as e:
        return f"Search error: {str(e)[:150]}"

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
    if not msg: msg = "Hello from JARVIS!"
    _ps(f'''
        $t=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime];
        $d=New-Object Windows.Data.Xml.Dom.XmlDocument;
        $d.LoadXml("<toast><visual><binding template='ToastText01'><text id='1'>{msg}</text></binding></visual></toast>");
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($d)
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


# ── Desktop Control (advanced window/mouse/keyboard) ──────────────

@register("focus_window")
def _focus_window(text):
    from desktop_control import focus_window
    title = extract_param(text, r"(?:focus|switch\s+to|show)\s+(?:window\s+)?(.+?)$")
    if not title: return "Which window?"
    ok = focus_window(title)
    return f"Focused '{title}'." if ok else f"Window '{title}' not found."

@register("close_window")
def _close_window(text):
    from desktop_control import close_window
    title = extract_param(text, r"(?:close|kill)\s+(?:window\s+)?(.+?)$")
    if not title: return "Which window?"
    ok = close_window(title)
    return f"Closed '{title}'." if ok else f"Window '{title}' not found."

@register("list_windows")
def _list_windows(_):
    from desktop_control import list_windows
    wins = list_windows()
    if not wins: return "No visible windows."
    result = "Open windows:\n"
    for w in wins[:15]:
        result += f"  • {w['title'][:40]} ({w['w']}x{w['h']})\n"
    return result

@register("mouse_move")
def _mouse_move(text):
    m = re.search(r"(\d+)\s*[, ]\s*(\d+)", text)
    if not m: return "Position? (e.g., move mouse to 500 300)"
    x, y = int(m.group(1)), int(m.group(2))
    from desktop_control import mouse_move
    mouse_move(x, y)
    return f"Mouse moved to ({x}, {y})."

@register("mouse_click")
def _mouse_click(text):
    m = re.search(r"(\d+)\s*[, ]\s*(\d+)", text)
    from desktop_control import mouse_click
    if m:
        mouse_click(int(m.group(1)), int(m.group(2)))
        return f"Clicked at ({m.group(1)}, {m.group(2)})."
    mouse_click()
    return "Clicked."


# ── Microsoft Word Automation ─────────────────────────────────────

@register("word_new")
def _word_new(_):
    from app_automation import word_open, word_new_document
    word_open(); import time; time.sleep(1)
    return word_new_document()

@register("word_write")
def _word_write(text):
    from app_automation import word_type_text
    content = extract_param(text, r"(?:type|write|add)\s+(?:text|content|paragraph)?\s*(.+?)$")
    if not content: content = text
    # Check for formatting hints
    style = "Normal"; fs = 11; bold = False
    if "heading" in text.lower() or "# " in text:
        style = "Heading 1"; fs = 16; bold = True
    if "subheading" in text.lower() or "## " in text:
        style = "Heading 2"; fs = 14; bold = True
    word_type_text(content, style=style, font_size=fs, bold=bold)
    return f"Written to Word."

@register("word_heading")
def _word_heading(text):
    from app_automation import word_insert_heading
    h = extract_param(text, r"(?:heading|title)\s+(.+?)$")
    if not h: h = text.replace("heading", "").strip()
    level = 2 if "sub" in text.lower() else 1
    word_insert_heading(h, level)
    return f"Heading '{h}' inserted."

@register("word_save")
def _word_save(text):
    from app_automation import word_save
    path = extract_param(text, r"(?:save|to)\s+(.+?\.docx)")
    return word_save(path)

@register("word_table")
def _word_table(text):
    from app_automation import word_insert_table
    m = re.search(r"(\d+)\s*x\s*(\d+)", text)
    if not m: return "Specify rows x cols (e.g., table 3x4)"
    word_insert_table(int(m.group(1)), int(m.group(2)))
    return f"Table {m.group(1)}x{m.group(2)} inserted."


# ── OneNote Automation ────────────────────────────────────────────

@register("onenote_open")
def _onenote_open(_):
    from app_automation import onenote_open
    return onenote_open()

@register("onenote_write")
def _onenote_write(text):
    from app_automation import onenote_write_content
    content = extract_param(text, r"(?:write|type|add)\s+(?:to\s+)?(?:onenote\s+)?(.+?)$")
    if not content: content = text
    # Extract page title if specified
    page = extract_param(text, r"(?:page|in)\s+(?:titled\s+|called\s+)?['\"]?(.+?)['\"]?$")
    return onenote_write_content(content, page or "")


# ── Excel Automation ──────────────────────────────────────────────

@register("excel_open")
def _excel_open(_):
    from app_automation import excel_open
    return excel_open()

@register("excel_set")
def _excel_set(text):
    from app_automation import excel_set_cell
    m = re.search(r"(?:cell\s+)?([A-Z]+)(\d+)\s*[=:]\s*(.+)", text, re.IGNORECASE)
    if not m: return "Format: set cell A1 = value"
    col = sum((ord(c) - 64) * (26 ** i) for i, c in enumerate(reversed(m.group(1).upper())))
    row = int(m.group(2))
    val = m.group(3).strip().strip('"')
    excel_set_cell(1, row, col, val)
    return f"Set {m.group(1).upper()}{row} = {val}."

@register("excel_save")
def _excel_save(_):
    from app_automation import excel_save
    return excel_save()


# ── Chrome / Browser ──────────────────────────────────────────────

@register("chrome_open")
def _chrome_open(text):
    from app_automation import chrome_open
    url = extract_param(text, r"(?:open|go\s+to|navigate)\s+(.+?)$")
    if not url: url = "https://google.com"
    if not url.startswith("http"): url = "https://" + url
    return chrome_open(url)

@register("chrome_tab")
def _chrome_tab(_):
    from app_automation import send_keys
    send_keys("^t")
    return "New tab opened."


# ── App Launcher (universal) ──────────────────────────────────────

@register("launch_app")
def _launch_app(text):
    """Launch ANY app by searching installed apps, or start as executable."""
    name = extract_param(text, r"(?:launch|start|open|run)\s+(?:app\s+|application\s+|program\s+)?(.+?)$")
    if not name: return "Which app?"

    # Map of common apps to their executable names
    common = {
        "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
        "outlook": "outlook", "onenote": "onenote", "notepad": "notepad",
        "chrome": "chrome", "firefox": "firefox", "edge": "msedge",
        "calculator": "calc", "paint": "mspaint", "vs code": "code",
        "terminal": "wt", "cmd": "cmd", "powershell": "powershell",
        "spotify": "spotify", "discord": "discord", "slack": "slack",
        "zoom": "zoom", "teams": "teams", "vlc": "vlc",
    }
    exe = common.get(name.lower(), name)
    _ps(f'Start-Process "{exe}" 2>$null; if(-not$?){{Start-Process "{exe}.exe" 2>$null; if(-not$?){{Start-Process "{name}.exe" 2>$null}}}}')
    return f"Launching {name}..."


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
    text = "I control 215+ things on your PC & network. Categories:\n"
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


# ── REAL-WORLD TASK ACTIONS ──────────────────────────────────────

@register("search_flights")
def _search_flights(text):
    """Search for flights between destinations with real data via DuckDuckGo."""
    from duckduckgo_search import DDGS
    q = extract_param(text, r"(?:flights?|search)\s+(.+?)$") or text
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"flights {q} 2025 2026 cheap", max_results=6))
        if results:
            lines = [f"✈️ {r['title']}\n   {r['body'][:200]}\n   {r['href']}" for r in results]
            return f"Flight results for '{q}':\n\n" + "\n\n".join(lines)
        return f"No flight results for '{q}'. Opening Skyscanner..."
    except: pass
    _ps(f'Start-Process "https://www.skyscanner.net/transport/flights?q={_uq(q)}"')
    _ps(f'Start-Process "https://www.google.com/travel/flights?q={_uq(q)}"')
    return f"Opened flight search for '{q}' in browser."

@register("search_hotels")
def _search_hotels(text):
    """Search for hotels with real data."""
    from duckduckgo_search import DDGS
    q = extract_param(text, r"(?:hotels?|stay|accommodation)\s+(.+?)$") or text
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"hotels {q} booking", max_results=6))
        if results:
            lines = [f"🏨 {r['title']}\n   {r['body'][:200]}\n   {r['href']}" for r in results]
            return f"Hotel results for '{q}':\n\n" + "\n\n".join(lines)
    except: pass
    _ps(f'Start-Process "https://www.booking.com/searchresults.html?ss={_uq(q)}"')
    return f"Opened hotel search for '{q}' in browser."

@register("compare_prices")
def _compare_prices(text):
    """Search multiple sites to compare prices for flights/hotels/products."""
    from duckduckgo_search import DDGS
    q = extract_param(text, r"(?:compare|price|cheap|deal)\s+(.+?)$") or text
    results_text = f"🔍 Comparing prices for '{q}'...\n\n"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(q, max_results=10))
        if results:
            for r in results[:8]:
                results_text += f"• {r['title'][:80]}\n  {r['body'][:150]}\n  {r['href']}\n\n"
        # Also open comparison sites
        _ps(f'Start-Process "https://www.google.com/search?q={_uq(q)}&tbm=shop"')
        _ps(f'Start-Process "https://www.kayak.com/search?q={_uq(q)}"')
        return results_text
    except:
        return f"Opened price comparison for '{q}'."

@register("calendar_events")
def _calendar_events(text):
    """Read Outlook/Windows calendar events."""
    q = extract_param(text, r"(?:calendar|schedule|events?|appointments?)\s+(.+?)$") or "today"
    period = "today"
    if "tomorrow" in q.lower(): period = "tomorrow"
    elif "week" in q.lower(): period = "week"
    elif "month" in q.lower(): period = "month"
    try:
        ps_script = '''
            Add-Type -AssemblyName "Microsoft.Office.Interop.Outlook" 2>$null;
            if(-not $?) {
                # Fallback: use Windows Calendar via COM
                try {
                    $outlook = New-Object -ComObject Outlook.Application 2>$null;
                    $ns = $outlook.GetNamespace("MAPI");
                    $cal = $ns.GetDefaultFolder(9);  # olFolderCalendar
                    $appts = $cal.Items | Select-Object -First 10 Subject,Start,Duration,Location;
                    return ($appts | Format-Table -Auto | Out-String);
                } catch { return "Calendar not available via COM." }
            }
        '''
        result = _ps(ps_script)
        if "Calendar not available" in result or "outlook" not in result.lower():
            # Fallback: open calendar web
            _ps('Start-Process "https://calendar.google.com"')
            return f"Opened calendar. Upcoming events: not available via COM. Try web calendar."
        return f"Calendar ({period}):\n{result[:600]}"
    except:
        _ps('Start-Process "outlookcal:" 2>$null; Start-Process "https://calendar.google.com"')
        return f"Opening calendar for {period}..."

@register("calendar_add")
def _calendar_add(text):
    """Add event to calendar."""
    parts = text.split(",")
    title = parts[0].replace("add", "").replace("calendar", "").replace("event", "").strip()
    time_str = parts[1].strip() if len(parts) > 1 else "1 hour"
    duration = parts[2].strip() if len(parts) > 2 else "60"
    try:
        _ps(f'''
            $o = New-Object -ComObject Outlook.Application;
            $a = $o.CreateItem(1);  # olAppointmentItem
            $a.Subject = "{title[:100]}";
            $a.Start = [DateTime]::Now.AddHours(1);
            $a.Duration = {duration};
            $a.Save();
            return "Event created: {title[:50]}"
        ''')
        return f"✅ Event added: {title[:50]}"
    except:
        _ps('Start-Process "https://calendar.google.com/calendar/u/0/r/eventedit"')
        return f"Opening calendar to add event: {title[:50]}"

@register("onenote_tasks")
def _onenote_tasks(text):
    """List OneNote pages/notes."""
    try:
        result = _ps('''
            try {
                $o = New-Object -ComObject OneNote.Application 15 $null;
                $xml = "";
                $o.GetHierarchy("", [Microsoft.Office.Interop.OneNote.HierarchyScope]::hsPages, [ref]$xml);
                $xml
            } catch { "OneNote COM not available" }
        ''')
        if "OneNote COM not available" in result or not result.strip():
            # Fallback: open OneNote
            _ps('Start-Process "onenote:"')
            return "Opening OneNote..."
        return f"OneNote pages:\n{result[:600]}"
    except:
        _ps('Start-Process "onenote:"')
        return f"Opening OneNote..."

@register("onenote_add_note")
def _onenote_add_note(text):
    """Add a note/page to OneNote."""
    content = extract_param(text, r"(?:write|add|create|note)\s+(?:to\s+)?(?:onenote\s+)?(.+?)$") or text
    try:
        from app_automation import onenote_write_content
        result = onenote_write_content(content)
        return f"📝 Added to OneNote: {content[:50]}"
    except:
        _ps(f'Start-Process "onenote:"')
        return f"Opening OneNote to write: {content[:50]}"

@register("teams_status")
def _teams_status(text):
    """Open Microsoft Teams or check status."""
    _ps('Start-Process "msteams:" 2>$null; if(-not $?) { Start-Process "https://teams.microsoft.com" }')
    return "Opening Microsoft Teams..."


@register("teams_assignments")
def _teams_assignments(text):
    """Use the computer vision agent to navigate Teams and read out assignments."""
    from screen_agent import run_task, capture_screen, analyze_screen, _HAS_PYGUI, _HAS_PIL, _HAS_MSS

    if not _HAS_PYGUI or not _HAS_PIL or not _HAS_MSS:
        # Fallback: just open Teams
        _ps('Start-Process "msteams:" 2>$null; if(-not $?) { Start-Process "https://teams.microsoft.com" }')
        return "Screen agent not available. Opening Teams manually — check Assignments tab."

    # Step 1: Open Teams
    _ps('Start-Process "msteams:" 2>$null; if(-not $?) { Start-Process "https://teams.microsoft.com" }')
    import time as _t
    _t.sleep(4)  # Wait for Teams to launch

    # Step 2: Run screen agent synchronously (up to 12 iterations, ~45 seconds)
    prompt = "Look at the screen. If you see Microsoft Teams, navigate to the Assignments or Tasks section. Find all pending/remaining assignments with their due dates and status. Read them out clearly with subject name, assignment title, due date, and status."
    result = run_task(prompt, max_iter=12)

    if result.success:
        return f"✅ Teams Assignments:\n{result.summary}"
    elif result.steps > 0:
        return f"Partially completed after {result.steps} steps ({round(result.duration_sec, 1)}s):\n{result.summary}"
    else:
        return f"Teams agent: {result.summary}"


# ── Web Automation (relay to desktop if alive, else run on HF Space) ──
from concurrent.futures import ThreadPoolExecutor

_WEB_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def _web_or_relay(action_name, web_fn_name, text="", *args, **kwargs):
    """Relay to desktop if relay agent is alive, else run web automation on HF Space."""
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action(action_name, text)
    except Exception:
        pass
    # Fallback: run web automation
    return _web_run(web_fn_name, *args, **kwargs)


def _web_run(fn_name, *args, **kwargs):
    """Run web automation function in a thread to avoid Playwright sync API issues with asyncio."""
    try:
        import sys as _sys
        _backend = os.path.dirname(os.path.abspath(__file__))
        if _backend not in _sys.path:
            _sys.path.insert(0, _backend)
        import web_automation as _wa
        future = _WEB_EXECUTOR.submit(_wa._ensure_browser)
        future.result(timeout=30)
        fn = getattr(_wa, fn_name)
        future = _WEB_EXECUTOR.submit(fn, *args, **kwargs)
        return future.result(timeout=120)
    except Exception as e:
        return f"Web automation error: {e}"


@register("whatsapp_open")
def _whatsapp_open(text):
    return _web_or_relay("whatsapp_open", "app_whatsapp_open", text)


@register("whatsapp_read")
def _whatsapp_read(text):
    return _web_or_relay("whatsapp_read", "app_whatsapp_read", text)


@register("whatsapp_unread")
def _whatsapp_unread(text):
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("whatsapp_unread", "", user_id="local")
    except Exception:
        pass
    return _web_run("app_whatsapp_read", unread_only=True)


@register("whatsapp_send")
def _whatsapp_send(text):
    contact = extract_param(text, r"(?:to|for)\s+'?\"?([a-zA-Z0-9_ ]+?)'?\"?\s*(?:saying|that|about|:|the|message|text)?") or ""
    msg = extract_param(text, r"(?:saying|that|:)\s+'?\"?(.+?)'?\"?\s*$") or ""
    if not contact:
        parts = text.lower().split("whatsapp")[-1].split("to")
        contact = parts[-1].strip().split()[0] if len(parts) > 1 else ""
    if not msg:
        msg = text.split("saying")[-1].strip() if "saying" in text.lower() else "Hi!"
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("whatsapp_send", f"{contact.strip()[:30]}|{msg.strip()[:200]}", user_id="local")
    except Exception:
        pass
    return _web_run("app_whatsapp_send", contact.strip()[:30], msg.strip()[:200])


@register("whatsapp_schedule")
def _whatsapp_schedule(text):
    contact = extract_param(text, r"(?:to|for)\s+'?\"?([a-zA-Z0-9_ ]+?)'?\"?") or ""
    msg = extract_param(text, r"(?:saying|that|:)\s+'?\"?(.+?)'?\"?\s*(?:at|for|in)\s") or "Hi!"
    time_str = extract_param(text, r"(?:at|for|in)\s+(.+?)$") or "in 10 minutes"
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("whatsapp_schedule", f"{contact.strip()[:30]}|{msg.strip()[:200]}|{time_str.strip()}", user_id="local")
    except Exception:
        pass
    return _web_run("app_whatsapp_send", contact.strip()[:30], f"[SCHEDULED] {msg.strip()[:200]}")


@register("teams_open")
@register("teams_status")
def _teams_open(text):
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("teams_open", "", user_id="local")
    except Exception:
        pass
    return _web_run("app_teams_open")


@register("teams_assignments")
def _teams_assignments_web(text):
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("teams_assignments", "", user_id="local")
    except Exception:
        pass
    return _web_run("app_teams_assignments")


@register("web_app_open")
def _web_app_open(text):
    app = extract_param(text, r"(?:open|launch|start)\s+(?:the\s+)?(?:web\s+)?(?:app\s+)?(.+)") or "gmail"
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_app_open", app.strip(), user_id="local")
    except Exception:
        pass
    return _web_run("app_open", app.strip())


@register("web_navigate")
def _web_navigate(text):
    url = extract_param(text, r"(?:navigate|go\s+to|browse|open)\s+(https?://[^\s]+|(?:[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?))")
    if not url:
        url = extract_param(text, r"(?:to|at)\s+(https?://[^\s]+)") or "google.com"
    if url and not url.startswith("http"):
        url = "https://" + url
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_navigate", url, user_id="local")
    except Exception:
        pass
    _web_run("navigate", url or "https://google.com")
    return f"Navigated to {url}"


@register("web_page_read")
def _web_page_read(text):
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_page_read", "", user_id="local")
    except Exception:
        pass
    result = _web_run("get_text")
    return result or "No readable content found"


@register("web_screenshot")
def _web_screenshot(text):
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_screenshot", "", user_id="local")
    except Exception:
        pass
    b64 = _web_run("screenshot_b64")
    if b64:
        return f"__SCREENSHOT__:{b64}"
    return "Screenshot failed"


@register("web_click_text")
def _web_click_text(text):
    target = extract_param(text, r"(?:click|press|tap)\s+(?:on\s+)?(?:the\s+)?['\"]?(.+?)['\"]?\s*(?:button|link|text)?")
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_click_text", target or text, user_id="local")
    except Exception:
        pass
    return _web_run("click_text", target or text)


@register("web_type")
def _web_type(text):
    content = extract_param(text, r"(?:type|enter|input|fill)\s+['\"]?(.+?)['\"]?\s*(?:into|in|on)") or text
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_type", content.strip()[:300], user_id="local")
    except Exception:
        pass
    return _web_run("type_text", content.strip()[:300])


@register("web_find")
def _web_find(text):
    target = extract_param(text, r"(?:find|search|look\s+for)\s+(?:the\s+)?(?:text\s+)?['\"]?(.+?)['\"]?") or text
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_find", target.strip()[:100], user_id="local")
    except Exception:
        pass
    found = _web_run("find_text", target.strip()[:100])
    if found:
        return f"Found '{found['text']}' at ({found['x']}, {found['y']})"
    return f"'{target}' not found on page"


@register("web_current")
def _web_current(text):
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_current", "", user_id="local")
    except Exception:
        pass
    return _web_run("app_current")


@register("web_close")
def _web_close(text):
    try:
        from relay import is_relay_alive
        if is_relay_alive():
            return relay_action("web_close", "", user_id="local")
    except Exception:
        pass
    _web_run("close")
    return "Browser closed"


@register("browser_tab_screenshot")
def _browser_tab_screenshot(text):
    """Open a URL, wait, and take a screenshot of the page."""
    url = extract_param(text, r"(?:screenshot|capture)\s+(?:of\s+)?(.+?)$") or "https://google.com"
    if not url.startswith("http"): url = "https://" + url
    path = os.path.expanduser(f"~/Desktop/page_{int(time.time())}.png")
    _ps(f'Start-Process "{url}"')
    time.sleep(3)  # Wait for page to load
    _ps(f'''
        Add-Type -AssemblyName System.Windows.Forms;
        $b=[System.Drawing.Bitmap]::new([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,
           [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height);
        $g=[System.Drawing.Graphics]::FromImage($b);
        $g.CopyFromScreen(0,0,0,0,$b.Size);
        $b.Save("{path}"); $g.Dispose(); $b.Dispose()
    ''')
    return f"📸 Page screenshot saved to Desktop. Opened {url[:60]}..."

@register("arbitrage_check")
def _arbitrage_check(text):
    """Check multiple flight/hotel sites for price arbitrage opportunities."""
    from duckduckgo_search import DDGS
    q = extract_param(text, r"(?:arbitrage|compare|deal)\s+(.+?)$") or text
    results_text = f"🔎 Checking arbitrage opportunities for '{q}'...\n\n"
    try:
        with DDGS() as ddgs:
            # Search multiple angles
            queries = [
                f"cheapest {q} deals",
                f"{q} discount coupons promo",
                f"compare prices {q}",
                f"best price {q} 2025",
            ]
            seen_urls = set()
            for qry in queries:
                for r in list(ddgs.text(qry, max_results=4)):
                    if r["href"] not in seen_urls:
                        seen_urls.add(r["href"])
                        results_text += f"💰 {r['title'][:80]}\n  {r['body'][:150]}\n  {r['href']}\n\n"
        # Open comparison sites
        _ps(f'Start-Process "https://www.skyscanner.net/transport/flights?q={_uq(q)}"')
        _ps(f'Start-Process "https://www.kayak.com/in?q={_uq(q)}"')
        _ps(f'Start-Process "https://www.google.com/travel/flights?q={_uq(q)}"')
        results_text += "🚀 Opened Skyscanner, Kayak, and Google Flights for side-by-side comparison!"
        return results_text
    except Exception as e:
        _ps(f'Start-Process "https://www.google.com/search?q={_uq(q)}+cheap+deals"')
        return f"Opened search for '{q}' deals. Error: {str(e)[:80]}"


# ── Keyboard shortcuts ─────────────────────────────────────────────

@register("send_keys")
def _send_keys(text):
    keys = extract_param(text, r"(?:send|press|type)\s+(?:keys?\s+)?(.+?)$") or "{ENTER}"
    _ps(f'$k=(New-Object -ComObject WScript.Shell); $k.SendKeys("{keys}")')
    return f"Sent keys: {keys[:20]}"


# ── Computer Use Agent ─────────────────────────────────────────────

@register("ai_computer_task")
def _ai_computer_task(text):
    """AI sees the screen and performs visual tasks (OneNote, forms, navigation)."""
    from screen_agent import run_task, capture_screen, _HAS_PYGUI, _HAS_PIL, _HAS_MSS

    if not _HAS_PYGUI or not _HAS_PIL or not _HAS_MSS:
        return "Screen agent not available — missing dependencies (pyautogui/Pillow/mss)."

    # Pre-launch relevant apps so vision model has a starting point
    try:
        import pyautogui
        lower = text.lower()
        if "chrome" in lower:
            pyautogui.hotkey("win", "r")
            pyautogui.sleep(0.5)
            pyautogui.write("chrome", interval=0.05)
            pyautogui.press("enter")
            pyautogui.sleep(2)
        elif "firefox" in lower:
            pyautogui.hotkey("win", "r")
            pyautogui.sleep(0.5)
            pyautogui.write("firefox", interval=0.05)
            pyautogui.press("enter")
            pyautogui.sleep(2)
        elif "edge" in lower:
            pyautogui.hotkey("win", "r")
            pyautogui.sleep(0.5)
            pyautogui.write("microsoft-edge:", interval=0.05)
            pyautogui.press("enter")
            pyautogui.sleep(2)
        elif "teams" in lower:
            pyautogui.hotkey("win", "r")
            pyautogui.sleep(0.5)
            pyautogui.write("teams", interval=0.05)
            pyautogui.press("enter")
            pyautogui.sleep(4)
        elif "outlook" in lower:
            pyautogui.hotkey("win", "r")
            pyautogui.sleep(0.5)
            pyautogui.write("outlook", interval=0.05)
            pyautogui.press("enter")
            pyautogui.sleep(3)
        elif "notepad" in lower or "notes" in lower:
            pyautogui.hotkey("win", "r")
            pyautogui.sleep(0.5)
            pyautogui.write("notepad", interval=0.05)
            pyautogui.press("enter")
            pyautogui.sleep(1)
    except Exception:
        pass  # Pre-launch is best-effort

    # Run synchronously — actually do the work before returning
    result = run_task(text, max_iter=40)

    if result.success:
        return f"✅ Done: {result.summary}"
    elif result.steps > 0:
        if result.summary.startswith("ASK:"):
            return f"__ASK__:{result.summary[4:].strip()}"
        return f"Partially done after {result.steps} steps ({round(result.duration_sec, 1)}s): {result.summary}"
    else:
        if result.summary.startswith("ASK:"):
            return f"__ASK__:{result.summary[4:].strip()}"
        return f"Screen agent: {result.summary}"


@register("screen_analyze")
def _screen_analyze(text):
    """Take a screenshot and describe what's on screen."""
    from screen_agent import capture_screen, analyze_screen
    img = capture_screen()
    if not img:
        return "Screen capture failed — missing dependencies (mss/Pillow)."
    result = analyze_screen(text or "Describe what's on this screen in detail.", img)
    return result.get("result") or result.get("summary") or json.dumps(result)


@register("device_scan")
def _device_scan(text):
    """Deep scan of the Windows device — apps, system, network, files, accounts."""
    try:
        from device_scanner import scan_device
        data = scan_device("local", force=True)
    except Exception as e:
        return f"Device scan failed: {e}"

    # Save to user profile for personalization
    try:
        from user_profile import load_profile, save_profile, merge_device_data
        p = load_profile("local")
        merge_device_data(p, data)
        save_profile("local", p)
    except:
        pass

    lines = ["── Device Scan Results ──"]

    sys = data.get("system", {})
    lines.append(f"OS: {sys.get('os', '?')} Build {sys.get('version', '?')}")
    lines.append(f"CPU: {sys.get('cpu', '?')} ({sys.get('cores', '?')} cores)")
    lines.append(f"RAM: {sys.get('ram_gb', '?')} GB")
    lines.append(f"Disk C: {sys.get('disk_free_gb', '?')} GB free / {sys.get('disk_total_gb', '?')} GB total")
    lines.append(f"Battery: {sys.get('battery', '?')}%")
    lines.append(f"Screen: {sys.get('screen_res', '?')}")
    lines.append(f"GPU: {sys.get('gpu', '?')}")

    apps = data.get("installed_apps", [])
    lines.append(f"Installed apps: {len(apps)}")
    if apps:
        lines.append("Top apps: " + ", ".join(a.get("name", "?")[:30] for a in apps[:10]))

    procs = data.get("running_processes", [])
    lines.append(f"Running processes: {len(procs)}")
    if procs:
        lines.append("Top memory: " + ", ".join(f"{p.get('Name','?')}({p.get('MB','?')}MB)" for p in procs[:5]))

    net = data.get("network", {})
    lines.append(f"IP: {net.get('local_ip', '?')}")
    lines.append(f"WiFi: {net.get('wifi_ssid', '?')}")
    lines.append(f"Hostname: {net.get('hostname', '?')}")

    browsers = data.get("browser_profiles", [])
    lines.append(f"Browser profiles: {len(browsers)}")
    for b in browsers:
        lines.append(f"  {b.get('browser','?')}/{b.get('profile','?')}: {b.get('email','no email')}")

    services = data.get("services", [])
    lines.append(f"Running services: {len(services)}")

    files = data.get("recent_files", [])
    lines.append(f"Recent documents: {len(files)} in Desktop/Documents/Downloads")

    lines.append(f"Scan time: {data.get('scan_time', '?')}")
    return "\n".join(lines)


# ── Platform-agnostic file I/O & code execution ──────────────────

@register("read_file")
def _read_file(text):
    path = text.replace("read file", "").replace("read", "").strip() or text
    path = os.path.expanduser(path)
    if not os.path.isfile(path): return f"File not found: {path}"
    try:
        with open(path, "r", errors="replace") as f:
            content = f.read(5000)
        return content[:3000]
    except Exception as e:
        return f"Read error: {e}"

@register("write_file")
def _write_file(text):
    rest = text.replace("write file", "").replace("write", "").strip()
    if "::" in rest:
        path, content = rest.split("::", 1)
    else:
        parts = rest.rsplit(" ", 1)
        if len(parts) < 2: return "Usage: write_file path::content"
        path, content = parts
    path = os.path.expanduser(path.strip())
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content.strip())
        return f"Written to {path}"
    except Exception as e:
        return f"Write error: {e}"

@register("list_dir")
def _list_dir(text):
    path = text.replace("list dir", "").replace("list", "").replace("directory", "").strip()
    if not path: path = "."
    path = os.path.expanduser(path)
    if not os.path.isdir(path): return f"Directory not found: {path}"
    try:
        entries = sorted(os.listdir(path))[:50]
        lines = []
        for e in entries:
            fp = os.path.join(path, e)
            sz = os.path.getsize(fp) if os.path.isfile(fp) else 0
            typ = "📄" if os.path.isfile(fp) else "📁" if os.path.isdir(fp) else "🔗"
            lines.append(f"{typ} {e}" + (f" ({sz} bytes)" if os.path.isfile(fp) else ""))
        return "\n".join(lines) + f"\n\n{len(entries)} entries"
    except Exception as e:
        return f"List error: {e}"


# ── Public API ─────────────────────────────────────────────────────

def get_all_actions() -> dict:
    return {k: {"label": _ACTION_LABELS.get(k, k), "tip": _ACTION_TIPS.get(k, "")} for k in sorted(_EXECUTORS.keys())}


# ═══════════════════════════════════════════════════════════════════
#  macOS Executors — override Windows actions when running on macOS
#  (registered last so they win over Windows versions)
# ═══════════════════════════════════════════════════════════════════

if sys.platform == "darwin":
    import subprocess as _sp

    def _mac_run(cmd: str, timeout=15) -> str:
        try:
            r = _sp.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return (r.stdout or r.stderr or f"exit {r.returncode}").strip()
        except Exception as e:
            return f"Error: {e}"

    @register("screenshot")
    def _mac_screenshot(_): return _mac_run("screencapture -x ~/Desktop/jarvis_screenshot.png 2>/dev/null; echo 'Saved to Desktop/'")

    @register("search")
    def _mac_search(text):
        from urllib.parse import quote as _uq2
        q = text.replace("search", "").replace("google", "").replace("look up", "").strip() or text
        _mac_run(f"open 'https://google.com/search?q={_uq2(q)}'")
        return f'Searching for "{q}"...'

    @register("search_youtube")
    def _mac_search_yt(text):
        from urllib.parse import quote as _uq2
        q = text.replace("search", "").replace("youtube", "").replace("yt", "").strip() or text
        _mac_run(f"open 'https://youtube.com/results?search_query={_uq2(q)}'")
        return f'Searching YouTube for "{q}"...'

    @register("search_wiki")
    def _mac_search_wiki(text):
        from urllib.parse import quote as _uq2
        q = text.replace("search", "").replace("wikipedia", "").replace("wiki", "").strip() or text
        _mac_run(f"open 'https://en.wikipedia.org/wiki/{_uq2(q).replace(' ', '_')}'")
        return f'Searching Wikipedia for "{q}"...'

    @register("open_url")
    def _mac_open_url(text):
        url = text.replace("open", "").replace("go to", "").replace("url", "").replace("website", "").strip()
        if not url: return "Which URL?"
        if not url.startswith("http"): url = "https://" + url
        _mac_run(f"open '{url}'")
        return f"Opening {url[:70]}..."

    @register("whoami")
    def _mac_whoami(_): return f"User: {_mac_run('whoami')}"

    @register("uptime")
    def _mac_uptime(_): return _mac_run("uptime")

    @register("system_info")
    def _mac_sysinfo(_):
        os_v = _mac_run("sw_vers 2>/dev/null")
        hw = _mac_run("uname -a")
        mem = _mac_run("sysctl -n hw.memsize 2>/dev/null")
        cpu = _mac_run("sysctl -n hw.ncpu 2>/dev/null")
        return f"macOS: {os_v}\nKernel: {hw}\nRAM: {int(mem)//1073741824}GB\nCPUs: {cpu}"

    @register("battery_status")
    def _mac_battery(_):
        r = _mac_run("pmset -g batt 2>/dev/null")
        if "drawing" in r or "charging" in r or "discharging" in r or "charged" in r:
            return r
        return "Desktop (no battery)"

    @register("public_ip")
    def _mac_public_ip(_):
        ip = _mac_run("curl -s --max-time 5 https://api.ipify.org 2>/dev/null")
        return f"Public IP: {ip or 'unknown'}"

    @register("weather")
    def _mac_weather(_):
        w = _mac_run("curl -s 'wttr.in?format=%C+%t+%w' 2>/dev/null")
        return w if w else "Weather unavailable"

    @register("speak")
    def _mac_speak(text):
        t = text.replace("say", "").replace("speak", "").replace("read", "").strip()
        if not t: t = text
        _mac_run(f"say '{t[:200].replace(chr(39), '')}'")
        return f'Saying: "{t[:60]}"...'

    @register("send_notification")
    def _mac_notify(text):
        t = text.replace("send notification", "").replace("notify", "").replace("notification", "").strip()
        if not t: t = "Hello from J.A.R.V.I.S."
        _mac_run(f"""osascript -e 'display notification "{t[:200].replace(chr(34), '')}" with title "J.A.R.V.I.S."' 2>/dev/null""")
        return "Notification sent."

    @register("notify_persistent")
    def _mac_notify_persistent(text):
        """Show a persistent floating notification window (centre-screen, always-on-top, draggable)."""
        _notify_window(text)

    @register("notify_center")
    def _mac_notify_center(text):
        _notify_window(text)

    def _notify_window(msg: str) -> str:
        np_path = os.path.join(os.path.dirname(__file__), "notification_window.py")
        if not os.path.isfile(np_path):
            return "Notification window script not found"
        escaped = msg[:500].replace("'", "'\\''")
        _mac_run(f"python3 '{np_path}' '{escaped}' &", timeout=2)
        return f"Notification: '{msg[:60]}'"

    @register("lock")
    def _mac_lock(_):
        _mac_run("""osascript -e 'tell application "System Events" to keystroke "q" using {command down, control down}' 2>/dev/null || pmset displaysleepnow 2>/dev/null || /System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend 2>/dev/null""")
        return "Locking screen..."

    @register("disk_info")
    def _mac_disk(_): return _mac_run("df -h /")

    @register("memory_info")
    def _mac_mem(_): return _mac_run("vm_stat | head -12")

    @register("process_list")
    def _mac_procs(_): return _mac_run("ps aux --sort=-%cpu | head -25")

    @register("wifi_list")
    def _mac_wifi(_):
        ap = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        r = _mac_run(f"{ap} -s 2>/dev/null")
        if not r: r = _mac_run("networksetup -listallhardwareports 2>/dev/null | grep -A1 Wi-Fi")
        return r or "No Wi-Fi interface found"

    @register("network_info")
    def _mac_net(_):
        r = _mac_run("ifconfig en0 2>/dev/null | grep 'inet '")
        if not r: r = _mac_run("ifconfig en1 2>/dev/null | grep 'inet '")
        r += "\n" + _mac_run("networksetup -getinfo Wi-Fi 2>/dev/null")
        return r.strip() or "No network info available"

    @register("volume_up")
    def _mac_vol_up(_):
        _mac_run("osascript -e 'set volume output volume (output volume of (get volume settings) + 10)'")
        return "Volume up"

    @register("volume_down")
    def _mac_vol_down(_):
        _mac_run("osascript -e 'set volume output volume (output volume of (get volume settings) - 10)'")
        return "Volume down"

    @register("volume_mute")
    def _mac_vol_mute(_):
        _mac_run("osascript -e 'set volume output muted true'")
        return "Muted"

    @register("time")
    def _mac_time(_): return __import__("datetime").datetime.now().strftime("%A, %B %d, %Y — %I:%M %p")

    @register("open_app")
    def _mac_open_app(text):
        name = text.lower().strip()
        apps = {"safari":"Safari","chrome":"Google Chrome","firefox":"Firefox","terminal":"Terminal",
                "code":"Visual Studio Code","vs code":"Visual Studio Code","finder":"Finder",
                "spotify":"Spotify","music":"Music","photos":"Photos","settings":"System Settings",
                "notes":"Notes","calendar":"Calendar","mail":"Mail","messages":"Messages",
                "maps":"Maps","facetime":"FaceTime","calculator":"Calculator",
                "system settings":"System Settings","app store":"App Store"}
        an = apps.get(name, name.title())
        _mac_run(f'open -a "{an}"')
        return f"Opened {an}"

    @register("finder_open")
    def _mac_finder(text):
        path = text.replace("open", "").replace("finder", "").replace("directory", "").replace("folder", "").strip()
        if not path: path = "~"
        _mac_run(f"open '{path}'")
        return f"Opening {path}..."

    @register("read_file")
    def _mac_read_file(text):
        path = text.replace("read file", "").replace("read", "").strip() or text
        path = os.path.expanduser(path.strip())
        return _mac_run(f"cat '{path}' 2>/dev/null || echo 'File not found: {path}'")

    @register("write_file")
    def _mac_write_file(text):
        rest = text.replace("write file", "").replace("write", "").strip()
        if "::" in rest:
            path, content = rest.split("::", 1)
        else:
            parts = rest.rsplit(" ", 1)
            if len(parts) < 2: return "Usage: write_file path::content"
            path, content = parts
        path = os.path.expanduser(path.strip())
        escaped = content.strip().replace("'", "'\\''")
        _mac_run(f"mkdir -p '{os.path.dirname(path)}' 2>/dev/null; printf '%s' '{escaped}' > '{path}'")
        return f"Written to {path}"

    @register("list_dir")
    def _mac_list_dir(text):
        path = text.replace("list dir", "").replace("list", "").replace("directory", "").strip() or "."
        path = os.path.expanduser(path)
        return _mac_run(f"ls -la '{path}' 2>/dev/null | head -40 || echo 'Not found: {path}'")

    @register("run_python")
    def _mac_run_python(text):
        code = text.replace("run python", "").replace("run_python", "").strip() or text
        return _mac_run(f"python3 -c '{code.replace(chr(39), chr(39)+'\\'+chr(39)+chr(39))}'", timeout=30)

    @register("run_shell")
    def _mac_run_shell(text):
        cmd = text.replace("run shell", "").replace("run_shell", "").strip() or text
        return _mac_run(cmd, timeout=30)

    @register("take_screenshot")
    def _mac_take_screenshot(_):
        return _mac_run("screencapture -x ~/Desktop/jarvis_screenshot.png 2>/dev/null; echo 'Screenshot: ~/Desktop/jarvis_screenshot.png'")

    # ── Network & Smart Home ────────────────────────────────────

    @register("network_scan_quick")
    def _mac_net_scan_quick(_):
        r = _mac_run("arp -a 2>/dev/null")
        count = r.count(") at ") if r else 0
        return f"Devices on LAN:\n{r}\n{count} devices found" if r else "No devices found"

    @register("network_scan_deep")
    def _mac_net_scan_deep(_):
        subnet = _mac_run("ipconfig getifaddr en0 2>/dev/null || ifconfig en0 | grep 'inet ' | awk '{print $2}'")
        if not subnet: subnet = _mac_run("ipconfig getifaddr en1 2>/dev/null || ifconfig en1 | grep 'inet ' | awk '{print $2}'")
        if not subnet: return "Could not determine local IP"
        base = ".".join(subnet.split(".")[:3]) + ".0/24"
        r = _mac_run(f"nmap -sn -T4 --max-retries 1 --host-timeout 5 {base} 2>/dev/null | grep -E 'Nmap|Host|MAC' | head -60")
        return f"Deep scan of {base}:\n{r}" if r else f"No hosts found on {base}"

    @register("network_device_info")
    def _mac_net_device_info(text):
        ip = text.strip().split()[-1] if text.strip() else ""
        if not ip: return "Specify an IP address"
        r = _mac_run(f"nmap -sV -T4 --host-timeout 15 -p 22,80,443,8080,8443,8123,9981,502,1883,1900,5353,9999,6053 {ip} 2>/dev/null | grep -E 'PORT|open|closed' | head -20")
        return f"Device info for {ip}:\n{r}" if r else f"No info for {ip}"

    @register("wake_on_lan")
    def _mac_wol(text):
        mac = text.replace("wake", "").replace("wol", "").replace("wake on lan", "").strip()
        if not mac: return "Which MAC address?"
        import socket as _sock, struct as _struct
        mac_clean = mac.replace(":", "").replace("-", "").strip()
        if len(mac_clean) != 12: return f"Invalid MAC: {mac}"
        packet = b"\xff" * 6 + bytes.fromhex(mac_clean) * 16
        try:
            with _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM) as s:
                s.setsockopt(_sock.SOL_SOCKET, _sock.SO_BROADCAST, 1)
                s.sendto(packet, ("192.168.0.255", 9))
                s.sendto(packet, ("255.255.255.255", 9))
            return f"WoL packet sent to {mac}"
        except Exception as e:
            return f"WoL error: {e}"

    @register("smart_home_discover")
    def _mac_sh_discover(_):
        """Probe for known smart home devices on the LAN."""
        try:
            from smart_home_manager import run_discovery
            devices = run_discovery()
            lines = [f"🏠 Smart Home: {len(devices)} devices found"]
            for d in devices[:40]:
                status = "🟢" if d.get("status") == "online" else "⚪"
                lines.append(f"{status} {d.get('name','?')} ({d.get('type','?')}) @ {d.get('ip','?')} [{d.get('protocol','?')}]")
            return "\n".join(lines)
        except Exception:
            pass
        ips = _mac_run("arp -a 2>/dev/null | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b' | head -20").split()
        found = []
        for ip in ips:
            for port, service in [(80,"HTTP"),(443,"HTTPS"),(8123,"HomeAssistant"),(9981,"TVHeadend"),
                                  (6053,"ESPHome"),(9999,"Kasa"),(502,"Modbus"),(1883,"MQTT"),
                                  (8080,"HTTP-ALT"),(8443,"HTTPS-ALT")]:
                r = _mac_run(f"curl -s --max-time 2 http://{ip}:{port}/ 2>/dev/null | head -1")
                r2 = _mac_run(f"curl -s --max-time 2 https://{ip}:{port}/ 2>/dev/null | head -1")
                if r or r2:
                    body = (r or r2)[:100].replace("\n", " ").strip()
                    found.append(f"{ip}:{port} ({service}) — {body}")
                    break
        if found:
            return "Smart home devices:\n" + "\n".join(found)
        devices = _mac_run("arp -a 2>/dev/null | head -20")
        return f"Scanned {len(ips)} hosts. No known smart home services found.\nDevices:\n{devices}"

    @register("smart_home_control")
    def _mac_sh_control(text):
        """Control smart home devices via HTTP API.
        Format: device_ip action [params]
        Actions: on, off, toggle, status, color <hex>, brightness <0-255>
        """
        parts = text.split()
        if len(parts) < 2: return "Usage: smart_home_control <ip> <on|off|toggle|status>"
        target = parts[0]
        action = parts[1].lower()
        rest = " ".join(parts[2:])

        try:
            from smart_home_manager import control_device, control_by_ip
            r = control_device(target, action, rest)
            if "not found" in r:
                r = control_by_ip(target, action, rest)
            return r
        except Exception:
            pass

        ip = target
        results = []

        # Try Philips Hue (bridge sends to all lights)
        hue_result = _mac_run(f"curl -s --max-time 3 http://{ip}/api/newdeveloper/lights 2>/dev/null")
        if hue_result and hue_result != "404":
            state = "true" if action == "on" else "false"
            if action == "toggle":
                r = _mac_run(f"curl -s --max-time 3 http://{ip}/api/newdeveloper/lights/1 2>/dev/null")
                state = "false" if '"on":true' in r else "true"
            hue_cmd = _mac_run(f"curl -s -X PUT --max-time 3 -H 'Content-Type: application/json' -d '{{\"on\":{state}}}' http://{ip}/api/newdeveloper/groups/0/action 2>/dev/null")
            results.append(f"Hue: {'on' if state == 'true' else 'off'}")

        # Try ESPHome / WLED
        if action == "toggle":
            wled = _mac_run(f"curl -s --max-time 2 http://{ip}/toggle 2>/dev/null")
            if wled: results.append("WLED toggled")
        elif action == "on":
            wled = _mac_run(f"curl -s --max-time 2 -H 'Content-Type: application/json' -d '{{\"on\":true}}' http://{ip}/json/state 2>/dev/null")
            if not wled: wled = _mac_run(f"curl -s --max-time 2 http://{ip}/win& 2>/dev/null")
            if wled: results.append("Device turned on")
        elif action == "off":
            wled = _mac_run(f"curl -s --max-time 2 -H 'Content-Type: application/json' -d '{{\"on\":false}}' http://{ip}/json/state 2>/dev/null")
            if not wled: wled = _mac_run(f"curl -s --max-time 2 http://{ip}/win& 2>/dev/null")
            if wled: results.append("Device turned off")
        elif action == "status":
            st = _mac_run(f"curl -s --max-time 2 http://{ip}/json/info 2>/dev/null | head -5")
            if not st: st = _mac_run(f"curl -s --max-time 2 http://{ip}/ 2>/dev/null | head -5")
            results.append(f"Status:\n{st[:300]}")

        # Try brightness
        if rest and action == "brightness" and rest.isdigit():
            bri = min(255, max(0, int(rest)))
            _mac_run(f"curl -s -X PUT --max-time 2 -H 'Content-Type: application/json' -d '{{\"bri\":{bri},\"on\":true}}' http://{ip}/api/newdeveloper/groups/0/action 2>/dev/null")
            _mac_run(f"curl -s --max-time 2 -H 'Content-Type: application/json' -d '{{\"bri\":{bri}}}' http://{ip}/json/state 2>/dev/null")
            results.append(f"Brightness: {bri}")

        if not results:
            results.append(f"No known smart device protocols responded at {ip}")

        return "\n".join(results)

    @register("set_device_credentials")
    def _mac_set_device_creds(text):
        """Set Tapo device credentials. Usage: set_device_credentials <username> <password>"""
        parts = text.strip().split()
        if len(parts) < 2:
            return "Usage: set_device_credentials <tapo_username> <tapo_password>"
        username = parts[0]
        password = parts[1]
        os.environ["TAPO_USERNAME"] = username
        os.environ["TAPO_PASSWORD"] = password
        # Reset the Tapo client
        try:
            import tapo_client
            tapo_client._tapo = None
        except:
            pass
        return f"✅ Tapo credentials set for user: {username}\nDevice control is now active."

    @register("device_by_name")
    def _mac_device_by_name(text):
        """Control a device by name. Usage: device_by_name <name> <on|off|toggle>"""
        parts = text.strip().split()
        if len(parts) < 2:
            return "Usage: device_by_name <device_name> <on|off|toggle>"
        device_name = parts[0].lower()
        action = parts[1].lower()

        try:
            from device_manager import DeviceManager
            dm = DeviceManager()
            devices = dm.get_all_devices()

            # Find matching device
            target = None
            for d in devices:
                name = d.get("name", "").lower()
                # Exact match
                if name == device_name:
                    target = d
                    break
                # Partial match
                if device_name in name or name in device_name:
                    target = d
                    break
                # Word match
                if any(w in name for w in device_name.split()):
                    target = d
                    break

            if not target:
                device_list = ", ".join(d.get("name", "?") for d in devices[:10])
                return f"Device '{device_name}' not found. Available: {device_list or 'none discovered yet'}"

            ip = target.get("ip", "")
            if not ip:
                return f"Device '{target.get('name')}' has no IP address assigned."

            # Control via Tapo
            from tapo_client import TapoClient
            client = TapoClient()
            if action == "on":
                result = client.turn_on(ip)
            elif action == "off":
                result = client.turn_off(ip)
            elif action == "toggle":
                result = client.toggle(ip)
            elif action == "status":
                result = client.get_device_info(ip)
            else:
                return f"Unknown action: {action}. Use: on, off, toggle, status"

            return f"✅ {target.get('name')} ({ip}) → {action.upper()}\n{result}"
        except Exception as e:
            return f"Device control error: {e}"

    # ── Phone & Notifications ────────────────────────────────────

    @register("phone_notify")
    def _mac_phone_notify(text):
        """Send push notification to phone via ntfy.sh."""
        msg = text.replace("notify", "").replace("phone", "").replace("send", "").strip()
        if not msg: msg = "Hello from J.A.R.V.I.S."
        topic = f"jarvis_{_mac_run('whoami').strip()}"
        r = _mac_run(f'curl -s -d "{msg[:500].replace(chr(34),chr(39))}" "https://ntfy.sh/{topic}" 2>/dev/null')
        if r:
            return f"Notification sent to ntfy.sh/{topic}"
        # Fallback to Pushover if configured
        token = os.environ.get("PUSHOVER_TOKEN", "")
        user = os.environ.get("PUSHOVER_USER", "")
        if token and user:
            _mac_run(f'curl -s --max-time 5 -F "token={token}" -F "user={user}" -F "title=J.A.R.V.I.S." -F "message={msg[:500].replace(chr(34),chr(39))}" https://api.pushover.net/1/messages.json 2>/dev/null')
            return "Notification sent via Pushover"
        return "To receive phone notifications, install ntfy.sh on your phone and subscribe to: " + topic

    @register("camera_snap")
    def _mac_camera_snap(_):
        """Take a photo using the Mac camera (requires imagesnap or ffmpeg)."""
        r = _mac_run("which imagesnap 2>/dev/null")
        path = os.path.expanduser("~/Desktop/jarvis_cam.jpg")
        if r:
            _mac_run(f"imagesnap -w 1 '{path}' 2>/dev/null")
        else:
            _mac_run(f"ffmpeg -f avfoundation -framerate 1 -video_size 640x480 -i '0' -frames:v 1 '{path}' -y 2>/dev/null")
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            return f"Photo saved to {path}"
        return "Camera not available (install imagesnap: brew install imagesnap)"

    # ── System Monitoring ────────────────────────────────────────

    @register("who_is_online")
    def _mac_who_online(_):
        """List currently active users/computers on the network."""
        r = _mac_run("smbutil status -v 2>/dev/null | head -20")
        arp = _mac_run("arp -a 2>/dev/null | grep -v incomplete | head -20")
        return f"Network activity:\n{r}\n\nActive devices:\n{arp}" if r else f"Active devices:\n{arp}"

    @register("system_load")
    def _mac_system_load(_):
        cpu = _mac_run("top -l 1 -n 0 -nocolor 2>/dev/null | grep 'CPU usage'")
        mem = _mac_run("memory_pressure 2>/dev/null | head -5")
        disk = _mac_run("df -h / 2>/dev/null | tail -1")
        net = _mac_run("netstat -ib 2>/dev/null | grep -E 'en0|en1' | head -5")
        upt = _mac_run("uptime")
        return f"CPU: {cpu}\nMemory: {mem}\nDisk: {disk}\nNetwork:\n{net}\nUptime: {upt}"

    # ── UI Automation (Computer Vision + Mouse/Keyboard) ────────

    @register("ui_screenshot")
    def _mac_ui_screenshot(_):
        """Take screenshot and return path."""
        _mac_run("screencapture -x /tmp/jv_ui_screen.png 2>/dev/null")
        return "/tmp/jv_ui_screen.png"

    @register("ui_get_text")
    def _mac_ui_get_text(_):
        """OCR the screen and return all visible text."""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
            from ui_automation import get_screen_text
            return get_screen_text()
        except:
            _mac_run("screencapture -x /tmp/jv_ui_screen.png 2>/dev/null")
            r = _mac_run("which tesseract && tesseract /tmp/jv_ui_screen.png stdout 2>/dev/null || echo 'OCR not available'")
            return r or "Tesseract not installed (brew install tesseract)"

    @register("ui_find")
    def _mac_ui_find(text):
        """Find text on screen and return coordinates."""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
            from ui_automation import find_text_on_screen
            el = find_text_on_screen(text)
            if el:
                return f"Found '{el['text']}' at ({el['x']},{el['y']}) size {el['width']}x{el['height']}"
            return f"'{text}' not found on screen"
        except:
            return f"UI find error for '{text}'"

    @register("ui_click")
    def _mac_ui_click(text):
        """Click at coordinates. Format: 'x y' or 'x y button'."""
        parts = text.split()
        if len(parts) < 2: return "Usage: ui_click x y [left|right|double]"
        x, y = parts[0], parts[1]
        btn = parts[2].lower() if len(parts) > 2 else "left"
        if btn == "right":
            _mac_run(f"osascript -e 'tell application \"System Events\" to click at {{{x},{y}}}' 2>/dev/null")
        elif btn == "double":
            _mac_run(f"osascript -e 'tell application \"System Events\" to double click at {{{x},{y}}}' 2>/dev/null")
        else:
            _mac_run(f"osascript -e 'tell application \"System Events\" to click at {{{x},{y}}}' 2>/dev/null")
        return f"Clicked ({x},{y})"

    @register("ui_click_text")
    def _mac_ui_click_text(text):
        """Find text on screen and click it."""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
            from ui_automation import click_text
            found = click_text(text, timeout=5)
            return f"Clicked '{text}'" if found else f"'{text}' not found"
        except:
            return f"Click text error for '{text}'"

    @register("ui_type")
    def _mac_ui_type(text):
        """Type text using macOS keystroke simulation."""
        t = text.replace("type", "").replace("ui_type", "").strip() or text
        escaped = t[:300].replace(chr(34), chr(39))
        _mac_run(f"osascript -e 'tell application \"System Events\" to keystroke \"{escaped}\"' 2>/dev/null")
        return f"Typed: '{t[:50]}'"

    @register("ui_handwrite")
    def _mac_ui_handwrite(text):
        """Handwrite text using bezier strokes. Format: text|start_x|start_y"""
        parts = text.split("|")
        txt = parts[0]
        xs = int(parts[1]) if len(parts) > 1 else 400
        ys = int(parts[2]) if len(parts) > 2 else 400
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
            from ui_automation import handwrite_text
            handwrite_text(txt, xs, ys)
            return f"Handwriting: '{txt[:50]}' at ({xs},{ys})"
        except:
            return f"Handwriting error for '{txt[:30]}'"

    @register("ui_drag")
    def _mac_ui_drag(text):
        """Drag from (x1,y1) to (x2,y2). Format: 'x1 y1 x2 y2'."""
        parts = text.split()
        if len(parts) < 4: return "Usage: ui_drag x1 y1 x2 y2"
        x1, y1, x2, y2 = parts[:4]
        _mac_run(f"osascript -e 'tell application \"System Events\" to drag from {{{x1},{y1}}} to {{{x2},{y2}}}' 2>/dev/null")
        return f"Dragged ({x1},{y1}) -> ({x2},{y2})"

    @register("ui_activate_app")
    def _mac_ui_activate(text):
        """Bring an app to the foreground."""
        _mac_run(f"osascript -e 'tell application \"{text}\" to activate' 2>/dev/null")
        return f"Activated {text}"

    @register("ui_app_running")
    def _mac_ui_running(text):
        """Check if an app is running."""
        r = _mac_run(f"osascript -e 'tell application \"System Events\" to exists process \"{text}\"' 2>/dev/null")
        return f"{text} is {'running' if 'true' in r else 'not running'}"

    # ── Phone Bridge (ADB over WiFi) ─────────────────────────────

    _adb_cache: str | None = None

    def _mac_adb(cmd: str) -> str:
        r = _mac_run(f"adb shell {cmd} 2>/dev/null", timeout=15)
        if r: return r
        # Try to auto-connect known phones
        global _adb_cache
        if _adb_cache is None:
            ip = _mac_run("arp -a 2>/dev/null | grep -i 'android\|oneplus\|samsung\|pixel\|xiaomi\|motorola' | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b' | head -1")
            if ip:
                _mac_run(f"adb connect {ip}:5555 2>/dev/null", timeout=5)
                _adb_cache = ip
                r = _mac_run(f"adb shell {cmd} 2>/dev/null", timeout=15)
                if r: return r
        _adb_cache = ""
        return "ADB not available. Connect phone: adb connect <phone_ip>:5555"

    @register("phone_adb_connect")
    def _mac_phone_connect(text):
        """Connect to phone via ADB over WiFi."""
        ip = text.strip()
        if not ip: return "Usage: phone_adb_connect <phone_ip>"
        r = _mac_run(f"adb connect {ip}:5555 2>/dev/null", timeout=10)
        global _adb_cache
        _adb_cache = ip
        return f"ADB connected to {ip}" if r else f"Connection failed for {ip}"

    @register("phone_read_sms")
    def _mac_phone_sms(_):
        """Read recent SMS messages from connected Android phone."""
        r = _mac_adb("content query --uri content://sms/inbox --projection address,body,date --sort date DESC --limit 10 2>/dev/null")
        if r: return r
        return _mac_adb("content query --uri content://sms --projection address,body,date --sort date DESC --limit 5 2>/dev/null")

    @register("phone_get_notifications")
    def _mac_phone_notifications(_):
        """Get recent notifications from connected Android phone."""
        r = _mac_adb("dumpsys notification --naked 2>/dev/null | grep -E 'tickerText=|title=|text=' | head -60")
        if not r:
            r = _mac_adb("dumpsys notification 2>/dev/null | grep -A 2 'NotificationRecord' | head -40")
        return r or "No notifications or ADB not connected"

    @register("phone_call_log")
    def _mac_phone_call_log(_):
        """Read recent call log from connected Android phone."""
        return _mac_adb("content query --uri content://call_log/calls --projection number,type,duration,date --sort date DESC --limit 10 2>/dev/null")

    @register("phone_battery")
    def _mac_phone_battery(_):
        """Get battery status of connected Android phone."""
        r = _mac_adb("shell dumpsys battery 2>/dev/null | grep -E 'level|status|powered'")
        return r or "Phone battery info not available"

    @register("phone_contacts")
    def _mac_phone_contacts(_):
        """Read recent contacts from connected Android phone."""
        return _mac_adb("content query --uri content://contacts/phones/ --projection display_name,number --sort data_id DESC --limit 20 2>/dev/null")

    @register("phone_location")
    def _mac_phone_location(_):
        """Get last known location from connected Android phone."""
        r = _mac_adb("shell dumpsys location 2>/dev/null | grep -E 'last.*Location|LastKnownLocation' | head -5")
        return r or "Location not available (may need GPS enabled)"

    # ── Home Assistant Integration ───────────────────────────────

    @register("ha_discover")
    def _mac_ha_discover(_):
        """Discover Home Assistant instance on LAN."""
        ips = _mac_run("arp -a 2>/dev/null | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b' | head -20").split()
        for ip in ips:
            r = _mac_run(f"curl -s --max-time 2 http://{ip}:8123/api/ 2>/dev/null")
            if r and "message" in r:
                return f"Home Assistant found at {ip}:8123"
            r2 = _mac_run(f"curl -s --max-time 2 http://{ip}:8123/ 2>/dev/null | head -1")
            if r2 and "home" in r2.lower():
                return f"Home Assistant found at {ip}:8123"
        return "No Home Assistant instance found on LAN"

    @register("ha_status")
    def _mac_ha_status(_):
        """Get Home Assistant API status."""
        return _ha_api_call("", "GET")

    @register("ha_sensors")
    def _mac_ha_sensors(_):
        """List all Home Assistant sensor states."""
        return _ha_api_call("states", "GET")

    @register("ha_control")
    def _mac_ha_control(text):
        """Control a Home Assistant entity. Format: entity_id state or entity_id on|off|toggle."""
        parts = text.split()
        if len(parts) < 2: return "Usage: ha_control entity_id state"
        return _ha_api_call(f"states/{parts[0]}", "POST", {"state": parts[1]})

    def _ha_api_call(endpoint: str, method: str = "GET", data: dict | None = None) -> str:
        token = os.environ.get("HA_TOKEN", "")
        host = os.environ.get("HA_HOST", "")
        if not host:
            ips = _mac_run("arp -a 2>/dev/null | grep -oE '\\b([0-9]{1,3}\\.){3}[0-9]{1,3}\\b' | head -20").split()
            for ip in ips:
                r = _mac_run(f"curl -s --max-time 2 http://{ip}:8123/api/ 2>/dev/null")
                if r and "message" in r:
                    host = f"http://{ip}:8123"
                    break
        if not host: return "Home Assistant not found on LAN"
        url = f"{host}/api/{endpoint}" if endpoint else host + "/api/"
        headers = f'-H "Authorization: Bearer {token}"' if token else ""
        if method == "POST" and data:
            payload = data.get("state", "")
            r = _mac_run(f'curl -s --max-time 5 -X POST {headers} -H "Content-Type: application/json" -d \'{{"state":"{payload}"}}\' "{url}" 2>/dev/null')
        else:
            r = _mac_run(f"curl -s --max-time 5 {headers} '{url}' 2>/dev/null | head -50")
        return r or f"No response from {url}"

    # ── Cognitive Surveillance ───────────────────────────────────

    @register("cognitive_scan")
    def _mac_cognitive_scan(_):
        """Comprehensive environment scan: processes, windows, network, system."""
        lines = []
        lines.append(f"=== COGNITIVE ENVIRONMENT SCAN ===")
        lines.append(f"Time: {_mac_run('date')}")
        lines.append(f"Uptime: {_mac_run('uptime')}")
        lines.append(f"Users: {_mac_run('who')}")
        lines.append(f"Processes (top 5 by CPU): {_mac_run('ps aux --sort=-%cpu | head -6')}")
        _winc = """osascript -e 'tell application "System Events" to get name of every process whose visible is true' 2>/dev/null"""
        lines.append(f"Visibility: {_mac_run(_winc)}")
        wifi = _mac_run("/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null | grep -E 'SSID|agrCtlRSSI|state'")
        lines.append(f"WiFi: {wifi}")
        lines.append(f"Network neighbours: {_mac_run('arp -a 2>/dev/null')}")
        lines.append(f"Disk: {_mac_run('df -h / 2>/dev/null | tail -1')}")
        return "\n".join(lines)

    @register("cognitive_insight")
    def _mac_cognitive_insight(_):
        """Generate a synthesized insight about the user's environment."""
        scan = _mac_cognitive_scan(None)
        try:
            import urllib.request
            payload = json.dumps({"text": f"Analyze this environment scan and produce ONE concise, useful insight (1 sentence):\n{scan[:800]}",
                                  "user_id": "jarvis", "tier": "free"}).encode()
            req = urllib.request.Request(f"{_mac_run('echo $HF_API')}/api/text/chat", data=payload,
                                          headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read())
                return f"[INSIGHT] {resp.get('text', 'Analysis complete')[:300]}"
        except:
            return "[INSIGHT] Environment scanned. All systems nominal."

    @register("cognitive_monitor")
    def _mac_cognitive_monitor(text):
        """Start or stop ambient monitoring thread. Format: 'start' or 'stop' or 'status'."""
        import threading
        action = text.strip().lower()
        if not hasattr(_mac_cognitive_monitor, "_thread"):
            _mac_cognitive_monitor._thread = None
            _mac_cognitive_monitor._running = False
        if action == "start" and not (_mac_cognitive_monitor._running and _mac_cognitive_monitor._thread and _mac_cognitive_monitor._thread.is_alive()):
            _mac_cognitive_monitor._running = True
            def _monitor_loop():
                import time
                while _mac_cognitive_monitor._running:
                    _mac_cognitive_scan(None)
                    time.sleep(120)
            _mac_cognitive_monitor._thread = threading.Thread(target=_monitor_loop, daemon=True)
            _mac_cognitive_monitor._thread.start()
            return "Cognitive monitoring started (interval: 120s)"
        elif action == "stop":
            _mac_cognitive_monitor._running = False
            return "Cognitive monitoring stopped"
        else:
            running = _mac_cognitive_monitor._thread and _mac_cognitive_monitor._thread.is_alive() if _mac_cognitive_monitor._thread else False
            return f"Cognitive monitoring: {'running' if running else 'stopped'}"

    @register("cognitive_alert")
    def _mac_cognitive_alert(text):
        """Set a cognitive alert condition. Format: 'condition' e.g. 'cpu > 90' or 'battery < 20'."""
        condition = text.strip()
        if not condition: return "Usage: cognitive_alert <condition>"
        import threading, time
        if not hasattr(_mac_cognitive_alert, "_thread"):
            _mac_cognitive_alert._thread = None
            _mac_cognitive_alert._running = False
            _mac_cognitive_alert._condition = ""
        if not (_mac_cognitive_alert._running and _mac_cognitive_alert._thread and _mac_cognitive_alert._thread.is_alive()):
            _mac_cognitive_alert._running = True
            _mac_cognitive_alert._condition = condition
            def _alert_loop():
                while _mac_cognitive_alert._running:
                    try:
                        if "cpu" in _mac_cognitive_alert._condition.lower():
                            r = _mac_run("ps aux --sort=-%cpu | head -2 | tail -1 | awk '{print $3}'")
                            if r and float(r) > 90:
                                _mac_run(f"""osascript -e 'display notification "CPU at {r}%!" with title "J.A.R.V.I.S. Alert"' 2>/dev/null""")
                        if "battery" in _mac_cognitive_alert._condition.lower():
                            r = _mac_run("pmset -g batt 2>/dev/null | grep -E '\\d+%' | grep -oE '\\d+'")
                            if r and int(r) < 20:
                                _mac_run(f"""osascript -e 'display notification "Battery at {r}%!" with title "J.A.R.V.I.S. Alert"' 2>/dev/null""")
                    except: pass
                    time.sleep(60)
            _mac_cognitive_alert._thread = threading.Thread(target=_alert_loop, daemon=True)
            _mac_cognitive_alert._thread.start()
            return f"Cognitive alert set: '{condition}'"
        return f"Alert already running: {_mac_cognitive_alert._condition}"


# ═══════════════════════════════════════════════════════════════════
#  Linux Executors — override Windows actions when running on Linux
#  (registered last so they win over Windows versions)
# ═══════════════════════════════════════════════════════════════════

elif sys.platform == "linux":
    import subprocess as _sp

    def _linux_run(cmd: str, timeout=15) -> str:
        try:
            r = _sp.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return (r.stdout or r.stderr or f"exit {r.returncode}").strip()
        except Exception as e:
            return f"Error: {e}"

    @register("screenshot")
    def _linux_screenshot(_):
        return "Screenshot not available on cloud server. Use relay agent for local screenshots."

    @register("clipboard_show")
    def _linux_clipboard_show(_):
        c = _linux_run("xclip -selection clipboard -o 2>/dev/null || pbpaste 2>/dev/null || echo ''")
        return f"Clipboard: {c[:500] or 'empty (no display)'}"

    @register("clipboard_copy")
    def _linux_clipboard_copy(text):
        c = text.replace("copy", "").replace("clipboard", "").strip() or "test"
        _linux_run(f'echo "{c[:100]}" | xclip -selection clipboard 2>/dev/null')
        return f"Copied: {c[:50]}"

    @register("vol_level")
    def _linux_vol_level(_):
        r = _linux_run("amixer get Master 2>/dev/null | grep -oP '\\d+%' | head -1")
        return f"Volume: {r or 'unknown'}"

    @register("vol_up")
    def _linux_vol_up(_):
        _linux_run("amixer set Master 10%+ 2>/dev/null")
        return "Volume up"

    @register("vol_down")
    def _linux_vol_down(_):
        _linux_run("amixer set Master 10%- 2>/dev/null")
        return "Volume down"

    @register("vol_mute")
    def _linux_vol_mute(_):
        _linux_run("amixer set Master toggle 2>/dev/null")
        return "Mute toggled"

    @register("vol_set")
    def _linux_vol_set(text):
        import re as _re
        m = _re.search(r"(\d+)", text)
        if not m: return "Specify a number."
        lvl = min(100, max(0, int(m.group(1))))
        _linux_run(f"amixer set Master {lvl}% 2>/dev/null")
        return f"Volume set to {lvl}%"

    @register("brightness_up")
    def _linux_brightness_up(_):
        return "Brightness control not available on cloud server."

    @register("brightness_down")
    def _linux_brightness_down(_):
        return "Brightness control not available on cloud server."

    @register("brightness_set")
    def _linux_brightness_set(_):
        return "Brightness control not available on cloud server."

    @register("display_info")
    def _linux_display_info(_):
        r = _linux_run("xrandr 2>/dev/null | head -5 || echo 'No display'")
        return f"Display: {r}"

    @register("send_notification")
    def _linux_notify(text):
        t = text.replace("send notification", "").replace("notify", "").replace("notification", "").strip()
        if not t: t = "Hello from JARVIS"
        # Try notify-send (Linux desktop), fall back to terminal message
        _linux_run(f'notify-send "JARVIS" "{t[:200]}" 2>/dev/null')
        return f"Notification: {t[:60]}"

    @register("lock")
    def _linux_lock(_):
        _linux_run("xdg-screensaver lock 2>/dev/null || gnome-screensaver-command -l 2>/dev/null || loginctl lock-session 2>/dev/null")
        return "Locking screen..."

    @register("time")
    def _linux_time(_):
        return __import__("datetime").datetime.now().strftime("%A, %B %d, %Y — %I:%M %p")

    @register("whoami")
    def _linux_whoami(_):
        return f"User: {_linux_run('whoami')}"

    @register("uptime")
    def _linux_uptime(_):
        return _linux_run("uptime -p 2>/dev/null || uptime")

    @register("system_info")
    def _linux_sysinfo(_):
        os_v = _linux_run("cat /etc/os-release 2>/dev/null | head -2")
        cpu = _linux_run("lscpu 2>/dev/null | grep 'Model name' | head -1")
        mem = _linux_run("free -h 2>/dev/null | head -2")
        return f"OS: {os_v}\nCPU: {cpu}\nMemory:\n{mem}"

    @register("disk_info")
    def _linux_disk(_):
        return _linux_run("df -h / 2>/dev/null | tail -1")

    @register("memory_info")
    def _linux_mem(_):
        return _linux_run("free -h 2>/dev/null | head -2")

    @register("process_list")
    def _linux_procs(_):
        return _linux_run("ps aux --sort=-%cpu | head -15")

    @register("network_info")
    def _linux_net(_):
        return _linux_run("ip addr show 2>/dev/null | grep 'inet ' || ifconfig 2>/dev/null | grep 'inet '")

    @register("wifi_list")
    def _linux_wifi(_):
        return _linux_run("nmcli device wifi list 2>/dev/null || iwlist scanning 2>/dev/null | head -20 || echo 'No WiFi tools available'")

    @register("battery_status")
    def _linux_battery(_):
        return _linux_run("cat /sys/class/power_supply/BAT*/capacity 2>/dev/null || echo 'No battery detected'")

    @register("open_app")
    def _linux_open_app(text):
        name = text.lower().strip()
        _linux_run(f"xdg-open https://{name} 2>/dev/null || echo 'Cannot open {name}'")
        return f"Opening {name}..."

    @register("open_url")
    def _linux_open_url(text):
        url = text.replace("open", "").replace("go to", "").replace("url", "").replace("website", "").strip()
        if not url: return "Which URL?"
        if not url.startswith("http"): url = "https://" + url
        _linux_run(f"xdg-open '{url}' 2>/dev/null")
        return f"Opening {url[:70]}..."

    @register("search")
    def _linux_search(text):
        from urllib.parse import quote as _uq2
        q = text.replace("search", "").replace("google", "").replace("look up", "").strip() or text
        _linux_run(f"xdg-open 'https://google.com/search?q={_uq2(q)}' 2>/dev/null")
        return f'Searching for "{q}"...'

    @register("cognitive_scan")
    def _linux_cognitive_scan(_):
        lines = []
        lines.append(f"=== COGNITIVE ENVIRONMENT SCAN ===")
        lines.append(f"Time: {_linux_run('date')}")
        lines.append(f"Uptime: {_linux_run('uptime -p 2>/dev/null || uptime')}")
        lines.append(f"Users: {_linux_run('who')}")
        lines.append(f"Processes (top 5 by CPU): {_linux_run('ps aux --sort=-%cpu | head -6')}")
        lines.append(f"Disk: {_linux_run('df -h / 2>/dev/null | tail -1')}")
        lines.append(f"Network: {_linux_run('ip route 2>/dev/null | head -3')}")
        return "\n".join(lines)
