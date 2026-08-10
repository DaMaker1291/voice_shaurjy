"""
Unified Tool Registry — gives the LLM a single catalog of EVERY tool it can use:
  - 276+ built-in OS actions (open app, screenshot, clipboard, etc.)
  - MCP tools (when servers are connected)
  - Smart home devices (lights, plugs, vacuum, locks, cameras, etc.)
  - External device commands (phone, relay, Alexa, etc.)
  - Computer use (mouse, keyboard, screen vision)
  - Web tools (search, browse, email compose)
"""

import json
from typing import Optional


def build_tool_catalog(user_id: str = "local") -> str:
    """Build a concise tool catalog string for the LLM system prompt.
    Keeps it short so it fits in the LLM context window."""
    sections = []

    # Core tools — the LLM needs to know these exist
    sections.append(
        "TOOL CATALOG (use execute_unified_tool tool or JSON block to call):\n"
        "OS: open_app, close_app, app_list, app_running, screenshot, clipboard, "
        "lock, shutdown, restart, sleep, volume_up, volume_down, mute, brightness_set\n"
        "BROWSER: browser (open URL in Chrome), browser_open (with profile), browser_read (page text), "
        "browser_click (element by text), browser_fill (form field), browser_prices (extract prices)\n"
        "SEARCH: search (web search), fetch_search (real results), search_news, search_wiki, search_youtube, search_maps\n"
        "FILES: file_open, file_create, file_delete, file_search, folder_open, folder_create\n"
        "EMAIL: send_email, compose_email, calendar_add, calendar_events\n"
        "MESSAGING: send_whatsapp, send_telegram, notification\n"
        "SYSTEM: time, battery_status, network_status, sys_info, cpu_info, disk\n"
        "COMPUTER USE: ai_computer_task (autonomous screen control), "
        "type_text, send_keystrokes, click, scroll\n"
        "VISION: scan_screen (OCR desktop), click_screen (OCR click), type_screen (OCR type)\n"
        "SMART HOME: smart_home_control, scene_activate\n"
        "VM: vm_task (run in isolated virtual desktop)\n"
        "MEDIA: play, pause, stop, next_track, prev_track\n"
        "DEVICES: webcam, mic, speaker_test\n"
        "RULES:\n"
        "  - NEVER handle money/payments — navigate to checkout, show receipt, let user pay\n"
        "  - NEVER enter card numbers, CVV, bank details, passwords\n"
        "  - NEVER create accounts — open browser for user to do it\n"
        "  - When blocked (login/CAPTCHA/payment) → notify user, bring to screen\n"
        "To call a tool, include JSON: {\"tool\": \"tool_name\", \"params\": \"arg\"}\n"
        "Multiple tools: {\"tool_calls\": [{\"tool\": \"t1\"}, {\"tool\": \"t2\", \"params\": \"a\"}]}"
    )

    # MCP tools — dynamic, from connected servers
    try:
        from mcp_client import get_mcp_client
        client = get_mcp_client()
        mcp_tools = client.get_tools()
        if mcp_tools:
            mcp_names = [t.name for t in mcp_tools[:20]]  # Cap at 20
            sections.append(
                f"MCP TOOLS ({len(mcp_tools)} available via connected servers):\n"
                + ", ".join(mcp_names)
                + "\nCall with: {\"tool\": \"mcp_<name>\", \"params\": {...}}"
            )
    except Exception:
        pass

    return "\n\n".join(sections)


def get_tool_names() -> list[str]:
    """Get flat list of all tool/action names."""
    names = []
    try:
        from actions import get_all_actions
        names.extend(get_all_actions().keys())
    except Exception:
        pass
    try:
        from mcp_client import get_mcp_client
        names.extend(t.name for t in get_mcp_client().get_tools())
    except Exception:
        pass
    return names


def execute_unified_tool(tool_name: str, params: str, user_id: str = "local") -> str:
    """Execute any tool by name — tries MCP first, then built-in actions.
    Includes alias mapping so LLM can use natural names."""
    # Alias mapping: LLM-friendly names → actual action IDs
    ALIASES = {
        "web_search": "search",
        "weblookup": "search",
        "web_page_open": "browser",
        "web_browse": "browser",
        "open_browser": "browser",
        "open_chrome": "browser",
        "play_music": "play",
        "pause_music": "pause",
        "stop_music": "stop",
        "volume_up": "vol_up",
        "volume_down": "vol_down",
        "mute_audio": "mute",
        "unmute_audio": "unmute",
        "shutdown_pc": "shutdown",
        "restart_pc": "restart",
        "sleep_pc": "sleep",
        "lock_screen": "lock",
        "minimize_window": "minimize",
        "maximize_window": "maximize",
        "close_window": "close",
        "new_tab": "browser_tab_new",
        "close_tab": "browser_tab_close",
        "copy_text": "copy",
        "paste_text": "paste",
        "cut_text": "cut",
        "undo_action": "undo",
        "redo_action": "redo",
        "select_all": "select_all",
        "take_photo": "webcam",
        "record_video": "webcam",
        "set_timer": "alarm",
        "set_reminder": "alarm",
        "set_alarm": "alarm",
        "check_weather": "weather",
        "get_weather": "weather",
        "news": "news",
        "get_news": "news",
        "send_message": "send_whatsapp",
        "make_call": "call",
        "phone_call": "call",
        "video_call": "teams_meeting",
        "turn_on_light": "smart_home_control",
        "turn_off_light": "smart_home_control",
        "dim_light": "smart_home_control",
        "set_brightness": "brightness_set",
        "increase_brightness": "brightness_up",
        "decrease_brightness": "brightness_down",
        "open_settings": "settings",
        "system_info": "sys_info",
        "disk_info": "disk",
        "network_info": "network_status",
        "wifi_status": "wifi_status",
        "bluetooth_toggle": "bt_on",
        "screenshot_region": "screenshot",
        "full_screenshot": "screenshot",
        "open_terminal": "terminal",
        "open_cmd": "terminal",
        "open_powershell": "terminal",
        "run_command": "terminal",
        "create_file": "file_create",
        "delete_file": "file_delete",
        "move_file": "file_move",
        "open_file": "file_open",
        "save_file": "file_save",
        "open_folder": "folder_open",
        "create_folder": "folder_create",
        "compress_file": "zip",
        "extract_file": "unzip",
    }

    # Resolve alias
    resolved = ALIASES.get(tool_name, tool_name)

    # Try MCP first
    try:
        from mcp_client import get_mcp_client
        client = get_mcp_client()
        tools = client.get_tools()
        for t in tools:
            if t.name == tool_name or t.name == resolved:
                import asyncio
                args = json.loads(params) if isinstance(params, str) and params.startswith("{") else {"input": params}
                try:
                    result = asyncio.run(client.call_tool(t.name, args))
                    text = ""
                    for c in result.content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text += c.get("text", "")
                    return text or f"MCP tool {t.name} executed."
                except Exception as e:
                    return f"MCP tool error: {e}"
    except Exception:
        pass

    # Try built-in action (resolved name first, then original)
    try:
        from actions import detect_action, cloud_safe_execute
        aid = detect_action(resolved) or detect_action(tool_name) or resolved
        return cloud_safe_execute(aid, params, user_id=user_id)
    except Exception as e:
        return f"Action error: {e}"


# ── Singleton ──────────────────────────────────────────────────────
_catalog_cache: dict[str, str] = {}


def get_tool_catalog(user_id: str = "local") -> str:
    """Get cached tool catalog."""
    if user_id not in _catalog_cache:
        _catalog_cache[user_id] = build_tool_catalog(user_id)
    return _catalog_cache[user_id]


def invalidate_catalog():
    """Clear catalog cache (call when devices/MCP change)."""
    _catalog_cache.clear()
