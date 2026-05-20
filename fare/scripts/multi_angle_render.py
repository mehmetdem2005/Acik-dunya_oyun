"""
Comprehensive multi-angle render: 16-angle orbit + close-ups + pose tests +
overlay views. Designed to give expert agents enough visual data to evaluate
the rig from every perspective.

Usage:
    blender --background --python fare/scripts/multi_angle_render.py

Outputs (in fare/out/previews/):
  - orbit_NN.png      (16 angles, 22.5° apart, mesh + skeleton overlay)
  - skel_orbit_NN.png (same 16 angles, skeleton ONLY)
  - mesh_orbit_NN.png (same 16 angles, mesh ONLY)
  - close_*.png       (head, paws, tail, ear close-ups)
  - skel_close_*.png  (same close-ups, skeleton only)
  - pose_*.png        (rest + 8 test poses)
"""

import bpy
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
OUT = os.path.join(ROOT, "out", "previews")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, SCRIPTS_DIR)
import rig_mouse_v3 as rig_module
import rig_mouse as rig_constraints


def log(m): print(f"[multi] {m}", flush=True)


# ============================================================================
# Setup
# ============================================================================
def setup_render(res=1024):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 0.75)
    sc.render.film_transparent = False
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.display.shading.show_object_outline = True
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)


def add_camera(name, loc, look_at, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new(f"{name}_tgt", None); tgt.location = look_at
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam


def build_rig():
    log("Building v3 rig in-session (no GLB roundtrip)")
    rig_module.reset_scene()
    rig_module.import_glb(rig_module.SRC)
    mesh = rig_module.cleanup_and_merge()
    A = rig_module.Anatomy(mesh)
    arm, bones_meta, limb_data, tn, tc = rig_module.build_armature(A)
    class S: pass
    s = S()
    s.head_dir = A.head_dir; s.x_center = A.x_center
    s.y_size = A.y_size; s.z_size = A.z_size; s.x_half = A.x_half
    s.z_spine = A.p_hips.z; s.y_hips = A.p_hips.y; s.y_tail_tip = A.p_tail_tip.y
    rig_constraints.setup_constraints(arm, limb_data, tn, tc, s)
    rig_constraints.organize_collections(arm, bones_meta)
    rig_constraints.parent_with_auto_weights(mesh, arm)
    rig_constraints.smooth_weights(mesh, iterations=2)
    rig_constraints.clamp_normalize(mesh, max_inf=4)
    rig_constraints.ensure_all_weighted(mesh, arm)
    return arm, mesh, A


# ============================================================================
# Bone visualizer (LARGER + colored per category)
# ============================================================================
def category_for_bone(name):
    if name.startswith("CTRL-foot") or name.startswith("CTRL-pole"): return "ctrl_ik"
    if name.startswith("CTRL"):
        if any(k in name for k in ("ear", "eye", "jaw", "head", "cheek", "nose", "brow", "eyelid")):
            return "ctrl_face"
        return "ctrl_main"
    if name.startswith("MCH"): return "mch"
    if name.startswith("DEF"):
        n = name
        if "rib" in n:    return "rib"
        if "tail" in n:   return "tail"
        if "ear" in n:    return "ear"
        if "head" in n or "neck" in n or "jaw" in n or "nose" in n or "cheek" in n or "brow" in n or "eye" in n or "tongue" in n:
            return "head_face"
        if "whisker" in n: return "whisker"
        if "spine" in n or "hips" in n or "chest" in n or "belly" in n: return "spine"
        if "shoulder" in n or "arm" in n or "forearm" in n or "paw_F" in n or "toe_F" in n: return "limb_F"
        if "thigh" in n or "shin" in n or "ankle" in n or "paw_B" in n or "toe_B" in n: return "limb_B"
        return "def"
    return "other"


CATEGORY_COLOR = {
    "def":        (0.85, 0.30, 0.30, 1.0),
    "ctrl_main":  (0.95, 0.85, 0.15, 1.0),  # yellow
    "ctrl_ik":    (0.20, 0.55, 1.00, 1.0),  # blue
    "ctrl_face":  (0.30, 0.90, 0.45, 1.0),  # green
    "mch":        (0.55, 0.55, 0.55, 1.0),  # grey
    "spine":      (1.00, 0.55, 0.20, 1.0),  # orange — main spine
    "rib":        (0.95, 0.20, 0.95, 1.0),  # magenta — ribs (very visible!)
    "tail":       (0.95, 0.45, 0.15, 1.0),  # orange-red
    "ear":        (0.20, 0.90, 0.90, 1.0),  # cyan
    "head_face":  (0.95, 0.95, 0.55, 1.0),  # pale yellow
    "whisker":    (1.00, 1.00, 1.00, 1.0),  # white
    "limb_F":     (0.50, 0.30, 0.95, 1.0),  # purple
    "limb_B":     (0.30, 0.70, 0.30, 1.0),  # green
    "other":      (1.0, 1.0, 1.0, 1.0),
}


def ensure_material(name, rgba):
    m = bpy.data.materials.get(name)
    if m is None: m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = rgba
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        try: bsdf.inputs["Roughness"].default_value = 0.4
        except KeyError: pass
    return m


def make_cylinder(name, head, tail, radius, material):
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


def make_sphere(name, pos, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=pos,
                                          segments=12, ring_count=8)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def visualize_bones(arm, radius_scale=1.6):
    """LARGER bone visualizers for clear visibility."""
    log("Building enlarged bone visualizers")
    mw = arm.matrix_world
    mats = {cat: ensure_material(f"BoneMat_{cat}", rgba)
            for cat, rgba in CATEGORY_COLOR.items()}
    objs = []
    for b in arm.data.bones:
        cat = category_for_bone(b.name)
        head_w = mw @ b.head_local
        tail_w = mw @ b.tail_local
        length = (tail_w - head_w).length
        r_mul = {
            "ctrl_main": 1.5, "ctrl_ik": 1.4, "ctrl_face": 1.2,
            "mch": 0.6,
            "spine": 1.5, "rib": 1.0, "tail": 1.2,
            "ear": 1.0, "head_face": 1.0, "whisker": 0.5,
            "limb_F": 1.2, "limb_B": 1.2,
        }.get(cat, 1.0)
        radius = max(length * 0.06, 0.006) * r_mul * radius_scale
        c = make_cylinder(f"VIS_{b.name}", head_w, tail_w, radius, mats[cat])
        if c: objs.append(c)
        s = make_sphere(f"VISJ_{b.name}", head_w, radius * 1.4, mats[cat])
        objs.append(s)
    log(f"  {len(objs)} visualizer objects")
    return objs


# ============================================================================
# Camera placement
# ============================================================================
def aabb_world(mesh):
    mw = mesh.matrix_world
    xs=[];ys=[];zs=[]
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    return ((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2,
            max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)))


def orbit_cameras(center, size, count=16, elevation=15):
    """Place `count` cameras in a horizontal orbit around `center`.
    elevation: degrees above the horizon."""
    cx, cy, cz = center
    d = size * 1.4
    el_rad = math.radians(elevation)
    cams = []
    for i in range(count):
        theta = (i / count) * 2 * math.pi
        x = cx + d * math.cos(theta) * math.cos(el_rad)
        y = cy + d * math.sin(theta) * math.cos(el_rad)
        z = cz + d * math.sin(el_rad)
        cam = add_camera(f"Cam_orbit_{i:02d}", (x, y, z), (cx, cy, cz + size*0.05))
        cams.append(cam)
    return cams


def render_to(name, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.context.view_layer.update()
    bpy.context.evaluated_depsgraph_get().update()
    bpy.ops.render.render(write_still=True)
    log(f"  → {name}.png")


# ============================================================================
# Pose application for tests
# ============================================================================
def apply_pose(arm, rotations, translations=None):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    for name, rot in rotations.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            log(f"  WARN: bone '{name}' missing"); continue
        pb.rotation_euler = rot
    if translations:
        for name, tr in translations.items():
            pb = arm.pose.bones.get(name)
            if pb is None: continue
            pb.location = tr
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()


# ============================================================================
# Main
# ============================================================================
def main():
    arm, mesh, A = build_rig()
    setup_render(res=1024)

    cx, cy, cz, size = aabb_world(mesh)
    center = (cx, cy, cz)
    log(f"AABB center: {center}, size: {size:.2f}")

    # 16-angle orbit cameras
    orbit_cams = orbit_cameras(center, size, count=16, elevation=15)

    # ----- PASS 1: mesh only, 16-angle orbit -----
    log("PASS 1: mesh-only 16-angle orbit")
    for i, cam in enumerate(orbit_cams):
        render_to(f"mesh_orbit_{i:02d}", cam)

    # Build bone visualizers (LARGER, color-coded by anatomy)
    bone_viz = visualize_bones(arm, radius_scale=1.8)

    # ----- PASS 2: mesh + bones overlay (skeleton on top of mesh) -----
    log("PASS 2: mesh + bones overlay")
    for i, cam in enumerate(orbit_cams):
        render_to(f"overlay_orbit_{i:02d}", cam)

    # ----- PASS 3: skeleton only (mesh removed) -----
    log("PASS 3: skeleton-only orbit (mesh removed)")
    bpy.data.objects.remove(mesh, do_unlink=True)
    for i, cam in enumerate(orbit_cams):
        render_to(f"skel_orbit_{i:02d}", cam)

    log("DONE")


if __name__ == "__main__":
    main()
