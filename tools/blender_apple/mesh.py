"""Pass 2 — mesh: iskelet polylinelarini konik tup geometrisine cevirir
(cam pine_mesh yansimasi). Paralel-transport cerceve -> burulmasiz halka.
Tek 'AppleTree_Wood' objesi, kabuk materyali."""
import bmesh
import bpy
from mathutils import Vector

from . import config as C


def _ring_sides(depth):
    return 10 if depth == 0 else (7 if depth == 1 else (5 if depth == 2 else 4))


def _frames(pts):
    """Her noktada (tangent, normal, binormal) — paralel transport."""
    n = len(pts)
    tans = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        if t.length < 1e-6:
            t = Vector((0, 0, 1))
        tans.append(t.normalized())
    ref = Vector((1, 0, 0))
    if abs(tans[0].dot(ref)) > 0.9:
        ref = Vector((0, 1, 0))
    nrm = (ref - tans[0] * ref.dot(tans[0])).normalized()
    norms = [nrm]
    for i in range(1, n):
        v = nrm - tans[i] * nrm.dot(tans[i])
        if v.length < 1e-6:
            v = tans[i].cross(Vector((0, 0, 1)))
        nrm = v.normalized()
        norms.append(nrm)
    bins = [tans[i].cross(norms[i]).normalized() for i in range(n)]
    return tans, norms, bins


def build(skel, mats):
    bm = bmesh.new()
    TAU = 6.283185307179586
    for st in skel["stems"]:
        pts, radii, depth = st["pts"], st["radii"], st["depth"]
        if len(pts) < 2:
            continue
        sides = _ring_sides(depth)
        _, norms, bins = _frames(pts)
        rings = []
        for i, p in enumerate(pts):
            r = max(radii[i], 0.004)
            ring = []
            for s in range(sides):
                a = TAU * s / sides
                off = norms[i] * (r * __import__("math").cos(a)) + \
                      bins[i] * (r * __import__("math").sin(a))
                ring.append(bm.verts.new(p + off))
            rings.append(ring)
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            for s in range(sides):
                s2 = (s + 1) % sides
                bm.faces.new((r0[s], r0[s2], r1[s2], r1[s]))
        # uc kapagi
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("AppleTree_Wood")
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new("AppleTree_Wood", me)
    me.materials.append(mats["bark"])
    return ob
