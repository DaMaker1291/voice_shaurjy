"""Vision Agent — lightweight action verification using Windows OCR + screenshot analysis. No GPU needed."""

import os
import re
import time
import json
from ps_executor import ps
from desktop_control import screenshot_save


def ocr_screen(region: tuple = None) -> str:
    """Read all text from the screen (or a region) using Windows OCR."""
    if region:
        x, y, w, h = region
        region_ps = f'"$x={x}; $y={y}; $w={w}; $h={h};"'
        crop = f"""
            Add-Type -AssemblyName System.Windows.Forms
            $b = New-Object Drawing.Bitmap($w, $h)
            $g = [Drawing.Graphics]::FromImage($b)
            $g.CopyFromScreen($x, $y, 0, 0, ($w, $h))
        """
    else:
        crop = """
            Add-Type -AssemblyName System.Windows.Forms
            $b = New-Object Drawing.Bitmap(
                [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,
                [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
            )
            $g = [Drawing.Graphics]::FromImage($b)
            $g.CopyFromScreen(0, 0, 0, 0, $b.Size)
        """

    return ps(f"""
        {crop}
        $g.Dispose()
        $ocr = New-Object Windows.Media.Ocr.OcrEngine
        $result = $ocr.RecognizeAsync($b).GetAwaiter().GetResult()
        $b.Dispose()
        if ($result -and $result.Text) {{ $result.Text }} else {{ "" }}
    """)


def verify_action(action: str, expected_text: str = None, timeout: int = 10) -> dict:
    """Execute an action, wait, screenshot, and verify it succeeded using OCR."""
    from actions import execute_action, detect_action

    detected = detect_action(action) or action
    result = execute_action(detected, action)
    time.sleep(1.5)

    screen_text = ocr_screen()

    verified = True
    details = ""
    if expected_text:
        found = expected_text.lower() in screen_text.lower()
        verified = found
        details = f"expected '{expected_text}': {'found' if found else 'not found'}"

    return {
        "action": action,
        "result": result,
        "verified": verified,
        "screen_text": screen_text[:500],
        "details": details,
    }


def verify_change(before_screenshot: str, after_screenshot: str, description: str) -> dict:
    """Compare two screenshots to verify a change occurred (pixel-diff based)."""
    result = ps(f"""
        Add-Type -AssemblyName System.Drawing
        $b1 = [Drawing.Image]::FromFile("{before_screenshot}")
        $b2 = [Drawing.Image]::FromFile("{after_screenshot}")
        if ($b1.Width -ne $b2.Width -or $b1.Height -ne $b2.Height) {{
            "CHANGED (different dimensions)"
            return
        }}
        $diff = 0; $total = $b1.Width * $b1.Height
        $bmp1 = $b1 -as [Drawing.Bitmap]; $bmp2 = $b2 -as [Drawing.Bitmap]
        for ($x=0; $x -lt $b1.Width; $x+=4) {{
            for ($y=0; $y -lt $b1.Height; $y+=4) {{
                $c1 = $bmp1.GetPixel($x,$y); $c2 = $bmp2.GetPixel($x,$y)
                if ($c1 -ne $c2) {{ $diff++ }}
            }}
        }}
        $b1.Dispose(); $b2.Dispose()
        $pct = [math]::Round(($diff / ($total/16)) * 100, 1)
        if ($pct -gt 5) {{ "CHANGED ({0}% pixels differ)" -f $pct }}
        else {{ "UNCHANGED ({0}% pixels differ)" -f $pct }}
    """)
    return {
        "description": description,
        "result": result.strip(),
        "changed": "CHANGED" in result,
    }


def action_with_verification(action: str, params: str = "",
                             expected_result: str = None,
                             retry_count: int = 2) -> dict:
    """Execute an action and verify it succeeded with OCR. Retry if verification fails."""
    from actions import execute_action, detect_action

    detected = detect_action(action) or action
    first_result = execute_action(detected, params)
    time.sleep(1)

    if expected_result:
        screen_text = ocr_screen()
        if expected_result.lower() in screen_text.lower():
            return {"action": action, "result": first_result, "verified": True, "attempts": 1}

        for attempt in range(retry_count):
            time.sleep(0.5)
            retry_result = execute_action(detected, params)
            time.sleep(1)
            screen_text = ocr_screen()
            if expected_result.lower() in screen_text.lower():
                return {"action": action, "result": retry_result, "verified": True, "attempts": attempt + 2}

        return {"action": action, "result": first_result, "verified": False,
                "attempts": retry_count + 1,
                "screen_text": screen_text[:300]}

    return {"action": action, "result": first_result, "verified": True, "attempts": 1}


# ── Web App Launcher (PWA fallback for everything) ────────────────

WEB_APPS = {
    "spotify": "https://open.spotify.com",
    "music": "https://open.spotify.com",
    "word": "https://word.office.com",
    "excel": "https://excel.office.com",
    "powerpoint": "https://powerpoint.office.com",
    "onenote": "https://onenote.com",
    "outlook": "https://outlook.live.com",
    "email": "https://mail.google.com",
    "gmail": "https://mail.google.com",
    "mail": "https://mail.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "slides": "https://slides.google.com",
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "discord": "https://discord.com/app",
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
}


def launch_web_app(app_name: str) -> str:
    """Launch the web version of an app. Falls back to browser search if unknown."""
    url = WEB_APPS.get(app_name.lower())
    if not url:
        url = f"https://google.com/search?q={app_name.replace(' ', '+')}"
    ps(f'Start-Process "chrome.exe" -ArgumentList "--app={url}" 2>$null; if(-not$?){{Start-Process "{url}"}}')
    return f"Opened {app_name} web app"


def launch_in_chrome_pwa(url: str) -> str:
    """Open a URL as a PWA-style window (in Chrome app mode)."""
    ps(f'Start-Process "chrome.exe" -ArgumentList "--app={url}" 2>$null; if(-not$?){{Start-Process "{url}"}}')
    return f"Opened {url}"
