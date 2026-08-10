import bpy
import math
import os
import sys
import time

print("[JARVIS] === GENERATING PARAMETRIC TURBINE ===")
start = time.time()

OUTPUT_DIR = "/opt/jarvis/cad_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Parameters
NUM_BLADES = 12
HUB_RADIUS = 1.0
BLADE_LENGTH = 2.0

# Turbine Hub
bpy.ops.mesh.primitive_cylinder_add(radius=HUB_RADIUS, depth=0.6, location=(0, 0, 0), vertices=64)
hub = bpy.context.active_object
hub.name = "TurbineHub"

# Turbine Blades
for i in range(NUM_BLADES):
    angle = i * (2 * math.pi / NUM_BLADES)
    x = math.cos(angle) * (HUB_RADIUS + BLADE_LENGTH / 2)
    y = math.sin(angle) * (HUB_RADIUS + BLADE_LENGTH / 2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 0))
    blade = bpy.context.active_object
    blade.name = f"Blade_{i:02d}"
    blade.scale = (0.3, BLADE_LENGTH, 0.05)
    blade.rotation_euler = (0.2, 0, angle)

# Central Shaft
bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=3.0, location=(0, 0, 0), vertices=32)
shaft = bpy.context.active_object
shaft.name = "DriveShaft"

# Base Plate
bpy.ops.mesh.primitive_cylinder_add(radius=2.8, depth=0.15, location=(0, 0, -0.375), vertices=64)
base = bpy.context.active_object
base.name = "BasePlate"

# Materials
mat_metal = bpy.data.materials.new(name="Metal")
mat_metal.use_nodes = True
bsdf = mat_metal.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.35, 0.38, 0.42, 1)
bsdf.inputs["Metallic"].default_value = 0.95
bsdf.inputs["Roughness"].default_value = 0.15

mat_blade = bpy.data.materials.new(name="BladeMetal")
mat_blade.use_nodes = True
bsdf_b = mat_blade.node_tree.nodes["Principled BSDF"]
bsdf_b.inputs["Base Color"].default_value = (0.45, 0.48, 0.52, 1)
bsdf_b.inputs["Metallic"].default_value = 0.9
bsdf_b.inputs["Roughness"].default_value = 0.1

for obj in bpy.data.objects:
    if obj.type == 'MESH':
        if "Blade" in obj.name:
            obj.data.materials.append(mat_blade)
        else:
            obj.data.materials.append(mat_metal)

# Camera
bpy.ops.object.camera_add(location=(0, -10, 5), rotation=(1.1, 0, 0))
camera = bpy.context.active_object
camera.name = "Camera"
bpy.context.scene.camera = camera

# Lighting
bpy.ops.object.light_add(type='AREA', location=(5, -5, 8))
key = bpy.context.active_object
key.data.energy = 400

bpy.ops.object.light_add(type='AREA', location=(-5, 5, 3))
fill = bpy.context.active_object
fill.data.energy = 150

# Render settings
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# Save blend file
blend_path = os.path.join(OUTPUT_DIR, "turbine_engine.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"[JARVIS] Saved: {blend_path}")

# Render hero frame
hero_path = os.path.join(OUTPUT_DIR, "turbine_hero.png")
scene.render.filepath = hero_path
bpy.ops.render.render(write_still=True)
print(f"[JARVIS] Hero render: {hero_path}")

# Render 10-frame turntable (reduced for speed)
anim_dir = os.path.join(OUTPUT_DIR, "turntable_frames")
os.makedirs(anim_dir, exist_ok=True)
for frame in range(10):
    angle = frame * (2 * math.pi / 10)
    camera.location.x = math.sin(angle) * 10
    camera.location.y = -math.cos(angle) * 10
    camera.location.z = 5
    scene.frame_set(frame + 1)
    frame_path = os.path.join(anim_dir, f"frame_{frame+1:04d}.png")
    scene.render.filepath = frame_path
    bpy.ops.render.render(write_still=True)
    print(f"[JARVIS] Frame {frame+1}/10")

# Export STL
stl_path = os.path.join(OUTPUT_DIR, "turbine_model.stl")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_mesh.stl(filepath=stl_path, use_selection=True)
print(f"[JARVIS] STL: {stl_path}")

elapsed = time.time() - start
print(f"[JARVIS] === BLENDER PIPELINE COMPLETE in {elapsed:.1f}s ===")
