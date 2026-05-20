"""
RIG ONLY v7 — mouse-specific dense rig per detailed spec.

ABSOLUTE RULE: The mesh is NOT modified.

Architecture:
  root → COG → pelvis → sacrum + spine_01..07 → chest → ribcage/belly + neck_01..03 → head → face bones
  pelvis → scapula_L/R → front leg chain
  pelvis → hip_L/R → back leg chain
  sacrum → tail_01..14

~80 deform bones + ~50 control bones = ~130 total.

Bone collections:
- ARMATURE_DEFORM   (DEF bones, the only ones with use_deform=True)
- ARMATURE_CONTROLS (CTRL bones, animator-facing)
- RIG_HELPERS       (MCH bones, mechanism / twist / IK targets)

Usage:
    blender --background --python fare/scripts/rig_mouse_v7.py
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
OUT_BLEND = os.path.join(OUT_DIR, "stage3_rig_v7.blend")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[rig7] {m}", flush=True)


# ============================================================================
# Scene import & Tripo extraction (mesh untouched)
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path} (mesh preserved)")
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
    log(f"Tripo: {len(bones)} bones extracted")
    return bones


def cleanup_keep_mesh_only():
    log("Cleanup (mesh UNTOUCHED)")
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
# BVH + snap helpers
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


# ============================================================================
# Build the rig
# ============================================================================
def build_rig(tripo, mesh_obj):
    log("=" * 60)
    log("STAGE 3 v7 — dense mouse-specific rig")
    log("=" * 60)

    bvh = make_bvh(mesh_obj)
    verts = mesh_obj.data.vertices
    xs=[v.co.x for v in verts]; ys=[v.co.y for v in verts]; zs=[v.co.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    x_center = sum(xs) / len(xs)  # mesh mean (asymmetric mesh)
    x_half = (x_max - x_min) / 2
    y_size = y_max - y_min
    z_size = z_max - z_min
    log(f"AABB X=[{x_min:.3f},{x_max:.3f}] Y=[{y_min:.3f},{y_max:.3f}] Z=[{z_min:.3f},{z_max:.3f}] x_center={x_center:.3f}")

    # Determine head direction from Tripo
    head_y = tripo["tripo::Head_3"][1].y
    tail_y = tripo["tripo::Tail_3"][1].y
    head_dir = -1 if head_y < tail_y else +1
    log(f"Head direction: {'+Y' if head_dir>0 else '-Y'}")

    # Create armature
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig_v7"
    arm = arm_obj.data
    arm.name = "MouseRigData_v7"
    eb = arm.edit_bones

    created = {}        # name -> EditBone
    meta = {}           # name -> {"role": DEF|CTRL|MCH, "collection": str}

    def mk(name, head, tail, parent=None, connect=False, bbones=1, role="DEF", coll="ARMATURE_DEFORM"):
        b = eb.new(name)
        b.head = Vector(head); b.tail = Vector(tail)
        if parent is not None:
            if isinstance(parent, str): parent = created.get(parent)
            if parent is not None:
                b.parent = parent
                b.use_connect = connect
        b.bbone_segments = bbones
        created[name] = b
        meta[name] = {"role": role, "collection": coll}
        return b

    # ========================================================================
    # SPINE: 7 segments between pelvis and chest
    # ========================================================================
    # Tripo's spine endpoints:
    #   spine_0 head = (x, +0.076, +0.311)  back of spine
    #   spine_1 tail = (x, -0.154, +0.291)  front of spine (where neck starts)
    spine_start = tripo["tripo::Spine_0"][0]  # back/hip end
    spine_end   = tripo["tripo::Spine_1"][1]  # chest/neck end
    log(f"Spine span: {spine_start} → {spine_end}")

    # ---- root + COG + pelvis + sacrum ----
    root_size = 0.04
    root_b = mk("root",
                 Vector((x_center, 0.0, 0.0)),
                 Vector((x_center, 0.0, root_size)),
                 role="CTRL", coll="ARMATURE_CONTROLS")
    cog_h = Vector((x_center, (y_min + y_max) / 2, (z_min + z_max) / 2))
    cog_b = mk("COG", cog_h, cog_h + Vector((0, 0, 0.04)),
                parent=root_b, role="CTRL", coll="ARMATURE_CONTROLS")

    # Pelvis (short bone at back of spine)
    tail_base = tripo["bone_21"][0]  # where tail begins
    pelvis_h = spine_start.copy()
    pelvis_t = pelvis_h.lerp(tail_base, 0.30)
    pelvis_t = snap_to_inside(bvh, pelvis_t)
    pelvis_b = mk("pelvis", pelvis_h, pelvis_t, parent=cog_b)

    # Sacrum (bridge to tail)
    sacrum_b = mk("sacrum", pelvis_t.copy(), tail_base.copy(),
                   parent=pelvis_b, connect=True, bbones=2)

    # Spine 7 segments (interpolate between spine_start and spine_end)
    # Spine goes from pelvis (back) to chest (front).
    n_spine = 7
    spine_pts = [spine_start.lerp(spine_end, i / n_spine) for i in range(n_spine + 1)]
    # snap each to mesh interior (axis follows curved body if any)
    spine_pts = [snap_to_inside(bvh, p) for p in spine_pts]
    prev = pelvis_b
    spine_bones = []
    for i in range(n_spine):
        name = f"spine_{i+1:02d}"
        b = mk(name, spine_pts[i], spine_pts[i+1],
                parent=prev, connect=(i > 0), bbones=2)
        spine_bones.append(b)
        prev = b

    # CHEST (between last spine and neck base)
    neck_start = tripo["tripo::Head_0"][0]
    chest_b = mk("chest", spine_pts[-1].copy(), neck_start.copy(),
                  parent=spine_bones[-1], connect=True, bbones=2)

    # ========================================================================
    # RIBCAGE + BELLY helpers
    # ========================================================================
    # Ribcage center under spine_03 (mid-chest), L/R at sides
    chest_mid_pt = spine_pts[3]  # mid spine
    ribcage_center_h = chest_mid_pt + Vector((0, 0, -z_size * 0.05))
    ribcage_center_h = snap_to_inside(bvh, ribcage_center_h)
    ribcage_center_t = ribcage_center_h + Vector((0, 0, -z_size * 0.10))
    mk("ribcage_center", ribcage_center_h, ribcage_center_t,
        parent="spine_04", coll="RIG_HELPERS", role="DEF")

    for side, sx in (("L", +1), ("R", -1)):
        rib_h = chest_mid_pt + Vector((sx * x_half * 0.20, 0, -z_size * 0.05))
        rib_h = snap_to_inside(bvh, rib_h)
        rib_t = chest_mid_pt + Vector((sx * x_half * 0.60, 0, -z_size * 0.10))
        # don't snap tail — let it be at mesh edge
        mk(f"ribcage_{side}", rib_h, rib_t,
            parent="spine_04", coll="RIG_HELPERS", role="DEF", bbones=2)

    # Belly center/L/R under spine_05/06 (lower belly)
    belly_pt = spine_pts[5]
    belly_center_h = belly_pt + Vector((0, 0, -z_size * 0.15))
    belly_center_h = snap_to_inside(bvh, belly_center_h)
    belly_center_t = belly_pt + Vector((0, -head_dir * y_size * 0.05, -z_size * 0.18))
    mk("belly_center", belly_center_h, belly_center_t,
        parent="spine_06", coll="RIG_HELPERS", role="DEF")
    for side, sx in (("L", +1), ("R", -1)):
        belly_h = belly_pt + Vector((sx * x_half * 0.15, 0, -z_size * 0.12))
        belly_h = snap_to_inside(bvh, belly_h)
        belly_t = belly_pt + Vector((sx * x_half * 0.40, 0, -z_size * 0.15))
        mk(f"belly_{side}", belly_h, belly_t,
            parent="spine_06", coll="RIG_HELPERS", role="DEF", bbones=2)

    # ========================================================================
    # NECK chain (3 segments)
    # ========================================================================
    # Neck from chest end to head base. Tripo Head_0 has head=neck_start,
    # tail=neck_end. We subdivide to 3.
    neck_end = tripo["tripo::Head_0"][1]
    neck_pts = [neck_start.lerp(neck_end, i / 3) for i in range(4)]
    neck_pts = [snap_to_inside(bvh, p) for p in neck_pts]
    prev = chest_b
    neck_bones = []
    for i in range(3):
        b = mk(f"neck_{i+1:02d}", neck_pts[i], neck_pts[i+1],
                parent=prev, connect=(i > 0), bbones=2)
        neck_bones.append(b)
        prev = b
    last_neck = neck_bones[-1]

    # ========================================================================
    # HEAD + SKULL + FACE bones
    # ========================================================================
    # Head: from neck end to skull center (between ear bases)
    ear_L_base_pos = tripo["bone_7"][0]   # +X
    ear_R_base_pos = tripo["bone_6"][0]   # -X
    skull_center = (ear_L_base_pos + ear_R_base_pos) * 0.5
    nose_tip_pos = tripo["tripo::Head_3"][1]
    log(f"Skull center: {skull_center}")
    log(f"Nose tip: {nose_tip_pos}")

    head_b = mk("head", neck_end.copy(), skull_center.copy(),
                 parent=last_neck, connect=True, bbones=2)

    # Skull (rigid skull bone — small, inside head)
    skull_h = skull_center.copy()
    skull_t = skull_center + Vector((0, head_dir * y_size * 0.04, 0))
    mk("skull", skull_h, skull_t, parent=head_b)

    # Snout chain: base → mid → nose_tip
    snout_base_pos = skull_center.lerp(nose_tip_pos, 0.25)
    snout_mid_pos = skull_center.lerp(nose_tip_pos, 0.65)
    snout_base_b = mk("snout_base", skull_center.copy(), snout_base_pos,
                       parent=head_b, bbones=2)
    snout_mid_b = mk("snout_mid", snout_base_pos, snout_mid_pos,
                      parent=snout_base_b, connect=True, bbones=2)
    nose_tip_b = mk("nose_tip", snout_mid_pos, nose_tip_pos.copy(),
                     parent=snout_mid_b, connect=True)

    # Nose L/R (nostrils)
    for side, sx in (("L", +1), ("R", -1)):
        n_h = nose_tip_pos + Vector((sx * 0.012, 0, 0.005))
        n_t = n_h + Vector((sx * 0.008, head_dir * 0.005, 0.003))
        mk(f"nose_{side}", n_h, n_t, parent=nose_tip_b, coll="ARMATURE_DEFORM")

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

    # Lips: upper L/R, lower L/R
    lip_y = snout_mid_pos.y + head_dir * y_size * 0.02
    lip_z = snout_mid_pos.z - z_size * 0.05
    for side, sx in (("L", +1), ("R", -1)):
        up_h = Vector((sx * x_half * 0.05, lip_y, lip_z + 0.005))
        up_t = Vector((sx * x_half * 0.15, lip_y + head_dir * 0.01, lip_z + 0.005))
        mk(f"upper_lip_{side}", up_h, up_t, parent=snout_mid_b)
        lo_h = Vector((sx * x_half * 0.05, lip_y, lip_z - 0.005))
        lo_t = Vector((sx * x_half * 0.15, lip_y + head_dir * 0.01, lip_z - 0.005))
        mk(f"lower_lip_{side}", lo_h, lo_t)
        # parent set below to jaw_base

    # Jaw: jaw_base → jaw_tip (hinge at back of jaw, extends to chin)
    jaw_base_h = Vector((x_center,
                         skull_center.y + head_dir * (-0.02),
                         skull_center.z - z_size * 0.12))
    jaw_base_h = snap_to_inside(bvh, jaw_base_h)
    jaw_base_t = Vector((x_center,
                         snout_mid_pos.y,
                         skull_center.z - z_size * 0.10))
    jaw_base_b = mk("jaw_base", jaw_base_h, jaw_base_t, parent=head_b, bbones=2)
    jaw_tip_t = Vector((x_center, nose_tip_pos.y - head_dir * 0.02,
                         nose_tip_pos.z - z_size * 0.03))
    mk("jaw_tip", jaw_base_t.copy(), jaw_tip_t, parent=jaw_base_b, connect=True)

    # Reparent lower_lip_L/R to jaw_base (lower lip follows jaw)
    for side in ("L", "R"):
        ll = created.get(f"lower_lip_{side}")
        if ll: ll.parent = jaw_base_b

    # Ears: base → mid → tip per side
    for side, base_pos in (("L", ear_L_base_pos), ("R", ear_R_base_pos)):
        # Tripo gives us a SINGLE bone per ear. We subdivide into base/mid/tip.
        tripo_name = "bone_7" if side == "L" else "bone_6"
        tripo_h, tripo_t, _ = tripo[tripo_name]
        # interpolate
        ear_base_h = tripo_h.copy()
        ear_mid_h = tripo_h.lerp(tripo_t, 0.4)
        ear_tip_h = tripo_h.lerp(tripo_t, 0.8)
        ear_tip_t = tripo_t.copy()
        ear_base_b = mk(f"ear_{side}_base", ear_base_h, ear_mid_h,
                         parent=head_b, bbones=2)
        ear_mid_b = mk(f"ear_{side}_mid", ear_mid_h, ear_tip_h,
                        parent=ear_base_b, connect=True, bbones=2)
        ear_tip_b = mk(f"ear_{side}_tip", ear_tip_h, ear_tip_t,
                        parent=ear_mid_b, connect=True)

    # ========================================================================
    # FRONT LEGS: scapula → upper → lower → paw → toes
    # ========================================================================
    # Tripo gives: bone_9 (shoulder, L=+X), bone_13 (R=-X), Limb_0/1/2 = upper/lower/paw
    # We add scapula HELPER, and use Tripo's chain for upper/lower/paw + synthesize toes.
    for side, sh_name, limb_prefix in (("L", "bone_9", "tripo::0_Left_Limb"),
                                         ("R", "bone_13", "tripo::0_Right_Limb")):
        sh_h, sh_t, _ = tripo[sh_name]
        upper_h, upper_t, _ = tripo[f"{limb_prefix}_0"]
        lower_h, lower_t, _ = tripo[f"{limb_prefix}_1"]
        paw_h, paw_t, _ = tripo[f"{limb_prefix}_2"]

        # Scapula = the shoulder strut from Tripo (renamed to scapula_L/R)
        scap_b = mk(f"scapula_{side}", sh_h, sh_t,
                     parent="COG", role="DEF", coll="ARMATURE_DEFORM")
        upper_b = mk(f"upper_front_leg_{side}", upper_h, upper_t,
                      parent=scap_b, connect=True, bbones=2)
        lower_b = mk(f"lower_front_leg_{side}", lower_h, lower_t,
                      parent=upper_b, connect=True, bbones=2)
        paw_b = mk(f"front_paw_{side}", paw_h, paw_t,
                    parent=lower_b, connect=True)
        # Toes (synthesize: small bone extending past paw)
        toes_h = paw_t.copy()
        toes_t = paw_t + Vector(((paw_t - paw_h).x * 0.3,
                                  (paw_t - paw_h).y * 0.3,
                                  -0.005))
        mk(f"front_toes_{side}", toes_h, toes_t, parent=paw_b, connect=True)

    # ========================================================================
    # BACK LEGS: hip → thigh → shin → paw → toes
    # ========================================================================
    # Tripo asymmetric — L has more segments than R. Handle separately.
    # Left: bone_27 (hip), 1_Left_Limb_0 (thigh), Limb_1 (shin), Limb_2 (paw), Limb_3 (toes)
    # Right: bone_17 (hip), bone_18 (thigh), 1_Right_Limb_0 (shin), 1_Right_Limb_1 (paw)
    for side, hip_name, thigh_name, shin_name, paw_name, toes_name in (
        ("L", "bone_27", "tripo::1_Left_Limb_0", "tripo::1_Left_Limb_1",
         "tripo::1_Left_Limb_2", "tripo::1_Left_Limb_3"),
        ("R", "bone_17", "bone_18", "tripo::1_Right_Limb_0",
         "tripo::1_Right_Limb_1", None),
    ):
        hip_h, hip_t, _ = tripo[hip_name]
        thigh_h, thigh_t, _ = tripo[thigh_name]
        shin_h, shin_t, _ = tripo[shin_name]
        paw_h, paw_t, _ = tripo[paw_name]

        hip_b = mk(f"hip_{side}", hip_h, hip_t, parent="pelvis")
        thigh_b = mk(f"thigh_{side}", thigh_h, thigh_t,
                      parent=hip_b, connect=False, bbones=2)
        shin_b = mk(f"shin_{side}", shin_h, shin_t,
                     parent=thigh_b, connect=True, bbones=2)
        paw_b = mk(f"back_paw_{side}", paw_h, paw_t,
                    parent=shin_b, connect=True)

        # Back toes
        if toes_name and toes_name in tripo:
            toes_h, toes_t, _ = tripo[toes_name]
            mk(f"back_toes_{side}", toes_h, toes_t,
                parent=paw_b, connect=True)
        else:
            # Synthesize for R side
            toes_h = paw_t.copy()
            toes_t = paw_t + Vector(((paw_t - paw_h).x * 0.3,
                                      (paw_t - paw_h).y * 0.3,
                                      -0.005))
            mk(f"back_toes_{side}", toes_h, toes_t,
                parent=paw_b, connect=True)

    # ========================================================================
    # TAIL: 14 bones (subdivide Tripo's 5-segment tail)
    # ========================================================================
    # Tripo tail chain: bone_21 → Tail_0 → Tail_1 → Tail_2 → Tail_3 → bone_26
    # Endpoints: tail_base (bone_21.head) → tail_tip (bone_26.tail)
    tail_chain_tripo = ["bone_21", "tripo::Tail_0", "tripo::Tail_1",
                         "tripo::Tail_2", "tripo::Tail_3", "bone_26"]
    # Collect all tail points (head of first + tails of each = chain points)
    tail_pts = [tripo[tail_chain_tripo[0]][0]]
    for tn in tail_chain_tripo:
        tail_pts.append(tripo[tn][1])
    # Now we have 7 points along tail. Resample to 15 points → 14 bones.
    def resample_polyline(pts, n_segments):
        # Cumulative arc length
        cum = [0.0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + (pts[i] - pts[i-1]).length)
        total = cum[-1]
        if total < 1e-6: return [pts[0]] * (n_segments + 1)
        target = [i * total / n_segments for i in range(n_segments + 1)]
        out = []
        for tg in target:
            # find which segment
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

    n_tail = 14
    tail_resampled = resample_polyline(tail_pts, n_tail)
    prev = sacrum_b
    tail_bones = []
    for i in range(n_tail):
        name = f"tail_{i+1:02d}"
        b = mk(name, tail_resampled[i], tail_resampled[i+1],
                parent=prev, connect=(i > 0), bbones=2)
        tail_bones.append(b)
        prev = b

    # ========================================================================
    # CONTROL BONES (CTRL_*)
    # ========================================================================
    # Body CTRLs
    def add_ctrl(name, head, tail, parent=None, coll="ARMATURE_CONTROLS"):
        return mk(name, head, tail, parent=parent, role="CTRL", coll=coll)

    # CTRL_root = root itself (we don't duplicate)
    # CTRL_COG = COG itself
    # CTRL for spine/pelvis/chest — these are FK controllers, same position as DEF
    add_ctrl("CTRL_pelvis", pelvis_h, pelvis_t, parent="COG")
    add_ctrl("CTRL_sacrum", pelvis_t.copy(), tail_base.copy(), parent="CTRL_pelvis")
    add_ctrl("CTRL_chest", spine_pts[-1].copy(), neck_start.copy(), parent="CTRL_pelvis")
    add_ctrl("CTRL_head", neck_end.copy(), skull_center.copy(), parent="CTRL_chest")

    # Spine curve / curl / arch — use offset bones above the spine
    spine_mid = spine_pts[3]
    add_ctrl("CTRL_spine_curve",
              spine_mid + Vector((0, 0, z_size * 0.3)),
              spine_mid + Vector((0, 0, z_size * 0.3 + 0.04)),
              parent="CTRL_pelvis")
    add_ctrl("CTRL_spine_curl_L",
              spine_mid + Vector((x_half * 0.5, 0, z_size * 0.25)),
              spine_mid + Vector((x_half * 0.5 + 0.04, 0, z_size * 0.25)),
              parent="CTRL_spine_curve")
    add_ctrl("CTRL_spine_curl_R",
              spine_mid + Vector((-x_half * 0.5, 0, z_size * 0.25)),
              spine_mid + Vector((-x_half * 0.5 - 0.04, 0, z_size * 0.25)),
              parent="CTRL_spine_curve")
    add_ctrl("CTRL_spine_arch_up",
              spine_mid + Vector((0, 0, z_size * 0.35)),
              spine_mid + Vector((0, 0, z_size * 0.35 + 0.04)),
              parent="CTRL_spine_curve")
    add_ctrl("CTRL_spine_arch_down",
              spine_mid + Vector((0, 0, -z_size * 0.05)),
              spine_mid + Vector((0, 0, -z_size * 0.05 - 0.04)),
              parent="CTRL_spine_curve")
    add_ctrl("CTRL_body_stretch",
              cog_h + Vector((0, -head_dir * 0.10, z_size * 0.25)),
              cog_h + Vector((0, -head_dir * 0.10, z_size * 0.25 + 0.04)),
              parent="COG")
    add_ctrl("CTRL_body_crouch",
              cog_h + Vector((0, 0, -z_size * 0.10)),
              cog_h + Vector((0, 0, -z_size * 0.10 - 0.04)),
              parent="COG")

    # Ribcage / belly controls (positioned above the helpers)
    add_ctrl("CTRL_ribcage_expand",
              ribcage_center_h + Vector((0, 0, z_size * 0.25)),
              ribcage_center_h + Vector((0, 0, z_size * 0.25 + 0.04)),
              parent="CTRL_chest")
    add_ctrl("CTRL_ribcage_compress",
              ribcage_center_h + Vector((0, 0, -z_size * 0.10)),
              ribcage_center_h + Vector((0, 0, -z_size * 0.10 - 0.04)),
              parent="CTRL_chest")
    add_ctrl("CTRL_breath_in",
              ribcage_center_h + Vector((x_half * 0.5, 0, z_size * 0.20)),
              ribcage_center_h + Vector((x_half * 0.5 + 0.04, 0, z_size * 0.20)),
              parent="CTRL_chest")
    add_ctrl("CTRL_breath_out",
              ribcage_center_h + Vector((-x_half * 0.5, 0, z_size * 0.20)),
              ribcage_center_h + Vector((-x_half * 0.5 - 0.04, 0, z_size * 0.20)),
              parent="CTRL_chest")
    add_ctrl("CTRL_belly_soft_motion",
              belly_center_h + Vector((0, 0, -z_size * 0.15)),
              belly_center_h + Vector((0, 0, -z_size * 0.15 - 0.04)),
              parent="CTRL_pelvis")

    # Face controls — anchored to CTRL_head
    head_ctrl_pos = skull_center + Vector((0, 0, z_size * 0.15))
    add_ctrl("CTRL_jaw_open",
              jaw_base_h + Vector((0, 0, -z_size * 0.1)),
              jaw_base_h + Vector((0, 0, -z_size * 0.1 - 0.04)),
              parent="CTRL_head")
    add_ctrl("CTRL_jaw_side",
              jaw_base_h + Vector((x_half * 0.3, 0, -z_size * 0.1)),
              jaw_base_h + Vector((x_half * 0.3 + 0.04, 0, -z_size * 0.1)),
              parent="CTRL_head")
    add_ctrl("CTRL_snout_forward",
              snout_mid_pos + Vector((0, head_dir * 0.05, 0)),
              snout_mid_pos + Vector((0, head_dir * 0.05 + 0.04, 0)),
              parent="CTRL_head")
    add_ctrl("CTRL_snout_up",
              snout_mid_pos + Vector((0, 0, z_size * 0.15)),
              snout_mid_pos + Vector((0, 0, z_size * 0.15 + 0.04)),
              parent="CTRL_head")
    add_ctrl("CTRL_snout_scrunch",
              snout_base_pos + Vector((0, 0, z_size * 0.1)),
              snout_base_pos + Vector((0, 0, z_size * 0.1 + 0.04)),
              parent="CTRL_head")
    for side in ("L", "R"):
        sx = +1 if side == "L" else -1
        add_ctrl(f"CTRL_nose_twitch_{side}",
                  nose_tip_pos + Vector((sx * x_half * 0.20, 0, z_size * 0.05)),
                  nose_tip_pos + Vector((sx * x_half * 0.20 + 0.03, 0, z_size * 0.05)),
                  parent="CTRL_head")
        add_ctrl(f"CTRL_cheek_puff_{side}",
                  skull_center + Vector((sx * x_half * 0.50, 0, -z_size * 0.05)),
                  skull_center + Vector((sx * x_half * 0.50 + sx * 0.03, 0, -z_size * 0.05)),
                  parent="CTRL_head")
        add_ctrl(f"CTRL_whisker_pad_forward_{side}",
                  snout_mid_pos + Vector((sx * x_half * 0.40, head_dir * 0.03, 0)),
                  snout_mid_pos + Vector((sx * x_half * 0.40, head_dir * 0.03 + 0.03, 0)),
                  parent="CTRL_head")
        add_ctrl(f"CTRL_whisker_spread_{side}",
                  snout_mid_pos + Vector((sx * x_half * 0.55, 0, 0)),
                  snout_mid_pos + Vector((sx * x_half * 0.55 + sx * 0.03, 0, 0)),
                  parent="CTRL_head")

    # Ear controls — 5 per side
    for side in ("L", "R"):
        sx = +1 if side == "L" else -1
        base_b = created[f"ear_{side}_base"]
        ear_outer_pos = base_b.tail + Vector((sx * 0.04, 0, 0.02))
        for ctrl_suffix, offset in (
            ("perk",       Vector((0, 0, 0.04))),
            ("relax",      Vector((0, 0, -0.03))),
            ("rotate_back", Vector((0, head_dir * -0.04, 0))),
            ("twitch",     Vector((sx * 0.03, 0, 0))),
            ("fold",       Vector((sx * 0.02, 0, -0.02))),
        ):
            n = f"CTRL_ear_{side}_{ctrl_suffix}"
            add_ctrl(n, ear_outer_pos + offset, ear_outer_pos + offset + Vector((0, 0, 0.03)),
                      parent="CTRL_head")

    # Leg controls: IK foot, knee pole, scapula/hip ctrls
    z_floor = z_min
    for side, sx in (("L", +1), ("R", -1)):
        # Front paw IK
        fp = created[f"front_paw_{side}"]
        fp_pos = fp.tail.copy()
        ik_h = Vector((fp_pos.x, fp_pos.y - head_dir * 0.03, z_floor))
        add_ctrl(f"CTRL_front_paw_IK_{side}",
                  ik_h, ik_h + Vector((0, head_dir * 0.05, 0)),
                  parent="root", coll="ARMATURE_CONTROLS")
        # Knee pole
        upper = created[f"upper_front_leg_{side}"]
        pole_pos = Vector((upper.tail.x, upper.tail.y + head_dir * x_half * 0.3,
                            upper.tail.z))
        add_ctrl(f"CTRL_front_knee_pole_{side}",
                  pole_pos, pole_pos + Vector((0, 0, 0.04)),
                  parent="root")
        # Scapula ctrl
        scap = created[f"scapula_{side}"]
        add_ctrl(f"CTRL_scapula_{side}", scap.head, scap.tail, parent="CTRL_chest")

        # Back paw IK
        bp = created[f"back_paw_{side}"]
        bp_pos = bp.tail.copy()
        ik_h = Vector((bp_pos.x, bp_pos.y - head_dir * 0.03, z_floor))
        add_ctrl(f"CTRL_back_paw_IK_{side}",
                  ik_h, ik_h + Vector((0, head_dir * 0.05, 0)),
                  parent="root")
        # Back knee pole
        thigh = created[f"thigh_{side}"]
        pole_pos = Vector((thigh.tail.x, thigh.tail.y + head_dir * x_half * 0.3,
                            thigh.tail.z))
        add_ctrl(f"CTRL_back_knee_pole_{side}",
                  pole_pos, pole_pos + Vector((0, 0, 0.04)),
                  parent="root")
        # Hip ctrl
        hip = created[f"hip_{side}"]
        add_ctrl(f"CTRL_hip_{side}", hip.head, hip.tail, parent="CTRL_pelvis")

    # Tail controls
    tail_base_b = tail_bones[0]
    tail_mid_b = tail_bones[len(tail_bones) // 2]
    tail_tip_b = tail_bones[-1]
    add_ctrl("CTRL_tail_base", tail_base_b.head, tail_base_b.tail, parent="CTRL_sacrum")
    add_ctrl("CTRL_tail_mid", tail_mid_b.head, tail_mid_b.tail, parent="CTRL_tail_base")
    add_ctrl("CTRL_tail_tip", tail_tip_b.head, tail_tip_b.tail, parent="CTRL_tail_mid")
    # Misc tail motion controls
    tail_top = tail_mid_b.head + Vector((0, 0, z_size * 0.25))
    add_ctrl("CTRL_tail_curl_L", tail_top + Vector((x_half * 0.5, 0, 0)),
              tail_top + Vector((x_half * 0.5 + 0.03, 0, 0)), parent="CTRL_sacrum")
    add_ctrl("CTRL_tail_curl_R", tail_top + Vector((-x_half * 0.5, 0, 0)),
              tail_top + Vector((-x_half * 0.5 - 0.03, 0, 0)), parent="CTRL_sacrum")
    add_ctrl("CTRL_tail_up", tail_top, tail_top + Vector((0, 0, 0.03)),
              parent="CTRL_sacrum")
    add_ctrl("CTRL_tail_down", tail_mid_b.head + Vector((0, 0, -z_size * 0.15)),
              tail_mid_b.head + Vector((0, 0, -z_size * 0.15 - 0.03)),
              parent="CTRL_sacrum")
    add_ctrl("CTRL_tail_sway", tail_mid_b.head + Vector((0, head_dir * -0.10, 0)),
              tail_mid_b.head + Vector((0, head_dir * -0.10 - 0.03, 0)),
              parent="CTRL_sacrum")

    # Exit edit mode
    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Armature built: {len(arm.bones)} bones")

    # ========================================================================
    # Bone collections (Blender 4.0)
    # ========================================================================
    coll_names = ["ARMATURE_DEFORM", "ARMATURE_CONTROLS", "RIG_HELPERS"]
    colls = {}
    for n in coll_names:
        try:
            colls[n] = arm.collections.new(name=n)
        except Exception:
            colls[n] = arm.collections.get(n)
    for bone in arm.bones:
        m = meta.get(bone.name, {"collection": "ARMATURE_DEFORM"})
        c = colls.get(m["collection"])
        if c: c.assign(bone)
        # Only DEF bones are deformers; CTRL/MCH have use_deform=False
        if m["role"] != "DEF":
            bone.use_deform = False

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

    # Save blend
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved .blend → {OUT_BLEND}")
    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
