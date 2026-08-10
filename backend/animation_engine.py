"""
Animation Engine — LLM-to-bpy Code Synthesis & Execution Pipeline.

Translates natural language prompts into executable Blender Python scripts,
renders with Eevee for speed, and runs a vision inspection loop for quality.

4-Layer Pipeline:
  1. LLM Code Generator  — prompt → executable bpy Python script
  2. Scene & Rig Builder  — meshes, armatures, procedural shaders
  3. Keyframe & Physics   — motion curves, rigid bodies, particles
  4. Headless Renderer    — blender --background with Eevee viewport
"""

import os
import re
import json
import time
import glob
import base64
import logging
import tempfile
import subprocess
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-anim")


# ── Security Validation for LLM-Generated bpy Code ──────────────────────────

_BPY_FORBIDDEN = [
    "subprocess", "os.system", "os.popen", "os.remove", "os.rmdir",
    "os.rename", "shutil", "open(", "file(", "import ctypes",
    "__import__", "exec(", "eval(", "compile(", "globals(",
    "locals(", "__builtins__", "importlib", "sys.modules",
    "os.environ", "socket", "urllib", "requests", "http",
    "ftplib", "smtplib", "telnetlib", "paramiko",
]


def _validate_bpy_code(code: str) -> str:
    """Validate LLM-generated bpy code to ensure it only uses Blender APIs."""
    for pattern in _BPY_FORBIDDEN:
        if pattern in code:
            raise ValueError(f"Refusing to execute bpy code: forbidden pattern '{pattern}' detected")
    return code


@dataclass
class AnimationResult:
    """Result of an animation generation + render pipeline."""
    success: bool = False
    script_path: str = ""
    output_dir: str = ""
    video_path: str = ""
    frame_paths: List[str] = field(default_factory=list)
    preview_images: List[str] = field(default_factory=list)
    error: str = ""
    attempts: int = 0
    vision_feedback: str = ""
    script_code: str = ""


# ── LLM bpy Code Generation Prompt ─────────────────────────────────────────
_BPY_CODEGEN_PROMPT = """You are an expert Blender Python (bpy) code generator.
Write a COMPLETE, runnable Blender Python script for this request:

REQUEST: {prompt}

ANIMATION SPECS:
- Duration: {duration_seconds} seconds at {fps} FPS ({total_frames} frames)
- Output: {output_path} (as PNG sequence or MP4)
- Engine: Use 'BLENDER_EEVEE' for fast viewport rendering
- Resolution: {resolution}

RULES:
1. Import bpy and math at the top
2. Clear ALL existing objects first: bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
3. Use bpy.ops for mesh creation, modifiers, materials
4. Animate using keyframe_insert() on frame ranges
5. Set scene.frame_start=1 and scene.frame_end={total_frames}
6. For materials: use Principled BSDF with Metallic, Roughness, Emission
7. For lighting: use AREA or POINT lights with energy values
8. For camera: add a camera object and set scene.camera
9. For particles: use bpy.ops.object.modifier_add(type='PARTICLE_SYSTEM')
10. For rigid body: use bpy.ops.rigidbody.object_add()
11. Set render engine: bpy.context.scene.render.engine = 'BLENDER_EEVEE'
12. Set output format: bpy.context.scene.render.image_settings.file_format = 'PNG'
13. Set render filepath: bpy.context.scene.render.filepath = "{output_path}"
14. At the end, render: bpy.ops.render.render(animation=True)
15. Print "ANIMATION_RENDER_COMPLETE" when done
16. Use ONLY standard bpy API — no external imports except math, mathutils, random
17. Use f-strings for string formatting
18. Add comments explaining each section
19. If the animation involves motion, use keyframes with linear or bezier interpolation
20. For procedural animation (constant motion), use scene.frame_set() in a loop

OUTPUT: Return ONLY the Python code, no markdown, no explanation. The code must be complete and runnable.

PYTHON CODE:
"""


class AnimationEngine:
    """LLM-to-bpy arbitrary 3D animation pipeline."""

    def __init__(self, blender_path: str = None):
        self._blender = blender_path or self._find_blender()
        self._max_retries = 3
        self._vision_available = False

        # Check if vision is available
        try:
            from vision_controller import get_vision
            self._vision_available = True
        except Exception:
            pass

    def _find_blender(self) -> Optional[str]:
        """Find Blender executable."""
        from blender_headless import find_blender
        return find_blender()

    def generate_animation(self, prompt: str, duration_seconds: float = 5.0,
                            fps: int = 24, resolution: str = "1920x1080",
                            output_dir: str = None, max_retries: int = 3) -> AnimationResult:
        """Full pipeline: prompt → code → render → inspect → fix → final render.
        
        Returns AnimationResult with video_path, frame_paths, etc.
        """
        self._max_retries = max_retries
        result = AnimationResult()

        if not self._blender:
            result.error = "Blender not found on system"
            return result

        if output_dir is None:
            output_dir = os.path.join(tempfile.gettempdir(), "jarvis_anim",
                                       f"anim_{int(time.time())}")
        os.makedirs(output_dir, exist_ok=True)
        result.output_dir = output_dir

        total_frames = int(duration_seconds * fps)
        output_path = os.path.join(output_dir, "frame_####").replace("\\", "/")

        # Phase 1: Generate bpy code via LLM
        log.info(f"[ANIM] Generating bpy code for: {prompt[:80]}...")
        script = self._generate_code(prompt, duration_seconds, fps, total_frames,
                                       output_path, resolution)
        if not script:
            result.error = "LLM failed to generate bpy code"
            return result

        result.script_code = script

        # Phase 2-4: Execute, render, inspect, self-correct
        for attempt in range(1, max_retries + 1):
            result.attempts = attempt
            log.info(f"[ANIM] Attempt {attempt}/{max_retries}")

            # Write script
            script_path = os.path.join(output_dir, f"anim_attempt_{attempt}.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script)
            result.script_path = script_path

            # Execute headlessly
            exec_result = self._execute_blender(script_path, output_dir)
            if not exec_result["success"]:
                log.warning(f"[ANIM] Execution failed: {exec_result['error'][:200]}")
                if attempt < max_retries:
                    script = self._fix_script(script, exec_result["error"], prompt)
                    continue
                result.error = exec_result["error"]
                return result

            # Collect rendered frames
            frames = sorted(glob.glob(os.path.join(output_dir, "*.png")))
            result.frame_paths = frames

            if not frames:
                log.warning("[ANIM] No frames rendered")
                if attempt < max_retries:
                    script = self._fix_script(script, "No output frames rendered", prompt)
                    continue
                result.error = "No frames rendered"
                return result

            # Render preview images (frame 1 and middle frame)
            preview = self._extract_previews(frames, total_frames, output_dir)
            result.preview_images = preview

            # Phase 3: Vision inspection
            if self._vision_available and preview:
                vision_ok, feedback = self._vision_inspect(preview[0], prompt)
                result.vision_feedback = feedback
                if not vision_ok:
                    log.info(f"[ANIM] Vision found issues: {feedback[:200]}")
                    if attempt < max_retries:
                        script = self._fix_script(script, f"Vision feedback: {feedback}", prompt)
                        continue

            # Success — try to encode to MP4
            video = self._encode_video(frames, fps, output_dir)
            result.video_path = video
            result.success = True
            result.script_code = script
            break

        log.info(f"[ANIM] Pipeline complete: success={result.success}, attempts={result.attempts}")
        return result

    def _generate_code(self, prompt: str, duration: float, fps: int,
                        total_frames: int, output_path: str, resolution: str) -> str:
        """Use LLM to generate bpy Python code from a natural language prompt."""
        try:
            from groq_agent import call
            user_prompt = _BPY_CODEGEN_PROMPT.format(
                prompt=prompt,
                duration_seconds=duration,
                fps=fps,
                total_frames=total_frames,
                output_path=output_path,
                resolution=resolution,
            )
            response = call(
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=3000,
                temperature=0.2,
            )
            if not response:
                return ""

            # Clean up — remove markdown code fences if present
            code = response.strip()
            if code.startswith("```"):
                code = re.sub(r'^```\w*\n?', '', code)
                code = re.sub(r'\n?```$', '', code)

            # Verify it imports bpy
            if "import bpy" not in code:
                code = "import bpy\nimport math\n\n" + code

            # Security validation: screen generated code for dangerous patterns
            _validate_bpy_code(code)

            return code

        except Exception as e:
            log.error(f"[ANIM] Code generation failed: {e}")
            return ""

    def _execute_blender(self, script_path: str, output_dir: str,
                          timeout: int = 120) -> Dict:
        """Execute a bpy script headlessly with Eevee."""
        try:
            result = subprocess.run(
                [self._blender, "--background", "--python", script_path],
                capture_output=True, text=True, timeout=timeout,
                cwd=output_dir,
            )
            output = result.stdout + result.stderr
            success = ("ANIMATION_RENDER_COMPLETE" in output or
                       "BLENDER_RENDER_COMPLETE" in output or
                       result.returncode == 0)

            # Check for common errors
            error = ""
            if not success:
                if "Error" in output or "Traceback" in output:
                    # Extract the error
                    lines = output.split("\n")
                    error_lines = [l for l in lines if any(x in l for x in ["Error", "Traceback", "Exception"])]
                    error = "\n".join(error_lines[-5:]) if error_lines else output[-500:]
                else:
                    error = output[-500:]

            return {"success": success, "output": output[-2000:], "error": error}

        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"Blender timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _fix_script(self, script: str, error: str, original_prompt: str) -> str:
        """Use LLM to fix a broken bpy script based on error output."""
        try:
            from groq_agent import call
            fix_prompt = f"""This Blender Python script has an error. Fix it.

ORIGINAL REQUEST: {original_prompt}

ERROR OUTPUT:
{error[:1500]}

CURRENT SCRIPT:
```python
{script[-2500:]}
```

Fix the error and return the COMPLETE corrected script. Common fixes:
- "Object has no attribute" → check bpy API method names
- "Error setting value" → check input index ranges
- "Modifier not found" → check modifier type names
- "File not found" → check file paths
- "No camera" → add bpy.ops.object.camera_add()

Return ONLY the fixed Python code, no explanation."""

            response = call(
                messages=[{"role": "user", "content": fix_prompt}],
                max_tokens=3000,
                temperature=0.1,
            )
            if response:
                code = response.strip()
                if code.startswith("```"):
                    code = re.sub(r'^```\w*\n?', '', code)
                    code = re.sub(r'\n?```$', '', code)
                if "import bpy" not in code:
                    code = "import bpy\nimport math\n\n" + code
                # Security validation on fixed code
                _validate_bpy_code(code)
                return code

        except Exception as e:
            log.debug(f"[ANIM] Script fix failed: {e}")

        return script

    def _extract_previews(self, frames: List[str], total_frames: int,
                           output_dir: str) -> List[str]:
        """Extract preview images: frame 1 and middle frame."""
        previews = []
        if frames:
            previews.append(frames[0])
        mid = total_frames // 2
        if mid < len(frames):
            previews.append(frames[mid])
        return previews

    def _vision_inspect(self, image_path: str, prompt: str) -> Tuple[bool, str]:
        """Use vision LLM to inspect a rendered frame against the user's prompt.
        
        Returns (is_ok, feedback_text).
        """
        try:
            from vision_controller import get_vision
            v = get_vision()

            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            inspect_prompt = f"""You are a 3D render quality inspector.

USER REQUEST: {prompt}

Analyze this rendered frame and evaluate:
1. Are the main objects/subjects present and visible?
2. Is the lighting adequate (not too dark/bright)?
3. Is the camera framing reasonable?
4. Are materials/colors appropriate?
5. Any obvious clipping, missing objects, or broken geometry?

Respond with ONLY a JSON object:
{{"ok": true/false, "issues": ["issue1", "issue2"], "suggestion": "brief fix suggestion"}}

If the render looks good for the request, set ok=true."""

            result = v.analyze_with_prompt(img_b64, inspect_prompt)
            if isinstance(result, str):
                # Try to parse JSON from the response
                json_match = re.search(r'\{[^}]+\}', result)
                if json_match:
                    data = json.loads(json_match.group())
                    return data.get("ok", True), data.get("suggestion", "No issues found")
                return "error" not in result.lower(), result
            return True, "Vision inspection skipped"

        except Exception as e:
            log.debug(f"[ANIM] Vision inspect failed: {e}")
            return True, "Vision inspection unavailable"

    def _encode_video(self, frames: List[str], fps: int, output_dir: str) -> str:
        """Encode PNG frames to MP4 using ffmpeg."""
        if not frames:
            return ""

        video_path = os.path.join(output_dir, "animation.mp4")

        # Check if ffmpeg is available
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        except Exception:
            log.debug("[ANIM] ffmpeg not available, skipping MP4 encode")
            return ""

        try:
            # Use frame pattern
            frame_pattern = os.path.join(os.path.dirname(frames[0]),
                                          "frame_%04d.png")
            subprocess.run([
                "ffmpeg", "-y", "-framerate", str(fps),
                "-i", frame_pattern,
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "23",
                video_path,
            ], capture_output=True, timeout=60, cwd=output_dir)

            if os.path.isfile(video_path):
                return video_path

        except Exception as e:
            log.debug(f"[ANIM] ffmpeg encode failed: {e}")

        return ""


# ── Convenience functions ──────────────────────────────────────────────────

_engine: Optional[AnimationEngine] = None

def get_engine() -> AnimationEngine:
    global _engine
    if _engine is None:
        _engine = AnimationEngine()
    return _engine

def create_animation(prompt: str, duration: float = 5.0, fps: int = 24,
                     resolution: str = "1920x1080", output_dir: str = None) -> AnimationResult:
    """One-call convenience: prompt → animation."""
    return get_engine().generate_animation(
        prompt=prompt, duration_seconds=duration,
        fps=fps, resolution=resolution, output_dir=output_dir,
    )
