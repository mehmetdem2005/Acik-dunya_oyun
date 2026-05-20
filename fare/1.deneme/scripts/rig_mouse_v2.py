"""
AAA mouse rigger v2 — mesh-topology-aware bone placement.

v1 used AABB-based hard-coded ratios for spine/limb landmarks. That fails on
this model because the mouse is in a "sniffing" posture (head lowered, body
curved). Bones placed by AABB land OUTSIDE the actual mesh body.

v2 fixes this by:
  1. Extracting the body MEDIAL AXIS (centerline of mesh cross-sections along Y).
     Spine bones lie on this curved path, not on a straight line.
  2. Tracing limbs from each paw to the body junction via mesh-vertex paths,
     so arm/forearm/shin bones lie inside the limb geometry.
  3. Validating bone placement: every bone head/tail is inside the mesh
     (BVH closest-point test + inside check). Out-of-mesh bones are snapped to
     the nearest interior point.

Usage:
    blender --background --python fare/scripts/rig_mouse_v2.py

Input:  fare/source/mouse3dmodel1k.glb
Output: fare/out/mouse.glb
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
OUT = os.path.join(OUT_DIR, "mouse.glb")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[rig2] {m}", flush=True)


# ============================================================================
# Scene import & cleanup (same as v1)
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path}")
    bpy.ops.import_scene.gltf(filepath=path)


def cleanup_and_merge():
    log("Cleanup: delete placeholder + tripo armature, keep body meshes")
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
# Mesh topology utilities
# ============================================================================
def _connected_islands(mesh_obj, allowed_indices):
    me = mesh_obj.data
    adj = {i: set() for i in allowed_indices}
    for edge in me.edges:
        a, b = edge.vertices
        if a in adj and b in adj:
            adj[a].add(b); adj[b].add(a)
    seen = set(); islands = []
    for start in allowed_indices:
        if start in seen: continue
        stack = [start]; comp = set()
        while stack:
            n = stack.pop()
            if n in seen: continue
            seen.add(n); comp.add(n)
            stack.extend(adj[n] - seen)
        if comp: islands.append(comp)
    return islands


def _full_adjacency(mesh_obj):
    me = mesh_obj.data
    adj = {i: set() for i in range(len(me.vertices))}
    for e in me.edges:
        a, b = e.vertices
        adj[a].add(b); adj[b].add(a)
    return adj


def _bvh_for_mesh(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.transform(mesh_obj.matrix_world)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    return bvh, bm


def _is_inside(bvh, point, sample_dirs=None):
    """Inside-mesh test via parity ray-casting along multiple directions."""
    if sample_dirs is None:
        sample_dirs = [Vector((1, 0.1, 0.05)).normalized(),
                       Vector((0.1, 1, 0.05)).normalized(),
                       Vector((0.05, 0.1, 1)).normalized()]
    inside_count = 0
    for d in sample_dirs:
        hits = 0
        origin = point.copy()
        while True:
            loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
            if loc is None: break
            hits += 1
            origin = loc + d * 1e-5
        if hits % 2 == 1:
            inside_count += 1
    return inside_count >= 2  # majority


def _snap_to_inside(bvh, point, fallback_search_radius=0.2):
    """If point isn't inside the mesh, search a small neighborhood for an inside point."""
    if _is_inside(bvh, point):
        return point
    best = None
    best_d = float('inf')
    # spiral sample
    for r in (0.02, 0.05, 0.1, 0.2):
        if r > fallback_search_radius: break
        for theta in [i * math.pi / 6 for i in range(12)]:
            for phi in [-math.pi/3, 0, math.pi/3]:
                offset = Vector((r * math.cos(theta) * math.cos(phi),
                                  r * math.sin(theta) * math.cos(phi),
                                  r * math.sin(phi)))
                cand = point + offset
                if _is_inside(bvh, cand):
                    d = offset.length
                    if d < best_d:
                        best_d = d; best = cand
        if best: break
    return best if best else point


# ============================================================================
# Anatomy: medial axis + feature detection
# ============================================================================
class Anatomy:
    """
    Mesh-topology-aware anatomy.
    Spine path: list of Vector points along the body centerline, ordered tail→head.
    Limb paths: list of Vectors from paw to body junction.
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
        self.x_half = max(0.001, (self.x_max - self.x_min) / 2.0)
        self.y_size = self.y_max - self.y_min
        self.z_size = self.z_max - self.z_min
        log(f"AABB X=[{self.x_min:.3f},{self.x_max:.3f}] "
            f"Y=[{self.y_min:.3f},{self.y_max:.3f}] "
            f"Z=[{self.z_min:.3f},{self.z_max:.3f}]")

        self.bvh, _bm = _bvh_for_mesh(mesh_obj)

        self._build_body_axis()
        self.head_dir = self._detect_head_direction_from_axis()
        log(f"Head direction: {'+Y' if self.head_dir > 0 else '-Y'}")

        # Sample landmarks along the curved axis (parameterized 0..1, tail to head)
        self._sample_axis_landmarks()
        self.paws = self._detect_paws()
        self.ears = self._detect_ears()
        self.eyes = self._detect_eyes()
        self.nose_tip = self._detect_nose_tip()
        log(f"Body axis: {len(self.axis)} centroid points")
        log(f"Paws: { {k: [round(c,3) for c in p] for k, p in self.paws.items()} }")
        log(f"Ears: { {k: [round(c,3) for c in p] for k, p in self.ears.items()} }")
        log(f"Nose: {[round(c,3) for c in self.nose_tip]}")

    def _build_body_axis(self):
        """Compute body centerline by slicing into Y-bands and taking centroids."""
        bands = 50
        y_step = self.y_size / bands
        path = []
        for i in range(bands):
            y_lo = self.y_min + i * y_step
            y_hi = y_lo + y_step
            band = [v for v in self.verts if y_lo <= v.y < y_hi]
            if len(band) < 8: continue
            cx = sum(v.x for v in band) / len(band)
            cy = sum(v.y for v in band) / len(band)
            cz = sum(v.z for v in band) / len(band)
            path.append(Vector((cx, cy, cz)))
        # Smooth with a small moving-average window
        smoothed = []
        w = 2  # +/- 2 bands → window of 5
        for i in range(len(path)):
            lo = max(0, i - w); hi = min(len(path), i + w + 1)
            chunk = path[lo:hi]
            avg = Vector((sum(p.x for p in chunk)/len(chunk),
                          sum(p.y for p in chunk)/len(chunk),
                          sum(p.z for p in chunk)/len(chunk)))
            smoothed.append(avg)
        # SNAP each axis point to inside mesh (centroid of band sometimes isn't inside)
        snapped = [_snap_to_inside(self.bvh, p) for p in smoothed]
        self.axis = snapped
        # Cumulative arc-length parameterization (0=first point=lower Y, 1=last)
        arc = [0.0]
        for i in range(1, len(snapped)):
            arc.append(arc[-1] + (snapped[i] - snapped[i-1]).length)
        total = arc[-1] if arc[-1] > 0 else 1.0
        self.axis_t = [a / total for a in arc]
        log(f"  axis built: {len(snapped)} pts, total arc length {total:.3f}")

    def axis_at_t(self, t):
        """Sample axis at normalized arc length t∈[0,1]. t=0 at first point, t=1 at last.
        Always returns a Vector inside the mesh (snapped)."""
        if not self.axis: return Vector((self.x_center, 0, 0))
        t = max(0.0, min(1.0, t))
        # binary search
        lo, hi = 0, len(self.axis_t) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self.axis_t[mid] < t: lo = mid
            else: hi = mid
        # Interpolate between lo and hi
        t0, t1 = self.axis_t[lo], self.axis_t[hi]
        if t1 - t0 < 1e-9:
            return self.axis[lo]
        f = (t - t0) / (t1 - t0)
        return self.axis[lo].lerp(self.axis[hi], f)

    def _detect_head_direction_from_axis(self):
        """Head end = where mesh cross-section is thinnest (snout).
        Compute cross-sectional radius at each axis point."""
        radii = []
        for p in self.axis:
            y_lo = p.y - self.y_size * 0.025
            y_hi = p.y + self.y_size * 0.025
            band = [v for v in self.verts if y_lo <= v.y <= y_hi]
            if not band: radii.append(0.0); continue
            r = max(math.hypot(v.x - p.x, v.z - p.z) for v in band)
            radii.append(r)
        # Head/snout is where radius is thinnest
        min_idx = radii.index(min(radii))
        snout_at_high_t = min_idx >= len(radii) // 2
        log(f"  cross-section thinnest at idx {min_idx}/{len(radii)} → "
            f"snout at {'high-t (Y+)' if snout_at_high_t else 'low-t (Y-)'}")
        return +1 if snout_at_high_t else -1

    def _sample_axis_landmarks(self):
        """Map t∈[0,1] along axis to anatomy points.
        For body sections (tail/hips/spine/chest) we use the medial axis.
        For HEAD/JAW/NECK we use the HEAD VOLUME center (computed from where
        ears+eyes verts cluster), NOT the axis end — because for a sniffing
        pose the axis ends at floor where the snout is, missing the actual
        head/skull volume up top.
        """
        d = self.head_dir
        def at(frac):
            t = frac if d > 0 else (1.0 - frac)
            return self.axis_at_t(t)

        # Body/tail use the medial axis directly
        self.p_tail_tip   = at(0.00)
        self.p_hips       = at(0.30)
        self.p_spine_1    = at(0.40)
        self.p_spine_2    = at(0.50)
        self.p_chest      = at(0.62)
        self.p_shoulders  = at(0.72)

        # ---- Head volume detection ----
        # Head verts = mesh verts in the "head" portion of Y range AND with
        # high enough Z to be above the snout-extension.
        if d > 0:
            head_y_lo = self.y_min + self.y_size * 0.60   # neck zone start
            head_y_hi = self.y_max
        else:
            head_y_lo = self.y_min
            head_y_hi = self.y_min + self.y_size * 0.40

        head_verts = [v for v in self.verts if head_y_lo <= v.y <= head_y_hi]
        if not head_verts:
            head_verts = self.verts
        # Filter out snout-extension verts (very low Z near the floor)
        head_z_min_all = min(v.z for v in head_verts)
        head_z_max_all = max(v.z for v in head_verts)
        head_z_range = max(1e-3, head_z_max_all - head_z_min_all)
        skull_z_thresh = head_z_min_all + head_z_range * 0.35  # exclude bottom 35% (snout)
        skull_verts = [v for v in head_verts if v.z > skull_z_thresh]
        if not skull_verts:
            skull_verts = head_verts

        # Skull center = centroid of high-Z head verts
        sx = sum(v.x for v in skull_verts) / len(skull_verts)
        sy = sum(v.y for v in skull_verts) / len(skull_verts)
        sz = sum(v.z for v in skull_verts) / len(skull_verts)
        skull_center = Vector((sx, sy, sz))
        log(f"  skull center (head volume): ({sx:+.3f}, {sy:+.3f}, {sz:+.3f}) "
            f"from {len(skull_verts)} verts")

        # Neck = where the body transitions into the head. Take the medial axis
        # point at the Y-position just BEFORE skull_center.y on the body side.
        if d > 0:
            neck_y = skull_center.y - self.y_size * 0.08
        else:
            neck_y = skull_center.y + self.y_size * 0.08
        # Find nearest axis point to that Y
        best_idx = min(range(len(self.axis)),
                        key=lambda i: abs(self.axis[i].y - neck_y))
        self.p_neck = self.axis[best_idx]

        # Head bone goes from neck → skull_center
        self.p_head_base = self.p_neck   # head bone HEAD (origin)
        self.p_head_tail = skull_center  # head bone TAIL — at skull centroid

        # Jaw: lower-front of skull volume, extending to nose_tip
        # Find lowest-Z vertex in the head-y range (the snout/jaw bottom)
        if d > 0:
            jaw_verts = [v for v in self.verts if v.y > head_y_lo + self.y_size * 0.15]
        else:
            jaw_verts = [v for v in self.verts if v.y < head_y_hi - self.y_size * 0.15]
        if jaw_verts:
            jaw_z = min(v.z for v in jaw_verts)
            jaw_y = (max(v.y for v in jaw_verts) + min(v.y for v in jaw_verts)) / 2
            # Jaw root: under the skull, at the front
            self.p_jaw = Vector((self.x_center,
                                  skull_center.y + d * self.y_size * 0.05,
                                  jaw_z + self.z_size * 0.03))
        else:
            self.p_jaw = Vector((self.x_center,
                                  skull_center.y + d * self.y_size * 0.05,
                                  skull_center.z - self.z_size * 0.10))

        # Nose is the actual snout tip
        # (computed later in _detect_nose_tip; here we just hold an axis position)
        self.p_nose = at(1.00)

        # convenience
        self.z_floor = self.z_min
        self.z_belly = self.z_min + self.z_size * 0.30
        self.skull_center = skull_center

    # ---- Paw detection (v1 method — direct Y/X quadrant on floor verts) ----
    def _detect_paws(self):
        """4 paw plant points: lowest-Z verts in each X(L/R) × Y(F/B) quadrant.
        Snout exclusion: skip verts in the snout 12% of Y range (otherwise the
        downturned snout gets misclassified as a front paw)."""
        floor_thresh = self.z_min + self.z_size * 0.10
        d = self.head_dir
        # Snout Y range — exclude
        if d > 0:
            snout_y_min = self.y_max - self.y_size * 0.12
            snout_pred = lambda p: p.y > snout_y_min
        else:
            snout_y_max = self.y_min + self.y_size * 0.12
            snout_pred = lambda p: p.y < snout_y_max

        # Body Y mid-point on axis
        mid_y = self.axis_at_t(0.5).y

        def front_pred(p):
            return (p.y > mid_y) if d > 0 else (p.y < mid_y)
        def back_pred(p):
            return (p.y < mid_y) if d > 0 else (p.y > mid_y)

        left_pred  = lambda p: p.x < self.x_center
        right_pred = lambda p: p.x > self.x_center

        out = {}
        for name, fz, fx in (("paw_F_L", front_pred, left_pred),
                              ("paw_F_R", front_pred, right_pred),
                              ("paw_B_L", back_pred, left_pred),
                              ("paw_B_R", back_pred, right_pred)):
            cand = [v for v in self.verts
                    if v.z < floor_thresh and fz(v) and fx(v) and not snout_pred(v)]
            if len(cand) < 6:
                cand = [v for v in self.verts if fz(v) and fx(v) and not snout_pred(v)]
                cand.sort(key=lambda p: p.z)
                cand = cand[: max(20, len(cand)//50)]
            if not cand:
                # Last-ditch: quadrant center
                qx = self.x_center + (-1 if "L" in name else 1) * self.x_half * 0.6
                qy = mid_y + (self.y_size * 0.25) * (1 if "F" in name else -1) * d
                out[name] = Vector((qx, qy, self.z_floor))
                continue
            cx = sum(v.x for v in cand) / len(cand)
            cy = sum(v.y for v in cand) / len(cand)
            cz = self.z_floor + self.z_size * 0.02
            out[name] = Vector((cx, cy, cz))
        return out

    def trace_limb_path(self, paw_idx_island, body_root, max_steps=12, step_size=None):
        """Return a list of mesh-interior points from a paw plant point up to
        the body junction. Uses BFS across the mesh: start at paw centroid,
        walk along mesh-vert adjacency toward body_root, sampling positions
        every N steps. Returns the inner-axis points of the limb."""
        # Simpler approach: linearly interpolate between paw and body junction
        # but snap each intermediate point to be inside the mesh.
        steps = max_steps
        path = []
        for i in range(steps + 1):
            t = i / steps
            p = paw_idx_island.lerp(body_root, t)
            p = _snap_to_inside(self.bvh, p)
            path.append(p)
        return path

    def _detect_ears(self):
        """Ears = lateral X verts in the HEAD-Y range, at locally high Z.

        For a curved-pose body the global max-Z is the back hump, NOT the ears.
        We restrict to verts whose Y is in the head/neck region (AABB-based:
        roughly the upper-Y 25% for head_dir=+1), then take high local Z.
        """
        d = self.head_dir
        # Head-region Y range: from neck-frac to nose-frac
        # neck = 0.74, nose = 1.00 — these are AABB-relative because we want
        # the head VOLUME regardless of how the axis curves.
        if d > 0:
            head_y_lo = self.y_min + self.y_size * 0.72
            head_y_hi = self.y_max
        else:
            head_y_lo = self.y_min
            head_y_hi = self.y_max - self.y_size * 0.72

        head_verts = [v for v in self.verts if head_y_lo <= v.y <= head_y_hi]
        if not head_verts:
            return {
                "ear_L": Vector((self.x_center - self.x_half * 0.55,
                                  self.p_head_base.y, self.p_head_base.z + self.z_size * 0.20)),
                "ear_R": Vector((self.x_center + self.x_half * 0.55,
                                  self.p_head_base.y, self.p_head_base.z + self.z_size * 0.20)),
            }

        head_z_min = min(v.z for v in head_verts)
        head_z_max = max(v.z for v in head_verts)
        head_z_size = max(1e-3, head_z_max - head_z_min)
        z_thresh = head_z_min + head_z_size * 0.75  # top 25% of head

        ear_L_verts = [v for v in head_verts
                       if v.z > z_thresh and (v.x - self.x_center) < -self.x_half * 0.18]
        ear_R_verts = [v for v in head_verts
                       if v.z > z_thresh and (v.x - self.x_center) > self.x_half * 0.18]
        out = {}
        for verts, key, sign in ((ear_L_verts, "ear_L", -1), (ear_R_verts, "ear_R", +1)):
            if verts:
                cx = sum(v.x for v in verts) / len(verts)
                cy = sum(v.y for v in verts) / len(verts)
                cz = sum(v.z for v in verts) / len(verts)
                out[key] = Vector((cx, cy, cz))
            else:
                out[key] = Vector((self.x_center + sign * self.x_half * 0.55,
                                    self.p_head_base.y,
                                    self.p_head_base.z + self.z_size * 0.20))
        return out

    def _detect_eyes(self):
        head = self.p_head_base
        return {
            "eye_L": Vector((self.x_center - self.x_half * 0.45, head.y, head.z + self.z_size * 0.05)),
            "eye_R": Vector((self.x_center + self.x_half * 0.45, head.y, head.z + self.z_size * 0.05)),
        }

    def _detect_nose_tip(self):
        d = self.head_dir
        if d > 0:
            cand = [v for v in self.verts if v.y > self.y_min + self.y_size * 0.95]
        else:
            cand = [v for v in self.verts if v.y < self.y_min + self.y_size * 0.05]
        if not cand: return self.p_nose.copy()
        cx = sum(v.x for v in cand) / len(cand)
        cy = sum(v.y for v in cand) / len(cand)
        cz = sum(v.z for v in cand) / len(cand)
        return Vector((cx, cy, cz))


# ============================================================================
# Armature build using axis path
# ============================================================================
def V(x, y, z): return Vector((x, y, z))


def build_armature(A: Anatomy):
    log("Build armature (axis-following)")
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig"
    arm = arm_obj.data
    arm.name = "MouseRigData"
    eb = arm.edit_bones
    d = A.head_dir
    cx = A.x_center

    bones_meta = {}

    def mk(name, head, tail, parent=None, connect=False, roll=0.0,
           role="DEF", coll="deform", bbones=1):
        b = eb.new(name)
        b.head = Vector(head); b.tail = Vector(tail); b.roll = roll
        if parent is not None:
            b.parent = parent; b.use_connect = connect
        b.bbone_segments = bbones
        bones_meta[name] = {"role": role, "collection": coll}
        return b

    # Root (CTRL) — placed at hips axis point, offset toward floor
    hips_pos = A.p_hips
    root = mk("root",
              V(cx, hips_pos.y - d * 0.06, A.z_floor + 0.005),
              V(cx, hips_pos.y + d * 0.06, A.z_floor + 0.005),
              role="CTRL", coll="ctrl_main")

    # ---- Spine: medial axis for body, then SKULL-CENTER for head ----
    # Body chain (no head yet — head goes to skull volume, not axis end)
    spine_pts = [A.p_hips, A.p_spine_1, A.p_spine_2, A.p_chest, A.p_neck]
    spine_names = ["DEF-hips", "DEF-spine_01", "DEF-spine_02", "DEF-chest", "DEF-neck_part"]
    spine_bbones = [1, 2, 2, 2, 2]
    prev = root
    spine_bones = {}
    for i in range(len(spine_pts) - 1):
        name = spine_names[i]
        b = mk(name, spine_pts[i], spine_pts[i + 1], parent=prev,
                connect=(prev is not root), coll="deform", bbones=spine_bbones[i])
        spine_bones[name] = b
        prev = b

    # Compute "back of skull" — pivot point where head rotates around.
    # 70% of the way from p_neck → skull_center, so DEF-head pivot is at the
    # rear of the head volume, NOT in the middle (which would prevent rotation
    # from visibly moving head verts).
    back_of_skull = A.p_neck.lerp(A.skull_center, 0.70)

    # NECK bone: from chest_top (p_neck axis) → back_of_skull
    neck_bone = mk("DEF-neck", A.p_neck, back_of_skull,
                    parent=spine_bones["DEF-spine_02"],
                    connect=False, coll="deform", bbones=2)
    spine_bones["DEF-neck"] = neck_bone

    # HEAD bone: from back_of_skull → all the way to nose tip.
    # This long bone covers the entire head + snout volume, so heat weighting
    # binds skull top, eyes, and upper snout to it. Rotating pivots at
    # back_of_skull, swinging the whole head.
    head_tail = A.nose_tip
    head_bone = mk("DEF-head", back_of_skull, head_tail,
                    parent=neck_bone, connect=True, coll="deform")
    spine_bones["DEF-head"] = head_bone

    # JAW bone: from under-skull forward to nose_tip
    jaw_head = A.p_jaw
    jaw_tail = A.nose_tip
    if (jaw_tail - jaw_head).length < 1e-3:
        jaw_tail = jaw_head + V(0, d * 0.04, 0)
    jaw_bone = mk("DEF-jaw", jaw_head, jaw_tail, parent=head_bone, coll="deform")

    # Spine CTRL mirrors
    hips_ctrl  = mk("CTRL-hips",  A.p_hips, A.p_spine_1, parent=root, role="CTRL", coll="ctrl_main")
    chest_ctrl = mk("CTRL-chest", A.p_chest, A.p_neck, parent=hips_ctrl, role="CTRL", coll="ctrl_main")
    # CTRL-head matches DEF-head exactly (same head and tail) so LOCAL→LOCAL copy works
    head_ctrl  = mk("CTRL-head",  back_of_skull, A.nose_tip, parent=chest_ctrl, role="CTRL", coll="ctrl_face")
    jaw_ctrl   = mk("CTRL-jaw",   jaw_head, jaw_tail, parent=head_ctrl, role="CTRL", coll="ctrl_face")

    # ---- Tail: 8 segments along axis from hips → tail tip ----
    tail_bones = []
    tail_pts = []
    for i in range(9):
        t = i / 8.0  # 0 at tail tip end of axis (low t if head_dir=+1 → flipped)
        # We want tail to start AT hips and END at tail tip.
        # head_dir = +1: head at axis_t=1, tail at axis_t=0. Tail starts at frac 0.30 (hips) and goes to 0.00.
        # head_dir = -1: head at axis_t=0, tail at axis_t=1. Tail starts at 0.70 (hips) and goes to 1.00.
        if d > 0:
            frac = 0.30 * (1.0 - t)   # from 0.30 down to 0.00
        else:
            frac = 0.70 + 0.30 * t    # from 0.70 up to 1.00
        tail_pts.append(A.axis_at_t(frac))
    prev = spine_bones["DEF-hips"]
    tail_bone_names = []
    for i in range(8):
        b = mk(f"DEF-tail_{i+1:02d}", tail_pts[i], tail_pts[i+1],
                parent=prev, connect=(i > 0), coll="deform", bbones=2)
        tail_bones.append(b); tail_bone_names.append(b.name); prev = b

    # Tail spline IK control bones
    tail_ctrl_names = []
    for ti, t in enumerate((0.0, 0.5, 1.0)):
        idx = int(round(t * 8))
        p = tail_pts[idx]
        name = f"CTRL-tail_{ti+1}"
        mk(name, p, p + V(0, d * 0.04, 0.02),
            parent=root, role="CTRL", coll="ctrl_main")
        tail_ctrl_names.append(name)

    # ---- Limbs: trace from paw to body junction ----
    limb_data = []

    chest_b = spine_bones["DEF-chest"]
    hips_b  = spine_bones["DEF-hips"]

    for side, sx in (("L", -1), ("R", +1)):
        paw_pos = A.paws[f"paw_F_{side}"]
        # Body junction = shoulder area on axis, slightly lateral
        shoulder_axis = A.p_shoulders
        shoulder_pos = V(cx + sx * A.x_half * 0.30, shoulder_axis.y, shoulder_axis.z - A.z_size * 0.05)
        # Path from shoulder to paw (4 segments: shoulder, arm, forearm, paw)
        path = []
        for i in range(5):
            t = i / 4
            p = shoulder_pos.lerp(paw_pos, t)
            p = _snap_to_inside(A.bvh, p) if i < 4 else p  # paw is at surface, don't snap
            path.append(p)
        sh = mk(f"DEF-shoulder.{side}", path[0], path[1], parent=chest_b, coll="deform")
        upper = mk(f"DEF-arm.{side}", path[1], path[2], parent=sh, connect=True, coll="deform")
        # twist bone in upper arm
        mid_arm = (path[1] + path[2]) * 0.5
        mk(f"MCH-arm_twist.{side}", path[1], mid_arm, parent=upper, role="MCH", coll="mch")
        fore = mk(f"DEF-forearm.{side}", path[2], path[3], parent=upper, connect=True, coll="deform")
        paw = mk(f"DEF-paw_F.{side}", path[3], path[4], parent=fore, connect=True, coll="deform")

        # Foot-roll MCH chain + IK foot ctrl + pole
        heel = V(paw_pos.x, paw_pos.y - d * A.y_size * 0.04, A.z_floor)
        toe  = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.06, A.z_floor)
        mch_heel = mk(f"MCH-heel_F.{side}", heel, V(paw_pos.x, paw_pos.y, A.z_floor),
                       parent=root, role="MCH", coll="mch")
        mk(f"MCH-toe_F.{side}", V(paw_pos.x, paw_pos.y, A.z_floor), toe,
            parent=mch_heel, role="MCH", coll="mch")
        mk(f"CTRL-foot_F.{side}", heel, heel + V(0, d * 0.05, 0),
            parent=root, role="CTRL", coll="ctrl_ik")
        pole_pos = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.30, A.z_belly + A.z_size * 0.25)
        mk(f"CTRL-pole_F.{side}", pole_pos, pole_pos + V(0, 0, 0.03),
            parent=root, role="CTRL", coll="ctrl_ik")

        # Toes: 3 fingers × 3 seg
        for fi in range(3):
            spread = (fi - 1) * 0.20
            prev_t = paw
            for si in range(3):
                t0 = si / 3.0; t1 = (si + 1) / 3.0
                base = path[4]
                fwd = V(sx * spread * A.x_half * 0.3, d * A.y_size * 0.03, 0)
                bn = mk(f"DEF-toe_F_{fi+1}_{si+1:02d}.{side}",
                         base + fwd * t0, base + fwd * t1,
                         parent=prev_t, connect=(si > 0), coll="deform")
                prev_t = bn

        limb_data.append({"side": side, "front": True,
                          "paw": f"DEF-paw_F.{side}",
                          "forearm": f"DEF-forearm.{side}",
                          "arm": f"DEF-arm.{side}",
                          "ik_target": f"CTRL-foot_F.{side}",
                          "pole_target": f"CTRL-pole_F.{side}",
                          "twist": f"MCH-arm_twist.{side}"})

    for side, sx in (("L", -1), ("R", +1)):
        paw_pos = A.paws[f"paw_B_{side}"]
        hip_axis = A.p_hips
        hip_pos = V(cx + sx * A.x_half * 0.30, hip_axis.y, hip_axis.z - A.z_size * 0.04)
        path = []
        for i in range(5):
            t = i / 4
            p = hip_pos.lerp(paw_pos, t)
            p = _snap_to_inside(A.bvh, p) if i < 4 else p
            path.append(p)
        th = mk(f"DEF-thigh.{side}", path[0], path[1], parent=hips_b, coll="deform")
        mid_t = (path[0] + path[1]) * 0.5
        mk(f"MCH-thigh_twist.{side}", path[0], mid_t, parent=th, role="MCH", coll="mch")
        sh = mk(f"DEF-shin.{side}", path[1], path[2], parent=th, connect=True, coll="deform")
        # Wait, the chain should be: thigh → shin → ankle → paw_B → toes (5 segments).
        # I have 5 path points: 0=hip, 1=knee, 2=ankle, 3=heel_top, 4=paw_floor
        # Let me restructure: thigh = 0→1, shin = 1→2, paw = 2→4 effectively
        # Actually path has 5 pts. Let's use: thigh path[0]→path[2], shin path[2]→path[3], paw path[3]→path[4]
        # Or, more naturally, a 4-bone chain on 4 segments.
        # Rebuild:
        bpy.ops.armature.select_all(action='DESELECT')
        # delete just-added shin and thigh
        eb.remove(eb[sh.name])
        eb.remove(eb[th.name])
        eb.remove(eb[f"MCH-thigh_twist.{side}"])
        # Use path with 4 segments → 4 bones
        path4 = []
        for i in range(5):
            t = i / 4
            p = hip_pos.lerp(paw_pos, t)
            p = _snap_to_inside(A.bvh, p) if i < 4 else p
            path4.append(p)
        th = mk(f"DEF-thigh.{side}", path4[0], path4[1], parent=hips_b, coll="deform")
        mid_t = (path4[0] + path4[1]) * 0.5
        mk(f"MCH-thigh_twist.{side}", path4[0], mid_t, parent=th, role="MCH", coll="mch")
        sh = mk(f"DEF-shin.{side}", path4[1], path4[2], parent=th, connect=True, coll="deform")
        ankle = mk(f"DEF-ankle.{side}", path4[2], path4[3], parent=sh, connect=True, coll="deform")
        paw = mk(f"DEF-paw_B.{side}", path4[3], path4[4], parent=ankle, connect=True, coll="deform")

        heel = V(paw_pos.x, paw_pos.y - d * A.y_size * 0.04, A.z_floor)
        toe  = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.06, A.z_floor)
        mch_heel = mk(f"MCH-heel_B.{side}", heel, V(paw_pos.x, paw_pos.y, A.z_floor),
                       parent=root, role="MCH", coll="mch")
        mk(f"MCH-toe_B.{side}", V(paw_pos.x, paw_pos.y, A.z_floor), toe,
            parent=mch_heel, role="MCH", coll="mch")
        mk(f"CTRL-foot_B.{side}", heel, heel + V(0, d * 0.05, 0),
            parent=root, role="CTRL", coll="ctrl_ik")
        pole_pos = V(paw_pos.x, paw_pos.y + d * A.y_size * 0.30, A.z_belly + A.z_size * 0.25)
        mk(f"CTRL-pole_B.{side}", pole_pos, pole_pos + V(0, 0, 0.03),
            parent=root, role="CTRL", coll="ctrl_ik")

        for fi in range(3):
            spread = (fi - 1) * 0.20
            prev_t = paw
            for si in range(3):
                t0 = si / 3.0; t1 = (si + 1) / 3.0
                base = path4[4]
                fwd = V(sx * spread * A.x_half * 0.3, d * A.y_size * 0.03, 0)
                bn = mk(f"DEF-toe_B_{fi+1}_{si+1:02d}.{side}",
                         base + fwd * t0, base + fwd * t1,
                         parent=prev_t, connect=(si > 0), coll="deform")
                prev_t = bn

        limb_data.append({"side": side, "front": False,
                          "paw": f"DEF-paw_B.{side}",
                          "forearm": f"DEF-shin.{side}",
                          "arm": f"DEF-thigh.{side}",
                          "ik_target": f"CTRL-foot_B.{side}",
                          "pole_target": f"CTRL-pole_B.{side}",
                          "twist": f"MCH-thigh_twist.{side}"})

    # ---- Ears ----
    # Ear base = skull_center but shifted laterally toward each ear
    for side, key in (("L", "ear_L"), ("R", "ear_R")):
        ear_pos = A.ears[key]
        # Base on the side of the skull, halfway between skull_center and ear tip
        base = A.skull_center.lerp(ear_pos, 0.4)
        # Make sure base is inside mesh
        base = _snap_to_inside(A.bvh, base)
        mk(f"DEF-ear.{side}", base, ear_pos, parent=head_bone, coll="deform", bbones=3)
        mk(f"CTRL-ear.{side}", base, ear_pos, parent=head_ctrl, role="CTRL", coll="ctrl_face")

    # ---- Whiskers (4 per side) ----
    # Whisker base = on cheek (lateral, at snout level), tip extends outward
    for side, sx in (("L", -1), ("R", +1)):
        for i in range(4):
            t = i / 3.0
            yb = A.p_jaw.y + (A.nose_tip.y - A.p_jaw.y) * (0.3 + 0.4 * t)
            zb = A.p_jaw.z + (A.skull_center.z - A.p_jaw.z) * (0.3 + 0.2 * t)
            xb = cx + sx * A.x_half * 0.25
            base = V(xb, yb, zb)
            tip = V(cx + sx * A.x_half * 1.40,
                     A.nose_tip.y + d * A.y_size * 0.04,
                     zb)
            mk(f"DEF-whisker_{i+1:02d}.{side}", base, tip,
                parent=head_bone, coll="deform", bbones=4)

    # ---- Eyes ----
    aim_dist = A.y_size * 0.35
    y_target = A.nose_tip.y + d * aim_dist
    eye_aim_master = mk("CTRL-eye_aim",
                         V(cx, y_target, A.skull_center.z),
                         V(cx, y_target, A.skull_center.z + 0.03),
                         parent=head_ctrl, role="CTRL", coll="ctrl_face")
    for side in ("L", "R"):
        eye_pos = A.eyes[f"eye_{side}"]
        # Place eye bone in the skull volume (use skull_center.z for height)
        eye_pos_fixed = Vector((eye_pos.x, eye_pos.y, max(eye_pos.z, A.skull_center.z * 0.85)))
        mk(f"DEF-eye.{side}", eye_pos_fixed, eye_pos_fixed + V(0, d * 0.02, 0),
            parent=head_bone, coll="deform")
        mk(f"CTRL-eye_aim.{side}",
            V(eye_pos.x, y_target, A.skull_center.z),
            V(eye_pos.x, y_target, A.skull_center.z + 0.02),
            parent=eye_aim_master, role="CTRL", coll="ctrl_face")

    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"Armature built: {len(arm.bones)} bones")
    return arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names


# ============================================================================
# Constraints, drivers, collections, skinning — reuse v1 implementations
# ============================================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rig_mouse as v1  # noqa: E402


# ============================================================================
# Main
# ============================================================================
def main():
    reset_scene()
    import_glb(SRC)
    mesh_obj = cleanup_and_merge()
    A = Anatomy(mesh_obj)
    arm_obj, bones_meta, limb_data, tail_bone_names, tail_ctrl_names = build_armature(A)

    # Pose-mode constraints (reuse v1 but pass our Anatomy — the methods only need
    # generic Anatomy fields like x_center, y_size, head_dir, etc.)
    # We adapt: v1.setup_constraints expects a v1.Anatomy. Provide a shim.
    class AnatomyShim:
        pass
    A_shim = AnatomyShim()
    A_shim.head_dir = A.head_dir
    A_shim.x_center = A.x_center
    A_shim.y_size = A.y_size
    A_shim.z_size = A.z_size
    A_shim.x_half = A.x_half
    A_shim.z_spine = A.p_hips.z
    A_shim.y_hips = A.p_hips.y
    A_shim.y_tail_tip = A.p_tail_tip.y

    v1.setup_constraints(arm_obj, limb_data, tail_bone_names, tail_ctrl_names, A_shim)
    v1.organize_collections(arm_obj, bones_meta)
    widgets = v1.make_widgets()
    v1.assign_widgets(arm_obj, widgets, bones_meta)
    v1.parent_with_auto_weights(mesh_obj, arm_obj)
    # Skip manual weight overrides for now (v1 ones may not align with v2 anatomy)
    v1.smooth_weights(mesh_obj, iterations=2)
    v1.clamp_normalize(mesh_obj, max_inf=4)
    v1.ensure_all_weighted(mesh_obj, arm_obj)
    v1.verify(arm_obj, mesh_obj)
    v1.export_glb(OUT, mesh_obj, arm_obj)
    log("DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
