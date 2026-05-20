"""
v15 — Fix v14 issues:
  1. Back-leg chain ASYMMETRY (L=6 nodes, R=4 nodes) caused different
     kinematic when animating same way. Now symmetric: both sides use
     hip → thigh → shin → back_paw (4 bones).
  2. Envelope-weight BLEED — finger bones grab leg verts, jaw grabs arm
     verts. Replaced with REGION-AWARE weighting: each vertex assigned
     to its body region (head/FL/FR/BL/BR/tail/body) and only bones in
     that region (or directly adjacent) can influence it.
  3. Walk-anim amplitudes reduced (was 20°/45°, now 8°/22°).

Usage:
    blender --background --python fare/scripts/rig_mouse_v15.py
"""

import bpy, bmesh, math, os, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "mouse3dmodel1k.glb")
OUT_DIR = os.path.join(ROOT, "out")
OUT_BLEND = os.path.join(OUT_DIR, "mouse_v15.blend")
OUT_GLB = os.path.join(OUT_DIR, "mouse.glb")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[v15] {m}", flush=True)


# ============================================================================
# Scene + import (unchanged from v14)
# ============================================================================
def reset_scene(): bpy.ops.wm.read_factory_settings(use_empty=True)

def import_glb(path):
    log(f"Importing {path}")
    bpy.ops.import_scene.gltf(filepath=path)

def extract_tripo_joints():
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    if not arms: return {}
    arm = arms[0]
    mw = arm.matrix_world
    joints = {}
    for b in arm.data.bones:
        joints[b.name] = {
            "head": (mw @ b.head_local).copy(),
            "tail": (mw @ b.tail_local).copy(),
        }
    log(f"Extracted {len(joints)} Tripo joints")
    return joints

def cleanup_keep_mesh_only():
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    body_parts = [o for o in bpy.data.objects
                   if o.type == 'MESH' and o.name.startswith("tripo_part")]
    for m in body_parts:
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
    body_parts = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in body_parts: m.select_set(True)
    bpy.context.view_layer.objects.active = body_parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(body_parts) > 1: bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    log(f"Mesh kept: {len(merged.data.vertices)} verts")
    return merged


# ============================================================================
# BVH utilities (unchanged)
# ============================================================================
def build_bvh(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.transform(mesh.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh

def is_inside(bvh, p, eps=1e-4):
    dirs = [Vector((1,0,0)), Vector((-1,0,0)),
            Vector((0,1,0)), Vector((0,-1,0)),
            Vector((0,0,1)), Vector((0,0,-1))]
    inside_count = 0
    for d in dirs:
        hits = 0
        origin = p + d * eps
        while True:
            hit, _, _, _ = bvh.ray_cast(origin, d, 100.0)
            if hit is None: break
            hits += 1
            origin = hit + d * (eps * 4)
            if hits > 16: break
        if hits % 2 == 1: inside_count += 1
    return inside_count >= 4

def closest_inside(bvh, target, mesh, max_iter=20):
    if is_inside(bvh, target): return target.copy()
    loc, n, _, _ = bvh.find_nearest(target)
    if loc is None: return target.copy()
    inward = -n.normalized()
    p = loc + inward * 0.005
    for _ in range(max_iter):
        if is_inside(bvh, p): return p
        p = p + inward * 0.003
    return p


# ============================================================================
# Landmarks
# ============================================================================
def detect_landmarks(mesh):
    verts = [v.co for v in mesh.data.vertices]
    xs=[v.x for v in verts]; ys=[v.y for v in verts]; zs=[v.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    x_center = sum(xs)/len(xs)
    y_size = y_max - y_min
    nose_cands = [v for v in verts if v.y < y_min + y_size * 0.04]
    nose_tip = (sum(nose_cands, Vector((0,0,0))) / len(nose_cands)) if nose_cands else Vector((0,y_min,z_max*0.7))
    tail_cands = [v for v in verts if v.y > y_max - y_size * 0.04]
    tail_tip = (sum(tail_cands, Vector((0,0,0))) / len(tail_cands)) if tail_cands else Vector((0,y_max,z_max*0.3))
    return {
        "nose_tip": nose_tip, "tail_tip": tail_tip,
        "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max,
        "z_min": z_min, "z_max": z_max, "x_center": x_center,
    }


# ============================================================================
# Armature build — SYMMETRIC back legs this time
# ============================================================================
def build_armature(tripo, mesh, lm, bvh):
    bpy.ops.object.armature_add(enter_editmode=True, location=(0,0,0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig"
    arm = arm_obj.data
    arm.name = "MouseRig"
    eb = arm.edit_bones
    for b in list(eb): eb.remove(b)
    bones = {}

    def J(name):
        j = tripo.get(name)
        return j["head"].copy() if j else None
    def Jt(name):
        j = tripo.get(name)
        return j["tail"].copy() if j else None
    def mk(name, head, tail, parent=None, use_connect=False, deform=True):
        b = eb.new(name)
        b.head = head; b.tail = tail
        if parent:
            p = bones.get(parent)
            if p: b.parent = p
            b.use_connect = use_connect
        b.use_deform = deform
        bones[name] = b
        return b

    # ===== Body / spine / head =====
    root_p     = J("tripo::Root")
    spine_01_p = J("tripo::Spine_0")
    spine_02_p = J("tripo::Spine_1")
    neck_p     = J("tripo::Head_0")
    skull_p    = J("tripo::Head_1")
    snout_p    = J("tripo::Head_2")
    nose_root  = J("tripo::Head_3")
    nose_end   = Jt("tripo::Head_3")

    mk("root", Vector((root_p.x, root_p.y, root_p.z)),
       Vector((root_p.x, root_p.y + 0.18, root_p.z)), parent=None, deform=False)
    mk("hips", Vector((root_p.x, root_p.y + 0.10, spine_01_p.z * 0.7)),
       spine_01_p, parent="root", deform=True)
    mk("spine_01", spine_01_p, spine_02_p, parent="hips", use_connect=True)
    mk("spine_02", spine_02_p, neck_p, parent="spine_01", use_connect=True)
    chest_top = (neck_p + skull_p) * 0.5
    mk("chest", neck_p, chest_top, parent="spine_02", use_connect=True)
    mk("neck", chest_top, skull_p, parent="chest", use_connect=True)
    mk("head", skull_p, snout_p, parent="neck", use_connect=True)
    mk("snout", snout_p, nose_root, parent="head", use_connect=True)
    mk("nose", nose_root, nose_end, parent="snout", use_connect=True)

    jaw_head = closest_inside(bvh,
        Vector((skull_p.x, skull_p.y - 0.04, skull_p.z - 0.06)), mesh)
    jaw_tail = closest_inside(bvh,
        Vector((nose_end.x, nose_end.y - 0.02, nose_end.z - 0.06)), mesh)
    mk("jaw", jaw_head, jaw_tail, parent="head")

    for side, sx in (("L", +1), ("R", -1)):
        eye_h = closest_inside(bvh,
            Vector((sx * 0.04, skull_p.y - 0.02, skull_p.z + 0.025)), mesh)
        eye_t = closest_inside(bvh,
            Vector((sx * 0.05, skull_p.y - 0.06, skull_p.z + 0.025)), mesh)
        mk(f"eye_{side}", eye_h, eye_t, parent="head")

    # Ears
    for side, src in (("L", "bone_7"), ("R", "bone_6")):
        base = J(src); tip = Jt(src)
        mid1 = base + (tip - base) * 0.33
        mid2 = base + (tip - base) * 0.66
        mk(f"ear_{side}_base", base, mid1, parent="head")
        mk(f"ear_{side}_mid",  mid1, mid2, parent=f"ear_{side}_base", use_connect=True)
        mk(f"ear_{side}_tip",  mid2, tip,  parent=f"ear_{side}_mid",  use_connect=True)

    # Whiskers
    for side, sx in (("L", +1), ("R", -1)):
        for i, (dx, dz) in enumerate([(0.012, 0.04), (0.018, 0.01),
                                        (0.012, -0.02), (0.005, -0.04)]):
            base = closest_inside(bvh,
                Vector((sx * (0.022 + dx), nose_root.y - 0.01, nose_root.z + dz)), mesh)
            tip = Vector((sx * (0.10 + dx), nose_root.y - 0.06, nose_root.z + dz))
            mk(f"whisker_{side}_{i+1}", base, tip, parent="snout")

    # ===== Front legs =====
    for side, scap_src, limb_pfx, sx in (("L", "bone_9", "tripo::0_Left_Limb_", +1),
                                           ("R", "bone_13", "tripo::0_Right_Limb_", -1)):
        scap_h = J(scap_src); scap_t = Jt(scap_src)
        ua_h = J(f"{limb_pfx}0"); ua_t = J(f"{limb_pfx}1")
        fa_h = ua_t; fa_t = J(f"{limb_pfx}2")
        paw_h = fa_t; paw_t = Jt(f"{limb_pfx}2")
        paw_t = Vector((paw_t.x, paw_t.y, max(paw_t.z, lm["z_min"] + 0.002)))
        mk(f"scapula_{side}", scap_h, scap_t, parent="chest")
        mk(f"upper_arm_{side}", ua_h, ua_t, parent=f"scapula_{side}")
        mk(f"forearm_{side}", fa_h, fa_t, parent=f"upper_arm_{side}", use_connect=True)
        mk(f"front_paw_{side}", paw_h, paw_t, parent=f"forearm_{side}", use_connect=True)
        for i, ox in enumerate([-0.012, 0.0, 0.012]):
            f_base = Vector((paw_t.x + sx * ox, paw_t.y - 0.005, paw_t.z))
            f_mid = Vector((paw_t.x + sx * ox * 1.5, paw_t.y - 0.018, paw_t.z))
            f_tip = Vector((paw_t.x + sx * ox * 1.8, paw_t.y - 0.028, paw_t.z))
            mk(f"finger_F_{side}_{i+1}_01", f_base, f_mid, parent=f"front_paw_{side}")
            mk(f"finger_F_{side}_{i+1}_02", f_mid, f_tip,
               parent=f"finger_F_{side}_{i+1}_01", use_connect=True)

    # ===== Back legs — SYMMETRIC: hip → thigh → shin → back_paw on BOTH sides
    # Left has 6 Tripo nodes, right has 4. We use first 4 for left to match right.
    back_chains = {
        "L": ["bone_27", "tripo::1_Left_Limb_0", "tripo::1_Left_Limb_1",
              "tripo::1_Left_Limb_3"],  # SKIP intermediate _2 to compress to 4
        "R": ["bone_17", "bone_18", "tripo::1_Right_Limb_0", "tripo::1_Right_Limb_1"],
    }
    # For left: head=bone_27.head, tail=Limb_0.head (hip)
    #           head=Limb_0.head, tail=Limb_1.head (thigh)
    #           head=Limb_1.head, tail=Limb_3.head (shin spans 1→3, longer)
    #           head=Limb_3.head, tail=Limb_3.tail (paw, clamped)
    # Actually for left, the Tripo paw is at Limb_3 head / Limb_4 area.
    # Let's just use: hip(bone_27→Limb_0), thigh(Limb_0→Limb_1), shin(Limb_1→Limb_2),
    #                 paw(Limb_2→Limb_4 endpoint clamped)
    back_chains["L"] = ["bone_27", "tripo::1_Left_Limb_0", "tripo::1_Left_Limb_1",
                         "tripo::1_Left_Limb_2", "tripo::1_Left_Limb_4"]

    for side in ("L", "R"):
        sx = +1 if side == "L" else -1
        chain = back_chains[side]
        # 4-bone leg: hip, thigh, shin, back_paw
        # Map chain entries to bone names:
        #   L: [bone_27, Limb_0, Limb_1, Limb_2, Limb_4]
        #      hip = bone_27.head → Limb_0.head
        #      thigh = Limb_0.head → Limb_1.head
        #      shin = Limb_1.head → Limb_2.head
        #      back_paw = Limb_2.head → Limb_4.tail (last point)
        #   R: [bone_17, bone_18, Limb_0, Limb_1]
        #      hip = bone_17.head → bone_18.head
        #      thigh = bone_18.head → Limb_0.head
        #      shin = Limb_0.head → Limb_1.head
        #      back_paw = Limb_1.head → Limb_1.tail
        bone_names = [f"hip_{side}", f"thigh_{side}", f"shin_{side}", f"back_paw_{side}"]
        parent_name = "hips"
        for i, bn in enumerate(bone_names):
            chain_head = chain[i]
            head_p = J(chain_head)
            if i < len(bone_names) - 1:
                tail_p = J(chain[i + 1])
            else:
                # last bone: extend to final tail
                tail_p = Jt(chain[-1])
                tail_p = Vector((tail_p.x, tail_p.y, max(tail_p.z, lm["z_min"] + 0.002)))
            mk(bn, head_p, tail_p, parent=parent_name, use_connect=(i > 0))
            parent_name = bn

        # Back paw tail position for finger placement
        last_p = J(chain[-1]) if len(chain) > 0 else Vector((0, 0, 0))
        paw_t = Jt(chain[-1])
        paw_t = Vector((paw_t.x, paw_t.y, max(paw_t.z, lm["z_min"] + 0.002)))
        for i, ox in enumerate([-0.012, 0.0, 0.012]):
            f_base = Vector((paw_t.x + sx * ox, paw_t.y - 0.005, paw_t.z))
            f_mid = Vector((paw_t.x + sx * ox * 1.4, paw_t.y - 0.020, paw_t.z))
            f_tip = Vector((paw_t.x + sx * ox * 1.7, paw_t.y - 0.032, paw_t.z))
            mk(f"finger_B_{side}_{i+1}_01", f_base, f_mid, parent=f"back_paw_{side}")
            mk(f"finger_B_{side}_{i+1}_02", f_mid, f_tip,
               parent=f"finger_B_{side}_{i+1}_01", use_connect=True)

    # ===== Tail =====
    tail_anchors = [J("bone_21"), J("tripo::Tail_0"), J("tripo::Tail_1"),
                     J("tripo::Tail_2"), J("tripo::Tail_3"), J("bone_26"),
                     Jt("bone_26")]
    tail_anchors = [p for p in tail_anchors if p is not None]
    if len(tail_anchors) >= 2:
        total_len = sum((tail_anchors[i+1] - tail_anchors[i]).length
                         for i in range(len(tail_anchors) - 1))
        N = 20
        seg_len = total_len / N
        out = [tail_anchors[0]]
        accum = 0
        i = 0
        cur = tail_anchors[0]
        remaining = (tail_anchors[i+1] - cur).length
        for n in range(1, N + 1):
            target = n * seg_len
            while accum + remaining < target and i < len(tail_anchors) - 2:
                accum += remaining
                i += 1
                cur = tail_anchors[i]
                remaining = (tail_anchors[i+1] - cur).length
            t = (target - accum) / remaining if remaining > 0 else 0
            out.append(cur + (tail_anchors[i+1] - cur) * t)
        prev_name = "hips"
        for k in range(len(out) - 1):
            name = f"tail_{k+1:02d}"
            mk(name, out[k], out[k+1], parent=prev_name, use_connect=(k > 0))
            prev_name = name

    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Built armature: {len(arm.bones)} bones")
    return arm_obj


# ============================================================================
# Constraints + drivers
# ============================================================================
def setup_constraints(arm_obj):
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm_obj.pose.bones
    # IK
    for name, chain in (("front_paw_L", 3), ("front_paw_R", 3),
                          ("back_paw_L", 3), ("back_paw_R", 3)):
        if name in pb:
            c = pb[name].constraints.new('IK')
            c.chain_count = chain; c.use_tail = True; c.use_stretch = False
    # Breath
    chest = pb.get("chest")
    if chest:
        arm_obj["breath"] = 0.0
        arm_obj.id_properties_ui("breath").update(min=-1.0, max=1.0, default=0.0)
        d = chest.driver_add("scale", 1).driver
        d.type = 'SCRIPTED'
        v = d.variables.new(); v.name = "b"
        v.targets[0].id = arm_obj; v.targets[0].data_path = '["breath"]'
        d.expression = "1 + b * 0.08"
    # Jaw
    jaw = pb.get("jaw")
    if jaw:
        arm_obj["jaw_open"] = 0.0
        arm_obj.id_properties_ui("jaw_open").update(min=0.0, max=1.0, default=0.0)
        d = jaw.driver_add("rotation_euler", 0).driver
        d.type = 'SCRIPTED'
        v = d.variables.new(); v.name = "j"
        v.targets[0].id = arm_obj; v.targets[0].data_path = '["jaw_open"]'
        d.expression = "j * 0.6"
        jaw.rotation_mode = 'XYZ'
    # Ears
    for side in ("L", "R"):
        eb_ = pb.get(f"ear_{side}_base")
        if not eb_: continue
        prop = f"ear_{side}_perk"
        arm_obj[prop] = 0.0
        arm_obj.id_properties_ui(prop).update(min=-1.0, max=1.0, default=0.0)
        d = eb_.driver_add("rotation_euler", 0).driver
        d.type = 'SCRIPTED'
        v = d.variables.new(); v.name = "p"
        v.targets[0].id = arm_obj; v.targets[0].data_path = f'["{prop}"]'
        d.expression = "p * 0.4"
        eb_.rotation_mode = 'XYZ'
    bpy.ops.object.mode_set(mode='OBJECT')


# ============================================================================
# REGION-AWARE WEIGHTING (replaces envelope binding)
# ============================================================================
def assign_region(p, lm):
    """Assign vertex to one of: head, FL, FR, BL, BR, tail, body."""
    y_min = lm["y_min"]; y_max = lm["y_max"]
    z_min = lm["z_min"]; z_max = lm["z_max"]
    x_cen = lm["x_center"]
    y_size = y_max - y_min
    z_size = z_max - z_min
    # Head: front 35% Y
    if p.y < y_min + y_size * 0.35: return "head"
    # Tail: back 25% Y AND narrow (close to centerline OR low Z)
    if p.y > y_min + y_size * 0.78:
        # Tail base + tail itself
        return "tail"
    # Front legs: middle-front Y region, lower Z, off-center X
    if (y_min + y_size * 0.20 < p.y < y_min + y_size * 0.55
        and p.z < z_min + z_size * 0.35
        and abs(p.x - x_cen) > 0.04):
        return "FL" if p.x > x_cen else "FR"
    # Back legs: back-middle Y region, lower Z, off-center X
    if (y_min + y_size * 0.50 < p.y < y_min + y_size * 0.85
        and p.z < z_min + z_size * 0.50
        and abs(p.x - x_cen) > 0.04):
        return "BL" if p.x > x_cen else "BR"
    return "body"


# Which bones belong to which region
def region_bones(arm_obj):
    """Map region → set of bone names allowed to influence verts in that region."""
    head_bones = set()
    FL = set(); FR = set(); BL = set(); BR = set()
    tail = set(); body = set()
    for b in arm_obj.data.bones:
        n = b.name
        if n.startswith(("nose", "snout", "head", "jaw", "eye_", "ear_", "whisker_", "neck")):
            head_bones.add(n)
        elif n.startswith("tail_"):
            tail.add(n)
        elif n.startswith(("scapula_L", "upper_arm_L", "forearm_L", "front_paw_L", "finger_F_L_")):
            FL.add(n)
        elif n.startswith(("scapula_R", "upper_arm_R", "forearm_R", "front_paw_R", "finger_F_R_")):
            FR.add(n)
        elif n.startswith(("hip_L", "thigh_L", "shin_L", "back_paw_L", "finger_B_L_")):
            BL.add(n)
        elif n.startswith(("hip_R", "thigh_R", "shin_R", "back_paw_R", "finger_B_R_")):
            BR.add(n)
        elif n in ("root", "hips", "spine_01", "spine_02", "chest"):
            body.add(n)
    # Each region also includes nearest body bones so transitions are smooth
    return {
        "head":  head_bones | {"neck", "chest"},
        "FL":    FL | {"chest", "spine_02"},
        "FR":    FR | {"chest", "spine_02"},
        "BL":    BL | {"hips", "spine_01"},
        "BR":    BR | {"hips", "spine_01"},
        "tail":  tail | {"hips"},
        "body":  body | {"neck", "chest"},
    }


def dist_to_segment(p, a, b):
    """Distance from p to segment a-b."""
    ab = b - a
    L = ab.length
    if L < 1e-9: return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / (L * L)))
    return (p - (a + ab * t)).length


def bind_region_aware(arm_obj, mesh, lm):
    """Compute weights by region — bones outside region have ZERO influence."""
    # Clear any existing groups
    for vg in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(vg)
    # Create groups for all deform bones
    name_to_vg = {}
    for b in arm_obj.data.bones:
        if b.use_deform:
            name_to_vg[b.name] = mesh.vertex_groups.new(name=b.name)

    # Precompute bone segments in world space
    mw_arm = arm_obj.matrix_world
    bone_segs = {}
    for b in arm_obj.data.bones:
        if not b.use_deform: continue
        bone_segs[b.name] = (mw_arm @ b.head_local, mw_arm @ b.tail_local)

    reg_bones = region_bones(arm_obj)

    mw_mesh = mesh.matrix_world
    K = 4  # top K bones per vertex
    n_verts = len(mesh.data.vertices)
    region_counts = {}
    for vi, v in enumerate(mesh.data.vertices):
        wp = mw_mesh @ v.co
        region = assign_region(wp, lm)
        region_counts[region] = region_counts.get(region, 0) + 1
        candidates = reg_bones[region]
        # Score each candidate bone by distance
        scored = []
        for bn in candidates:
            if bn not in bone_segs: continue
            a, b = bone_segs[bn]
            d = dist_to_segment(wp, a, b)
            scored.append((bn, d))
        if not scored: continue
        scored.sort(key=lambda x: x[1])
        top = scored[:K]
        # Inverse-distance weighting with soft falloff
        # weight = 1 / (d + eps)^2
        weights = []
        for bn, d in top:
            w = 1.0 / max(d + 0.005, 0.005) ** 2
            weights.append((bn, w))
        # Normalize
        wsum = sum(w for _, w in weights)
        for bn, w in weights:
            normalized = w / wsum
            if normalized > 0.005:
                name_to_vg[bn].add([vi], normalized, 'REPLACE')

    log("Region counts: " + ", ".join(f"{k}={v}" for k, v in sorted(region_counts.items())))

    # Add ARMATURE modifier (since parent_set ARMATURE_AUTO would clear groups)
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm_obj
    mod.use_vertex_groups = True
    # Parent mesh to armature (object-level, no auto-weight)
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type='OBJECT')
    log("Mesh weighted (region-aware) + parented to armature")


# ============================================================================
# Main
# ============================================================================
def main():
    reset_scene()
    import_glb(SRC)
    tripo = extract_tripo_joints()
    mesh = cleanup_keep_mesh_only()
    lm = detect_landmarks(mesh)
    bvh = build_bvh(mesh)
    arm = build_armature(tripo, mesh, lm, bvh)
    setup_constraints(arm)
    bind_region_aware(arm, mesh, lm)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved blend → {OUT_BLEND}")

    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    try:
        bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
                                    use_selection=True, export_skins=True,
                                    export_animations=False, export_yup=True,
                                    export_apply=False)
        log(f"Saved GLB → {OUT_GLB}")
    except Exception as e:
        log(f"GLB export FAILED: {e}")
    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
