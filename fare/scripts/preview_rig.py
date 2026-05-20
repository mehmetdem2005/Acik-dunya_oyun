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

# Make rig_mouse modules importable
sys.path.insert(0, SCRIPTS_DIR)
# v2 has medial-axis bone placement; v1 had AABB-based which broke on curved poses.
import rig_mouse_v2 as rig_module  # noqa: E402
import rig_mouse  # noqa: E402  (still needed for setup_constraints, etc.)


def log(m): print(f"[preview] {m}", flush=True)


# ============================================================================
# Rig setup (reuse rig_mouse.py pipeline up to and including weight binding)
# ============================================================================
def build_rig():
    log("Running v2 rig pipeline (medial-axis, no GLB roundtrip)")
    rig_module.reset_scene()
    rig_module.import_glb(rig_module.SRC)
    mesh_obj = rig_module.cleanup_and_merge()
    A = rig_module.Anatomy(mesh_obj)
    arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names = rig_module.build_armature(A)

    # Shim for setup_constraints (which uses some flat fields)
    class S: pass
    s = S()
    s.head_dir = A.head_dir
    s.x_center = A.x_center
    s.y_size = A.y_size
    s.z_size = A.z_size
    s.x_half = A.x_half
    s.z_spine = A.p_hips.z
    s.y_hips = A.p_hips.y
    s.y_tail_tip = A.p_tail_tip.y
    rig_mouse.setup_constraints(arm_obj, limb_data, tail_bone_names, tail_ctrl_names, s)
    rig_mouse.organize_collections(arm_obj, bones_meta)
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
    """Camera with a TRACK_TO constraint so up_axis stays aligned with world +Z
    (correct for our Z-up scene). to_track_quat with 'Y' interpreted Y as the
    world up, which is wrong when world is Z-up — produces tilted/rolled views.
    """
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    target = bpy.data.objects.new(f"{name}_TGT", None)
    target.location = look_at
    bpy.context.collection.objects.link(target)
    c = cam.constraints.new('TRACK_TO')
    c.target = target
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'  # camera local Y stays aligned with world +Z
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
        # Head close-up: aim at actual nose tip
        "head":   add_camera("Cam_head",
                              (A.nose_tip.x + size*0.35, A.nose_tip.y + size*0.30, A.nose_tip.z + size*0.30),
                              (A.nose_tip.x,             A.nose_tip.y,             A.nose_tip.z), lens=45),
        # Front-left paw close-up
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
