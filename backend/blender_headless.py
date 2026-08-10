"""
Blender Headless — Run Blender Python scripts in background.

Finds Blender, writes a temp .py script, executes headlessly,
and returns the output files (PNG, OBJ, STL, etc.).
"""

import os
import sys
import json
import glob
import time
import shutil
import logging
import tempfile
import subprocess
from typing import Optional, Dict

log = logging.getLogger("jarvis-blender")

# Common Blender locations on Windows
_BLENDER_PATHS = [
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 3.5\blender.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender\blender.exe"),
]

# Template scripts for common tasks
TEMPLATES = {
    "product_prototype": '''
import bpy
import math

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create a product prototype — isometric cube with bevel
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
obj = bpy.context.active_object
obj.name = "ProductPrototype"

# Add bevel modifier for smooth edges
mod = obj.modifiers.new(name="Bevel", type='BEVEL')
mod.width = 0.1
mod.segments = 4

# Metallic material
mat = bpy.data.materials.new(name="MetallicMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
bsdf = nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.85, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.9
    bsdf.inputs["Roughness"].default_value = 0.15
obj.data.materials.append(mat)

# Add floor
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
floor = bpy.context.active_object
floor_mat = bpy.data.materials.new(name="FloorMat")
floor_mat.use_nodes = True
floor_bsdf = floor_mat.node_tree.nodes.get("Principled BSDF")
if floor_bsdf:
    floor_bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.07, 1.0)
    floor_bsdf.inputs["Roughness"].default_value = 0.3
floor.data.materials.append(floor_mat)

# Camera
bpy.ops.object.camera_add(location=(4, -4, 4))
cam = bpy.context.active_object
cam.rotation_euler = (math.radians(55), 0, math.radians(45))
bpy.context.scene.camera = cam

# Sun light
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
light = bpy.context.active_object
light.data.energy = 3

# Render settings
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 128
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'

# Set output path
scene.render.filepath = "{output_path}"

# Render
bpy.ops.render.render(write_still=True)
print("BLENDER_RENDER_COMPLETE")
''',

    "export_obj": '''
import bpy
import os

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create a sample mesh
bpy.ops.mesh.primitive_monkey_add(size=2, location=(0, 0, 1))
obj = bpy.context.active_object
obj.name = "ExportModel"

# Add subdivision
mod = obj.modifiers.new(name="Subsurf", type='SUBSURF')
mod.levels = 2

# Export as OBJ
bpy.ops.wm.obj_export(
    filepath="{output_path}",
    export_selected_objects=True,
    export_materials=True,
)
print("BLENDER_EXPORT_COMPLETE: {output_path}")
''',

    "rotating_object": '''
import bpy
import math

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create and animate a rotating torus
bpy.ops.mesh.primitive_torus_add(major_radius=1.5, minor_radius=0.4, location=(0, 0, 1))
obj = bpy.context.active_object
obj.name = "RotatingTorus"

# Metallic material
mat = bpy.data.materials.new(name="MetalMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.1, 0.5, 1.0, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.95
    bsdf.inputs["Roughness"].default_value = 0.1
obj.data.materials.append(mat)

# Keyframe rotation
scene = bpy.context.scene
for frame in range(1, {total_frames} + 1):
    scene.frame_set(frame)
    obj.rotation_euler.x = math.radians(frame * 3)
    obj.rotation_euler.z = math.radians(frame * 5)
    obj.keyframe_insert(data_path="rotation_euler")

# Camera
bpy.ops.object.camera_add(location=(4, -4, 3))
cam = bpy.context.active_object
cam.rotation_euler = (math.radians(60), 0, math.radians(45))
scene.camera = cam

# Light
bpy.ops.object.light_add(type='AREA', location=(3, -3, 5))
light = bpy.context.active_object
light.data.energy = 500

# Render settings
scene.render.engine = 'BLENDER_EEVEE'
scene.frame_start = 1
scene.frame_end = {total_frames}
scene.render.fps = {fps}
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = "{output_path}"
bpy.ops.render.render(animation=True)
print("ANIMATION_RENDER_COMPLETE")
''',

    "particle_explosion": '''
import bpy
import math
import random

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = {total_frames}

# Central sphere
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 2))
sphere = bpy.context.active_object
sphere.name = "CoreSphere"

# Emissive material
mat = bpy.data.materials.new(name="GlowMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (1.0, 0.2, 0.05, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 5.0
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.3, 0.1, 1.0)
sphere.data.materials.append(mat)

# Particle system for explosion
bpy.ops.object.modifier_add(type='PARTICLE_SYSTEM')
psys = sphere.particle_systems[0].settings
psys.count = 5000
psys.frame_start = {explode_start}
psys.frame_end = {explode_end}
psys.normal_factor = 15.0
psys.lifetime = 40

# Animate sphere scale (shrink as it explodes)
for frame in range(1, {total_frames} + 1):
    scene.frame_set(frame)
    if frame < {explode_start}:
        s = 1.0 + 0.2 * math.sin(frame * 0.2)
    else:
        progress = (frame - {explode_start}) / max(1, {total_frames} - {explode_start})
        s = max(0.1, 1.0 - progress * 0.9)
    sphere.scale = (s, s, s)
    sphere.keyframe_insert(data_path="scale")

# Camera
bpy.ops.object.camera_add(location=(5, -5, 4))
cam = bpy.context.active_object
cam.rotation_euler = (math.radians(55), 0, math.radians(45))
scene.camera = cam

# Lights
bpy.ops.object.light_add(type='POINT', location=(3, -3, 6))
light = bpy.context.active_object
light.data.energy = 300
light.data.color = (1.0, 0.5, 0.2)

# Render
scene.render.engine = 'BLENDER_EEVEE'
scene.render.fps = {fps}
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = "{output_path}"
bpy.ops.render.render(animation=True)
print("ANIMATION_RENDER_COMPLETE")
''',
}


def find_blender() -> Optional[str]:
    """Find Blender executable on the system."""
    # Check common paths
    for path in _BLENDER_PATHS:
        if os.path.isfile(path):
            return path

    # Check PATH
    blender = shutil.which("blender")
    if blender:
        return blender

    # Check via where command
    try:
        result = subprocess.run(["where", "blender"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0]
    except Exception:
        pass

    return None


def run_blender_code(code: str, output_dir: str = None, timeout: int = 120) -> Dict:
    """Run arbitrary Blender Python code headlessly.
    
    Returns: {"success": bool, "output": str, "error": str, "files": list}
    """
    blender = find_blender()
    if not blender:
        return {"success": False, "error": "Blender not found on system"}

    if output_dir is None:
        output_dir = os.path.join(tempfile.gettempdir(), "jarvis_blender")
    os.makedirs(output_dir, exist_ok=True)

    # Write the Python script
    script_path = os.path.join(output_dir, "script.py")
    with open(script_path, "w") as f:
        f.write(code)

    # Run Blender headlessly
    try:
        result = subprocess.run(
            [blender, "--background", "--python", script_path],
            capture_output=True, text=True, timeout=timeout,
            cwd=output_dir,
        )
        output = result.stdout + result.stderr
        success = "BLENDER_RENDER_COMPLETE" in output or result.returncode == 0

        # Collect output files
        files = []
        for ext in ["*.png", "*.jpg", "*.obj", "*.stl", "*.fbx", "*.blend"]:
            files.extend(glob.glob(os.path.join(output_dir, ext)))

        return {
            "success": success,
            "output": output[-2000:],
            "error": result.stderr[-1000:] if not success else "",
            "files": files,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Blender timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_template(template_name: str, output_dir: str = None, **kwargs) -> Dict:
    """Run a predefined Blender template.
    
    Templates: product_prototype, export_obj, rotating_object, particle_explosion
    Animation templates accept: fps, total_frames, explode_start, explode_end
    """
    if template_name not in TEMPLATES:
        return {"success": False, "error": f"Unknown template: {template_name}. Available: {list(TEMPLATES.keys())}"}

    if output_dir is None:
        output_dir = os.path.join(tempfile.gettempdir(), "jarvis_blender")
    os.makedirs(output_dir, exist_ok=True)

    # Default animation params
    fps = kwargs.get("fps", 24)
    duration = kwargs.get("duration_seconds", 5)
    total_frames = kwargs.get("total_frames", int(duration * fps))
    explode_start = kwargs.get("explode_start", int(total_frames * 0.4))
    explode_end = kwargs.get("explode_end", int(total_frames * 0.6))

    # Generate output path
    if "rotating" in template_name or "explosion" in template_name or "particle" in template_name:
        output_path = os.path.join(output_dir, "frame_####")
    elif "prototype" in template_name:
        output_path = os.path.join(output_dir, f"output_{template_name}.png")
    else:
        output_path = os.path.join(output_dir, f"output_{template_name}.obj")

    # Fill in template
    script = TEMPLATES[template_name].format(
        output_path=output_path.replace("\\", "/"),
        fps=fps,
        total_frames=total_frames,
        explode_start=explode_start,
        explode_end=explode_end,
        **kwargs,
    )
    return run_blender_code(script, output_dir)


def create_material(name: str, color: tuple = (0.8, 0.8, 0.85, 1.0),
                     metallic: float = 0.9, roughness: float = 0.15) -> str:
    """Generate Blender Python code to create a material."""
    return f"""
mat = bpy.data.materials.new(name="{name}")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = {color}
    bsdf.inputs["Metallic"].default_value = {metallic}
    bsdf.inputs["Roughness"].default_value = {roughness}
obj.data.materials.append(mat)
"""


# Module-level convenience
_blender_path = None

def get_blender_path() -> Optional[str]:
    global _blender_path
    if _blender_path is None:
        _blender_path = find_blender()
    return _blender_path
