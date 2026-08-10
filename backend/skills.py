"""JARVIS Native Skills — Application-specific control interfaces.

Instead of blindly clicking, JARVIS uses the best available control
mechanism for each application:

1. Native API (most reliable, fastest)
2. CLI (scriptable, automatable)
3. CDP for browsers (DOM-level control)
4. UI Automation (Windows accessibility)
5. Mouse/keyboard (fallback)

Each skill provides:
- name: identifier
- capabilities: what it can do
- execute(action, params): perform an action
- verify(result): check if it worked
"""

import os
import json
import time
import logging
import subprocess
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum

log = logging.getLogger("native_skills")


class SkillCapability(Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    READ = "read"
    SCREENSHOT = "screenshot"
    SCROLL = "scroll"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    EVALUATE_JS = "evaluate_js"
    GET_HTML = "get_html"
    GET_TEXT = "get_text"
    GET_TITLE = "get_title"
    GET_URL = "get_url"
    NEW_TAB = "new_tab"
    CLOSE_TAB = "close_tab"
    SWITCH_TAB = "switch_tab"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    RELOAD = "reload"
    CLONE = "clone"
    COMMIT = "commit"
    PUSH = "push"
    PULL = "pull"
    BRANCH = "branch"
    STATUS = "status"
    DIFF = "diff"
    LOG = "log"
    CREATE_SCENE = "create_scene"
    ADD_OBJECT = "add_object"
    SET_MATERIAL = "set_material"
    RENDER = "render"
    ANIMATE = "animate"
    EXPORT = "export"


@dataclass
class ActionResult:
    """Result of a skill action execution."""
    success: bool
    action: str
    result: Any = None
    error: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "action": self.action,
            "result": self.result,
            "error": self.error,
            "evidence": self.evidence,
            "duration_ms": self.duration_ms,
        }


class BaseSkill(ABC):
    """Base class for all native skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def capabilities(self) -> List[SkillCapability]:
        ...

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any] = None) -> ActionResult:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    def verify(self, result: ActionResult, expected: Any = None) -> bool:
        """Verify that an action produced the expected result."""
        return result.success and result.error == ""


class ChromeCDPSkill(BaseSkill):
    """Chrome DevTools Protocol skill — controls Chrome at the DOM level."""

    def __init__(self, port: int = 9222):
        self._port = port
        self._targets = []
        self._ws_url = None

    @property
    def name(self) -> str:
        return "chrome_cdp"

    @property
    def capabilities(self) -> List[SkillCapability]:
        return [
            SkillCapability.NAVIGATE, SkillCapability.CLICK, SkillCapability.TYPE,
            SkillCapability.READ, SkillCapability.SCREENSHOT, SkillCapability.SCROLL,
            SkillCapability.EVALUATE_JS, SkillCapability.GET_HTML, SkillCapability.GET_TEXT,
            SkillCapability.GET_TITLE, SkillCapability.GET_URL, SkillCapability.NEW_TAB,
            SkillCapability.CLOSE_TAB, SkillCapability.SWITCH_TAB,
            SkillCapability.GO_BACK, SkillCapability.GO_FORWARD, SkillCapability.RELOAD,
        ]

    def is_available(self) -> bool:
        """Check if Chrome is running with remote debugging."""
        try:
            import httpx
            resp = httpx.get(f"http://127.0.0.1:{self._port}/json/version", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def execute(self, action: str, params: Dict[str, Any] = None) -> ActionResult:
        params = params or {}
        start = time.time()

        try:
            if action == "navigate":
                return self._navigate(params.get("url", ""))
            elif action == "click":
                return self._click(params.get("selector", ""), params.get("x", 0), params.get("y", 0))
            elif action == "type":
                return self._type(params.get("selector", ""), params.get("text", ""))
            elif action == "get_text":
                return self._get_text(params.get("selector", ""))
            elif action == "get_html":
                return self._get_html()
            elif action == "get_title":
                return self._get_title()
            elif action == "get_url":
                return self._get_url()
            elif action == "screenshot":
                return self._screenshot()
            elif action == "evaluate_js":
                return self._evaluate_js(params.get("expression", ""))
            elif action == "scroll":
                return self._scroll(params.get("x", 0), params.get("y", 0))
            elif action == "new_tab":
                return self._new_tab(params.get("url", ""))
            elif action == "close_tab":
                return self._close_tab()
            elif action == "go_back":
                return self._go_back()
            elif action == "reload":
                return self._reload()
            else:
                return ActionResult(False, action, error=f"Unknown action: {action}")
        except Exception as e:
            return ActionResult(False, action, error=str(e))
        finally:
            pass

    def _get_page_target(self) -> Optional[str]:
        """Get WebSocket URL of the first page target."""
        try:
            import httpx
            resp = httpx.get(f"http://127.0.0.1:{self._port}/json", timeout=2)
            targets = resp.json()
            for target in targets:
                if target.get("type") == "page":
                    return target.get("webSocketDebuggerUrl")
        except Exception:
            pass
        return None

    def _navigate(self, url: str) -> ActionResult:
        ws_url = self._get_page_target()
        if not ws_url:
            return ActionResult(False, "navigate", error="No Chrome page target")

        try:
            import asyncio
            import websockets

            async def do_navigate():
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "Page.navigate",
                        "params": {"url": url},
                    }))
                    resp = await asyncio.wait_for(ws.recv(), timeout=10)
                    return json.loads(resp)

            result = asyncio.get_event_loop().run_until_complete(do_navigate())
            return ActionResult(
                success=True,
                action="navigate",
                result=result,
                evidence={"url": url, "response": result},
                duration_ms=(time.time() - 0) * 1000,
            )
        except Exception as e:
            return ActionResult(False, "navigate", error=str(e))

    def _click(self, selector: str, x: int = 0, y: int = 0) -> ActionResult:
        if selector:
            js = f"""
            (function() {{
                var el = document.querySelector('{selector}');
                if (el) {{
                    el.click();
                    return {{ clicked: true, tag: el.tagName, text: el.textContent?.substring(0, 50) }};
                }}
                return {{ clicked: false, error: 'Element not found' }};
            }})()
            """
        else:
            js = f"""
            (function() {{
                var el = document.elementFromPoint({x}, {y});
                if (el) {{
                    el.click();
                    return {{ clicked: true, x: {x}, y: {y}, tag: el.tagName }};
                }}
                return {{ clicked: false }};
            }})()
            """
        return self._evaluate_js(js)

    def _type(self, selector: str, text: str) -> ActionResult:
        js = f"""
        (function() {{
            var el = document.querySelector('{selector}');
            if (el) {{
                el.focus();
                el.value = '{text}';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return {{ typed: true, length: {len(text)} }};
            }}
            return {{ typed: false, error: 'Element not found' }};
        }})()
        """
        return self._evaluate_js(js)

    def _get_text(self, selector: str = "body") -> ActionResult:
        js = f"""
        (function() {{
            var el = document.querySelector('{selector}');
            return el ? el.textContent : 'Element not found';
        }})()
        """
        return self._evaluate_js(js)

    def _get_html(self) -> ActionResult:
        return self._evaluate_js("document.documentElement.outerHTML")

    def _get_title(self) -> ActionResult:
        return self._evaluate_js("document.title")

    def _get_url(self) -> ActionResult:
        return self._evaluate_js("window.location.href")

    def _screenshot(self) -> ActionResult:
        ws_url = self._get_page_target()
        if not ws_url:
            return ActionResult(False, "screenshot", error="No Chrome page target")

        try:
            import asyncio
            import websockets
            import base64

            async def do_screenshot():
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "Page.captureScreenshot",
                        "params": {"format": "jpeg", "quality": 60},
                    }))
                    resp = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(resp)
                    return base64.b64decode(data["result"]["data"])

            image_data = asyncio.get_event_loop().run_until_complete(do_screenshot())
            return ActionResult(
                success=True,
                action="screenshot",
                result={"size": len(image_data)},
                evidence={"format": "jpeg", "size_bytes": len(image_data)},
                duration_ms=0,
            )
        except Exception as e:
            return ActionResult(False, "screenshot", error=str(e))

    def _evaluate_js(self, expression: str) -> ActionResult:
        ws_url = self._get_page_target()
        if not ws_url:
            return ActionResult(False, "evaluate_js", error="No Chrome page target")

        try:
            import asyncio
            import websockets

            async def do_eval():
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": expression, "returnByValue": True},
                    }))
                    resp = await asyncio.wait_for(ws.recv(), timeout=10)
                    return json.loads(resp)

            result = asyncio.get_event_loop().run_until_complete(do_eval())
            value = result.get("result", {}).get("result", {}).get("value")

            return ActionResult(
                success=True,
                action="evaluate_js",
                result=value,
                evidence={"expression": expression[:100], "result_preview": str(value)[:200] if value else None},
                duration_ms=0,
            )
        except Exception as e:
            return ActionResult(False, "evaluate_js", error=str(e))

    def _scroll(self, x: int, y: int) -> ActionResult:
        return self._evaluate_js(f"window.scrollTo({x}, {y})")

    def _new_tab(self, url: str = "") -> ActionResult:
        try:
            import httpx
            resp = httpx.get(f"http://127.0.0.1:{self._port}/json/new?{url}", timeout=5)
            return ActionResult(success=True, action="new_tab", result=resp.json())
        except Exception as e:
            return ActionResult(False, "new_tab", error=str(e))

    def _close_tab(self) -> ActionResult:
        ws_url = self._get_page_target()
        if ws_url:
            try:
                import asyncio
                import websockets
                async def do_close():
                    async with websockets.connect(ws_url) as ws:
                        await ws.close()
                asyncio.get_event_loop().run_until_complete(do_close())
                return ActionResult(success=True, action="close_tab")
            except Exception as e:
                return ActionResult(False, "close_tab", error=str(e))
        return ActionResult(False, "close_tab", error="No tab to close")

    def _go_back(self) -> ActionResult:
        return self._evaluate_js("window.history.back()")

    def _reload(self) -> ActionResult:
        return self._evaluate_js("window.location.reload()")


class GitCLISkill(BaseSkill):
    """Git command-line skill — scriptable Git operations."""

    @property
    def name(self) -> str:
        return "git_cli"

    @property
    def capabilities(self) -> List[SkillCapability]:
        return [
            SkillCapability.CLONE, SkillCapability.COMMIT, SkillCapability.PUSH,
            SkillCapability.PULL, SkillCapability.BRANCH, SkillCapability.STATUS,
            SkillCapability.DIFF, SkillCapability.LOG,
        ]

    def is_available(self) -> bool:
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def execute(self, action: str, params: Dict[str, Any] = None) -> ActionResult:
        params = params or {}
        start = time.time()

        try:
            if action == "clone":
                return self._clone(params.get("url", ""), params.get("path", "."))
            elif action == "commit":
                return self._commit(params.get("message", ""))
            elif action == "push":
                return self._push(params.get("remote", "origin"), params.get("branch", "main"))
            elif action == "pull":
                return self._pull(params.get("remote", "origin"), params.get("branch", "main"))
            elif action == "branch":
                return self._branch(params.get("name", ""), params.get("action", "list"))
            elif action == "status":
                return self._status()
            elif action == "diff":
                return self._diff(params.get("cached", False))
            elif action == "log":
                return self._log(params.get("count", 10))
            else:
                return ActionResult(False, action, error=f"Unknown action: {action}")
        except Exception as e:
            return ActionResult(False, action, error=str(e))

    def _run_git(self, args: List[str], cwd: str = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, timeout=30,
            cwd=cwd or os.getcwd(),
        )

    def _clone(self, url: str, path: str) -> ActionResult:
        result = self._run_git(["clone", url, path])
        success = result.returncode == 0
        return ActionResult(
            success=success,
            action="clone",
            result={"path": path} if success else None,
            error=result.stderr if not success else "",
            evidence={"url": url, "output": result.stdout[:200]},
        )

    def _commit(self, message: str) -> ActionResult:
        self._run_git(["add", "."])
        result = self._run_git(["commit", "-m", message])
        success = result.returncode == 0
        return ActionResult(
            success=success,
            action="commit",
            result={"message": message} if success else None,
            error=result.stderr if not success else "",
            evidence={"output": result.stdout[:200]},
        )

    def _push(self, remote: str, branch: str) -> ActionResult:
        result = self._run_git(["push", remote, branch])
        success = result.returncode == 0
        return ActionResult(
            success=success, action="push",
            result={"remote": remote, "branch": branch} if success else None,
            error=result.stderr if not success else "",
        )

    def _pull(self, remote: str, branch: str) -> ActionResult:
        result = self._run_git(["pull", remote, branch])
        success = result.returncode == 0
        return ActionResult(
            success=success, action="pull",
            result={"remote": remote, "branch": branch} if success else None,
            error=result.stderr if not success else "",
        )

    def _branch(self, name: str, action: str) -> ActionResult:
        if action == "list":
            result = self._run_git(["branch", "-a"])
            branches = [b.strip().strip("* ") for b in result.stdout.split("\n") if b.strip()]
            return ActionResult(True, "branch", result={"branches": branches})
        elif action == "create":
            result = self._run_git(["checkout", "-b", name])
            return ActionResult(result.returncode == 0, "branch", result={"name": name}, error=result.stderr)
        elif action == "switch":
            result = self._run_git(["checkout", name])
            return ActionResult(result.returncode == 0, "branch", result={"name": name}, error=result.stderr)
        return ActionResult(False, "branch", error=f"Unknown branch action: {action}")

    def _status(self) -> ActionResult:
        result = self._run_git(["status", "--porcelain"])
        lines = [l for l in result.stdout.split("\n") if l.strip()]
        return ActionResult(True, "status", result={"files": len(lines), "changes": lines[:20]})

    def _diff(self, cached: bool) -> ActionResult:
        args = ["diff", "--cached"] if cached else ["diff"]
        result = self._run_git(args)
        return ActionResult(True, "diff", result={"diff": result.stdout[:5000]})

    def _log(self, count: int) -> ActionResult:
        result = self._run_git(["log", f"--oneline", f"-{count}"])
        commits = [l for l in result.stdout.split("\n") if l.strip()]
        return ActionResult(True, "log", result={"commits": commits, "count": len(commits)})


class BlenderPythonSkill(BaseSkill):
    """Blender Python API skill — 3D modeling, animation, rendering."""

    @property
    def name(self) -> str:
        return "blender_python"

    @property
    def capabilities(self) -> List[SkillCapability]:
        return [
            SkillCapability.CREATE_SCENE, SkillCapability.ADD_OBJECT,
            SkillCapability.SET_MATERIAL, SkillCapability.RENDER,
            SkillCapability.ANIMATE, SkillCapability.EXPORT,
        ]

    def is_available(self) -> bool:
        """Check if Blender is installed."""
        common_paths = [
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
            "/usr/bin/blender",
            "/Applications/Blender.app/Contents/MacOS/Blender",
        ]
        for path in common_paths:
            if os.path.isfile(path):
                self._blender_path = path
                return True
        try:
            result = subprocess.run(["blender", "--version"], capture_output=True, timeout=5)
            self._blender_path = "blender"
            return result.returncode == 0
        except Exception:
            return False

    def execute(self, action: str, params: Dict[str, Any] = None) -> ActionResult:
        params = params or {}
        start = time.time()

        try:
            if action == "create_scene":
                return self._run_blender_script(self._create_scene_script(params))
            elif action == "add_object":
                return self._run_blender_script(self._add_object_script(params))
            elif action == "set_material":
                return self._run_blender_script(self._set_material_script(params))
            elif action == "render":
                return self._run_blender_script(self._render_script(params))
            elif action == "export":
                return self._run_blender_script(self._export_script(params))
            else:
                return ActionResult(False, action, error=f"Unknown action: {action}")
        except Exception as e:
            return ActionResult(False, action, error=str(e))

    def _run_blender_script(self, script: str) -> ActionResult:
        """Run a Python script inside Blender."""
        script_path = f"/tmp/jarvis_blender_{int(time.time())}.py"
        with open(script_path, "w") as f:
            f.write(script)

        try:
            result = subprocess.run(
                [self._blender_path, "--background", "--python", script_path],
                capture_output=True, text=True, timeout=300,
            )
            success = result.returncode == 0
            return ActionResult(
                success=success,
                action="blender_script",
                result={"output": result.stdout[:1000]} if success else None,
                error=result.stderr if not success else "",
                evidence={"script": script[:200], "output_preview": result.stdout[:200]},
            )
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)

    def _create_scene_script(self, params: Dict) -> str:
        return f"""
import bpy
bpy.ops.wm.read_factory_settings_use_empty()
bpy.context.scene.name = "{params.get('name', 'JARVIS_Scene')}"
print("Scene created")
"""

    def _add_object_script(self, params: Dict) -> str:
        obj_type = params.get("type", "cube")
        location = params.get("location", [0, 0, 0])
        return f"""
import bpy
if "{obj_type}" == "cube":
    bpy.ops.mesh.primitive_cube_add(location={location})
elif "{obj_type}" == "sphere":
    bpy.ops.mesh.primitive_uv_sphere_add(location={location})
elif "{obj_type}" == "cylinder":
    bpy.ops.mesh.primitive_cylinder_add(location={location})
obj = bpy.context.active_object
obj.name = "{params.get('name', 'Object')}"
print(f"Added {obj_type} at {location}")
"""

    def _render_script(self, params: Dict) -> str:
        output = params.get("output", "/tmp/jarvis_render.png")
        return f"""
import bpy
bpy.context.scene.render.filepath = "{output}"
bpy.context.scene.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
print(f"Rendered to {output}")
"""

    def _set_material_script(self, params: Dict) -> str:
        color = params.get("color", [0.8, 0.2, 0.2, 1.0])
        return f"""
import bpy
obj = bpy.context.active_object
mat = bpy.data.materials.new(name="{params.get('name', 'Material')}")
mat.diffuse_color = {tuple(color)}
obj.data.materials.append(mat)
print(f"Material applied")
"""

    def _export_script(self, params: Dict) -> str:
        filepath = params.get("filepath", "/tmp/jarvis_export.fbx")
        return f"""
import bpy
bpy.ops.export_scene.fbx(filepath="{filepath}")
print(f"Exported to {filepath}")
"""


class SkillRegistry:
    """Registry of all available native skills."""

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register all built-in skills."""
        self.register(ChromeCDPSkill())
        self.register(GitCLISkill())
        self.register(BlenderPythonSkill())

    def register(self, skill: BaseSkill):
        """Register a new skill."""
        self._skills[skill.name] = skill
        log.info(f"[SKILLS] Registered: {skill.name}")

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_available_skills(self) -> List[dict]:
        """Get all available (detected) skills."""
        return [
            {
                "name": skill.name,
                "capabilities": [c.value for c in skill.capabilities],
                "available": skill.is_available(),
            }
            for skill in self._skills.values()
        ]

    def execute_action(self, skill_name: str, action: str, params: Dict[str, Any] = None) -> ActionResult:
        """Execute an action using a specific skill."""
        skill = self.get_skill(skill_name)
        if not skill:
            return ActionResult(False, action, error=f"Skill not found: {skill_name}")
        if not skill.is_available():
            return ActionResult(False, action, error=f"Skill not available: {skill_name}")
        return skill.execute(action, params)


# Global instance
_registry = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
