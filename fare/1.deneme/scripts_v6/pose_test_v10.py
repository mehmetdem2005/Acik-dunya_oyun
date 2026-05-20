"""
Stage 3 v10 pose test — verify rig CONSTRAINTS actually work:
  - Setting jaw_open property → jaw rotates → mesh deforms (after auto-weights)
  - Translating IK foot ctrl → leg chain follows
  - Translating Spline IK tail ctrls → tail curves
  - Setting breath → ribcage expands
  - Translating eye_aim → eyes track

Renders pose comparisons for visual proof the rig WORKS.

Usage:
    blender --background --python fare/scripts/pose_test_v10.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "out", "pose_test_v10")
os.makedirs(OUT_DIR, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import rig_mouse_v10 as v10


def log(m): print(f"[pose10] {m}", flush=True)


def build():
    v10.reset_scene()
    v10.import_glb(v10.SRC)
    tripo = v10.extract_tripo_skeleton()
    mesh = v10.cleanup_keep_mesh_only()
    arm, meta = v10.build_rig(tripo, mesh)
    v10.setup_pose_rigging(arm, meta, tripo, mesh)
    # For the pose test, weld the duplicate seam vertices that Tripo's GLB
    # exporter creates between sub-meshes. This is a Tripo export ARTIFACT
    # (not artistic mesh data) and welding restores skinning continuity.
    log("Welding Tripo seam duplicates (skinning prep — not artistic edit)")
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"  Post-weld: {len(mesh.data.vertices)} verts")

    # Auto-skin
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    for b in arm.data.bones:
        m = meta.get(b.name, {})
        b.use_deform = (m.get("role") == "DEF")
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    return arm, mesh


def setup_render(res=1024):
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
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new(f"{name}_tgt", None); tgt.location = look_at
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam


def render_to(name, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT_DIR, f"{name}.png")
    sc.frame_set(sc.frame_current)
    bpy.context.view_layer.update()
    bpy.context.evaluated_depsgraph_get().update()
    bpy.ops.render.render(write_still=True)


def apply_pose(arm, prop_values=None, rotations=None, translations=None):
    """Reset rig + apply property changes / bone rotations / bone translations."""
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    # Reset all bones
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    # Reset custom properties
    for k in ("breath", "jaw_open", "nose_twitch_L", "nose_twitch_R",
              "ear_L_perk", "ear_R_perk"):
        arm[k] = 0.0
    # Apply property changes
    if prop_values:
        for k, v in prop_values.items():
            arm[k] = v
    # Apply rotations
    if rotations:
        for name, rot in rotations.items():
            pb = arm.pose.bones.get(name)
            if pb is None:
                log(f"  WARN: missing bone {name}"); continue
            pb.rotation_euler = rot
    # Apply translations
    if translations:
        for name, tr in translations.items():
            pb = arm.pose.bones.get(name)
            if pb is None:
                log(f"  WARN: missing bone {name}"); continue
            pb.location = tr
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.update_tag()
    bpy.context.view_layer.update()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    bpy.context.evaluated_depsgraph_get().update()


def main():
    arm, mesh = build()
    log(f"Rig: {len(arm.data.bones)} bones built + constrained")

    setup_render(res=1024)
    # AABB camera
    mw = mesh.matrix_world
    xs=[]; ys=[]; zs=[]
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2; cz = (min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))

    # Persp camera (3/4 view)
    cam = add_camera("Cam_persp", (cx + size*0.9, cy - size*0.9, cz + size*0.4),
                      (cx, cy, cz + size*0.05))

    # Pose set — each tests a DIFFERENT constraint/driver
    poses = [
        # (name, props, rotations, translations)
        ("00_rest",            {}, {}, {}),
        # ---- Drivers ----
        ("01_jaw_open",        {"jaw_open": 0.7}, {}, {}),
        ("02_breath_in",       {"breath": 1.0}, {}, {}),
        ("03_ear_L_perk",      {"ear_L_perk": 1.0}, {}, {}),
        ("04_ear_R_perk",      {"ear_R_perk": 1.0}, {}, {}),
        ("05_nose_twitch_L",   {"nose_twitch_L": 1.0}, {}, {}),
        # ---- FK mirror ----
        ("06_CTRL_head_tilt",  {}, {"CTRL_head": (math.radians(-30), 0, 0)}, {}),
        ("07_CTRL_pelvis_twist", {}, {"CTRL_pelvis": (0, 0, math.radians(30))}, {}),
        # ---- IK on legs ----
        ("08_front_paw_L_lift", {}, {}, {"CTRL_front_paw_IK_L": (0, 0, 0.08)}),
        ("09_back_paw_L_lift",  {}, {}, {"CTRL_back_paw_IK_L":  (0, 0, 0.08)}),
        # ---- Spline IK on tail ----
        ("10_tail_curl",        {}, {}, {"CTRL_tail_tip": (0, 0, 0.10)}),
        # ---- Eye look-at ----
        ("11_eye_look_up",      {}, {}, {"CTRL_eye_aim": (0, 0, 0.05)}),
        ("12_eye_look_left",    {}, {}, {"CTRL_eye_aim": (0.05, 0, 0)}),
        # ---- Combined: scurry pose (multi-bone choreography) ----
        ("13_scurry_pose",      {"breath": 0.5},
                                {"CTRL_head": (math.radians(-45), 0, math.radians(15)),
                                 "CTRL_pelvis": (0, math.radians(15), 0),
                                 "CTRL_tail_mid": (math.radians(-30), 0, math.radians(20))},
                                {"CTRL_front_paw_IK_L": (0, 0, 0.05),
                                 "CTRL_back_paw_IK_R": (0, 0, 0.04)}),
        # ---- Combined: sniff/curious pose ----
        ("14_sniff_pose",       {"jaw_open": 0.3, "nose_twitch_L": 0.8, "nose_twitch_R": 0.8,
                                 "ear_L_perk": 0.7, "ear_R_perk": 0.7},
                                {"CTRL_head": (math.radians(-40), 0, 0)}, {}),
        # ---- Spine curl (use bbones via spine CTRL bones) ----
        ("15_spine_C_curl",     {},
                                {"CTRL_pelvis": (0, 0, math.radians(20)),
                                 "CTRL_chest": (0, 0, math.radians(-20)),
                                 "CTRL_head": (0, 0, math.radians(25))}, {}),
    ]

    log("Rendering pose test sheet")
    for name, props, rots, trs in poses:
        apply_pose(arm, props, rots, trs)
        render_to(name, cam)
        log(f"  → {name}.png")

    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
