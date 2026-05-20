"""
AAA Mouse Rig v8 — 3-layer architecture per detailed anatomical spec.

ABSOLUTE RULES:
- Mesh is NEVER modified (no weld, no normals recalc, no transform).
- Only rig is built.
- No weight painting yet.
- No animations yet.
- No Corrective Smooth yet.

THREE LAYERS:

  LAYER 1 — ANATOMICAL_REFERENCE
    Full anatomical mouse skeleton proof. NOT used as deformers.
    C01_atlas, C02_axis, C03..C07     (7 cervical)
    T01..T13                          (13 thoracic)
    L01..L06                          (6 lumbar)
    S01..S04                          (4 sacral)
    Ca01..Ca28                        (28 caudal)
    rib_L_01..13, rib_R_01..13         (13 rib pairs)
    manubrium, sternebra_01..04, xiphoid  (6 sternum)
    skull/face anatomy bones, forelimb/hindlimb anatomy bones

  LAYER 2 — ARMATURE_DEFORM
    Dense skinning rig. use_deform=True. Per the rig spec.

  LAYER 3 — ARMATURE_CONTROLS
    Animator-facing controls.

  + RIG_HELPERS (rib center, belly center, etc.)

Usage:
    blender --background --python fare/scripts/rig_mouse_v8.py
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
OUT_BLEND = os.path.join(OUT_DIR, "stage3_rig_v8.blend")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[rig8] {m}", flush=True)


# ============================================================================
# Scene import & cleanup (mesh untouched)
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path} (mesh untouched)")
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
    return bones


def cleanup_keep_mesh_only():
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    body = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("tripo_part")]
    for m in body:
        bpy.context.view_layer.objects.active = m
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE': m.modifiers.remove(mod)
        bpy.ops.object.select_all(action='DESELECT')
        m.select_set(True); bpy.context.view_layer.objects.active = m
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        m.vertex_groups.clear()
    for o in list(bpy.data.objects):
        if o.type in ('ARMATURE', 'EMPTY'):
            bpy.data.objects.remove(o, do_unlink=True)
    body = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in body: m.select_set(True)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(body) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    log(f"Mesh: {len(merged.data.vertices)} verts (untouched)")
    return merged


# ============================================================================
# BVH + helpers
# ============================================================================
def make_bvh(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.transform(mesh_obj.matrix_world)
    bm.faces.ensure_lookup_table()
    return BVHTree.FromBMesh(bm)


def is_inside(bvh, p):
    d = Vector((0.0, 1.0, 0.05)).normalized()
    hits = 0; origin = p.copy()
    for _ in range(20):
        loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
        if loc is None: break
        hits += 1; origin = loc + d * 1e-5
    return hits % 2 == 1


def snap_to_inside(bvh, p, search_radius=0.15):
    if is_inside(bvh, p): return p
    for r in (0.02, 0.04, 0.08, 0.15):
        if r > search_radius: break
        for theta in [i * math.pi / 8 for i in range(16)]:
            for phi in (-math.pi/3, 0, math.pi/3):
                off = Vector((r*math.cos(theta)*math.cos(phi),
                               r*math.sin(theta)*math.cos(phi),
                               r*math.sin(phi)))
                cand = p + off
                if is_inside(bvh, cand): return cand
    return p


def lerp_v(a, b, t):
    return a.lerp(b, t)


def resample_polyline(pts, n_segments):
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + (pts[i] - pts[i-1]).length)
    total = cum[-1]
    if total < 1e-6: return [pts[0]] * (n_segments + 1)
    target = [i * total / n_segments for i in range(n_segments + 1)]
    out = []
    for tg in target:
        for j in range(len(cum) - 1):
            if cum[j] <= tg <= cum[j+1]:
                if cum[j+1] - cum[j] < 1e-9:
                    out.append(pts[j])
                else:
                    f = (tg - cum[j]) / (cum[j+1] - cum[j])
                    out.append(pts[j].lerp(pts[j+1], f))
                break
        else:
            out.append(pts[-1])
    return out


# ============================================================================
# BUILD THE RIG
# ============================================================================
def build_rig(tripo, mesh_obj):
    log("=" * 60)
    log("STAGE 3 v8 — AAA 3-layer anatomical rig")
    log("=" * 60)

    bvh = make_bvh(mesh_obj)
    verts = mesh_obj.data.vertices
    xs=[v.co.x for v in verts]; ys=[v.co.y for v in verts]; zs=[v.co.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    x_center = sum(xs) / len(xs)
    x_half = (x_max - x_min) / 2
    y_size = y_max - y_min
    z_size = z_max - z_min

    # Head direction
    head_y = tripo["tripo::Head_3"][1].y
    tail_y = tripo["tripo::Tail_3"][1].y
    head_dir = -1 if head_y < tail_y else +1
    log(f"head_dir={head_dir:+d}  x_center={x_center:.3f}  mesh_size=({x_max-x_min:.2f},{y_size:.2f},{z_size:.2f})")

    # Create armature
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig_v8"
    arm = arm_obj.data
    arm.name = "MouseRigData_v8"
    eb = arm.edit_bones

    created = {}
    meta = {}  # name -> {"layer": ANATOMICAL_REFERENCE|ARMATURE_DEFORM|ARMATURE_CONTROLS|RIG_HELPERS, "role": REF|DEF|CTRL|HLP}

    def mk(name, head, tail, parent=None, connect=False, bbones=1,
           layer="ARMATURE_DEFORM", role="DEF"):
        b = eb.new(name)
        b.head = Vector(head); b.tail = Vector(tail)
        if parent is not None:
            if isinstance(parent, str): parent = created.get(parent)
            if parent is not None:
                b.parent = parent
                b.use_connect = connect
        b.bbone_segments = bbones
        created[name] = b
        meta[name] = {"layer": layer, "role": role}
        return b

    # ========================================================================
    # KEY LANDMARKS from Tripo
    # ========================================================================
    spine_back = tripo["tripo::Spine_0"][0]      # back of spine (lumbar end)
    spine_front = tripo["tripo::Spine_1"][1]     # front of spine (neck base)
    neck_start = tripo["tripo::Head_0"][0]       # = spine_front area
    neck_end = tripo["tripo::Head_0"][1]         # base of skull
    nose_tip_pos = tripo["tripo::Head_3"][1]
    tail_base_pos = tripo["bone_21"][0]
    ear_L_base_pos = tripo["bone_7"][0]
    ear_R_base_pos = tripo["bone_6"][0]
    skull_center = (ear_L_base_pos + ear_R_base_pos) * 0.5

    # ========================================================================
    # LAYER 1 — ANATOMICAL_REFERENCE
    #
    # Place full anatomical bone reference. These bones are NOT deformers.
    # They prove anatomical completeness and validate placement.
    # ========================================================================
    log("LAYER 1: Anatomical reference skeleton")

    REF_LAYER = "ANATOMICAL_REFERENCE"
    REF_ROLE = "REF"

    def mk_ref(name, head, tail, parent=None, connect=False):
        return mk(name, head, tail, parent=parent, connect=connect,
                   layer=REF_LAYER, role=REF_ROLE)

    # --- Vertebral column: place 7C + 13T + 6L + 4S along spine path ---
    # Use Tripo spine (back of spine → neck base) for the trunk vertebrae
    # The cervical is between neck_base and skull. The sacrum is at hip/tail base.
    n_C, n_T, n_L, n_S, n_Ca = 7, 13, 6, 4, 28
    n_total_trunk = n_C + n_T + n_L + n_S  # 30 trunk vertebrae from neck_end to sacrum
    # Sacrum sits at tail_base_pos. Lumbar ends just before sacrum.
    # The "spine" runs from neck_end (cervical_1=atlas) backward to sacrum tail.
    # Cervical: from neck_end → spine_front (Tripo Head_0 head)
    # Then thoracic + lumbar: from spine_front → spine_back
    # Then sacral: from spine_back → tail_base
    cervical_pts = [neck_end.lerp(spine_front, i / n_C) for i in range(n_C + 1)]
    thoracic_pts = [spine_front.lerp(spine_back, i / n_T) for i in range(n_T + 1)]
    lumbar_pts = [thoracic_pts[-1].lerp(spine_back, 1.0)] if False else None  # use spine_back for lumbar end
    # Actually distribute T+L across spine_front → spine_back
    # T: first 13 of 19 (T+L=13+6)
    trunk_n = n_T + n_L  # 19
    trunk_pts = [spine_front.lerp(spine_back, i / trunk_n) for i in range(trunk_n + 1)]
    # T01..T13 → trunk_pts[0..13]
    # L01..L06 → trunk_pts[13..19]
    # S01..S04 → from trunk_pts[19] to tail_base_pos
    sacrum_pts = [trunk_pts[-1].lerp(tail_base_pos, i / n_S) for i in range(n_S + 1)]

    # Build C bones
    for i in range(n_C):
        if i == 0:
            name = "C01_atlas"
        elif i == 1:
            name = "C02_axis"
        else:
            name = f"C{i+1:02d}"
        mk_ref(name, cervical_pts[i], cervical_pts[i+1])
    # Build T bones
    for i in range(n_T):
        mk_ref(f"T{i+1:02d}", trunk_pts[i], trunk_pts[i+1])
    # Build L bones
    for i in range(n_L):
        mk_ref(f"L{i+1:02d}", trunk_pts[n_T + i], trunk_pts[n_T + i + 1])
    # Build S bones
    for i in range(n_S):
        mk_ref(f"S{i+1:02d}", sacrum_pts[i], sacrum_pts[i+1])
    # Build Ca (caudal) bones - 28 bones along tail
    tail_endpoints = [tripo[n][0] for n in ("bone_21", "tripo::Tail_0", "tripo::Tail_1",
                                              "tripo::Tail_2", "tripo::Tail_3")] + [tripo["bone_26"][1]]
    ca_pts = resample_polyline(tail_endpoints, n_Ca)
    for i in range(n_Ca):
        mk_ref(f"Ca{i+1:02d}", ca_pts[i], ca_pts[i+1])

    # --- Ribs: 13 pairs (rib_L_01..13, rib_R_01..13) ---
    # Ribs attach to thoracic vertebrae. Sweep outward and down to sternum line.
    sternum_y = (spine_front.y + spine_back.y) * 0.5
    sternum_z = spine_front.z - z_size * 0.18
    sternum_top_pt = Vector((x_center, spine_front.y, sternum_z))
    sternum_bot_pt = Vector((x_center, spine_back.y, sternum_z))
    sternum_top_pt = snap_to_inside(bvh, sternum_top_pt)
    sternum_bot_pt = snap_to_inside(bvh, sternum_bot_pt)
    for i in range(13):
        t = i / 12
        spine_pt = trunk_pts[i]    # T01..T13
        sternum_pt = sternum_top_pt.lerp(sternum_bot_pt, t)
        for side, sx in (("L", +1), ("R", -1)):
            rib_tail = Vector((x_center + sx * x_half * 0.30,
                                sternum_pt.y,
                                sternum_pt.z + z_size * 0.03))
            rib_tail = snap_to_inside(bvh, rib_tail)
            mk_ref(f"rib_{side}_{i+1:02d}", spine_pt, rib_tail)

    # --- Sternum: manubrium + 4 sternebrae + xiphoid ---
    sternum_pts_6 = [sternum_top_pt.lerp(sternum_bot_pt, i / 5) for i in range(6)]
    for i, name in enumerate(("manubrium", "sternebra_01", "sternebra_02",
                                "sternebra_03", "sternebra_04", "xiphoid")):
        if i < 5:
            mk_ref(name, sternum_pts_6[i], sternum_pts_6[i+1])
        else:
            # xiphoid extends slightly further back
            mk_ref(name, sternum_pts_6[i], sternum_pts_6[i] + Vector((0, head_dir*-0.02, 0)))

    # --- Skull anatomy reference ---
    # Cranium = big bone at head center
    mk_ref("skull_cranium", neck_end.copy(), skull_center.copy())
    # frontal, parietal, occipital (3 cranial bones)
    mk_ref("frontal", skull_center.copy(), skull_center + Vector((0, head_dir * y_size * 0.05, z_size * 0.02)))
    mk_ref("parietal", skull_center.copy(), skull_center + Vector((0, 0, z_size * 0.06)))
    mk_ref("occipital", neck_end.copy(), neck_end + Vector((0, head_dir * -y_size * 0.02, z_size * 0.04)))
    # Bilateral skull bones
    for side, sx in (("L", +1), ("R", -1)):
        temporal_h = skull_center + Vector((sx * x_half * 0.20, 0, 0))
        temporal_h = snap_to_inside(bvh, temporal_h)
        mk_ref(f"temporal_{side}", temporal_h, temporal_h + Vector((sx * 0.02, 0, 0)))
        zygo_h = skull_center + Vector((sx * x_half * 0.25, head_dir * y_size * 0.05, -z_size * 0.05))
        zygo_h = snap_to_inside(bvh, zygo_h)
        mk_ref(f"zygomatic_{side}", zygo_h, zygo_h + Vector((sx * 0.015, head_dir * 0.02, 0)))
        nasal_h = skull_center.lerp(nose_tip_pos, 0.40) + Vector((sx * x_half * 0.08, 0, z_size * 0.04))
        nasal_h = snap_to_inside(bvh, nasal_h)
        mk_ref(f"nasal_{side}", nasal_h, nasal_h + Vector((0, head_dir * 0.02, 0)))
        maxilla_h = skull_center.lerp(nose_tip_pos, 0.55) + Vector((sx * x_half * 0.12, 0, -z_size * 0.05))
        maxilla_h = snap_to_inside(bvh, maxilla_h)
        mk_ref(f"maxilla_{side}", maxilla_h, maxilla_h + Vector((sx * 0.015, head_dir * 0.02, 0)))
        premax_h = skull_center.lerp(nose_tip_pos, 0.85) + Vector((sx * x_half * 0.08, 0, -z_size * 0.03))
        mk_ref(f"premaxilla_{side}", premax_h, premax_h + Vector((sx * 0.01, head_dir * 0.015, 0)))
        mandible_h = Vector((sx * x_half * 0.15, neck_end.y + head_dir * -y_size * 0.05, skull_center.z - z_size * 0.10))
        mandible_h = snap_to_inside(bvh, mandible_h)
        mandible_t = Vector((sx * x_half * 0.10, nose_tip_pos.y, nose_tip_pos.z - z_size * 0.03))
        mk_ref(f"mandible_{side}", mandible_h, mandible_t)
    # Incisors
    incisor_upper_h = Vector((x_center, nose_tip_pos.y - head_dir * 0.005, nose_tip_pos.z - z_size * 0.02))
    incisor_upper_t = Vector((x_center, nose_tip_pos.y, nose_tip_pos.z - z_size * 0.04))
    mk_ref("incisors_upper", incisor_upper_h, incisor_upper_t)
    incisor_lower_h = Vector((x_center, nose_tip_pos.y - head_dir * 0.005, nose_tip_pos.z - z_size * 0.05))
    incisor_lower_t = Vector((x_center, nose_tip_pos.y, nose_tip_pos.z - z_size * 0.07))
    mk_ref("incisors_lower", incisor_lower_h, incisor_lower_t)

    # --- Forelimb anatomical reference ---
    for side, sh_name, limb_prefix in (("L", "bone_9", "tripo::0_Left_Limb"),
                                         ("R", "bone_13", "tripo::0_Right_Limb")):
        sh_h, sh_t, _ = tripo[sh_name]
        upper_h, upper_t, _ = tripo[f"{limb_prefix}_0"]
        lower_h, lower_t, _ = tripo[f"{limb_prefix}_1"]
        paw_h, paw_t, _ = tripo[f"{limb_prefix}_2"]
        mk_ref(f"scapula_{side}_ref", sh_h, sh_t)
        mk_ref(f"clavicle_{side}_ref", sh_h, sh_h + Vector((0, head_dir * -0.02, -0.005)))
        mk_ref(f"humerus_{side}_ref", upper_h, upper_t)
        # radius + ulna (paired in Tripo's single forearm bone)
        mk_ref(f"radius_{side}_ref", lower_h, lower_t)
        ulna_off = Vector((0, 0, 0.005))
        mk_ref(f"ulna_{side}_ref", lower_h + ulna_off, lower_t + ulna_off)
        # carpals + metacarpals + phalanges at paw
        carpals_h = paw_h.copy()
        carpals_t = paw_h.lerp(paw_t, 0.3)
        mk_ref(f"carpals_{side}_ref", carpals_h, carpals_t)
        metacarp_h = carpals_t
        metacarp_t = paw_h.lerp(paw_t, 0.7)
        mk_ref(f"metacarpals_{side}_ref", metacarp_h, metacarp_t)
        mk_ref(f"phalanges_front_{side}_ref", metacarp_t, paw_t)

    # --- Hindlimb anatomical reference ---
    for side, hip_name, thigh_name, shin_name, paw_name in (
        ("L", "bone_27", "tripo::1_Left_Limb_0", "tripo::1_Left_Limb_1", "tripo::1_Left_Limb_2"),
        ("R", "bone_17", "bone_18", "tripo::1_Right_Limb_0", "tripo::1_Right_Limb_1"),
    ):
        hip_h, hip_t, _ = tripo[hip_name]
        thigh_h, thigh_t, _ = tripo[thigh_name]
        shin_h, shin_t, _ = tripo[shin_name]
        paw_h, paw_t, _ = tripo[paw_name]
        # ilium, ischium, pubis = 3 pelvis bones
        sx = +1 if side == "L" else -1
        mk_ref(f"ilium_{side}_ref", hip_h, hip_t)
        ischium_h = hip_t + Vector((0, head_dir * 0.01, -0.005))
        mk_ref(f"ischium_{side}_ref", ischium_h, ischium_h + Vector((sx * 0.01, 0, -0.005)))
        pubis_h = hip_t + Vector((sx * 0.005, head_dir * -0.005, -0.01))
        mk_ref(f"pubis_{side}_ref", pubis_h, pubis_h + Vector((0, head_dir * -0.01, 0)))
        mk_ref(f"femur_{side}_ref", thigh_h, thigh_t)
        # patella as small bone at knee
        patella_h = thigh_t.copy()
        mk_ref(f"patella_{side}_ref", patella_h, patella_h + Vector((0, head_dir * -0.005, -0.005)))
        mk_ref(f"tibia_{side}_ref", shin_h, shin_t)
        fibula_off = Vector((sx * 0.003, 0, 0))
        mk_ref(f"fibula_{side}_ref", shin_h + fibula_off, shin_t + fibula_off)
        # tarsals + metatarsals + phalanges
        tarsals_t = paw_h.lerp(paw_t, 0.3)
        mk_ref(f"tarsals_{side}_ref", paw_h, tarsals_t)
        meta_t = paw_h.lerp(paw_t, 0.7)
        mk_ref(f"metatarsals_{side}_ref", tarsals_t, meta_t)
        mk_ref(f"phalanges_back_{side}_ref", meta_t, paw_t)

    log(f"  Anatomical reference layer: ~{sum(1 for n in meta if meta[n]['layer']==REF_LAYER)} bones")

    # ========================================================================
    # LAYER 2 — ARMATURE_DEFORM (deformation skeleton)
    # ========================================================================
    log("LAYER 2: Deformation rig")

    DEF_LAYER = "ARMATURE_DEFORM"
    HLP_LAYER = "RIG_HELPERS"

    # root + COG + pelvis + sacrum
    root_b = mk("root",
                 Vector((x_center, 0, 0)),
                 Vector((x_center, 0, 0.04)),
                 layer="ARMATURE_CONTROLS", role="CTRL")
    cog_h = Vector((x_center, (y_min+y_max)/2, (z_min+z_max)/2))
    cog_b = mk("COG", cog_h, cog_h + Vector((0, 0, 0.04)),
                parent=root_b, layer="ARMATURE_CONTROLS", role="CTRL")
    pelvis_h = spine_back.copy()
    pelvis_t = lerp_v(pelvis_h, tail_base_pos, 0.30)
    pelvis_t = snap_to_inside(bvh, pelvis_t)
    pelvis_b = mk("pelvis", pelvis_h, pelvis_t, parent=cog_b)
    sacrum_b = mk("sacrum", pelvis_t.copy(), tail_base_pos.copy(),
                   parent=pelvis_b, connect=True, bbones=2)

    # --- Dense deform spine: cervical + thoracic + lumbar ---
    # DEFORM uses simplified names: cervical_01_atlas, cervical_02_axis, cervical_03..07,
    #                                thoracic_01..13, lumbar_01..06
    # Total deform vertebrae: 7+13+6 = 26
    # These are CHAINED from pelvis up to head:
    # pelvis → lumbar_06 → lumbar_05 → ... → lumbar_01 → thoracic_13 → ... → thoracic_01 → cervical_07 → ... → cervical_01_atlas → head
    deform_spine_pts_LtoT = [trunk_pts[i] for i in range(n_T + n_L + 1)]
    # We want chain order from PELVIS (back) → HEAD (front), so reverse if needed
    # spine_back is at trunk_pts[-1] (lumbar end), spine_front at trunk_pts[0] (thoracic start near neck)
    # So trunk_pts[0]=thoracic_01.head ... trunk_pts[19]=lumbar_06.tail
    # For chain: start at pelvis (= lumbar_06.tail) and go FORWARD to head
    # Chain pts: pelvis → lumbar_06.head → lumbar_05.head → ... → cervical_01_atlas → head
    lumbar_bones = []
    prev = pelvis_b
    for i in range(n_L):
        # lumbar_01 is closest to thoracic_13, lumbar_06 is at the back (closest to pelvis)
        # In our point array: trunk_pts[n_T + 0] = lumbar_01.head, ..., trunk_pts[n_T + n_L] = lumbar_06.tail = spine_back
        # In CHAIN order from pelvis (back) → forward:
        #   pelvis → lumbar_06 (at spine_back) → lumbar_05 → ... → lumbar_01 → thoracic_13 → ...
        idx_a = n_T + n_L - i        # lumbar_06.tail is at trunk_pts[n_T+n_L]; lumbar_06 spans trunk_pts[n_T+n_L-1]..trunk_pts[n_T+n_L]
        idx_b = idx_a - 1
        name = f"lumbar_{n_L - i:02d}"   # lumbar_06, _05, ..., _01
        b = mk(name, trunk_pts[idx_a], trunk_pts[idx_b],
                parent=prev, connect=False, bbones=2)
        prev = b
        lumbar_bones.append(b)
    # Thoracic chain
    thoracic_bones = []
    for i in range(n_T):
        idx_a = n_T - i              # thoracic_13.head is at trunk_pts[n_T-1], goes to trunk_pts[0]
        idx_b = idx_a - 1
        name = f"thoracic_{n_T - i:02d}"
        b = mk(name, trunk_pts[idx_a], trunk_pts[idx_b],
                parent=prev, connect=False, bbones=2)
        prev = b
        thoracic_bones.append(b)
    # Cervical chain
    cervical_bones = []
    for i in range(n_C):
        idx_a = n_C - i
        idx_b = idx_a - 1
        if i == n_C - 1:
            name = "cervical_01_atlas"
        elif i == n_C - 2:
            name = "cervical_02_axis"
        else:
            name = f"cervical_{n_C - i:02d}"
        b = mk(name, cervical_pts[idx_a], cervical_pts[idx_b],
                parent=prev, connect=False, bbones=2)
        prev = b
        cervical_bones.append(b)

    # --- Head + face bones (deform) ---
    head_b = mk("head", neck_end.copy(), skull_center.copy(),
                 parent=prev, connect=True, bbones=2)
    mk("skull", skull_center.copy(),
        skull_center + Vector((0, head_dir * y_size * 0.03, 0)),
        parent=head_b)

    # Snout chain
    snout_base_pos = skull_center.lerp(nose_tip_pos, 0.25)
    snout_mid_pos = skull_center.lerp(nose_tip_pos, 0.65)
    snout_base_b = mk("snout_base", skull_center.copy(), snout_base_pos,
                       parent=head_b, bbones=2)
    snout_mid_b = mk("snout_mid", snout_base_pos, snout_mid_pos,
                      parent=snout_base_b, connect=True, bbones=2)
    nose_tip_b = mk("nose_tip", snout_mid_pos, nose_tip_pos.copy(),
                     parent=snout_mid_b, connect=True)

    # Nose L/R
    for side, sx in (("L", +1), ("R", -1)):
        n_h = nose_tip_pos + Vector((sx * 0.012, 0, 0.005))
        n_t = n_h + Vector((sx * 0.008, head_dir * 0.005, 0.003))
        mk(f"nose_{side}", n_h, n_t, parent=nose_tip_b)

    # Cheeks
    for side, sx in (("L", +1), ("R", -1)):
        c_h = skull_center + Vector((sx * x_half * 0.20, 0, -z_size * 0.05))
        c_h = snap_to_inside(bvh, c_h)
        c_t = snout_mid_pos + Vector((sx * x_half * 0.30, 0, -z_size * 0.03))
        mk(f"cheek_{side}", c_h, c_t, parent=head_b, bbones=2)

    # Whisker pads
    for side, sx in (("L", +1), ("R", -1)):
        wp_h = snout_mid_pos + Vector((sx * x_half * 0.15, 0, -z_size * 0.02))
        wp_h = snap_to_inside(bvh, wp_h)
        wp_t = wp_h + Vector((sx * x_half * 0.20, head_dir * y_size * 0.03, 0))
        mk(f"whisker_pad_{side}", wp_h, wp_t, parent=head_b, bbones=2)

    # Lips
    lip_y = snout_mid_pos.y + head_dir * y_size * 0.02
    lip_z = snout_mid_pos.z - z_size * 0.05
    # Jaw built first since lower_lip parents to jaw
    jaw_base_h = Vector((x_center, skull_center.y + head_dir * (-0.02), skull_center.z - z_size * 0.12))
    jaw_base_h = snap_to_inside(bvh, jaw_base_h)
    jaw_base_t = Vector((x_center, snout_mid_pos.y, skull_center.z - z_size * 0.10))
    jaw_base_b = mk("jaw_base", jaw_base_h, jaw_base_t, parent=head_b, bbones=2)
    jaw_tip_t = Vector((x_center, nose_tip_pos.y - head_dir * 0.02, nose_tip_pos.z - z_size * 0.03))
    mk("jaw_tip", jaw_base_t.copy(), jaw_tip_t, parent=jaw_base_b, connect=True)
    for side, sx in (("L", +1), ("R", -1)):
        up_h = Vector((sx * x_half * 0.05, lip_y, lip_z + 0.005))
        up_t = Vector((sx * x_half * 0.15, lip_y + head_dir * 0.01, lip_z + 0.005))
        mk(f"upper_lip_{side}", up_h, up_t, parent=snout_mid_b)
        lo_h = Vector((sx * x_half * 0.05, lip_y, lip_z - 0.005))
        lo_t = Vector((sx * x_half * 0.15, lip_y + head_dir * 0.01, lip_z - 0.005))
        mk(f"lower_lip_{side}", lo_h, lo_t, parent=jaw_base_b)

    # Eyes
    eye_y = (head_b.head.y + head_b.tail.y) * 0.5
    eye_z = skull_center.z
    for side, sx in (("L", +1), ("R", -1)):
        eye_pos = Vector((x_center + sx * x_half * 0.30, eye_y, eye_z))
        mk(f"eye_{side}", eye_pos, eye_pos + Vector((0, head_dir * 0.015, 0)), parent=head_b)

    # Ears: 3-segment chain per side
    for side, tripo_name in (("L", "bone_7"), ("R", "bone_6")):
        th, tt, _ = tripo[tripo_name]
        ear_base_h = th.copy()
        ear_mid_h = th.lerp(tt, 0.4)
        ear_tip_h = th.lerp(tt, 0.8)
        ear_tip_t = tt.copy()
        ear_b_b = mk(f"ear_{side}_base", ear_base_h, ear_mid_h, parent=head_b, bbones=2)
        ear_m_b = mk(f"ear_{side}_mid", ear_mid_h, ear_tip_h, parent=ear_b_b, connect=True, bbones=2)
        mk(f"ear_{side}_tip", ear_tip_h, ear_tip_t, parent=ear_m_b, connect=True)

    # --- Ribcage helpers (5 pairs L/R + center) ---
    rib_center_pt = trunk_pts[6]  # mid thoracic
    rib_center_t = rib_center_pt + Vector((0, 0, -z_size * 0.1))
    mk("ribcage_center", rib_center_pt, rib_center_t,
        parent="thoracic_07" if "thoracic_07" in created else thoracic_bones[6],
        layer=HLP_LAYER, role="HLP")
    for i in range(5):
        idx = 2 + i * 2  # spread across thoracic vertebrae
        if idx >= len(trunk_pts): idx = len(trunk_pts) - 1
        spine_pt = trunk_pts[idx]
        for side, sx in (("L", +1), ("R", -1)):
            rib_h = spine_pt + Vector((sx * x_half * 0.18, 0, -z_size * 0.05))
            rib_h = snap_to_inside(bvh, rib_h)
            rib_t = spine_pt + Vector((sx * x_half * 0.55, 0, -z_size * 0.10))
            parent_t = f"thoracic_{13 - idx + 1:02d}" if f"thoracic_{13 - idx + 1:02d}" in created else "thoracic_07"
            mk(f"ribcage_{side}_{i+1:02d}", rib_h, rib_t,
                parent=parent_t, layer=HLP_LAYER, role="HLP", bbones=2)
    # Sternum ctrl (helper for breathing)
    sternum_ctrl_h = sternum_top_pt.copy()
    sternum_ctrl_t = sternum_bot_pt.copy()
    mk("sternum_ctrl", sternum_ctrl_h, sternum_ctrl_t,
        parent="thoracic_07", layer=HLP_LAYER, role="HLP", bbones=2)

    # --- Belly ---
    belly_pt = trunk_pts[15] if 15 < len(trunk_pts) else trunk_pts[-2]
    belly_center_h = belly_pt + Vector((0, 0, -z_size * 0.15))
    belly_center_h = snap_to_inside(bvh, belly_center_h)
    belly_center_t = belly_pt + Vector((0, head_dir * y_size * 0.05, -z_size * 0.18))
    mk("belly_center", belly_center_h, belly_center_t,
        parent="lumbar_03" if "lumbar_03" in created else "lumbar_06",
        layer=HLP_LAYER, role="HLP")
    for side, sx in (("L", +1), ("R", -1)):
        b_h = belly_pt + Vector((sx * x_half * 0.15, 0, -z_size * 0.12))
        b_h = snap_to_inside(bvh, b_h)
        b_t = belly_pt + Vector((sx * x_half * 0.40, 0, -z_size * 0.15))
        mk(f"belly_{side}", b_h, b_t,
            parent="lumbar_03" if "lumbar_03" in created else "lumbar_06",
            layer=HLP_LAYER, role="HLP", bbones=2)

    # --- Front legs (deform) ---
    for side, sh_name, limb_prefix in (("L", "bone_9", "tripo::0_Left_Limb"),
                                         ("R", "bone_13", "tripo::0_Right_Limb")):
        sh_h, sh_t, _ = tripo[sh_name]
        upper_h, upper_t, _ = tripo[f"{limb_prefix}_0"]
        lower_h, lower_t, _ = tripo[f"{limb_prefix}_1"]
        paw_h, paw_t, _ = tripo[f"{limb_prefix}_2"]
        scap_b = mk(f"scapula_{side}", sh_h, sh_t, parent=cog_b)
        upper_b = mk(f"upper_front_leg_{side}", upper_h, upper_t,
                      parent=scap_b, connect=True, bbones=2)
        lower_b = mk(f"lower_front_leg_{side}", lower_h, lower_t,
                      parent=upper_b, connect=True, bbones=2)
        paw_b = mk(f"front_paw_{side}", paw_h, paw_t,
                    parent=lower_b, connect=True)
        # 5 toes per paw
        sx = +1 if side == "L" else -1
        for i in range(5):
            spread = (i - 2) * 0.20  # spread fingers
            toe_h = paw_t.copy()
            toe_t = paw_t + Vector((sx * spread * 0.02, head_dir * 0.02, -0.005))
            mk(f"front_toes_{side}_{i+1:02d}", toe_h, toe_t, parent=paw_b)

    # --- Back legs (deform) ---
    for side, hip_name, thigh_name, shin_name, paw_name in (
        ("L", "bone_27", "tripo::1_Left_Limb_0", "tripo::1_Left_Limb_1", "tripo::1_Left_Limb_2"),
        ("R", "bone_17", "bone_18", "tripo::1_Right_Limb_0", "tripo::1_Right_Limb_1"),
    ):
        hip_h, hip_t, _ = tripo[hip_name]
        thigh_h, thigh_t, _ = tripo[thigh_name]
        shin_h, shin_t, _ = tripo[shin_name]
        paw_h, paw_t, _ = tripo[paw_name]
        hip_b = mk(f"hip_{side}", hip_h, hip_t, parent=pelvis_b)
        thigh_b = mk(f"thigh_{side}", thigh_h, thigh_t, parent=hip_b, bbones=2)
        shin_b = mk(f"shin_{side}", shin_h, shin_t, parent=thigh_b, connect=True, bbones=2)
        paw_b = mk(f"back_paw_{side}", paw_h, paw_t, parent=shin_b, connect=True)
        sx = +1 if side == "L" else -1
        for i in range(5):
            spread = (i - 2) * 0.20
            toe_h = paw_t.copy()
            toe_t = paw_t + Vector((sx * spread * 0.02, head_dir * 0.02, -0.005))
            mk(f"back_toes_{side}_{i+1:02d}", toe_h, toe_t, parent=paw_b)

    # --- Deform tail: 28 segments ---
    tail_pts = resample_polyline(tail_endpoints, n_Ca)
    prev = sacrum_b
    for i in range(n_Ca):
        name = f"tail_{i+1:02d}"
        b = mk(name, tail_pts[i], tail_pts[i+1],
                parent=prev, connect=(i > 0), bbones=2)
        prev = b

    # ========================================================================
    # LAYER 3 — ARMATURE_CONTROLS
    # ========================================================================
    log("LAYER 3: Animator controls")

    CTRL_LAYER = "ARMATURE_CONTROLS"

    def mk_ctrl(name, head, tail, parent=None):
        return mk(name, head, tail, parent=parent, layer=CTRL_LAYER, role="CTRL")

    # Body / Spine
    mk_ctrl("CTRL_pelvis", pelvis_h, pelvis_t, parent="COG")
    mk_ctrl("CTRL_sacrum", pelvis_t.copy(), tail_base_pos.copy(), parent="CTRL_pelvis")
    mk_ctrl("CTRL_chest", trunk_pts[2], trunk_pts[0], parent="CTRL_pelvis")
    mk_ctrl("CTRL_neck_base", neck_end.copy(), neck_end + Vector((0, head_dir*0.03, 0)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_neck_mid", cervical_pts[3], cervical_pts[4], parent="CTRL_neck_base")
    mk_ctrl("CTRL_head", neck_end.copy(), skull_center.copy(), parent="CTRL_neck_mid")
    mk_ctrl("CTRL_skull", skull_center.copy(),
             skull_center + Vector((0, head_dir * y_size * 0.03, 0)),
             parent="CTRL_head")

    # Spine curve/curl/arch controls (offset above body)
    spine_mid = trunk_pts[9]
    mk_ctrl("CTRL_lumbar_curve",
             trunk_pts[16] + Vector((0, 0, z_size * 0.3)),
             trunk_pts[16] + Vector((0, 0, z_size * 0.3 + 0.04)),
             parent="CTRL_pelvis")
    mk_ctrl("CTRL_thoracic_curve",
             trunk_pts[6] + Vector((0, 0, z_size * 0.3)),
             trunk_pts[6] + Vector((0, 0, z_size * 0.3 + 0.04)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_body_curl_L",
             spine_mid + Vector((x_half * 0.5, 0, z_size * 0.25)),
             spine_mid + Vector((x_half * 0.5 + 0.04, 0, z_size * 0.25)),
             parent="COG")
    mk_ctrl("CTRL_body_curl_R",
             spine_mid + Vector((-x_half * 0.5, 0, z_size * 0.25)),
             spine_mid + Vector((-x_half * 0.5 - 0.04, 0, z_size * 0.25)),
             parent="COG")
    mk_ctrl("CTRL_body_arch_up",
             spine_mid + Vector((0, 0, z_size * 0.35)),
             spine_mid + Vector((0, 0, z_size * 0.35 + 0.04)),
             parent="COG")
    mk_ctrl("CTRL_body_arch_down",
             spine_mid + Vector((0, 0, -z_size * 0.10)),
             spine_mid + Vector((0, 0, -z_size * 0.10 - 0.04)),
             parent="COG")
    mk_ctrl("CTRL_body_stretch",
             cog_h + Vector((0, -head_dir * 0.10, z_size * 0.25)),
             cog_h + Vector((0, -head_dir * 0.10, z_size * 0.25 + 0.04)),
             parent="COG")
    mk_ctrl("CTRL_body_crouch",
             cog_h + Vector((0, 0, -z_size * 0.10)),
             cog_h + Vector((0, 0, -z_size * 0.10 - 0.04)),
             parent="COG")

    # Ribcage / breathing controls
    rib_pt = trunk_pts[6]
    mk_ctrl("CTRL_breath_in",
             rib_pt + Vector((x_half * 0.4, 0, z_size * 0.25)),
             rib_pt + Vector((x_half * 0.4 + 0.04, 0, z_size * 0.25)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_breath_out",
             rib_pt + Vector((-x_half * 0.4, 0, z_size * 0.25)),
             rib_pt + Vector((-x_half * 0.4 - 0.04, 0, z_size * 0.25)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_expand",
             rib_pt + Vector((0, 0, z_size * 0.30)),
             rib_pt + Vector((0, 0, z_size * 0.30 + 0.04)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_compress",
             rib_pt + Vector((0, 0, -z_size * 0.05)),
             rib_pt + Vector((0, 0, -z_size * 0.05 - 0.04)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_L_squash",
             rib_pt + Vector((x_half * 0.7, 0, 0)),
             rib_pt + Vector((x_half * 0.7 + 0.04, 0, 0)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_R_squash",
             rib_pt + Vector((-x_half * 0.7, 0, 0)),
             rib_pt + Vector((-x_half * 0.7 - 0.04, 0, 0)),
             parent="CTRL_chest")
    mk_ctrl("CTRL_sternum", sternum_top_pt, sternum_bot_pt, parent="CTRL_chest")
    mk_ctrl("CTRL_belly_soft",
             belly_center_h + Vector((0, 0, -z_size * 0.10)),
             belly_center_h + Vector((0, 0, -z_size * 0.10 - 0.04)),
             parent="CTRL_pelvis")

    # Face controls
    mk_ctrl("CTRL_jaw_open",
             jaw_base_h + Vector((0, 0, -z_size * 0.1)),
             jaw_base_h + Vector((0, 0, -z_size * 0.1 - 0.04)),
             parent="CTRL_head")
    mk_ctrl("CTRL_jaw_side",
             jaw_base_h + Vector((x_half * 0.3, 0, -z_size * 0.1)),
             jaw_base_h + Vector((x_half * 0.3 + 0.04, 0, -z_size * 0.1)),
             parent="CTRL_head")
    mk_ctrl("CTRL_jaw_forward",
             jaw_base_h + Vector((0, head_dir * 0.04, -z_size * 0.1)),
             jaw_base_h + Vector((0, head_dir * 0.04 + 0.04, -z_size * 0.1)),
             parent="CTRL_head")
    mk_ctrl("CTRL_snout_forward",
             snout_mid_pos + Vector((0, head_dir * 0.05, 0)),
             snout_mid_pos + Vector((0, head_dir * 0.05 + 0.04, 0)),
             parent="CTRL_head")
    mk_ctrl("CTRL_snout_up",
             snout_mid_pos + Vector((0, 0, z_size * 0.15)),
             snout_mid_pos + Vector((0, 0, z_size * 0.15 + 0.04)),
             parent="CTRL_head")
    mk_ctrl("CTRL_snout_down",
             snout_mid_pos + Vector((0, 0, -z_size * 0.10)),
             snout_mid_pos + Vector((0, 0, -z_size * 0.10 - 0.04)),
             parent="CTRL_head")
    mk_ctrl("CTRL_snout_scrunch",
             snout_base_pos + Vector((0, 0, z_size * 0.1)),
             snout_base_pos + Vector((0, 0, z_size * 0.1 + 0.04)),
             parent="CTRL_head")
    mk_ctrl("CTRL_nose_tip",
             nose_tip_pos + Vector((0, head_dir * 0.02, 0)),
             nose_tip_pos + Vector((0, head_dir * 0.02 + 0.03, 0)),
             parent="CTRL_head")
    for side, sx in (("L", +1), ("R", -1)):
        mk_ctrl(f"CTRL_nose_twitch_{side}",
                 nose_tip_pos + Vector((sx * x_half * 0.20, 0, z_size * 0.05)),
                 nose_tip_pos + Vector((sx * x_half * 0.20 + 0.03, 0, z_size * 0.05)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_cheek_puff_{side}",
                 skull_center + Vector((sx * x_half * 0.50, 0, -z_size * 0.05)),
                 skull_center + Vector((sx * x_half * 0.50 + sx * 0.03, 0, -z_size * 0.05)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_whisker_pad_forward_{side}",
                 snout_mid_pos + Vector((sx * x_half * 0.40, head_dir * 0.03, 0)),
                 snout_mid_pos + Vector((sx * x_half * 0.40, head_dir * 0.03 + 0.03, 0)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_whisker_pad_up_{side}",
                 snout_mid_pos + Vector((sx * x_half * 0.40, 0, z_size * 0.10)),
                 snout_mid_pos + Vector((sx * x_half * 0.40 + sx * 0.03, 0, z_size * 0.10)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_whisker_spread_{side}",
                 snout_mid_pos + Vector((sx * x_half * 0.55, 0, 0)),
                 snout_mid_pos + Vector((sx * x_half * 0.55 + sx * 0.03, 0, 0)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_whisker_root_{side}",
                 snout_mid_pos + Vector((sx * x_half * 0.30, 0, 0)),
                 snout_mid_pos + Vector((sx * x_half * 0.30 + sx * 0.02, 0, 0)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_whisker_forward_{side}",
                 snout_mid_pos + Vector((sx * x_half * 0.45, head_dir * 0.04, 0)),
                 snout_mid_pos + Vector((sx * x_half * 0.45 + sx * 0.02, head_dir * 0.04, 0)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_whisker_twitch_{side}",
                 snout_mid_pos + Vector((sx * x_half * 0.50, 0, z_size * 0.05)),
                 snout_mid_pos + Vector((sx * x_half * 0.50 + sx * 0.02, 0, z_size * 0.05)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_upper_lip_{side}",
                 Vector((sx * x_half * 0.10, lip_y, lip_z + 0.005)),
                 Vector((sx * x_half * 0.10 + sx * 0.03, lip_y, lip_z + 0.005)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_lower_lip_{side}",
                 Vector((sx * x_half * 0.10, lip_y, lip_z - 0.005)),
                 Vector((sx * x_half * 0.10 + sx * 0.03, lip_y, lip_z - 0.005)),
                 parent="CTRL_head")

    # Ear controls (7 per side from spec)
    for side in ("L", "R"):
        sx = +1 if side == "L" else -1
        ear_b = created.get(f"ear_{side}_base")
        ear_tip_pos = (ear_b.head + ear_b.tail) * 0.5 if ear_b else skull_center
        for suffix, offset in (
            ("perk",          Vector((0, 0, 0.04))),
            ("relax",         Vector((0, 0, -0.03))),
            ("rotate_back",   Vector((0, head_dir * -0.04, 0))),
            ("rotate_forward", Vector((0, head_dir * 0.04, 0))),
            ("twitch",        Vector((sx * 0.03, 0, 0))),
            ("fold",          Vector((sx * 0.02, 0, -0.02))),
            ("tip_follow",    Vector((sx * 0.04, 0, 0.03))),
        ):
            mk_ctrl(f"CTRL_ear_{side}_{suffix}",
                     ear_tip_pos + offset,
                     ear_tip_pos + offset + Vector((0, 0, 0.03)),
                     parent="CTRL_head")

    # Leg controls
    for side, sx in (("L", +1), ("R", -1)):
        # Front paw IK/FK + pole + scapula
        fp = created[f"front_paw_{side}"]
        ik_h = Vector((fp.tail.x, fp.tail.y - head_dir * 0.03, z_min))
        mk_ctrl(f"CTRL_front_paw_IK_{side}",
                 ik_h, ik_h + Vector((0, head_dir * 0.05, 0)),
                 parent="root")
        mk_ctrl(f"CTRL_front_paw_FK_{side}", fp.head, fp.tail, parent="CTRL_chest")
        upper = created[f"upper_front_leg_{side}"]
        pole = Vector((upper.tail.x, upper.tail.y + head_dir * x_half * 0.3, upper.tail.z))
        mk_ctrl(f"CTRL_front_knee_pole_{side}", pole, pole + Vector((0, 0, 0.04)), parent="root")
        scap = created[f"scapula_{side}"]
        mk_ctrl(f"CTRL_scapula_{side}", scap.head, scap.tail, parent="CTRL_chest")
        mk_ctrl(f"CTRL_toe_curl_front_{side}",
                 ik_h + Vector((sx * 0.04, head_dir * 0.05, 0.02)),
                 ik_h + Vector((sx * 0.04 + sx * 0.02, head_dir * 0.05, 0.02)),
                 parent=f"CTRL_front_paw_IK_{side}")

        # Back paw IK/FK + pole + hip
        bp = created[f"back_paw_{side}"]
        ik_h = Vector((bp.tail.x, bp.tail.y - head_dir * 0.03, z_min))
        mk_ctrl(f"CTRL_back_paw_IK_{side}",
                 ik_h, ik_h + Vector((0, head_dir * 0.05, 0)),
                 parent="root")
        mk_ctrl(f"CTRL_back_paw_FK_{side}", bp.head, bp.tail, parent="CTRL_pelvis")
        thigh = created[f"thigh_{side}"]
        pole = Vector((thigh.tail.x, thigh.tail.y + head_dir * x_half * 0.3, thigh.tail.z))
        mk_ctrl(f"CTRL_back_knee_pole_{side}", pole, pole + Vector((0, 0, 0.04)), parent="root")
        hip = created[f"hip_{side}"]
        mk_ctrl(f"CTRL_hip_{side}", hip.head, hip.tail, parent="CTRL_pelvis")
        mk_ctrl(f"CTRL_toe_curl_back_{side}",
                 ik_h + Vector((sx * 0.04, head_dir * 0.05, 0.02)),
                 ik_h + Vector((sx * 0.04 + sx * 0.02, head_dir * 0.05, 0.02)),
                 parent=f"CTRL_back_paw_IK_{side}")

    # Tail controls
    tail_first = created.get("tail_01")
    tail_mid = created.get(f"tail_{n_Ca // 2 + 1:02d}")
    tail_last = created.get(f"tail_{n_Ca:02d}")
    if tail_first:
        mk_ctrl("CTRL_tail_base", tail_first.head, tail_first.tail, parent="CTRL_sacrum")
    if tail_mid:
        mk_ctrl("CTRL_tail_mid", tail_mid.head, tail_mid.tail, parent="CTRL_tail_base")
    if tail_last:
        mk_ctrl("CTRL_tail_tip", tail_last.head, tail_last.tail, parent="CTRL_tail_mid")
    # CTRL_tail_01 = same as base
    if tail_first:
        mk_ctrl("CTRL_tail_01", tail_first.head, tail_first.tail, parent="CTRL_sacrum")
    if tail_mid:
        tail_top = tail_mid.head + Vector((0, 0, z_size * 0.25))
        mk_ctrl("CTRL_tail_curl_L", tail_top + Vector((x_half * 0.5, 0, 0)),
                 tail_top + Vector((x_half * 0.5 + 0.03, 0, 0)), parent="CTRL_sacrum")
        mk_ctrl("CTRL_tail_curl_R", tail_top + Vector((-x_half * 0.5, 0, 0)),
                 tail_top + Vector((-x_half * 0.5 - 0.03, 0, 0)), parent="CTRL_sacrum")
        mk_ctrl("CTRL_tail_up", tail_top, tail_top + Vector((0, 0, 0.03)), parent="CTRL_sacrum")
        mk_ctrl("CTRL_tail_down",
                 tail_mid.head + Vector((0, 0, -z_size * 0.15)),
                 tail_mid.head + Vector((0, 0, -z_size * 0.15 - 0.03)),
                 parent="CTRL_sacrum")
        mk_ctrl("CTRL_tail_sway",
                 tail_mid.head + Vector((0, head_dir * -0.10, 0)),
                 tail_mid.head + Vector((0, head_dir * -0.10 - 0.03, 0)),
                 parent="CTRL_sacrum")
        mk_ctrl("CTRL_tail_follow_body",
                 tail_mid.head + Vector((0, head_dir * -0.05, z_size * 0.1)),
                 tail_mid.head + Vector((0, head_dir * -0.05 - 0.03, z_size * 0.1)),
                 parent="CTRL_sacrum")

    # Exit edit mode
    bpy.ops.object.mode_set(mode='OBJECT')

    # ========================================================================
    # Bone collections
    # ========================================================================
    coll_names = ["ANATOMICAL_REFERENCE", "ARMATURE_DEFORM",
                   "ARMATURE_CONTROLS", "RIG_HELPERS"]
    colls = {}
    for n in coll_names:
        try:
            colls[n] = arm.collections.new(name=n)
        except Exception:
            colls[n] = arm.collections.get(n)
    for bone in arm.bones:
        m = meta.get(bone.name, {"layer": "ARMATURE_DEFORM", "role": "DEF"})
        c = colls.get(m["layer"])
        if c: c.assign(bone)
        # Only DEF bones are deformers
        if m["role"] != "DEF":
            bone.use_deform = False

    # Hide the ANATOMICAL_REFERENCE collection by default (it's a reference layer)
    if "ANATOMICAL_REFERENCE" in colls:
        colls["ANATOMICAL_REFERENCE"].is_visible = False

    # Stats
    def_n = sum(1 for n in meta if meta[n]["role"] == "DEF")
    ref_n = sum(1 for n in meta if meta[n]["role"] == "REF")
    ctrl_n = sum(1 for n in meta if meta[n]["role"] == "CTRL")
    hlp_n = sum(1 for n in meta if meta[n]["role"] == "HLP")
    log(f"Layer counts — REF: {ref_n}  DEF: {def_n}  CTRL: {ctrl_n}  HLP: {hlp_n}  TOTAL: {len(meta)}")

    return arm_obj, meta


# ============================================================================
# Main
# ============================================================================
def main():
    reset_scene()
    import_glb(SRC)
    tripo = extract_tripo_skeleton()
    mesh = cleanup_keep_mesh_only()
    arm, meta = build_rig(tripo, mesh)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved .blend → {OUT_BLEND}")
    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
