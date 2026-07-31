"""LOD uretimi, carpisma proxy'leri, golge proxy'si ve glTF 2.0 disa aktarim."""

import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

from . import config as C


# ==================================================================
# YARDIMCI
# ==================================================================
def tri_count(obj):
    me = obj.data
    n = 0
    for p in me.polygons:
        n += len(p.vertices) - 2
    return n


def only_select(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def recalc_normals(obj):
    """Her BAGLI KABUGU ayri ayri disa dogru cevirir.

    bmesh'in recalc_face_normals'i ic ice gecmis kabuklarda (goz, dil, dis
    kafanin icinde) yonu ters secebiliyor. Bu yuzden her adanin isaretli
    hacmi hesaplanir; negatifse o adanin yuzleri cevrilir. Hacim isareti
    kapali kabuk icin orijinden bagimsizdir -> guvenilir olcut.
    """
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()

    seen = set()
    flipped_islands = 0
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack = [f0]
        island = []
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for nf in e.link_faces:
                    if nf.index not in seen:
                        seen.add(nf.index)
                        stack.append(nf)
        vol = 0.0
        for f in island:
            vs = [v.co for v in f.verts]
            for k in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[k].cross(vs[k + 1])) / 6.0
        if vol < 0.0:
            bmesh.ops.reverse_faces(bm, faces=island)
            flipped_islands += 1
    bm.to_mesh(me)
    bm.free()
    me.update()
    return flipped_islands


def cleanup_mesh(obj, merge_dist=0.0004):
    """Cift vertex, sifir alanli yuz ve gevsek geometri temizligi."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    before_v = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
    # sifir alanli yuzleri sil
    degen = [f for f in bm.faces if f.calc_area() < 1e-9]
    if degen:
        bmesh.ops.delete(bm, geom=degen, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.dissolve_degenerate(bm, dist=merge_dist * 0.5, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    after_v = len(bm.verts)
    bm.to_mesh(me)
    bm.free()
    # Blender'in kendi gecerlilik onarimi (glTF "not valid" uyarisini kapatir)
    me.validate(verbose=False, clean_customdata=False)
    me.update()
    return before_v - after_v, len(degen)


def add_lightmap_uv(obj, name="UV1_Lightmap"):
    """Ikinci UV kanali (lightmap / ek bake icin), cakismasiz."""
    me = obj.data
    if name in me.uv_layers:
        return
    me.uv_layers.new(name=name)
    me.uv_layers.active = me.uv_layers[name]
    prev = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = obj
    only_select([obj])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    try:
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.006,
                                 correct_aspect=True, scale_to_bounds=True)
    except Exception as exc:
        print("  ! lightmap UV uyarisi:", exc)
    bpy.ops.object.mode_set(mode='OBJECT')
    me.uv_layers.active = me.uv_layers[0]
    for i, l in enumerate(me.uv_layers):
        l.active_render = (i == 0)
    bpy.context.view_layer.objects.active = prev


def shade_smooth_with_split(obj, angle_deg=42.0):
    """Yumusak golgeleme + sert kenarlarda split normal."""
    me = obj.data
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(angle_deg))
    except AttributeError:
        prev = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        only_select([obj])
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))
        bpy.context.view_layer.objects.active = prev


# ==================================================================
# LOD
# ==================================================================
def make_lods(base_obj, arm, targets=C.LOD_TARGETS):
    out = [(targets[0][0], base_obj)]
    src_tris = tri_count(base_obj)
    print("  LOD0 ucgen:", src_tris)
    for name, target in targets[1:]:
        dup = base_obj.copy()
        dup.data = base_obj.data.copy()
        dup.name = "Dragon_" + name
        dup.data.name = "Dragon_" + name + "_mesh"
        bpy.context.collection.objects.link(dup)
        ratio = min(1.0, max(0.01, target / max(src_tris, 1)))
        m = dup.modifiers.new("Decimate", 'DECIMATE')
        m.decimate_type = 'COLLAPSE'
        m.ratio = ratio
        m.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = dup
        bpy.ops.object.modifier_apply(modifier=m.name)
        # decimate sonrasi dejenere geometri temizligi (glTF "not valid" uyarisi)
        cleanup_mesh(dup, merge_dist=0.0006)
        # armature modifier'i yeniden bagla
        am = dup.modifiers.new("Armature", 'ARMATURE')
        am.object = arm
        dup.parent = arm
        print("  %s ucgen: %d (hedef %d)" % (name, tri_count(dup), target))
        out.append((name, dup))
    return out


def make_mobile(base_obj, arm, target=C.MOBILE_TARGET):
    dup = base_obj.copy()
    dup.data = base_obj.data.copy()
    dup.name = "Dragon_Mobile"
    dup.data.name = "Dragon_Mobile_mesh"
    bpy.context.collection.objects.link(dup)
    src = tri_count(base_obj)
    m = dup.modifiers.new("Decimate", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = min(1.0, target / max(src, 1))
    m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = dup
    bpy.ops.object.modifier_apply(modifier=m.name)
    cleanup_mesh(dup, merge_dist=0.0006)
    am = dup.modifiers.new("Armature", 'ARMATURE')
    am.object = arm
    dup.parent = arm
    print("  Mobile ucgen:", tri_count(dup))
    return dup


# ==================================================================
# CARPISMA PROXY'LERI
# ==================================================================
def _capsule(name, a, b, r, segs=8, mat=None):
    """Dusuk poligonlu, konveks kapsul benzeri prizma."""
    a, b = Vector(a), Vector(b)
    d = (b - a)
    L = d.length
    if L < 1e-5:
        d = Vector((0.0, 1.0, 0.0))
        L = 1.0
    d = d.normalized()
    up = Vector((0.0, 1.0, 0.0))
    x = d.cross(up)
    if x.length < 1e-4:
        x = d.cross(Vector((1.0, 0.0, 0.0)))
    x.normalize()
    y = d.cross(x).normalized()
    verts, faces = [], []
    a2 = a - d * (r * 0.55)
    b2 = b + d * (r * 0.55)
    for k, ctr in enumerate((a2, a2 + d * (L * 0.5 + r * 0.55), b2)):
        rr = r if k == 1 else r * 0.62
        for i in range(segs):
            th = 2.0 * math.pi * i / segs
            verts.append(ctr + x * (rr * math.cos(th)) + y * (rr * math.sin(th)))
    top = len(verts)
    verts.append(a2 - d * (r * 0.35))
    bot = len(verts)
    verts.append(b2 + d * (r * 0.35))
    for ring in (0, 1):
        for i in range(segs):
            j = (i + 1) % segs
            faces.append((ring * segs + i, ring * segs + j,
                          (ring + 1) * segs + j, (ring + 1) * segs + i))
    for i in range(segs):
        j = (i + 1) % segs
        faces.append((top, j, i))
        faces.append((bot, 2 * segs + i, 2 * segs + j))
    me = bpy.data.meshes.new(name)
    me.from_pydata([v[:] for v in verts], [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    recalc_normals(obj)
    return obj


def build_collision(bonedefs, spine, wings, mat):
    """Sartnamede istenen adlarla konveks, dusuk maliyetli proxy parcalari."""
    d = {b.name: b for b in bonedefs}
    parts = []
    spec = [
        ("Head_Collision",      d["Head"].head,     d["Head"].tail,     0.62),
        ("Neck_Collision",      d["Neck_04"].tail,  d["Neck_01"].head,  0.62),
        ("Chest_Collision",     d["Chest"].tail,    d["Spine_02"].head, 1.28),
        ("Pelvis_Collision",    d["Spine_01"].tail, d["Pelvis"].head,   1.10),
        ("Tail_Collision_01",   d["Tail_01"].head,  d["Tail_03"].head,  0.66),
        ("Tail_Collision_02",   d["Tail_03"].head,  d["Tail_05"].head,  0.44),
        ("Tail_Collision_03",   d["Tail_05"].head,  d["Tail_Tip"].tail, 0.24),
        ("FrontLeg_Collision_L", d["Shoulder_L"].head, d["FrontFoot_L"].tail, 0.40),
        ("FrontLeg_Collision_R", d["Shoulder_R"].head, d["FrontFoot_R"].tail, 0.40),
        ("RearLeg_Collision_L", d["Hip_L"].head,    d["RearFoot_L"].tail, 0.48),
        ("RearLeg_Collision_R", d["Hip_R"].head,    d["RearFoot_R"].tail, 0.48),
    ]
    for name, a, b, r in spec:
        parts.append(_capsule(name, a, b, r, segs=8, mat=mat))
    for sfx in ("L", "R"):
        sk = wings[sfx]
        tip = sk["origins"][0] + sk["dirs"][0] * sk["lens"][0]
        parts.append(_capsule("Wing_Collision_" + sfx, sk["shoulder"], tip,
                              0.85, segs=6, mat=mat))
    root = bpy.data.objects.new("Dragon_Collision", None)
    bpy.context.collection.objects.link(root)
    for p in parts:
        p.parent = root
        p.hide_render = True
        p.display_type = 'WIRE'
    return root, parts


def build_shadow_proxy(base_obj, target=3000):
    dup = base_obj.copy()
    dup.data = base_obj.data.copy()
    dup.name = "Dragon_ShadowProxy"
    dup.data.name = "Dragon_ShadowProxy_mesh"
    bpy.context.collection.objects.link(dup)
    dup.parent = None
    for m in list(dup.modifiers):
        dup.modifiers.remove(m)
    src = tri_count(base_obj)
    m = dup.modifiers.new("Decimate", 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = min(1.0, target / max(src, 1))
    m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = dup
    bpy.ops.object.modifier_apply(modifier=m.name)
    cleanup_mesh(dup, merge_dist=0.0008)
    return dup


# ==================================================================
# EXPORT
# ==================================================================
def _export(filepath, objs, fmt='GLB', anims=True):
    only_select(objs)
    kwargs = dict(
        filepath=filepath,
        export_format=fmt,
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_texcoords=True,
        export_normals=True,
        export_tangents=True,
        export_materials='EXPORT',
        export_skins=True,
        export_morph=True,
        export_cameras=False,
        export_lights=False,
        export_extras=False,
        export_animations=anims,
    )
    if anims:
        kwargs.update(dict(
            export_animation_mode='ACTIONS',
            export_bake_animation=False,
            export_optimize_animation_size=False,
            export_anim_single_armature=True,
            export_current_frame=False,
            export_frame_range=False,
        ))
    if fmt == 'GLTF_SEPARATE':
        kwargs["export_keep_originals"] = False
        kwargs["export_texture_dir"] = "textures"
    # Blender surumu tanimayan parametreleri ele
    import inspect
    valid = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    kwargs = {k: v for k, v in kwargs.items() if k in valid}
    bpy.ops.export_scene.gltf(**kwargs)
    return filepath
