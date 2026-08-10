#!/bin/bash
cd /mnt/c/Users/supro/Downloads/CODE/voice_shaurjy/backend
python3 << 'PYEOF'
from entity_engine import Entity
e = Entity("local")

print("=== First call ===")
r1 = e.process("find the best holiday to vietnam")
print(f"  action: {r1.get('action')}")
print(f"  text: {r1.get('text', '')[:200]}")
print(f"  questions: {r1.get('questions')}")
print(f"  pending: {e._pending_clarify is not None}")
if e._pending_clarify:
    print(f"  pending_questions: {e._pending_clarify.get('questions')}")

print("\n=== Second call with answers ===")
r2 = e.process("find the best holiday to vietnam", answers={"answer_0": "december", "answer_1": "hanoi and phu quoc"})
print(f"  action: {r2.get('action')}")
print(f"  text: {r2.get('text', '')[:300]}")
print(f"  questions: {r2.get('questions')}")
PYEOF
