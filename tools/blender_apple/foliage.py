"""Pass 4 — yaprak: ince dal/surgun boyunca capraz-quad yaprak kumeleri.
Tek 'AppleTree_Leaves' objesi, alpha-cut yaprak materyali."""
import math
import random
import bmesh
import bpy
from mathutils import Vector, Quaternion

from . import config as C


def build(skel, mats):
    rng = random.Random(C.SEED + 7)
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    def _leaf(center, ldir, size):
        # tek kucuk yaprak quad'i (taban center, uc ldir yonunde)
        up = Vector((0, 0, 1))
        t = ldir.normalized()
        side = t.cross(up)
        if side.length < 1e-3:
            side = Vector((1, 0, 0))
        side.normalize()
        tip = center + ldir * (size * 1.5)
        wdir = side * (size * 0.5)
        v0 = bm.verts.new(center - wdir)
        v1 = bm.verts.new(center + wdir)
        v2 = bm.verts.new(tip + wdir * 0.45)
        v3 = bm.verts.new(tip - wdir * 0.45)
        f = bm.faces.new((v0, v1, v2, v3))
        for lo, uv in zip(f.loops, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            lo[uv_layer].uv = uv

    def card(center, n_dir, size):
        # kucuk yaprak DEMETI: cevreye sacilan 5-7 mini yaprak (yogun tac)
        t = n_dir.normalized()
        up = Vector((0, 0, 1))
        side = t.cross(up)
        if side.length < 1e-3:
            side = Vector((1, 0, 0))
        side.normalize()
        binv = t.cross(side).normalized()
        cnt = rng.randint(5, 7)
        for _ in range(cnt):
            az = rng.uniform(0, 6.2831)
            el = rng.uniform(0.15, 0.95)
            ld = (t * el
                  + side * (math.cos(az) * (1 - el))
                  + binv * (math.sin(az) * (1 - el))
                  + Vector((0, 0, 0.05))).normalized()
            o = (side * rng.uniform(-1, 1) + binv * rng.uniform(-1, 1)) * size * 0.4
            _leaf(center + o, ld, size * rng.uniform(0.8, 1.2))

    for st in skel["stems"]:
        if st["depth"] < C.LEAF_MIN_DEPTH:
            continue
        pts = st["pts"]
        if len(pts) < 2:
            continue
        m = len(pts) - 1
        for k in range(C.LEAF_CLUSTERS_PER_TWIG):
            u = 0.35 + 0.62 * (k / max(C.LEAF_CLUSTERS_PER_TWIG - 1, 1))
            fi = min(int(u * m), m - 1)
            frac = u * m - fi
            c = pts[fi].lerp(pts[fi + 1], frac)
            d = (pts[fi + 1] - pts[fi]).normalized()
            d = (d + Vector((rng.uniform(-.3, .3), rng.uniform(-.3, .3),
                             rng.uniform(-.15, .15)))).normalized()
            sz = C.LEAF_CARD * rng.uniform(0.8, 1.2)
            card(c, d, sz)

    me = bpy.data.meshes.new("AppleTree_Leaves")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("AppleTree_Leaves", me)
    me.materials.append(mats["leaf"])
    return ob
