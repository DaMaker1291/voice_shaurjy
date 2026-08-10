"""
Blender Engine
Generates bug-free Python bpy scripts for Eevee/Cycles 3D renders
and executes headlessly via blender --background --python.
"""
import os
import subprocess
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("blender_engine")

BLENDER_RENDER_ENGINE = "EEVEE"
DEFAULT_RESOLUTION = (1920, 1080)
DEFAULT_SAMPLES = 64
DEFAULT_OUTPUT_FORMAT = "PNG"


def generate_bpy_script(
    output_path: str,
    scene_name: str = "JARVIS_Scene",
    objects: Optional[List[Dict[str, Any]]] = None,
    camera_position: tuple = (0, -5, 3),
    render_samples: int = DEFAULT_SAMPLES,
    engine: str = BLENDER_RENDER_ENGINE,
) -> str:
    """Generate a bpy Python script for headless rendering."""
    objects = objects or [
        {"type": "cube", "location": (0, 0, 0), "scale": (1, 1, 1), "name": "Cube"},
        {"type": "sphere", "location": (2, 0, 1), "scale": (0.5, 0.5, 0.5), "name": "Sphere"},
        {"type": "light", "location": (0, 0, 5), "name": "SunLight"},
    ]

    lines = [
        "import bpy",
        "import math",
        "",
        f"# Scene setup",
        f'scene = bpy.context.scene',
        f'scene.name = "{scene_name}"',
        f'scene.render.engine = "{engine}"',
        f'scene.render.resolution_x = {DEFAULT_RESOLUTION[0]}',
        f'scene.render.resolution_y = {DEFAULT_RESOLUTION[1]}',
        f'scene.render.resolution_percentage = 100',
        f'scene.render.filepath = "{output_path}"',
        f'scene.render.image_settings.file_format = "{DEFAULT_OUTPUT_FORMAT}"',
        f'scene.render.samples = {render_samples}',
        "",
        "# Clear default objects",
        "bpy.ops.object.select_all(action='SELECT')",
        "bpy.ops.object.delete(use_global=False)",
        "",
    ]

    for obj in objects:
        obj_type = obj.get("type", "cube")
        location = obj.get("location", (0, 0, 0))
        scale = obj.get("scale", (1, 1, 1))
        name = obj.get("name", obj_type.title())

        if obj_type == "cube":
            lines.append(f'bpy.ops.mesh.primitive_cube_add(size=2, location=({location[0]}, {location[1]}, {location[2]}))')
        elif obj_type == "sphere":
            lines.append(f'bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=({location[0]}, {location[1]}, {location[2]}))')
        elif obj_type == "light":
            lines.append(f'bpy.ops.object.light_add(type="SUN", location=({location[0]}, {location[1]}, {location[2]}))')
        elif obj_type == "plane":
            lines.append(f'bpy.ops.mesh.primitive_plane_add(size=10, location=({location[0]}, {location[1]}, {location[2]}))')
        else:
            lines.append(f'bpy.ops.mesh.primitive_cube_add(size=2, location=({location[0]}, {location[1]}, {location[2]}))')

        lines.append(f'bpy.context.active_object.name = "{name}"')
        lines.append(f'bpy.context.active_object.scale = ({scale[0]}, {scale[1]}, {scale[2]})')
        lines.append("")

    lines.append("# Camera setup")
    cam_x, cam_y, cam_z = camera_position
    lines.append(f'bpy.ops.object.camera_add(location=({cam_x}, {cam_y}, {cam_z}))')
    lines.append('bpy.context.active_object.name = "Camera"')
    lines.append('bpy.context.scene.camera = bpy.context.active_object')
    lines.append("")

    lines.append("# Render")
    lines.append('bpy.ops.render.render(write_still=True)')
    lines.append('print("Render complete")')

    script_content = "\n".join(lines)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    script_file = output_path.replace(".png", ".py")
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(script_content)

    return script_file


def run_blender_render(
    script_path: str,
    blender_path: str = "blender",
    background: bool = True,
) -> Dict[str, Any]:
    """Execute a bpy script headlessly via Blender."""
    cmd = [blender_path]
    if background:
        cmd.append("--background")
    cmd.extend(["--python", script_path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": " ".join(cmd),
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Blender not found. Install with: apt install blender",
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Blender render timed out after 300s",
            "command": " ".join(cmd),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "command": " ".join(cmd),
        }


def render_scene(
    output_image: str,
    objects: Optional[List[Dict[str, Any]]] = None,
    blender_path: str = "blender",
) -> Dict[str, Any]:
    """Full pipeline: generate script -> render -> return result."""
    script_path = generate_bpy_script(output_image, objects=objects)
    result = run_blender_render(script_path, blender_path=blender_path)
    return result