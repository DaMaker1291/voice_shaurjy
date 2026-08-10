#!/bin/bash
cd /mnt/c/Users/supro/Downloads/CODE/voice_shaurjy/backend
python3 << 'PYEOF'
from entity_engine import Entity
e = Entity("local")
tests = [
    ("close all apps in the vdi and open chrome", True),
    ("search for cute cats in edge", True),
    ("press ctrl+l", True),
    ("type hello world", True),
    ("open terminal", True),
    ("close chrome", True),
    ("screenshot", True),
    ("click at 500 300", True),
    ("hi could you close all apps and only open chrome", True),
    ("hey jarvis can you open up the web browser for me", True),
    ("would you mind searching for dogs on edge please", True),
    ("could you fire up the terminal", True),
    ("shut down everything and open firefox", True),
    ("i want to find python tutorials on google", True),
    ("hit ctrl c", True),
    ("type the word hello", True),
    ("tap on 100 200", True),
    ("go ahead and open chrome", True),
    ("can we close edge and also open the browser", True),
    ("i need you to look up recipes on edge", True),
    ("hey jarvis, could you please open up edge and search for weather", True),
    ("screen shot", True),
    ("close down the browser", True),
    ("start firefox", True),
    ("boot up microsoft edge", True),
    ("mind searching for dogs on edge", True),
    ("only open chrome", True),
    ("just close everything", True),
    ("can you type hello", True),
    ("please press enter", True),
]
passed = 0
failed = 0
for text, should_pass in tests:
    result = e._parse_vdi_intent(text)
    ok = len(result) > 0
    status = "OK" if ok == should_pass else "FAIL"
    if ok == should_pass:
        passed += 1
    else:
        failed += 1
    print(f"  [{status}] {text} => {result}")

print(f"\nResults: {passed}/{passed+failed} passed, {failed} failed")
PYEOF
