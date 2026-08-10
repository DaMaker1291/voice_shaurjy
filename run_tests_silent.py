"""
JARVIS Silent Test Runner
=========================
Tests the entire workspace + agent + verifier pipeline without opening
any visible terminal windows. All output is captured to log files.

Run: python run_tests_silent.py
"""

import os
import sys
import json
import time
import logging
import traceback
import unittest
import io
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

os.chdir(BACKEND_DIR)

LOG_DIR = Path(__file__).parent / ".test_logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "test_run.log", mode="w", encoding="utf-8"),
        logging.StreamHandler(io.StringIO()),
    ],
)
log = logging.getLogger("jarvis_test")


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.results = []

    def record(self, name: str, ok: bool, detail: str = ""):
        status = "PASS" if ok else "FAIL"
        self.results.append({"name": name, "ok": ok, "detail": detail})
        if ok:
            self.passed += 1
            log.info(f"  ✓ {name}")
        else:
            self.failed += 1
            log.error(f"  ✗ {name}: {detail}")

    def summary(self):
        total = self.passed + self.failed + self.errors
        return {
            "total": total,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "pass_rate": f"{self.passed / max(total, 1) * 100:.0f}%",
        }


result = TestResult()


_TEST_REGISTRY = []

def test(name):
    """Decorator to register a test function."""
    def decorator(func):
        def wrapper():
            try:
                func()
                result.record(name, True)
            except AssertionError as e:
                result.record(name, False, str(e))
            except Exception as e:
                result.record(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
        wrapper.test_name = name
        _TEST_REGISTRY.append(wrapper)
        return wrapper
    return decorator


# ── Mission State Tests ──

@test("MissionStateMachine: create mission")
def _():
    from mission_state import MissionStateMachine, get_mission_state
    sm = get_mission_state()
    m = sm.create("test-1", "Build a website", "ws-123")
    assert m.id == "test-1"
    assert m.objective == "Build a website"
    assert m.state == "queued"

@test("MissionStateMachine: state transitions")
def _():
    from mission_state import get_mission_state
    sm = get_mission_state()
    sm.transition("test-1", "planning")
    m = sm.get("test-1")
    assert m.state == "planning"
    sm.transition("test-1", "executing")
    m = sm.get("test-1")
    assert m.state == "executing"

@test("MissionStateMachine: action validation - valid action")
def _():
    from mission_state import validate_action
    ok, err, risk = validate_action("click", {"x": 100, "y": 200})
    assert ok is True, f"Expected ok, got: {err}"
    assert risk == "low"

@test("MissionStateMachine: action validation - missing required param")
def _():
    from mission_state import validate_action
    ok, err, risk = validate_action("click", {"x": 100})
    assert ok is False
    assert "Missing required param" in err

@test("MissionStateMachine: action validation - invalid action")
def _():
    from mission_state import validate_action
    ok, err, risk = validate_action("nonexistent_action", {})
    assert ok is False
    assert "Unknown action" in err

@test("MissionStateMachine: high risk action detection")
def _():
    from mission_state import validate_action
    ok, err, risk = validate_action("run_command", {"cmd": "echo test"})
    assert ok is True
    assert risk == "high"

@test("MissionStateMachine: coordinate validation")
def _():
    from mission_state import validate_action
    ok, err, risk = validate_action("click", {"x": -1, "y": 500})
    assert ok is False
    assert "Invalid value" in err

@test("MissionStateMachine: persistence")
def _():
    from mission_state import MissionStateMachine, MISSIONS_DIR, get_mission_state
    from pathlib import Path
    sm = get_mission_state()
    m = sm.get("test-1")
    assert m is not None
    mission_file = Path(MISSIONS_DIR) / "test-1.json"
    assert mission_file.exists(), "Mission should persist to disk"
    with open(mission_file) as f:
        data = json.load(f)
    assert data["id"] == "test-1"

@test("MissionStateMachine: recovery count")
def _():
    from mission_state import get_mission_state
    sm = get_mission_state()
    sm.create("test-recover", "Test recovery", "ws-999")
    sm.transition("test-recover", "executing")
    can_recover = sm.start_recovery("test-recover")
    assert can_recover is True
    m = sm.get("test-recover")
    assert m.recovery_count == 1
    assert m.state == "recovering"


# ── Workspace Manager Tests ──

@test("WorkspaceManager: create workspace")
def _():
    from workspace_manager import get_workspace_manager
    wm = get_workspace_manager()
    ws = wm.create_workspace(name="Test Workspace", resolution=(1920, 1080))
    assert ws.id is not None
    assert ws.name == "Test Workspace"
    assert ws.resolution == (1920, 1080)
    assert ws.status == "created"

@test("WorkspaceManager: workspace persistence")
def _():
    from workspace_manager import get_workspace_manager, WORKSPACE_DIR
    wm = get_workspace_manager()
    ws_list = wm.list_workspaces()
    assert len(ws_list) > 0
    last_ws = ws_list[-1]
    ws_dir = WORKSPACE_DIR / last_ws["id"]
    state_file = ws_dir / "state.json"
    assert state_file.exists()

@test("WorkspaceManager: list workspaces")
def _():
    from workspace_manager import get_workspace_manager
    wm = get_workspace_manager()
    ws_list = wm.list_workspaces()
    assert isinstance(ws_list, list)
    if len(ws_list) > 0:
        assert "id" in ws_list[0]
        assert "status" in ws_list[0]


# ── Workspace Agent Tests ──

@test("WorkspaceAgent: create mission")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    m = agent.create_mission("Test mission objective", "ws-test-1")
    assert m.id is not None
    assert m.objective == "Test mission objective"
    assert m.workspace_id == "ws-test-1"
    assert m.status == "planning"

@test("WorkspaceAgent: capability resolver - browser uses API")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    method, config = agent.resolve_capability("chrome")
    assert method == "api", f"Expected API method for Chrome, got {method}"
    assert config["method"] == "cdp"

@test("WorkspaceAgent: capability resolver - git uses CLI")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    method, config = agent.resolve_capability("git")
    assert method == "cli", f"Expected CLI method for Git, got {method}"

@test("WorkspaceAgent: capability resolver - unknown app falls back to GUI")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    method, config = agent.resolve_capability("some_random_app_xyz")
    assert method == "gui", f"Expected GUI fallback, got {method}"

@test("WorkspaceAgent: capability resolver - VSCode has API")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    method, config = agent.resolve_capability("vscode")
    assert method == "api", f"Expected API for VSCode, got {method}"

@test("WorkspaceAgent: get mission")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    m = agent.create_mission("Another test", "ws-test-2")
    retrieved = agent.get_mission(m.id)
    assert retrieved is not None
    assert retrieved["id"] == m.id

@test("WorkspaceAgent: list missions")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    missions = agent.list_missions()
    assert isinstance(missions, list)
    assert len(missions) >= 2

@test("WorkspaceAgent: pause/resume mission")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    m = agent.create_mission("Pause test mission", "ws-test-3")
    pause_result = agent.pause_mission(m.id)
    assert pause_result["ok"] is True
    resume_result = agent.resume_mission(m.id)
    assert resume_result["ok"] is True

@test("WorkspaceAgent: stop mission")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    m = agent.create_mission("Stop test mission", "ws-test-4")
    stop_result = agent.stop_mission(m.id)
    assert stop_result["ok"] is True


# ── Verifier Tests ──

@test("WorkspaceVerifier: verify screenshot with content")
def _():
    from workspace_verifier import get_workspace_verifier
    verifier = get_workspace_verifier()
    import io
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (800, 600), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.text((100, 100), "JARVIS Dashboard", fill=(0, 255, 100))
        draw.text((100, 200), "Mission: Build Website", fill=(200, 200, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        screenshot = buf.getvalue()
        v = verifier.verify_step(screenshot, "screenshot", {})
        assert v.verified is True
        assert v.confidence >= 0.5
    except ImportError:
        pass

@test("WorkspaceVerifier: verify_file_created - file exists")
def _():
    from workspace_verifier import get_workspace_verifier
    verifier = get_workspace_verifier()
    test_file = LOG_DIR / "verify_test.txt"
    test_file.write_text("test content")
    v = verifier.verify_file_created(b"", str(test_file))
    assert v.verified is True
    assert v.confidence == 1.0
    assert "exists" in v.evidence

@test("WorkspaceVerifier: verify_file_created - file missing")
def _():
    from workspace_verifier import get_workspace_verifier
    verifier = get_workspace_verifier()
    v = verifier.verify_file_created(b"", str(LOG_DIR / "nonexistent_file_xyz.txt"))
    assert v.verified is False

@test("WorkspaceVerifier: verify_process_running")
def _():
    from workspace_verifier import get_workspace_verifier
    verifier = get_workspace_verifier()
    if sys.platform == "win32":
        v = verifier.verify_process_running("python.exe")
    else:
        v = verifier.verify_process_running("python3")
    assert isinstance(v.verified, bool)


# ── Laser Gate Tests ──

@test("LaserGate: risk assessment - low risk")
def _():
    from laser_gate import LaserGate
    gate = LaserGate()
    risk = gate.assess_risk("create_file", {"path": "/tmp/test.txt"})
    assert risk.value == "low"

@test("LaserGate: risk assessment - medium risk")
def _():
    from laser_gate import LaserGate
    gate = LaserGate()
    risk = gate.assess_risk("send_email", {"to": "user@example.com"})
    assert risk.value in ("medium", "high")

@test("LaserGate: risk assessment - high risk")
def _():
    from laser_gate import LaserGate
    gate = LaserGate()
    risk = gate.assess_risk("send_email", {"action": "publish paper to arxiv"})
    assert risk.value in ("high", "critical")

@test("LaserGate: intercept low risk action")
def _():
    from laser_gate import LaserGate
    gate = LaserGate()
    result = gate.intercept("create_file", {"path": "/tmp/test.txt"})
    assert result["allowed"] is True

@test("LaserGate: intercept high risk action")
def _():
    from laser_gate import LaserGate
    gate = LaserGate()
    result = gate.intercept("send_email", {"body": "publish stock trade order arxiv"})
    assert result["allowed"] is False
    assert result["requires_confirmation"] is True

@test("LaserGate: approval workflow")
def _():
    from laser_gate import LaserGate
    gate = LaserGate()
    sub = gate.submit_action("test_action", {"key": "value"}, "Test high-risk action")
    assert "action_id" in sub
    pending = gate.get_pending_actions()
    assert len(pending) >= 1
    approve = gate.approve_action(sub["action_id"])
    assert approve["success"] is True
    pending_after = gate.get_pending_actions()
    assert len(pending_after) < len(pending)

@test("LaserGate: deny workflow")
def _():
    from laser_gate import LaserGate
    gate = LaserGate()
    sub = gate.submit_action("dangerous_action", {"key": "value"}, "sudo delete everything")
    deny = gate.deny_action(sub["action_id"])
    assert deny["success"] is True
    stats = gate.get_stats()
    assert stats["denied"] >= 1

@test("LaserGate: hold confirmation")
def _():
    from laser_gate import LaserGate
    import time
    gate = LaserGate()
    gate.start_hold()
    time.sleep(1.6)
    confirmed = gate.stop_hold()
    assert confirmed is True


# ── Self-Healing Tests ──

@test("SelfHealingEngine: register and list tools")
def _():
    from self_healing import SelfHealingEngine
    engine = SelfHealingEngine()
    tool_code = "def run():\n    return 'hello world'"
    engine.register_tool("test_tool_silent", tool_code)
    tools = engine.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "test_tool_silent" in tool_names

@test("SelfHealingEngine: generate repair for ModuleNotFoundError")
def _():
    from self_healing import SelfHealingEngine
    engine = SelfHealingEngine()
    original = "import nonexistent_module\nprint(nonexistent_module.data)"
    repaired = engine._generate_repair_regex(
        "ModuleNotFoundError: No module named 'nonexistent_module'",
        "Traceback...",
        original,
    )
    assert repaired is not None
    assert "nonexistent_module" in repaired

@test("SelfHealingEngine: execute with healing - success on first try")
def _():
    from self_healing import SelfHealingEngine
    engine = SelfHealingEngine()
    def my_fn():
        return 42
    res = engine.execute_with_healing("test_success", my_fn, max_retries=2)
    assert res["status"] == "SUCCESS"
    assert res["result"] == 42

@test("SelfHealingEngine: stats")
def _():
    from self_healing import SelfHealingEngine
    engine = SelfHealingEngine()
    stats = engine.get_stats()
    assert "total_tools" in stats
    assert "total_attempts" in stats


# ── Workspace Replicator Tests ──

@test("WorkspaceReplicator: profile retrieval")
def _():
    from workspace_replicator import get_workspace_replicator
    r = get_workspace_replicator()
    profile = r.get_profile_dict()
    assert isinstance(profile, dict)
    assert "installed_apps" in profile or "platform" in profile


# ── JSON Parser Tests (from agent) ──

@test("Agent: JSON parser - valid array")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    steps = agent._parse_json_robust('[{"action": "click", "params": {"x": 100}}]')
    assert steps is not None
    assert len(steps) == 1

@test("Agent: JSON parser - markdown wrapped")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    text = '```json\n[{"action": "screenshot", "params": {}}]\n```'
    steps = agent._parse_json_robust(text)
    assert steps is not None
    assert len(steps) == 1

@test("Agent: JSON parser - partial recovery")
def _():
    from workspace_agent import get_workspace_agent
    agent = get_workspace_agent()
    text = '[{"action": "screenshot", "params": {}}, {"action": "click", "params": {"x": 100'
    steps = agent._parse_json_robust(text)
    assert steps is not None
    assert len(steps) >= 1


# ── Config Tests ──

@test("Config: load configuration")
def _():
    from config import JARVISConfig
    cfg = JARVISConfig()
    assert cfg is not None
    assert hasattr(cfg, "is_cloud")


# ── Main Test Runner ──

def main():
    start = time.time()
    log.info("=" * 60)
    log.info("JARVIS Silent Test Suite")
    log.info("=" * 60)
    test_functions = list(_TEST_REGISTRY)
    log.info(f"Running {len(test_functions)} tests...\n")
    for fn in test_functions:
        fn()
    elapsed = time.time() - start
    summary = result.summary()
    log.info("\n" + "=" * 60)
    log.info(f"RESULTS: {summary['passed']}/{summary['total']} passed ({summary['pass_rate']})")
    log.info(f"Failed: {summary['failed']}, Errors: {summary['errors']}")
    log.info(f"Duration: {elapsed:.2f}s")
    log.info("=" * 60)
    report_path = LOG_DIR / "test_report.json"
    report = {
        "summary": summary,
        "duration_seconds": round(elapsed, 2),
        "tests": result.results,
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log.info(f"\nFull report: {report_path}")
    log.info(f"Log file: {LOG_DIR / 'test_run.log'}")
    if summary["failed"] > 0:
        log.info("\nFailed tests:")
        for t in result.results:
            if not t["ok"]:
                log.info(f"  ✗ {t['name']}: {t['detail'][:100]}")
    return 0 if summary["failed"] == 0 and summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
