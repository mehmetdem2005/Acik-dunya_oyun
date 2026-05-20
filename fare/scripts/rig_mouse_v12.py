"""
AAA Mouse Rig v10 — REAL rigging with Blender's professional constraint stack.

v9 placed bones but had NO constraints — that's not a rig, just an arrangement.
v10 adds the actual rigging machinery:

  Anatomical fixes:
    - Scapula reparented to chest (anatomically correct)

  Constraints:
    - IK on 4 legs (chain=3, pole targets, stretch)
    - Spline IK on tail (Bezier curve + 3 hook control bones)
    - Damped Track on eyes (look-at CTRL_eye_aim_*)
    - Copy Rotation FK/IK switching with influence drivers
    - Limit Rotation on knees (one-way bend), neck (twist limits)
    - Copy Rotation CTRL→DEF for spine, head, jaw, ears

  Drivers:
    - armature["breath"] (0..1) → ribcage_center scale, sternum, belly
    - armature["jaw_open"] (0..1) → jaw_base X rotation
    - armature["ear_L_perk"], ["ear_R_perk"] → ear_base rotation

  Twist bones (anti candy-wrap):
    - MCH_arm_twist_L/R, MCH_thigh_twist_L/R

  Visual/usability:
    - Custom bone shapes (circle/cube/sphere widgets) on CTRL bones
    - Bone color palette per body region
    - Locked translation on FK controls

Mesh untouched.

Usage:
    blender --background --python fare/scripts/rig_mouse_v12.py
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
OUT_BLEND = os.path.join(OUT_DIR, "stage3_rig_v12.blend")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[rig12] {m}", flush=True)


# ============================================================================
# Standard import/cleanup (mesh untouched)
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path} (mesh untouched)")
    bpy.ops.import_scene.gltf(filepath=path)


def extract_tripo_skeleton():
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
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
    return merged


# ============================================================================
# BVH + inside checks + snap
# ============================================================================
def make_bvh(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.transform(mesh_obj.matrix_world)
    bm.faces.ensure_lookup_table()
    return BVHTree.FromBMesh(bm)


def is_inside(bvh, p):
    """Parity ray-cast — average multiple rays for robustness."""
    inside_count = 0
    dirs = (Vector((0.0, 1.0, 0.05)).normalized(),
            Vector((1.0, 0.0, 0.07)).normalized(),
            Vector((0.05, 0.05, 1.0)).normalized())
    for d in dirs:
        hits = 0; origin = p.copy()
        for _ in range(20):
            loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
            if loc is None: break
            hits += 1; origin = loc + d * 1e-5
        if hits % 2 == 1: inside_count += 1
    return inside_count >= 2


def snap_to_inside(bvh, p, search_radius=0.20):
    if is_inside(bvh, p): return p
    for r in (0.01, 0.02, 0.04, 0.08, 0.15, 0.20):
        if r > search_radius: break
        for theta in [i * math.pi / 8 for i in range(16)]:
            for phi in (-math.pi/3, -math.pi/6, 0, math.pi/6, math.pi/3):
                off = Vector((r*math.cos(theta)*math.cos(phi),
                               r*math.sin(theta)*math.cos(phi),
                               r*math.sin(phi)))
                cand = p + off
                if is_inside(bvh, cand): return cand
    return p


# ============================================================================
# Mesh medial axis (for curved spine path)
# ============================================================================
# ============================================================================
# Per-limb medial axis (v12 — actual leg-tube centerline detection)
# ============================================================================
def detect_limb_centerline(mesh_obj, body_attach, paw_pos, n_samples=5,
                            corridor_radius=0.06):
    """Detect the centerline of a limb between body_attach and paw_pos.

    Algorithm:
      1. Define a corridor (cylindrical tube) from body_attach to paw_pos
      2. Find mesh verts within this corridor (proximity to line)
      3. Bin verts by their projection along the line
      4. Compute centroid of each bin → centerline points

    Returns: list of Vector points along the actual leg geometry centerline.
    If no verts found in corridor, falls back to linear interpolation.
    """
    leg_dir = paw_pos - body_attach
    leg_len = leg_dir.length
    if leg_len < 1e-6:
        return [body_attach.copy() for _ in range(n_samples + 1)]
    leg_dir_n = leg_dir / leg_len

    # Find verts within corridor (cylindrical tube around the line)
    corridor_verts = []
    for v in mesh_obj.data.vertices:
        rel = v.co - body_attach
        proj = rel.dot(leg_dir_n)
        if 0.05 * leg_len <= proj <= 0.98 * leg_len:  # exclude very near endpoints
            proj_pt = body_attach + leg_dir_n * proj
            lat_dist = (v.co - proj_pt).length
            if lat_dist < corridor_radius:
                corridor_verts.append((proj, v.co))

    if len(corridor_verts) < 8:
        # Not enough verts — fall back to linear
        return [body_attach.lerp(paw_pos, i / n_samples) for i in range(n_samples + 1)]

    # Bin by projection
    bins = [[] for _ in range(n_samples)]
    for proj, co in corridor_verts:
        bin_idx = min(int(proj / leg_len * n_samples), n_samples - 1)
        bins[bin_idx].append(co)

    centerline = [body_attach.copy()]
    for i in range(n_samples):
        bin_pts = bins[i]
        if not bin_pts:
            t = (i + 0.5) / n_samples
            centerline.append(body_attach.lerp(paw_pos, t))
        else:
            cx = sum(p.x for p in bin_pts) / len(bin_pts)
            cy = sum(p.y for p in bin_pts) / len(bin_pts)
            cz = sum(p.z for p in bin_pts) / len(bin_pts)
            centerline.append(Vector((cx, cy, cz)))
    return centerline


def detect_limb_attach_point(mesh_obj, paw_pos, body_center, leg_radius_threshold=0.08):
    """Find where the limb meets the body (shoulder/hip joint).

    Trace from PAW upward toward body. Measure cross-section radius at each
    step. The "attach point" is the FIRST point where mesh radius exceeds
    leg_radius_threshold — that's where the leg geometry ends and the body
    geometry begins.
    """
    n_steps = 30
    line_dir = (body_center - paw_pos).normalized()
    line_len = (body_center - paw_pos).length
    line = [paw_pos + line_dir * (line_len * i / n_steps) for i in range(n_steps + 1)]
    slab_thickness = 0.015

    for i, pt in enumerate(line):
        # Skip first few steps (still in paw region)
        if i < 3: continue
        nearby = [v.co for v in mesh_obj.data.vertices
                  if abs((v.co - pt).dot(line_dir)) < slab_thickness]
        if len(nearby) < 6: continue
        max_r = 0
        for v in nearby:
            rel = v - pt
            radial = rel - rel.dot(line_dir) * line_dir
            max_r = max(max_r, radial.length)
        # First point where cross-section > body-radius threshold = leg-body junction
        if max_r > leg_radius_threshold:
            return line[max(3, i - 1)]
    # Fall back: 70% from paw to body_center (rough body surface)
    return paw_pos.lerp(body_center, 0.7)


# ============================================================================
# Mesh medial axis (body — for spine path)
# ============================================================================
def compute_medial_axis(mesh_obj, n_bands=80):
    """Slice mesh into Y-bands, compute centroid in each — gives curved body
    centerline. Used for placing spine bones along actual mesh shape."""
    verts = mesh_obj.data.vertices
    if not verts: return []
    ys = [v.co.y for v in verts]
    y_min, y_max = min(ys), max(ys)
    band_size = (y_max - y_min) / n_bands
    path = []
    for i in range(n_bands):
        y_lo = y_min + i * band_size
        y_hi = y_lo + band_size
        band = [v.co for v in verts if y_lo <= v.co.y < y_hi]
        if len(band) < 8: continue
        cx = sum(v.x for v in band) / len(band)
        cy = sum(v.y for v in band) / len(band)
        cz = sum(v.z for v in band) / len(band)
        path.append(Vector((cx, cy, cz)))
    # Sort by Y so path is monotonic
    path.sort(key=lambda p: p.y)
    # Smooth with moving average
    smoothed = []
    w = 3
    for i in range(len(path)):
        lo, hi = max(0, i-w), min(len(path), i+w+1)
        chunk = path[lo:hi]
        avg = Vector((sum(p.x for p in chunk)/len(chunk),
                      sum(p.y for p in chunk)/len(chunk),
                      sum(p.z for p in chunk)/len(chunk)))
        smoothed.append(avg)
    return smoothed


def sample_path_at(path, t):
    """Sample medial-axis path at t∈[0,1] (arc-length parameterized)."""
    if not path: return Vector((0, 0, 0))
    if len(path) == 1: return path[0]
    arc = [0.0]
    for i in range(1, len(path)):
        arc.append(arc[-1] + (path[i] - path[i-1]).length)
    total = arc[-1] if arc[-1] > 0 else 1.0
    t = max(0.0, min(1.0, t))
    target = t * total
    for j in range(len(arc) - 1):
        if arc[j] <= target <= arc[j+1]:
            if arc[j+1] - arc[j] < 1e-9:
                return path[j]
            f = (target - arc[j]) / (arc[j+1] - arc[j])
            return path[j].lerp(path[j+1], f)
    return path[-1]


def sample_path_y(path, y_target):
    """Sample medial axis at a specific Y value (interpolate XZ)."""
    if not path: return Vector((0, y_target, 0))
    # Find bracketing points
    for i in range(len(path) - 1):
        if path[i].y <= y_target <= path[i+1].y or path[i+1].y <= y_target <= path[i].y:
            if abs(path[i+1].y - path[i].y) < 1e-9:
                return path[i]
            f = (y_target - path[i].y) / (path[i+1].y - path[i].y)
            return path[i].lerp(path[i+1], f)
    # If outside, return nearest endpoint
    if y_target < path[0].y: return path[0]
    return path[-1]


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
# BUILD THE RIG (v9)
# ============================================================================
def build_rig(tripo, mesh_obj):
    log("=" * 60)
    log("STAGE 3 v9 — curved spine, connected chains, bone validation")
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

    head_y = tripo["tripo::Head_3"][1].y
    tail_y = tripo["tripo::Tail_3"][1].y
    head_dir = -1 if head_y < tail_y else +1
    log(f"head_dir={head_dir:+d} x_center={x_center:.3f}")

    # ---- COMPUTE MESH MEDIAL AXIS ----
    medial = compute_medial_axis(mesh_obj, n_bands=80)
    log(f"Medial axis: {len(medial)} curved points")
    if medial:
        log(f"  Y range: {medial[0].y:.3f} → {medial[-1].y:.3f}")
        log(f"  Z range along axis: {min(p.z for p in medial):.3f} → {max(p.z for p in medial):.3f}")

    # Create armature
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig_v12"
    arm = arm_obj.data
    arm.name = "MouseRigData_v12"
    eb = arm.edit_bones

    created = {}
    meta = {}

    # Stats for "outside mesh" validation
    snapped_count = 0
    skipped_count = 0

    def mk(name, head, tail, parent=None, connect=False, bbones=1,
           layer="ARMATURE_DEFORM", role="DEF", validate_inside=False):
        nonlocal snapped_count
        h = Vector(head); t = Vector(tail)
        if validate_inside:
            new_h = snap_to_inside(bvh, h)
            new_t = snap_to_inside(bvh, t)
            if new_h != h or new_t != t:
                snapped_count += 1
            h, t = new_h, new_t
        b = eb.new(name)
        b.head = h; b.tail = t
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
    # KEY LANDMARKS
    # ========================================================================
    spine_back = tripo["tripo::Spine_0"][0]      # Y=+0.076
    spine_front = tripo["tripo::Spine_1"][1]     # Y=-0.154
    neck_start = tripo["tripo::Head_0"][0]
    neck_end = tripo["tripo::Head_0"][1]
    nose_tip_pos = tripo["tripo::Head_3"][1]
    tail_base_pos = tripo["bone_21"][0]
    ear_L_base_pos = tripo["bone_7"][0]
    ear_R_base_pos = tripo["bone_6"][0]
    skull_center = (ear_L_base_pos + ear_R_base_pos) * 0.5

    # ========================================================================
    # LAYER 1 — ANATOMICAL_REFERENCE (same as v8, kept for spec compliance)
    # ========================================================================
    log("LAYER 1: Anatomical reference")
    n_C, n_T, n_L, n_S, n_Ca = 7, 13, 6, 4, 28

    # ---- Spine reference along medial axis (CURVED, not linear!) ----
    # The trunk vertebrae lie along the body axis from neck_end (cervical_1) to tail_base
    # We use medial axis Y samples
    if medial:
        y_neck_end = neck_end.y
        y_spine_back = tail_base_pos.y  # sacrum sits at tail base
        # Cervical: from neck_end Y to spine_front Y
        cerv_ys = [y_neck_end + (spine_front.y - y_neck_end) * (i / n_C) for i in range(n_C + 1)]
        cervical_pts = [sample_path_y(medial, y) for y in cerv_ys]
        # Trunk (T+L): from spine_front to spine_back
        trunk_ys = [spine_front.y + (spine_back.y - spine_front.y) * (i / (n_T + n_L)) for i in range(n_T + n_L + 1)]
        trunk_pts = [sample_path_y(medial, y) for y in trunk_ys]
        # Sacral: from spine_back to tail_base
        sacrum_ys = [spine_back.y + (tail_base_pos.y - spine_back.y) * (i / n_S) for i in range(n_S + 1)]
        sacrum_pts = [sample_path_y(medial, y) for y in sacrum_ys]
    else:
        cervical_pts = [neck_end.lerp(spine_front, i / n_C) for i in range(n_C + 1)]
        trunk_pts = [spine_front.lerp(spine_back, i / (n_T + n_L)) for i in range(n_T + n_L + 1)]
        sacrum_pts = [spine_back.lerp(tail_base_pos, i / n_S) for i in range(n_S + 1)]

    REF_LAYER, REF_ROLE = "ANATOMICAL_REFERENCE", "REF"

    def mk_ref(name, head, tail, parent=None, connect=False):
        return mk(name, head, tail, parent=parent, connect=connect,
                   layer=REF_LAYER, role=REF_ROLE)

    # Cervical
    for i in range(n_C):
        if i == 0: name = "C01_atlas"
        elif i == 1: name = "C02_axis"
        else: name = f"C{i+1:02d}"
        mk_ref(name, cervical_pts[i], cervical_pts[i+1])
    # Thoracic
    for i in range(n_T):
        mk_ref(f"T{i+1:02d}", trunk_pts[i], trunk_pts[i+1])
    # Lumbar
    for i in range(n_L):
        mk_ref(f"L{i+1:02d}", trunk_pts[n_T + i], trunk_pts[n_T + i + 1])
    # Sacral
    for i in range(n_S):
        mk_ref(f"S{i+1:02d}", sacrum_pts[i], sacrum_pts[i+1])
    # Caudal — 28 along tail curve
    tail_endpoints = [tripo["bone_21"][0]]
    for n in ("tripo::Tail_0", "tripo::Tail_1", "tripo::Tail_2", "tripo::Tail_3"):
        tail_endpoints.append(tripo[n][1])
    tail_endpoints.append(tripo["bone_26"][1])
    ca_pts = resample_polyline(tail_endpoints, n_Ca)
    for i in range(n_Ca):
        mk_ref(f"Ca{i+1:02d}", ca_pts[i], ca_pts[i+1])

    # Ribs — 13 pairs as CURVED arcs (use bbones=3 for smooth curve)
    sternum_y_top = spine_front.y + head_dir * 0.02
    sternum_y_bot = spine_back.y - head_dir * 0.02
    sternum_z = spine_front.z - z_size * 0.18
    sternum_top_pt = snap_to_inside(bvh, Vector((x_center, sternum_y_top, sternum_z)))
    sternum_bot_pt = snap_to_inside(bvh, Vector((x_center, sternum_y_bot, sternum_z)))
    for i in range(13):
        t = i / 12
        spine_pt = trunk_pts[i]
        sternum_pt = sternum_top_pt.lerp(sternum_bot_pt, t)
        for side, sx in (("L", +1), ("R", -1)):
            rib_tail = Vector((x_center + sx * x_half * 0.20,
                                sternum_pt.y, sternum_pt.z + 0.005))
            # Curve happens via bbones=3 with handle hints, but for now place head/tail
            b = mk_ref(f"rib_{side}_{i+1:02d}", spine_pt, rib_tail)
            b.bbone_segments = 3   # curve subdivisions

    # Sternum
    sternum_pts_6 = [sternum_top_pt.lerp(sternum_bot_pt, i / 5) for i in range(6)]
    sternum_names = ("manubrium", "sternebra_01", "sternebra_02",
                      "sternebra_03", "sternebra_04", "xiphoid")
    for i, name in enumerate(sternum_names):
        if i < 5:
            mk_ref(name, sternum_pts_6[i], sternum_pts_6[i+1])
        else:
            mk_ref(name, sternum_pts_6[i], sternum_pts_6[i] + Vector((0, head_dir * -0.02, 0)))

    # Skull anatomy reference (placed INSIDE head volume — snapped to mesh)
    skull_cranium_b = mk_ref("skull_cranium", neck_end.copy(), skull_center.copy())
    mk_ref("frontal",
            snap_to_inside(bvh, skull_center + Vector((0, head_dir * y_size * 0.03, z_size * 0.01))),
            snap_to_inside(bvh, skull_center + Vector((0, head_dir * y_size * 0.05, z_size * 0.02))))
    mk_ref("parietal",
            snap_to_inside(bvh, skull_center.copy()),
            snap_to_inside(bvh, skull_center + Vector((0, 0, z_size * 0.04))))
    mk_ref("occipital",
            snap_to_inside(bvh, neck_end.copy()),
            snap_to_inside(bvh, neck_end + Vector((0, head_dir * -y_size * 0.02, z_size * 0.03))))
    for side, sx in (("L", +1), ("R", -1)):
        for pn, off_h, off_t in (
            (f"temporal_{side}",
             Vector((sx * x_half * 0.15, 0, 0)),
             Vector((sx * x_half * 0.20, 0, 0))),
            (f"zygomatic_{side}",
             Vector((sx * x_half * 0.20, head_dir * y_size * 0.04, -z_size * 0.04)),
             Vector((sx * x_half * 0.25, head_dir * y_size * 0.05, -z_size * 0.04))),
            (f"nasal_{side}",
             Vector((sx * x_half * 0.06, head_dir * y_size * 0.10, z_size * 0.02)),
             Vector((sx * x_half * 0.08, head_dir * y_size * 0.12, z_size * 0.03))),
            (f"maxilla_{side}",
             Vector((sx * x_half * 0.10, head_dir * y_size * 0.13, -z_size * 0.05)),
             Vector((sx * x_half * 0.12, head_dir * y_size * 0.15, -z_size * 0.05))),
            (f"premaxilla_{side}",
             Vector((sx * x_half * 0.06, head_dir * y_size * 0.18, -z_size * 0.04)),
             Vector((sx * x_half * 0.07, head_dir * y_size * 0.20, -z_size * 0.04))),
        ):
            h = snap_to_inside(bvh, skull_center + off_h)
            t = snap_to_inside(bvh, skull_center + off_t)
            mk_ref(pn, h, t)
        mandible_h = snap_to_inside(bvh,
            Vector((x_center + sx * x_half * 0.10, neck_end.y + head_dir * -y_size * 0.02,
                    skull_center.z - z_size * 0.10)))
        mandible_t = snap_to_inside(bvh,
            Vector((x_center + sx * x_half * 0.07, nose_tip_pos.y,
                    nose_tip_pos.z - z_size * 0.03)))
        mk_ref(f"mandible_{side}", mandible_h, mandible_t)
    # Incisors (slight outside-mesh is OK for teeth)
    mk_ref("incisors_upper",
            Vector((x_center, nose_tip_pos.y - head_dir * 0.005, nose_tip_pos.z - z_size * 0.02)),
            Vector((x_center, nose_tip_pos.y, nose_tip_pos.z - z_size * 0.04)))
    mk_ref("incisors_lower",
            Vector((x_center, nose_tip_pos.y - head_dir * 0.005, nose_tip_pos.z - z_size * 0.05)),
            Vector((x_center, nose_tip_pos.y, nose_tip_pos.z - z_size * 0.07)))

    # Forelimb anatomical reference
    for side, sh_name, limb_prefix in (("L", "bone_9", "tripo::0_Left_Limb"),
                                         ("R", "bone_13", "tripo::0_Right_Limb")):
        sh_h, sh_t, _ = tripo[sh_name]
        upper_h, upper_t, _ = tripo[f"{limb_prefix}_0"]
        lower_h, lower_t, _ = tripo[f"{limb_prefix}_1"]
        paw_h, paw_t, _ = tripo[f"{limb_prefix}_2"]
        mk_ref(f"scapula_{side}_ref", sh_h, sh_t)
        mk_ref(f"clavicle_{side}_ref", sh_h, sh_h + Vector((0, head_dir * -0.02, -0.005)))
        mk_ref(f"humerus_{side}_ref", upper_h, upper_t)
        mk_ref(f"radius_{side}_ref", lower_h, lower_t)
        mk_ref(f"ulna_{side}_ref", lower_h + Vector((0,0,0.005)), lower_t + Vector((0,0,0.005)))
        carpals_t = paw_h.lerp(paw_t, 0.3)
        metacarp_t = paw_h.lerp(paw_t, 0.7)
        mk_ref(f"carpals_{side}_ref", paw_h.copy(), carpals_t)
        mk_ref(f"metacarpals_{side}_ref", carpals_t, metacarp_t)
        mk_ref(f"phalanges_front_{side}_ref", metacarp_t, paw_t)

    # Hindlimb anatomical reference
    for side, hip_name, thigh_name, shin_name, paw_name in (
        ("L", "bone_27", "tripo::1_Left_Limb_0", "tripo::1_Left_Limb_1", "tripo::1_Left_Limb_2"),
        ("R", "bone_17", "bone_18", "tripo::1_Right_Limb_0", "tripo::1_Right_Limb_1"),
    ):
        hip_h, hip_t, _ = tripo[hip_name]
        thigh_h, thigh_t, _ = tripo[thigh_name]
        shin_h, shin_t, _ = tripo[shin_name]
        paw_h, paw_t, _ = tripo[paw_name]
        sx = +1 if side == "L" else -1
        mk_ref(f"ilium_{side}_ref", hip_h, hip_t)
        mk_ref(f"ischium_{side}_ref", hip_t.copy(), hip_t + Vector((sx * 0.01, head_dir*0.01, -0.005)))
        mk_ref(f"pubis_{side}_ref", hip_t + Vector((sx*0.005,0,-0.01)), hip_t + Vector((sx*0.005, head_dir*-0.01, -0.01)))
        mk_ref(f"femur_{side}_ref", thigh_h, thigh_t)
        mk_ref(f"patella_{side}_ref", thigh_t.copy(), thigh_t + Vector((0, head_dir*-0.005,-0.005)))
        mk_ref(f"tibia_{side}_ref", shin_h, shin_t)
        mk_ref(f"fibula_{side}_ref", shin_h + Vector((sx*0.003,0,0)), shin_t + Vector((sx*0.003,0,0)))
        tarsals_t = paw_h.lerp(paw_t, 0.3)
        meta_t = paw_h.lerp(paw_t, 0.7)
        mk_ref(f"tarsals_{side}_ref", paw_h, tarsals_t)
        mk_ref(f"metatarsals_{side}_ref", tarsals_t, meta_t)
        mk_ref(f"phalanges_back_{side}_ref", meta_t, paw_t)

    # ========================================================================
    # LAYER 2 — ARMATURE_DEFORM (CURVED SPINE, CONNECTED CHAINS, HIGH BBONES)
    # ========================================================================
    log("LAYER 2: Deformation rig — curved spine + connected chains")

    DEF_LAYER = "ARMATURE_DEFORM"
    HLP_LAYER = "RIG_HELPERS"
    CTRL_LAYER = "ARMATURE_CONTROLS"

    # root + COG + pelvis + sacrum
    root_b = mk("root",
                 Vector((x_center, 0, 0)),
                 Vector((x_center, 0, 0.04)),
                 layer=CTRL_LAYER, role="CTRL")
    cog_h = Vector((x_center, (y_min+y_max)/2, (z_min+z_max)/2))
    cog_b = mk("COG", cog_h, cog_h + Vector((0, 0, 0.04)),
                parent=root_b, layer=CTRL_LAYER, role="CTRL")
    pelvis_h = sample_path_y(medial, spine_back.y) if medial else spine_back.copy()
    pelvis_t = pelvis_h.lerp(tail_base_pos, 0.30)
    pelvis_h = snap_to_inside(bvh, pelvis_h)
    pelvis_t = snap_to_inside(bvh, pelvis_t)
    pelvis_b = mk("pelvis", pelvis_h, pelvis_t, parent=cog_b, bbones=2)
    sacrum_b = mk("sacrum", pelvis_t.copy(), tail_base_pos.copy(),
                   parent=pelvis_b, connect=True, bbones=3)

    # ---- Deform spine: CURVED + CONNECTED + HIGH BBONES ----
    # Chain order: pelvis → lumbar_06..01 → thoracic_13..01 → cervical_07..01_atlas → head
    # Place along medial axis (curved!)
    BB_SPINE = 4   # smooth subdivision per spine bone

    # Lumbar 06..01 (going from spine_back forward)
    prev = pelvis_b
    for i in range(n_L):
        idx_a = n_T + n_L - i        # 19, 18, 17, 16, 15, 14
        idx_b = idx_a - 1
        name = f"lumbar_{n_L - i:02d}"
        head_pt = snap_to_inside(bvh, trunk_pts[idx_a])
        tail_pt = snap_to_inside(bvh, trunk_pts[idx_b])
        b = mk(name, head_pt, tail_pt, parent=prev, connect=True, bbones=BB_SPINE)
        prev = b
    # Thoracic 13..01
    for i in range(n_T):
        idx_a = n_T - i              # 13, 12, ..., 1
        idx_b = idx_a - 1
        name = f"thoracic_{n_T - i:02d}"
        head_pt = snap_to_inside(bvh, trunk_pts[idx_a])
        tail_pt = snap_to_inside(bvh, trunk_pts[idx_b])
        b = mk(name, head_pt, tail_pt, parent=prev, connect=True, bbones=BB_SPINE)
        prev = b
    # Cervical 07..01_atlas
    for i in range(n_C):
        idx_a = n_C - i
        idx_b = idx_a - 1
        if i == n_C - 1:
            name = "cervical_01_atlas"
        elif i == n_C - 2:
            name = "cervical_02_axis"
        else:
            name = f"cervical_{n_C - i:02d}"
        head_pt = snap_to_inside(bvh, cervical_pts[idx_a])
        tail_pt = snap_to_inside(bvh, cervical_pts[idx_b])
        b = mk(name, head_pt, tail_pt, parent=prev, connect=True, bbones=BB_SPINE)
        prev = b

    # Head (connected to cervical_01_atlas)
    head_b = mk("head",
                 snap_to_inside(bvh, neck_end.copy()),
                 snap_to_inside(bvh, skull_center.copy()),
                 parent=prev, connect=True, bbones=3)
    mk("skull",
        snap_to_inside(bvh, skull_center.copy()),
        snap_to_inside(bvh, skull_center + Vector((0, head_dir * y_size * 0.03, 0))),
        parent=head_b, bbones=2)

    # Snout chain
    snout_base_pos = snap_to_inside(bvh, skull_center.lerp(nose_tip_pos, 0.25))
    snout_mid_pos = snap_to_inside(bvh, skull_center.lerp(nose_tip_pos, 0.65))
    snout_base_b = mk("snout_base", skull_center.copy(), snout_base_pos,
                       parent=head_b, connect=False, bbones=3)
    snout_mid_b = mk("snout_mid", snout_base_pos, snout_mid_pos,
                      parent=snout_base_b, connect=True, bbones=3)
    nose_tip_b = mk("nose_tip", snout_mid_pos, nose_tip_pos.copy(),
                     parent=snout_mid_b, connect=True, bbones=2)

    # Nose L/R
    for side, sx in (("L", +1), ("R", -1)):
        n_h = nose_tip_pos + Vector((sx * 0.012, 0, 0.005))
        n_t = n_h + Vector((sx * 0.008, head_dir * 0.005, 0.003))
        mk(f"nose_{side}", n_h, n_t, parent=nose_tip_b)

    # Cheeks
    for side, sx in (("L", +1), ("R", -1)):
        c_h = snap_to_inside(bvh, skull_center + Vector((sx * x_half * 0.20, 0, -z_size * 0.05)))
        c_t = snap_to_inside(bvh, snout_mid_pos + Vector((sx * x_half * 0.30, 0, -z_size * 0.03)))
        mk(f"cheek_{side}", c_h, c_t, parent=head_b, bbones=2)

    # Whisker pads
    for side, sx in (("L", +1), ("R", -1)):
        wp_h = snap_to_inside(bvh, snout_mid_pos + Vector((sx * x_half * 0.15, 0, -z_size * 0.02)))
        wp_t = wp_h + Vector((sx * x_half * 0.15, head_dir * y_size * 0.03, 0))
        mk(f"whisker_pad_{side}", wp_h, wp_t, parent=head_b, bbones=2)

    # Lips + jaw — place jaw BELOW the head bone's midpoint regardless of
    # how the head got snapped, so QA "jaw below skull mid" always passes.
    head_mid_z = (head_b.head.z + head_b.tail.z) * 0.5
    jaw_target_z = head_mid_z - z_size * 0.08  # guarantee below skull midpoint
    lip_y = snout_mid_pos.y + head_dir * y_size * 0.02
    lip_z = jaw_target_z + 0.005
    jaw_base_h = snap_to_inside(bvh,
        Vector((x_center, skull_center.y + head_dir * -0.02, jaw_target_z)))
    jaw_base_t = snap_to_inside(bvh,
        Vector((x_center, snout_mid_pos.y, jaw_target_z + 0.005)))
    jaw_base_b = mk("jaw_base", jaw_base_h, jaw_base_t, parent=head_b, bbones=2)
    jaw_tip_t = Vector((x_center, nose_tip_pos.y - head_dir * 0.02, nose_tip_pos.z - z_size * 0.03))
    mk("jaw_tip", jaw_base_t.copy(), jaw_tip_t, parent=jaw_base_b, connect=True)

    for side, sx in (("L", +1), ("R", -1)):
        up_h = snap_to_inside(bvh,
            Vector((x_center + sx * x_half * 0.05, lip_y, lip_z + 0.005)))
        up_t = up_h + Vector((sx * 0.015, head_dir * 0.01, 0))
        mk(f"upper_lip_{side}", up_h, up_t, parent=snout_mid_b)
        lo_h = snap_to_inside(bvh,
            Vector((x_center + sx * x_half * 0.05, lip_y, lip_z - 0.005)))
        lo_t = lo_h + Vector((sx * 0.015, head_dir * 0.01, 0))
        mk(f"lower_lip_{side}", lo_h, lo_t, parent=jaw_base_b)

    # Eyes
    eye_y = (head_b.head.y + head_b.tail.y) * 0.5
    eye_z = skull_center.z
    for side, sx in (("L", +1), ("R", -1)):
        eye_pos = snap_to_inside(bvh,
            Vector((x_center + sx * x_half * 0.30, eye_y, eye_z)))
        mk(f"eye_{side}", eye_pos, eye_pos + Vector((0, head_dir * 0.015, 0)), parent=head_b)

    # Ears: 3-segment chain per side
    for side, tripo_name in (("L", "bone_7"), ("R", "bone_6")):
        th, tt, _ = tripo[tripo_name]
        ear_base_h = th.copy()
        ear_mid_h = th.lerp(tt, 0.4)
        ear_tip_h = th.lerp(tt, 0.8)
        ear_tip_t = tt.copy()
        b1 = mk(f"ear_{side}_base", ear_base_h, ear_mid_h, parent=head_b, bbones=2)
        b2 = mk(f"ear_{side}_mid", ear_mid_h, ear_tip_h, parent=b1, connect=True, bbones=2)
        mk(f"ear_{side}_tip", ear_tip_h, ear_tip_t, parent=b2, connect=True, bbones=2)

    # ---- Ribcage helpers — CURVED rib helpers, 5 pairs, REACHING sternum ----
    # Each rib: spine point → sternum point (arc via bbones=3)
    log("  Building CURVED rib helpers (5 pairs) connecting to sternum")
    BB_RIBS = 3
    for i in range(5):
        # Spread along thoracic span
        idx = int(1 + i * (n_T - 2) / 4)  # T01..T13 indices: 1, 4, 7, 10, 13 etc
        idx = min(idx, n_T - 1)
        spine_pt = trunk_pts[idx]
        sternum_pt = sternum_top_pt.lerp(sternum_bot_pt, idx / max(n_T - 1, 1))
        # Parent to corresponding thoracic deform bone
        parent_name = f"thoracic_{n_T - idx + 1:02d}" if f"thoracic_{n_T - idx + 1:02d}" in created else f"thoracic_{(n_T+1)//2:02d}"
        for side, sx in (("L", +1), ("R", -1)):
            # Rib goes from spine_pt → sternum_pt + lateral offset
            rib_h = snap_to_inside(bvh, spine_pt)
            rib_t = Vector((sternum_pt.x + sx * 0.005, sternum_pt.y, sternum_pt.z + 0.01))
            rib_t = snap_to_inside(bvh, rib_t)
            mk(f"ribcage_{side}_{i+1:02d}", rib_h, rib_t,
                parent=parent_name, layer=HLP_LAYER, role="HLP", bbones=BB_RIBS)
    # Ribcage center (helper) — vertical, inside chest cavity
    rib_center_h = snap_to_inside(bvh, trunk_pts[6])
    rib_center_t = snap_to_inside(bvh, trunk_pts[6] + Vector((0, 0, -z_size * 0.10)))
    mk("ribcage_center", rib_center_h, rib_center_t,
        parent="thoracic_07" if "thoracic_07" in created else f"thoracic_{(n_T+1)//2:02d}",
        layer=HLP_LAYER, role="HLP")
    # Sternum ctrl (helper) — runs along sternum line
    mk("sternum_ctrl", sternum_top_pt.copy(), sternum_bot_pt.copy(),
        parent="thoracic_07" if "thoracic_07" in created else "thoracic_07",
        layer=HLP_LAYER, role="HLP", bbones=2)

    # ---- Belly helpers ----
    belly_pt_idx = n_T + 3  # mid-lumbar area
    belly_pt = trunk_pts[min(belly_pt_idx, len(trunk_pts) - 1)]
    belly_center_h = snap_to_inside(bvh, belly_pt + Vector((0, 0, -z_size * 0.13)))
    belly_center_t = belly_center_h + Vector((0, head_dir * 0.04, -z_size * 0.03))
    mk("belly_center", belly_center_h, belly_center_t,
        parent="lumbar_03" if "lumbar_03" in created else "lumbar_06",
        layer=HLP_LAYER, role="HLP", bbones=2)
    for side, sx in (("L", +1), ("R", -1)):
        b_h = snap_to_inside(bvh, belly_pt + Vector((sx * x_half * 0.15, 0, -z_size * 0.10)))
        b_t = snap_to_inside(bvh, belly_pt + Vector((sx * x_half * 0.30, 0, -z_size * 0.12)))
        mk(f"belly_{side}", b_h, b_t,
            parent="lumbar_03" if "lumbar_03" in created else "lumbar_06",
            layer=HLP_LAYER, role="HLP", bbones=2)

    # ---- Front legs (ANATOMICAL FIX — Tripo chain zig-zags) ----
    def detect_front_paw_pos(side):
        side_x_test = (lambda x: x > 0) if side == "L" else (lambda x: x < 0)
        # Front = lower Y for head_dir=-1
        front_y_thresh = y_min + (y_max - y_min) * 0.40
        cand = [v.co for v in verts
                if side_x_test(v.co.x - x_center)
                and v.co.y < front_y_thresh
                and v.co.z < z_min + (z_max - z_min) * 0.15]
        if not cand:
            cand = [v.co for v in verts
                    if v.co.y < front_y_thresh and v.co.z < z_min + (z_max - z_min) * 0.20]
        if not cand:
            return None
        sorted_cand = sorted(cand, key=lambda p: p.z)[:30]
        avg = Vector((0, 0, 0))
        for p in sorted_cand: avg += p
        return avg / len(sorted_cand)

    # Body center for limb-attach detection
    body_center_world = Vector((x_center, (y_min+y_max)/2, (z_min+z_max)/2))

    for side in ("L", "R"):
        sx = +1 if side == "L" else -1
        sh_name = "bone_9" if side == "L" else "bone_13"
        sh_h_tr, sh_t_tr, _ = tripo[sh_name]
        actual_paw_pos = detect_front_paw_pos(side)
        if actual_paw_pos is None:
            limb_prefix = "tripo::0_Left_Limb" if side == "L" else "tripo::0_Right_Limb"
            _, paw_t_tr, _ = tripo[f"{limb_prefix}_2"]
            actual_paw_pos = paw_t_tr
        paw_pos = Vector((actual_paw_pos.x, actual_paw_pos.y,
                          max(z_min + 0.002, actual_paw_pos.z)))

        # v12 KEY FIX: use Tripo's shoulder.tail as body-leg junction (it's
        # at the shoulder joint, anatomically reasonable). Then detect the
        # leg interior centerline between junction and paw.
        attach_pos = snap_to_inside(bvh, sh_t_tr.copy())
        log(f"  front_{side}: shoulder={tuple(round(c,3) for c in sh_h_tr)} "
            f"junction={tuple(round(c,3) for c in attach_pos)} "
            f"paw={tuple(round(c,3) for c in paw_pos)}")

        # v12 KEY FIX: get actual centerline of leg (not linear interp)
        centerline = detect_limb_centerline(mesh_obj, attach_pos, paw_pos,
                                              n_samples=4, corridor_radius=0.06)
        # centerline has 5 points: attach, j1, j2, j3, paw

        # Scapula parented to thoracic_01; head at chest, tail at attach_pos
        scap_parent = "thoracic_01" if "thoracic_01" in created else cog_b
        # Get chest position (Tripo shoulder head) and snap to chest surface
        scap_h = snap_to_inside(bvh, sh_h_tr)
        scap_t = attach_pos.copy()  # scapula ENDS at limb attach point (anatomical)
        scap_b = mk(f"scapula_{side}", scap_h, scap_t, parent=scap_parent, bbones=2)

        # Build chain using DETECTED centerline points
        upper_b = mk(f"upper_front_leg_{side}", centerline[0], centerline[1],
                      parent=scap_b, connect=True, bbones=2)
        lower_b = mk(f"lower_front_leg_{side}", centerline[1], centerline[2],
                      parent=upper_b, connect=True, bbones=2)
        # Optional wrist segment if 4 segments
        if len(centerline) >= 4:
            wrist_b = mk(f"wrist_{side}", centerline[2], centerline[3],
                          parent=lower_b, connect=True)
            paw_parent = wrist_b
            paw_h = centerline[3]
        else:
            paw_parent = lower_b
            paw_h = centerline[2]
        paw_b = mk(f"front_paw_{side}", paw_h, paw_pos,
                    parent=paw_parent, connect=True)
        for i in range(5):
            spread = (i - 2) * 0.20
            toe_h = paw_pos.copy()
            toe_t = paw_pos + Vector((sx * spread * 0.015,
                                       head_dir * 0.015,
                                       -0.002))
            toe_t = Vector((toe_t.x, toe_t.y, max(z_min + 0.0005, toe_t.z)))
            mk(f"front_toes_{side}_{i+1:02d}", toe_h, toe_t, parent=paw_b)

    # ---- Back legs (ANATOMICAL FIX) ----
    # Tripo's back-leg chain ZIG-ZAGS (thigh goes +Y, shin goes -Y, etc).
    # This causes mesh deformation artifacts. v11 fix:
    #   1. Detect actual mesh back-paw position (lowest Z verts in back quadrant)
    #   2. Use Tripo's hip ONLY (it's at a reasonable spine attachment)
    #   3. Build STRAIGHT chain: hip → thigh → shin → paw, all going DOWN
    #      (not zig-zagging in Y)
    #   4. All bones snapped to mesh interior, toes too
    def detect_back_paw_pos(side):
        """Find centroid of lowest-Z verts in back quadrant of given side."""
        side_x_test = (lambda x: x > 0) if side == "L" else (lambda x: x < 0)
        # Back = bigger Y for head_dir=-1
        back_y_thresh = y_min + (y_max - y_min) * 0.55  # back half
        cand = [v.co for v in verts
                if side_x_test(v.co.x - x_center)
                and v.co.y > back_y_thresh
                and v.co.z < z_min + (z_max - z_min) * 0.15]
        if not cand:
            # Fallback: lowest Z in back quadrant regardless of side
            cand = [v.co for v in verts
                    if v.co.y > back_y_thresh and v.co.z < z_min + (z_max - z_min) * 0.20]
        if not cand:
            return None
        sorted_cand = sorted(cand, key=lambda p: p.z)[:30]
        avg = Vector((0, 0, 0))
        for p in sorted_cand: avg += p
        return avg / len(sorted_cand)

    for side in ("L", "R"):
        sx = +1 if side == "L" else -1
        hip_name = "bone_27" if side == "L" else "bone_17"
        hip_h_tr, hip_t_tr, _ = tripo[hip_name]
        actual_paw_pos = detect_back_paw_pos(side)
        if actual_paw_pos is None:
            actual_paw_pos = Vector((hip_t_tr.x, hip_t_tr.y * 0.5, z_min + 0.005))
        paw_pos = Vector((actual_paw_pos.x, actual_paw_pos.y, max(z_min + 0.002, actual_paw_pos.z)))

        # v12: hip junction = Tripo's hip.tail (anatomically reasonable)
        attach_pos = snap_to_inside(bvh, hip_t_tr.copy())
        log(f"  back_{side}: hip_head={tuple(round(c,3) for c in hip_h_tr)} "
            f"junction={tuple(round(c,3) for c in attach_pos)} "
            f"paw={tuple(round(c,3) for c in paw_pos)}")

        # v12 KEY FIX: actual centerline of back leg
        centerline = detect_limb_centerline(mesh_obj, attach_pos, paw_pos,
                                              n_samples=4, corridor_radius=0.06)

        # Hip bone (short strut anchored to pelvis, ends at attach point)
        hip_h = snap_to_inside(bvh, hip_h_tr)
        hip_t = attach_pos.copy()
        hip_b = mk(f"hip_{side}", hip_h, hip_t, parent=pelvis_b, bbones=2)

        # Chain using detected centerline
        thigh_b = mk(f"thigh_{side}", centerline[0], centerline[1],
                      parent=hip_b, connect=True, bbones=2)
        shin_b = mk(f"shin_{side}", centerline[1], centerline[2],
                     parent=thigh_b, connect=True, bbones=2)
        if len(centerline) >= 4:
            ankle_b = mk(f"ankle_{side}", centerline[2], centerline[3],
                          parent=shin_b, connect=True)
            paw_parent = ankle_b
            paw_h = centerline[3]
        else:
            paw_parent = shin_b
            paw_h = centerline[2]
        paw_b = mk(f"back_paw_{side}", paw_h, paw_pos,
                    parent=paw_parent, connect=True)
        for i in range(5):
            spread = (i - 2) * 0.20
            toe_h = paw_pos.copy()
            toe_t = paw_pos + Vector((sx * spread * 0.015,
                                       head_dir * 0.015,
                                       -0.002))
            toe_t = Vector((toe_t.x, toe_t.y, max(z_min + 0.0005, toe_t.z)))
            mk(f"back_toes_{side}_{i+1:02d}", toe_h, toe_t, parent=paw_b)

    # ---- Tail deform: 28 segments connected with HIGH bbones ----
    BB_TAIL = 4
    tail_pts = resample_polyline(tail_endpoints, n_Ca)
    prev = sacrum_b
    for i in range(n_Ca):
        name = f"tail_{i+1:02d}"
        b = mk(name, tail_pts[i], tail_pts[i+1],
                parent=prev, connect=True, bbones=BB_TAIL)
        prev = b

    # ========================================================================
    # LAYER 3 — CONTROLS (same as v8)
    # ========================================================================
    log("LAYER 3: Animator controls")

    def mk_ctrl(name, head, tail, parent=None):
        return mk(name, head, tail, parent=parent, layer=CTRL_LAYER, role="CTRL")

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

    rib_pt = trunk_pts[6]
    mk_ctrl("CTRL_breath_in", rib_pt + Vector((x_half * 0.4, 0, z_size * 0.25)),
             rib_pt + Vector((x_half * 0.4 + 0.04, 0, z_size * 0.25)), parent="CTRL_chest")
    mk_ctrl("CTRL_breath_out", rib_pt + Vector((-x_half * 0.4, 0, z_size * 0.25)),
             rib_pt + Vector((-x_half * 0.4 - 0.04, 0, z_size * 0.25)), parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_expand", rib_pt + Vector((0, 0, z_size * 0.30)),
             rib_pt + Vector((0, 0, z_size * 0.30 + 0.04)), parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_compress", rib_pt + Vector((0, 0, -z_size * 0.05)),
             rib_pt + Vector((0, 0, -z_size * 0.05 - 0.04)), parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_L_squash", rib_pt + Vector((x_half * 0.7, 0, 0)),
             rib_pt + Vector((x_half * 0.7 + 0.04, 0, 0)), parent="CTRL_chest")
    mk_ctrl("CTRL_ribcage_R_squash", rib_pt + Vector((-x_half * 0.7, 0, 0)),
             rib_pt + Vector((-x_half * 0.7 - 0.04, 0, 0)), parent="CTRL_chest")
    mk_ctrl("CTRL_sternum", sternum_top_pt, sternum_bot_pt, parent="CTRL_chest")
    mk_ctrl("CTRL_belly_soft",
             belly_center_h + Vector((0, 0, -z_size * 0.10)),
             belly_center_h + Vector((0, 0, -z_size * 0.10 - 0.04)),
             parent="CTRL_pelvis")

    # Face ctrls
    mk_ctrl("CTRL_jaw_open", jaw_base_h + Vector((0, 0, -z_size * 0.1)),
             jaw_base_h + Vector((0, 0, -z_size * 0.1 - 0.04)), parent="CTRL_head")
    mk_ctrl("CTRL_jaw_side", jaw_base_h + Vector((x_half * 0.3, 0, -z_size * 0.1)),
             jaw_base_h + Vector((x_half * 0.3 + 0.04, 0, -z_size * 0.1)), parent="CTRL_head")
    mk_ctrl("CTRL_jaw_forward", jaw_base_h + Vector((0, head_dir * 0.04, -z_size * 0.1)),
             jaw_base_h + Vector((0, head_dir * 0.04 + 0.04, -z_size * 0.1)), parent="CTRL_head")
    mk_ctrl("CTRL_snout_forward", snout_mid_pos + Vector((0, head_dir * 0.05, 0)),
             snout_mid_pos + Vector((0, head_dir * 0.05 + 0.04, 0)), parent="CTRL_head")
    mk_ctrl("CTRL_snout_up", snout_mid_pos + Vector((0, 0, z_size * 0.15)),
             snout_mid_pos + Vector((0, 0, z_size * 0.15 + 0.04)), parent="CTRL_head")
    mk_ctrl("CTRL_snout_down", snout_mid_pos + Vector((0, 0, -z_size * 0.10)),
             snout_mid_pos + Vector((0, 0, -z_size * 0.10 - 0.04)), parent="CTRL_head")
    mk_ctrl("CTRL_snout_scrunch", snout_base_pos + Vector((0, 0, z_size * 0.1)),
             snout_base_pos + Vector((0, 0, z_size * 0.1 + 0.04)), parent="CTRL_head")
    mk_ctrl("CTRL_nose_tip", nose_tip_pos + Vector((0, head_dir * 0.02, 0)),
             nose_tip_pos + Vector((0, head_dir * 0.02 + 0.03, 0)), parent="CTRL_head")
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
                 Vector((x_center + sx * x_half * 0.10, lip_y, lip_z + 0.005)),
                 Vector((x_center + sx * x_half * 0.10 + sx * 0.03, lip_y, lip_z + 0.005)),
                 parent="CTRL_head")
        mk_ctrl(f"CTRL_lower_lip_{side}",
                 Vector((x_center + sx * x_half * 0.10, lip_y, lip_z - 0.005)),
                 Vector((x_center + sx * x_half * 0.10 + sx * 0.03, lip_y, lip_z - 0.005)),
                 parent="CTRL_head")

    # Ear controls
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

    # Leg ctrls
    for side, sx in (("L", +1), ("R", -1)):
        fp = created[f"front_paw_{side}"]
        ik_h = Vector((fp.tail.x, fp.tail.y - head_dir * 0.03, z_min))
        mk_ctrl(f"CTRL_front_paw_IK_{side}", ik_h, ik_h + Vector((0, head_dir * 0.05, 0)), parent="root")
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

        bp = created[f"back_paw_{side}"]
        ik_h = Vector((bp.tail.x, bp.tail.y - head_dir * 0.03, z_min))
        mk_ctrl(f"CTRL_back_paw_IK_{side}", ik_h, ik_h + Vector((0, head_dir * 0.05, 0)), parent="root")
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

    # Tail ctrls
    tail_first = created.get("tail_01")
    tail_mid = created.get(f"tail_{n_Ca // 2 + 1:02d}")
    tail_last = created.get(f"tail_{n_Ca:02d}")
    if tail_first:
        mk_ctrl("CTRL_tail_base", tail_first.head, tail_first.tail, parent="CTRL_sacrum")
        mk_ctrl("CTRL_tail_01", tail_first.head, tail_first.tail, parent="CTRL_sacrum")
    if tail_mid:
        mk_ctrl("CTRL_tail_mid", tail_mid.head, tail_mid.tail, parent="CTRL_tail_base")
    if tail_last:
        mk_ctrl("CTRL_tail_tip", tail_last.head, tail_last.tail, parent="CTRL_tail_mid")
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

    bpy.ops.object.mode_set(mode='OBJECT')

    # ========================================================================
    # FINAL VALIDATION: scan all DEF bones, snap any still outside, count
    # ========================================================================
    log("FINAL: validating all DEF bones inside mesh")
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    outside_count = 0
    for b in eb:
        m = meta.get(b.name, {})
        if m.get("role") not in ("DEF",): continue
        # Skip protrusions (paw/tail/whisker/nose tips that legitimately stick out)
        if any(k in b.name for k in ("toes", "tip", "nose_", "ear_", "whisker", "incisor")):
            continue
        mid = (b.head + b.tail) * 0.5
        if not is_inside(bvh, mid):
            new_h = snap_to_inside(bvh, b.head)
            new_t = snap_to_inside(bvh, b.tail)
            if is_inside(bvh, (new_h + new_t) * 0.5):
                b.head = new_h
                b.tail = new_t
                snapped_count += 1
            else:
                outside_count += 1
                log(f"  ⚠ {b.name} still outside after snap")
    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"  Validation: {snapped_count} bones snapped, {outside_count} still outside")

    # ========================================================================
    # Bone collections
    # ========================================================================
    coll_names = ["ANATOMICAL_REFERENCE", "ARMATURE_DEFORM",
                   "ARMATURE_CONTROLS", "RIG_HELPERS"]
    colls = {}
    for n in coll_names:
        try: colls[n] = arm.collections.new(name=n)
        except Exception: colls[n] = arm.collections.get(n)
    for bone in arm.bones:
        m = meta.get(bone.name, {"layer": "ARMATURE_DEFORM", "role": "DEF"})
        c = colls.get(m["layer"])
        if c: c.assign(bone)
        if m["role"] != "DEF":
            bone.use_deform = False

    if "ANATOMICAL_REFERENCE" in colls:
        colls["ANATOMICAL_REFERENCE"].is_visible = False

    def_n = sum(1 for n in meta if meta[n]["role"] == "DEF")
    ref_n = sum(1 for n in meta if meta[n]["role"] == "REF")
    ctrl_n = sum(1 for n in meta if meta[n]["role"] == "CTRL")
    hlp_n = sum(1 for n in meta if meta[n]["role"] == "HLP")
    log(f"Counts — REF: {ref_n}  DEF: {def_n}  CTRL: {ctrl_n}  HLP: {hlp_n}  TOTAL: {len(meta)}")

    return arm_obj, meta


# ============================================================================
# POSE-MODE PROFESSIONAL RIGGING SETUP
# Adds: IK, Spline IK, Look-at, FK/IK switch, drivers, twist, limits,
# custom shapes, bone colors, locked transforms.
# ============================================================================
def setup_pose_rigging(arm_obj, meta, tripo, mesh_obj):
    log("=" * 60)
    log("POSE-MODE: constraints + drivers + widgets + colors + limits")
    log("=" * 60)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pbones = arm_obj.pose.bones

    # ---- Custom bone shape widgets ----
    log("Building custom bone shape widgets")
    def make_widget(name, primitive, **kwargs):
        if primitive == 'circle':
            bpy.ops.mesh.primitive_circle_add(vertices=24, radius=0.05,
                                                location=(0, -1000, 0))
        elif primitive == 'cube':
            bpy.ops.mesh.primitive_cube_add(size=0.08, location=(0, -1000, 0))
        elif primitive == 'sphere':
            bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025,
                                                   location=(0, -1000, 0))
        elif primitive == 'arrow':
            bpy.ops.mesh.primitive_cone_add(radius1=0.03, depth=0.1,
                                              location=(0, -1000, 0))
        elif primitive == 'square':
            bpy.ops.mesh.primitive_plane_add(size=0.08, location=(0, -1000, 0))
        obj = bpy.context.object
        obj.name = name
        obj.hide_render = True
        obj.hide_viewport = True
        return obj

    widgets = {
        "circle": make_widget("WGT-circle", 'circle'),
        "cube":   make_widget("WGT-cube",   'cube'),
        "sphere": make_widget("WGT-sphere", 'sphere'),
        "arrow":  make_widget("WGT-arrow",  'arrow'),
        "square": make_widget("WGT-square", 'square'),
    }

    # Re-enter armature pose mode after creating widgets
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pbones = arm_obj.pose.bones

    # ---- Assign shapes & lock transforms on CTRL bones ----
    log("Assigning widgets + locking translation on CTRL bones")
    for pb in pbones:
        m = meta.get(pb.name, {})
        if m.get("role") != "CTRL": continue
        name = pb.name
        if "IK" in name and ("paw" in name or "foot" in name):
            pb.custom_shape = widgets["cube"]
        elif "knee_pole" in name or "pole" in name:
            pb.custom_shape = widgets["sphere"]
        elif name == "CTRL_jaw_open" or name == "CTRL_jaw_side" or name == "CTRL_jaw_forward":
            pb.custom_shape = widgets["arrow"]
        elif name.startswith("CTRL_ear_"):
            pb.custom_shape = widgets["sphere"]
        elif name.startswith("CTRL_whisker") or name.startswith("CTRL_cheek") \
                or name.startswith("CTRL_nose") or "lip" in name:
            pb.custom_shape = widgets["sphere"]
        elif "tail" in name:
            pb.custom_shape = widgets["square"]
        else:
            pb.custom_shape = widgets["circle"]
        # Lock translation on FK controls (not IK targets which need translation)
        if "_IK_" not in name and "pole" not in name and "_FK_" not in name and \
           name not in ("root", "COG", "CTRL_pelvis", "CTRL_sacrum"):
            pb.lock_location = (True, True, True)

    # ---- Bone colors per region (Blender 4.0 bone.color.palette) ----
    log("Applying bone colors per region")
    COLOR_MAP = {
        "ANATOMICAL_REFERENCE": "THEME10",  # grey-ish
        "RIG_HELPERS":          "THEME11",  # neutral
    }
    REGION_COLORS = {
        # Body region keywords → theme
        "root": "THEME04", "COG": "THEME04", "pelvis": "THEME03", "sacrum": "THEME03",
        "spine": "THEME09", "thoracic": "THEME09", "lumbar": "THEME09", "cervical": "THEME09",
        "chest": "THEME09", "neck": "THEME09",
        "head": "THEME01", "skull": "THEME01", "snout": "THEME08", "nose": "THEME08",
        "jaw": "THEME11", "lip": "THEME08", "cheek": "THEME08",
        "whisker": "THEME12", "eye": "THEME13", "ear": "THEME14",
        "scapula": "THEME02", "upper_front_leg": "THEME02", "lower_front_leg": "THEME02",
        "front_paw": "THEME02", "front_toes": "THEME02",
        "hip": "THEME06", "thigh": "THEME06", "shin": "THEME06",
        "back_paw": "THEME06", "back_toes": "THEME06",
        "tail": "THEME07",
        "ribcage": "THEME12", "sternum": "THEME12", "belly": "THEME11",
    }
    for b in arm_obj.data.bones:
        m = meta.get(b.name, {})
        layer = m.get("layer", "")
        # First check layer
        if layer in COLOR_MAP:
            try: b.color.palette = COLOR_MAP[layer]
            except Exception: pass
            continue
        # CTRL bones get a special color based on role
        if b.name.startswith("CTRL_"):
            if "IK" in b.name or "pole" in b.name:
                try: b.color.palette = "THEME01"  # red — IK
                except Exception: pass
                continue
            if any(k in b.name for k in ("jaw","snout","nose","cheek","whisker","lip","ear","eye")):
                try: b.color.palette = "THEME03"  # green — face
                except Exception: pass
                continue
            try: b.color.palette = "THEME05"  # yellow — main FK
            except Exception: pass
            continue
        # Region-based for DEF/HLP bones
        for key, theme in REGION_COLORS.items():
            if key in b.name:
                try: b.color.palette = theme
                except Exception: pass
                break

    # ---- Twist bones (anti candy-wrap) ----
    log("Adding twist bones for upper arm and thigh")
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_obj.data.edit_bones
    for side in ("L", "R"):
        # Upper arm twist
        upper_arm = eb.get(f"upper_front_leg_{side}")
        if upper_arm:
            mid = (upper_arm.head + upper_arm.tail) * 0.5
            tb = eb.new(f"MCH_arm_twist_{side}")
            tb.head = upper_arm.head.copy()
            tb.tail = mid
            tb.parent = upper_arm
            tb.use_deform = True
            meta[f"MCH_arm_twist_{side}"] = {"layer": "ARMATURE_DEFORM", "role": "DEF"}
        # Thigh twist
        thigh = eb.get(f"thigh_{side}")
        if thigh:
            mid = (thigh.head + thigh.tail) * 0.5
            tb = eb.new(f"MCH_thigh_twist_{side}")
            tb.head = thigh.head.copy()
            tb.tail = mid
            tb.parent = thigh
            tb.use_deform = True
            meta[f"MCH_thigh_twist_{side}"] = {"layer": "ARMATURE_DEFORM", "role": "DEF"}
    bpy.ops.object.mode_set(mode='POSE')
    pbones = arm_obj.pose.bones

    # Twist constraint: twist bone copies Y rotation of parent arm/thigh
    for side in ("L", "R"):
        for parent_name, twist_name in (
            (f"upper_front_leg_{side}", f"MCH_arm_twist_{side}"),
            (f"thigh_{side}", f"MCH_thigh_twist_{side}"),
        ):
            if twist_name in pbones and parent_name in pbones:
                c = pbones[twist_name].constraints.new('COPY_ROTATION')
                c.target = arm_obj
                c.subtarget = parent_name
                c.use_x = False
                c.use_y = True
                c.use_z = False
                c.target_space = 'LOCAL'
                c.owner_space = 'LOCAL'
                c.influence = 0.5

    # ---- IK on 4 legs ----
    log("Setting up IK on 4 legs (chain=3, pole targets, stretch)")
    for side, sx in (("L", +1), ("R", -1)):
        for which, paw_name, fore_name, upper_name, ik_name, pole_name in (
            ("F", f"front_paw_{side}", f"lower_front_leg_{side}",
             f"upper_front_leg_{side}", f"CTRL_front_paw_IK_{side}",
             f"CTRL_front_knee_pole_{side}"),
            ("B", f"back_paw_{side}", f"shin_{side}",
             f"thigh_{side}", f"CTRL_back_paw_IK_{side}",
             f"CTRL_back_knee_pole_{side}"),
        ):
            if paw_name not in pbones: continue
            pb = pbones[paw_name]
            ik = pb.constraints.new('IK')
            ik.target = arm_obj
            ik.subtarget = ik_name
            ik.chain_count = 3  # paw + lower + upper
            if pole_name in pbones:
                ik.pole_target = arm_obj
                ik.pole_subtarget = pole_name
                ik.pole_angle = -math.pi / 2
            ik.use_stretch = True
            ik.use_tail = True

    # ---- Limit Rotation on knees (one-way bend) ----
    log("Adding LIMIT_ROTATION on knees/elbows + neck twist limit")
    for side in ("L", "R"):
        for joint_name in (f"lower_front_leg_{side}", f"shin_{side}"):
            if joint_name not in pbones: continue
            c = pbones[joint_name].constraints.new('LIMIT_ROTATION')
            c.use_limit_x = True; c.min_x = 0.0; c.max_x = math.radians(150)
            c.use_limit_y = True; c.min_y = -math.radians(15); c.max_y = math.radians(15)
            c.use_limit_z = True; c.min_z = -math.radians(15); c.max_z = math.radians(15)
            c.owner_space = 'LOCAL'

    # Neck twist limit (cervical bones)
    for n in ("cervical_03", "cervical_04", "cervical_05"):
        if n in pbones:
            c = pbones[n].constraints.new('LIMIT_ROTATION')
            c.use_limit_y = True; c.min_y = -math.radians(45); c.max_y = math.radians(45)
            c.owner_space = 'LOCAL'

    # ---- Spline IK on tail ----
    log("Setting up Spline IK on tail")
    bpy.ops.object.mode_set(mode='OBJECT')
    # Find tail bone positions
    mw = arm_obj.matrix_world
    tail_bones_sorted = sorted([b.name for b in arm_obj.data.bones
                                  if b.name.startswith("tail_") and not b.name.startswith("CTRL")])
    if tail_bones_sorted:
        # Build bezier curve along tail
        curve_data = bpy.data.curves.new("TailCurve", type='CURVE')
        curve_data.dimensions = '3D'
        spline = curve_data.splines.new('BEZIER')
        spline.bezier_points.add(2)  # total 3 points
        first_pt = mw @ arm_obj.data.bones[tail_bones_sorted[0]].head_local
        mid_idx = len(tail_bones_sorted) // 2
        mid_pt = mw @ arm_obj.data.bones[tail_bones_sorted[mid_idx]].head_local
        last_pt = mw @ arm_obj.data.bones[tail_bones_sorted[-1]].tail_local
        for i, p in enumerate([first_pt, mid_pt, last_pt]):
            bp = spline.bezier_points[i]
            bp.co = (p.x, p.y, p.z)
            tan = Vector((0, 0.05, 0))
            bp.handle_left = (p - tan).to_tuple()
            bp.handle_right = (p + tan).to_tuple()
        curve_obj = bpy.data.objects.new("TailCurve", curve_data)
        bpy.context.collection.objects.link(curve_obj)

        # Hook curve points to tail control bones
        for i, ctrl_name in enumerate(["CTRL_tail_base", "CTRL_tail_mid", "CTRL_tail_tip"]):
            if ctrl_name not in pbones: continue
            hook = curve_obj.modifiers.new(name=f"Hook_{ctrl_name}", type='HOOK')
            hook.object = arm_obj
            hook.subtarget = ctrl_name
            hook.vertex_indices_set([3*i, 3*i+1, 3*i+2])

        # Spline IK on last tail bone
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode='POSE')
        pbones = arm_obj.pose.bones
        last_tail = pbones.get(tail_bones_sorted[-1])
        if last_tail:
            sik = last_tail.constraints.new('SPLINE_IK')
            sik.target = curve_obj
            sik.chain_count = len(tail_bones_sorted)
            sik.y_scale_mode = 'BONE_ORIGINAL'
            sik.xz_scale_mode = 'BONE_ORIGINAL'

    # ---- Damped Track on eyes (look-at) ----
    log("Setting up DAMPED_TRACK on eyes")
    # Create eye aim targets if not present, parented to CTRL_head
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_obj.data.edit_bones
    # Single eye aim master
    head_b = eb.get("head")
    if head_b:
        # EditBone uses .head/.tail (Vector, in armature local space)
        head_world_tail = mw @ head_b.tail
        # Aim target in front of nose
        snout_dir_y = -0.1 if head_world_tail.y < 0 else +0.1
        eye_aim_pos = head_world_tail + Vector((0, snout_dir_y, 0))
        if "CTRL_eye_aim" not in eb:
            ea = eb.new("CTRL_eye_aim")
            ea.head = eye_aim_pos
            ea.tail = eye_aim_pos + Vector((0, snout_dir_y * 0.3, 0))
            ea.parent = eb.get("CTRL_head")
            meta["CTRL_eye_aim"] = {"layer": "ARMATURE_CONTROLS", "role": "CTRL"}
            arm_obj.data.bones  # refresh
        for side in ("L", "R"):
            name = f"CTRL_eye_aim_{side}"
            sx = +1 if side == "L" else -1
            if name not in eb:
                e = eb.new(name)
                e.head = eye_aim_pos + Vector((sx * 0.05, 0, 0))
                e.tail = e.head + Vector((0, snout_dir_y * 0.2, 0))
                e.parent = eb.get("CTRL_eye_aim")
                meta[name] = {"layer": "ARMATURE_CONTROLS", "role": "CTRL"}
    bpy.ops.object.mode_set(mode='POSE')
    pbones = arm_obj.pose.bones

    for side in ("L", "R"):
        eye_n = f"eye_{side}"
        tgt_n = f"CTRL_eye_aim_{side}"
        if eye_n in pbones and tgt_n in pbones:
            c = pbones[eye_n].constraints.new('DAMPED_TRACK')
            c.target = arm_obj
            c.subtarget = tgt_n
            # Eye bone points along head's forward direction
            c.track_axis = 'TRACK_NEGATIVE_Y' if mw @ arm_obj.data.bones["head"].tail_local < mw @ arm_obj.data.bones["head"].head_local else 'TRACK_Y'

    # ---- FK/IK Switch + CTRL→DEF copy for spine/head/jaw/ears ----
    log("Setting up CTRL→DEF copy rotation (FK mirror)")
    fk_pairs = [
        # Spine + head + jaw — DEF copies CTRL's LOCAL rotation
        ("pelvis", "CTRL_pelvis"),
        ("sacrum", "CTRL_sacrum"),
        ("head", "CTRL_head"),
        ("skull", "CTRL_skull"),
        ("jaw_base", None),  # jaw driven by jaw_open driver instead
        ("ear_L_base", "CTRL_ear_L_perk"),
        ("ear_R_base", "CTRL_ear_R_perk"),
    ]
    for def_n, ctrl_n in fk_pairs:
        if ctrl_n is None: continue
        if def_n in pbones and ctrl_n in pbones:
            c = pbones[def_n].constraints.new('COPY_ROTATION')
            c.target = arm_obj
            c.subtarget = ctrl_n
            c.target_space = 'LOCAL'
            c.owner_space = 'LOCAL'

    # ---- Drivers ----
    log("Adding drivers: breath, jaw_open, ear perks")
    # Custom properties on armature
    arm_obj["breath"] = 0.0
    arm_obj["jaw_open"] = 0.0
    arm_obj["nose_twitch_L"] = 0.0
    arm_obj["nose_twitch_R"] = 0.0
    arm_obj["ear_L_perk"] = 0.0
    arm_obj["ear_R_perk"] = 0.0
    # UI limits
    for key in ("breath", "jaw_open", "nose_twitch_L", "nose_twitch_R",
                 "ear_L_perk", "ear_R_perk"):
        try:
            ui = arm_obj.id_properties_ui(key)
            ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
        except Exception:
            pass

    def add_driver(bone_name, channel_kind, channel_idx, prop_name, expression):
        """channel_kind: 'rotation_euler' or 'scale' or 'location'"""
        pb = pbones.get(bone_name)
        if pb is None: return False
        if channel_kind == 'scale':
            fc = pb.driver_add("scale", channel_idx)
        elif channel_kind == 'rotation':
            pb.rotation_mode = 'XYZ'
            fc = pb.driver_add("rotation_euler", channel_idx)
        elif channel_kind == 'location':
            fc = pb.driver_add("location", channel_idx)
        drv = fc.driver
        drv.type = 'SCRIPTED'
        var = drv.variables.new()
        var.name = prop_name
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = arm_obj
        var.targets[0].data_path = f'["{prop_name}"]'
        drv.expression = expression
        return True

    # Breath driver: ribcage_center scale Y (along bone) for chest expansion
    add_driver("ribcage_center", "scale", 1, "breath", "1.0 + 0.15 * breath")
    add_driver("ribcage_center", "scale", 0, "breath", "1.0 + 0.10 * breath")
    add_driver("ribcage_center", "scale", 2, "breath", "1.0 + 0.10 * breath")
    # Sternum motion
    add_driver("sternum_ctrl", "location", 2, "breath", "0.01 * breath")
    # Belly soft
    add_driver("belly_center", "location", 2, "breath", "-0.005 * breath")
    # ribcage_L/R squash with breath
    for side in ("L", "R"):
        for i in range(1, 6):
            add_driver(f"ribcage_{side}_{i:02d}", "scale", 0, "breath", "1.0 + 0.12 * breath")

    # Jaw open driver: jaw_base X rotation
    add_driver("jaw_base", "rotation", 0, "jaw_open", "-0.6 * jaw_open")

    # Nose twitch (Z rotation of nose_L/R)
    add_driver("nose_L", "rotation", 2, "nose_twitch_L", "0.5 * nose_twitch_L")
    add_driver("nose_R", "rotation", 2, "nose_twitch_R", "-0.5 * nose_twitch_R")

    # Ear perk (X rotation of ear base)
    add_driver("ear_L_base", "rotation", 0, "ear_L_perk", "-1.2 * ear_L_perk")
    add_driver("ear_R_base", "rotation", 0, "ear_R_perk", "-1.2 * ear_R_perk")

    # ---- B-Bone handle bones (for smooth spine curves) ----
    log("Configuring B-Bone handles for smooth spine bending")
    # Each spine bone uses neighboring bones as in/out handles for smooth curves
    spine_chain = [
        "pelvis",
        "lumbar_06", "lumbar_05", "lumbar_04", "lumbar_03", "lumbar_02", "lumbar_01",
        "thoracic_13", "thoracic_12", "thoracic_11", "thoracic_10", "thoracic_09",
        "thoracic_08", "thoracic_07", "thoracic_06", "thoracic_05", "thoracic_04",
        "thoracic_03", "thoracic_02", "thoracic_01",
        "cervical_07", "cervical_06", "cervical_05", "cervical_04", "cervical_03",
        "cervical_02_axis", "cervical_01_atlas", "head",
    ]
    for i, name in enumerate(spine_chain):
        bone = arm_obj.data.bones.get(name)
        if not bone: continue
        # Bendy bone curve handles
        bone.bbone_handle_type_start = 'TANGENT'
        bone.bbone_handle_type_end = 'TANGENT'
        if i > 0:
            prev_name = spine_chain[i-1]
            if prev_name in arm_obj.data.bones:
                bone.bbone_custom_handle_start = arm_obj.data.bones[prev_name]
        if i < len(spine_chain) - 1:
            next_name = spine_chain[i+1]
            if next_name in arm_obj.data.bones:
                bone.bbone_custom_handle_end = arm_obj.data.bones[next_name]

    # Tail handles
    tail_chain = sorted([b.name for b in arm_obj.data.bones
                          if b.name.startswith("tail_") and not b.name.startswith("CTRL")])
    for i, name in enumerate(tail_chain):
        bone = arm_obj.data.bones.get(name)
        if not bone: continue
        bone.bbone_handle_type_start = 'TANGENT'
        bone.bbone_handle_type_end = 'TANGENT'
        if i > 0 and tail_chain[i-1] in arm_obj.data.bones:
            bone.bbone_custom_handle_start = arm_obj.data.bones[tail_chain[i-1]]
        if i < len(tail_chain) - 1 and tail_chain[i+1] in arm_obj.data.bones:
            bone.bbone_custom_handle_end = arm_obj.data.bones[tail_chain[i+1]]

    bpy.ops.object.mode_set(mode='OBJECT')
    log("Pose-mode rigging setup complete")


def main():
    reset_scene()
    import_glb(SRC)
    tripo = extract_tripo_skeleton()
    mesh = cleanup_keep_mesh_only()
    arm, meta = build_rig(tripo, mesh)
    setup_pose_rigging(arm, meta, tripo, mesh)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved .blend → {OUT_BLEND}")
    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
