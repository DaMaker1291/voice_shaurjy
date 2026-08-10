"""
Cloudflare Workers AI Analyzer
Runs the 16-prompt test suite, captures all outputs, and sends them to
Cloudflare Workers AI for a comprehensive design/execution/workflow analysis.

Credentials must be set as environment variables:
  CLOUDFLARE_API_TOKEN  - your Cloudflare API token
  CLOUDFLARE_ACCOUNT_ID - your Cloudflare account ID
  CLOUDFLARE_R2_ENDPOINT - your R2 S3 endpoint (optional, for storing outputs)
  CLOUDFLARE_R2_ACCESS_KEY_ID - R2 access key (optional)
  CLOUDFLARE_R2_SECRET_ACCESS_KEY - R2 secret key (optional)
"""
import os
import sys
import json
import time
import asyncio
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "ai_analyzer.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ai_analyzer")

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_JSON = os.path.join(BACKEND_DIR, "hidden_complex_results.json")
RESULTS_LOG = os.path.join(BACKEND_DIR, "hidden_complex_results.log")
TEST_OUTPUT_DIR = os.path.join(BACKEND_DIR, "test_output")

CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_R2_ENDPOINT = os.environ.get("CLOUDFLARE_R2_ENDPOINT", "")
CLOUDFLARE_R2_ACCESS_KEY_ID = os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID", "")
CLOUDFLARE_R2_SECRET_ACCESS_KEY = os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "")

WORKERS_AI_MODEL = "@cf/meta/llama-3.1-70b-instruct"
WORKERS_AI_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{WORKERS_AI_MODEL}"

MAX_ANALYSIS_TOKENS = 4096
MAX_FILE_CONTENT_CHARS = 2000


def load_test_results():
    if not os.path.exists(RESULTS_JSON):
        return None, "Results file not found. Run the test suite first."
    with open(RESULTS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data, None


def load_test_log():
    if not os.path.exists(RESULTS_LOG):
        return "Test log not found."
    with open(RESULTS_LOG, encoding="utf-8") as f:
        return f.read()


def load_file_contents():
    files = {}
    if not os.path.isdir(TEST_OUTPUT_DIR):
        return files
    for fname in os.listdir(TEST_OUTPUT_DIR):
        fpath = os.path.join(TEST_OUTPUT_DIR, fname)
        if os.path.isfile(fpath):
            try:
                size = os.path.getsize(fpath)
                if size > 10 * 1024 * 1024:
                    files[fname] = f"[file too large: {size} bytes]"
                    continue
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    content = f.read()[:MAX_FILE_CONTENT_CHARS]
                files[fname] = content
            except Exception as e:
                files[fname] = f"[error reading file: {e}]"
    return files


def build_analysis_prompt(results_data, test_log, file_contents):
    pass_count = sum(1 for r in results_data if r.get("success")) if results_data else 0
    total_count = len(results_data) if results_data else 0
    pass_rate = (pass_count / total_count * 100) if total_count > 0 else 0

    results_summary = json.dumps(results_data, indent=2, default=str)
    if len(results_summary) > 8000:
        results_summary = results_summary[:8000] + "\n... [truncated]"

    prompt = f"""You are an expert AI agent pipeline analyst. Analyze the following test suite results from a hidden-desktop execution of 16 complex prompts through an OpenCode AI agent.

## TEST SUITE RESULTS SUMMARY
Total prompts: {total_count}
Passed: {pass_count}
Failed: {total_count - pass_count}
Pass rate: {pass_rate:.1f}%

## DETAILED RESULTS (JSON)
{results_summary}

## TEST LOG (last 50 lines)
{test_log[-3000:] if len(test_log) > 3000 else test_log}

## GENERATED FILE CONTENTS
"""
    for fname, content in file_contents.items():
        prompt += f"\n--- {fname} ---\n{content}\n"

    prompt += """
## YOUR ANALYSIS

Analyze what is wrong with this AI agent pipeline. Be specific about:

1. DESIGN ISSUES: What's wrong with the generated file designs? (PPTX slides empty/bad, DOCX content missing, XLSX placeholder data, scraped.txt raw CSS)
2. EXECUTION ISSUES: Which prompts failed and why? What patterns do you see in the failures?
3. WORKFLOW ISSUES: What's wrong with the overall pipeline design? (LLM plan inconsistency, missing deterministic fallbacks, content injection failures)
4. ARCHITECTURE FIXES: What specific code changes would fix each issue? Give concrete code examples.
5. RELIABILITY: What would make this pipeline 95%+ reliable?

Be brutally honest. Give actionable fixes, not vague suggestions.
"""
    return prompt


def call_cloudflare_workers_ai(prompt):
    if not CLOUDFLARE_API_TOKEN:
        return None, "CLOUDFLARE_API_TOKEN not set in environment variables"
    if not CLOUDFLARE_ACCOUNT_ID:
        return None, "CLOUDFLARE_ACCOUNT_ID not set in environment variables"

    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "max_tokens": MAX_ANALYSIS_TOKENS,
        "temperature": 0.3,
    }

    max_retries = 4
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                WORKERS_AI_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 0) or 0)
                delay = max(retry_after, 5 * (attempt + 1))
                logger.warning(f"Rate limited (429) on attempt {attempt + 1}. Waiting {delay:.0f}s...")
                time.sleep(delay)
                last_err = f"Rate limited (429) after attempt {attempt + 1}"
                continue
            resp.raise_for_status()
            data = resp.json()
            if data.get("success"):
                result = data.get("result", {}).get("response", "")
                return result, None
            else:
                return None, f"API error: {json.dumps(data)}"
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code == 429:
                delay = 5 * (attempt + 1)
                logger.warning(f"Rate limited on attempt {attempt + 1}. Waiting {delay}s...")
                time.sleep(delay)
                last_err = f"Rate limited (429) after attempt {attempt + 1}"
                continue
            return None, f"HTTP error: {e}"
        except requests.exceptions.Timeout:
            last_err = "Request timed out after 120s"
            logger.warning(f"Timeout on attempt {attempt + 1}")
            time.sleep(2)
            continue
        except requests.exceptions.ConnectionError as e:
            return None, f"Connection error: {e}"
        except Exception as e:
            return None, f"Error: {e}"

    return None, last_err or "Analysis failed after all retries"


def save_analysis(analysis_text):
    path = os.path.join(BACKEND_DIR, "ai_analysis.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(analysis_text)
    logger.info(f"Analysis saved to {path}")
    return path


def run_analysis():
    logger.info("Loading test results...")
    results_data, err = load_test_results()
    if err:
        logger.error(err)
        return None, err

    logger.info("Loading test log...")
    test_log = load_test_log()

    logger.info("Loading generated file contents...")
    file_contents = load_file_contents()
    logger.info(f"Loaded {len(file_contents)} files: {list(file_contents.keys())}")

    logger.info("Building analysis prompt...")
    prompt = build_analysis_prompt(results_data, test_log, file_contents)
    logger.info(f"Prompt length: {len(prompt)} chars")

    logger.info("Sending to Cloudflare Workers AI...")
    analysis, err = call_cloudflare_workers_ai(prompt)
    if err:
        logger.error(f"AI analysis failed: {err}")
        return None, err

    logger.info(f"Analysis received: {len(analysis)} chars")
    analysis_path = save_analysis(analysis)

    return analysis, None


if __name__ == "__main__":
    analysis, err = run_analysis()
    if err:
        logger.error(f"Analysis failed: {err}")
        sys.exit(1)
    print(analysis)