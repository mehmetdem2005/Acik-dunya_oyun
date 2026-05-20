"""Render v14 mouse rig — visual proof."""

import bpy, sys, os
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(ROOT, "out", "mouse_v14.blend")
OUT = os.path.join(ROOT, "out", "qa_v14")
os.makedirs(OUT, exist_ok=True)

def log(m): print(f"[r14] {m}", flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
log(f"Opened: {BLEND}")

mesh = next((o for o in bpy.data.objects if o.type == 'MESH'), None)
rig = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
log(f"Mesh: {mesh.name}; Rig: {rig.name} ({len(rig.data.bones)} bones)")

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = 1280
sc.render.resolution_y = 960
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_cavity = True
sc.display.shading.show_object_outline = True
sc.display.shading.show_xray = True
sc.display.shading.xray_alpha = 0.32
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)

REF_COLOR = {
    "spine":  (0.95, 0.85, 0.15, 1.0),
    "front":  (0.55, 0.35, 0.85, 1.0),
    "back":   (0.20, 0.85, 0.30, 1.0),
    "tail":   (0.95, 0.55, 0.15, 1.0),
    "face":   (0.15, 0.85, 0.90, 1.0),
    "whisker":(0.90, 0.90, 0.95, 1.0),
    "other":  (0.65, 0.65, 0.65, 1.0),
}

def categorize(name):
    n = name.lower()
    if "tail" in n: return "tail"
    if "whisker" in n: return "whisker"
    if n.startswith(("ear_", "eye_", "jaw", "snout", "nose")) or n in ("head", "neck"):
        return "face"
    if "scapula" in n or "upper_arm" in n or "forearm" in n or "front_paw" in n or "finger_f" in n:
        return "front"
    if "hip" in n or "thigh" in n or "shin" in n or "ankle" in n or "back_paw" in n or "finger_b" in n:
        return "back"
    if "root" in n or "hips" in n or "spine" in n or "chest" in n:
        return "spine"
    return "other"

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

mats = {cat: make_mat(f"refmat_{cat}", rgba) for cat, rgba in REF_COLOR.items()}
mw = rig.matrix_world
n_drawn = 0
for b in rig.data.bones:
    cat = categorize(b.name)
    h = mw @ b.head_local; t = mw @ b.tail_local
    length = (t - h).length
    if length < 1e-5: continue
    r_mul = 1.3 if cat in ("front","back","spine","tail") else 1.1
    radius = max(length * 0.07, 0.004) * r_mul
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius,
                                         depth=length, location=(0,0,0))
    obj = bpy.context.object
    obj.name = f"VIS_{b.name}"
    direction = (t - h).normalized()
    rq = Vector((0, 0, 1)).rotation_difference(direction)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rq
    obj.location = h + (t - h) * 0.5
    obj.data.materials.append(mats[cat])
    # joint sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.4, location=h,
                                          segments=10, ring_count=6)
    s = bpy.context.object
    s.name = f"VISJ_{b.name}"
    s.data.materials.append(mats[cat])
    n_drawn += 1
log(f"Visualized {n_drawn} bones as cylinders+spheres")

# Camera AABB
mwm = mesh.matrix_world
xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    wp = mwm @ v.co
    xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
d = size * 1.3
center = (cx, cy, cz)

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
    "side":  add_cam("c_side",  (cx + d, cy, cz + size*0.05), center),
    "side2": add_cam("c_side2", (cx - d, cy, cz + size*0.05), center),
    "front": add_cam("c_front", (cx, cy - d, cz + size*0.05), center),
    "back":  add_cam("c_back",  (cx, cy + d, cz + size*0.05), center),
    "top":   add_cam("c_top",   (cx, cy, cz + d * 0.7), center, lens=45),
    "persp": add_cam("c_persp", (cx + d*0.7, cy - d*0.7, cz + size*0.4), center),
}

for name, cam in cams.items():
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, f"v14_{name}.png")
    bpy.ops.render.render(write_still=True)
    log(f"  → v14_{name}.png")

log("DONE")
