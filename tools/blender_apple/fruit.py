"""Pass 5 — elma: surgun uclarinin bir alt kumesine hafif basik kure
(sap cukuru). Tek 'AppleTree_Apples' objesi, elma materyali."""
import random
import bmesh
import bpy
from mathutils import Vector, Matrix

from . import config as C


def build(skel, mats):
    rng = random.Random(C.SEED + 13)
    tips = [t for t in skel["tips"]]
    rng.shuffle(tips)
    tips = tips[:min(C.APPLE_COUNT, len(tips))]

    bm = bmesh.new()
    r = C.APPLE_RADIUS
    for t in tips:
        pos = t["pos"] + Vector((0, 0, -r * 0.9))   # daldan asili
        tmp = bmesh.new()
        bmesh.ops.create_icosphere(tmp, subdivisions=2, radius=r)
        # dikey basiklik + ust/alt hafif cukur
        for v in tmp.verts:
            v.co.z *= C.APPLE_SQUASH
            if v.co.z > r * 0.62:
                v.co.z -= r * 0.18
            if v.co.z < -r * 0.55:
                v.co.z += r * 0.10
        for v in tmp.verts:
            v.co += pos
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        me_tmp = bpy.data.meshes.new("ap_tmp")
        tmp.to_mesh(me_tmp)
        tmp.free()
        bm.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)

    me = bpy.data.meshes.new("AppleTree_Apples")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("AppleTree_Apples", me)
    me.materials.append(mats["apple"])
    return ob
