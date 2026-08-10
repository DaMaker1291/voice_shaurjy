import socket, json, subprocess, os

os.environ['DISPLAY'] = ':99'

# Test port 8766
print("=== Port 8766 ===")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
try:
    s.connect(('127.0.0.1', 8766))
    s.send(json.dumps({"type":"ping"}).encode() + b'\n')
    data = s.recv(4096)
    print(f"Response: {data[:500]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    s.close()

# Test port 8765
print("\n=== Port 8765 ===")
s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s2.settimeout(3)
try:
    s2.connect(('127.0.0.1', 8765))
    s2.send(json.dumps({"type":"ping"}).encode() + b'\n')
    data = s2.recv(4096)
    print(f"Response: {data[:500]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    s2.close()

# Test screenshot
print("\n=== Screenshot test ===")
os.system("DISPLAY=:99 scrot /tmp/test_vdi.png && echo 'OK' || echo 'FAILED'")

# Test Edge
print("\n=== Edge processes ===")
os.system("ps aux | grep -i edge | grep -v grep | head -5")

# Check active window
print("\n=== Active window ===")
os.system("DISPLAY=:99 xdotool getactivewindow getwindowname 2>/dev/null || echo 'No active window'")

# List running apps
print("\n=== XFCE apps ===")
os.system("DISPLAY=:99 wmctrl -l 2>/dev/null || echo 'wmctrl not available'")
