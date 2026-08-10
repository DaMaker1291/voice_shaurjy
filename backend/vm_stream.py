"""
JARVIS VM Stream — Captures VirtualBox VM display and streams to browser.
Extends stream_server.py with VM display source.

Usage:
  from vm_stream import start_vm_stream
  start_vm_stream("jarvis_desktop")  # Stream VM display to viewer
  
Or standalone:
  python vm_stream.py --vm jarvis_desktop
"""
import asyncio
import base64
import io
import os
import subprocess
import time
import threading
import logging

logger = logging.getLogger("vm_stream")

try:
    from PIL import Image
except ImportError:
    from mss import mss
    Image = None

# ── VirtualBox display capture ──

class VMFrameCapturer:
    """Captures frames from a VirtualBox VM via VBoxManage screenshotpng."""

    def __init__(self, vm_name: str):
        self.vm_name = vm_name
        self.vboxmanage = self._find_vboxmanage()
        self._frame: bytes | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._fps = 10

    def _find_vboxmanage(self) -> str:
        paths = [
            r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
            r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
            "/usr/bin/VBoxManage",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        try:
            result = subprocess.run(["where", "VBoxManage"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return "VBoxManage"

    def _capture_once(self) -> bytes | None:
        """Take a single screenshot from the VM."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        try:
            result = subprocess.run(
                [self.vboxmanage, "controlvm", self.vm_name, "screenshotpng", tmp],
                capture_output=True, text=True, timeout=10
            )
            if os.path.exists(tmp):
                with open(tmp, "rb") as f:
                    data = f.read()
                os.unlink(tmp)
                if len(data) > 100:
                    return data
            return None
        except Exception as e:
            logger.error(f"VM screenshot failed: {e}")
            if os.path.exists(tmp):
                os.unlink(tmp)
            return None

    def _capture_loop(self):
        """Background thread capturing VM frames."""
        interval = 1.0 / self._fps
        while self._running:
            frame = self._capture_once()
            if frame:
                self._frame = frame
            time.sleep(interval)

    def start(self):
        """Start capturing VM frames."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"VM capture started: {self.vm_name} @ {self._fps} fps")

    def stop(self):
        """Stop capturing."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info(f"VM capture stopped: {self.vm_name}")

    def get_latest_frame(self) -> bytes | None:
        """Get the latest captured frame as JPEG bytes."""
        if not self._frame:
            return None
        try:
            img = Image.open(io.BytesIO(self._frame))
            img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=60)
            return out.getvalue()
        except Exception:
            return self._frame


# ── Integration with stream_server.py ──

def set_vm_source(vm_name: str):
    """Switch stream_server to capture from a VM."""
    try:
        import stream_server
        capturer = VMFrameCapturer(vm_name)
        capturer.start()
        stream_server.set_vdi_source(capturer)
        logger.info(f"Stream source set to VM: {vm_name}")
        return capturer
    except ImportError:
        logger.error("stream_server.py not found")
        return None


def set_local_source():
    """Switch stream_server back to local desktop capture."""
    try:
        import stream_server
        stream_server.set_desktop_source()
        logger.info("Stream source set to local desktop")
    except ImportError:
        pass


# ── Standalone VM stream ──

async def vm_stream_main(vm_name: str, host: str = "127.0.0.1", port: int = 8765):
    """Run a standalone stream server for a VM."""
    import stream_server

    # Set VM as source
    capturer = VMFrameCapturer(vm_name)
    capturer.start()
    stream_server.set_vdi_source(capturer)

    logger.info(f"Streaming VM '{vm_name}' to http://{host}:{port}")
    await stream_server.main(host, port)


# ── One-Click VM Provisioning ──

class VMProvisioner:
    """
    One-click VM provisioning.
    Creates a VirtualBox VM, installs Ubuntu, installs the JARVIS agent.
    """

    def __init__(self):
        self.vm_manager = None
        self._init_vm_manager()

    def _init_vm_manager(self):
        try:
            from vm_manager import JarvisVM
            self.vm_manager = JarvisVM()
        except ImportError:
            logger.error("vm_manager.py not found")

    def is_ready(self) -> bool:
        """Check if VirtualBox is available."""
        return self.vm_manager and self.vm_manager.is_available()

    def get_or_create_vm(self, name: str = "desktop") -> dict:
        """Get existing VM or create a new one."""
        if not self.is_ready():
            return {"error": "VirtualBox not installed. Download from virtualbox.org"}

        vm_name = f"jarvis_{name}"

        # Check if VM exists
        vms = self.vm_manager.list_vms()
        existing = [v for v in vms if v["name"] == vm_name]
        if existing:
            return {"status": "exists", "name": vm_name, "vm": existing[0]}

        # Create VM
        success = self.vm_manager.create(name, ram_mb=4096, cpus=2, disk_gb=50)
        if success:
            return {"status": "created", "name": vm_name}
        else:
            return {"error": "VM creation failed"}

    def start_vm(self, name: str = "desktop") -> dict:
        """Start the VM."""
        if not self.is_ready():
            return {"error": "VirtualBox not installed"}

        vm_name = f"jarvis_{name}"

        # Check if already running
        running = self.vm_manager.get_running_vm()
        if running == vm_name:
            return {"status": "already_running", "name": vm_name}

        # Start VM
        success = self.vm_manager.start(name, headless=True)
        if success:
            return {"status": "started", "name": vm_name}
        else:
            return {"error": "VM start failed"}

    def stop_vm(self, name: str = "desktop") -> dict:
        """Stop the VM."""
        if not self.is_ready():
            return {"error": "VirtualBox not installed"}

        success = self.vm_manager.stop(name, force=True)
        if success:
            return {"status": "stopped"}
        else:
            return {"error": "VM stop failed"}

    def get_status(self, name: str = "desktop") -> dict:
        """Get VM status."""
        if not self.is_ready():
            return {"status": "virtualbox_not_installed"}

        return self.vm_manager.get_status(name)

    def provision_full(self, name: str = "desktop") -> dict:
        """
        Full provisioning:
        1. Create VM if not exists
        2. Start VM
        3. Wait for VM to boot
        4. Install agent via SSH
        """
        steps = []

        # Step 1: Create
        result = self.get_or_create_vm(name)
        steps.append(("create", result))
        if "error" in result:
            return {"error": result["error"], "steps": steps}

        # Step 2: Start
        result = self.start_vm(name)
        steps.append(("start", result))
        if "error" in result:
            return {"error": result["error"], "steps": steps}

        # Step 3: Wait for boot
        logger.info("Waiting for VM to boot...")
        time.sleep(30)  # Wait for Ubuntu to boot

        # Step 4: Install agent
        result = self.install_agent_via_ssh(name)
        steps.append(("install", result))

        return {"status": "provisioned", "steps": steps}

    def install_agent_via_ssh(self, name: str = "desktop") -> dict:
        """Install the JARVIS agent inside the VM via SSH."""
        vm_name = f"jarvis_{name}"

        # Generate install script
        install_script = self._generate_install_script()

        try:
            # SSH into VM and run install script
            ssh_cmd = [
                "ssh", "-p", "2222",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "root@localhost",
                install_script
            ]
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return {"status": "installed", "output": result.stdout[-500:]}
            else:
                return {"error": result.stderr[-500:]}
        except subprocess.TimeoutExpired:
            return {"error": "SSH timeout — VM may still be booting"}
        except Exception as e:
            return {"error": str(e)}

    def _generate_install_script(self) -> str:
        """Generate the agent install script for the VM."""
        return '''#!/bin/bash
set -e
echo "=== JARVIS Agent Installer ==="

# Update system
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl wget

# Create agent directory
mkdir -p /opt/jarvis
cd /opt/jarvis

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install websockets pydantic Pillow python-docx python-pptx openpyxl psutil groq duckduckgo-search mss pyautogui pynput

# Create systemd service for the agent
cat > /etc/systemd/system/jarvis-daemon.service << 'EOF'
[Unit]
Description=JARVIS Agent Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/jarvis
ExecStart=/opt/jarvis/venv/bin/python -m jarvis_vm_daemon
Restart=always
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable jarvis-daemon

echo "=== JARVIS Agent Installed ==="
echo "Run: systemctl start jarvis-daemon"
'''


# ── CLI entry point ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS VM Stream")
    parser.add_argument("--vm", default="jarvis_desktop", help="VM name to stream")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--provision", action="store_true", help="Provision a new VM")
    parser.add_argument("--status", action="store_true", help="Show VM status")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[VM] %(message)s")

    if args.provision:
        provisioner = VMProvisioner()
        if not provisioner.is_ready():
            print("VirtualBox not installed!")
            print("Download from: https://www.virtualbox.org/wiki/Downloads")
            print("Then run: python vm_stream.py --provision")
            return
        print("Provisioning VM...")
        result = provisioner.provision_full()
        print(f"Result: {result}")
        return

    if args.status:
        provisioner = VMProvisioner()
        status = provisioner.get_status(args.vm)
        print(f"VM Status: {status}")
        return

    # Stream VM display
    asyncio.run(vm_stream_main(args.vm, args.host, args.port))


if __name__ == "__main__":
    main()
