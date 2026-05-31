"""Device scanner — reads local files, calendar, contacts, system info via PowerShell."""

import subprocess
import json
import os
from pathlib import Path


def _ps(cmd: str) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout.strip()
    except:
        return ""


def scan_filesystem(max_files: int = 50) -> list[dict]:
    """Scan common user directories for documents."""
    dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
    ]
    files = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in Path(d).glob("*"):
            if f.suffix.lower() in (".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".log"):
                try:
                    size = f.stat().st_size
                    if size > 0 and size < 1024 * 1024:  # skip empty or >1MB
                        files.append({
                            "name": f.name,
                            "path": str(f),
                            "size": size,
                            "modified": f.stat().st_mtime,
                        })
                except:
                    pass
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            break
    return files


def read_calendar(days: int = 7) -> list[dict]:
    """Read Windows Calendar events via PowerShell COM."""
    script = f"""
    $events = @()
    $outlook = New-Object -ComObject Outlook.Application -ErrorAction SilentlyContinue
    if (-not $outlook) {{ return "[]" }}
    $namespace = $outlook.GetNamespace("MAPI")
    $calendar = $namespace.GetDefaultFolder(9)
    $filter = "[Start] >= '{_ps("Get-Date -Format 'yyyy-MM-dd'")}' AND [Start] <= '{_ps("(Get-Date).AddDays({days}).ToString('yyyy-MM-dd')")}'"
    $items = $calendar.Items
    $items.Sort("[Start]")
    $items.IncludeRecurrences = $true
    foreach ($item in $items) {{
        $events += @{{
            subject = $item.Subject
            start = $item.Start.ToString("yyyy-MM-dd HH:mm")
            end = $item.End.ToString("yyyy-MM-dd HH:mm")
            location = $item.Location
        }}
    }}
    return ($events | ConvertTo-Json -Compress)
    """
    try:
        result = _ps(script)
        return json.loads(result) if result else []
    except:
        return []


def get_system_info() -> dict:
    """Gather basic system information."""
    info = {
        "os": _ps("(Get-CimInstance Win32_OperatingSystem).Caption"),
        "version": _ps("[Environment]::OSVersion.VersionString"),
        "hostname": _ps("hostname"),
        "user": _ps("[Environment]::UserName"),
        "cpu": _ps("(Get-CimInstance Win32_Processor).Name"),
        "ram_gb": _ps("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)"),
        "uptime_hours": _ps("[math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 1)"),
    }
    return info


def scan_device(user_id: str) -> dict:
    """Full device scan — returns structured data about the user's system."""
    result = {
        "system": get_system_info(),
        "recent_files": scan_filesystem(30),
        "calendar_events": read_calendar(7),
    }
    return result
