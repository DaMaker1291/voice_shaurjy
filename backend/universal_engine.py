#!/usr/bin/env python3
"""
Universal Action Engine for JARVIS
Handles EVERY task: flights, visas, forms, emails, homework, trips, discounts, etc.
Plans multi-step workflows and executes via headless browser + device control.
"""
import time
import json
import re
from typing import Dict, Any, List, Optional

class UniversalActionEngine:
    """
    Recognizes ANY user intent and creates executable action plans.
    Covers: travel, immigration, productivity, device control, web, email, forms, education.
    """

    # ── Intent Recognition ────────────────────────────────────────────
    INTENT_PATTERNS = {
        # Travel & Flights
        "flight_search": [r"find\s+flights?", r"search\s+flights?", r"cheap\s+flights?", r"flight\s+deals?", r"airfare"],
        "flight_book": [r"book\s+(?:a\s+)?flight", r"reserve\s+flight", r"buy\s+flight\s+ticket"],
        "flight_checkin": [r"check[\s-]?in", r"boarding\s+pass", r"online\s+check[\s-]?in"],
        "flight_status": [r"flight\s+status", r"where(?:'s|\s+is)\s+my\s+flight", r"flight\s+track"],
        "hotel_search": [r"find\s+hotels?", r"search\s+hotels?", r"hotel\s+deals?", r"places?\s+to\s+stay"],
        "hotel_book": [r"book\s+(?:a\s+)?hotel", r"reserve\s+hotel", r"reserve\s+room"],
        "car_rental": [r"rent\s+(?:a\s+)?car", r"car\s+hire", r"vehicle\s+rental"],
        "trip_plan": [r"plan\s+(?:a\s+)?trip", r"plan\s+vacation", r"travel\s+itinerary", r"trip\s+planner"],

        # Immigration & Documents
        "visa_check": [r"visa\s+(?:requirements?|status|application)", r"do\s+i\s+need\s+(?:a\s+)?visa", r"visa\s+for"],
        "visa_apply": [r"apply\s+(?:for\s+)?(?:a\s+)?visa", r"visa\s+application", r"start\s+visa"],
        "oci_apply": [r"oci\s+(?:application|apply)", r"overseas\s+citizen", r"oci\s+card", r"oci\s+registration"],
        "passport": [r"passport", r"renew\s+passport", r"passport\s+status", r"passport\s+photo"],
        "travel_auth": [r"esta", r"eta", r"travel\s+authorization", r"evus"],

        # Forms & Documents
        "fill_form": [r"fill\s+(?:out\s+)?(?:a\s+)?form", r"complete\s+form", r"form\s+filling"],
        "pdf_fill": [r"fill\s+pdf", r"pdf\s+form", r"fillable\s+pdf"],
        "sign_document": [r"sign\s+(?:a\s+)?document", r"e[\s-]?signature", r"esign"],
        "scan_document": [r"scan\s+(?:a\s+)?document", r"digitize", r"ocr"],

        # Email & Communication
        "email_read": [r"check\s+(?:my\s+)?email", r"read\s+(?:my\s+)?email", r"any\s+(?:new\s+)?emails?", r"inbox"],
        "email_send": [r"send\s+(?:an?\s+)?email", r"reply\s+to\s+email", r"email\s+to"],
        "email_reply": [r"reply", r"respond\s+to", r"write\s+back"],
        "email_draft": [r"draft\s+(?:an?\s+)?email", r"compose\s+email", r"write\s+email"],
        "message_read": [r"check\s+(?:my\s+)?messages?", r"read\s+(?:my\s+)?messages?", r"any\s+texts?"],
        "message_send": [r"send\s+(?:a\s+)?message", r"text\s+someone", r"message\s+to"],

        # Homework & Education
        "homework_help": [r"homework", r"help\s+with\s+(?:my\s+)?(?:math|science|english|history)", r"solve\s+(?:this|the)\s+problem"],
        "essay_write": [r"write\s+(?:an?\s+)?essay", r"essay\s+help", r"write\s+(?:a\s+)?report"],
        "research": [r"research\s+(?:on|about)", r"find\s+information\s+about", r"look\s+up"],
        "study": [r"study\s+(?:for|about)", r"flashcards?", r"summarize\s+(?:this|the)"],
        "tutor": [r"explain\s+(?:this|the|how)", r"teach\s+me", r"tutor", r"tutorial"],

        # Shopping & Discounts
        "find_discounts": [r"discount", r"coupon", r"deal", r"promo\s+code", r"sale", r"cheapest"],
        "price_compare": [r"compare\s+prices?", r"price\s+check", r"which\s+(?:is\s+)?cheaper", r"best\s+price"],
        "product_search": [r"find\s+(?:a\s+)?(?:product|item|thing)", r"search\s+(?:for\s+)?(?:a\s+)?product", r"buy"],
        "amazon": [r"amazon", r"on\s+amazon"],

        # Device & System
        "device_control": [r"turn\s+(?:on|off|up|down)", r"switch\s+(?:on|off)", r"lights?\s+(?:on|off)", r"volume"],
        "device_scan": [r"scan\s+(?:all\s+)?devices?", r"find\s+(?:all\s+)?devices?", r"what\s+devices?"],
        "system_info": [r"cpu", r"memory", r"disk", r"battery", r"system\s+(?:info|status|health)"],
        "screenshot": [r"screenshot", r"screen\s+(?:capture|shot)"],
        "type_text": [r"type\s+(?:this|text|it)", r"keystroke", r"type\s+out"],
        "hotkey": [r"press\s+(?:cmd|ctrl|alt|shift)", r"keyboard\s+shortcut", r"hotkey", r"press\s+ctrl"],
        "launch_app": [r"open\s+(?:the\s+)?(?:app|application)", r"launch\s+(?:the\s+)?(?:app|application)", r"start\s+(?:the\s+)?(?:app|application)"],
        "quit_app": [r"quit\s+(?:the\s+)?(?:app|application)", r"close\s+(?:the\s+)?(?:app|application)", r"force\s+quit"],
        "clipboard": [r"clipboard", r"copy\s+(?:this|it|to)", r"paste", r"copy\s+paste"],
        "frontmost": [r"what(?:'s|\s+is)\s+(?:in\s+)?front", r"frontmost\s+app", r"active\s+window"],
        "running_apps": [r"(?:what\s+)?(?:apps?|applications?)\s+(?:are\s+)?running", r"list\s+(?:all\s+)?(?:apps|processes)"],

        # Disk & Cleanup
        "disk_usage": [r"(?:how\s+(?:much|many)\s+)?(?:disk|storage|space)\s+(?:left|used|available)", r"disk\s+(?:space|usage)", r"storage\s+status"],
        "clean_cache": [r"clean\s+(?:my\s+)?(?:cache|caches)", r"clear\s+(?:my\s+)?(?:cache|caches)", r"free\s+(?:up\s+)?cache"],
        "clean_logs": [r"clean\s+(?:my\s+)?(?:logs?|log\s+files?)", r"clear\s+(?:my\s+)?(?:logs?|log\s+files?)"],
        "clean_downloads": [r"clean\s+(?:my\s+)?downloads", r"clear\s+(?:my\s+)?downloads", r"large\s+(?:files?|downloads?)"],
        "free_space": [r"free\s+(?:up\s+)?(?:disk\s+)?space", r"clean\s+(?:up\s+)?(?:my\s+)?(?:disk|computer|mac|laptop)", r"make\s+space", r"disk\s+cleanup"],

        # Web & Navigation
        "web_search": [r"google\s+(?:for\s+)?", r"search\s+(?:for\s+)?", r"look\s+up\s+(?:on\s+)?(?:google|web|internet)"],
        "web_open": [r"open\s+(?:the\s+)?(?:website|site|page|url)", r"go\s+to\s+(?:the\s+)?(?:website|site|url)"],
        "web_scrape": [r"scrape\s+(?:the\s+)?(?:page|site|website)", r"extract\s+(?:from\s+)?(?:the\s+)?(?:page|site)"],
        "social_media": [r"(?:check|open|scroll)\s+(?:my\s+)?(?:twitter|instagram|linkedin|facebook|tiktok)"],
        "news": [r"(?:read|get|fetch|what(?:'s|\s+is))\s+(?:the\s+)?news", r"headlines?", r"current\s+events?"],

        # Calendar & Scheduling
        "calendar": [r"calendar", r"what(?:'s|\s+is)\s+on\s+my\s+(?:schedule|calendar)", r"today(?:'s|\s+is)?\s+schedule"],
        "reminder": [r"remind\s+me", r"set\s+(?:a\s+)?reminder", r"reminder"],
        "schedule": [r"schedule\s+(?:a\s+)?", r"book\s+(?:a\s+)?meeting", r"set\s+up\s+(?:a\s+)?meeting"],

        # Productivity
        "todo": [r"todo", r"to[\s-]?do\s+list", r"tasks?\s+(?:to\s+do|list)", r"add\s+to\s+todo"],
        "notes": [r"(?:take|write|create)\s+(?:a\s+)?note", r"notes?", r"save\s+(?:this|the)\s+(?:as\s+)?(?:a\s+)?note"],
        "summary": [r"summarize", r"summary\s+of", r"give\s+me\s+(?:a\s+)?summary"],

        # Smart Home
        "alexa": [r"alexa", r"echo", r"ask\s+alexa"],
        "smart_home": [r"smart\s+home", r"home\s+automation", r"lights?", r"thermostat"],

        # Desktop Control (System)
        "desktop_open": [r"open\s+(?:the\s+)?(?:app|application|program)", r"launch\s+(?:the\s+)?(?:app|application)", r"start\s+(?:the\s+)?(?:app|application)"],
        "desktop_type": [r"type\s+(?:this|text|it|out)", r"keystroke", r"type\s+(?:on\s+)?(?:keyboard|screen)"],
        "desktop_click": [r"click\s+(?:on\s+)?", r"press\s+(?:the\s+)?button", r"tap\s+(?:on\s+)?"],
        "desktop_scroll": [r"scroll\s+(?:up|down|left|right)", r"scroll\s+(?:the\s+)?page"],
        "desktop_hotkey": [r"press\s+(?:cmd|ctrl|alt|shift|command|option)", r"keyboard\s+shortcut", r"hotkey"],
        "desktop_screenshot": [r"screenshot", r"screen\s+(?:capture|shot)", r"capture\s+(?:the\s+)?screen"],
        "desktop_see": [r"what(?:'s|\s+is)\s+on\s+(?:the\s+)?screen", r"what\s+do\s+you\s+see", r"read\s+(?:the\s+)?screen", r"describe\s+(?:the\s+)?screen"],
        "desktop_find": [r"find\s+(?:the\s+)?(?:button|field|element|text|label)", r"where\s+is\s+(?:the\s+)?(?:button|field|element)", r"locate\s+(?:the\s+)?"],
        "desktop_find_click": [r"click\s+(?:on\s+)?(?:the\s+)?(?:button|link|option|tab|menu)", r"find\s+and\s+click"],
        "desktop_close": [r"close\s+(?:the\s+)?(?:app|window|tab)", r"quit\s+(?:the\s+)?(?:app|application)"],
        "desktop_minimize": [r"minimize", r"minimise", r"hide\s+(?:the\s+)?(?:app|window)"],
        "desktop_fullscreen": [r"full\s*screen", r"maximize", r"maximise"],
        "desktop_new_tab": [r"new\s+tab", r"open\s+(?:a\s+)?(?:new\s+)?tab"],
        "desktop_new_window": [r"new\s+window", r"open\s+(?:a\s+)?(?:new\s+)?window"],
        "desktop_search": [r"search\s+(?:for\s+)?(?:in\s+)?(?:this|the|current)", r"find\s+(?:in\s+)?(?:this|the|current)"],
        "desktop_select_all": [r"select\s+all", r"select\s+everything"],
        "desktop_copy": [r"copy\s+(?:this|it|selection|selected)", r"copy\s+(?:to\s+)?clipboard"],
        "desktop_paste": [r"paste\s+(?:this|it|from)", r"paste\s+(?:from\s+)?clipboard"],
        "desktop_undo": [r"undo", r"undo\s+(?:this|that|the\s+last)"],
        "desktop_save": [r"save\s+(?:this|the|current)", r"save\s+(?:the\s+)?(?:file|document)"],
        "desktop_go_to": [r"go\s+to\s+(?:https?://|www\.|google|youtube|github|reddit|twitter|facebook)", r"navigate\s+to", r"open\s+(?:the\s+)?(?:website|site|url|page)"],

        # Autonomous
        "autonomous": [r"do\s+(?:this|that|it)\s+(?:for\s+me|autonomously)", r"handle\s+(?:this|that)", r"take\s+care\s+of"],
    }

    # ── Workflow Templates ────────────────────────────────────────────
    WORKFLOWS = {
        "flight_search": [
            {"action": "browser_open", "description": "Open Google Flights", "params": {"url": "https://www.google.com/travel/flights"}},
            {"action": "wait", "description": "Wait for page to load", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read current flight search page"},
            {"action": "browser_type", "description": "Enter origin city", "params": {"selector": "[aria-label='Where from?']", "text": ""}},
            {"action": "browser_type", "description": "Enter destination city", "params": {"selector": "[aria-label='Where to?']", "text": ""}},
            {"action": "browser_click", "description": "Click search button"},
            {"action": "wait", "description": "Wait for results", "params": {"seconds": 5}},
            {"action": "browser_get_text", "description": "Read flight results and prices"},
            {"action": "browser_screenshot", "description": "Capture flight results"},
            {"action": "report_findings", "description": "Report best flight options with prices"},
        ],
        "flight_checkin": [
            {"action": "browser_open", "description": "Open Gmail to find booking confirmation", "params": {"url": "https://mail.google.com"}},
            {"action": "wait", "description": "Wait for Gmail to load", "params": {"seconds": 5}},
            {"action": "browser_type", "description": "Search for flight confirmation emails", "params": {"selector": "input[aria-label='Search mail']", "text": "flight confirmation booking"}},
            {"action": "wait", "description": "Wait for search results", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read email subjects for airline and booking reference"},
            {"action": "browser_click", "description": "Open most recent flight email"},
            {"action": "browser_get_text", "description": "Extract booking reference and airline"},
            {"action": "browser_open", "description": "Navigate to airline check-in page"},
            {"action": "wait", "description": "Wait for airline page", "params": {"seconds": 4}},
            {"action": "browser_type", "description": "Enter booking reference"},
            {"action": "browser_type", "description": "Enter last name"},
            {"action": "browser_click", "description": "Click check-in button"},
            {"action": "wait", "description": "Wait for check-in to process", "params": {"seconds": 5}},
            {"action": "browser_get_text", "description": "Read check-in confirmation"},
            {"action": "browser_screenshot", "description": "Screenshot boarding pass"},
            {"action": "report_findings", "description": "Report check-in status and boarding pass details"},
        ],
        "flight_status": [
            {"action": "browser_open", "description": "Open FlightAware", "params": {"url": "https://www.flightaware.com"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read flight tracking page"},
            {"action": "browser_screenshot", "description": "Capture flight status"},
            {"action": "report_findings", "description": "Report flight status"},
        ],
        "visa_check": [
            {"action": "browser_open", "description": "Open visa requirements page", "params": {"url": "https://www.ivisa.com/visa-requirements"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read visa requirements information"},
            {"action": "browser_screenshot", "description": "Capture visa info"},
            {"action": "report_findings", "description": "Report visa requirements"},
        ],
        "oci_apply": [
            {"action": "browser_open", "description": "Open OCI application portal", "params": {"url": "https://portal6indiagov.org"}},
            {"action": "wait", "description": "Wait for portal to load", "params": {"seconds": 5}},
            {"action": "browser_get_text", "description": "Read OCI application requirements"},
            {"action": "browser_screenshot", "description": "Capture application page"},
            {"action": "report_findings", "description": "Report OCI application steps and required documents"},
        ],
        "passport": [
            {"action": "browser_open", "description": "Open passport service page", "params": {"url": "https://www.uspassportservices.gov"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read passport renewal information"},
            {"action": "report_findings", "description": "Report passport status and renewal options"},
        ],
        "email_read": [
            {"action": "browser_open", "description": "Open Gmail", "params": {"url": "https://mail.google.com"}},
            {"action": "wait", "description": "Wait for Gmail to load", "params": {"seconds": 5}},
            {"action": "browser_get_text", "description": "Read inbox contents"},
            {"action": "categorize_emails", "description": "Categorize emails by importance"},
            {"action": "report_findings", "description": "Report email summary with priorities"},
        ],
        "email_send": [
            {"action": "browser_open", "description": "Open Gmail compose", "params": {"url": "https://mail.google.com/mail/?view=cm"}},
            {"action": "wait", "description": "Wait for compose window", "params": {"seconds": 3}},
            {"action": "browser_type", "description": "Enter recipient email"},
            {"action": "browser_type", "description": "Enter subject"},
            {"action": "browser_type", "description": "Enter email body"},
            {"action": "browser_click", "description": "Click send button"},
            {"action": "report_findings", "description": "Confirm email sent"},
        ],
        "homework_help": [
            {"action": "browser_open", "description": "Open educational resources", "params": {"url": "https://www.khanacademy.org"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read relevant educational content"},
            {"action": "browser_screenshot", "description": "Capture reference material"},
            {"action": "report_findings", "description": "Provide homework help with explanations"},
        ],
        "essay_write": [
            {"action": "browser_open", "description": "Open Google Docs", "params": {"url": "https://docs.google.com/document/create"}},
            {"action": "wait", "description": "Wait for editor", "params": {"seconds": 3}},
            {"action": "browser_type", "description": "Write essay content"},
            {"action": "report_findings", "description": "Report essay draft completion"},
        ],
        "find_discounts": [
            {"action": "browser_open", "description": "Open deal aggregator", "params": {"url": "https://www.retailmenot.com"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read available discounts and coupons"},
            {"action": "browser_screenshot", "description": "Capture deals"},
            {"action": "report_findings", "description": "Report best available discounts"},
        ],
        "product_search": [
            {"action": "browser_open", "description": "Open product search", "params": {"url": "https://www.google.com/shopping"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_type", "description": "Enter product search query"},
            {"action": "browser_click", "description": "Click search"},
            {"action": "wait", "description": "Wait for results", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read product results and prices"},
            {"action": "report_findings", "description": "Report product options with prices"},
        ],
        "web_search": [
            {"action": "browser_open", "description": "Open Google Search", "params": {"url": "https://www.google.com"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 2}},
            {"action": "browser_type", "description": "Enter search query"},
            {"action": "browser_click", "description": "Click search"},
            {"action": "wait", "description": "Wait for results", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read search results"},
            {"action": "report_findings", "description": "Report search findings"},
        ],
        "screenshot": [
            {"action": "browser_screenshot", "description": "Capture current screen"},
            {"action": "report_findings", "description": "Report screenshot captured"},
        ],
        "system_info": [
            {"action": "system_exec", "description": "Get system information"},
            {"action": "report_findings", "description": "Report system status"},
        ],
        "alexa": [
            {"action": "alexa_control", "description": "Control Alexa device"},
            {"action": "report_findings", "description": "Report Alexa action completed"},
        ],
        "device_control": [
            {"action": "device_control", "description": "Control smart device"},
            {"action": "report_findings", "description": "Report device action completed"},
        ],
        "news": [
            {"action": "browser_open", "description": "Open news site", "params": {"url": "https://news.google.com"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read top headlines"},
            {"action": "report_findings", "description": "Report today's top news"},
        ],
        "calendar": [
            {"action": "browser_open", "description": "Open Google Calendar", "params": {"url": "https://calendar.google.com"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 3}},
            {"action": "browser_get_text", "description": "Read today's schedule"},
            {"action": "report_findings", "description": "Report calendar events"},
        ],
        "type_text": [
            {"action": "system_type", "description": "Type the specified text on the system"},
            {"action": "report_findings", "description": "Confirm text was typed"},
        ],
        "hotkey": [
            {"action": "system_hotkey", "description": "Press the specified keyboard shortcut"},
            {"action": "report_findings", "description": "Confirm hotkey was pressed"},
        ],
        "launch_app": [
            {"action": "system_launch_app", "description": "Launch the specified application"},
            {"action": "report_findings", "description": "Confirm app was launched"},
        ],
        "quit_app": [
            {"action": "system_quit_app", "description": "Quit the specified application"},
            {"action": "report_findings", "description": "Confirm app was quit"},
        ],
        "frontmost": [
            {"action": "system_frontmost", "description": "Get the frontmost application"},
            {"action": "report_findings", "description": "Report which app is in front"},
        ],
        "running_apps": [
            {"action": "system_running_apps", "description": "List all running applications"},
            {"action": "report_findings", "description": "Report running apps list"},
        ],
        "clipboard": [
            {"action": "system_clipboard", "description": "Get/set clipboard contents"},
            {"action": "report_findings", "description": "Report clipboard status"},
        ],
        "disk_usage": [
            {"action": "system_disk_usage", "description": "Check disk usage"},
            {"action": "report_findings", "description": "Report disk space status"},
        ],
        "clean_cache": [
            {"action": "system_scan_cache", "description": "Scan for cache files"},
            {"action": "report_findings", "description": "Report cache sizes and ask for confirmation"},
        ],
        "clean_logs": [
            {"action": "system_scan_logs", "description": "Scan for log files"},
            {"action": "report_findings", "description": "Report log sizes and ask for confirmation"},
        ],
        "clean_downloads": [
            {"action": "system_scan_downloads", "description": "Scan for large files in Downloads"},
            {"action": "report_findings", "description": "Report large files and ask for confirmation"},
        ],
        "free_space": [
            {"action": "system_disk_usage", "description": "Check current disk usage"},
            {"action": "system_scan_cache", "description": "Scan for cache files to clean"},
            {"action": "system_scan_logs", "description": "Scan for log files to clean"},
            {"action": "report_findings", "description": "Report cleanup options and ask for confirmation before cleaning"},
        ],
        "desktop_open": [
            {"action": "system_launch_app", "description": "Launch the specified application"},
            {"action": "system_screenshot", "description": "Verify app launched"},
            {"action": "report_findings", "description": "Confirm app is open"},
        ],
        "desktop_type": [
            {"action": "system_type", "description": "Type the specified text"},
            {"action": "report_findings", "description": "Confirm text was typed"},
        ],
        "desktop_click": [
            {"action": "system_find_click", "description": "Find and click the element"},
            {"action": "report_findings", "description": "Confirm element was clicked"},
        ],
        "desktop_hotkey": [
            {"action": "system_hotkey", "description": "Press the keyboard shortcut"},
            {"action": "report_findings", "description": "Confirm hotkey was pressed"},
        ],
        "desktop_screenshot": [
            {"action": "system_screenshot", "description": "Take a screenshot"},
            {"action": "report_findings", "description": "Report screenshot captured"},
        ],
        "desktop_see": [
            {"action": "system_screenshot", "description": "Take screenshot to see screen"},
            {"action": "system_ocr", "description": "OCR to read screen text"},
            {"action": "report_findings", "description": "Describe what's on screen"},
        ],
        "desktop_find": [
            {"action": "system_screenshot", "description": "Take screenshot"},
            {"action": "system_ocr", "description": "OCR to find element"},
            {"action": "report_findings", "description": "Report element location"},
        ],
        "desktop_find_click": [
            {"action": "system_screenshot", "description": "Take screenshot"},
            {"action": "system_find_click", "description": "Find and click the element"},
            {"action": "report_findings", "description": "Confirm element was clicked"},
        ],
        "desktop_close": [
            {"action": "system_quit_app", "description": "Quit the application"},
            {"action": "report_findings", "description": "Confirm app was closed"},
        ],
        "desktop_go_to": [
            {"action": "system_hotkey", "description": "Focus address bar (Cmd+L)", "params": {"keys": ["cmd", "l"]}},
            {"action": "system_type", "description": "Type the URL"},
            {"action": "system_key", "description": "Press Enter", "params": {"key": "return"}},
            {"action": "wait", "description": "Wait for page to load", "params": {"seconds": 3}},
            {"action": "report_findings", "description": "Confirm navigation"},
        ],
        "desktop_search": [
            {"action": "system_hotkey", "description": "Focus search (Cmd+F)", "params": {"keys": ["cmd", "f"]}},
            {"action": "system_type", "description": "Type search query"},
            {"action": "system_key", "description": "Press Enter", "params": {"key": "return"}},
            {"action": "report_findings", "description": "Confirm search initiated"},
        ],
        "desktop_select_all": [
            {"action": "system_hotkey", "description": "Select all (Cmd+A)", "params": {"keys": ["cmd", "a"]}},
            {"action": "report_findings", "description": "Confirm all selected"},
        ],
        "desktop_copy": [
            {"action": "system_hotkey", "description": "Copy (Cmd+C)", "params": {"keys": ["cmd", "c"]}},
            {"action": "report_findings", "description": "Confirm copied to clipboard"},
        ],
        "desktop_paste": [
            {"action": "system_hotkey", "description": "Paste (Cmd+V)", "params": {"keys": ["cmd", "v"]}},
            {"action": "report_findings", "description": "Confirm pasted"},
        ],
        "desktop_undo": [
            {"action": "system_hotkey", "description": "Undo (Cmd+Z)", "params": {"keys": ["cmd", "z"]}},
            {"action": "report_findings", "description": "Confirm undo"},
        ],
        "desktop_save": [
            {"action": "system_hotkey", "description": "Save (Cmd+S)", "params": {"keys": ["cmd", "s"]}},
            {"action": "report_findings", "description": "Confirm saved"},
        ],
        "desktop_minimize": [
            {"action": "system_hotkey", "description": "Minimize (Cmd+M)", "params": {"keys": ["cmd", "m"]}},
            {"action": "report_findings", "description": "Confirm minimized"},
        ],
        "desktop_fullscreen": [
            {"action": "system_hotkey", "description": "Toggle fullscreen", "params": {"keys": ["cmd", "ctrl", "f"]}},
            {"action": "report_findings", "description": "Confirm fullscreen toggled"},
        ],
        "desktop_new_tab": [
            {"action": "system_hotkey", "description": "New tab (Cmd+T)", "params": {"keys": ["cmd", "t"]}},
            {"action": "report_findings", "description": "Confirm new tab opened"},
        ],
        "desktop_new_window": [
            {"action": "system_hotkey", "description": "New window (Cmd+N)", "params": {"keys": ["cmd", "n"]}},
            {"action": "report_findings", "description": "Confirm new window opened"},
        ],
    }

    def __init__(self):
        self.conversation_history = []
        self.active_workflows = {}
        self.proactive_monitors = {}

    def recognize_intent(self, text: str) -> Dict[str, Any]:
        """Recognize user intent from natural language text."""
        lower = text.lower().strip()
        scores = {}
        params = {}

        for intent, patterns in self.INTENT_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, lower):
                    score += 1
            if score > 0:
                scores[intent] = score

        if not scores:
            return {"intent": "general_chat", "confidence": 0.5, "params": {}}

        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent] / 3.0, 1.0)

        # Extract parameters
        params = self._extract_params(best_intent, text)

        return {
            "intent": best_intent,
            "confidence": confidence,
            "params": params,
        }

    def _extract_params(self, intent: str, text: str) -> Dict[str, Any]:
        """Extract relevant parameters from text based on intent."""
        params = {}
        lower = text.lower()

        # Extract cities/locations
        location_patterns = [
            r"(?:from|departure)\s+(\w[\w\s]*?)(?:\s+to|\s+for|\s*,|\s*$)",
            r"(?:to|destination|in|at|from)\s+(\w[\w\s]*?)(?:\s+on|\s+for|\s*,|\s*$)",
        ]
        for p in location_patterns:
            m = re.search(p, lower)
            if m:
                params["location"] = m.group(1).strip()

        # Extract dates
        date_patterns = [
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(tomorrow|today|next\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday))",
            r"(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{2,4})",
        ]
        for p in date_patterns:
            m = re.search(p, lower)
            if m:
                params["date"] = m.group(1)

        # Extract email addresses
        email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', text)
        if email_match:
            params["email"] = email_match.group(0)

        # Extract flight numbers
        flight_match = re.search(r'([a-z]{2}\d{2,4})', lower)
        if flight_match:
            params["flight_number"] = flight_match.group(1).upper()

        # Extract names (simple heuristic)
        name_patterns = [
            r"(?:name|passenger)\s+(?:is\s+)?(\w[\w\s]*?)(?:\s+and|\s+for|\s*,|\s*$)",
            r"(?:mr|mrs|ms|dr)\.?\s+(\w[\w\s]*?)(?:\s+and|\s+for|\s*,|\s*$)",
        ]
        for p in name_patterns:
            m = re.search(p, lower)
            if m:
                params["passenger_name"] = m.group(1).strip().title()

        return params

    def create_workflow(self, intent: str, params: Dict[str, Any] = None) -> List[Dict]:
        """Create an execution workflow based on intent and params."""
        params = params or {}

        if intent in self.WORKFLOWS:
            workflow = self.WORKFLOWS[intent].copy()
            # Inject params into workflow steps
            for step in workflow:
                if step["action"] == "browser_type":
                    # Try to fill in relevant params
                    if "origin" in step.get("description", "").lower() and "location" in params:
                        step["params"]["text"] = params["location"]
                    elif "destination" in step.get("description", "").lower() and "destination" in params:
                        step["params"]["text"] = params["destination"]
                    elif "recipient" in step.get("description", "").lower() and "email" in params:
                        step["params"]["text"] = params["email"]
                elif step["action"] == "browser_open" and params.get("search_query"):
                    step["params"]["url"] = f"https://www.google.com/search?q={params['search_query'].replace(' ', '+')}"
            return workflow

        # Default: generic web search + report
        return [
            {"action": "browser_open", "description": "Open web browser", "params": {"url": "https://www.google.com"}},
            {"action": "wait", "description": "Wait for page", "params": {"seconds": 2}},
            {"action": "browser_type", "description": f"Search for: {params.get('query', intent)}"},
            {"action": "browser_get_text", "description": "Read search results"},
            {"action": "report_findings", "description": "Report findings"},
        ]

    def get_available_intents(self) -> List[str]:
        """Return all available intent categories."""
        return list(self.INTENT_PATTERNS.keys())

    def get_workflow_for_intent(self, intent: str) -> List[Dict]:
        """Get the workflow steps for a specific intent."""
        return self.WORKFLOWS.get(intent, [])

    def format_workflow_summary(self, workflow: List[Dict]) -> str:
        """Format a workflow as a readable summary."""
        lines = []
        for i, step in enumerate(workflow, 1):
            lines.append(f"{i}. {step['description']}")
        return "\n".join(lines)


# Singleton
_engine = None

def get_engine() -> UniversalActionEngine:
    global _engine
    if _engine is None:
        _engine = UniversalActionEngine()
    return _engine
