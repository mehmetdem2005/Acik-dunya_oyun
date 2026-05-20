"""
Pose test: build the rig, apply several test poses, render the mesh deformation.
This is the "real" test of whether the rig actually works — does the mesh
deform correctly when bones are rotated?

Usage:
    blender --background --python fare/scripts/pose_test.py

Output: fare/out/previews/pose_*.png   (rest, head_down, tail_up, etc.)
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
import rig_mouse_v4 as rig_module
import rig_mouse as rig1


def log(m): print(f"[pose] {m}", flush=True)


def setup_render(res=1280):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 0.75)
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.display.shading.show_object_outline = True
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)


def add_camera(name, loc, look_at, lens=50):
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
    c.up_axis = 'UP_Y'
    return cam


def build_rig():
    rig_module.reset_scene()
    rig_module.import_glb(rig_module.SRC)
    mesh = rig_module.cleanup_and_merge()
    A = rig_module.Anatomy(mesh)
    arm, bones_meta, limb_data, tail_names, tail_ctrl_names = rig_module.build_armature(A)
    class S: pass
    s = S()
    s.head_dir = A.head_dir; s.x_center = A.x_center
    s.y_size = A.y_size; s.z_size = A.z_size; s.x_half = A.x_half
    s.z_spine = A.p_hips.z; s.y_hips = A.p_hips.y; s.y_tail_tip = A.p_tail_tip.y
    # Fields needed by manual_weight_overrides
    s.x_min = A.x_min; s.x_max = A.x_max
    s.y_min = A.y_min; s.y_max = A.y_max
    s.z_min = A.z_min; s.z_max = A.z_max
    s.verts = A.verts; s.mesh = A.mesh
    s.y_head = A.skull_center.y; s.y_nose = A.nose_tip.y
    s.y_neck = A.p_neck.y; s.y_jaw = A.p_jaw.y
    s.z_eyes = A.skull_center.z; s.z_head = A.skull_center.z
    s.z_floor = A.z_floor; s.z_belly = A.z_belly
    rig1.setup_constraints(arm, limb_data, tail_names, tail_ctrl_names, s)
    rig1.organize_collections(arm, bones_meta)
    rig1.parent_with_auto_weights(mesh, arm)
    rig1.manual_weight_overrides(mesh, s)  # v4 fix: enabled
    rig1.smooth_weights(mesh, iterations=1)  # was 2 — agent said over-blurs
    rig1.clamp_normalize(mesh, max_inf=4)
    rig1.ensure_all_weighted(mesh, arm)
    return arm, mesh, A


def apply_pose(arm, bone_rotations):
    """bone_rotations: dict bone_name → (euler_x, euler_y, euler_z) in radians."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    for name, (rx, ry, rz) in bone_rotations.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            log(f"  WARN: bone '{name}' not found")
            continue
        pb.rotation_euler = (rx, ry, rz)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Force depsgraph update
    bpy.context.view_layer.update()


def render_pose(name, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT, f"pose_{name}.png")
    # Force depsgraph + scene frame refresh BEFORE render
    bpy.context.view_layer.update()
    sc.frame_set(sc.frame_current)
    bpy.context.evaluated_depsgraph_get().update()
    bpy.ops.render.render(write_still=True)
    log(f"  → pose_{name}.png")


def main():
    arm, mesh, A = build_rig()
    setup_render(res=1280)

    # AABB-based camera
    xs=[];ys=[];zs=[]
    mw = mesh.matrix_world
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx = (min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))

    cam = add_camera("Cam_persp",
                      (cx + size*0.9, cy + size*0.9, cz + size*0.55),
                      (cx, cy, cz + size*0.10))

    poses = {
        "01_rest":          {},
        "02_head_up":       {"CTRL-head":   (math.radians(-90), 0, 0)},
        "03_tail_up":       {f"CTRL-tail_{i}": (math.radians(-45), 0, 0) for i in (1, 2, 3)},
        "04_hip_twist":     {"CTRL-hips":   (0, 0, math.radians(45))},
        "05_chest_bend":    {"CTRL-chest":  (math.radians(50), 0, 0)},
        "06_ears_up":       {"CTRL-ear.L":  (math.radians(-80), 0, 0),
                             "CTRL-ear.R": (math.radians(-80), 0, 0)},
        "07_jaw_open":      {"CTRL-jaw":    (math.radians(60), 0, 0)},
        "08_paw_lift":      {"CTRL-foot_F.L": (0, 0, 0)},
        # New v4 tests
        "09_muzzle_flex":   {"CTRL-muzzle": (math.radians(-30), 0, 0)},
        "10_nose_twitch":   {"CTRL-nose_tip": (math.radians(-30), math.radians(15), 0)},
        "11_lips_pucker":   {"CTRL-lip_upper": (math.radians(-25), 0, 0),
                              "CTRL-lip_lower": (math.radians(25), 0, 0)},
        "12_cheek_smile":   {"CTRL-cheek.L": (0, 0, math.radians(20)),
                              "CTRL-cheek.R": (0, 0, math.radians(-20))},
        "13_blink":         {"CTRL-eyelid_upper.L": (math.radians(45), 0, 0),
                              "CTRL-eyelid_upper.R": (math.radians(45), 0, 0)},
        "14_brow_raise":    {"CTRL-brow.L": (math.radians(-25), 0, 0),
                              "CTRL-brow.R": (math.radians(-25), 0, 0)},
    }

    for name, rots in poses.items():
        apply_pose(arm, rots)
        # Special: for 08_paw_lift, additionally translate the IK foot ctrl
        if name == "08_paw_lift":
            bpy.context.view_layer.objects.active = arm
            bpy.ops.object.mode_set(mode='POSE')
            pb = arm.pose.bones.get("CTRL-foot_F.L")
            if pb:
                pb.location = (0, 0, 0.10)  # lift Z by 10cm in bone-local space
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.context.view_layer.update()
        render_pose(name, cam)

    log("DONE")


if __name__ == "__main__":
    main()
