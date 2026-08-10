"""JARVIS device discovery + control integration test (run on local machine).
Each section runs in its own worker thread with a hard watchdog timeout."""
import sys, os, json, time, traceback, threading
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS, FAIL, TIMEOUTS = 0, 0, 0

def log(msg=""):
    print(msg, flush=True)

def report(name, ok, detail=""):
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok: PASS += 1
    else: FAIL += 1
    log(f"  [{status}] {name}" + (f"  | {detail}" if detail else ""))

def run_with_timeout(fn, timeout_s, label):
    """Run fn in a thread; return (ok, result) with hard timeout."""
    result_box = {}
    def runner():
        try:
            result_box["value"] = fn()
            result_box["ok"] = True
        except Exception as e:
            result_box["ok"] = False
            result_box["err"] = f"{type(e).__name__}: {e}"
    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        global TIMEOUTS
        TIMEOUTS += 1
        log(f"  [TIMEOUT] {label} exceeded {timeout_s}s watchdog")
        return False, "timeout"
    if not result_box.get("ok"):
        return False, result_box.get("err", "unknown")
    return True, result_box.get("value")

results = []

# ── 1. NetworkScanner ARP scan only (fast) ──────────────────────────────
log("\n=== 1. NetworkScanner.scan_arp() ===")
try:
    from network_scanner import NetworkScanner
    ns = NetworkScanner(scan_interval=99999, db_path=os.path.join(os.environ.get("TEMP", "."), "jarvis_test_net.db"))
    ok, value = run_with_timeout(lambda: ns.scan_arp(), 30, "scan_arp")
    report("ARP scan completed", ok, str(value) if not ok else f"{len(value)} devices")
    if ok:
        for nd in value[:10]:
            log(f"       {nd.ip:18} {nd.hostname or '?':24} {nd.manufacturer or '?':16} mac={nd.mac or '?'}")
except Exception as e:
    traceback.print_exc()
    report("ARP scan completed", False, str(e))

# ── 2. NetworkScanner full scan (bounded) ───────────────────────────────
log("\n=== 2. NetworkScanner.full_scan() ===")
try:
    t0 = time.time()
    ok, value = run_with_timeout(lambda: ns.full_scan(), 60, "full_scan")
    dt = round(time.time() - t0, 1)
    report("full scan completed", ok, str(value) if not ok else f"{dt}s, {len(value)} devices")
    if ok:
        for dev_id, nd in list(value.items())[:15]:
            log(f"       {nd.ip:18} {nd.hostname or '?':24} {nd.manufacturer or '?':16} {nd.discovery_method}  mac={nd.mac or '?'}")
        for dev_id, nd in value.items():
            results.append({"ip": nd.ip, "hostname": nd.hostname, "manufacturer": nd.manufacturer, "mac": nd.mac, "method": nd.discovery_method})
except Exception as e:
    traceback.print_exc()
    report("full scan completed", False, str(e))

# ── 3. Tapo discovery ───────────────────────────────────────────────────
log("\n=== 3. Tapo discovery ===")
try:
    from tapo_client import TapoClient, _detect_subnet
    sub = _detect_subnet()
    report("subnet detected dynamically", bool(sub), f"subnet={sub or 'none'}")
    tc = TapoClient()
    ok, value = run_with_timeout(lambda: tc.discover_on_network(), 30, "tapo discover")
    report("tapo discover completed", ok, str(value) if not ok else f"{len(value)} devices")
    if ok:
        for d in value:
            log(f"       {d['ip']:18} {d.get('name','?'):24} {d.get('manufacturer','?')}")
except Exception as e:
    traceback.print_exc()
    report("tapo discover completed", False, str(e))

# ── 4. Phone discovery ──────────────────────────────────────────────────
log("\n=== 4. Phone discovery ===")
try:
    from phone_client import PhoneClient
    pc = PhoneClient()
    ok, value = run_with_timeout(lambda: pc.discover_phones(), 30, "phone discover")
    report("phone discover completed", ok, str(value) if not ok else f"{len(value)} phones")
    if ok:
        for d in value:
            log(f"       {d['ip']:18} {d.get('name','?'):24} {d.get('manufacturer','?')} {d.get('model','')}")
except Exception as e:
    traceback.print_exc()
    report("phone discover completed", False, str(e))

# ── 5. Control: DeviceBridge.execute() ──────────────────────────────────
log("\n=== 5. DeviceBridge control ===")
try:
    from device_bridge import DeviceBridge
    bridge = DeviceBridge()
    report("bridge instantiated", True)
    ok, value = run_with_timeout(
        lambda: bridge.execute({"id": "test_offline", "ip": "127.0.0.1", "protocol": "http"}, {"action": "ping", "params": {}}),
        15, "control offline device")
    if ok:
        report("control returns structured result", True, f"status={value.status} error={value.error}")
    else:
        report("control returns structured result", False, str(value))
except Exception as e:
    traceback.print_exc()
    report("control returns structured result", False, str(e))

log(f"\n===== SUMMARY: {PASS} passed, {FAIL} failed, {TIMEOUTS} timed out =====")
with open(os.path.join(os.environ.get("TEMP", "."), "jarvis_discovery_test.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
sys.exit(1 if (FAIL or TIMEOUTS) else 0)
