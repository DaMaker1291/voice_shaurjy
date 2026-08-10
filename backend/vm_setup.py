"""
JARVIS VM Setup Helper — Guides you through setting up a VirtualBox VM.
This gives you a "2nd computer" where the agent runs without touching your desktop.

Usage:
  python vm_setup.py              # Check status and guide setup
  python vm_setup.py --install    # Try to install VirtualBox (Windows)
  python vm_setup.py --create     # Create a new VM
  python vm_setup.py --start      # Start the VM
  python vm_setup.py --stream     # Stream VM display to browser
"""
import os
import sys
import subprocess
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="[VM SETUP] %(message)s")
logger = logging.getLogger("vm_setup")


def check_virtualbox() -> dict:
    """Check VirtualBox installation status."""
    paths = [
        r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
        r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
        "/usr/bin/VBoxManage",
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                result = subprocess.run([p, "--version"], capture_output=True, text=True)
                return {"installed": True, "path": p, "version": result.stdout.strip()}
            except Exception:
                pass

    try:
        result = subprocess.run(["where", "VBoxManage"], capture_output=True, text=True)
        if result.returncode == 0:
            path = result.stdout.strip().split("\n")[0]
            result2 = subprocess.run([path, "--version"], capture_output=True, text=True)
            return {"installed": True, "path": path, "version": result2.stdout.strip()}
    except Exception:
        pass

    return {"installed": False}


def check_vm_exists(name: str = "desktop") -> dict:
    """Check if a JARVIS VM exists."""
    vbox = check_virtualbox()
    if not vbox["installed"]:
        return {"exists": False, "reason": "VirtualBox not installed"}

    try:
        result = subprocess.run(
            [vbox["path"], "list", "vms"],
            capture_output=True, text=True
        )
        vm_name = f"jarvis_{name}"
        if f'"{vm_name}"' in result.stdout:
            return {"exists": True, "name": vm_name}
        return {"exists": False, "name": vm_name}
    except Exception as e:
        return {"exists": False, "reason": str(e)}


def download_virtualbox():
    """Download VirtualBox installer."""
    import urllib.request

    url = "https://download.virtualbox.org/virtualbox/7.0.14/VirtualBox-7.0.14-161095-Win.exe"
    target = os.path.join(os.environ.get("TEMP", "."), "VirtualBox-7.0.14-Win.exe")

    if os.path.exists(target):
        logger.info(f"VirtualBox installer already downloaded: {target}")
        return target

    logger.info(f"Downloading VirtualBox from {url}...")
    logger.info("This may take a few minutes...")

    try:
        urllib.request.urlretrieve(url, target)
        logger.info(f"Download complete: {target}")
        return target
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return None


def install_virtualbox():
    """Download and install VirtualBox silently."""
    installer = download_virtualbox()
    if not installer:
        return False

    logger.info("Installing VirtualBox (this may take a few minutes)...")
    try:
        # Silent install
        result = subprocess.run(
            [installer, "--silent", "--extract", "--wait", "-"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            logger.info("VirtualBox installed successfully!")
            return True
        else:
            logger.error(f"Installation failed: {result.stderr[:500]}")
            return False
    except Exception as e:
        logger.error(f"Installation error: {e}")
        return False


def create_vm(name: str = "desktop"):
    """Create a new JARVIS VM."""
    try:
        from vm_manager import JarvisVM
        vm = JarvisVM()

        if not vm.is_available():
            logger.error("VirtualBox not installed. Run: python vm_setup.py --install")
            return False

        logger.info(f"Creating VM: jarvis_{name} (4GB RAM, 2 CPUs, 50GB disk)")
        success = vm.create(name, ram_mb=4096, cpus=2, disk_gb=50)

        if success:
            logger.info("VM created successfully!")
            logger.info("Next steps:")
            logger.info("  1. Download Ubuntu ISO: python vm_setup.py --download-iso")
            logger.info("  2. Start VM: python vm_setup.py --start")
            logger.info("  3. Install Ubuntu from ISO")
            logger.info("  4. Install agent: python vm_setup.py --install-agent")
        else:
            logger.error("VM creation failed")

        return success
    except ImportError:
        logger.error("vm_manager.py not found")
        return False


def start_vm(name: str = "desktop"):
    """Start the VM."""
    try:
        from vm_manager import JarvisVM
        vm = JarvisVM()

        if not vm.is_available():
            logger.error("VirtualBox not installed")
            return False

        logger.info(f"Starting VM: jarvis_{name}")
        success = vm.start(name, headless=True)

        if success:
            logger.info("VM started!")
            logger.info("Stream viewer: python vm_stream.py")
        else:
            logger.error("VM start failed")

        return success
    except ImportError:
        logger.error("vm_manager.py not found")
        return False


def stream_vm(name: str = "desktop"):
    """Stream VM display to browser."""
    try:
        import asyncio
        from vm_stream import vm_stream_main

        logger.info(f"Streaming VM: jarvis_{name}")
        logger.info("Open http://127.0.0.1:8765 in your browser to watch")

        asyncio.run(vm_stream_main(f"jarvis_{name}"))
    except ImportError:
        logger.error("vm_stream.py not found")
    except KeyboardInterrupt:
        logger.info("Stream stopped")


def show_status():
    """Show full VM status."""
    vbox = check_virtualbox()
    vm = check_vm_exists()

    print("=" * 60)
    print("  JARVIS VM STATUS")
    print("=" * 60)

    if vbox["installed"]:
        print(f"\n  VirtualBox:  INSTALLED ({vbox['version']})")
        print(f"  Path:        {vbox['path']}")
    else:
        print("\n  VirtualBox:  NOT INSTALLED")
        print("  Install:     python vm_setup.py --install")
        print("  Or download: https://www.virtualbox.org/wiki/Downloads")

    if vm["exists"]:
        print(f"\n  VM:          EXISTS ({vm['name']})")
        print("  Start:       python vm_setup.py --start")
        print("  Stream:      python vm_setup.py --stream")
    else:
        print(f"\n  VM:          NOT CREATED")
        print("  Create:      python vm_setup.py --create")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="JARVIS VM Setup Helper")
    parser.add_argument("--install", action="store_true", help="Install VirtualBox")
    parser.add_argument("--create", action="store_true", help="Create a new VM")
    parser.add_argument("--start", action="store_true", help="Start the VM")
    parser.add_argument("--stream", action="store_true", help="Stream VM display")
    parser.add_argument("--name", default="desktop", help="VM name (default: desktop)")
    parser.add_argument("--download-iso", action="store_true", help="Download Ubuntu ISO")
    args = parser.parse_args()

    if args.install:
        install_virtualbox()
    elif args.create:
        create_vm(args.name)
    elif args.start:
        start_vm(args.name)
    elif args.stream:
        stream_vm(args.name)
    elif args.download_iso:
        try:
            from vm_manager import download_ubuntu_iso
            iso = download_ubuntu_iso()
            if iso:
                print(f"ISO downloaded: {iso}")
        except ImportError:
            print("vm_manager.py not found")
    else:
        show_status()


if __name__ == "__main__":
    main()
