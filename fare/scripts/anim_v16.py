"""
v16 animations — Walk, Run, Idle, Sniff (+ Look) as separate actions.

Foot-lock locomotion via IK targets (CTRL_ik_F/B L/R). Each IK target is a
top-level bone at the armature origin, so pose_bone.matrix.translation is a
world-space position. We keyframe the IK targets along a gait curve:
  - stance: foot planted, slides backward (+Y) as body advances (treadmill)
  - swing : foot lifts (+Z) and swings forward (-Y)
4-beat lateral-sequence walk (Muybridge): BL, FL, BR, FR at phase 0,.25,.5,.75.

All actions exported into one GLB (mouse_anim.glb).

Usage:
    blender --background --python fare/scripts/anim_v16.py
"""

import bpy, os, sys, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as Lib

IN_BLEND = os.path.join(Lib.OUT_DIR, "mouse_v16.blend")
OUT_BLEND = os.path.join(Lib.OUT_DIR, "mouse_anim.blend")
OUT_GLB = os.path.join(Lib.OUT_DIR, "mouse_anim.glb")


def log(m): print(f"[anim] {m}", flush=True)


def deg(x): return math.radians(x)


class Rig:
    def __init__(self, arm):
        self.arm = arm
        self.pb = arm.pose.bones
        # cache rest-world positions of IK target bones
        self.ik_rest = {}
        for n in ("CTRL_ik_FL","CTRL_ik_FR","CTRL_ik_BL","CTRL_ik_BR"):
            if n in self.pb:
                self.ik_rest[n] = (arm.matrix_world @ self.pb[n].bone.matrix_local).translation.copy()

    def key_ik(self, name, world_delta, frame):
        if name not in self.pb: return
        pbone = self.pb[name]
        target = self.ik_rest[name] + world_delta
        m = pbone.matrix.copy(); m.translation = target
        pbone.matrix = m
        bpy.context.view_layer.update()
        pbone.keyframe_insert("location", frame=frame)

    def key_rot(self, name, xyz_deg, frame):
        if name not in self.pb: return
        b = self.pb[name]; b.rotation_mode = 'XYZ'
        b.rotation_euler = (deg(xyz_deg[0]), deg(xyz_deg[1]), deg(xyz_deg[2]))
        b.keyframe_insert("rotation_euler", frame=frame)

    def key_scale(self, name, s, frame):
        if name not in self.pb: return
        b = self.pb[name]; b.scale = s
        b.keyframe_insert("scale", frame=frame)

    def key_prop(self, prop, val, frame):
        self.arm[prop] = val
        self.arm.keyframe_insert(data_path=f'["{prop}"]', frame=frame)

    def reset(self):
        for b in self.pb:
            b.rotation_mode = 'XYZ'
            b.rotation_euler = (0,0,0); b.location = (0,0,0); b.scale = (1,1,1)


def new_action(arm, name):
    if arm.animation_data is None:
        arm.animation_data_create()
    act = bpy.data.actions.new(name)
    arm.animation_data.action = act
    return act


def finalize(arm, cyclic=True):
    act = arm.animation_data.action
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
        if cyclic:
            for m in list(fc.modifiers): fc.modifiers.remove(m)
            mod = fc.modifiers.new('CYCLES')
            mod.mode_before = 'REPEAT'; mod.mode_after = 'REPEAT'


# ---------------------------------------------------------------------------
# Gait foot curve
# ---------------------------------------------------------------------------
def foot_delta(phase, stride=0.05, lift=0.045, swing_frac=0.30):
    """World-space delta for a foot at cycle phase [0,1).
       Forward = -Y. Stance: foot slides +Y. Swing: lifts +Z, moves -Y."""
    phase = phase % 1.0
    if phase < (1.0 - swing_frac):
        # stance: linear slide from -stride/2 (front) to +stride/2 (back)
        t = phase / (1.0 - swing_frac)
        y = -stride/2 + stride * t
        z = 0.0
    else:
        # swing: from +stride/2 back to -stride/2, lift arc
        t = (phase - (1.0 - swing_frac)) / swing_frac
        y = stride/2 - stride * t
        z = lift * math.sin(math.pi * t)
    return Vector((0.0, y, z))


# ---------------------------------------------------------------------------
# WALK (32f) — 4-beat foot-lock
# ---------------------------------------------------------------------------
def make_walk(rig, frames=32):
    new_action(rig.arm, "Walk")
    rig.reset()
    phases = {"CTRL_ik_BL":0.0, "CTRL_ik_FL":0.25, "CTRL_ik_BR":0.5, "CTRL_ik_FR":0.75}
    n_key = 12  # keys per foot
    for f_i in range(n_key+1):
        frame = 1 + f_i * frames / n_key
        cyc = f_i / n_key
        for ik, ph in phases.items():
            rig.key_ik(ik, foot_delta((cyc+ph), stride=0.05, lift=0.045), frame)
    # body bob + sway
    for f, (rz_h, rz_c) in [(1,(0,0)), (1+frames*0.25,(2.0,-1.0)),
                             (1+frames*0.5,(0,0)), (1+frames*0.75,(-2.0,1.0)),
                             (1+frames,(0,0))]:
        rig.key_rot("COG", (0, rz_h, 0), f)
        rig.key_rot("thoracic_03", (0, rz_c, 0), f)
        # vertical bob
        rig.pb["COG"].location = (0,0, -0.004 if (f in (1+frames*0.25,1+frames*0.75)) else 0)
        rig.pb["COG"].keyframe_insert("location", frame=f)
    # spine wave + tail sway + head
    for i,nm in enumerate(["lumbar_02","thoracic_04","cervical_01"]):
        for f, rz in [(1, 1.5), (1+frames*0.5, -1.5), (1+frames, 1.5)]:
            rig.key_rot(nm, (0,0,rz*(1 if i%2 else -1)), f+i)
    for i,nm in enumerate(["tail_03","tail_08","tail_13","tail_18"]):
        d=i*1.5
        for f, rz in [(1+d,3), (1+frames*0.5+d,-3), (1+frames+d,3)]:
            rig.key_rot(nm, (0,0,rz), ((f-1)%frames)+1)
    # breathing underlay
    rig.key_prop("breath", 0.0, 1); rig.key_prop("breath", 0.5, 1+frames*0.5)
    rig.key_prop("breath", 0.0, 1+frames)
    finalize(rig.arm, cyclic=True)
    log("Walk done")


# ---------------------------------------------------------------------------
# RUN (16f) — faster, bigger stride, 2-beat-ish gallop
# ---------------------------------------------------------------------------
def make_run(rig, frames=16):
    new_action(rig.arm, "Run")
    rig.reset()
    # gallop: fronts together-ish, backs together-ish, offset
    phases = {"CTRL_ik_BL":0.0, "CTRL_ik_BR":0.12, "CTRL_ik_FL":0.5, "CTRL_ik_FR":0.62}
    n_key = 10
    for f_i in range(n_key+1):
        frame = 1 + f_i*frames/n_key; cyc=f_i/n_key
        for ik,ph in phases.items():
            rig.key_ik(ik, foot_delta((cyc+ph), stride=0.08, lift=0.07, swing_frac=0.45), frame)
    # strong spine stretch/crouch (gallop)
    for f, st in [(1,0.0),(1+frames*0.25,1.0),(1+frames*0.5,0.0),(1+frames*0.75,-0.6),(1+frames,0.0)]:
        rig.key_rot("lumbar_02", (st*8,0,0), f)
        rig.key_rot("thoracic_03", (-st*6,0,0), f)
        rig.pb["COG"].location=(0,0, st*0.01); rig.pb["COG"].keyframe_insert("location",frame=f)
    for i,nm in enumerate(["tail_03","tail_08","tail_13","tail_18"]):
        d=i*1
        for f, rx in [(1+d,-8),(1+frames*0.5+d,4),(1+frames+d,-8)]:
            rig.key_rot(nm,(rx,0,0),((f-1)%frames)+1)
    finalize(rig.arm, cyclic=True)
    log("Run done")


# ---------------------------------------------------------------------------
# IDLE (60f) — breathing + ear + whisker micro motion
# ---------------------------------------------------------------------------
def make_idle(rig, frames=60):
    new_action(rig.arm, "Idle")
    rig.reset()
    rig.key_prop("breath", -0.3, 1); rig.key_prop("breath", 0.7, 1+frames*0.5)
    rig.key_prop("breath", -0.3, 1+frames)
    # subtle chest/head
    for f, rz in [(1,0),(1+frames*0.5,0.6),(1+frames,0)]:
        rig.key_rot("cervical_01",(0,0,rz),f)
    # ear occasional perk
    rig.key_prop("ear_L_perk",0.0,1); rig.key_prop("ear_L_perk",0.0,1+frames*0.6)
    rig.key_prop("ear_L_perk",0.8,1+frames*0.7); rig.key_prop("ear_L_perk",0.0,1+frames*0.8)
    rig.key_prop("ear_L_perk",0.0,1+frames)
    # whisker micro twitch
    import random; random.seed(1)
    for side in ("L","R"):
        for i in range(1,5):
            for f in (1, frames*0.3, frames*0.6, frames):
                rig.key_rot(f"whisker_{side}_{i}_root",
                            (random.uniform(-2,2),0,random.uniform(-2,2)), 1+f if f else 1)
    finalize(rig.arm, cyclic=True)
    log("Idle done")


# ---------------------------------------------------------------------------
# SNIFF (24f) — nose/whisker vibration + head dips
# ---------------------------------------------------------------------------
def make_sniff(rig, frames=24):
    new_action(rig.arm, "Sniff")
    rig.reset()
    # head dips toward ground, nose region vibrates via snout + whisker
    for f, rx in [(1,0),(1+frames*0.3,6),(1+frames*0.6,3),(1+frames,0)]:
        rig.key_rot("cervical_01",(rx,0,0),f)
        rig.key_rot("snout_base",(rx*0.5,0,0),f)
    # rapid whisker + nose vibration
    import random; random.seed(2)
    for side in ("L","R"):
        for i in range(1,5):
            for f in range(1, frames+1, 2):
                rig.key_rot(f"whisker_{side}_{i}_root",
                            (random.uniform(-4,4), random.uniform(-3,3), random.uniform(-4,4)), f)
        rig.key_rot(f"nose_{side}", (0,0,0), 1)
    for f in range(1, frames+1, 3):
        rig.key_rot("nose_tip",(random.uniform(-3,3),0,0), f)
    # tiny breath
    rig.key_prop("breath",0.0,1); rig.key_prop("breath",0.4,1+frames*0.5); rig.key_prop("breath",0.0,1+frames)
    finalize(rig.arm, cyclic=True)
    log("Sniff done")


def main():
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
    mesh = next(o for o in bpy.data.objects if o.type=='MESH')
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    rig = Rig(arm)
    log(f"IK rest positions: { {k:(round(v.x,3),round(v.y,3),round(v.z,3)) for k,v in rig.ik_rest.items()} }")

    # Build all actions; stash each so export sees them all
    actions = []
    for maker in (make_walk, make_run, make_idle, make_sniff):
        maker(rig)
        actions.append(arm.animation_data.action)
        arm.animation_data.action.use_fake_user = True

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved {OUT_BLEND} with {len(actions)} actions")

    # Export all actions
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    try:
        bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
                                   use_selection=True, export_skins=True,
                                   export_animations=True, export_animation_mode='ACTIONS',
                                   export_force_sampling=True, export_yup=True)
        log(f"Saved {OUT_GLB}")
    except Exception as e:
        log(f"GLB export FAIL: {e}")
    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
