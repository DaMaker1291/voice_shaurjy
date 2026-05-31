"""Deep device scanner — apps, accounts, browser data, system, network, files."""

import subprocess
import json
import os
import socket
from pathlib import Path
from datetime import datetime


def _ps(cmd: str) -> str:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except:
        return ""


# ── System ────────────────────────────────────────────────────

def get_system() -> dict:
    return {
        "os": _ps("(Get-CimInstance Win32_OperatingSystem).Caption"),
        "version": _ps("[Environment]::OSVersion.VersionString"),
        "arch": _ps("(Get-CimInstance Win32_ComputerSystem).SystemType"),
        "hostname": _ps("hostname"),
        "user": _ps("[Environment]::UserName"),
        "domain": _ps("[Environment]::UserDomainName"),
        "cpu": _ps("(Get-CimInstance Win32_Processor).Name"),
        "cores": _ps("(Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors"),
        "ram_gb": _ps("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)"),
        "disk_free_gb": _ps("$d=Get-PSDrive C; [math]::Round($d.Free/1GB,1)"),
        "disk_total_gb": _ps("$d=Get-PSDrive C; [math]::Round(($d.Used+$d.Free)/1GB,1)"),
        "uptime_hours": _ps("[math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours,1)"),
        "boot_time": _ps("(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"),
        "timezone": _ps("(Get-TimeZone).Id"),
        "culture": _ps("[System.Globalization.CultureInfo]::CurrentCulture.Name"),
        "battery": _ps("$b=Get-CimInstance Win32_Battery; if($b){[math]::Round($b.EstimatedChargeRemaining,0)}else{'desktop'}"),
        "screen_res": _ps("(Get-CimInstance Win32_VideoController).VideoModeDescription -join '; '"),
        "gpu": _ps("(Get-CimInstance Win32_VideoController).Name"),
    }


# ── Installed apps ────────────────────────────────────────────

def get_installed_apps() -> list[dict]:
    script = '''
    $apps = @()
    $paths = @(
        "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
        "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",
        "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*"
    )
    foreach ($p in $paths) {
        Get-ItemProperty $p -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.DisplayName) {
                $apps += @{name=$_.DisplayName; version=$_.DisplayVersion; vendor=$_.Publisher; install_date=$_.InstallDate}
            }
        }
    }
    return ($apps | ConvertTo-Json -Compress)
    '''
    try:
        result = _ps(script)
        apps = json.loads(result) if result else []
        return sorted(apps, key=lambda a: a.get("name", "").lower())[:100]
    except:
        return []


# ── Startup programs ──────────────────────────────────────────

def get_startup() -> list[str]:
    raw = _ps("Get-CimInstance Win32_StartupCommand | Select-Object -ExpandProperty Name -ErrorAction SilentlyContinue")
    return [s.strip() for s in raw.splitlines() if s.strip()] if raw else []


# ── Running processes (top memory) ────────────────────────────

def get_running_processes(top: int = 20) -> list[dict]:
    script = (
        "Get-Process | Sort-Object WorkingSet -Descending | "
        "Select-Object -First %d Name,Id,@{N='MB';E={[math]::Round($_.WorkingSet/1MB,1)}} | "
        "ConvertTo-Json -Compress"
    ) % top
    try:
        result = _ps(script)
        return json.loads(result) if result else []
    except:
        return []


# ── Services ──────────────────────────────────────────────────

def get_services() -> list[dict]:
    script = '''
    Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name,DisplayName,StartType | ConvertTo-Json -Compress
    '''
    try:
        result = _ps(script)
        return json.loads(result) if result and result.startswith("[") else []
    except:
        return []


# ── Scheduled tasks ───────────────────────────────────────────

def get_scheduled_tasks() -> list[str]:
    raw = _ps("Get-ScheduledTask -TaskPath '\\' -ErrorAction SilentlyContinue | Where-Object State -ne 'Disabled' | Select-Object -ExpandProperty TaskName")
    return [s.strip() for s in raw.splitlines() if s.strip()][:30] if raw else []


# ── Network ───────────────────────────────────────────────────

def get_network() -> dict:
    return {
        "hostname": socket.gethostname(),
        "local_ip": _ps("(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).IPAddress"),
        "dns": _ps("(Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses"),
        "mac": _ps("(Get-NetAdapter -Name 'Wi-Fi','Ethernet' -ErrorAction SilentlyContinue).MacAddress"),
        "gateway": _ps("(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop"),
        "wifi_ssid": _ps("(Get-NetConnectionProfile -ErrorAction SilentlyContinue).Name"),
        "interfaces": _ps("(Get-NetAdapter -ErrorAction SilentlyContinue | Select-Object Name,Status,LinkSpeed | ConvertTo-Json -Compress)"),
    }


# ── User accounts ─────────────────────────────────────────────

def get_user_accounts() -> list[dict]:
    script = '''
    Get-LocalUser | Select-Object Name,Enabled,LastLogon,PasswordLastSet,UserMayChangePassword,PasswordRequired,Description | ConvertTo-Json -Compress
    '''
    try:
        result = _ps(script)
        return json.loads(result) if result and result.startswith("[") else []
    except:
        return []


# ── Environment variables ─────────────────────────────────────

def get_env() -> dict:
    raw = _ps("Get-ChildItem Env: | Format-Table -AutoSize -HideTableHeaders | Out-String")
    env = {}
    for line in (raw or "").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return dict(list(env.items())[:40])


# ── Browser data (Chrome/Edge profiles) ───────────────────────

def get_browser_profiles() -> list[dict]:
    profiles = []
    browsers = {
        "Chrome": os.path.expanduser("~/AppData/Local/Google/Chrome/User Data"),
        "Edge": os.path.expanduser("~/AppData/Local/Microsoft/Edge/User Data"),
        "Brave": os.path.expanduser("~/AppData/Local/BraveSoftware/Brave-Browser/User Data"),
    }
    for name, path in browsers.items():
        local_state = Path(path) / "Local State"
        if local_state.exists():
            try:
                data = json.loads(local_state.read_text(encoding="utf-8", errors="ignore"))
                info = data.get("profile", {}).get("info_cache", {})
                for pid, pdata in info.items():
                    profiles.append({
                        "browser": name,
                        "profile": pid,
                        "name": pdata.get("name", ""),
                        "user_name": pdata.get("user_name", ""),
                        "email": pdata.get("email", ""),
                        "is_signed_in": bool(pdata.get("email")),
                    })
            except:
                pass
    return profiles


# ── Git config ────────────────────────────────────────────────

def get_git_config() -> dict:
    result = {
        "global_user": _ps("git config --global user.name 2>$null"),
        "global_email": _ps("git config --global user.email 2>$null"),
    }
    return result


# ── SSH keys ──────────────────────────────────────────────────

def get_ssh_keys() -> list[str]:
    ssh_dir = Path(os.path.expanduser("~/.ssh"))
    if ssh_dir.exists():
        return [str(p) for p in ssh_dir.glob("id_*") if p.name != "id_rsa.pub"]
    return []


# ── OneDrive / cloud storage ──────────────────────────────────

def get_cloud_storage() -> dict:
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveCommercial")
    return {
        "onedrive_path": onedrive or "",
        "onedrive_exists": bool(onedrive and Path(onedrive).exists()),
    }


# ── Recent documents ──────────────────────────────────────────

def get_recent_files(max_files: int = 50) -> list[dict]:
    recent = Path(os.path.expanduser("~/AppData/Roaming/Microsoft/Windows/Recent"))
    files = []
    dirs_to_scan = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
    ]
    for d in dirs_to_scan:
        if not os.path.isdir(d):
            continue
        for f in Path(d).glob("*"):
            if f.suffix.lower() in (".txt", ".md", ".pdf", ".docx", ".doc", ".xlsx", ".csv", ".json", ".log", ".py", ".js", ".ts", ".html", ".css", ".jpg", ".png"):
                try:
                    files.append({
                        "name": f.name,
                        "path": str(f),
                        "size_kb": round(f.stat().st_size / 1024, 1),
                        "ext": f.suffix.lower(),
                    })
                except:
                    pass
                if len(files) >= max_files:
                    break
        if len(files) >= max_files:
            break
    return files


# ── WiFi profiles (saved networks) ────────────────────────────

def get_wifi_profiles() -> list[str]:
    raw = _ps("(netsh wlan show profiles) | Select-String 'All User Profile' | ForEach-Object { $_ -replace '.*:\\s*', '' }")
    return [s.strip() for s in raw.splitlines() if s.strip()] if raw else []


# ── Windows features ──────────────────────────────────────────

def get_windows_features() -> dict:
    return {
        "defender": _ps("(Get-MpComputerStatus -ErrorAction SilentlyContinue).RealTimeProtectionEnabled"),
        "firewall": _ps("(Get-NetFirewallProfile -Profile Domain,Public,Private -ErrorAction SilentlyContinue | Where-Object {$_.Enabled -eq 'True'}).Count -eq 3"),
        "bitlocker": _ps("(Get-BitLockerVolume -MountPoint C -ErrorAction SilentlyContinue).ProtectionStatus"),
        "powershell_version": _ps("$PSVersionTable.PSVersion"),
    }


# ── System locale / language ─────────────────────────────────

def get_locale() -> dict:
    return {
        "keyboard": _ps("(Get-WinUserLanguageList).InputMethodTips"),
        "language": _ps("(Get-WinUserLanguageList).LanguageTag -join ', '"),
        "region": _ps("(Get-Culture).DisplayName"),
    }


# ── Full scan ─────────────────────────────────────────────────

_SCAN_CACHE: dict | None = None

def scan_device(user_id: str, force: bool = False) -> dict:
    global _SCAN_CACHE
    if _SCAN_CACHE and not force:
        return _SCAN_CACHE

    import threading
    results = {}
    threads = []

    def scan_system():
        results["system"] = get_system()
    def scan_apps():
        results["installed_apps"] = get_installed_apps()
    def scan_processes():
        results["running_processes"] = get_running_processes(15)
    def scan_network():
        results["network"] = get_network()
    def scan_accounts():
        results["user_accounts"] = get_user_accounts()
    def scan_browsers():
        results["browser_profiles"] = get_browser_profiles()
    def scan_files():
        results["recent_files"] = get_recent_files(30)
    def scan_services():
        results["services"] = get_services()
    def scan_startup():
        results["startup"] = get_startup()
    def scan_env():
        results["environment"] = get_env()
    def scan_git():
        results["git"] = get_git_config()
    def scan_cloud():
        results["cloud"] = get_cloud_storage()
    def scan_wifi():
        results["wifi_profiles"] = get_wifi_profiles()
    def scan_features():
        results["windows_features"] = get_windows_features()
    def scan_locale():
        results["locale"] = get_locale()
    def scan_scheduled():
        results["scheduled_tasks"] = get_scheduled_tasks()
    def scan_ssh():
        results["ssh_keys"] = get_ssh_keys()

    scans = [
        scan_system, scan_apps, scan_processes, scan_network,
        scan_accounts, scan_browsers, scan_files, scan_services,
        scan_startup, scan_env, scan_git, scan_cloud, scan_wifi,
        scan_features, scan_locale, scan_scheduled, scan_ssh,
    ]
    for s in scans:
        t = threading.Thread(target=s, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=15)

    results["scan_time"] = datetime.now().isoformat()
    results["user_id"] = user_id
    _SCAN_CACHE = results
    return results
