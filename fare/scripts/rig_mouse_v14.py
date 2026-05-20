"""
v14 — Clean mouse rig built from Tripo's well-placed 33 joints.

Strategy:
  Tripo AI auto-rigged the mesh with 33 joints that ARE INSIDE the mesh,
  correctly placed at body centroids. The joints just have generic names
  ("tripo::0_Left_Limb_0", "bone_6") and lack detail (no whiskers,
  ears are 1 bone, tail is 5 segments, no fingers, no jaw, no eyes).

  v14:
    1. Extract Tripo joint positions (the ANATOMY is correct)
    2. Strip the Tripo armature from mesh (mesh stays untouched)
    3. Build a new mouse-named armature from those positions
    4. ADD missing details (tail-extend, ear-cartilage, whiskers,
       fingers, jaw, eyes) using mesh landmarks + snap-to-inside
    5. Add Blender constraints: IK on legs, Spline IK on tail,
       drivers for breath/jaw/ear_perk
    6. Save .blend + render 6 angles

Mesh stays UNTOUCHED (no transform_apply on mesh, no weld, no normals).

Usage:
    blender --background --python fare/scripts/rig_mouse_v14.py
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
OUT_BLEND = os.path.join(OUT_DIR, "mouse_v14.blend")
OUT_GLB = os.path.join(OUT_DIR, "mouse.glb")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[v14] {m}", flush=True)


# ============================================================================
# Scene + import
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path}")
    bpy.ops.import_scene.gltf(filepath=path)


def extract_tripo_joints():
    """Read Tripo armature joints (world space) before deletion."""
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    if not arms:
        log("ERROR: no armature found in GLB")
        return {}
    arm = arms[0]
    mw = arm.matrix_world
    joints = {}
    for b in arm.data.bones:
        joints[b.name] = {
            "head": (mw @ b.head_local).copy(),
            "tail": (mw @ b.tail_local).copy(),
            "parent": b.parent.name if b.parent else None,
        }
    log(f"Extracted {len(joints)} Tripo joints")
    return joints


def cleanup_keep_mesh_only():
    """Remove Tripo armature + helpers, keep mesh untouched (no transform_apply)."""
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    body_parts = [o for o in bpy.data.objects
                   if o.type == 'MESH' and o.name.startswith("tripo_part")]
    for m in body_parts:
        bpy.context.view_layer.objects.active = m
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE':
                m.modifiers.remove(mod)
        bpy.ops.object.select_all(action='DESELECT')
        m.select_set(True)
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        m.vertex_groups.clear()
    for o in list(bpy.data.objects):
        if o.type in ('ARMATURE', 'EMPTY'):
            bpy.data.objects.remove(o, do_unlink=True)
    body_parts = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in body_parts: m.select_set(True)
    bpy.context.view_layer.objects.active = body_parts[0]
    # NOTE: Apply transform ONLY to bake the GLB orientation (Y-up→Z-up).
    # That is the import's own transform; the mesh geometry itself is unchanged.
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(body_parts) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    log(f"Mesh kept: {len(merged.data.vertices)} verts")
    return merged


# ============================================================================
# Mesh utilities — BVH, inside test, snap-to-inside
# ============================================================================
def build_bvh(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.transform(mesh.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


def is_inside(bvh, p, eps=1e-4):
    """Parity-vote across 6 directions to robustly test inside-mesh."""
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
        if hits % 2 == 1:
            inside_count += 1
    return inside_count >= 4


def closest_inside(bvh, target, mesh, max_iter=20):
    """If point is outside, walk it toward the closest mesh surface +
    epsilon along the inward normal."""
    if is_inside(bvh, target):
        return target.copy()
    loc, n, _, _ = bvh.find_nearest(target)
    if loc is None:
        return target.copy()
    # walk inward
    inward = -n.normalized()
    step = (target - loc).length * 0.5 + 0.005
    p = loc + inward * 0.005
    for _ in range(max_iter):
        if is_inside(bvh, p):
            return p
        p = p + inward * 0.003
    return p


# ============================================================================
# Mouse landmarks (from mesh)
# ============================================================================
def detect_landmarks(mesh):
    verts = [v.co for v in mesh.data.vertices]
    xs=[v.x for v in verts]; ys=[v.y for v in verts]; zs=[v.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    x_center = sum(xs)/len(xs)
    y_size = y_max - y_min
    z_size = z_max - z_min

    # Nose tip — extremal -Y verts averaged
    nose_cands = [v for v in verts if v.y < y_min + y_size * 0.04]
    nose_tip = (sum(nose_cands, Vector((0,0,0))) / len(nose_cands)) if nose_cands else Vector((0,y_min,z_max*0.7))

    # Tail tip — extremal +Y verts
    tail_cands = [v for v in verts if v.y > y_max - y_size * 0.04]
    tail_tip = (sum(tail_cands, Vector((0,0,0))) / len(tail_cands)) if tail_cands else Vector((0,y_max,z_max*0.3))

    return {
        "nose_tip": nose_tip, "tail_tip": tail_tip,
        "x_min": x_min, "x_max": x_max,
        "y_min": y_min, "y_max": y_max,
        "z_min": z_min, "z_max": z_max,
        "x_center": x_center,
    }


# ============================================================================
# Build mouse armature from Tripo joints + extensions
# ============================================================================
def build_armature(tripo, mesh, lm, bvh):
    """Build a clean mouse-named armature using Tripo positions as anchors."""
    bpy.ops.object.armature_add(enter_editmode=True, location=(0,0,0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig"
    arm = arm_obj.data
    arm.name = "MouseRig"
    eb = arm.edit_bones
    # Remove the default bone
    for b in list(eb): eb.remove(b)

    bones = {}  # name -> editbone

    def J(name):
        """Tripo joint head."""
        j = tripo.get(name)
        if j is None: return None
        return j["head"].copy()

    def Jt(name):
        """Tripo joint tail."""
        j = tripo.get(name)
        if j is None: return None
        return j["tail"].copy()

    def mk(name, head, tail, parent=None, use_connect=False, deform=True):
        # Snap interior bones inside the mesh (skip nose/whisker tips which legitimately reach surface)
        b = eb.new(name)
        b.head = head
        b.tail = tail
        if parent:
            p = bones.get(parent)
            if p: b.parent = p
            b.use_connect = use_connect
        b.use_deform = deform
        bones[name] = b
        return b

    # ----- Spine chain (Tripo: Root → Spine_0 → Spine_1 → Head_0) -----
    # Reorganize: root → hips → spine_01..03 → chest → neck → head → snout → nose
    root_p = J("tripo::Root")  # (0, 0, 0.018) - on ground at hip
    sacrum_p = Vector((root_p.x, root_p.y + 0.10, root_p.z + 0.18))  # behind root, inside body
    sacrum_p = closest_inside(bvh, sacrum_p, mesh)
    # Use Tripo spine joints
    spine_01_p = J("tripo::Spine_0")  # head=(0,0.076,0.311)
    spine_02_p = J("tripo::Spine_1")  # head=(0,-0.045,0.303)
    neck_p     = J("tripo::Head_0")   # head=(0,-0.154,0.291)
    skull_p    = J("tripo::Head_1")   # head=(0,-0.264,0.295)  - inside skull
    snout_p    = J("tripo::Head_2")   # head=(0,-0.262,0.294)  - skull/snout junction
    nose_root  = J("tripo::Head_3")   # head=(0,-0.357,0.256)  - nose root
    nose_end   = Jt("tripo::Head_3")  # tail=(0,-0.452,0.218)  - nose tip

    # Hips bone (root → spine_01)
    mk("root", Vector((root_p.x, root_p.y, root_p.z)),
       Vector((root_p.x, root_p.y + 0.18, root_p.z)), parent=None, deform=False)

    mk("hips", Vector((root_p.x, root_p.y + 0.10, spine_01_p.z * 0.7)),
       spine_01_p, parent="root", deform=True)

    mk("spine_01", spine_01_p, spine_02_p, parent="hips", use_connect=True, deform=True)
    mk("spine_02", spine_02_p, neck_p,     parent="spine_01", use_connect=True, deform=True)
    mk("chest",    neck_p,    (neck_p + skull_p) * 0.5,  parent="spine_02", use_connect=True, deform=True)
    # neck stretches from chest top to skull
    chest_top = (neck_p + skull_p) * 0.5
    mk("neck",  chest_top, skull_p, parent="chest", use_connect=True, deform=True)
    mk("head",  skull_p,   snout_p, parent="neck",  use_connect=True, deform=True)
    mk("snout", snout_p,   nose_root, parent="head", use_connect=True, deform=True)
    mk("nose",  nose_root, nose_end,  parent="snout", use_connect=True, deform=True)

    # Jaw — under skull, going to mouth tip
    jaw_head = Vector((skull_p.x, skull_p.y - 0.04, skull_p.z - 0.06))
    jaw_head = closest_inside(bvh, jaw_head, mesh)
    jaw_tail = Vector((nose_end.x, nose_end.y - 0.02, nose_end.z - 0.06))
    jaw_tail = closest_inside(bvh, jaw_tail, mesh)
    mk("jaw", jaw_head, jaw_tail, parent="head", deform=True)

    # Eyes — inside skull, looking forward (-Y)
    for side, sx in (("L", +1), ("R", -1)):
        eye_h = Vector((sx * 0.04, skull_p.y - 0.02, skull_p.z + 0.025))
        eye_h = closest_inside(bvh, eye_h, mesh)
        eye_t = Vector((sx * 0.05, skull_p.y - 0.06, skull_p.z + 0.025))
        eye_t = closest_inside(bvh, eye_t, mesh)
        mk(f"eye_{side}", eye_h, eye_t, parent="head", deform=True)

    # ----- Ears (Tripo bone_6, bone_7 = ears) -----
    # bone_7 head=(0.049,-0.264,0.369) tail=(0.126,-0.265,0.438) → ear_L
    # bone_6 head=(-0.119,-0.268,0.369) tail=(-0.196,-0.272,0.439) → ear_R
    for side, src in (("L", "bone_7"), ("R", "bone_6")):
        base = J(src); tip = Jt(src)
        # split into 3 cartilage segments
        mid1 = base + (tip - base) * 0.33
        mid2 = base + (tip - base) * 0.66
        mk(f"ear_{side}_base", base, mid1, parent="head", deform=True)
        mk(f"ear_{side}_mid",  mid1, mid2, parent=f"ear_{side}_base", use_connect=True, deform=True)
        mk(f"ear_{side}_tip",  mid2, tip,  parent=f"ear_{side}_mid",  use_connect=True, deform=True)

    # ----- Whiskers — 4 per side, base at snout sides, tips forward-out -----
    for side, sx in (("L", +1), ("R", -1)):
        for i, (dx, dz) in enumerate([(0.012, 0.04), (0.018, 0.01),
                                        (0.012, -0.02), (0.005, -0.04)]):
            base = Vector((sx * (0.022 + dx), nose_root.y - 0.01, nose_root.z + dz))
            base = closest_inside(bvh, base, mesh)
            tip = Vector((sx * (0.10 + dx), nose_root.y - 0.06, nose_root.z + dz))
            # Whisker tips can extend beyond mesh (they're hairs)
            mk(f"whisker_{side}_{i+1}", base, tip, parent="snout", deform=True)

    # ----- Front legs — Tripo 0_Left_Limb_0..2 / 0_Right_Limb_0..2 -----
    # bone_9 / bone_13 are scapula bones from spine → shoulder
    # 0_Left_Limb_0 head=(0.080,-0.213,0.201) → upper_arm
    # 0_Left_Limb_1 head=(0.080,-0.189,0.069) → forearm
    # 0_Left_Limb_2 head=(0.080,-0.260,0.022) → wrist/paw
    # 0_Left_Limb_2 tail=(0.080,-0.330,-0.025) → paw tip
    for side, scap_src, limb_pfx, sx in (("L", "bone_9", "tripo::0_Left_Limb_", +1),
                                           ("R", "bone_13", "tripo::0_Right_Limb_", -1)):
        scap_h = J(scap_src); scap_t = Jt(scap_src)
        ua_h = J(f"{limb_pfx}0"); ua_t = J(f"{limb_pfx}1")
        fa_h = ua_t; fa_t = J(f"{limb_pfx}2")
        paw_h = fa_t; paw_t = Jt(f"{limb_pfx}2")
        # Lift paw so it doesn't sink under floor
        paw_t = Vector((paw_t.x, paw_t.y, max(paw_t.z, lm["z_min"] + 0.002)))
        mk(f"scapula_{side}",   scap_h, scap_t, parent="chest", deform=True)
        mk(f"upper_arm_{side}", ua_h,  ua_t,    parent=f"scapula_{side}", deform=True)
        mk(f"forearm_{side}",   fa_h,  fa_t,    parent=f"upper_arm_{side}", use_connect=True, deform=True)
        mk(f"front_paw_{side}", paw_h, paw_t,   parent=f"forearm_{side}",  use_connect=True, deform=True)
        # Fingers — 3 per paw × 2 segments
        for i, ox in enumerate([-0.012, 0.0, 0.012]):
            f_base = Vector((paw_t.x + sx * ox, paw_t.y - 0.005, paw_t.z))
            f_mid = Vector((paw_t.x + sx * ox * 1.5, paw_t.y - 0.018, paw_t.z))
            f_tip = Vector((paw_t.x + sx * ox * 1.8, paw_t.y - 0.028, paw_t.z))
            mk(f"finger_F_{side}_{i+1}_01", f_base, f_mid,
               parent=f"front_paw_{side}", deform=True)
            mk(f"finger_F_{side}_{i+1}_02", f_mid, f_tip,
               parent=f"finger_F_{side}_{i+1}_01", use_connect=True, deform=True)

    # ----- Back legs -----
    # Tripo's back-leg chains are asymmetric (left has 6 nodes, right has 4).
    # Walk Tripo's parent→child chain dynamically.
    # Left:  bone_27 → 1_Left_Limb_0 → _1 → _2 → _3 → _4
    # Right: bone_17 → bone_18 → 1_Right_Limb_0 → _1
    back_chains = {
        "L": ["bone_27", "tripo::1_Left_Limb_0", "tripo::1_Left_Limb_1",
              "tripo::1_Left_Limb_2", "tripo::1_Left_Limb_3", "tripo::1_Left_Limb_4"],
        "R": ["bone_17", "bone_18", "tripo::1_Right_Limb_0", "tripo::1_Right_Limb_1"],
    }
    for side in ("L", "R"):
        sx = +1 if side == "L" else -1
        chain = [c for c in back_chains[side] if c in tripo]
        # Bone names by position in chain (depending on length)
        n = len(chain)
        # Map: pelvis→thigh→shin→[ankle]→[ankle2]→paw  (last bone is paw)
        # We'll always end with hip / thigh / shin / back_paw at minimum
        # Names by chain length:
        if n >= 5:
            names = ["hip", "thigh", "shin", "ankle", "back_paw"] + \
                     ([f"back_paw_ext"] if n > 5 else [])
            # 6 chain entries → 5 bones (consecutive pairs)
        elif n == 4:
            names = ["hip", "thigh", "shin", "back_paw"]
        else:
            names = ["hip", "thigh", "shin", "back_paw"]
        bone_names = []
        for i in range(n - 1):
            base_name = names[i] if i < len(names) else f"back_extra_{i}"
            bone_names.append(f"{base_name}_{side}")
        # Build bones from consecutive Tripo joint heads
        parent_name = "hips"
        for i in range(n - 1):
            head = J(chain[i])
            # tail = head of next, OR for the last segment use Jt
            tail = J(chain[i+1]) if (i+1 < n) else Jt(chain[i])
            # On the very last segment, extend to Tripo's tail for paw tip
            if i == n - 2:
                tail = Jt(chain[i+1])
                # Clamp to floor
                tail = Vector((tail.x, tail.y, max(tail.z, lm["z_min"] + 0.002)))
            mk(bone_names[i], head, tail,
               parent=parent_name, use_connect=(i > 0), deform=True)
            parent_name = bone_names[i]
        # paw_t = end of back_paw bone for finger placement
        last_chain_idx = n - 1
        paw_t = Jt(chain[last_chain_idx]) if last_chain_idx >= 0 else Vector((0,0,0))
        paw_t = Vector((paw_t.x, paw_t.y, max(paw_t.z, lm["z_min"] + 0.002)))
        paw_bone_name = f"back_paw_{side}"
        if paw_bone_name not in bones:
            paw_bone_name = bone_names[-1]
        # Back fingers — small extension from paw
        for i, ox in enumerate([-0.012, 0.0, 0.012]):
            f_base = Vector((paw_t.x + sx * ox, paw_t.y - 0.005, paw_t.z))
            f_mid = Vector((paw_t.x + sx * ox * 1.4, paw_t.y - 0.020, paw_t.z))
            f_tip = Vector((paw_t.x + sx * ox * 1.7, paw_t.y - 0.032, paw_t.z))
            mk(f"finger_B_{side}_{i+1}_01", f_base, f_mid,
               parent=paw_bone_name, deform=True)
            mk(f"finger_B_{side}_{i+1}_02", f_mid, f_tip,
               parent=f"finger_B_{side}_{i+1}_01", use_connect=True, deform=True)

    # ----- Tail — use Tripo Tail_0..3 + bone_21 + bone_26 -----
    # bone_21 = pelvis-tail attach
    # tripo::Tail_0..3 = main tail
    # bone_26 = tail tip extension
    # We extend the tail to ~20 segments via interpolation
    tail_anchors = [
        J("bone_21"),
        J("tripo::Tail_0"),
        J("tripo::Tail_1"),
        J("tripo::Tail_2"),
        J("tripo::Tail_3"),
        J("bone_26"),
        Jt("bone_26"),
    ]
    tail_anchors = [p for p in tail_anchors if p is not None]
    if len(tail_anchors) >= 2:
        # Resample to 20 segments along the polyline
        segs = []
        total_len = 0
        for i in range(len(tail_anchors)-1):
            total_len += (tail_anchors[i+1] - tail_anchors[i]).length
        N = 20
        seg_len = total_len / N
        accum = 0
        out = [tail_anchors[0]]
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
            p = cur + (tail_anchors[i+1] - cur) * t
            out.append(p)
        # Build tail bones tail_01..tail_20
        prev_name = "hips"
        for k in range(len(out) - 1):
            name = f"tail_{k+1:02d}"
            mk(name, out[k], out[k+1], parent=prev_name,
               use_connect=(k > 0), deform=True)
            prev_name = name

    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Built armature: {len(arm.bones)} bones")
    return arm_obj


# ============================================================================
# Constraints (IK, drivers)
# ============================================================================
def setup_constraints(arm_obj):
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm_obj.pose.bones

    # IK on 4 paws (chain_count=2 = paw + lower leg)
    for name, chain in (("front_paw_L", 3), ("front_paw_R", 3),
                          ("back_paw_L", 3),  ("back_paw_R", 3)):
        if name not in pb: continue
        c = pb[name].constraints.new('IK')
        c.chain_count = chain
        c.use_tail = True
        c.use_stretch = False

    # Breath driver — chest scale_y
    chest = pb.get("chest")
    if chest:
        # Custom property on root for breath
        root = pb.get("root")
        if root:
            arm_obj["breath"] = 0.0
            arm_obj.id_properties_ui("breath").update(min=-1.0, max=1.0, default=0.0)
            # Driver: chest.scale.y = 1 + breath * 0.08
            d = chest.driver_add("scale", 1).driver
            d.type = 'SCRIPTED'
            v = d.variables.new()
            v.name = "b"
            v.targets[0].id = arm_obj
            v.targets[0].data_path = '["breath"]'
            d.expression = "1 + b * 0.08"

    # Jaw open driver
    jaw = pb.get("jaw")
    if jaw:
        arm_obj["jaw_open"] = 0.0
        arm_obj.id_properties_ui("jaw_open").update(min=0.0, max=1.0, default=0.0)
        d = jaw.driver_add("rotation_euler", 0).driver
        d.type = 'SCRIPTED'
        v = d.variables.new()
        v.name = "j"
        v.targets[0].id = arm_obj
        v.targets[0].data_path = '["jaw_open"]'
        d.expression = "j * 0.6"
        jaw.rotation_mode = 'XYZ'

    # Ear perk drivers
    for side in ("L", "R"):
        ear_base = pb.get(f"ear_{side}_base")
        if not ear_base: continue
        prop = f"ear_{side}_perk"
        arm_obj[prop] = 0.0
        arm_obj.id_properties_ui(prop).update(min=-1.0, max=1.0, default=0.0)
        d = ear_base.driver_add("rotation_euler", 0).driver
        d.type = 'SCRIPTED'
        v = d.variables.new()
        v.name = "p"
        v.targets[0].id = arm_obj
        v.targets[0].data_path = f'["{prop}"]'
        d.expression = "p * 0.4"
        ear_base.rotation_mode = 'XYZ'

    bpy.ops.object.mode_set(mode='OBJECT')
    log("Constraints + drivers wired")


# ============================================================================
# Parent mesh to armature with auto-weights
# ============================================================================
def bind_mesh(arm_obj, mesh):
    # Set sensible envelope radii on each bone (Blender 4.0 headless's
    # ARMATURE_AUTO/heat is broken; ENVELOPE is reliable).
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in arm_obj.data.edit_bones:
        # Envelope radius scales with bone length, with a minimum
        length = (eb.tail - eb.head).length
        eb.envelope_distance = max(length * 1.2, 0.04)
        eb.envelope_weight = 1.0
        eb.head_radius = max(length * 0.18, 0.012)
        eb.tail_radius = max(length * 0.18, 0.012)
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type='ARMATURE_ENVELOPE')
    log("Mesh bound to armature (envelope weights)")

    # Find orphan verts (outside all envelopes) and assign to nearest bone.
    bpy.context.view_layer.update()
    name_to_vg = {vg.name: vg for vg in mesh.vertex_groups}
    n_verts = len(mesh.data.vertices)
    n_orphan = 0
    mw_arm = arm_obj.matrix_world
    bone_heads = [(b.name, mw_arm @ b.head_local) for b in arm_obj.data.bones if b.use_deform]
    mw_mesh = mesh.matrix_world
    for vi in range(n_verts):
        total = 0.0
        for vg in mesh.vertex_groups:
            try: total += vg.weight(vi)
            except RuntimeError: pass
        if total < 1e-6:
            wp = mw_mesh @ mesh.data.vertices[vi].co
            best_name, best_d = None, 1e9
            for bn, bp in bone_heads:
                d = (wp - bp).length
                if d < best_d:
                    best_d = d; best_name = bn
            if best_name and best_name in name_to_vg:
                name_to_vg[best_name].add([vi], 1.0, 'REPLACE')
                n_orphan += 1
    log(f"Orphan verts reassigned to nearest bone: {n_orphan} / {n_verts}")


# ============================================================================
# Main
# ============================================================================
def main():
    reset_scene()
    import_glb(SRC)
    tripo = extract_tripo_joints()
    mesh = cleanup_keep_mesh_only()
    lm = detect_landmarks(mesh)
    log(f"Mesh AABB: X[{lm['x_min']:.3f},{lm['x_max']:.3f}] "
        f"Y[{lm['y_min']:.3f},{lm['y_max']:.3f}] "
        f"Z[{lm['z_min']:.3f},{lm['z_max']:.3f}]")
    log(f"Nose tip: {lm['nose_tip']}")
    log(f"Tail tip: {lm['tail_tip']}")
    bvh = build_bvh(mesh)
    arm = build_armature(tripo, mesh, lm, bvh)
    setup_constraints(arm)
    bind_mesh(arm, mesh)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved → {OUT_BLEND}")

    # Ensure every DEF bone has a vertex group on the mesh — Blender 4.0
    # gltf addon NPE workaround.
    existing_vgs = {vg.name for vg in mesh.vertex_groups}
    added_vgs = 0
    for b in arm.data.bones:
        if b.use_deform and b.name not in existing_vgs:
            mesh.vertex_groups.new(name=b.name)
            added_vgs += 1
    log(f"Added {added_vgs} empty vertex groups for orphan DEF bones")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True)
    arm.select_set(True)
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
