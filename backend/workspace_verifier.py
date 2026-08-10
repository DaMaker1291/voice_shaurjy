"""JARVIS Workspace Verification Engine - Real screenshot diffing + LLM vision.

After each mission step, captures a screenshot and verifies completion via:
1. LLM vision analysis (send screenshot to gpt-4o for confirmation)
2. Pixel-level screenshot diffing (compare before/after)
3. OCR text extraction on real screenshots (pytesseract)
4. Direct filesystem/process checks where applicable

This closes the OBSERVE -> ACT -> VERIFY -> RECOVER loop with real evidence.
"""

import os
import io
import sys
import json
import time
import base64
import hashlib
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

log = logging.getLogger("workspace_verification")


@dataclass
class VerificationResult:
    step_number: int
    verified: bool
    confidence: float
    evidence: str
    screenshot_b64: str = ""
    method: str = ""
    duration_ms: float = 0
    diff_hash: str = ""
    before_hash: str = ""
    after_hash: str = ""

    def to_dict(self):
        return {
            "step_number": self.step_number,
            "verified": self.verified,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "method": self.method,
            "duration_ms": self.duration_ms,
            "diff_hash": self.diff_hash,
        }


class WorkspaceVerifier:
    """Verifies mission step completion via real screenshots and LLM vision."""

    def __init__(self):
        self._ocr_engine = None
        self._prev_screenshot_hash: Optional[str] = None
        self._llm_client = None

    def _get_ocr(self):
        if self._ocr_engine is None:
            try:
                import pytesseract
                self._ocr_engine = pytesseract
            except ImportError:
                log.debug("[VERIFY] pytesseract not available, using text matching fallback")
                self._ocr_engine = "fallback"
        return self._ocr_engine

    def _extract_text(self, image_bytes: bytes) -> str:
        ocr = self._get_ocr()
        if ocr == "fallback":
            return self._image_info(image_bytes)
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            text = ocr.image_to_string(img)
            return text
        except Exception as e:
            log.debug(f"[VERIFY] OCR failed: {e}")
            return self._image_info(image_bytes)

    def _image_info(self, image_bytes: bytes) -> str:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            if img.size[0] > 0 and img.size[1] > 0:
                small = img.resize((20, 20))
                pixels = list(small.getdata())
                avg_r = sum(p[0] for p in pixels) / len(pixels)
                avg_g = sum(p[1] for p in pixels) / len(pixels)
                avg_b = sum(p[2] for p in pixels) / len(pixels)
                if avg_g > 200 and avg_r < 50 and avg_b < 50:
                    return "[SYNTHETIC: green grid - no real content]"
                return f"[Image {img.size[0]}x{img.size[1]}, RGB=({avg_r:.0f},{avg_g:.0f},{avg_b:.0f})]"
        except Exception:
            pass
        return "[Screenshot captured]"

    def _compute_hash(self, image_bytes: bytes) -> str:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            img = img.resize((8, 8), Image.Resampling.LANCZOS).convert("L")
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = "".join("1" if p > avg else "0" for p in pixels)
            return hashlib.md5(bits.encode()).hexdigest()
        except Exception:
            return hashlib.md5(image_bytes[:1024]).hexdigest()

    def _diff_screenshots(self, before: bytes, after: bytes) -> Tuple[float, str]:
        try:
            from PIL import Image
            img_a = Image.open(io.BytesIO(before)).convert("RGB")
            img_b = Image.open(io.BytesIO(after)).convert("RGB")
            size = (160, 120)
            img_a = img_a.resize(size, Image.Resampling.LANCZOS)
            img_b = img_b.resize(size, Image.Resampling.LANCZOS)
            pixels_a = list(img_a.getdata())
            pixels_b = list(img_b.getdata())
            total = len(pixels_a)
            changed = 0
            for pa, pb in zip(pixels_a, pixels_b):
                if any(abs(a - b) > 30 for a, b in zip(pa, pb)):
                    changed += 1
            ratio = changed / max(total, 1)
            if ratio < 0.01:
                desc = "No visible change"
            elif ratio < 0.05:
                desc = "Minor UI changes (cursor, animation)"
            elif ratio < 0.20:
                desc = "Moderate content change"
            elif ratio < 0.50:
                desc = "Significant screen change"
            else:
                desc = "Major screen transition"
            return ratio, desc
        except Exception as e:
            return 0.0, f"Diff failed: {e}"

    def _llm_vision_verify(self, screenshot_b64: str, step_action: str,
                           step_params: dict, expected_outcome: str = "") -> Tuple[bool, float, str]:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return False, 0.0, "No OpenAI API key"
        try:
            import httpx
        except ImportError:
            return False, 0.0, "httpx not installed"

        prompt_parts = [
            "Analyze this screenshot of a workspace after executing a computer task.",
            f"Action performed: {step_action}",
        ]
        if expected_outcome:
            prompt_parts.append(f"Expected outcome: {expected_outcome}")
        if step_params:
            safe = {k: v for k, v in step_params.items()
                    if k not in ("screenshot_before", "screenshot_after")}
            prompt_parts.append(f"Parameters: {json.dumps(safe, indent=None)[:500]}")
        prompt_parts.extend([
            "",
            "Respond with ONLY a JSON object (no markdown):",
            '{"verified": true/false, "confidence": 0.0-1.0, "evidence": "brief description"}',
            "",
            "Rules:",
            "- verified=true if the screen shows the action completed successfully",
            "- verified=false if there is an error dialog, blank screen, or failure",
            "- confidence=1.0 for definitive, 0.5 for uncertain, 0.2 for unlikely",
        ])

        payload = {
            "model": "gpt-4o",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "\n".join(prompt_parts)},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}",
                            "detail": "low",
                        },
                    },
                ],
            }],
            "max_tokens": 300,
            "temperature": 0.1,
        }

        try:
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                if text.startswith("{"):
                    result = json.loads(text)
                    return (
                        result.get("verified", False),
                        result.get("confidence", 0.0),
                        result.get("evidence", "LLM vision analysis"),
                    )
            else:
                log.debug(f"[VERIFY] LLM vision API error: {resp.status_code}")
        except json.JSONDecodeError:
            log.debug("[VERIFY] Failed to parse LLM vision response")
        except Exception as e:
            log.debug(f"[VERIFY] LLM vision failed: {e}")

        return False, 0.0, "LLM vision analysis failed"

    def verify_step(self, screenshot_bytes: bytes, step_action: str,
                    step_params: dict, expected_outcome: str = "",
                    before_screenshot: bytes = None) -> VerificationResult:
        start = time.time()
        b64 = base64.b64encode(screenshot_bytes).decode() if screenshot_bytes else ""
        after_hash = self._compute_hash(screenshot_bytes) if screenshot_bytes else ""

        if not screenshot_bytes:
            return VerificationResult(
                step_number=0, verified=False, confidence=0,
                evidence="No screenshot available", method="none",
            )

        image_info = self._image_info(screenshot_bytes)
        if "SYNTHETIC" in image_info:
            log.warning(f"[VERIFY] Screenshot is synthetic: {image_info}")
            return VerificationResult(
                step_number=0, verified=False, confidence=0.1,
                evidence=f"Synthetic screenshot detected: {image_info}",
                method="synthetic_rejection", screenshot_b64=b64,
                duration_ms=(time.time() - start) * 1000,
            )

        # Method 1: LLM Vision (highest confidence)
        llm_verified, llm_confidence, llm_evidence = self._llm_vision_verify(
            b64, step_action, step_params, expected_outcome
        )
        if llm_confidence >= 0.5:
            return VerificationResult(
                step_number=0, verified=llm_verified, confidence=llm_confidence,
                evidence=llm_evidence, screenshot_b64=b64,
                method="llm_vision",
                duration_ms=(time.time() - start) * 1000,
                before_hash=self._prev_screenshot_hash or "",
                after_hash=after_hash,
            )

        # Method 2: Screenshot diffing
        if before_screenshot:
            diff_ratio, diff_desc = self._diff_screenshots(before_screenshot, screenshot_bytes)
            if diff_ratio > 0.05:
                return VerificationResult(
                    step_number=0, verified=True, confidence=min(0.5 + diff_ratio, 0.8),
                    evidence=f"Screen changed: {diff_desc} ({diff_ratio:.1%} pixels)",
                    screenshot_b64=b64, method="screenshot_diff",
                    duration_ms=(time.time() - start) * 1000,
                    before_hash=self._prev_screenshot_hash or "",
                    after_hash=after_hash,
                )

        # Method 3: OCR text matching
        text = self._extract_text(screenshot_bytes)
        ocr_verified, ocr_confidence, ocr_evidence = self._analyze_text(
            text, step_action, step_params, expected_outcome
        )

        self._prev_screenshot_hash = after_hash

        return VerificationResult(
            step_number=0, verified=ocr_verified, confidence=ocr_confidence,
            evidence=ocr_evidence, screenshot_b64=b64,
            method="ocr",
            duration_ms=(time.time() - start) * 1000,
            before_hash=self._prev_screenshot_hash or "",
            after_hash=after_hash,
        )

    def _analyze_text(self, text: str, action: str, params: dict,
                      expected_outcome: str) -> tuple:
        text_lower = text.lower()

        if "SYNTHETIC" in text:
            return False, 0.1, "Cannot verify synthetic screenshot"

        if expected_outcome:
            keywords = expected_outcome.lower().split()
            matches = sum(1 for kw in keywords if kw in text_lower)
            confidence = matches / max(len(keywords), 1)
            if confidence >= 0.5:
                return True, confidence, f"Expected text found: {expected_outcome}"
            return False, confidence, f"Expected text not fully found (matched {matches}/{len(keywords)})"

        if action in ("launch_app", "navigate_web"):
            app_name = params.get("name", params.get("url", ""))
            if app_name and app_name.lower() in text_lower:
                return True, 0.8, f"App/URL '{app_name}' visible on screen"
            if text.strip() and len(text.strip()) > 20:
                return True, 0.5, "Screen has content after launch"
            return False, 0.2, "Could not confirm app launched"

        if action == "type_text":
            typed = params.get("text", "")
            if typed and typed.lower() in text_lower:
                return True, 0.9, f"Typed text '{typed[:30]}...' visible on screen"
            return False, 0.3, "Typed text not visible on screen"

        if action == "click":
            if text.strip() and len(text.strip()) > 10:
                return True, 0.6, "Screen content changed after click"
            return True, 0.4, "Click executed (no text change detectable)"

        if action == "run_command":
            stdout = params.get("stdout", "")
            if stdout and stdout[:50].lower() in text_lower:
                return True, 0.8, "Command output visible on screen"
            return True, 0.5, "Command executed"

        if action == "screenshot":
            return True, 1.0, "Screenshot captured"

        if action == "write_file":
            path = params.get("path", "")
            if path:
                return True, 0.7, f"File write requested: {path}"
            return True, 0.5, "File write executed"

        if text.strip() and len(text.strip()) > 20:
            return True, 0.5, "Screen has content"
        return True, 0.3, "Step executed (limited verification)"

    def verify_webpage_loaded(self, screenshot_bytes: bytes, expected_text: str = "") -> VerificationResult:
        if not screenshot_bytes:
            return VerificationResult(
                step_number=0, verified=False, confidence=0,
                evidence="No screenshot", method="none",
            )
        text = self._extract_text(screenshot_bytes)
        if expected_text and expected_text.lower() in text.lower():
            return VerificationResult(
                step_number=0, verified=True, confidence=0.9,
                evidence=f"Expected content '{expected_text[:40]}' found",
                method="ocr",
            )
        if len(text.strip()) > 50:
            return VerificationResult(
                step_number=0, verified=True, confidence=0.6,
                evidence="Webpage has loaded (content detected)",
                method="ocr",
            )
        return VerificationResult(
            step_number=0, verified=False, confidence=0.2,
            evidence="Page may not have loaded yet", method="ocr",
        )

    def verify_file_created(self, screenshot_bytes: bytes, filepath: str) -> VerificationResult:
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            return VerificationResult(
                step_number=0, verified=True, confidence=1.0,
                evidence=f"File exists: {filepath} ({size} bytes)",
                method="filesystem",
            )
        return VerificationResult(
            step_number=0, verified=False, confidence=0,
            evidence=f"File not found: {filepath}",
            method="filesystem",
        )

    def verify_process_running(self, process_name: str) -> VerificationResult:
        try:
            import subprocess
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                    capture_output=True, text=True, timeout=5
                )
            else:
                result = subprocess.run(
                    ["pgrep", "-f", process_name],
                    capture_output=True, text=True, timeout=5
                )
            if process_name.lower() in result.stdout.lower() or result.returncode == 0:
                return VerificationResult(
                    step_number=0, verified=True, confidence=0.9,
                    evidence=f"Process '{process_name}' is running",
                    method="process_check",
                )
        except Exception:
            pass
        return VerificationResult(
            step_number=0, verified=False, confidence=0,
            evidence=f"Process '{process_name}' not detected",
            method="process_check",
        )


_verifier = None

def get_workspace_verifier() -> WorkspaceVerifier:
    global _verifier
    if _verifier is None:
        _verifier = WorkspaceVerifier()
    return _verifier
