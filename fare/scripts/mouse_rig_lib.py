"""
Mouse rig pipeline v2 — shared library.

Proven utilities reused across stage scripts:
  - Tripo joint extraction (anchors that are already inside the mesh)
  - Mesh cleanup (mesh kept UNTOUCHED except import Y-up→Z-up bake)
  - BVH inside-test + closest_inside snap
  - Medial-axis resampling for spine/tail
  - Region-aware weighting with per-bone vertex budgets + L/R mirror
"""

import bpy, bmesh, math, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "mouse3dmodel1k.glb")
OUT_DIR = os.path.join(ROOT, "out")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[lib] {m}", flush=True)


# ----------------------------------------------------------------------------
# Scene / import
# ----------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path=SRC):
    bpy.ops.import_scene.gltf(filepath=path)


def extract_tripo_joints():
    """World-space head/tail of every Tripo joint (anchors)."""
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    if not arms: return {}
    arm = arms[0]
    mw = arm.matrix_world
    j = {}
    for b in arm.data.bones:
        j[b.name] = {"head": (mw @ b.head_local).copy(),
                     "tail": (mw @ b.tail_local).copy()}
    return j


def cleanup_keep_mesh_only():
    """Strip Tripo armature; mesh kept (only import transform baked)."""
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    parts = [o for o in bpy.data.objects
             if o.type == 'MESH' and o.name.startswith("tripo_part")]
    for m in parts:
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
    parts = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in parts: m.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(parts) > 1: bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    return merged


# ----------------------------------------------------------------------------
# BVH inside test
# ----------------------------------------------------------------------------
def build_bvh(mesh):
    bm = bmesh.new(); bm.from_mesh(mesh.data)
    bm.transform(mesh.matrix_world)
    bvh = BVHTree.FromBMesh(bm); bm.free()
    return bvh


def is_inside(bvh, p, eps=1e-4):
    dirs = [Vector((1,0,0)), Vector((-1,0,0)), Vector((0,1,0)),
            Vector((0,-1,0)), Vector((0,0,1)), Vector((0,0,-1))]
    inside = 0
    for d in dirs:
        hits = 0; origin = p + d * eps
        while True:
            hit, _, _, _ = bvh.ray_cast(origin, d, 100.0)
            if hit is None: break
            hits += 1; origin = hit + d * (eps * 4)
            if hits > 16: break
        if hits % 2 == 1: inside += 1
    return inside >= 4


def closest_inside(bvh, target, max_iter=24):
    if is_inside(bvh, target): return target.copy()
    loc, n, _, _ = bvh.find_nearest(target)
    if loc is None: return target.copy()
    inward = -n.normalized()
    p = loc + inward * 0.004
    for _ in range(max_iter):
        if is_inside(bvh, p): return p
        p = p + inward * 0.003
    return p


def cross_section_centroid(mesh, y, bvh, band=0.012):
    """Centroid of mesh verts in a thin Y-band → medial point at that Y."""
    pts = [v.co for v in mesh.data.vertices if abs(v.co.y - y) < band]
    if not pts:
        return None
    c = sum(pts, Vector((0,0,0))) / len(pts)
    return closest_inside(bvh, c)


# ----------------------------------------------------------------------------
# Landmarks
# ----------------------------------------------------------------------------
def detect_landmarks(mesh):
    verts = [v.co for v in mesh.data.vertices]
    xs=[v.x for v in verts]; ys=[v.y for v in verts]; zs=[v.z for v in verts]
    x_min,x_max=min(xs),max(xs); y_min,y_max=min(ys),max(ys); z_min,z_max=min(zs),max(zs)
    ys_size = y_max - y_min
    nose = [v for v in verts if v.y < y_min + ys_size*0.04]
    nose_tip = (sum(nose, Vector((0,0,0)))/len(nose)) if nose else Vector((0,y_min,z_max*0.7))
    tail = [v for v in verts if v.y > y_max - ys_size*0.04]
    tail_tip = (sum(tail, Vector((0,0,0)))/len(tail)) if tail else Vector((0,y_max,z_max*0.3))
    return {"x_min":x_min,"x_max":x_max,"y_min":y_min,"y_max":y_max,
            "z_min":z_min,"z_max":z_max,"x_center":sum(xs)/len(xs),
            "nose_tip":nose_tip,"tail_tip":tail_tip}


# ----------------------------------------------------------------------------
# Medial axis resampler
# ----------------------------------------------------------------------------
def resample_polyline(points, n_segments):
    """Resample a polyline into n_segments+1 equally spaced points."""
    pts = [p for p in points if p is not None]
    if len(pts) < 2: return pts
    seg_len = []
    total = 0.0
    for i in range(len(pts)-1):
        L = (pts[i+1]-pts[i]).length; seg_len.append(L); total += L
    if total < 1e-9: return pts
    step = total / n_segments
    out = [pts[0]]; i = 0; acc = 0.0; cur = pts[0]
    remaining = seg_len[0]
    for k in range(1, n_segments+1):
        target = k * step
        while acc + remaining < target and i < len(pts)-2:
            acc += remaining; i += 1; cur = pts[i]; remaining = seg_len[i]
        t = (target - acc)/remaining if remaining > 1e-9 else 0.0
        out.append(cur + (pts[i+1]-cur)*t)
    return out


# ----------------------------------------------------------------------------
# Region-aware weighting with budgets + L/R mirror
# ----------------------------------------------------------------------------
def dist_to_segment(p, a, b):
    ab = b - a; L2 = ab.dot(ab)
    if L2 < 1e-12: return (p-a).length
    t = max(0.0, min(1.0, (p-a).dot(ab)/L2))
    return (p-(a+ab*t)).length


def region_of_vertex(p, lm):
    """head / FL / FR / BL / BR / tail / body."""
    y0,y1 = lm["y_min"],lm["y_max"]; z0,z1 = lm["z_min"],lm["z_max"]
    xc = lm["x_center"]; ys=y1-y0; zs=z1-z0
    if p.y < y0 + ys*0.34: return "head"
    if p.y > y0 + ys*0.80: return "tail"
    if (y0+ys*0.18 < p.y < y0+ys*0.54 and p.z < z0+zs*0.38 and abs(p.x-xc)>0.035):
        return "FL" if p.x > xc else "FR"
    if (y0+ys*0.48 < p.y < y0+ys*0.86 and p.z < z0+zs*0.52 and abs(p.x-xc)>0.035):
        return "BL" if p.x > xc else "BR"
    return "body"
