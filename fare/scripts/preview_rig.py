"""
Build the rig from scratch (re-using rig_mouse.py) and render previews in the
same Blender session — avoids GLB export/import roundtrip which mangles armature
transforms.

Usage:
    blender --background --python fare/scripts/preview_rig.py

Output: fare/out/previews/{mesh,skel,combined}_{side,front,top,persp,head,paw}.png
"""

import bpy
import os
import sys
import math
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
OUT = os.path.join(ROOT, "out", "previews")
os.makedirs(OUT, exist_ok=True)

# Make rig_mouse.py importable
sys.path.insert(0, SCRIPTS_DIR)
import rig_mouse  # noqa: E402


def log(m): print(f"[preview] {m}", flush=True)


# ============================================================================
# Rig setup (reuse rig_mouse.py pipeline up to and including weight binding)
# ============================================================================
def build_rig():
    log("Running full rig pipeline (no GLB roundtrip)")
    rig_mouse.reset_scene()
    rig_mouse.import_glb(rig_mouse.SRC)
    mesh_obj = rig_mouse.cleanup_and_merge()
    A = rig_mouse.Anatomy(mesh_obj)
    arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names = rig_mouse.build_armature(A)
    rig_mouse.setup_constraints(arm_obj, limb_data, tail_bone_names, tail_ctrl_names, A)
    rig_mouse.organize_collections(arm_obj, bones_meta)
    # Skip widgets / weight refinement for preview (faster)
    rig_mouse.parent_with_auto_weights(mesh_obj, arm_obj)
    return arm_obj, mesh_obj, A


# ============================================================================
# Render setup
# ============================================================================
def setup_render(res=1280):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 0.75)
    sc.render.film_transparent = False
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.display.shading.cavity_type = 'BOTH'
    sc.display.shading.show_object_outline = True

    # Background
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)


def add_camera(name, loc, look_at, lens=50):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    direction = (Vector(look_at) - Vector(loc)).normalized()
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    return cam


def render_to(name, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    log(f"  → {name}.png")


# ============================================================================
# Bone visualizer (cylinder + sphere meshes)
# ============================================================================
def category_for_bone(name):
    if name.startswith("CTRL-foot") or name.startswith("CTRL-pole"): return "ctrl_ik"
    if name.startswith("CTRL"):
        if any(k in name for k in ("ear", "eye", "jaw", "head")): return "ctrl_face"
        return "ctrl_main"
    if name.startswith("MCH"): return "mch"
    if name.startswith("DEF"): return "def"
    return "other"


CATEGORY_COLOR = {
    "def":       (0.95, 0.35, 0.30, 1.0),  # red — deform bones
    "ctrl_main": (0.95, 0.85, 0.20, 1.0),  # yellow — main FK
    "ctrl_ik":   (0.20, 0.55, 1.00, 1.0),  # blue — IK targets / poles
    "ctrl_face": (0.30, 0.90, 0.45, 1.0),  # green — face
    "mch":       (0.55, 0.55, 0.55, 1.0),  # grey — mechanism
    "other":     (1.00, 1.00, 1.00, 1.0),
}


def ensure_material(name, rgba):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = rgba
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        try: bsdf.inputs["Roughness"].default_value = 0.4
        except KeyError: pass
    return m


def cylinder_from_to(name, head, tail, radius, material):
    direction = tail - head
    length = direction.length
    if length < 1e-5: return None
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius,
                                         depth=length, location=(0,0,0))
    obj = bpy.context.object
    obj.name = name
    rot_quat = Vector((0, 0, 1)).rotation_difference(direction.normalized())
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rot_quat
    obj.location = head + direction * 0.5
    obj.data.materials.append(material)
    return obj


def sphere_at(name, pos, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=pos,
                                          segments=10, ring_count=6)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def visualize_bones(arm):
    log("Building bone visualizer geometry")
    mw = arm.matrix_world
    mats = {cat: ensure_material(f"BoneMat_{cat}", rgba)
            for cat, rgba in CATEGORY_COLOR.items()}
    objs = []
    for b in arm.data.bones:
        cat = category_for_bone(b.name)
        head_w = mw @ b.head_local
        tail_w = mw @ b.tail_local
        length = (tail_w - head_w).length
        r_mul = {"ctrl_main": 1.6, "ctrl_ik": 1.4, "ctrl_face": 1.3,
                 "mch": 0.7, "def": 1.0, "other": 1.0}.get(cat, 1.0)
        radius = max(length * 0.04, 0.003) * r_mul
        c = cylinder_from_to(f"VIS_{b.name}", head_w, tail_w, radius, mats[cat])
        if c: objs.append(c)
        # Joint sphere
        s = sphere_at(f"VISJ_{b.name}", head_w, radius * 1.4, mats[cat])
        objs.append(s)
    log(f"  {len(objs)} visualizer objects")
    return objs


# ============================================================================
# Main
# ============================================================================
def main():
    arm, mesh, A = build_rig()
    setup_render(res=1280)

    # World-space bbox from real mesh data
    xs=[];ys=[];zs=[]
    mw = mesh.matrix_world
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx = (min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    log(f"Mesh AABB X=[{min(xs):.2f},{max(xs):.2f}] Y=[{min(ys):.2f},{max(ys):.2f}] Z=[{min(zs):.2f},{max(zs):.2f}]")
    log(f"Center=({cx:.2f},{cy:.2f},{cz:.2f}) size={size:.2f}")

    center = (cx, cy, cz)
    d = size * 1.4

    cams = {
        "side":   add_camera("Cam_side",   (cx + d, cy, cz + size*0.05), center),
        "front":  add_camera("Cam_front",  (cx, cy + d, cz + size*0.05), center),
        "top":    add_camera("Cam_top",    (cx, cy, cz + d),             center, lens=45),
        "persp":  add_camera("Cam_persp",  (cx + d*0.7, cy + d*0.7, cz + size*0.45), center),
        # Head close-up: aim at actual nose tip (the snout, detected vertex-wise).
        # The model has a "sniffing" pose with the snout lowered toward the ground,
        # so we look at nose_tip directly from 3/4 forward angle.
        "head":   add_camera("Cam_head",
                              (A.nose_tip.x + size*0.35, A.nose_tip.y + size*0.30, A.nose_tip.z + size*0.30),
                              (A.nose_tip.x,             A.nose_tip.y,             A.nose_tip.z), lens=45),
        # Front-left paw close-up: aim at detected front paw
        "paw":    add_camera("Cam_paw",
                              (A.paws["paw_F_L"].x - size*0.30, A.paws["paw_F_L"].y + size*0.30, A.paws["paw_F_L"].z + size*0.30),
                              (A.paws["paw_F_L"].x,             A.paws["paw_F_L"].y,             A.paws["paw_F_L"].z + size*0.05), lens=45),
    }

    # PASS 1: mesh only — final character look
    log("PASS 1: mesh-only (character)")
    for name, cam in cams.items():
        render_to(f"mesh_{name}", cam)

    # Remove mesh from scene (foolproof)
    log("Removing mesh from scene")
    bpy.data.objects.remove(mesh, do_unlink=True)

    # Build skeleton visualizer
    visualize_bones(arm)

    # Hide the actual armature object so its (invisible) bones don't interfere
    # — only the cylinder/sphere visualizers matter for render.
    arm.hide_render = True

    # PASS 2: skeleton only
    log("PASS 2: skeleton-only")
    for name, cam in cams.items():
        render_to(f"skel_{name}", cam)

    log("DONE")


if __name__ == "__main__":
    main()
