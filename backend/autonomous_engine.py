#!/usr/bin/env python3
"""
Autonomous Task Engine for JARVIS Relay
Handles complex multi-step tasks: email scanning, flight check-in, browser automation.
Runs on the user's Mac with full screen + browser access.
"""
import subprocess
import json
import time
import re
import os

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "timeout"
    except Exception as e:
        return str(e)

# ── Browser Automation (AppleScript + Safari/Chrome) ─────────────────

def _get_active_browser():
    """Detect which browser is active."""
    result = run("osascript -e 'tell application \"System Events\" to get name of first application process whose frontmost is true'")
    if "Safari" in result:
        return "Safari"
    elif "Chrome" in result:
        return "Google Chrome"
    elif "Firefox" in result:
        return "Firefox"
    return "Safari"

def browser_open_url(url, browser=None):
    """Open a URL in the browser."""
    b = browser or _get_active_browser()
    if b == "Safari":
        run(f'osascript -e \'tell application "Safari" to activate\' -e \'tell application "Safari" to set URL of front document to "{url}"\'')
    elif b == "Google Chrome":
        run(f'osascript -e \'tell application "Google Chrome" to activate\' -e \'tell application "Google Chrome" to set URL of active tab of front window to "{url}"\'')
    else:
        run(f'open -a "{b}" "{url}"')
    time.sleep(2)
    return f"Opened {url} in {b}"

def browser_get_text():
    """Get visible text from the active browser tab."""
    b = _get_active_browser()
    if b == "Safari":
        return run('osascript -e \'tell application "Safari" to get text of front document\'', timeout=10)
    elif b == "Google Chrome":
        # Chrome doesn't support get text directly, use JS
        return run('''osascript -e 'tell application "Google Chrome" to execute active tab of front window javascript "document.body.innerText"\' ''', timeout=10)
    return ""

def browser_click_element(description):
    """Click an element by description using AppleScript accessibility."""
    # Use AppleScript to find and click UI elements
    script = f'''
    tell application "System Events"
        tell process "{_get_active_browser()}"
            set frontmost to true
            delay 0.5
            try
                click (first button whose description contains "{description}")
            on error
                try
                    click (first UI element whose description contains "{description}")
                on error
                    return "Element not found: {description}"
                end try
            end try
        end tell
    end tell
    '''
    return run(f"osascript -e '{script}'", timeout=10)

def browser_type_text(text):
    """Type text into the active browser field."""
    script = f'''
    tell application "System Events"
        keystroke "{text}"
    end tell
    '''
    return run(f"osascript -e '{script}'", timeout=10)

def browser_press_key(key):
    """Press a key (return, tab, escape, etc)."""
    script = f'''
    tell application "System Events"
        key code {{"return": 36, "tab": 48, "escape": 53}.get("{key}", 36)}
    end tell
    '''
    return run(f"osascript -e '{script}'", timeout=5)

def browser_screenshot(path="/tmp/jarvis_screen.png"):
    """Take a screenshot of the current screen."""
    run(f"screencapture -x {path}")
    return path

# ── Email Scanning ───────────────────────────────────────────────────

def scan_emails_for_flights():
    """Open Gmail/Outlook and scan for flight emails, check-in links."""
    results = []

    # Open Gmail
    browser_open_url("https://mail.google.com")
    time.sleep(4)

    # Get page text
    text = browser_get_text()

    # Look for flight-related keywords
    flight_keywords = ["flight", "boarding", "check-in", "check in", "itinerary", "booking", "reservation", "airline", "departure", "arrive"]
    lines = text.split("\n")
    flight_emails = []
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in flight_keywords):
            flight_emails.append(line.strip())

    # Also scan subject lines
    subject_text = run('''osascript -e '
    tell application "Safari"
        set allText to ""
        repeat with w in windows
            repeat with t in tabs of w
                set allText to allText & (name of t) & " "
            end repeat
        end repeat
        return allText
    end tell' ''', timeout=10)

    for kw in flight_keywords:
        if kw in subject_text.lower():
            flight_emails.append(f"Subject match: {subject_text[:200]}")

    return {
        "found": len(flight_emails) > 0,
        "items": flight_emails[:10],
        "page_text_preview": text[:500] if text else "No text captured"
    }

def scan_google_photos_for_passport():
    """Open Google Photos and look for passport/ID photos."""
    browser_open_url("https://photos.google.com")
    time.sleep(4)

    text = browser_get_text()
    photo_keywords = ["passport", "id card", "identification", "photo id", "visa", "travel"]
    matches = []
    for line in text.split("\n"):
        line_lower = line.lower()
        if any(kw in line_lower for kw in photo_keywords):
            matches.append(line.strip())

    return {
        "found": len(matches) > 0,
        "matches": matches[:10],
        "page_text_preview": text[:500] if text else "No text captured"
    }

# ── Complex Task Planner ─────────────────────────────────────────────

def plan_checkin_task(flight_info=None):
    """Plan the steps needed for flight check-in."""
    steps = []

    if flight_info:
        steps.append({"step": 1, "action": "open_airline_site", "url": flight_info.get("airline_url", ""), "description": f"Open {flight_info.get('airline', 'airline')} website"})
        steps.append({"step": 2, "action": "navigate_checkin", "description": "Navigate to check-in page"})
        steps.append({"step": 3, "action": "enter_booking", "description": f"Enter booking ref: {flight_info.get('booking_ref', 'UNKNOWN')}"})
        steps.append({"step": 4, "action": "enter_name", "description": f"Enter passenger name: {flight_info.get('name', 'UNKNOWN')}"})
        steps.append({"step": 5, "action": "submit_checkin", "description": "Submit check-in"})
        steps.append({"step": 6, "action": "get_boarding_pass", "description": "Download/save boarding pass"})
    else:
        steps.append({"step": 1, "action": "scan_emails", "description": "Scan emails for flight bookings"})
        steps.append({"step": 2, "action": "extract_booking", "description": "Extract booking reference and airline"})
        steps.append({"step": 3, "action": "check_passport_photo", "description": "Check Google Photos for passport/ID"})
        steps.append({"step": 4, "action": "open_airline", "description": "Open airline website"})
        steps.append({"step": 5, "action": "perform_checkin", "description": "Complete check-in process"})

    return {"total_steps": len(steps), "steps": steps}

def execute_task_sequence(steps):
    """Execute a sequence of task steps."""
    results = []
    for step in steps:
        action = step.get("action", "")
        desc = step.get("description", "")
        url = step.get("url", "")

        print(f"[Task] Step {step.get('step', '?')}: {desc}")

        if action == "open_airline_site" or action == "open_airline":
            if url:
                result = browser_open_url(url)
            else:
                result = "No URL provided"
        elif action == "scan_emails":
            result = scan_emails_for_flights()
        elif action == "check_passport_photo":
            result = scan_google_photos_for_passport()
        elif action == "navigate_checkin":
            time.sleep(2)
            text = browser_get_text()
            # Look for check-in button/link
            result = f"Page loaded. Text preview: {text[:200]}"
        elif action == "enter_booking":
            result = "Ready to enter booking reference"
        elif action == "submit_checkin":
            result = "Ready to submit check-in"
        else:
            result = f"Step prepared: {desc}"

        results.append({"step": step.get("step"), "action": action, "result": str(result)[:500]})
        time.sleep(1)

    return results

# ── Main Task Router ─────────────────────────────────────────────────

def handle_autonomous_task(text):
    """Route and execute autonomous tasks based on user intent."""
    lower = text.lower()

    # Flight / check-in related
    if any(kw in lower for kw in ["check in", "check-in", "flight", "boarding", "airline", "boarding pass"]):
        if any(kw in lower for kw in ["scan", "email", "find", "search", "look for"]):
            result = scan_emails_for_flights()
            return json.dumps(result, indent=2)
        elif any(kw in lower for kw in ["plan", "steps", "what do", "how to"]):
            plan = plan_checkin_task()
            return json.dumps(plan, indent=2)
        else:
            # Full check-in flow
            emails = scan_emails_for_flights()
            if emails["found"]:
                plan = plan_checkin_task()
                return f"Found flight-related emails:\n{json.dumps(emails['items'][:5], indent=2)}\n\nPlanned steps:\n{json.dumps(plan['steps'], indent=2)}"
            else:
                return "No flight emails found. Could you provide the airline website and booking reference?"

    # Passport / ID photo related
    if any(kw in lower for kw in ["passport", "id photo", "identification", "photo id", "visa photo"]):
        result = scan_google_photos_for_passport()
        return json.dumps(result, indent=2)

    # Email scanning
    if any(kw in lower for kw in ["check email", "scan email", "read email", "any emails", "inbox"]):
        result = scan_emails_for_flights()
        return json.dumps(result, indent=2)

    # Browser navigation
    if any(kw in lower for kw in ["go to", "open website", "navigate to", "browse to"]):
        # Extract URL
        url_match = re.search(r'https?://\S+', text)
        if url_match:
            return browser_open_url(url_match.group())
        # Try to find a site name
        site_match = re.search(r'(?:go to|open|navigate to|browse to)\s+(.+?)(?:\s+and|\s+then|$)', lower)
        if site_match:
            site = site_match.group(1).strip()
            sites = {
                "gmail": "https://mail.google.com",
                "google": "https://google.com",
                "youtube": "https://youtube.com",
                "outlook": "https://outlook.live.com",
                "photos": "https://photos.google.com",
                "drive": "https://drive.google.com",
                "calendar": "https://calendar.google.com",
                "maps": "https://maps.google.com",
                "github": "https://github.com",
                "twitter": "https://twitter.com",
                "x": "https://x.com",
                "linkedin": "https://linkedin.com",
                "facebook": "https://facebook.com",
                "instagram": "https://instagram.com",
                "reddit": "https://reddit.com",
                "netflix": "https://netflix.com",
                "spotify": "https://open.spotify.com",
                "amazon": "https://amazon.com",
                "apple": "https://apple.com",
                "microsoft": "https://microsoft.com",
            }
            url = sites.get(site, f"https://{site}.com")
            return browser_open_url(url)
        return "Where would you like me to navigate?"

    # Screen analysis
    if any(kw in lower for kw in ["what's on screen", "what do you see", "describe screen", "screenshot"]):
        path = browser_screenshot()
        return f"Screenshot saved to {path}. Analyzing..."

    # Generic: try to interpret as a task
    return None


# ── For direct testing ───────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "check email for flights"
    print(f"Task: {task}")
    result = handle_autonomous_task(task)
    print(f"Result: {result}")
