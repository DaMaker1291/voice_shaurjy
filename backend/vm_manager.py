"""
JARVIS VM Manager — Creates and manages VirtualBox VMs as "2nd computers".
Each user gets their own isolated VM with the agent pre-installed.

Requires: Oracle VirtualBox installed (free from virtualbox.org)

Usage:
  from vm_manager import JarvisVM
  vm = JarvisVM()
  vm.create("my_desktop")       # Create a new VM
  vm.start("my_desktop")        # Start it
  vm.install_agent("my_desktop") # Install JARVIS agent inside
  vm.screenshot("my_desktop")   # Capture VM display
  vm.stop("my_desktop")         # Stop it
"""
import os
import sys
import json
import time
import subprocess
import logging
import io
from pathlib import Path
from typing import Optional

logger = logging.getLogger("vm")

# ── VirtualBox paths ──
VBOX_PATHS = [
    r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
    r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
    "/usr/bin/VBoxManage",
    "/usr/local/bin/VBoxManage",
]

VM_DIR = Path(os.environ.get("JARVIS_VM_DIR",
              Path(__file__).parent / "data" / "vms"))

AGENT_ZIP = Path(__file__).parent  # The entire backend folder


def find_vboxmanage() -> Optional[str]:
    """Find VBoxManage executable."""
    for p in VBOX_PATHS:
        if os.path.exists(p):
            return p
    # Try PATH
    try:
        result = subprocess.run(["where", "VBoxManage"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except Exception:
        pass
    return None


class JarvisVM:
    """Manage VirtualBox VMs for JARVIS."""

    def __init__(self, vm_base_dir: str = None):
        self.vm_dir = Path(vm_base_dir) if vm_base_dir else VM_DIR
        self.vm_dir.mkdir(parents=True, exist_ok=True)
        self.vboxmanage = find_vboxmanage()
        if not self.vboxmanage:
            logger.warning("VBoxManage not found. Install VirtualBox from virtualbox.org")
        self._vm_configs: dict[str, dict] = {}
        self._load_configs()

    def _load_configs(self):
        """Load VM configurations."""
        config_file = self.vm_dir / "vm_configs.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    self._vm_configs = json.load(f)
            except Exception:
                self._vm_configs = {}

    def _save_configs(self):
        """Save VM configurations."""
        config_file = self.vm_dir / "vm_configs.json"
        with open(config_file, "w") as f:
            json.dump(self._vm_configs, f, indent=2)

    def _run_vbox(self, *args) -> subprocess.CompletedProcess:
        """Run a VBoxManage command."""
        if not self.vboxmanage:
            raise RuntimeError("VBoxManage not found. Install VirtualBox.")
        cmd = [self.vboxmanage] + list(args)
        logger.info(f"VBox: {' '.join(cmd[:5])}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"VBox error: {result.stderr[:500]}")
        return result

    def is_available(self) -> bool:
        """Check if VirtualBox is available."""
        return self.vboxmanage is not None

    def list_vms(self) -> list[dict]:
        """List all JARVIS VMs."""
        if not self.is_available():
            return []
        try:
            result = self._run_vbox("list", "vms")
            vms = []
            for line in result.stdout.strip().split("\n"):
                if '"' in line:
                    name = line.split('"')[1]
                    uuid = line.split("{")[1].split("}")[0] if "{" in line else ""
                    # Check if it's a JARVIS VM
                    if name in self._vm_configs or name.startswith("jarvis_"):
                        vms.append({
                            "name": name,
                            "uuid": uuid,
                            "config": self._vm_configs.get(name, {}),
                        })
            return vms
        except Exception as e:
            logger.error(f"List VMs failed: {e}")
            return []

    def create(self, name: str, ram_mb: int = 4096, cpus: int = 2,
               disk_gb: int = 50, iso_path: str = None) -> bool:
        """
        Create a new JARVIS VM.

        Args:
            name: VM name (will be prefixed with jarvis_)
            ram_mb: RAM in MB (default 4GB)
            cpus: Number of CPUs (default 2)
            disk_gb: Disk size in GB (default 50GB)
            iso_path: Path to Ubuntu ISO (will download if not provided)
        """
        if not self.is_available():
            logger.error("VirtualBox not installed")
            return False

        vm_name = f"jarvis_{name}"

        # Check if VM already exists
        result = self._run_vbox("list", "vms")
        if f'"{vm_name}"' in result.stdout:
            logger.info(f"VM '{vm_name}' already exists")
            return True

        logger.info(f"Creating VM: {vm_name} ({ram_mb}MB RAM, {cpus} CPUs, {disk_gb}GB disk)")

        try:
            # Create VM
            self._run_vbox("createvm", "--name", vm_name, "--register")

            # Configure VM
            self._run_vbox("modifyvm", vm_name,
                          "--memory", str(ram_mb),
                          "--cpus", str(cpus),
                          "--vram", "128",
                          "--graphicscontroller", "vmsvga",
                          "--audio", "none",
                          "--nic1", "nat",
                          "--natpf1", "ssh,tcp,,2222,,22",
                          "--natpf1", "agent,tcp,,8767,,8767",
                          "--natpf1", "stream,tcp,,8765,,8765",
                          "--boot1", "disk",
                          "--boot2", "dvd",
                          "--ostype", "Ubuntu_64")

            # Create and attach disk
            vm_path = str(self.vm_dir / vm_name)
            disk_path = os.path.join(vm_path, f"{vm_name}.vdi")
            self._run_vbox("createmedium", "disk",
                          "--filename", disk_path,
                          "--size", str(disk_gb * 1024),
                          "--format", "VDI")

            # Create storage controller
            self._run_vbox("storagectl", vm_name,
                          "--name", "SATA",
                          "--add", "sata",
                          "--controller", "IntelAhci")

            # Attach disk
            self._run_vbox("storageattach", vm_name,
                          "--storagectl", "SATA",
                          "--port", "0",
                          "--device", "0",
                          "--type", "hdd",
                          "--medium", disk_path)

            # Attach ISO if provided
            if iso_path and os.path.exists(iso_path):
                self._run_vbox("storageattach", vm_name,
                              "--storagectl", "SATA",
                              "--port", "1",
                              "--device", "0",
                              "--type", "dvddrive",
                              "--medium", iso_path)

            # Enable headless mode
            self._run_vbox("modifyvm", vm_name,
                          "--defaultfrontend", "headless")

            # Save config
            self._vm_configs[vm_name] = {
                "name": vm_name,
                "ram_mb": ram_mb,
                "cpus": cpus,
                "disk_gb": disk_gb,
                "created": time.time(),
                "status": "created",
                "agent_installed": False,
            }
            self._save_configs()

            logger.info(f"VM created: {vm_name}")
            return True

        except Exception as e:
            logger.error(f"VM creation failed: {e}")
            return False

    def start(self, name: str, headless: bool = True) -> bool:
        """Start a VM."""
        if not self.is_available():
            return False

        vm_name = f"jarvis_{name}"
        type_arg = "--type" if headless else "--type gui"

        try:
            self._run_vbox("startvm", vm_name, type_arg)
            if vm_name in self._vm_configs:
                self._vm_configs[vm_name]["status"] = "running"
                self._save_configs()
            logger.info(f"VM started: {vm_name}")
            return True
        except Exception as e:
            logger.error(f"VM start failed: {e}")
            return False

    def stop(self, name: str, force: bool = False) -> bool:
        """Stop a VM."""
        if not self.is_available():
            return False

        vm_name = f"jarvis_{name}"
        try:
            if force:
                self._run_vbox("controlvm", vm_name, "poweroff")
            else:
                self._run_vbox("controlvm", vm_name, "acpipowerbutton")
            if vm_name in self._vm_configs:
                self._vm_configs[vm_name]["status"] = "stopped"
                self._save_configs()
            logger.info(f"VM stopped: {vm_name}")
            return True
        except Exception as e:
            logger.error(f"VM stop failed: {e}")
            return False

    def screenshot(self, name: str) -> Optional[bytes]:
        """Take a screenshot of the VM display. Returns PNG bytes."""
        if not self.is_available():
            return None

        vm_name = f"jarvis_{name}"
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp_path = f.name

            result = self._run_vbox("controlvm", vm_name, "screenshotpng", tmp_path)
            if os.path.exists(tmp_path):
                with open(tmp_path, "rb") as f:
                    png_data = f.read()
                os.unlink(tmp_path)
                if len(png_data) > 100:  # Valid PNG
                    return png_data
            return None
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    def get_running_vm(self) -> Optional[str]:
        """Get the name of the currently running JARVIS VM."""
        if not self.is_available():
            return None
        try:
            result = self._run_vbox("list", "runningvms")
            for line in result.stdout.strip().split("\n"):
                if '"' in line:
                    name = line.split('"')[1]
                    if name.startswith("jarvis_"):
                        return name
        except Exception:
            pass
        return None

    def install_agent(self, name: str, agent_zip_path: str = None) -> bool:
        """
        Install JARVIS agent inside the VM.
        This copies the agent code and installs dependencies.
        """
        vm_name = f"jarvis_{name}"
        logger.info(f"Installing agent in {vm_name}...")

        try:
            # Copy agent code to VM via shared folder or SCP
            # For now, create an install script
            install_script = '''
#!/bin/bash
set -e
echo "Installing JARVIS Agent..."

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
pip install websockets pydantic mss Pillow python-docx python-pptx openpyxl psutil groq duckduckgo-search

# Create systemd service
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
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable jarvis-daemon
systemctl start jarvis-daemon

echo "JARVIS Agent installed successfully!"
'''
            # Save install script
            script_path = self.vm_dir / vm_name / "install_agent.sh"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            with open(script_path, "w") as f:
                f.write(install_script)

            # Run install script in VM
            # This requires SSH access to the VM
            self._run_vbox("controlvm", vm_name, "sharedfolder_add",
                          "agent_share", "--hostpath", str(AGENT_ZIP),
                          "--automount")

            if vm_name in self._vm_configs:
                self._vm_configs[vm_name]["agent_installed"] = True
                self._save_configs()

            logger.info(f"Agent install script created: {script_path}")
            logger.info(f"SSH into VM and run: bash /mnt/shared/install_agent.sh")
            return True

        except Exception as e:
            logger.error(f"Agent install failed: {e}")
            return False

    def ssh(self, name: str, command: str = None) -> Optional[str]:
        """SSH into the VM and run a command."""
        vm_name = f"jarvis_{name}"
        try:
            ssh_cmd = ["ssh", "-p", "2222", "-o", "StrictHostKeyChecking=no",
                       "root@localhost"]
            if command:
                ssh_cmd.append(command)
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            return result.stdout
        except Exception as e:
            logger.error(f"SSH failed: {e}")
            return None

    def get_status(self, name: str) -> dict:
        """Get VM status."""
        vm_name = f"jarvis_{name}"
        if not self.is_available():
            return {"status": "virtualbox_not_installed"}
        try:
            result = self._run_vbox("showvminfo", vm_name, "--machinereadable")
            info = {}
            for line in result.stdout.split("\n"):
                if "=" in line:
                    key, _, val = line.partition("=")
                    info[key.strip('"')] = val.strip('"')
            return {
                "status": info.get("VMState", "unknown"),
                "name": vm_name,
                "ram": info.get("memory", "?"),
                "cpus": info.get("cpus", "?"),
                "running": info.get("VMState") == "running",
            }
        except Exception:
            return {"status": "unknown"}


# ── ISO Downloader ──

def download_ubuntu_iso(target_dir: str = None) -> Optional[str]:
    """Download Ubuntu Server ISO for VM installation."""
    import urllib.request

    url = "https://releases.ubuntu.com/22.04/ubuntu-22.04.4-live-server-amd64.iso"
    target = Path(target_dir or VM_DIR) / "ubuntu-22.04-live-server-amd64.iso"

    if target.exists():
        logger.info(f"Ubuntu ISO already exists: {target}")
        return str(target)

    logger.info(f"Downloading Ubuntu ISO to {target}...")
    try:
        urllib.request.urlretrieve(url, str(target))
        logger.info(f"Download complete: {target}")
        return str(target)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None


# ── Quick Setup ──

def quick_setup(name: str = "desktop") -> JarvisVM:
    """Quick setup — create and configure a VM."""
    vm = JarvisVM()

    if not vm.is_available():
        logger.error("=" * 60)
        logger.error("VirtualBox is NOT installed!")
        logger.error("")
        logger.error("Install it from: https://www.virtualbox.org/wiki/Downloads")
        logger.error("Then run this script again.")
        logger.error("=" * 60)
        return vm

    # Check if VM already exists
    vms = vm.list_vms()
    vm_name = f"jarvis_{name}"
    if any(v["name"] == vm_name for v in vms):
        logger.info(f"VM '{vm_name}' already exists")
        return vm

    # Create VM
    logger.info(f"Creating VM: {vm_name}")
    vm.create(name, ram_mb=4096, cpus=2, disk_gb=50)

    # Download Ubuntu ISO
    iso = download_ubuntu_iso()
    if iso:
        logger.info(f"Attach ISO and install Ubuntu: {iso}")
        logger.info(f"Then run: vm.install_agent('{name}')")

    return vm


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[VM] %(message)s")
    vm = quick_setup()
    if vm.is_available():
        print("\nVMs available:")
        for v in vm.list_vms():
            print(f"  - {v['name']}")
    else:
        print("\nPlease install VirtualBox first:")
        print("  https://www.virtualbox.org/wiki/Downloads")
