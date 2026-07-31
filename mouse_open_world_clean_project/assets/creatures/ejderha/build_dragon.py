"""Uretim ejderhasi - tek komutla tam pipeline.

Kullanim:
    blender --background --python build_dragon.py -- [--no-anim] [--no-lod]
                                                     [--quick] [--seed N]

Uretilenler (bu klasore):
    dragon_master.glb / .gltf + .bin + textures/
    dragon_lod1..4.glb, dragon_mobile.glb, dragon_collision.glb,
    dragon_shadowproxy.glb, dragon.blend, qa_report.txt, stats.json
"""

import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
import bmesh
from mathutils import Vector, Matrix

from dragon import config as C
from dragon import core, uvmap, body, head, limbs, wings, details
from dragon import textures, materials, rig, anim, pipeline
from dragon.core import MeshBuilder, Spine, TAU

T0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - T0, msg))
    sys.stdout.flush()


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    opt = {"anim": True, "lod": True, "quick": False, "seed": C.SEED,
           "render": True}
    for i, a in enumerate(argv):
        if a == "--no-anim":
            opt["anim"] = False
        elif a == "--no-lod":
            opt["lod"] = False
        elif a == "--no-render":
            opt["render"] = False
        elif a == "--quick":
            opt["quick"] = True
        elif a == "--seed":
            opt["seed"] = int(argv[i + 1])
    return opt


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scn = bpy.context.scene
    scn.unit_settings.system = 'METRIC'
    scn.unit_settings.scale_length = 1.0
    scn.render.fps = C.FPS


# ==================================================================
# OLCEK: omuz tepesi 4.5 m olacak sekilde omurgayi konumla
# ==================================================================
def place_spine(spine):
    best = -1e9
    for i in range(60):
        s = 0.330 + 0.140 * i / 59.0
        for j in range(40):
            phi = -math.radians(55.0) + math.radians(110.0) * j / 39.0
            p = body.surface_point(spine, s, phi if phi >= 0 else TAU + phi)
            best = max(best, p.y)
    spine.translate(Vector((0.0, C.SHOULDER_HEIGHT - best, 0.0)))
    # Z: karakter kok noktasi on/arka bacak arasinda, zeminde olsun
    spine.translate(Vector((0.0, 0.0, -spine.pos(0.472).z)))
    return best


# ==================================================================
# KAFA <-> BOYUN GECISI (bogaz)
# ==================================================================
def bridge_head_neck(mb, spine, body_res, head_res):
    """Kafa arka halkasi ile govde on halkasini yumusak gecisle kaynatir."""
    mat_head = mb.mat("M_Dragon_Head")
    mat_mouth = mb.mat("M_Dragon_Mouth")
    r_skull = uvmap.HEAD["skull"]
    r_throat = uvmap.MOUTH["throat"]

    a = head_res["rear_ring"]          # 64 vertex, index 0 = tepe
    b = body_res["front_ring"]         # 64 vertex, index 0 = tepe
    n = len(a)
    assert n == len(b), "kafa/boyun halka sayisi esit degil"

    steps = 5
    loops = [a]
    for k in range(1, steps):
        f = k / steps
        ring = []
        for i in range(n):
            pa = mb.verts[a[i]]
            pb = mb.verts[b[i]]
            p = pa.lerp(pb, f)
            # bogaz bolgesinde hafif sisme (kas)
            s_mid = core.lerp(C.S_HEAD_END, body.S_BODY_START, f)
            ctr = spine.pos(s_mid)
            d = p - ctr
            if d.length > 1e-6:
                p = ctr + d * (1.0 + 0.05 * math.sin(math.pi * f))
            ring.append(mb.add_vert(p, "body"))
        loops.append(ring)
    loops.append(b)

    palate = set(range(22, 43))         # damak/bogaz kolonlari
    for k in range(len(loops) - 1):
        A, Bl = loops[k], loops[k + 1]
        v0 = k / (len(loops) - 1)
        v1 = (k + 1) / (len(loops) - 1)
        for i in range(n):
            j = (i + 1) % n
            in_throat = (i in palate and j in palate)
            rect = r_throat if in_throat else r_skull
            mat = mat_mouth if in_throat else mat_head
            u0, u1 = rect[0], rect[2]
            fu0 = u0 + (u1 - u0) * (i / n)
            fu1 = u0 + (u1 - u0) * ((i + 1) / n)
            fv0 = rect[1] + (rect[3] - rect[1]) * v0
            fv1 = rect[1] + (rect[3] - rect[1]) * v1
            mb.add_face((A[i], A[j], Bl[j], Bl[i]),
                        ((fu0, fv0), (fu1, fv0), (fu1, fv1), (fu0, fv1)), mat)


# ==================================================================
# QA
# ==================================================================
def qa_check(obj, arm, order, vals, names):
    rep = []
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    non_manifold_e = sum(1 for e in bm.edges if not e.is_manifold)
    boundary_e = sum(1 for e in bm.edges if e.is_boundary)
    wire_e = sum(1 for e in bm.edges if e.is_wire)
    loose_v = sum(1 for v in bm.verts if not v.link_edges)
    zero_f = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    quads = sum(1 for f in bm.faces if len(f.verts) == 4)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)

    # asiri ince ucgen tespiti
    thin = 0
    for f in bm.faces:
        if len(f.verts) != 3:
            continue
        a, b, c = [v.co for v in f.verts]
        e = sorted([(b - a).length, (c - b).length, (a - c).length])
        if e[0] > 1e-9 and e[2] / e[0] > 22.0:
            thin += 1

    # normal yonu: hacim testi
    vol = 0.0
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        for k in range(1, len(vs) - 1):
            vol += vs[0].dot(vs[k].cross(vs[k + 1])) / 6.0

    bbox_min = Vector((1e9, 1e9, 1e9))
    bbox_max = Vector((-1e9, -1e9, -1e9))
    for v in bm.verts:
        for i in range(3):
            bbox_min[i] = min(bbox_min[i], v.co[i])
            bbox_max[i] = max(bbox_max[i], v.co[i])
    bm.free()

    # sinir (boundary) kenarlarini materyale gore raporla -> kaynak tespiti
    bm2 = bmesh.new()
    bm2.from_mesh(me)
    bm2.edges.ensure_lookup_table()
    slot_names = [m.name if m else "?" for m in obj.data.materials]
    bnd_by_mat = {}
    for e in bm2.edges:
        if e.is_boundary:
            for f in e.link_faces:
                n = slot_names[f.material_index] if f.material_index < len(slot_names) else "?"
                bnd_by_mat[n] = bnd_by_mat.get(n, 0) + 1
    bm2.free()

    wsum = vals.sum(axis=1)
    unweighted = int((wsum < 1e-6).sum())
    max_infl = int((vals > 1e-5).sum(axis=1).max())

    rep.append("GEOMETRI")
    rep.append("  ucgen           : %d" % tris)
    rep.append("  quad / ngon     : %d / %d" % (quads, ngons))
    rep.append("  vertex          : %d" % len(me.vertices))
    rep.append("  non-manifold edge: %d" % non_manifold_e)
    rep.append("  acik (boundary) edge: %d" % boundary_e)
    rep.append("  wire edge / loose vertex: %d / %d" % (wire_e, loose_v))
    rep.append("  sifir alanli yuz: %d" % zero_f)
    rep.append("  asiri ince ucgen (oran>22): %d" % thin)
    rep.append("  imzali hacim (>0 = normaller disa): %.3f m3" % vol)
    if bnd_by_mat:
        rep.append("  acik kenar dagilimi: %s" % ", ".join(
            "%s=%d" % (k, v) for k, v in sorted(bnd_by_mat.items(),
                                                key=lambda x: -x[1])))
    rep.append("")
    rep.append("OLCU")
    rep.append("  bbox min: (%.3f, %.3f, %.3f)" % tuple(bbox_min))
    rep.append("  bbox max: (%.3f, %.3f, %.3f)" % tuple(bbox_max))
    rep.append("  genislik X (kanat aciklik, bind poz): %.2f m" % (bbox_max.x - bbox_min.x))
    rep.append("  yukseklik Y: %.2f m" % (bbox_max.y - bbox_min.y))
    rep.append("  uzunluk Z  : %.2f m" % (bbox_max.z - bbox_min.z))
    rep.append("  zemin (min Y): %.4f m" % bbox_min.y)
    rep.append("")
    rep.append("RIG")
    rep.append("  kemik sayisi    : %d" % len(arm.data.bones))
    rep.append("  agirliksiz vertex: %d" % unweighted)
    rep.append("  vertex basina max kemik: %d" % max_infl)
    rep.append("  agirlik toplami min/max: %.4f / %.4f" % (wsum.min(), wsum.max()))
    rep.append("")
    rep.append("UV")
    rep.append("  UV kanali sayisi: %d" % len(me.uv_layers))
    rep.append("  kanallar        : %s" % ", ".join(l.name for l in me.uv_layers))
    rep.append("  materyal slotu  : %d (%s)" % (
        len(obj.data.materials), ", ".join(m.name for m in obj.data.materials)))
    return rep, {
        "tris": tris, "verts": len(me.vertices),
        "non_manifold": non_manifold_e, "boundary": boundary_e,
        "zero_area": zero_f, "thin_tris": thin, "volume": vol,
        "bbox_min": list(bbox_min), "bbox_max": list(bbox_max),
        "bones": len(arm.data.bones), "unweighted": unweighted,
        "max_influences": max_infl,
    }


# ==================================================================
# ONIZLEME RENDER
# ==================================================================
def render_previews(out_dir, target_objs, arm):
    os.makedirs(out_dir, exist_ok=True)
    scn = bpy.context.scene
    scn.render.engine = 'BLENDER_EEVEE_NEXT'
    scn.render.resolution_x = 900
    scn.render.resolution_y = 1150
    scn.render.film_transparent = False
    scn.view_settings.view_transform = 'Standard'
    scn.view_settings.look = 'None'
    scn.view_settings.exposure = 0.55
    try:
        scn.eevee.taa_render_samples = 24
    except Exception:
        pass

    world = bpy.data.worlds.new("W")
    scn.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.16, 0.165, 0.19, 1.0)
    bg.inputs[1].default_value = 1.0

    # zemin
    bpy.ops.mesh.primitive_plane_add(size=120, location=(0, -0.004, 0))
    floor = bpy.context.active_object
    fm = bpy.data.materials.new("Floor")
    fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.16, 0.16, 0.17, 1)
    fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.72
    floor.data.materials.append(fm)

    # --- gunes tabanli 3 noktali isik (koyu pullu deri icin yuksek sonme) ---
    def sun(name, energy, elev, azim, angle=0.06):
        d = bpy.data.lights.new(name, 'SUN')
        d.energy = energy
        d.angle = angle
        o = bpy.data.objects.new(name, d)
        scn.collection.objects.link(o)
        v = Vector((math.cos(math.radians(elev)) * math.sin(math.radians(azim)),
                    math.sin(math.radians(elev)),
                    math.cos(math.radians(elev)) * math.cos(math.radians(azim))))
        o.rotation_euler = (-v).to_track_quat('-Z', 'Y').to_euler()
        return o

    sun("Key", 7.5, 46.0, 214.0, angle=0.10)
    sun("Fill", 2.4, 22.0, 60.0, angle=0.60)
    sun("Rim", 6.0, 30.0, 350.0, angle=0.08)

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 62
    cam_data.sensor_fit = 'HORIZONTAL'
    cam = bpy.data.objects.new("Cam", cam_data)
    scn.collection.objects.link(cam)
    scn.camera = cam

    key = bpy.data.lights.new("Key", 'AREA')
    key.energy = 26000
    key.size = 14
    ko = bpy.data.objects.new("Key", key)
    scn.collection.objects.link(ko)
    ko.location = (-14, 20, -18)
    ko.rotation_euler = (math.radians(52), math.radians(-16), math.radians(-32))

    fill = bpy.data.lights.new("Fill", 'AREA')
    fill.energy = 7000
    fill.size = 20
    fo = bpy.data.objects.new("Fill", fill)
    scn.collection.objects.link(fo)
    fo.location = (18, 11, 15)
    fo.rotation_euler = (math.radians(70), 0, math.radians(150))

    rim = bpy.data.lights.new("Rim", 'AREA')
    rim.energy = 16000
    rim.size = 10
    ro = bpy.data.objects.new("Rim", rim)
    scn.collection.objects.link(ro)
    ro.location = (8, 15, 24)
    ro.rotation_euler = (math.radians(104), 0, math.radians(20))

    # --- otomatik cerceveleme: gercek bbox'tan mesafe hesapla ---
    src = target_objs[0]
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for v in src.data.vertices:
        for i in range(3):
            mn[i] = min(mn[i], v.co[i])
            mx[i] = max(mx[i], v.co[i])
    center = (mn + mx) * 0.5
    radius = (mx - mn).length * 0.5
    fov = 2.0 * math.atan(18.0 / cam_data.lens)      # yatay FOV (36mm sensor)
    fit = radius / math.tan(fov * 0.5) * 0.80
    log("      cerceveleme: merkez (%.2f,%.2f,%.2f) yaricap %.2f mesafe %.1f"
        % (center.x, center.y, center.z, radius, fit))

    head_c = Vector((0.0, mx.y * 0.62, mn.z * 0.82))
    shots = [
        ("front",         180.0,  6.0, fit),
        ("three_quarter", 218.0, 11.0, fit),
        ("side",          270.0,  5.0, fit),
        ("back",            2.0,  9.0, fit),
        ("head_close",    212.0, 10.0, radius * 0.30),
        ("top",           215.0, 60.0, fit * 0.95),
        ("wing_detail",   246.0, 26.0, fit * 0.55),
        ("foot_detail",   196.0, -4.0, radius * 0.26),
    ]
    targets = {
        "head_close": head_c,
        "foot_detail": Vector((1.6, 0.8, mn.z * 0.30)),
        "wing_detail": Vector((mx.x * 0.55, mx.y * 0.62, 0.6)),
    }
    paths = []
    for name, yaw, pitch, dist in shots:
        tgt = targets.get(name, center)
        y = math.radians(yaw)
        p = math.radians(pitch)
        pos = tgt + Vector((math.sin(y) * math.cos(p), math.sin(p),
                            math.cos(y) * math.cos(p))) * dist
        # kamera matrisini ACIKCA kur: dunya +Y her zaman ekran yukarisi
        f = (tgt - pos).normalized()
        rgt = f.cross(Vector((0.0, 1.0, 0.0)))
        if rgt.length < 1e-5:
            rgt = f.cross(Vector((1.0, 0.0, 0.0)))
        rgt.normalize()
        upv = rgt.cross(f).normalized()
        cam.matrix_world = Matrix((
            (rgt.x, upv.x, -f.x, pos.x),
            (rgt.y, upv.y, -f.y, pos.y),
            (rgt.z, upv.z, -f.z, pos.z),
            (0.0, 0.0, 0.0, 1.0)))
        scn.render.filepath = os.path.join(out_dir, "preview_%s.png" % name)
        bpy.ops.render.render(write_still=True)
        paths.append(scn.render.filepath)
        log("  render: %s" % name)
    return paths


# ==================================================================
# ANA AKIS
# ==================================================================
def main():
    opt = parse_args()
    seed = opt["seed"]
    clear_scene()
    out = C.OUT_DIR
    os.makedirs(out, exist_ok=True)

    # ---------------- 1. omurga + olcek ----------------
    log("1/10  omurga egrisi + olcek")
    spine = Spine(C.SPINE_SEGMENTS)
    nat = place_spine(spine)
    log("      omurga yay uzunlugu: %.2f m, omuz tepesi -> %.2f m"
        % (spine.total, C.SHOULDER_HEIGHT))

    # ---------------- 2. dokular ----------------
    log("2/10  prosedurel PBR dokular (%d x %d)" % (C.TEX_SIZE, C.TEX_SIZE))
    tex = textures.generate_all(C.TEX_DIR, seed)
    mats = materials.build_all(tex)

    # ---------------- 3. geometri ----------------
    log("3/10  geometri insasi")
    mb = MeshBuilder("Dragon_LOD0")
    for name in C.MATERIALS:
        mb.mat(name)

    body_res = body.build_body(mb, spine, seed)
    log("      govde: %d vertex" % mb.vcount())
    head_res = head.build_head(mb, spine, seed)
    bridge_head_neck(mb, spine, body_res, head_res)
    jaw_res = head.build_jaw(mb, spine, seed)
    head.build_tongue(mb, spine, jaw_res)
    head.build_eyes(mb, spine)
    log("      kafa+cene: %d vertex" % mb.vcount())

    legs = limbs.build_all_legs(mb, spine, body_res["holes"], 0.0, seed)
    log("      bacaklar: %d vertex" % mb.vcount())
    wing_res = wings.build_wings(mb, spine, body_res["holes"], seed)
    log("      kanatlar: %d vertex" % mb.vcount())

    details.build_horns(mb, spine, seed)
    n_crest = details.build_crest(mb, spine, seed)
    details.build_neck_frill(mb, spine, n_crest, seed)
    details.build_teeth(mb, spine, jaw_res, seed)
    details.build_ventral_plates(mb, spine, seed)
    log("      detaylar: %d vertex, %d ucgen" % (mb.vcount(), mb.tri_count()))

    # ---------------- 4. Blender nesnesi ----------------
    log("4/10  mesh olusturuluyor")
    obj = mb.to_object(mats)
    merged, degen = pipeline.cleanup_mesh(obj)
    flipped = pipeline.recalc_normals(obj)
    log("      normali duzeltilen kabuk (ada): %d" % flipped)
    pipeline.shade_smooth_with_split(obj, 42.0)
    log("      birlestirilen vertex: %d, silinen dejenere yuz: %d" % (merged, degen))
    log("      LOD0: %d ucgen" % pipeline.tri_count(obj))

    # ---------------- 5. UV1 lightmap ----------------
    log("5/10  ikinci UV kanali (lightmap)")
    if not opt["quick"]:
        pipeline.add_lightmap_uv(obj)

    # ---------------- 6. rig ----------------
    log("6/10  iskelet + skinning")
    landmarks = head.head_landmarks(spine)
    bonedefs = rig.build_skeleton(spine, legs, wing_res, jaw_res, landmarks)
    arm = rig.create_armature(bonedefs)
    order, vals, names = rig.compute_weights(mb, bonedefs, max_infl=4)
    rig.apply_weights(obj, order, vals, names)
    rig.bind(obj, arm)
    log("      %d kemik, %d vertex agirliklandirildi" % (len(bonedefs), len(mb.verts)))

    # ---------------- 7. animasyon ----------------
    clips = []
    if opt["anim"]:
        log("7/10  animasyon klipleri")
        clips = anim.bake_clips(arm, bonedefs, legs, 0.0, C.FPS, root_motion=True)
    else:
        log("7/10  animasyon atlandi")

    # ---------------- 8. LOD + proxy ----------------
    lods = [("LOD0", obj)]
    mobile = None
    if opt["lod"]:
        log("8/10  LOD zinciri + mobil + carpisma")
        lods = pipeline.make_lods(obj, arm)
        mobile = pipeline.make_mobile(obj, arm)
    coll_mat = bpy.data.materials.new("M_Dragon_Collision")
    coll_mat.diffuse_color = (0.1, 0.8, 0.3, 1.0)
    coll_root, coll_parts = pipeline.build_collision(bonedefs, spine, wing_res,
                                                     coll_mat)
    shadow = pipeline.build_shadow_proxy(obj, 3000)
    log("      collision: %d parca, shadow proxy: %d ucgen"
        % (len(coll_parts), pipeline.tri_count(shadow)))

    # ---------------- 9. QA ----------------
    log("9/10  kalite kontrol")
    obj.name = "Dragon_LOD0"
    obj.data.name = "Dragon_LOD0_mesh"
    arm.name = "Dragon_Skeleton"
    rep, stats = qa_check(obj, arm, order, vals, names)

    # kanat tam aciklik olcusu (bind pozdan bagimsiz, iskeletten)
    span = 0.0
    for sfx in ("L", "R"):
        sk = wing_res[sfx]
        tip = sk["origins"][0] + sk["dirs"][0] * sk["lens"][0]
        span += abs(tip.x)
    stats["wingspan_bind"] = stats["bbox_max"][0] - stats["bbox_min"][0]
    stats["spine_arclength"] = spine.total
    stats["shoulder_height"] = C.SHOULDER_HEIGHT
    stats["clips"] = [c[0] for c in clips]
    stats["lods"] = {n: pipeline.tri_count(o) for n, o in lods}
    if mobile:
        stats["mobile_tris"] = pipeline.tri_count(mobile)
    stats["shadow_tris"] = pipeline.tri_count(shadow)
    stats["collision_parts"] = [p.name for p in coll_parts]

    # ---------------- 10. export ----------------
    log("10/10 glTF 2.0 disa aktarim")
    main_objs = [obj, arm]
    pipeline._export(os.path.join(out, "dragon_master.glb"), main_objs,
                     'GLB', anims=opt["anim"])
    pipeline._export(os.path.join(out, "dragon_master.gltf"), main_objs,
                     'GLTF_SEPARATE', anims=opt["anim"])
    # LOD / mobil / golge: ORTAK textures klasorunu kullanan .gltf+.bin
    # (GLB olsalardi her biri 24 dokuyu tekrar gomerdi -> gereksiz ~200 MB)
    if opt["lod"]:
        for name, o in lods[1:]:
            pipeline._export(os.path.join(out, "dragon_%s.gltf" % name.lower()),
                             [o, arm], 'GLTF_SEPARATE', anims=False)
        pipeline._export(os.path.join(out, "dragon_mobile.gltf"), [mobile, arm],
                         'GLTF_SEPARATE', anims=opt["anim"])
    pipeline._export(os.path.join(out, "dragon_collision.glb"),
                     [coll_root] + coll_parts, 'GLB', anims=False)
    pipeline._export(os.path.join(out, "dragon_shadowproxy.gltf"), [shadow],
                     'GLTF_SEPARATE', anims=False)

    # rapor
    lines = ["EJDERHA - URETIM KALITE RAPORU",
             "=" * 62,
             "olusturma: %s" % time.strftime("%Y-%m-%d %H:%M"),
             "seed: %d" % seed, ""]
    lines += rep
    lines += ["", "LOD"]
    for n, t in stats["lods"].items():
        lines.append("  %-6s %8d ucgen" % (n, t))
    if mobile:
        lines.append("  %-6s %8d ucgen" % ("Mobile", stats["mobile_tris"]))
    lines.append("  %-6s %8d ucgen" % ("Shadow", stats["shadow_tris"]))
    lines += ["", "ANIMASYON (%d klip)" % len(clips)]
    for c in clips:
        lines.append("  %-22s %.2fs %s" % (c[0], c[1], "loop" if c[2] else "one-shot"))
    lines += ["", "CARPISMA PROXY (%d parca)" % len(coll_parts)]
    for p in coll_parts:
        lines.append("  " + p.name)
    with open(os.path.join(out, "qa_report.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    log("\n".join(lines))

    # blend kaydet
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "dragon.blend"))

    # onizleme
    if opt["render"]:
        log("onizleme render")
        for n, o in lods[1:]:
            o.hide_render = True
        if mobile:
            mobile.hide_render = True
        shadow.hide_render = True
        render_previews(os.path.join(out, "preview"), [obj], arm)
    log("BITTI (%.1f s)" % (time.time() - T0))


if __name__ == "__main__":
    main()
