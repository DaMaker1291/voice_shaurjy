"""
JARVIS Launcher — Start the full system daemon with streaming.

Usage:
  python jarvis_launch.py                    # Full daemon + stream viewer
  python jarvis_launch.py --goal "..."       # Execute a goal and exit
  python jarvis_launch.py --visible          # Run on visible desktop (no hidden)
  python jarvis_launch.py --chat             # Interactive chat mode
  python jarvis_launch.py --vm               # Run agent inside VirtualBox VM (2nd computer)
  python jarvis_launch.py --vm --vm-provision # Create and provision a new VM first
"""
import asyncio
import argparse
import json
import os
import sys
import logging
import threading
import time

sys.path.insert(0, os.path.dirname(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ["JARVIS_OUTPUT_DIR"] = os.path.join(os.path.dirname(__file__), "test_output")
os.makedirs(os.environ["JARVIS_OUTPUT_DIR"], exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
logger = logging.getLogger("jarvis")


def start_stream_server(port=8765, vm_name=None):
    """Start the screen stream server in a background thread."""
    try:
        if vm_name:
            # Stream from VM
            from vm_stream import VMFrameCapturer
            import stream_server
            capturer = VMFrameCapturer(vm_name)
            capturer.start()
            stream_server.set_vdi_source(capturer)
            logger.info(f"Streaming from VM: {vm_name}")
        from stream_server import main as stream_main
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(stream_main("127.0.0.1", port))
    except Exception as e:
        logger.error(f"Stream server failed: {e}")


def start_daemon(port=8766):
    """Start the WebSocket daemon in a background thread."""
    try:
        from system_daemon import run_daemon
        run_daemon("127.0.0.1", port)
    except Exception as e:
        logger.error(f"Daemon failed: {e}")


async def execute_goal_direct(goal: str):
    """Execute a goal directly (without daemon)."""
    from computer_use import ComputerUseAgent
    agent = ComputerUseAgent()
    result = await agent.execute(goal)
    return result


async def chat_mode():
    """Interactive chat mode."""
    from computer_use import ComputerUseAgent
    from groq_agent import call as groq_call
    agent = ComputerUseAgent()
    print("JARVIS Chat Mode (type 'quit' to exit)")
    print("=" * 50)
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if not user_input:
                continue
            action_words = ["search", "open", "create", "run", "send", "take",
                           "navigate", "scrape", "download", "install", "delete",
                           "move", "copy", "write", "read", "find", "show"]
            is_goal = any(w in user_input.lower() for w in action_words)
            if is_goal:
                print(f"\nJARVIS: Executing goal...")
                result = await agent.execute(user_input)
                if isinstance(result, dict):
                    done = result.get("steps_done", 0)
                    total = result.get("steps_total", 0)
                    success = result.get("success", False)
                    print(f"\nJARVIS: {'Done' if success else 'Failed'} ({done}/{total} steps)")
                    for s in result.get("steps", []):
                        icon = "+" if s.get("status") == "done" else "X"
                        print(f"  [{icon}] {s.get('action')}: {str(s.get('result', ''))[:150]}")
            else:
                response = groq_call(
                    [{"role": "system", "content": "You are JARVIS, a helpful AI assistant."},
                     {"role": "user", "content": user_input}],
                    max_tokens=500, temperature=0.7
                )
                print(f"\nJARVIS: {response}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")


def check_virtualbox() -> bool:
    """Check if VirtualBox is installed."""
    paths = [
        r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe",
        r"C:\Program Files (x86)\Oracle\VirtualBox\VBoxManage.exe",
        "/usr/bin/VBoxManage",
    ]
    for p in paths:
        if os.path.exists(p):
            return True
    try:
        import subprocess
        result = subprocess.run(["where", "VBoxManage"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def provision_vm(vm_name: str = "desktop"):
    """Provision a new VM."""
    try:
        from vm_stream import VMProvisioner
        provisioner = VMProvisioner()
        if not provisioner.is_ready():
            print("VirtualBox not installed!")
            print("Download from: https://www.virtualbox.org/wiki/Downloads")
            print("Then run: python jarvis_launch.py --vm --vm-provision")
            return False

        print(f"Provisioning VM: jarvis_{vm_name}")
        print("This may take a few minutes...")
        result = provisioner.provision_full(vm_name)
        print(f"Result: {json.dumps(result, indent=2)}")
        return "error" not in result
    except ImportError:
        print("vm_stream.py not found")
        return False


def run_in_vm(goal: str = None, vm_name: str = "desktop"):
    """Run the agent inside a VM."""
    try:
        from vm_stream import VMProvisioner, VMFrameCapturer
        from vm_manager import JarvisVM

        provisioner = VMProvisioner()
        if not provisioner.is_ready():
            print("VirtualBox not installed!")
            print("Download from: https://www.virtualbox.org/wiki/Downloads")
            return

        vm_manager = JarvisVM()
        vm_full_name = f"jarvis_{vm_name}"

        # Check if VM exists
        running = vm_manager.get_running_vm()
        if running != vm_full_name:
            print(f"Starting VM: {vm_full_name}")
            vm_manager.start(vm_name, headless=True)
            print("Waiting for VM to boot...")
            time.sleep(10)

        # Stream VM display
        print(f"Streaming VM display to viewer...")
        capturer = VMFrameCapturer(vm_full_name)
        capturer.start()

        # Set VM as stream source
        import stream_server
        stream_server.set_vdi_source(capturer)

        if goal:
            print(f"Executing goal in VM: {goal}")
            # TODO: Send goal to agent running inside VM
            # For now, run locally but stream from VM
            result = asyncio.run(execute_goal_direct(goal))
            print(json.dumps(result, indent=2, default=str))
        else:
            print("VM is running. Open viewer to watch.")
            print("Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    except ImportError as e:
        print(f"VM modules not found: {e}")
        print("Make sure vm_manager.py and vm_stream.py are in the backend directory")


def main():
    parser = argparse.ArgumentParser(description="JARVIS System Daemon")
    parser.add_argument("--goal", type=str, help="Execute a goal and exit")
    parser.add_argument("--visible", action="store_true", help="Run on visible desktop")
    parser.add_argument("--chat", action="store_true", help="Interactive chat mode")
    parser.add_argument("--port", type=int, default=8765, help="Stream server port")
    parser.add_argument("--daemon-port", type=int, default=8766, help="Daemon WebSocket port")
    parser.add_argument("--no-stream", action="store_true", help="Disable screen streaming")
    parser.add_argument("--vm", action="store_true", help="Run agent inside VirtualBox VM")
    parser.add_argument("--vm-name", default="desktop", help="VM name (default: desktop)")
    parser.add_argument("--vm-provision", action="store_true", help="Provision a new VM first")
    args = parser.parse_args()

    # VM provisioning
    if args.vm_provision:
        provision_vm(args.vm_name)
        return

    # VM mode
    if args.vm:
        run_in_vm(args.goal, args.vm_name)
        return

    # Direct goal execution
    if args.goal:
        result = asyncio.run(execute_goal_direct(args.goal))
        print(json.dumps(result, indent=2, default=str))
        return

    # Chat mode
    if args.chat:
        asyncio.run(chat_mode())
        return

    # Full daemon mode
    print("=" * 60)
    print("  JARVIS HOME & OS SYSTEM DAEMON")
    print("=" * 60)

    if not args.no_stream:
        print(f"\n  Stream Viewer: http://127.0.0.1:{args.port}")
        stream_thread = threading.Thread(target=start_stream_server, args=(args.port,), daemon=True)
        stream_thread.start()
        time.sleep(1)

    print(f"  Daemon WebSocket: ws://127.0.0.1:{args.daemon_port}")
    daemon_thread = threading.Thread(target=start_daemon, args=(args.daemon_port,), daemon=True)
    daemon_thread.start()

    # Start mesh discovery
    try:
        from mesh_discovery import MeshController
        from system_daemon import JarvisDB
        db = JarvisDB()
        mesh = MeshController(db)
        asyncio.get_event_loop().run_until_complete(mesh.start())
        print(f"  Devices found: {len(mesh.get_devices())}")
    except Exception as e:
        print(f"  Mesh discovery: {e}")

    print("\n  Daemon running. Ctrl+C to stop.")
    print("=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
