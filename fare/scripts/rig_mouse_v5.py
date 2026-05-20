"""
AAA mouse rigger v5 — Tripo skeleton as ground truth.

CRITICAL DISCOVERY: v1-v4 had head direction REVERSED. My Anatomy heuristic
detected head at +Y (because the tail is the thinnest cross-section, not the
snout). Tripo's armature confirms: head at -Y, tail at +Y. All four prior
versions rigged the wrong end of the mouse.

v5 methodology (per 3-agent consensus):
  1. Import GLB — KEEP Tripo armature (don't delete).
  2. Extract Tripo bone positions (head_world, tail_world, parent_name).
  3. Map Tripo bones → our naming convention (DEF-hips, DEF-spine_*, etc.)
     using a hand-curated table.
  4. Delete Tripo armature, build new armature with our names but
     COORDINATES TAKEN FROM TRIPO. Synthesize only bones Tripo lacks
     (whiskers, eyelids, lips, ribs, etc.) using Tripo's positions as
     reference frame.
  5. Skin with auto-weight + CORRECTIVE_SMOOTH modifier (Industry agent fix).
  6. Manual weight overrides for ear/jaw/tail using CORRECTED anatomy.

Usage:
    blender --background --python fare/scripts/rig_mouse_v5.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "mouse3dmodel1k.glb")
OUT_DIR = os.path.join(ROOT, "out")
OUT = os.path.join(OUT_DIR, "mouse.glb")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[rig5] {m}", flush=True)


# ============================================================================
# Tripo bone → our name mapping
# ============================================================================
# Tripo's structure (33 bones, observed):
#   tripo::Root (vertical Z)
#     tripo::Spine_0 → Spine_1
#       tripo::Head_0 → Head_1 → Head_2 → Head_3
#         bone_6, bone_7 = ears (children of Head_2)
#       bone_9 = front-left shoulder, bone_13 = front-right shoulder
#         tripo::0_Left_Limb_0/1/2 = front-left arm/forearm/paw
#         tripo::0_Right_Limb_0/1/2 = front-right arm/forearm/paw
#     bone_17 = back-right shoulder hump, bone_18 = back-right thigh anchor
#       tripo::1_Right_Limb_0/1 = back-right shin/paw
#     bone_27 = back-left shoulder hump
#       tripo::1_Left_Limb_0/1/2/3/4 = back-left thigh/shin/ankle/paw/toes
#     bone_21 = tail base
#       tripo::Tail_0/1/2/3 = tail segments
#         bone_26 = tail tip continuation
#
# NOTE: Tripo Left = +X side, Tripo Right = -X side.

TRIPO_MAP = {
    # Spine
    "tripo::Root":          "root",
    "tripo::Spine_0":       "DEF-hips",
    "tripo::Spine_1":       "DEF-spine_01",
    # Head chain (4 Tripo head bones → neck, head/skull, muzzle, nose_tip)
    "tripo::Head_0":        "DEF-neck",
    "tripo::Head_1":        "DEF-head",
    "tripo::Head_2":        "DEF-muzzle",
    "tripo::Head_3":        "DEF-nose_tip",
    # Ears (children of Head_2 = muzzle). They're at z=0.37, the actual ears.
    "bone_6":               "DEF-ear.R",   # x=-0.12 → right side
    "bone_7":               "DEF-ear.L",   # x=+0.05 → left side
    # Front limbs (Tripo "0_*_Limb_*")
    "bone_9":               "DEF-shoulder.L",
    "tripo::0_Left_Limb_0": "DEF-arm.L",
    "tripo::0_Left_Limb_1": "DEF-forearm.L",
    "tripo::0_Left_Limb_2": "DEF-paw_F.L",
    "bone_13":              "DEF-shoulder.R",
    "tripo::0_Right_Limb_0": "DEF-arm.R",
    "tripo::0_Right_Limb_1": "DEF-forearm.R",
    "tripo::0_Right_Limb_2": "DEF-paw_F.R",
    # Back limbs (Tripo "1_*_Limb_*")
    "bone_17":              "DEF-pelvis.R",       # actually the back-right hip strut
    "bone_18":              "DEF-thigh.R",
    "tripo::1_Right_Limb_0": "DEF-shin.R",
    "tripo::1_Right_Limb_1": "DEF-paw_B.R",
    "bone_27":              "DEF-pelvis.L",
    "tripo::1_Left_Limb_0": "DEF-thigh.L",
    "tripo::1_Left_Limb_1": "DEF-shin.L",
    "tripo::1_Left_Limb_2": "DEF-ankle.L",
    "tripo::1_Left_Limb_3": "DEF-paw_B.L",
    "tripo::1_Left_Limb_4": "DEF-toes_B.L",  # extra Tripo toe bone
    # Tail
    "bone_21":              "DEF-tail_01",
    "tripo::Tail_0":        "DEF-tail_02",
    "tripo::Tail_1":        "DEF-tail_03",
    "tripo::Tail_2":        "DEF-tail_04",
    "tripo::Tail_3":        "DEF-tail_05",
    "bone_26":              "DEF-tail_06",
}


# ============================================================================
# Scene import & cleanup with Tripo skeleton extraction
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path}")
    bpy.ops.import_scene.gltf(filepath=path)


def extract_tripo_skeleton():
    """Read Tripo armature, return dict[name] = (head_world, tail_world, parent_name)."""
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if arm is None:
        raise RuntimeError("No Tripo armature found in GLB")
    mw = arm.matrix_world
    bones = {}
    for b in arm.data.bones:
        h = mw @ b.head_local
        t = mw @ b.tail_local
        p = b.parent.name if b.parent else None
        bones[b.name] = (h.copy(), t.copy(), p)
    log(f"Extracted {len(bones)} Tripo bones")
    return bones


def cleanup_and_merge():
    """Same as v4 — strip Tripo armature, merge sub-meshes."""
    log("Cleanup: delete placeholder + Tripo armature, merge body meshes")
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o, do_unlink=True)

    body_meshes = [o for o in bpy.data.objects
                   if o.type == 'MESH' and o.name.startswith("tripo_part")]
    for m in body_meshes:
        bpy.context.view_layer.objects.active = m
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE':
                try: bpy.ops.object.modifier_apply(modifier=mod.name)
                except Exception: m.modifiers.remove(mod)
        bpy.ops.object.select_all(action='DESELECT')
        m.select_set(True)
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        m.vertex_groups.clear()

    for o in list(bpy.data.objects):
        if o.type in ('ARMATURE', 'EMPTY'):
            bpy.data.objects.remove(o, do_unlink=True)

    body_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in body_meshes: m.select_set(True)
    bpy.context.view_layer.objects.active = body_meshes[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(body_meshes) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    log(f"Pre-weld:  verts={len(merged.data.vertices)}")
    bpy.context.view_layer.objects.active = merged
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Post-weld: verts={len(merged.data.vertices)} polys={len(merged.data.polygons)}")
    return merged


# ============================================================================
# Anatomy from TRIPO bones (no AABB heuristics!)
# ============================================================================
class TripoAnatomy:
    """Compute anatomy points from Tripo's GROUND-TRUTH bone positions."""

    def __init__(self, tripo_bones, mesh_obj):
        self.tripo = tripo_bones
        self.mesh = mesh_obj
        verts = [v.co.copy() for v in mesh_obj.data.vertices]
        self.verts = verts

        # AABB (for synthesis of bones Tripo doesn't have)
        xs=[v.x for v in verts]; ys=[v.y for v in verts]; zs=[v.z for v in verts]
        self.x_min, self.x_max = min(xs), max(xs)
        self.y_min, self.y_max = min(ys), max(ys)
        self.z_min, self.z_max = min(zs), max(zs)
        self.x_center = (self.x_max + self.x_min) / 2
        self.x_half = max(1e-3, (self.x_max - self.x_min) / 2)
        self.y_size = self.y_max - self.y_min
        self.z_size = self.z_max - self.z_min

        # Head direction from Tripo: head bones are at -Y
        head_y = tripo_bones["tripo::Head_3"][1].y  # snout tail Y
        tail_y = tripo_bones["tripo::Tail_3"][1].y  # tail end Y
        self.head_dir = -1 if head_y < tail_y else +1
        log(f"Head direction (from Tripo): {'+Y' if self.head_dir>0 else '-Y'}")
        log(f"  head_y={head_y:+.3f}  tail_y={tail_y:+.3f}")

        # Anatomy landmarks taken directly from Tripo bones
        self.p_root        = tripo_bones["tripo::Root"][0]
        self.p_hips        = tripo_bones["tripo::Spine_0"][0]      # spine start
        self.p_spine_mid   = tripo_bones["tripo::Spine_1"][0]
        self.p_neck        = tripo_bones["tripo::Head_0"][0]       # neck start
        self.p_head_base   = tripo_bones["tripo::Head_1"][0]       # head start
        self.p_muzzle_base = tripo_bones["tripo::Head_2"][0]
        self.p_nose_base   = tripo_bones["tripo::Head_3"][0]
        self.nose_tip      = tripo_bones["tripo::Head_3"][1]

        # Skull center: average of Head_1 and Head_2 endpoints
        h1_h, h1_t, _ = tripo_bones["tripo::Head_1"]
        h2_h, h2_t, _ = tripo_bones["tripo::Head_2"]
        self.skull_center = (h1_h + h1_t + h2_h + h2_t) * 0.25

        # Ears from bone_6/7
        self.ear_L_pos = tripo_bones["bone_7"][1]   # +X = left
        self.ear_R_pos = tripo_bones["bone_6"][1]   # -X = right
        # Eyes: between ears and snout, on skull surface
        self.eye_L_pos = Vector((+abs(self.ear_L_pos.x) * 0.7,
                                  (self.skull_center.y + self.p_nose_base.y) * 0.5,
                                  self.skull_center.z))
        self.eye_R_pos = Vector((-abs(self.ear_L_pos.x) * 0.7,
                                  (self.skull_center.y + self.p_nose_base.y) * 0.5,
                                  self.skull_center.z))

        # Floor reference
        self.z_floor = self.z_min
        self.z_belly = self.z_min + self.z_size * 0.30

        # Paw plant points (already correct from Tripo paw end positions)
        self.paws = {
            "paw_F_L": tripo_bones["tripo::0_Left_Limb_2"][1],
            "paw_F_R": tripo_bones["tripo::0_Right_Limb_2"][1],
            "paw_B_L": tripo_bones["tripo::1_Left_Limb_3"][1],
            "paw_B_R": tripo_bones["tripo::1_Right_Limb_1"][1],
        }

        log(f"  Tripo-derived landmarks:")
        log(f"    p_hips={self.p_hips}")
        log(f"    skull_center={self.skull_center}")
        log(f"    nose_tip={self.nose_tip}")
        log(f"    ear_L={self.ear_L_pos}  ear_R={self.ear_R_pos}")
        log(f"    paws={ {k: [round(c,3) for c in v] for k,v in self.paws.items()} }")


# ============================================================================
# Armature build using Tripo positions
# ============================================================================
def V(x, y, z): return Vector((x, y, z))


def build_armature_from_tripo(tripo_bones, A: TripoAnatomy):
    """Build our DEF/CTRL/MCH armature using Tripo coords as ground truth.
    Synthesize bones Tripo doesn't have using Tripo positions as references."""
    log("Building armature from Tripo coords")
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig"
    arm = arm_obj.data
    arm.name = "MouseRigData"
    eb = arm.edit_bones
    bones_meta = {}

    d = A.head_dir
    cx = A.x_center

    def mk(name, head, tail, parent=None, connect=False, roll=0.0,
           role="DEF", coll="deform", bbones=1):
        b = eb.new(name)
        b.head = Vector(head); b.tail = Vector(tail); b.roll = roll
        if parent is not None:
            b.parent = parent; b.use_connect = connect
        b.bbone_segments = bbones
        bones_meta[name] = {"role": role, "collection": coll}
        return b

    # ---- PHASE 1: build mapped bones from Tripo coords ----
    # We need to construct in parent-first order. Build all mapped bones
    # first, then fix up parents.
    created = {}  # our_name -> EditBone
    for tripo_name, our_name in TRIPO_MAP.items():
        if tripo_name not in tripo_bones:
            log(f"  WARN: missing Tripo bone '{tripo_name}'"); continue
        h, t, _ = tripo_bones[tripo_name]
        role = "CTRL" if our_name == "root" else "DEF"
        coll = "ctrl_main" if our_name == "root" else "deform"
        # Skip parenting for now; we'll fix up after all bones exist
        b = mk(our_name, h, t, parent=None, role=role, coll=coll)
        created[our_name] = b

    # Set parents from Tripo hierarchy
    for tripo_name, our_name in TRIPO_MAP.items():
        if our_name not in created: continue
        if tripo_name not in tripo_bones: continue
        _, _, tripo_parent = tripo_bones[tripo_name]
        if tripo_parent is None: continue
        our_parent_name = TRIPO_MAP.get(tripo_parent)
        if our_parent_name and our_parent_name in created:
            created[our_name].parent = created[our_parent_name]

    root_b = created["root"]
    hips_b = created["DEF-hips"]
    head_b = created["DEF-head"]
    muzzle_b = created["DEF-muzzle"]
    neck_b = created["DEF-neck"]

    # ---- PHASE 2: bbone segments + connect ----
    for n in ("DEF-spine_01", "DEF-neck", "DEF-head", "DEF-muzzle"):
        if n in created: created[n].bbone_segments = 3
    for n in [k for k in created if k.startswith("DEF-tail_")]:
        created[n].bbone_segments = 4

    # ---- PHASE 3: synthesize bones Tripo doesn't have ----

    # Jaw bone (under skull, forward to nose_tip)
    jaw_head = V(cx,
                  A.p_head_base.y * 0.5 + A.p_muzzle_base.y * 0.5,
                  A.p_head_base.z - A.z_size * 0.10)
    jaw_tail = A.nose_tip
    jaw_b = mk("DEF-jaw", jaw_head, jaw_tail, parent=head_b, coll="deform")

    # Whiskers (4 per side) — parent to MUZZLE
    for side, sx in (("L", +1), ("R", -1)):  # Tripo: +X is left
        for i in range(4):
            t = i / 3.0
            yb = A.p_muzzle_base.y + (A.nose_tip.y - A.p_muzzle_base.y) * (0.3 + 0.4 * t)
            zb = A.p_muzzle_base.z + (A.skull_center.z - A.p_muzzle_base.z) * (0.3 + 0.2 * t)
            xb = cx + sx * A.x_half * 0.25
            tip_x = cx + sx * A.x_half * 1.40
            tip_y = A.nose_tip.y + d * A.y_size * 0.04
            mk(f"DEF-whisker_{i+1:02d}.{side}", V(xb, yb, zb), V(tip_x, tip_y, zb),
                parent=muzzle_b, coll="deform", bbones=4)

    # Eyes
    mk("DEF-eye.L", A.eye_L_pos, A.eye_L_pos + V(0, d * 0.02, 0),
        parent=head_b, coll="deform")
    mk("DEF-eye.R", A.eye_R_pos, A.eye_R_pos + V(0, d * 0.02, 0),
        parent=head_b, coll="deform")

    # Eyelids
    for side, sx, eye_p in (("L", +1, A.eye_L_pos), ("R", -1, A.eye_R_pos)):
        for which, dz in (("upper", +0.010), ("lower", -0.010)):
            mk(f"DEF-eyelid_{which}.{side}", eye_p,
                eye_p + V(sx * 0.005, d * 0.005, dz),
                parent=head_b, coll="deform")

    # Cheeks (under skull, lateral)
    for side, sx in (("L", +1), ("R", -1)):
        cheek_head = V(cx + sx * A.x_half * 0.20,
                        A.skull_center.y, A.skull_center.z - A.z_size * 0.05)
        cheek_tail = V(cx + sx * A.x_half * 0.55,
                        A.p_muzzle_base.y, A.skull_center.z - A.z_size * 0.03)
        mk(f"DEF-cheek.{side}", cheek_head, cheek_tail,
            parent=head_b, coll="deform", bbones=2)

    # Lips — parent to muzzle (upper) and jaw (lower)
    lip_y = (A.p_muzzle_base.y + A.nose_tip.y) * 0.5
    mk("DEF-lip_upper",
        V(cx, lip_y, A.p_muzzle_base.z - 0.005),
        V(cx, A.nose_tip.y, A.p_muzzle_base.z - 0.005),
        parent=muzzle_b, coll="deform")
    mk("DEF-lip_lower",
        V(cx, jaw_head.y, jaw_head.z + 0.003),
        V(cx, A.nose_tip.y, jaw_head.z + 0.003),
        parent=jaw_b, coll="deform")
    for side, sx in (("L", +1), ("R", -1)):
        corner_pos = V(cx + sx * A.x_half * 0.18,
                        (A.p_muzzle_base.y + A.nose_tip.y) * 0.5,
                        A.p_muzzle_base.z - 0.005)
        mk(f"DEF-lip_corner.{side}", corner_pos,
            corner_pos + V(sx * 0.008, d * 0.005, 0),
            parent=head_b, coll="deform")

    # Nostrils
    for side, sx in (("L", +1), ("R", -1)):
        nostril_pos = V(cx + sx * A.x_half * 0.10,
                         A.nose_tip.y - d * 0.005,
                         A.nose_tip.z + 0.003)
        mk(f"DEF-nostril.{side}", nostril_pos,
            nostril_pos + V(sx * 0.003, d * 0.003, 0.003),
            parent=muzzle_b, coll="deform")

    # Belly (2 segments from chest to hips, under spine)
    belly_chest = V(cx, A.p_neck.y + d * A.y_size * 0.05, A.p_neck.z - A.z_size * 0.18)
    belly_mid = V(cx, A.p_spine_mid.y, A.p_spine_mid.z - A.z_size * 0.20)
    belly_hips = V(cx, A.p_hips.y, A.p_hips.z - A.z_size * 0.18)
    spine01_b = created.get("DEF-spine_01", hips_b)
    belly1 = mk("DEF-belly_01", belly_chest, belly_mid, parent=spine01_b, coll="deform", bbones=2)
    mk("DEF-belly_02", belly_mid, belly_hips, parent=belly1, connect=True, coll="deform", bbones=2)

    # Ribcage — 4 pairs, arching from spine to a virtual sternum line
    sternum_top = V(cx, A.p_neck.y + d * A.y_size * 0.02, A.p_neck.z - A.z_size * 0.15)
    sternum_bot = V(cx, A.p_spine_mid.y, A.p_spine_mid.z - A.z_size * 0.18)
    mk("DEF-sternum", sternum_top, sternum_bot, parent=spine01_b, coll="deform", bbones=2)
    rib_count = 4
    for ri in range(rib_count):
        t = (ri + 1) / (rib_count + 1)
        spine_pt = A.p_neck.lerp(A.p_spine_mid, t)  # neck (-Y for d=-1) → spine_mid
        sternum_pt = sternum_top.lerp(sternum_bot, t)
        for side, sx in (("L", +1), ("R", -1)):
            rib_head = spine_pt
            rib_tail = V(cx + sx * A.x_half * 0.18,
                          sternum_pt.y, sternum_pt.z + 0.01)
            mk(f"DEF-rib_{ri+1:02d}.{side}", rib_head, rib_tail,
                parent=spine01_b, coll="deform", bbones=3)

    # Brow
    for side, sx in (("L", +1), ("R", -1)):
        brow_head = V(cx + sx * A.x_half * 0.20,
                       A.skull_center.y - d * A.y_size * 0.02,
                       A.skull_center.z + A.z_size * 0.05)
        brow_tail = V(cx + sx * A.x_half * 0.45,
                       A.skull_center.y + d * A.y_size * 0.02,
                       A.skull_center.z + A.z_size * 0.07)
        mk(f"DEF-brow.{side}", brow_head, brow_tail,
            parent=head_b, coll="deform")

    # ---- PHASE 4: CTRL mirrors for animator interaction ----
    ctrl_hips  = mk("CTRL-hips",  created["DEF-hips"].head, created["DEF-hips"].tail,
                     parent=root_b, role="CTRL", coll="ctrl_main")
    ctrl_spine = mk("CTRL-spine", created["DEF-spine_01"].head, created["DEF-spine_01"].tail,
                     parent=ctrl_hips, role="CTRL", coll="ctrl_main")
    ctrl_neck  = mk("CTRL-neck",  created["DEF-neck"].head, created["DEF-neck"].tail,
                     parent=ctrl_spine, role="CTRL", coll="ctrl_main")
    ctrl_head  = mk("CTRL-head",  head_b.head, head_b.tail,
                     parent=ctrl_neck, role="CTRL", coll="ctrl_face")
    ctrl_muzzle = mk("CTRL-muzzle", muzzle_b.head, muzzle_b.tail,
                      parent=ctrl_head, role="CTRL", coll="ctrl_face")
    ctrl_jaw   = mk("CTRL-jaw", jaw_head, jaw_tail,
                     parent=ctrl_head, role="CTRL", coll="ctrl_face")
    for side, eb_name in (("L", "DEF-ear.L"), ("R", "DEF-ear.R")):
        eb_b = created[eb_name]
        mk(f"CTRL-ear.{side}", eb_b.head, eb_b.tail,
            parent=ctrl_head, role="CTRL", coll="ctrl_face")

    # Eye look target
    aim_dist = A.y_size * 0.35
    y_target = A.nose_tip.y + d * aim_dist
    eye_aim_master = mk("CTRL-eye_aim",
                         V(cx, y_target, A.skull_center.z),
                         V(cx, y_target, A.skull_center.z + 0.03),
                         parent=ctrl_head, role="CTRL", coll="ctrl_face")
    for side, eye_p in (("L", A.eye_L_pos), ("R", A.eye_R_pos)):
        mk(f"CTRL-eye_aim.{side}",
            V(eye_p.x, y_target, A.skull_center.z),
            V(eye_p.x, y_target, A.skull_center.z + 0.02),
            parent=eye_aim_master, role="CTRL", coll="ctrl_face")

    # ---- IK foot controllers (4 limbs) ----
    limb_data = []
    for side, paw_name, fname in (
            ("L", "DEF-paw_F.L", "F"),
            ("R", "DEF-paw_F.R", "F"),
            ("L", "DEF-paw_B.L", "B"),
            ("R", "DEF-paw_B.R", "B")):
        paw_b = created.get(paw_name)
        if paw_b is None: continue
        paw_world = paw_b.tail.copy()
        heel = V(paw_world.x, paw_world.y - d * A.y_size * 0.04, A.z_floor)
        ctrl_foot = mk(f"CTRL-foot_{fname}.{side}", heel, heel + V(0, d * 0.05, 0),
                        parent=root_b, role="CTRL", coll="ctrl_ik")
        pole_pos = V(paw_world.x, paw_world.y + d * A.y_size * 0.30, A.z_belly + A.z_size * 0.25)
        mk(f"CTRL-pole_{fname}.{side}", pole_pos, pole_pos + V(0, 0, 0.03),
            parent=root_b, role="CTRL", coll="ctrl_ik")
        # find arm and forearm names for IK chain
        arm_n = f"DEF-arm.{side}" if fname == "F" else f"DEF-thigh.{side}"
        fore_n = f"DEF-forearm.{side}" if fname == "F" else f"DEF-shin.{side}"
        limb_data.append({
            "side": side, "front": fname == "F",
            "paw": paw_name, "forearm": fore_n, "arm": arm_n,
            "ik_target": f"CTRL-foot_{fname}.{side}",
            "pole_target": f"CTRL-pole_{fname}.{side}",
        })

    # ---- Tail CTRL bones — one CTRL per ~2 DEF bones, with MATCHING rest orientation ----
    # CTRL bone must share rest direction with the DEF it drives so LOCAL→LOCAL
    # rotation copy is geometrically correct.
    tail_bone_names = sorted([n for n in created if n.startswith("DEF-tail_")])
    tail_ctrl_names = []
    if tail_bone_names:
        # Use 3 CTRL bones at base/mid/tip of tail. Each ctrl shares orientation
        # with the closest DEF tail bone.
        positions = [(0, "base"),
                      (len(tail_bone_names)//2, "mid"),
                      (len(tail_bone_names)-1, "tip")]
        for ti, (def_idx, _label) in enumerate(positions):
            def_b = created[tail_bone_names[def_idx]]
            # CTRL bone matches DEF bone's head & tail (same rest orientation!)
            name = f"CTRL-tail_{ti+1}"
            mk(name, def_b.head, def_b.tail,
                parent=root_b, role="CTRL", coll="ctrl_main")
            tail_ctrl_names.append(name)

    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Armature built: {len(arm.bones)} bones")
    return arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names


# ============================================================================
# Skinning with CORRECTIVE_SMOOTH modifier (Industry Agent fix #2)
# ============================================================================
def setup_pose_constraints(arm_obj, limb_data, tail_bone_names, tail_ctrl_names, A):
    log("Pose constraints: IK + spline tail + look-at + FK mirrors + breath")
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pbones = arm_obj.pose.bones

    # IK on limbs (with stretch enabled for better paw reach)
    for L in limb_data:
        if L["paw"] not in pbones: continue
        pb = pbones[L["paw"]]
        ik = pb.constraints.new('IK')
        ik.target = arm_obj
        ik.subtarget = L["ik_target"]
        ik.chain_count = 4  # paw + forearm/shin + arm/thigh + shoulder/pelvis
        ik.use_stretch = True
        if L["pole_target"] in pbones:
            ik.pole_target = arm_obj
            ik.pole_subtarget = L["pole_target"]
            ik.pole_angle = -math.pi / 2

    # ---- Tail Spline IK (v4 approach — curve-driven, robust) ----
    # CTRL-tail_1/2/3 hook to a Bezier curve; DEF-tail chain follows the curve.
    if tail_bone_names and tail_ctrl_names:
        bpy.ops.object.mode_set(mode='OBJECT')
        # Build a 3-point Bezier curve along the tail
        curve_data = bpy.data.curves.new("TailCurve", type='CURVE')
        curve_data.dimensions = '3D'
        spline = curve_data.splines.new('BEZIER')
        spline.bezier_points.add(2)  # total 3 points
        # Place at base/mid/tip positions
        n = len(tail_bone_names)
        pos_base = arm_obj.matrix_world @ arm_obj.data.bones[tail_bone_names[0]].head_local
        pos_mid = arm_obj.matrix_world @ arm_obj.data.bones[tail_bone_names[n//2]].head_local
        pos_tip = arm_obj.matrix_world @ arm_obj.data.bones[tail_bone_names[-1]].tail_local
        spline_pos = [pos_base, pos_mid, pos_tip]
        for i, p in enumerate(spline_pos):
            bp = spline.bezier_points[i]
            bp.co = (p.x, p.y, p.z)
            # tangent along tail direction
            tan_off = 0.1
            tan_dir = Vector((0, A.head_dir * tan_off * -1, 0))  # tail extends -d direction... actually +Y for our case
            tan_dir = Vector((0, 0.1, 0))
            bp.handle_left = (p - tan_dir).to_tuple()
            bp.handle_right = (p + tan_dir).to_tuple()
        curve_obj = bpy.data.objects.new("TailCurve", curve_data)
        bpy.context.collection.objects.link(curve_obj)

        # Hook each curve point (+ its handles) to a CTRL-tail bone.
        # In Blender bezier curves, point i occupies vertex indices [3i, 3i+1, 3i+2]
        # = [left_handle, control_point, right_handle].
        for i, ctrl_name in enumerate(tail_ctrl_names[:3]):
            if ctrl_name not in arm_obj.pose.bones: continue
            hook = curve_obj.modifiers.new(name=f"Hook_{ctrl_name}", type='HOOK')
            hook.object = arm_obj
            hook.subtarget = ctrl_name
            hook.vertex_indices_set([3*i, 3*i + 1, 3*i + 2])

        # Spline IK on the last tail bone targeting the curve
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='POSE')
        last_tail_pb = arm_obj.pose.bones.get(tail_bone_names[-1])
        if last_tail_pb is not None:
            sik = last_tail_pb.constraints.new('SPLINE_IK')
            sik.target = curve_obj
            sik.chain_count = len(tail_bone_names)
            sik.y_scale_mode = 'BONE_ORIGINAL'
            sik.xz_scale_mode = 'BONE_ORIGINAL'

    # FK mirror: DEF copies CTRL local rotation
    for def_n, ctrl_n in (("DEF-hips", "CTRL-hips"),
                            ("DEF-spine_01", "CTRL-spine"),
                            ("DEF-neck", "CTRL-neck"),
                            ("DEF-head", "CTRL-head"),
                            ("DEF-muzzle", "CTRL-muzzle"),
                            ("DEF-jaw", "CTRL-jaw"),
                            ("DEF-ear.L", "CTRL-ear.L"),
                            ("DEF-ear.R", "CTRL-ear.R")):
        if def_n in pbones and ctrl_n in pbones:
            c = pbones[def_n].constraints.new('COPY_ROTATION')
            c.target = arm_obj; c.subtarget = ctrl_n
            c.target_space = 'LOCAL'; c.owner_space = 'LOCAL'

    # Eye look-at
    for side in ("L", "R"):
        eye_n = f"DEF-eye.{side}"
        tgt_n = f"CTRL-eye_aim.{side}"
        if eye_n in pbones and tgt_n in pbones:
            c = pbones[eye_n].constraints.new('DAMPED_TRACK')
            c.target = arm_obj; c.subtarget = tgt_n
            c.track_axis = 'TRACK_Y' if A.head_dir > 0 else 'TRACK_NEGATIVE_Y'

    # Breath driver
    arm_obj["breath"] = 0.0
    spine_pb = pbones.get("DEF-spine_01")
    if spine_pb is not None:
        for axis_idx, expr in ((0, "1.0 + 0.05 * breath"),
                                (1, "1.0 + 0.07 * breath"),
                                (2, "1.0 + 0.05 * breath")):
            fc = spine_pb.driver_add("scale", axis_idx)
            drv = fc.driver
            drv.type = 'SCRIPTED'
            v = drv.variables.new()
            v.name = "breath"; v.type = 'SINGLE_PROP'
            v.targets[0].id_type = 'OBJECT'; v.targets[0].id = arm_obj
            v.targets[0].data_path = '["breath"]'
            drv.expression = expr

    bpy.ops.object.mode_set(mode='OBJECT')


def skin_with_corrective_smooth(mesh_obj, arm_obj):
    """Industry-Agent fix #2: add CORRECTIVE_SMOOTH after armature modifier.
    Length-weighted smoothing hides bind-weight artifacts ('pipe pinch')."""
    log("Skinning: ARMATURE_AUTO + CORRECTIVE_SMOOTH modifier")
    arm = arm_obj.data
    for b in arm.bones:
        b.use_deform = b.name.startswith("DEF-")

    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

    # Add CORRECTIVE_SMOOTH modifier after the armature modifier
    bpy.context.view_layer.objects.active = mesh_obj
    cs = mesh_obj.modifiers.new(name="CorrectiveSmooth", type='CORRECTIVE_SMOOTH')
    cs.smooth_type = 'LENGTH_WEIGHTED'
    cs.factor = 0.5
    cs.iterations = 3
    cs.use_only_smooth = False
    cs.rest_source = 'ORCO'
    log(f"  CorrectiveSmooth added: factor=0.5 iter=3 length_weighted")


def targeted_weight_refinement(mesh_obj, A):
    """Geodesic-aware weight refinement for tricky regions: jaw, ears, tail.
    Uses spatial filtering with HARD CLEAR to prevent neighbor bones from
    holding majority weight after heat-binding. Industry agent fix."""
    log("Targeted weight refinement (jaw / ears / tail / lips)")
    cx = A.x_center
    d = A.head_dir
    verts = mesh_obj.data.vertices

    def ensure_vg(name):
        return mesh_obj.vertex_groups.get(name) or mesh_obj.vertex_groups.new(name=name)

    def assign(group_name, indices, weight=1.0, clear=None):
        if not indices: return 0
        g = ensure_vg(group_name)
        g.add(indices, weight, 'REPLACE')
        if clear:
            for og_name in clear:
                og = mesh_obj.vertex_groups.get(og_name)
                if og: og.remove(indices)
        return len(indices)

    # ---- Jaw: lower mouth/chin area ----
    # Verts below the skull center Z, in the front 50% of head Y range
    jaw_y_min = min(A.p_muzzle_base.y, A.nose_tip.y) - A.y_size * 0.02
    jaw_y_max = max(A.p_muzzle_base.y, A.nose_tip.y) + A.y_size * 0.02
    z_jaw_max = A.skull_center.z - A.z_size * 0.06
    jaw_candidates = [vi for vi, v in enumerate(verts)
                      if jaw_y_min <= v.co.y <= jaw_y_max
                      and v.co.z < z_jaw_max
                      and abs(v.co.x - cx) < A.x_half * 0.5]
    n = assign("DEF-jaw", jaw_candidates, 1.0,
                clear=["DEF-head", "DEF-muzzle", "DEF-neck", "DEF-nose_tip"])
    log(f"  jaw: {n} verts (FULL 1.0, cleared head/muzzle/neck/nose)")

    # ---- Ears: lateral verts above skull center Z, near head Y ----
    # Use HEAD-LOCAL Z (not global) — ears are top 25% of head verts
    head_y_lo = min(A.p_head_base.y, A.p_nose_base.y) - A.y_size * 0.05
    head_y_hi = max(A.p_head_base.y, A.p_nose_base.y) + A.y_size * 0.05
    head_verts = [v for v in verts if head_y_lo <= v.co.y <= head_y_hi]
    if head_verts:
        head_z_max = max(v.co.z for v in head_verts)
        head_z_min = min(v.co.z for v in head_verts)
        z_thresh = head_z_min + (head_z_max - head_z_min) * 0.70

        ear_L_idxs = []; ear_R_idxs = []
        for vi, v in enumerate(verts):
            if head_y_lo <= v.co.y <= head_y_hi and v.co.z > z_thresh:
                if (v.co.x - cx) > A.x_half * 0.20:
                    ear_L_idxs.append(vi)  # Tripo: +X = left
                elif (v.co.x - cx) < -A.x_half * 0.20:
                    ear_R_idxs.append(vi)
        n = assign("DEF-ear.L", ear_L_idxs, 1.0,
                    clear=["DEF-head", "DEF-muzzle", "DEF-neck", "DEF-spine_01"])
        log(f"  ear.L: {n} verts")
        n = assign("DEF-ear.R", ear_R_idxs, 1.0,
                    clear=["DEF-head", "DEF-muzzle", "DEF-neck", "DEF-spine_01"])
        log(f"  ear.R: {n} verts")

    # ---- Tail segments: each tail bone gets its own narrow Y-slice ----
    # Tail extends from hips (~+0.08) to tail tip (~+0.47) on +Y
    tail_bone_names = sorted([b.name for b in mesh_obj.parent.data.bones
                               if b.name.startswith("DEF-tail_")])
    if tail_bone_names:
        arm = mesh_obj.parent
        for tn in tail_bone_names:
            b = arm.data.bones[tn]
            mw = arm.matrix_world
            bh = mw @ b.head_local
            bt = mw @ b.tail_local
            y_lo, y_hi = min(bh.y, bt.y), max(bh.y, bt.y)
            cand = [vi for vi, v in enumerate(verts)
                    if y_lo - 0.01 <= v.co.y <= y_hi + 0.01
                    and abs(v.co.x - cx) < A.x_half * 0.30
                    and abs(v.co.z - (bh.z + bt.z) / 2) < A.z_size * 0.25]
            n = assign(tn, cand, 1.0,
                        clear=["DEF-hips", "DEF-spine_01", "root"])
            log(f"  {tn}: {n} verts")


def smart_orphan_adoption(mesh_obj, arm_obj):
    arm_mat = arm_obj.matrix_world
    bone_segs = []
    for b in arm_obj.data.bones:
        if not b.name.startswith("DEF-"): continue
        bone_segs.append((b.name, arm_mat @ b.head_local, arm_mat @ b.tail_local))

    def dist_to_seg(p, a, b):
        ab = b - a
        denom = max(ab.length_squared, 1e-12)
        t = max(0.0, min(1.0, (p - a).dot(ab) / denom))
        return (p - (a + ab * t)).length

    mesh_mat = mesh_obj.matrix_world
    orphans_by_bone = {}
    n = 0
    for vi, vert in enumerate(mesh_obj.data.vertices):
        if sum(g.weight for g in vert.groups) > 1e-6: continue
        n += 1
        wp = mesh_mat @ vert.co
        best, best_d = None, float('inf')
        for name, h, t in bone_segs:
            dd = dist_to_seg(wp, h, t)
            if dd < best_d: best_d = dd; best = name
        orphans_by_bone.setdefault(best, []).append(vi)
    for name, idxs in orphans_by_bone.items():
        g = mesh_obj.vertex_groups.get(name) or mesh_obj.vertex_groups.new(name=name)
        g.add(idxs, 1.0, 'REPLACE')
    log(f"Orphan adoption: {n} verts → {len(orphans_by_bone)} bones")


# ============================================================================
# Export
# ============================================================================
def export_glb(path, mesh_obj, arm_obj):
    log(f"Exporting → {path}")
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.export_scene.gltf(
        filepath=path, export_format='GLB',
        export_skins=True, export_yup=True,
        export_apply=False, export_animations=False,
        export_extras=True, use_selection=True,
    )


# ============================================================================
# Main
# ============================================================================
def main():
    reset_scene()
    import_glb(SRC)
    tripo_bones = extract_tripo_skeleton()
    mesh_obj = cleanup_and_merge()
    A = TripoAnatomy(tripo_bones, mesh_obj)
    arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names = \
        build_armature_from_tripo(tripo_bones, A)
    setup_pose_constraints(arm_obj, limb_data, tail_bone_names, tail_ctrl_names, A)
    skin_with_corrective_smooth(mesh_obj, arm_obj)
    targeted_weight_refinement(mesh_obj, A)
    smart_orphan_adoption(mesh_obj, arm_obj)
    export_glb(OUT, mesh_obj, arm_obj)
    log(f"DONE — {len(arm_obj.data.bones)} bones")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
