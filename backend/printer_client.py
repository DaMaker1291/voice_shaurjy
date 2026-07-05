"""
JARVIS Printer Client
======================
Real HP Printer control via IPP (Internet Printing Protocol).
Sends real print jobs, gets real printer status, ink levels, etc.
"""

import os
import time
import threading
import subprocess
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class PrinterDevice:
    """A real printer on the local network."""
    ip: str
    name: str
    model: str = ""
    manufacturer: str = "HP"
    protocol: str = "ipp"
    is_online: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    last_action: float = 0.0
    uri: str = ""

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "name": self.name,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "protocol": self.protocol,
            "is_online": self.is_online,
            "state": self.state,
            "last_action": self.last_action,
            "uri": self.uri,
        }


class PrinterClient:
    """
    Real HP Printer controller via IPP.
    Uses system `ipptool` or `lpstat` for printer operations.
    """

    def __init__(self):
        self._printers: Dict[str, PrinterDevice] = {}
        self._lock = threading.Lock()

    def add_printer(self, ip: str, name: str = "", model: str = "") -> PrinterDevice:
        """Register a printer by IP."""
        with self._lock:
            printer = PrinterDevice(
                ip=ip,
                name=name or f"Printer {ip}",
                model=model,
                uri=f"ipp://{ip}/ipp/print",
            )
            self._printers[ip] = printer
            return printer

    def get_printer_status(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get real printer status via IPP."""
        printer = self._printers.get(ip)
        if not printer:
            return None

        try:
            # Try lpstat first
            result = subprocess.run(
                ["lpstat", "-p", "-l"],
                capture_output=True, text=True, timeout=5
            )

            # Try IPP query
            ipp_result = subprocess.run(
                ["ipptool", "-I", "-t", f"ipp://{ip}/ipp/print", "get-printer-attributes.fdo"],
                capture_output=True, text=True, timeout=10
            )

            if ipp_result.returncode == 0:
                printer.is_online = True
                # Parse IPP response for status
                output = ipp_result.stdout
                state = {}

                if "printer-is-accepting-jobs" in output:
                    state["accepting_jobs"] = "true" in output.split("printer-is-accepting-jobs:")[1].split("\n")[0]
                if "printer-state:" in output:
                    state_val = output.split("printer-state:")[1].split("\n")[0].strip()
                    state["state"] = {3: "idle", 4: "printing", 5: "stopped"}.get(int(state_val) if state_val.isdigit() else 0, "unknown")
                if "printer-state-reasons:" in output:
                    state["reasons"] = output.split("printer-state-reasons:")[1].split("\n")[0].strip()
                if "printer-name:" in output:
                    state["printer_name"] = output.split("printer-name:")[1].split("\n")[0].strip()
                if "printer-make-and-model:" in output:
                    state["model"] = output.split("printer-make-and-model:")[1].split("\n")[0].strip()
                    printer.model = state["model"]

                printer.state = state
                printer.last_action = time.time()
                return printer.to_dict()
            else:
                # Fallback: try basic connectivity check
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((ip, 631))
                sock.close()
                printer.is_online = result == 0
                if printer.is_online:
                    printer.state = {"status": "connected"}
                    printer.last_action = time.time()
                return printer.to_dict()

        except Exception as e:
            printer.is_online = False
            return printer.to_dict()

    def get_ink_levels(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get real ink levels from an HP printer."""
        try:
            # HP printers expose ink levels via SNMP or web interface
            import urllib.request
            url = f"http://{ip}/hp/device/info_INK.htm"
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
            response = urllib.request.urlopen(req, timeout=5)
            html = response.read().decode("utf-8", errors="ignore")

            ink_data = {}
            # Parse ink levels from HP web interface
            import re
            # Look for percentage values
            percentages = re.findall(r'(\d+)%', html)
            colors = ["black", "cyan", "magenta", "yellow"]
            for i, pct in enumerate(percentages[:4]):
                if i < len(colors):
                    ink_data[colors[i]] = int(pct)

            return ink_data if ink_data else {"status": "unable_to_read"}
        except Exception:
            return {"status": "unable_to_read"}

    def print_file(self, ip: str, file_path: str, copies: int = 1) -> Dict[str, Any]:
        """Send a real print job to the printer."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            printer = self._printers.get(ip)
            if not printer:
                return {"success": False, "error": "Printer not registered"}

            # Use lp command to send print job
            cmd = ["lp", "-d", printer.name, "-n", str(copies), file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                printer.last_action = time.time()
                return {
                    "success": True,
                    "action": "print",
                    "file": file_path,
                    "copies": copies,
                    "printer": printer.name,
                    "output": result.stdout.strip(),
                }
            else:
                return {"success": False, "error": result.stderr.strip()}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_jobs(self, ip: str) -> Dict[str, Any]:
        """Cancel all pending print jobs."""
        try:
            printer = self._printers.get(ip)
            if not printer:
                return {"success": False, "error": "Printer not registered"}

            result = subprocess.run(
                ["cancel", "-a", printer.name],
                capture_output=True, text=True, timeout=10
            )

            return {"success": result.returncode == 0, "action": "cancel_all"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_queue(self, ip: str) -> List[Dict[str, Any]]:
        """Get the current print queue."""
        try:
            printer = self._printers.get(ip)
            if not printer:
                return []

            result = subprocess.run(
                ["lpq", "-P", printer.name],
                capture_output=True, text=True, timeout=5
            )

            jobs = []
            for line in result.stdout.splitlines()[2:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    jobs.append({
                        "job_id": parts[0],
                        "user": parts[1] if len(parts) > 1 else "",
                        "status": parts[2] if len(parts) > 2 else "",
                        "size": parts[3] if len(parts) > 3 else "",
                        "file": " ".join(parts[4:]) if len(parts) > 4 else "",
                    })
            return jobs
        except Exception:
            return []

    def discover_printers(self) -> List[Dict[str, Any]]:
        """Discover printers on the local network."""
        discovered = []
        try:
            # Use lpstat to find configured printers
            result = subprocess.run(
                ["lpstat", "-a"],
                capture_output=True, text=True, timeout=5
            )

            for line in result.stdout.splitlines():
                if "enabled" in line.lower() or "idle" in line.lower():
                    name = line.split()[0]
                    discovered.append({
                        "name": name,
                        "status": line,
                        "protocol": "ipp",
                    })

            # Also scan for printers via arp
            import re
            arp_result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=15)
            for line in arp_result.stdout.splitlines():
                if "hp" in line.lower() or "printer" in line.lower() or "hp33b" in line.lower():
                    match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                    if match:
                        ip = match.group(1)
                        discovered.append({
                            "ip": ip,
                            "name": line.split("(")[0].strip() if "(" in line else f"Printer {ip}",
                            "protocol": "ipp",
                            "manufacturer": "HP",
                        })
        except Exception:
            pass

        return discovered

    def get_all_printers(self) -> List[Dict[str, Any]]:
        """Get status of all registered printers."""
        printers = []
        with self._lock:
            for ip, printer in self._printers.items():
                try:
                    self.get_printer_status(ip)
                except Exception:
                    pass
                printers.append(printer.to_dict())
        return printers


# ── Global singleton ───────────────────────────────────────

_printer: Optional[PrinterClient] = None
_printer_lock = threading.Lock()


def get_printer_client() -> PrinterClient:
    """Get or create the global PrinterClient instance."""
    global _printer
    with _printer_lock:
        if _printer is None:
            _printer = PrinterClient()
        return _printer
