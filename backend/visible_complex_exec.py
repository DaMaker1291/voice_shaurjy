"""
Visible Desktop EXECUTION Runner — runs the MOST COMPLEX prompts through the
REAL execute_goal pipeline (LLM plan -> execute). Launched by
launch_visible_complex.py AFTER switching to visible Virtual Desktop #2, so
every app that opens and every keystroke happens on a REAL, VISIBLE desktop
(seen in Task View) — never on your primary desktop.
"""
import os
import sys
import json
import time
import asyncio
import traceback

# Force UTF-8 on redirected stdout/stderr so Chinese/emoji in step results
# never crash the runner with UnicodeEncodeError (cp1252 locale).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "visible_complex_results.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "visible_complex_results.log")

# Redirect ALL agent file output away from the real Desktop into a dedicated
# test folder. The user's actual Desktop is never touched.
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.environ["JARVIS_OUTPUT_DIR"] = OUTPUT_DIR

# ── The most complex, multi-step prompts ──────────────────────────────────
PROMPTS = [
    {"name": "open_notepad_and_type", "prompt": "open notepad, wait a moment, and type 'hello from the visible desktop' into it"},
    {"name": "chrome_example_screenshot", "prompt": "open chrome, navigate to example.com, wait for it to load, then take a screenshot"},
    {"name": "create_word_doc", "prompt": "create a word document called visible_report.docx on my desktop with a heading and two paragraphs about artificial intelligence"},
    {"name": "create_excel_budget", "prompt": "create an excel spreadsheet called visible_budget.xlsx on my desktop with headers for item, cost and notes and three rows of sample data"},
    {"name": "create_powerpoint", "prompt": "create a powerpoint presentation called visible_deck.pptx on my desktop with a title slide and two content slides"},
    {"name": "web_search_france", "prompt": "search the web for the capital city of france and report what you find"},
    {"name": "scrape_example", "prompt": "scrape the content from example.com and save it to a file called scraped.txt on my desktop"},
    {"name": "run_fibonacci", "prompt": "run python: compute and print the first 10 fibonacci numbers"},
    {"name": "http_get", "prompt": "fetch the content from https://httpbin.org/get"},
    {"name": "esolang_compute", "prompt": "compute hex 48656c6c6f using esolang"},
    {"name": "open_calculator", "prompt": "open calculator"},
    {"name": "list_windows", "prompt": "show me all the open windows on this computer"},
    {"name": "create_folder_and_file", "prompt": "create a folder called visible_test_folder on my desktop and write a file called visible_test.txt inside it with the text hello world"},
    {"name": "system_info", "prompt": "what are my system specs"},
    {"name": "cpu_memory", "prompt": "what are my cpu and memory usage right now"},
    {"name": "disk_usage", "prompt": "how much disk space do i have left on my c drive"},
]

# Prompts we auto-answer if the agent asks a clarification question.
GENERIC_ANSWER = "please use a reasonable default value and proceed"


async def run_one(entry, index, total):
    """Run one complex prompt through the real execution pipeline."""
    from computer_use import execute_goal

    # CRITICAL: re-assert we're on Desktop #2 BEFORE each prompt. If the user
    # switched to Desktop #1 mid-run, this pulls the execution context back to
    # #2 so apps launched below land on #2 — never on the user's desktop.
    try:
        from visible_desktop import switch_to, current_number
        if current_number() != 2:
            switch_to(2)
    except Exception:
        pass

    name = entry["name"]
    prompt = entry["prompt"]
    start = time.time()
    log_line = f"\n[{index}/{total}] {name}: {prompt}"
    print(log_line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

    try:
        result = await asyncio.wait_for(
            execute_goal(prompt, safety="full_auto", target_desktop=2),
            timeout=180,
        )

        # If the agent needs clarification, answer generically once and retry
        if isinstance(result, dict) and result.get("action") == "clarify":
            questions = result.get("questions", [])
            print(f"  -> clarify asked ({len(questions)} questions), auto-answering...", flush=True)
            answers = {f"answer_{i}": GENERIC_ANSWER for i in range(len(questions))}
            result = await asyncio.wait_for(
                execute_goal(prompt, safety="full_auto", followup_answers=answers, target_desktop=2),
                timeout=180,
            )

        duration = round(time.time() - start, 2)
        if isinstance(result, dict):
            steps = result.get("steps", [])
            record = {
                "name": name,
                "prompt": prompt,
                "success": result.get("success", False),
                "action": result.get("action"),
                "duration_s": duration,
                "steps_total": result.get("steps_total", len(steps)),
                "steps_done": result.get("steps_done", 0),
                "steps_failed": result.get("steps_failed", 0),
                "steps": [
                    {
                        "action": s.get("action"),
                        "status": s.get("status"),
                        "result": str(s.get("result", ""))[:200],
                    }
                    for s in steps
                ],
                "error": result.get("error"),
            }
            status = "PASS" if record["success"] else "FAIL"
            print(f"  -> {status} ({duration}s) done={record['steps_done']} failed={record['steps_failed']}", flush=True)
            for s in steps:
                print(f"     - {s.get('action','?'):20} {s.get('status','?')}: {str(s.get('result',''))[:90]}", flush=True)
        else:
            record = {
                "name": name, "prompt": prompt, "success": False,
                "action": None, "duration_s": duration,
                "steps_total": 0, "steps_done": 0, "steps_failed": 0,
                "steps": [], "error": f"Unexpected result type: {type(result).__name__}",
            }
            print(f"  -> FAIL unexpected result type {type(result).__name__}", flush=True)

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({k: record[k] for k in record if k != "steps"}, ensure_ascii=False) + "\n")
        return record

    except asyncio.TimeoutError:
        record = {
            "name": name, "prompt": prompt, "success": False, "action": None,
            "duration_s": round(time.time() - start, 2),
            "steps_total": 0, "steps_done": 0, "steps_failed": 0,
            "steps": [], "error": "TIMEOUT after 180s",
        }
        print("  -> FAIL TIMEOUT", flush=True)
        return record
    except Exception as e:
        record = {
            "name": name, "prompt": prompt, "success": False, "action": None,
            "duration_s": round(time.time() - start, 2),
            "steps_total": 0, "steps_done": 0, "steps_failed": 0,
            "steps": [], "error": f"{type(e).__name__}: {str(e)[:300]}",
        }
        print(f"  -> FAIL {type(e).__name__}: {str(e)[:200]}", flush=True)
        traceback.print_exc()
        return record


async def main():
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(f"=== Visible Desktop Complex Execution Run — {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    print(f"Output redirect: JARVIS_OUTPUT_DIR={OUTPUT_DIR}", flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"JARVIS_OUTPUT_DIR={OUTPUT_DIR}\n")

    results = []
    for i, entry in enumerate(PROMPTS):
        r = await run_one(entry, i + 1, len(PROMPTS))
        results.append(r)
        # Small delay between LLM calls to avoid rate limits
        await asyncio.sleep(1.5)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total = len(results)
    passed = sum(1 for r in results if r["success"])
    print(f"\n{'='*60}", flush=True)
    print(f"TOTAL: {total} | PASSED: {passed} | FAILED: {total - passed}", flush=True)
    print(f"{'='*60}", flush=True)
    for r in results:
        s = "PASS" if r["success"] else "FAIL"
        err = f"  [{r.get('error','')[:80]}]" if not r["success"] else ""
        print(f"  {s:4s} {r['name']:28s} {r['duration_s']:7.1f}s  done={r['steps_done']}/{r['steps_total']}{err}", flush=True)

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n=== DONE: {passed}/{total} passed ===\n")


if __name__ == "__main__":
    asyncio.run(main())
