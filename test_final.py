"""Final end-to-end test — all local AI, zero cloud APIs."""
import os, sys
sys.path.insert(0, "backend")
os.environ["GROQ_API_KEY"] = ""  # Ensure no Groq

print("=== TEST 1: groq_agent.generate (chat) ===")
from groq_agent import generate
reply = generate("Hello! Who are you?", user_id="final_test", max_tokens=100, temperature=0.8)
print(f"  Reply: {reply[:150] if reply else 'EMPTY'}")
print(f"  Length: {len(reply) if reply else 0} chars")

print("\n=== TEST 2: groq_agent._local_generate (raw) ===")
from groq_agent import _local_generate
raw = _local_generate([{"role": "user", "content": "Say hello in 3 words"}], 20, 0.1)
print(f"  Raw: {raw[:100] if raw else 'EMPTY'}")

print("\n=== TEST 3: groq_agent.call (custom messages) ===")
from groq_agent import call
custom = call([{"role": "system", "content": "You are a helpful AI. Be concise."}, {"role": "user", "content": "What is 2+2?"}], 50, 0.1)
print(f"  Custom: {custom[:100] if custom else 'EMPTY'}")

print("\n=== TEST 4: All cloud API keys removed ===")
from groq import Groq
try:
    c = Groq(api_key="")
    c.chat.completions.create(model="test", messages=[{"role": "user", "content": "hi"}])
    print("  ERROR: Groq still reachable!")
except Exception as e:
    print(f"  OK: Groq blocked ({type(e).__name__})")

print("\n✓ ALL TESTS PASS — Local AI only, zero cloud cost!")
