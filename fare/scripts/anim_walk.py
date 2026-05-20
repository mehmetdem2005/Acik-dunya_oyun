"""
v14 walk cycle — 24-frame quadruped walk animation.

4-beat walk gait:
  FL swing: frame 0-6     (BL stance during this)
  BL swing: frame 6-12    (FR stance)
  FR swing: frame 12-18   (BR stance)
  BR swing: frame 18-24
  Diagonal pairs alternate; 3 feet always on ground.

Animates:
  - Each leg's upper+lower bone rotation X (FK swing)
  - hips rotation Z (subtle 2deg side-to-side sway)
  - spine_02 rotation Z (counter-sway)
  - chest scale_y via breath driver (breathing during walk)
  - tail_01..tail_06 rotation Z (passive sway following hips)
  - head rotation Z (slight counter-sway to hips for balance)

Exports GLB at fare/out/mouse_walk.glb with embedded animation.

Usage:
    blender --background --python fare/scripts/anim_walk.py
"""

import bpy
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_BLEND = os.path.join(ROOT, "out", "mouse_v14.blend")
OUT_BLEND = os.path.join(ROOT, "out", "mouse_walk.blend")
OUT_GLB = os.path.join(ROOT, "out", "mouse_walk.glb")


def log(m): print(f"[walk] {m}", flush=True)


def main():
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    log(f"Opened {IN_BLEND}")

    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
    log(f"Rig: {arm.name}, {len(arm.data.bones)} bones")

    # Remove existing IK constraints from paws — they conflict with FK keyframes
    # for the leg chain. We do pure FK walk; IK is for retargeting later.
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm.pose.bones
    for n in ("front_paw_L", "front_paw_R", "back_paw_L", "back_paw_R"):
        if n in pb:
            for c in list(pb[n].constraints):
                if c.type == 'IK':
                    pb[n].constraints.remove(c)
    log("Removed IK constraints (using FK for walk)")

    # Scene timeline
    sc = bpy.context.scene
    sc.frame_start = 1
    sc.frame_end = 24
    sc.render.fps = 24

    FRAMES = 24

    def deg(x): return math.radians(x)

    def kf(bone_name, frame, rot_xyz=None, loc_xyz=None, scale_xyz=None):
        b = pb.get(bone_name)
        if not b: return
        b.rotation_mode = 'XYZ'
        if rot_xyz is not None:
            b.rotation_euler = (deg(rot_xyz[0]), deg(rot_xyz[1]), deg(rot_xyz[2]))
            b.keyframe_insert("rotation_euler", frame=frame)
        if loc_xyz is not None:
            b.location = Vector(loc_xyz)
            b.keyframe_insert("location", frame=frame)
        if scale_xyz is not None:
            b.scale = Vector(scale_xyz)
            b.keyframe_insert("scale", frame=frame)

    # ===== Walk cycle =====
    # Each leg swing window (6 frames). Stance covers the other 18 frames.
    # Phase offsets so 3 feet on ground at any time.
    # Standard quadruped walk gait offsets:
    #   FL: swing at frames 1-7
    #   BL: swing at frames 7-13
    #   FR: swing at frames 13-19
    #   BR: swing at frames 19-25(=1)
    # Reset values across frames to prevent jumpiness:
    # We define key poses at swing start, mid (lift apex), end, and stance mid.

    def animate_leg(upper_bone, lower_bone, swing_start, swing_end,
                     swing_axis_upper=+1, knee_axis=+1, stance_amp_deg=20,
                     swing_lift_deg=25, knee_bend_deg=35):
        """
        Animate one leg with 4 key poses:
          swing_start: foot lifted-back  (upper rotated back, knee bent)
          mid: foot at lift apex         (upper neutral, knee max bent)
          swing_end: foot planted-forward (upper rotated forward, knee straight)
          stance_mid: foot still planted (upper rotated back as body moves over it)

        swing_axis_upper: +1 or -1 — direction of swing in upper X rotation
        knee_axis: +1 or -1 — knee bend direction
        """
        mid = (swing_start + swing_end) // 2
        # Stance fills the rest of the 24-frame cycle from swing_end back to swing_start (next cycle)
        stance_mid = ((swing_end + (swing_start + FRAMES)) // 2) % FRAMES
        if stance_mid == 0: stance_mid = FRAMES

        # Swing start: foot just lifted, behind body
        kf(upper_bone, swing_start, rot_xyz=(swing_axis_upper * -stance_amp_deg, 0, 0))
        kf(lower_bone, swing_start, rot_xyz=(knee_axis * knee_bend_deg * 0.4, 0, 0))
        # Mid swing: foot at apex, knee max bent
        kf(upper_bone, mid, rot_xyz=(0, 0, 0))
        kf(lower_bone, mid, rot_xyz=(knee_axis * knee_bend_deg, 0, 0))
        # Swing end / plant: foot forward, knee straightening
        kf(upper_bone, swing_end, rot_xyz=(swing_axis_upper * +stance_amp_deg, 0, 0))
        kf(lower_bone, swing_end, rot_xyz=(knee_axis * knee_bend_deg * 0.15, 0, 0))
        # Stance mid: foot stays planted; upper rotates from forward to back as body moves
        kf(upper_bone, stance_mid, rot_xyz=(0, 0, 0))
        kf(lower_bone, stance_mid, rot_xyz=(knee_axis * knee_bend_deg * 0.05, 0, 0))

    # Phase windows (1-indexed-ish but Blender frames work fine starting 1)
    # FL leg: front-left
    animate_leg("upper_arm_L", "forearm_L", swing_start=1,  swing_end=7,
                 swing_axis_upper=+1, knee_axis=+1, stance_amp_deg=18, knee_bend_deg=40)
    # BL: back-left
    animate_leg("thigh_L", "shin_L", swing_start=7, swing_end=13,
                 swing_axis_upper=+1, knee_axis=-1, stance_amp_deg=20, knee_bend_deg=45)
    # FR: front-right
    animate_leg("upper_arm_R", "forearm_R", swing_start=13, swing_end=19,
                 swing_axis_upper=+1, knee_axis=+1, stance_amp_deg=18, knee_bend_deg=40)
    # BR: back-right
    animate_leg("thigh_R", "shin_R", swing_start=19, swing_end=25,
                 swing_axis_upper=+1, knee_axis=-1, stance_amp_deg=20, knee_bend_deg=45)

    # ===== Body sway =====
    # Hips Z rotation: subtle 2-3 deg side-to-side (twice per cycle)
    for f, ry in [(1, 0), (7, +3), (13, 0), (19, -3), (25, 0)]:
        kf("hips", f, rot_xyz=(0, ry, 0))
    # Spine counter-sway (chest)
    for f, ry in [(1, 0), (7, -1.5), (13, 0), (19, +1.5), (25, 0)]:
        kf("chest", f, rot_xyz=(0, ry, 0))
    # Head subtle bob (counter-balance) — Z rotation small
    for f, rz in [(1, 0), (7, +1), (13, 0), (19, -1), (25, 0)]:
        kf("head", f, rot_xyz=(0, 0, rz))

    # ===== Tail sway (lazy follow) =====
    # Tail Z rotation cascading delay
    for i, base in enumerate(["tail_01", "tail_03", "tail_05", "tail_07"]):
        delay = i * 2  # propagate down chain
        for f, rz in [(1 + delay, +5), (7 + delay, -5), (13 + delay, +5),
                       (19 + delay, -5), (25 + delay, +5)]:
            f_mod = ((f - 1) % FRAMES) + 1
            kf(base, f_mod, rot_xyz=(0, 0, rz))

    # ===== Breathing during walk =====
    # Subtle breath cycle — half-speed of walk
    arm["breath"] = 0.0
    arm.id_properties_ui("breath").update(min=-1.0, max=1.0, default=0.0)
    arm.keyframe_insert(data_path='["breath"]', frame=1)
    arm["breath"] = 0.6
    arm.keyframe_insert(data_path='["breath"]', frame=12)
    arm["breath"] = 0.0
    arm.keyframe_insert(data_path='["breath"]', frame=24)

    # ===== Ear small idle perk =====
    for side, sign in (("L", +1), ("R", -1)):
        bn = f"ear_{side}_base"
        for f, rx in [(1, 0), (12, sign * 4), (24, 0)]:
            kf(bn, f, rot_xyz=(rx, 0, 0))

    # ===== Whisker idle twitch =====
    # Random tiny rotations on each whisker
    import random
    random.seed(0)
    for side in ("L", "R"):
        for i in range(1, 5):
            bn = f"whisker_{side}_{i}"
            for f in (1, 6, 13, 18, 24):
                kf(bn, f, rot_xyz=(random.uniform(-3, 3),
                                    random.uniform(-3, 3),
                                    random.uniform(-3, 3)))

    # Set interpolation to BEZIER for smooth motion
    if arm.animation_data and arm.animation_data.action:
        for fc in arm.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'

    # Make the action loop (cyclic) — name + use_cyclic on the action
    if arm.animation_data and arm.animation_data.action:
        act = arm.animation_data.action
        act.name = "Walk"
        # Add Cycles modifier to each fcurve for true looping
        for fc in act.fcurves:
            # Replace if exists
            for m in list(fc.modifiers):
                fc.modifiers.remove(m)
            mod = fc.modifiers.new('CYCLES')
            mod.mode_before = 'REPEAT'
            mod.mode_after = 'REPEAT'

    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved blend: {OUT_BLEND}")

    # Export GLB with animation
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    try:
        bpy.ops.export_scene.gltf(
            filepath=OUT_GLB, export_format='GLB',
            use_selection=True,
            export_skins=True,
            export_animations=True,
            export_animation_mode='ACTIONS',
            export_force_sampling=True,
            export_frame_range=False,
            export_yup=True,
        )
        log(f"Saved GLB with animation: {OUT_GLB}")
    except Exception as e:
        log(f"GLB export FAILED: {e}")

    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
