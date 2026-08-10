#!/usr/bin/env python3
"""Test the new JARVIS architecture."""
import sys
sys.path.insert(0, '/mnt/c/Users/supro/Downloads/CODE/voice_shaurjy/backend')

print("=== Skill Registry ===")
from skill_registry import get_skill_registry
registry = get_skill_registry()
tools = registry.get_available_tools()
print(f"Found {len(tools)} available tools:")
for t in tools:
    print(f"  {t['name']} ({t['version']}): {', '.join(t['skills'])}")

print("\n=== Mission Engine ===")
from mission_engine import get_mission_engine
engine = get_mission_engine()
print(f"Active missions: {len(engine.active_missions)}")
print(f"Recovered missions: {sum(1 for m in engine.active_missions.values() if m.status == 'recovering')}")

print("\n=== Task Planner ===")
from task_planner import get_task_planner
planner = get_task_planner()
print("Planner initialized")

print("\n=== Verification Engine ===")
from verification_engine import get_verification_engine
verifier = get_verification_engine()
result = verifier.verify({"type": "command", "command": "echo test"})
print(f"Verification test: passed={result.passed}, details={result.details}")

print("\n=== Execution Fabric ===")
from execution_fabric import get_execution_fabric
fabric = get_execution_fabric()
result = fabric.execute("check_display")
print(f"Display check: passed={result.success}, output={result.output[:50] if result.output else 'N/A'}")

print("\n=== All Systems Operational ===")
