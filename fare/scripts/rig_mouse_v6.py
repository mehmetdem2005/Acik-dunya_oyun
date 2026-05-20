"""
RIG ONLY — Staged pipeline per ChatGPT/pipeline spec.

ABSOLUTE RULE: The mesh is NOT modified. Only the rig is built.

Stage 3: Skeleton placement
Stage 4: Skinning / weight painting (separate runs)
Stage 5: Corrective pass
Stage 6: Animation clips
Stage 7: Export
Stage 8: Final QA report

Each stage has its own gate (stage_qa.py). Do NOT advance until current stage
passes.

Hierarchy (ChatGPT spec):
    root
      pelvis
        spine_01 → spine_02 → chest → neck → head
          → snout → jaw, ear.L, ear.R, eye.L, eye.R
        shoulder.L → upper_arm.L → forearm.L → front_paw.L
        shoulder.R → ...
        hip.L → thigh.L → shin.L → back_paw.L
        hip.R → ...
        tail_01 → tail_02 → tail_03 → tail_04 → tail_05

Usage:
    blender --background --python fare/scripts/rig_mouse_v6.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "mouse3dmodel1k.glb")
OUT_DIR = os.path.join(ROOT, "out")
OUT_GLB = os.path.join(OUT_DIR, "mouse.glb")
OUT_BLEND = os.path.join(OUT_DIR, "mouse_character_final.blend")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[rig6] {m}", flush=True)


# ============================================================================
# Tripo → ChatGPT-spec name mapping
# ============================================================================
TRIPO_MAP = {
    "tripo::Root":           "root",
    # spine
    "tripo::Spine_0":        "spine_01",  # at hips
    "tripo::Spine_1":        "spine_02",  # at chest
    # head chain
    "tripo::Head_0":         "neck",
    "tripo::Head_1":         "head",
    "tripo::Head_2":         "snout",
    "tripo::Head_3":         "jaw_root",  # snout extension — we'll synthesize jaw separately
    # ears
    "bone_7":                "ear.L",   # x=+0.05 → left
    "bone_6":                "ear.R",   # x=-0.12 → right
    # front limbs
    "bone_9":                "shoulder.L",
    "tripo::0_Left_Limb_0":  "upper_arm.L",
    "tripo::0_Left_Limb_1":  "forearm.L",
    "tripo::0_Left_Limb_2":  "front_paw.L",
    "bone_13":               "shoulder.R",
    "tripo::0_Right_Limb_0": "upper_arm.R",
    "tripo::0_Right_Limb_1": "forearm.R",
    "tripo::0_Right_Limb_2": "front_paw.R",
    # back limbs
    "bone_27":               "hip.L",
    "tripo::1_Left_Limb_0":  "thigh.L",
    "tripo::1_Left_Limb_1":  "shin.L",
    "tripo::1_Left_Limb_2":  "back_paw.L",
    "tripo::1_Left_Limb_3":  "back_toes.L",     # extra Tripo segment
    "bone_17":               "hip.R",
    "bone_18":               "thigh.R",
    "tripo::1_Right_Limb_0": "shin.R",
    "tripo::1_Right_Limb_1": "back_paw.R",
    # tail
    "bone_21":               "tail_01",
    "tripo::Tail_0":         "tail_02",
    "tripo::Tail_1":         "tail_03",
    "tripo::Tail_2":         "tail_04",
    "tripo::Tail_3":         "tail_05",
    "bone_26":               "tail_06",
}


# ============================================================================
# Scene import & Tripo skeleton extraction
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path} (MESH PRESERVED, only Tripo armature will be re-used)")
    bpy.ops.import_scene.gltf(filepath=path)


def extract_tripo_skeleton():
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    if arm is None:
        raise RuntimeError("Tripo armature not found")
    mw = arm.matrix_world
    bones = {}
    for b in arm.data.bones:
        h = mw @ b.head_local
        t = mw @ b.tail_local
        p = b.parent.name if b.parent else None
        bones[b.name] = (h.copy(), t.copy(), p)
    log(f"Extracted {len(bones)} Tripo bones (ground truth)")
    return bones


def cleanup_keep_mesh_only():
    """Strip the Tripo armature + placeholder. KEEP the mesh untouched (no
    weld, no normals recalc, no modifier apply) per user instruction
    'modele dokunma'."""
    log("Cleanup: removing armature/empty, MESH UNTOUCHED")
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o, do_unlink=True)

    body_meshes = [o for o in bpy.data.objects
                   if o.type == 'MESH' and o.name.startswith("tripo_part")]
    for m in body_meshes:
        bpy.context.view_layer.objects.active = m
        # Remove existing armature modifier from Tripo (we'll add ours later)
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE':
                m.modifiers.remove(mod)
        bpy.ops.object.select_all(action='DESELECT')
        m.select_set(True)
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        m.vertex_groups.clear()

    # Delete Tripo armature + empties
    for o in list(bpy.data.objects):
        if o.type in ('ARMATURE', 'EMPTY'):
            bpy.data.objects.remove(o, do_unlink=True)

    # JOIN sub-meshes for skinning (this is a non-destructive merge — vertices
    # are preserved, just combined into one object). NO weld, NO normals fix.
    body_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in body_meshes: m.select_set(True)
    bpy.context.view_layer.objects.active = body_meshes[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(body_meshes) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    log(f"Mesh ready: verts={len(merged.data.vertices)} polys={len(merged.data.polygons)} (UNTOUCHED)")
    return merged


# ============================================================================
# BVH helpers
# ============================================================================
def make_bvh(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.transform(mesh_obj.matrix_world)
    bm.faces.ensure_lookup_table()
    return BVHTree.FromBMesh(bm)


def snap_to_inside(bvh, p, search_radius=0.15):
    """If p is outside the mesh, search neighborhood for an inside point."""
    def inside(point):
        hits = 0
        d = Vector((0.0, 1.0, 0.05)).normalized()
        origin = point.copy()
        for _ in range(20):
            loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
            if loc is None: break
            hits += 1
            origin = loc + d * 1e-5
        return hits % 2 == 1
    if inside(p): return p
    for r in (0.02, 0.04, 0.08, 0.15):
        if r > search_radius: break
        for theta in [i * math.pi / 8 for i in range(16)]:
            for phi in (-math.pi/3, 0, math.pi/3):
                off = Vector((r*math.cos(theta)*math.cos(phi),
                               r*math.sin(theta)*math.cos(phi),
                               r*math.sin(phi)))
                cand = p + off
                if inside(cand): return cand
    return p


# ============================================================================
# Build armature — Stage 3
# ============================================================================
def build_armature_stage3(tripo_bones, mesh_obj):
    """Skeleton placement only. No weights, no constraints, no animations."""
    log("=" * 60)
    log("STAGE 3: Skeleton placement (RIG ONLY — no weights)")
    log("=" * 60)

    bvh = make_bvh(mesh_obj)
    # AABB for synthesis
    verts = mesh_obj.data.vertices
    xs=[v.co.x for v in verts]; ys=[v.co.y for v in verts]; zs=[v.co.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    x_center = (x_max + x_min) / 2
    x_half = (x_max - x_min) / 2
    y_size = y_max - y_min
    z_size = z_max - z_min

    # Head dir: from Tripo, head_y < tail_y (head at -Y)
    head_y = tripo_bones["tripo::Head_3"][1].y
    tail_y = tripo_bones["tripo::Tail_3"][1].y
    head_dir = -1 if head_y < tail_y else +1
    log(f"Head direction (from Tripo): {'+Y' if head_dir>0 else '-Y'}")

    # Create armature
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig"
    arm_data = arm_obj.data
    arm_data.name = "MouseArmature"
    eb = arm_data.edit_bones

    created = {}

    def mk(name, head, tail, parent_name=None, connect=False, bbones=1):
        b = eb.new(name)
        b.head = Vector(head); b.tail = Vector(tail)
        if parent_name is not None and parent_name in created:
            b.parent = created[parent_name]
            b.use_connect = connect
        b.bbone_segments = bbones
        created[name] = b
        return b

    # ---- Phase A: Create all Tripo-mapped bones ----
    for tripo_name, our_name in TRIPO_MAP.items():
        if tripo_name not in tripo_bones: continue
        h, t, _ = tripo_bones[tripo_name]
        b = eb.new(our_name)
        b.head = h.copy(); b.tail = t.copy()
        created[our_name] = b

    # ---- Phase B: Set parents (manually per ChatGPT hierarchy) ----
    # ChatGPT hierarchy: root → pelvis → spine_01 → spine_02 → chest → neck → head
    # Our Tripo mapping gives:
    #   root → spine_01 (= Tripo Spine_0) → spine_02 (= Tripo Spine_1) → neck (= Head_0)
    # We need to INSERT pelvis between root and spine_01.

    # SYNTHESIZE pelvis (between root and spine_01) at the actual hip joint
    # location — midway between spine top and tail base, which is where the
    # back legs connect anatomically.
    root_b = created["root"]
    spine01_b = created["spine_01"]
    tail01_b = created.get("tail_01")
    # Pelvis HEAD = spine_01 base (hip end of spine), TAIL = toward tail base
    pelvis_h = spine01_b.head.copy()
    if tail01_b is not None:
        # Tail extends backward from pelvis — point pelvis bone at the tail base
        pelvis_t = tail01_b.head.copy()
    else:
        pelvis_t = spine01_b.head + Vector((0, head_dir * 0.04, -0.02))
    pelvis_t = snap_to_inside(bvh, pelvis_t)
    pelvis_b = eb.new("pelvis")
    pelvis_b.head = pelvis_h
    pelvis_b.tail = pelvis_t
    pelvis_b.parent = root_b
    created["pelvis"] = pelvis_b
    # spine_01 now parent = pelvis (spine extends forward from pelvis)
    spine01_b.parent = pelvis_b
    spine01_b.use_connect = False

    # SYNTHESIZE chest (between spine_02 and neck — ChatGPT spec wants chest)
    spine02_b = created["spine_02"]
    neck_b = created["neck"]
    chest_h = spine02_b.tail.copy()
    chest_t = neck_b.head.copy()
    if (chest_t - chest_h).length < 1e-3:
        chest_t = chest_h + Vector((0, -head_dir * 0.03, 0))
    chest_b = eb.new("chest")
    chest_b.head = chest_h
    chest_b.tail = chest_t
    chest_b.parent = spine02_b
    chest_b.use_connect = True
    created["chest"] = chest_b
    # neck parent → chest
    neck_b.parent = chest_b
    neck_b.use_connect = True

    # Spine chain connect
    spine02_b.parent = spine01_b
    spine02_b.use_connect = True

    # Head bone parent → neck (already from Tripo: Head_1's parent is Head_0/neck)
    head_b = created["head"]
    head_b.parent = neck_b
    head_b.use_connect = True

    # Snout parent → head (already from Tripo)
    snout_b = created["snout"]
    snout_b.parent = head_b
    snout_b.use_connect = True

    # SYNTHESIZE jaw (under skull, hinging from back of head)
    # Find approximate jaw hinge: at head_b.head Y but lower Z
    skull_center_z = head_b.head.z * 0.5 + head_b.tail.z * 0.5
    jaw_h = Vector((x_center, head_b.head.y, skull_center_z - z_size * 0.10))
    jaw_h = snap_to_inside(bvh, jaw_h)
    jaw_t = tripo_bones["tripo::Head_3"][1]  # nose tip
    jaw_b = eb.new("jaw")
    jaw_b.head = jaw_h
    jaw_b.tail = jaw_t.copy()
    jaw_b.parent = head_b
    created["jaw"] = jaw_b

    # Ears parent → head (Tripo had them under snout = Head_2, but per ChatGPT
    # spec ears parent to head)
    for side in ("L", "R"):
        e = created.get(f"ear.{side}")
        if e is not None:
            e.parent = head_b

    # SYNTHESIZE eyes (left/right) — parent to head
    # Place at skull center, lateral, on skull surface
    eye_y = (head_b.head.y + head_b.tail.y) * 0.5
    eye_z = skull_center_z
    for side, sx in (("L", +1), ("R", -1)):
        eye_pos = Vector((x_center + sx * x_half * 0.30, eye_y, eye_z))
        eye_b = eb.new(f"eye.{side}")
        eye_b.head = eye_pos
        eye_b.tail = eye_pos + Vector((0, head_dir * 0.015, 0))
        eye_b.parent = head_b
        created[f"eye.{side}"] = eye_b

    # Front legs — shoulder parents to chest (per ChatGPT spec)
    for side in ("L", "R"):
        sh = created.get(f"shoulder.{side}")
        if sh is not None:
            sh.parent = chest_b
        upper = created.get(f"upper_arm.{side}")
        if upper is not None:
            upper.parent = sh
            upper.use_connect = True
        fore = created.get(f"forearm.{side}")
        if fore is not None:
            fore.parent = upper
            fore.use_connect = True
        paw = created.get(f"front_paw.{side}")
        if paw is not None:
            paw.parent = fore
            paw.use_connect = True

    # Back legs — hip parents to pelvis, thigh to hip
    for side in ("L", "R"):
        hip = created.get(f"hip.{side}")
        if hip is not None:
            hip.parent = pelvis_b
        thigh = created.get(f"thigh.{side}")
        if thigh is not None:
            thigh.parent = hip
            thigh.use_connect = False  # hip is short strut, don't connect
        shin = created.get(f"shin.{side}")
        if shin is not None:
            shin.parent = thigh
            shin.use_connect = True
        paw = created.get(f"back_paw.{side}")
        if paw is not None:
            paw.parent = shin
            paw.use_connect = True
        toes = created.get(f"back_toes.{side}")
        if toes is not None:
            toes.parent = paw
            toes.use_connect = True

    # Tail chain — tail_01 parent to pelvis (per ChatGPT spec)
    tail01 = created.get("tail_01")
    if tail01 is not None:
        tail01.parent = pelvis_b
    # Chain through 06
    for i in range(2, 7):
        tn = f"tail_{i:02d}"
        prev = f"tail_{i-1:02d}"
        if tn in created and prev in created:
            created[tn].parent = created[prev]
            created[tn].use_connect = True
        if tn in created:
            created[tn].bbone_segments = 3  # smooth chain

    # bbone segments for smooth spine/neck/head/snout
    for n in ("spine_01", "spine_02", "chest", "neck", "head", "snout"):
        if n in created:
            created[n].bbone_segments = 3

    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Stage 3 armature: {len(arm_data.bones)} bones")
    log(f"  hierarchy root → pelvis → spine_01 → spine_02 → chest → neck → head")
    return arm_obj


# ============================================================================
# Main entry — only Stage 3 for now
# ============================================================================
def main():
    reset_scene()
    import_glb(SRC)
    tripo = extract_tripo_skeleton()
    mesh = cleanup_keep_mesh_only()
    arm = build_armature_stage3(tripo, mesh)

    # Save .blend file for Stage 3 inspection
    blend_path = os.path.join(OUT_DIR, "stage3_rig.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    log(f"Saved Stage 3 .blend → {blend_path}")
    log("DONE Stage 3 — run stage_qa.py to validate")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
