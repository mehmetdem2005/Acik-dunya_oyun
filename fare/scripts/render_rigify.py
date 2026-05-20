"""Render Rigify rig over mouse mesh — visual proof."""

import bpy, sys, os, math
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(ROOT, "out", "mouse_rigify.blend")
OUT = os.path.join(ROOT, "out", "qa_rigify")
os.makedirs(OUT, exist_ok=True)

def log(m): print(f"[render] {m}", flush=True)

# Open the saved blend
bpy.ops.wm.open_mainfile(filepath=BLEND)
log(f"Opened: {BLEND}")

# Find mesh and rig
mesh = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
# After rigify generate, both metarig and rig exist. Use the generated "rig"
rig = bpy.data.objects.get("rig") or bpy.data.objects.get("RIG-MouseMetarig")
metarig = bpy.data.objects.get("MouseMetarig")
log(f"Mesh: {mesh.name if mesh else None}")
log(f"Generated rig: {rig.name if rig else None}")
log(f"Metarig: {metarig.name if metarig else None}")

# Hide metarig for cleaner render (we want to see only the generated rig)
if metarig:
    metarig.hide_viewport = True
    metarig.hide_render = True

# Setup render
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = 1280
sc.render.resolution_y = 960
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_cavity = True
sc.display.shading.show_object_outline = True
sc.display.shading.show_xray = True
sc.display.shading.xray_alpha = 0.35
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)

# Workbench engine doesn't render armature widgets. Convert bones to cylinders.
def make_mat(name, rgba):
    m = bpy.data.materials.get(name)
    if m is None: m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = rgba
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        try: bsdf.inputs["Roughness"].default_value = 0.3
        except KeyError: pass
    return m

REF_COLOR = {
    "spine":  (0.95, 0.85, 0.15, 1.0),   # yellow torso
    "front":  (0.55, 0.35, 0.85, 1.0),   # purple front legs
    "back":   (0.20, 0.85, 0.30, 1.0),   # green back legs
    "tail":   (0.95, 0.55, 0.15, 1.0),   # orange tail
    "face":   (0.15, 0.85, 0.90, 1.0),   # cyan face/ears
    "other":  (0.65, 0.65, 0.65, 1.0),
}

def categorize_rigify(name):
    n = name.lower()
    if "tail" in n or "spine.00" in n[:9]:
        # spine.001-005 in wolf metarig are tail
        if "spine.001" in n or "spine.002" in n or "spine.003" in n or "spine.004" in n or "spine.005" in n:
            return "tail"
    if "shoulder" in n or "f_arm" in n or "front_thigh" in n or "front_shin" in n \
       or "front_foot" in n or "front_toe" in n or "f_palm" in n or "front_paw" in n:
        return "front"
    if "thigh" in n or "shin" in n or "foot" in n or "toe" in n or "r_palm" in n \
       or "pelvis" in n or "hip" in n or "back_paw" in n:
        return "back"
    if "face" in n or "nose" in n or "jaw" in n or "chin" in n or "lip" in n or "ear" in n \
       or "brow" in n or "lid" in n or "forehead" in n or "temple" in n or "cheek" in n \
       or "head" in n or "skull" in n:
        return "face"
    if "spine" in n or "chest" in n or "neck" in n or "rib" in n or "belly" in n \
       or "torso" in n or "back" in n:
        return "spine"
    return "other"

# Only visualize DEF- bones (rigify generated ones) for clarity
if rig:
    mats = {cat: make_mat(f"refmat_{cat}", rgba) for cat, rgba in REF_COLOR.items()}
    mwarm = rig.matrix_world
    n_drawn = 0
    for b in rig.data.bones:
        # Show only DEF bones (deform skeleton)
        if not b.name.startswith("DEF-"): continue
        cat = categorize_rigify(b.name)
        h = mwarm @ b.head_local
        t = mwarm @ b.tail_local
        length = (t - h).length
        if length < 1e-5: continue
        radius = max(length * 0.06, 0.003)
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius,
                                             depth=length, location=(0,0,0))
        obj = bpy.context.object
        obj.name = f"VIS_{b.name}"
        direction = (t - h).normalized()
        rq = Vector((0, 0, 1)).rotation_difference(direction)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = rq
        obj.location = h + (t - h) * 0.5
        obj.data.materials.append(mats[cat])
        n_drawn += 1
    log(f"Visualized {n_drawn} DEF bones as cylinders")

# AABB camera
mw = mesh.matrix_world
xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    wp = mw @ v.co
    xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
d = size * 1.3

def add_cam(name, loc, look_at, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new(f"{name}_tgt", None); tgt.location = look_at
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam

cams = {
    "side":  add_cam("c_side",  (cx + d, cy, cz + size*0.05), (cx, cy, cz)),
    "front": add_cam("c_front", (cx, cy - d, cz + size*0.05), (cx, cy, cz)),
    "top":   add_cam("c_top",   (cx, cy, cz + d * 0.7), (cx, cy, cz), lens=45),
    "back":  add_cam("c_back",  (cx, cy + d, cz + size*0.05), (cx, cy, cz)),
    "persp": add_cam("c_persp", (cx + d*0.7, cy - d*0.7, cz + size*0.4), (cx, cy, cz)),
}

for name, cam in cams.items():
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, f"rigify_{name}.png")
    bpy.ops.render.render(write_still=True)
    log(f"  → rigify_{name}.png")

log("DONE")
