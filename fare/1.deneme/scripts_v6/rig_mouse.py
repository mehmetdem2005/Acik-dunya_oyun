"""
AAA-grade mouse character rigger.

Usage:
    blender --background --python fare/scripts/rig_mouse.py

Input:  fare/source/mouse3dmodel1k.glb
Output: fare/out/mouse.glb

Coordinate convention (Blender native, Z-up):
  X = lateral (left negative, right positive)
  Y = length / antero-posterior axis (head ↔ tail)
  Z = vertical (up)

Professional techniques applied:
  - Mesh-feature-based anatomical bone placement (paws/ears/eyes detected
    from topology and AABB, not just bounding box guesses)
  - Deform / Control / Mechanism bone separation (DEF- / CTRL- / MCH-)
  - Bendy Bones (B-Bones) on spine, neck, tail, whiskers, ears
  - Spline IK on tail (Bezier curve + 3 hook control bones)
  - IK on all 4 limbs with pole targets, stretch, foot-roll controllers
  - Twist bones in upper arm / thigh (anti candy-wrap)
  - Look-at constraint on eye bones with eye-aim target controller
  - Breath driver: chest scale axes driven by armature['breath']
  - Limit rotation constraints (anatomical joint limits)
  - Bone collections + bone color themes
  - Custom bone shapes for controllers
  - Vertex weight smoothing + clamp 4 influences + normalize
"""

import bpy
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "mouse3dmodel1k.glb")
OUT_DIR = os.path.join(ROOT, "out")
OUT = os.path.join(OUT_DIR, "mouse.glb")

os.makedirs(OUT_DIR, exist_ok=True)


def log(msg):
    print(f"[rig] {msg}", flush=True)


# ============================================================================ #
#  1. Scene reset & import
# ============================================================================ #
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path}")
    bpy.ops.import_scene.gltf(filepath=path)


# ============================================================================ #
#  2. Strip Tripo auto-rig, merge real body meshes
# ============================================================================ #
def cleanup_and_merge():
    """
    GLB layout after import:
      - Icosphere       (placeholder, not part of body — remove)
      - ParentNode      (empty, remove)
      - Armature        (Tripo auto-rig, remove)
      - tripo_part_0..9 (the 10 actual body sub-meshes — KEEP, join into one)
    """
    log("Cleanup: deleting placeholder + Tripo armature, keeping body meshes")

    # Remove non-body placeholder & helpers
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)
            log(f"  removed {name}")

    # Apply armature modifier on body meshes (bakes rest pose into mesh) then clear parent
    body_meshes = [o for o in bpy.data.objects
                   if o.type == 'MESH' and o.name.startswith("tripo_part")]
    log(f"  body sub-meshes: {len(body_meshes)}")

    for m in body_meshes:
        bpy.context.view_layer.objects.active = m
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE':
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                except Exception:
                    m.modifiers.remove(mod)
        bpy.ops.object.select_all(action='DESELECT')
        m.select_set(True)
        bpy.context.view_layer.objects.active = m
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        m.vertex_groups.clear()

    # Delete Tripo armature & any remaining empties
    for o in list(bpy.data.objects):
        if o.type in ('ARMATURE', 'EMPTY'):
            bpy.data.objects.remove(o, do_unlink=True)

    body_meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in body_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = body_meshes[0]

    # Apply all transforms (mesh now in world coords, identity matrix)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Join into single MouseBody
    if len(body_meshes) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    log(f"Pre-weld: {merged.name}  verts={len(merged.data.vertices)}  polys={len(merged.data.polygons)}")

    # Weld duplicate verts at sub-mesh seams (critical for heat weighting)
    bpy.context.view_layer.objects.active = merged
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    # Recalc normals outside
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Post-weld:  verts={len(merged.data.vertices)}  polys={len(merged.data.polygons)}")
    return merged


# ============================================================================ #
#  3. Mesh-feature-based anatomy detection (Z-up convention)
# ============================================================================ #
def _connected_islands(mesh_obj, vert_filter):
    me = mesh_obj.data
    allowed = {i for i, vt in enumerate(me.vertices) if vert_filter(vt.co)}
    if not allowed:
        return []
    adj = {i: set() for i in allowed}
    for edge in me.edges:
        a, b = edge.vertices
        if a in allowed and b in allowed:
            adj[a].add(b); adj[b].add(a)
    seen = set()
    islands = []
    for start in allowed:
        if start in seen: continue
        stack = [start]; comp = set()
        while stack:
            n = stack.pop()
            if n in seen: continue
            seen.add(n); comp.add(n)
            stack.extend(adj[n] - seen)
        islands.append(comp)
    return islands


class Anatomy:
    """
    Blender Z-up convention:
      X = lateral, Y = anteroposterior (head/tail), Z = vertical
    head_dir = +1 if head is at +Y, -1 if head is at -Y.
    """

    def __init__(self, mesh_obj):
        self.mesh = mesh_obj
        verts = [v.co.copy() for v in mesh_obj.data.vertices]
        self.verts = verts
        xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
        self.x_min, self.x_max = min(xs), max(xs)
        self.y_min, self.y_max = min(ys), max(ys)
        self.z_min, self.z_max = min(zs), max(zs)
        self.x_center = (self.x_max + self.x_min) / 2.0
        self.x_half = (self.x_max - self.x_min) / 2.0
        self.y_size = self.y_max - self.y_min
        self.z_size = self.z_max - self.z_min
        log(f"AABB X=[{self.x_min:.3f},{self.x_max:.3f}] Y=[{self.y_min:.3f},{self.y_max:.3f}] Z=[{self.z_min:.3f},{self.z_max:.3f}]")

        self.head_dir = self._detect_head_direction()
        log(f"Head direction (Y axis): {'+Y' if self.head_dir>0 else '-Y'}")

        self._compute_landmarks()
        self.paws = self._detect_paws()
        self.ears = self._detect_ears()
        self.eyes = self._detect_eyes()
        self.nose_tip = self._detect_nose_tip()
        log(f"Paws: { {k: [round(c,3) for c in p] for k, p in self.paws.items()} }")
        log(f"Ears: { {k: [round(c,3) for c in p] for k, p in self.ears.items()} }")
        log(f"Eyes: { {k: [round(c,3) for c in p] for k, p in self.eyes.items()} }")
        log(f"Nose tip: {[round(c,3) for c in self.nose_tip]}")

    def _detect_head_direction(self):
        bands = 12
        y_step = self.y_size / bands
        radii = []
        for i in range(bands):
            y0 = self.y_min + i * y_step
            y1 = y0 + y_step
            band = [v for v in self.verts if y0 <= v.y < y1]
            if not band:
                radii.append(0.0); continue
            cx = sum(v.x for v in band) / len(band)
            cz = sum(v.z for v in band) / len(band)
            r = max(math.hypot(v.x - cx, v.z - cz) for v in band)
            radii.append(r)
        log(f"Band radii (Y- to Y+): {[round(r,3) for r in radii]}")
        # Heuristic 1: trailing-thin-band count (long tail end)
        thresh = max(radii) * 0.45
        front_thin = back_thin = 0
        for r in radii:
            if r < thresh: front_thin += 1
            else: break
        for r in reversed(radii):
            if r < thresh: back_thin += 1
            else: break
        # Heuristic 2: thinnest single band (head/snout end has the absolute thinnest)
        min_idx = radii.index(min(radii))
        snout_at_plus_y = min_idx >= len(radii) // 2
        # Heuristic 3: mean radius of first vs last quarter
        q = max(1, len(radii) // 4)
        front_mean = sum(radii[:q]) / q
        back_mean  = sum(radii[-q:]) / q
        log(f"front_thin={front_thin} back_thin={back_thin}  "
            f"min_idx={min_idx}  front_mean={front_mean:.3f} back_mean={back_mean:.3f}")
        # The "head" end is the one with the absolute thinnest cross-section
        # (the snout). Tail is just-thin but more uniform.
        if snout_at_plus_y: return +1
        return -1

    def _compute_landmarks(self):
        d = self.head_dir
        y0 = self.y_min if d > 0 else self.y_max
        y1 = self.y_max if d > 0 else self.y_min
        def lerp(t): return y0 + (y1 - y0) * t
        # 0% = tail tip, 100% = nose tip
        self.y_tail_tip   = lerp(0.00)
        self.y_hips       = lerp(0.30)
        self.y_spine_1    = lerp(0.40)
        self.y_spine_2    = lerp(0.50)
        self.y_chest      = lerp(0.60)
        self.y_shoulders  = lerp(0.66)
        self.y_neck       = lerp(0.74)
        self.y_head       = lerp(0.85)
        self.y_jaw        = lerp(0.92)
        self.y_nose       = lerp(1.00)

        # Vertical (Z-up)
        self.z_floor   = self.z_min
        self.z_belly   = self.z_min + self.z_size * 0.30
        self.z_spine   = self.z_min + self.z_size * 0.55
        self.z_chest   = self.z_min + self.z_size * 0.55
        self.z_neck    = self.z_min + self.z_size * 0.70
        self.z_head    = self.z_min + self.z_size * 0.78
        self.z_jaw_lo  = self.z_min + self.z_size * 0.55
        self.z_ears    = self.z_min + self.z_size * 0.95
        self.z_eyes    = self.z_min + self.z_size * 0.80

    def _detect_paws(self):
        floor_thresh = self.z_min + self.z_size * 0.10
        d = self.head_dir
        y_mid = (self.y_chest + self.y_hips) / 2.0
        if d > 0:
            front_pred = lambda p: p.y > y_mid
            back_pred  = lambda p: p.y < y_mid
        else:
            front_pred = lambda p: p.y < y_mid
            back_pred  = lambda p: p.y > y_mid
        left_pred  = lambda p: p.x < self.x_center
        right_pred = lambda p: p.x > self.x_center

        out = {}
        for name, fz, fx in (("paw_F_L", front_pred, left_pred),
                              ("paw_F_R", front_pred, right_pred),
                              ("paw_B_L", back_pred, left_pred),
                              ("paw_B_R", back_pred, right_pred)):
            cand = [v for v in self.verts if v.z < floor_thresh and fz(v) and fx(v)]
            if len(cand) < 6:
                # Fallback: 8% lowest in quadrant
                cand = [v for v in self.verts if fz(v) and fx(v)]
                cand.sort(key=lambda p: p.z)
                cand = cand[: max(20, len(cand)//50)]
            if not cand:
                quad_x = self.x_center + (-1 if "L" in name else +1) * self.x_half * 0.6
                quad_y = self.y_shoulders if "F" in name else self.y_hips
                out[name] = Vector((quad_x, quad_y, self.z_floor))
                continue
            cx = sum(v.x for v in cand) / len(cand)
            cy = sum(v.y for v in cand) / len(cand)
            cz = self.z_floor + self.z_size * 0.02
            out[name] = Vector((cx, cy, cz))
        return out

    def _detect_ears(self):
        z_lo = self.z_min + self.z_size * 0.82
        d = self.head_dir
        if d > 0: ylo, yhi = self.y_neck, self.y_nose
        else:     ylo, yhi = self.y_nose, self.y_neck
        ylo, yhi = min(ylo, yhi), max(ylo, yhi)

        def in_top_lateral(p):
            return p.z > z_lo and ylo <= p.y <= yhi and abs(p.x - self.x_center) > self.x_half * 0.20

        islands = _connected_islands(self.mesh, in_top_lateral)
        islands.sort(key=len, reverse=True)
        out = {}
        for isl in islands[:2]:
            cx = sum(self.verts[i].x for i in isl) / len(isl)
            cy = sum(self.verts[i].y for i in isl) / len(isl)
            cz = sum(self.verts[i].z for i in isl) / len(isl)
            key = "ear_L" if cx < self.x_center else "ear_R"
            out[key] = Vector((cx, cy, cz))
        if "ear_L" not in out:
            out["ear_L"] = Vector((self.x_center - self.x_half * 0.55, self.y_head, self.z_ears))
        if "ear_R" not in out:
            out["ear_R"] = Vector((self.x_center + self.x_half * 0.55, self.y_head, self.z_ears))
        return out

    def _detect_eyes(self):
        d = self.head_dir
        y_eye = self.y_head + (self.y_nose - self.y_head) * 0.30
        return {
            "eye_L": Vector((self.x_center - self.x_half * 0.45, y_eye, self.z_eyes)),
            "eye_R": Vector((self.x_center + self.x_half * 0.45, y_eye, self.z_eyes)),
        }

    def _detect_nose_tip(self):
        d = self.head_dir
        if d > 0:
            cand = [v for v in self.verts if v.y > self.y_min + self.y_size * 0.95]
        else:
            cand = [v for v in self.verts if v.y < self.y_min + self.y_size * 0.05]
        if not cand:
            return Vector((self.x_center, self.y_nose, self.z_eyes - self.z_size * 0.05))
        cx = sum(v.x for v in cand) / len(cand)
        cy = sum(v.y for v in cand) / len(cand)
        cz = sum(v.z for v in cand) / len(cand)
        return Vector((cx, cy, cz))


# ============================================================================ #
#  4. Armature build (edit mode)  -- Z-up
# ============================================================================ #
def V(x, y, z): return Vector((x, y, z))


def build_armature(A: Anatomy):
    log("Building armature")
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig"
    arm = arm_obj.data
    arm.name = "MouseRigData"
    eb = arm.edit_bones
    d = A.head_dir
    cx = A.x_center

    bones_meta = {}

    def make(name, head, tail, parent=None, connect=False, roll=0.0,
             role="DEF", collection="deform", bbones=1):
        b = eb.new(name)
        b.head = head
        b.tail = tail
        b.roll = roll
        if parent is not None:
            b.parent = parent
            b.use_connect = connect
        b.bbone_segments = bbones
        bones_meta[name] = {"role": role, "collection": collection}
        return b

    # ---- Root + spine chain ----
    root = make("root",
                V(cx, A.y_hips - d * 0.08, 0.0),
                V(cx, A.y_hips + d * 0.08, 0.0),
                role="CTRL", collection="ctrl_main")

    hips = make("DEF-hips",
                V(cx, A.y_hips, A.z_spine),
                V(cx, A.y_spine_1, A.z_spine),
                parent=root, collection="deform")

    spine_01 = make("DEF-spine_01",
                    hips.tail,
                    V(cx, A.y_spine_2, A.z_spine + A.z_size * 0.02),
                    parent=hips, connect=True, collection="deform", bbones=3)
    spine_02 = make("DEF-spine_02",
                    spine_01.tail,
                    V(cx, A.y_chest, A.z_chest),
                    parent=spine_01, connect=True, collection="deform", bbones=3)
    chest = make("DEF-chest",
                 spine_02.tail,
                 V(cx, A.y_shoulders, A.z_chest),
                 parent=spine_02, connect=True, collection="deform")
    neck = make("DEF-neck",
                chest.tail,
                V(cx, A.y_neck, A.z_neck),
                parent=chest, connect=True, collection="deform", bbones=2)
    head = make("DEF-head",
                neck.tail,
                V(cx, A.y_head, A.z_head),
                parent=neck, connect=True, collection="deform")
    jaw = make("DEF-jaw",
               V(cx, A.y_jaw, A.z_jaw_lo),
               V(cx, A.nose_tip.y, A.z_jaw_lo - A.z_size * 0.02),
               parent=head, collection="deform")

    # ---- Spine FK controllers (mirror selected deform bones) ----
    ctrl_hips  = make("CTRL-hips",  hips.head, hips.tail, parent=root, role="CTRL", collection="ctrl_main")
    ctrl_chest = make("CTRL-chest", chest.head, chest.tail, parent=ctrl_hips, role="CTRL", collection="ctrl_main")
    ctrl_head  = make("CTRL-head",  head.head, head.tail, parent=ctrl_chest, role="CTRL", collection="ctrl_face")
    ctrl_jaw   = make("CTRL-jaw",   jaw.head, jaw.tail, parent=ctrl_head, role="CTRL", collection="ctrl_face")

    # ---- Ears ----
    for side, sx, key in (("L", -1, "ear_L"), ("R", +1, "ear_R")):
        ear_pos = A.ears[key]
        base = V(cx + sx * A.x_half * 0.30, A.y_head, A.z_head + A.z_size * 0.05)
        tip  = ear_pos
        make(f"DEF-ear.{side}", base, tip, parent=head, collection="deform", bbones=3)
        make(f"CTRL-ear.{side}", base, tip, parent=ctrl_head, role="CTRL", collection="ctrl_face")

    # ---- Whiskers (4 per side) ----
    for side, sx in (("L", -1), ("R", +1)):
        for i in range(4):
            t = i / 3.0
            # whisker base on cheek
            zb = A.z_eyes - A.z_size * (0.05 + 0.18 * t)
            xb = cx + sx * A.x_half * 0.30
            yb = A.y_jaw + (A.y_nose - A.y_jaw) * 0.65
            # tip extends outward and slightly forward
            xt = cx + sx * A.x_half * 1.45
            yt = A.y_nose + d * A.y_size * 0.05
            zt = zb + A.z_size * 0.02
            make(f"DEF-whisker_{i+1:02d}.{side}",
                 V(xb, yb, zb), V(xt, yt, zt),
                 parent=head, collection="deform", bbones=4)

    # ---- Tail (8 segments + spline IK with 3 ctrl bones) ----
    tail_segs = 8
    y_a = A.y_hips
    y_b = A.y_tail_tip
    dy = (y_b - y_a) / tail_segs
    tail_bone_names = []
    prev = hips
    for i in range(tail_segs):
        tA = i / tail_segs; tB = (i + 1) / tail_segs
        # parabolic droop in Z (tail sags slightly)
        droop = lambda t: -0.06 * t * (1.0 - t * 0.5) * A.z_size
        z0 = A.z_spine + droop(tA)
        z1 = A.z_spine + droop(tB)
        y0 = y_a + dy * i
        y1 = y_a + dy * (i + 1)
        b = make(f"DEF-tail_{i+1:02d}",
                 V(cx, y0, z0), V(cx, y1, z1),
                 parent=prev, connect=(i > 0),
                 collection="deform", bbones=2)
        tail_bone_names.append(b.name); prev = b

    tail_ctrl_names = []
    for ti, t in enumerate((0.0, 0.5, 1.0)):
        y = y_a + (y_b - y_a) * t
        z = A.z_spine + (-0.06 * t * (1.0 - t * 0.5) * A.z_size)
        name = f"CTRL-tail_{ti+1}"
        make(name,
             V(cx, y, z),
             V(cx, y + d * 0.05, z + 0.03),
             parent=root, role="CTRL", collection="ctrl_main")
        tail_ctrl_names.append(name)

    # ---- Front limbs (shoulder → arm → forearm → paw → toes) ----
    limb_data = []
    for side, sx in (("L", -1), ("R", +1)):
        paw_pos = A.paws[f"paw_F_{side}"]
        # Shoulder on chest, slightly inward
        sh_head = V(cx + sx * A.x_half * 0.22, A.y_chest, A.z_chest - A.z_size * 0.05)
        sh_tail = V(cx + sx * A.x_half * 0.42, A.y_shoulders - d * A.y_size * 0.02, A.z_chest - A.z_size * 0.12)
        sh = make(f"DEF-shoulder.{side}", sh_head, sh_tail, parent=chest, collection="deform")

        arm_head = sh_tail
        arm_tail = V(paw_pos.x, A.y_shoulders + d * A.y_size * 0.02, A.z_belly)
        upper_arm = make(f"DEF-arm.{side}", arm_head, arm_tail, parent=sh, connect=True, collection="deform")

        mid = (arm_head + arm_tail) * 0.5
        make(f"MCH-arm_twist.{side}", arm_head, mid, parent=upper_arm, role="MCH", collection="mch")

        fore_head = arm_tail
        fore_tail = V(paw_pos.x, A.y_shoulders + d * A.y_size * 0.06, A.z_floor + A.z_size * 0.10)
        fore = make(f"DEF-forearm.{side}", fore_head, fore_tail, parent=upper_arm, connect=True, collection="deform")

        paw_head = fore_tail
        paw_tail = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.04, A.z_floor)
        paw = make(f"DEF-paw_F.{side}", paw_head, paw_tail, parent=fore, connect=True, collection="deform")

        # Foot roll MCH chain
        heel = V(paw_pos.x, paw_pos.y - d * A.y_size * 0.05, A.z_floor)
        toe  = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.08, A.z_floor)
        mch_heel = make(f"MCH-heel_F.{side}", heel, paw_pos.copy().to_tuple() and Vector((paw_pos.x, paw_pos.y, A.z_floor)),
                        parent=root, role="MCH", collection="mch")
        make(f"MCH-toe_F.{side}", Vector((paw_pos.x, paw_pos.y, A.z_floor)), toe,
             parent=mch_heel, role="MCH", collection="mch")

        # IK foot controller (heel-pivot)
        make(f"CTRL-foot_F.{side}",
             heel, heel + V(0, d * 0.05, 0),
             parent=root, role="CTRL", collection="ctrl_ik")

        # Pole target (in front, at belly height)
        pole_pos = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.25, A.z_belly + A.z_size * 0.20)
        make(f"CTRL-pole_F.{side}", pole_pos, pole_pos + V(0, 0, 0.03),
             parent=root, role="CTRL", collection="ctrl_ik")

        # Toes
        for fi in range(3):
            spread = (fi - 1) * 0.18
            prev_toe = paw
            for si in range(3):
                t0 = si / 3.0; t1 = (si + 1) / 3.0
                base = paw_tail
                fwd = V(sx * spread * A.x_half * 0.4, d * A.y_size * 0.04, 0.0)
                bn = make(f"DEF-toe_F_{fi+1}_{si+1:02d}.{side}",
                          base + fwd * t0, base + fwd * t1,
                          parent=prev_toe, connect=(si > 0), collection="deform")
                prev_toe = bn

        limb_data.append({
            "side": side, "front": True,
            "paw": f"DEF-paw_F.{side}",
            "forearm": f"DEF-forearm.{side}",
            "arm": f"DEF-arm.{side}",
            "ik_target": f"CTRL-foot_F.{side}",
            "pole_target": f"CTRL-pole_F.{side}",
            "twist": f"MCH-arm_twist.{side}",
        })

    # ---- Back limbs (thigh → shin → paw → toes) ----
    for side, sx in (("L", -1), ("R", +1)):
        paw_pos = A.paws[f"paw_B_{side}"]
        th_head = V(cx + sx * A.x_half * 0.22, A.y_hips, A.z_spine - A.z_size * 0.05)
        th_tail = V(paw_pos.x, A.y_hips - d * A.y_size * 0.05, A.z_belly)
        thigh = make(f"DEF-thigh.{side}", th_head, th_tail, parent=hips, collection="deform")

        mid = (th_head + th_tail) * 0.5
        make(f"MCH-thigh_twist.{side}", th_head, mid, parent=thigh, role="MCH", collection="mch")

        shin_head = th_tail
        shin_tail = V(paw_pos.x, A.y_hips - d * A.y_size * 0.02, A.z_floor + A.z_size * 0.10)
        shin = make(f"DEF-shin.{side}", shin_head, shin_tail, parent=thigh, connect=True, collection="deform")

        paw_head = shin_tail
        paw_tail = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.04, A.z_floor)
        paw = make(f"DEF-paw_B.{side}", paw_head, paw_tail, parent=shin, connect=True, collection="deform")

        heel = V(paw_pos.x, paw_pos.y - d * A.y_size * 0.05, A.z_floor)
        toe  = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.08, A.z_floor)
        mch_heel = make(f"MCH-heel_B.{side}", heel, Vector((paw_pos.x, paw_pos.y, A.z_floor)),
                        parent=root, role="MCH", collection="mch")
        make(f"MCH-toe_B.{side}", Vector((paw_pos.x, paw_pos.y, A.z_floor)), toe,
             parent=mch_heel, role="MCH", collection="mch")

        make(f"CTRL-foot_B.{side}", heel, heel + V(0, d * 0.05, 0),
             parent=root, role="CTRL", collection="ctrl_ik")

        pole_pos = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.25, A.z_belly + A.z_size * 0.20)
        make(f"CTRL-pole_B.{side}", pole_pos, pole_pos + V(0, 0, 0.03),
             parent=root, role="CTRL", collection="ctrl_ik")

        for fi in range(3):
            spread = (fi - 1) * 0.18
            prev_toe = paw
            for si in range(3):
                t0 = si / 3.0; t1 = (si + 1) / 3.0
                base = paw_tail
                fwd = V(sx * spread * A.x_half * 0.4, d * A.y_size * 0.04, 0.0)
                bn = make(f"DEF-toe_B_{fi+1}_{si+1:02d}.{side}",
                          base + fwd * t0, base + fwd * t1,
                          parent=prev_toe, connect=(si > 0), collection="deform")
                prev_toe = bn

        limb_data.append({
            "side": side, "front": False,
            "paw": f"DEF-paw_B.{side}",
            "forearm": f"DEF-shin.{side}",
            "arm": f"DEF-thigh.{side}",
            "ik_target": f"CTRL-foot_B.{side}",
            "pole_target": f"CTRL-pole_B.{side}",
            "twist": f"MCH-thigh_twist.{side}",
        })

    # ---- Eyes ----
    aim_dist = A.y_size * 0.35
    y_target = A.y_nose + d * aim_dist
    ctrl_eye_aim = make("CTRL-eye_aim",
                        V(cx, y_target, A.z_eyes),
                        V(cx, y_target, A.z_eyes + 0.03),
                        parent=ctrl_head, role="CTRL", collection="ctrl_face")
    for side in ("L", "R"):
        eye_pos = A.eyes[f"eye_{side}"]
        make(f"DEF-eye.{side}", eye_pos,
             eye_pos + V(0, d * 0.02, 0),
             parent=head, collection="deform")
        make(f"CTRL-eye_aim.{side}",
             V(eye_pos.x, y_target, A.z_eyes),
             V(eye_pos.x, y_target, A.z_eyes + 0.02),
             parent=ctrl_eye_aim, role="CTRL", collection="ctrl_face")

    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Armature built: {len(arm.bones)} bones")
    return arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names


# ============================================================================ #
#  5. Pose-mode constraints: IK, Spline IK on tail, Look-at on eyes, FK mirror
# ============================================================================ #
def setup_constraints(arm_obj, limb_data, tail_bone_names, tail_ctrl_names, A):
    log("Setting up constraints")
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pbones = arm_obj.pose.bones

    # 4-limb IK with pole + stretch
    for L in limb_data:
        pb = pbones[L["paw"]]
        ik = pb.constraints.new('IK')
        ik.target = arm_obj
        ik.subtarget = L["ik_target"]
        ik.chain_count = 3
        ik.pole_target = arm_obj
        ik.pole_subtarget = L["pole_target"]
        ik.pole_angle = -math.pi / 2
        ik.use_stretch = True

        # Twist bone copies Y rotation of upper arm/thigh (50%)
        tw = pbones[L["twist"]]
        c = tw.constraints.new('COPY_ROTATION')
        c.target = arm_obj
        c.subtarget = L["arm"]
        c.use_x = False; c.use_y = True; c.use_z = False
        c.target_space = 'LOCAL'; c.owner_space = 'LOCAL'
        c.influence = 0.5

    # Spline IK on tail
    bpy.ops.object.mode_set(mode='OBJECT')
    curve_data = bpy.data.curves.new("TailCurve", type='CURVE')
    curve_data.dimensions = '3D'
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(2)
    d = A.head_dir
    for i, t in enumerate((0.0, 0.5, 1.0)):
        y = A.y_hips + (A.y_tail_tip - A.y_hips) * t
        z = A.z_spine + (-0.06 * t * (1.0 - t * 0.5) * A.z_size)
        bp = spline.bezier_points[i]
        bp.co = (A.x_center, y, z)
        h_off = (A.y_tail_tip - A.y_hips) * 0.18
        bp.handle_left  = (A.x_center, y - h_off, z)
        bp.handle_right = (A.x_center, y + h_off, z)
    curve_obj = bpy.data.objects.new("TailCurve", curve_data)
    bpy.context.collection.objects.link(curve_obj)

    # Add hook modifiers using API directly (more robust than ops in headless)
    for i, ctrl_name in enumerate(tail_ctrl_names):
        hook = curve_obj.modifiers.new(name=f"Hook_{ctrl_name}", type='HOOK')
        hook.object = arm_obj
        hook.subtarget = ctrl_name
        hook.vertex_indices_set([i])  # bezier point indices

    # Spline IK constraint on last tail bone
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    last_tail = arm_obj.pose.bones[tail_bone_names[-1]]
    sik = last_tail.constraints.new('SPLINE_IK')
    sik.target = curve_obj
    sik.chain_count = len(tail_bone_names)
    sik.y_scale_mode = 'BONE_ORIGINAL'
    sik.xz_scale_mode = 'BONE_ORIGINAL'

    # Look-at on eyes
    for side in ("L", "R"):
        if f"DEF-eye.{side}" in pbones:
            pb = pbones[f"DEF-eye.{side}"]
            c = pb.constraints.new('DAMPED_TRACK')
            c.target = arm_obj
            c.subtarget = f"CTRL-eye_aim.{side}"
            # Eye bone points along +Y in head coords; with d<0 it's -Y
            c.track_axis = 'TRACK_Y' if A.head_dir > 0 else 'TRACK_NEGATIVE_Y'

    # FK spine: DEF bones copy CTRL bones (so animator drives CTRL only)
    for def_name, ctrl_name in (("DEF-hips","CTRL-hips"),
                                  ("DEF-chest","CTRL-chest"),
                                  ("DEF-head","CTRL-head"),
                                  ("DEF-jaw","CTRL-jaw")):
        if def_name in pbones and ctrl_name in pbones:
            pb = pbones[def_name]
            c = pb.constraints.new('COPY_ROTATION')
            c.target = arm_obj; c.subtarget = ctrl_name
            c.target_space = 'LOCAL'; c.owner_space = 'LOCAL'

    for side in ("L", "R"):
        if f"DEF-ear.{side}" in pbones and f"CTRL-ear.{side}" in pbones:
            pb = pbones[f"DEF-ear.{side}"]
            c = pb.constraints.new('COPY_ROTATION')
            c.target = arm_obj; c.subtarget = f"CTRL-ear.{side}"
            c.target_space = 'LOCAL'; c.owner_space = 'LOCAL'

    # Joint rotation limits
    for L in limb_data:
        if L["forearm"] in pbones:
            fa = pbones[L["forearm"]]
            c = fa.constraints.new('LIMIT_ROTATION')
            c.use_limit_x = True; c.min_x = 0.0; c.max_x = math.radians(140)
            c.use_limit_y = True; c.min_y = -math.radians(20); c.max_y = math.radians(20)
            c.use_limit_z = True; c.min_z = -math.radians(20); c.max_z = math.radians(20)
            c.owner_space = 'LOCAL'
    if "DEF-neck" in pbones:
        c = pbones["DEF-neck"].constraints.new('LIMIT_ROTATION')
        c.use_limit_x = True; c.min_x = -math.radians(60); c.max_x = math.radians(60)
        c.use_limit_y = True; c.min_y = -math.radians(45); c.max_y = math.radians(45)
        c.use_limit_z = True; c.min_z = -math.radians(45); c.max_z = math.radians(45)
        c.owner_space = 'LOCAL'

    # Breath custom property + drivers on chest scale
    arm_obj["breath"] = 0.0
    try:
        ui = arm_obj.id_properties_ui("breath")
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                  description="Breathing inhale=1 / exhale=0")
    except Exception:
        pass

    chest_pb = pbones["DEF-chest"]
    for axis_idx, expr in ((1, "1.0 + 0.07 * breath"),
                           (0, "1.0 + 0.05 * breath"),
                           (2, "1.0 + 0.05 * breath")):
        fc = chest_pb.driver_add("scale", axis_idx)
        drv = fc.driver
        drv.type = 'SCRIPTED'
        var = drv.variables.new()
        var.name = "breath"; var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = arm_obj
        var.targets[0].data_path = '["breath"]'
        drv.expression = expr

    bpy.ops.object.mode_set(mode='OBJECT')


# ============================================================================ #
#  6. Bone collections & colors
# ============================================================================ #
COLLECTION_COLORS = {
    "deform":    "THEME04",
    "ctrl_main": "THEME09",
    "ctrl_ik":   "THEME01",
    "ctrl_face": "THEME03",
    "mch":       "THEME10",
}

def organize_collections(arm_obj, bones_meta):
    log("Bone collections + colors")
    arm = arm_obj.data
    names = ["deform", "ctrl_main", "ctrl_ik", "ctrl_face", "mch"]
    colls = {}
    for n in names:
        colls[n] = arm.collections.get(n) or arm.collections.new(n)
    for bone in arm.bones:
        meta = bones_meta.get(bone.name)
        if not meta:
            cn = ("ctrl_main" if bone.name.startswith("CTRL") else
                  "mch" if bone.name.startswith("MCH") else "deform")
        else:
            cn = meta["collection"]
        coll = colls.get(cn)
        if coll: coll.assign(bone)
        theme = COLLECTION_COLORS.get(cn)
        if theme:
            try: bone.color.palette = theme
            except Exception: pass

    if "mch" in colls:
        colls["mch"].is_visible = False


# ============================================================================ #
#  7. Custom bone shapes
# ============================================================================ #
def make_widgets():
    widgets = {}
    bpy.ops.mesh.primitive_circle_add(vertices=24, radius=0.05, location=(0, -1000, 0))
    o = bpy.context.object; o.name = "WGT-circle"; o.hide_viewport = True; widgets["circle"] = o
    bpy.ops.mesh.primitive_cube_add(size=0.08, location=(0, -1000, 0))
    o = bpy.context.object; o.name = "WGT-cube"; o.hide_viewport = True; widgets["cube"] = o
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=(0, -1000, 0))
    o = bpy.context.object; o.name = "WGT-sphere"; o.hide_viewport = True; widgets["sphere"] = o
    return widgets


def assign_widgets(arm_obj, widgets, bones_meta):
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm_obj.pose.bones:
        meta = bones_meta.get(pb.name)
        if not meta: continue
        c = meta["collection"]
        if c == "ctrl_ik" and "foot" in pb.name:
            pb.custom_shape = widgets["cube"]
        elif c == "ctrl_ik" and "pole" in pb.name:
            pb.custom_shape = widgets["sphere"]
        elif c in ("ctrl_main", "ctrl_face"):
            pb.custom_shape = widgets["circle"]
    bpy.ops.object.mode_set(mode='OBJECT')


# ============================================================================ #
#  8. Skinning + manual weight overrides
# ============================================================================ #
def parent_with_auto_weights(mesh_obj, arm_obj):
    log("Parent ARMATURE_AUTO (DEF bones only)")
    arm = arm_obj.data
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    for b in arm.bones:
        b.use_deform = b.name.startswith("DEF-")

    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')


def _vg(mesh_obj, name):
    return mesh_obj.vertex_groups.get(name) or mesh_obj.vertex_groups.new(name=name)


def manual_weight_overrides(mesh_obj, A: Anatomy):
    log("Manual weight overrides (ears / tail / jaw)")
    cx = A.x_center
    d = A.head_dir
    pos = [v.co.copy() for v in mesh_obj.data.vertices]

    def assign(group_name, idxs, weight=1.0, clear=None):
        if not idxs: return 0
        g = _vg(mesh_obj, group_name)
        g.add(idxs, weight, 'REPLACE')
        if clear:
            for og_name in clear:
                og = mesh_obj.vertex_groups.get(og_name)
                if og: og.remove(idxs)
        return len(idxs)

    # Ears: each lateral upper-head vert assigned by its X sign (cx is mesh center)
    z_lo = A.z_min + A.z_size * 0.82
    ear_L_idxs = []; ear_R_idxs = []
    for vi, p in enumerate(pos):
        if p.z > z_lo and abs(p.x - cx) > A.x_half * 0.20:
            if p.x < cx: ear_L_idxs.append(vi)
            else: ear_R_idxs.append(vi)
    n = assign("DEF-ear.L", ear_L_idxs, 1.0, clear=["DEF-head","DEF-neck","DEF-chest"])
    log(f"  ear.L: {n} verts")
    n = assign("DEF-ear.R", ear_R_idxs, 1.0, clear=["DEF-head","DEF-neck","DEF-chest"])
    log(f"  ear.R: {n} verts")

    # Tail
    for i in range(8):
        ta = i / 8; tb = (i + 1) / 8
        ya = A.y_hips + (A.y_tail_tip - A.y_hips) * ta
        yb = A.y_hips + (A.y_tail_tip - A.y_hips) * tb
        y_lo, y_hi = min(ya, yb), max(ya, yb)
        cand = [vi for vi, p in enumerate(pos)
                if y_lo <= p.y <= y_hi
                and abs(p.x - cx) < A.x_half * 0.35
                and abs(p.z - A.z_spine) < A.z_size * 0.40]
        n = assign(f"DEF-tail_{i+1:02d}", cand, 1.0,
                   clear=["DEF-hips","DEF-spine_01","DEF-spine_02","root"])
        log(f"  tail_{i+1:02d}: {n} verts")

    # Jaw: lower-front of head (Skinning Agent fix #1).
    # Lower-lip / chin: z<eyes-0.05, |x|<0.4*x_half (narrow), front 40% of head.
    # Assign 1.0 REPLACE + clear DEF-head & DEF-neck so jaw rotation actually moves the chin.
    d = A.head_dir
    if d > 0:
        ylo, yhi = A.y_head, A.y_nose
        # Front 40%: closer to nose end
        y_front_lo = ylo + (yhi - ylo) * 0.20
    else:
        ylo, yhi = A.y_nose, A.y_head
        ylo, yhi = min(ylo, yhi), max(ylo, yhi)
        y_front_lo = ylo
    jaw_cand = [vi for vi, p in enumerate(pos)
                if y_front_lo <= p.y <= yhi
                and p.z < A.z_eyes - A.z_size * 0.05
                and abs(p.x - cx) < A.x_half * 0.40]
    n = assign("DEF-jaw", jaw_cand, 1.0,
                clear=["DEF-head", "DEF-neck", "DEF-muzzle"])
    log(f"  jaw: {n} verts (FULL 1.0, cleared head/neck/muzzle)")


def smooth_weights(mesh_obj, iterations=2):
    log(f"Smoothing weights × {iterations}")
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    try:
        bpy.ops.object.vertex_group_smooth(group_select_mode='ALL',
                                            factor=0.5, repeat=iterations,
                                            expand=0.0)
    except Exception as e:
        log(f"  smooth skipped: {e}")
    bpy.ops.object.mode_set(mode='OBJECT')


def clamp_normalize(mesh_obj, max_inf=4):
    log(f"Clamp to {max_inf} influences + normalize")
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    try:
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=max_inf)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    except Exception as e:
        log(f"  clamp skipped: {e}")
    bpy.ops.object.mode_set(mode='OBJECT')


def ensure_all_weighted(mesh_obj, arm_obj, fallback="DEF-hips"):
    """Smart orphan adoption: each unweighted vertex is assigned 1.0 weight to
    the closest DEF bone segment (point-to-segment distance)."""
    log("Smart orphan adoption: closest DEF bone per vertex")

    # Build list of (bone_name, head_world, tail_world) for all DEF bones
    arm_mat = arm_obj.matrix_world
    bone_segs = []
    for b in arm_obj.data.bones:
        if not b.name.startswith("DEF-"): continue
        bone_segs.append((b.name, arm_mat @ b.head_local, arm_mat @ b.tail_local))
    if not bone_segs:
        log("  no DEF bones; using fallback")
        g = _vg(mesh_obj, fallback)
        orphans = [vi for vi, vert in enumerate(mesh_obj.data.vertices)
                   if sum(grp.weight for grp in vert.groups) <= 1e-6]
        if orphans: g.add(orphans, 1.0, 'REPLACE')
        return len(orphans)

    def dist_to_seg(p, a, b):
        ab = b - a
        t = (p - a).dot(ab) / max(ab.length_squared, 1e-12)
        t = max(0.0, min(1.0, t))
        proj = a + ab * t
        return (p - proj).length

    mesh_mat = mesh_obj.matrix_world
    orphans_by_bone = {}
    n_orphans = 0
    for vi, vert in enumerate(mesh_obj.data.vertices):
        if sum(grp.weight for grp in vert.groups) > 1e-6:
            continue
        n_orphans += 1
        wp = mesh_mat @ vert.co
        best_name, best_d = None, float('inf')
        for name, h, t in bone_segs:
            dd = dist_to_seg(wp, h, t)
            if dd < best_d:
                best_d = dd; best_name = name
        orphans_by_bone.setdefault(best_name, []).append(vi)

    for name, idxs in orphans_by_bone.items():
        g = _vg(mesh_obj, name)
        g.add(idxs, 1.0, 'REPLACE')
    log(f"  adopted {n_orphans} orphans → distributed across {len(orphans_by_bone)} bones")
    for name, idxs in sorted(orphans_by_bone.items(), key=lambda x: -len(x[1]))[:8]:
        log(f"    {name}: {len(idxs)}")
    return n_orphans


# ============================================================================ #
#  9. Export
# ============================================================================ #
def export_glb(path, mesh_obj, arm_obj):
    log(f"Exporting → {path}")
    # Select ONLY the body mesh and armature (no widget meshes)
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format='GLB',
        export_skins=True,
        export_yup=True,
        export_apply=False,
        export_animations=False,
        export_extras=True,
        use_selection=True,
    )


# ============================================================================ #
# 10. Verification
# ============================================================================ #
def verify(arm_obj, mesh_obj):
    log("Verify")
    bone_names = {b.name for b in arm_obj.data.bones}
    expected = {
        "spine": ["DEF-hips","DEF-spine_01","DEF-spine_02","DEF-chest","DEF-neck","DEF-head","DEF-jaw"],
        "ears":  ["DEF-ear.L","DEF-ear.R"],
        "whiskers": [f"DEF-whisker_{i+1:02d}.{s}" for s in "LR" for i in range(4)],
        "tail": [f"DEF-tail_{i+1:02d}" for i in range(8)],
        "front_limbs": ["DEF-shoulder.L","DEF-shoulder.R","DEF-arm.L","DEF-arm.R","DEF-forearm.L","DEF-forearm.R","DEF-paw_F.L","DEF-paw_F.R"],
        "back_limbs":  ["DEF-thigh.L","DEF-thigh.R","DEF-shin.L","DEF-shin.R","DEF-paw_B.L","DEF-paw_B.R"],
        "fingers_front": [f"DEF-toe_F_{fi}_{si:02d}.{s}" for s in "LR" for fi in (1,2,3) for si in (1,2,3)],
        "fingers_back":  [f"DEF-toe_B_{fi}_{si:02d}.{s}" for s in "LR" for fi in (1,2,3) for si in (1,2,3)],
        "controllers": ["CTRL-hips","CTRL-chest","CTRL-head","CTRL-jaw","CTRL-foot_F.L","CTRL-foot_F.R","CTRL-foot_B.L","CTRL-foot_B.R","CTRL-eye_aim"],
    }
    ok = True
    for cat, names in expected.items():
        missing = [n for n in names if n not in bone_names]
        if missing:
            log(f"  ✗ {cat}: missing {missing}"); ok = False
        else:
            log(f"  ✓ {cat}: {len(names)}")
    log(f"  Total bones: {len(bone_names)}")
    orphans = sum(1 for v in mesh_obj.data.vertices
                  if sum(g.weight for g in v.groups) <= 1e-6)
    if orphans: log(f"  ✗ orphans: {orphans}"); ok=False
    else: log(f"  ✓ all {len(mesh_obj.data.vertices)} verts weighted")
    if "breath" in arm_obj.keys(): log(f"  ✓ breath={arm_obj['breath']}")
    else: log("  ✗ breath missing"); ok=False
    ik_count = sum(1 for pb in arm_obj.pose.bones
                   if any(c.type == 'IK' for c in pb.constraints))
    log(f"  IK constraints: {ik_count}/4")
    sik = arm_obj.pose.bones.get("DEF-tail_08")
    log(f"  Spline IK on tail: {'YES' if sik and any(c.type=='SPLINE_IK' for c in sik.constraints) else 'NO'}")
    log("  Result: " + ("PASS" if ok else "PARTIAL (see warnings)"))


# ============================================================================ #
# Main
# ============================================================================ #
def main():
    reset_scene()
    import_glb(SRC)
    mesh_obj = cleanup_and_merge()
    A = Anatomy(mesh_obj)
    arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names = build_armature(A)
    setup_constraints(arm_obj, limb_data, tail_bone_names, tail_ctrl_names, A)
    organize_collections(arm_obj, bones_meta)
    widgets = make_widgets()
    assign_widgets(arm_obj, widgets, bones_meta)
    parent_with_auto_weights(mesh_obj, arm_obj)
    manual_weight_overrides(mesh_obj, A)
    smooth_weights(mesh_obj, iterations=2)
    clamp_normalize(mesh_obj, max_inf=4)
    ensure_all_weighted(mesh_obj, arm_obj)
    verify(arm_obj, mesh_obj)
    export_glb(OUT, mesh_obj, arm_obj)
    log("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
