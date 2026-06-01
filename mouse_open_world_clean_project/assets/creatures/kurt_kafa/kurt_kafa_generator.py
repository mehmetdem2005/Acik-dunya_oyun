"""Kurt (Canis lupus) kafa segmenti — sıfırdan prosedürel Blender modeli.

Acik-dunya_oyun için "agresif/yırtıcı" stilize-gerçekçi kurt kafası.
Hiçbir mesh import EDİLMEZ — her şey bpy ile sıfırdan kurulur (skill kuralı).

Hedef motor: Godot 4.6 mobil + Prisma 3D.
Stil: fotorealistik tabanlı, hafif agresif (geniş zigomatik, belirgin kaş, büyük canine).

Aşamalı (staged) üretim — her katman bir sonrakinin üstüne kurulur:
    L1  blockout   : enine kesit loft ile temel kafa hacmi + kulak + alt çene
    (L2+ sonraki katmanlarda eklenir: sculpt detay, retopo, UV, PBR, rig)

Çalıştırma (headless):
    blender --background --python kurt_kafa_generator.py -- \
        --stage L1 [--render] [--save-blend]

Render: Cycles CPU (denoise kapalı — apt build OIDN'siz), kamera origin'e track-to.
"""

import argparse
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

# ------------------------------------------------------------------
# CONFIG — anatomik spec (kafa uzunluğu = 1.0 birim, Y ekseni boyunca)
# Koordinat: -Y = burun (ön), +Y = ense (arka), X = sağ/sol, Z = yukarı
# L0 araştırmasından + kullanıcı "agresif/yırtıcı" seçiminden türetildi.
# ------------------------------------------------------------------
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

RING_SEGMENTS = 24  # her enine kesit halkasındaki vertex sayısı

# Boylamsal kesit istasyonları: (y, half_width, top_z, bottom_z, etiket)
# half_width : X yarı-genişlik (üstten görünüm = kama silüeti)
# top_z      : DORSAL hat — kafanın üst sırtı (snout düşük, stop'ta yükselir, kubbe)
# bottom_z   : VENTRAL hat — kafanın alt tabanı (üst dudak/damak hattı, ~yatay)
# Üst ve alt hattı AYRI kontrol etmek snout/stop/kafatası ayrışmasını sağlar.
# "agresif" ayar: geniş zigomatik, belirgin kaş çıkıntısı, keskin kama.
HEAD_STATIONS = [
    # y,      hw,    top_z,  bot_z,  label
    (-0.500, 0.050,  0.015, -0.045, "nose_tip"),    # burun pad ucu
    (-0.455, 0.072,  0.045, -0.060, "nostril"),      # burun delikleri
    (-0.350, 0.082,  0.060, -0.070, "muzzle_mid"),   # snout orta (ince, düşük, ~yatay)
    (-0.230, 0.098,  0.075, -0.082, "muzzle_base"),  # snout dibi
    (-0.090, 0.130,  0.135, -0.092, "stop"),         # STOP — dorsal sıçrar (alın kırılması)
    (-0.010, 0.175,  0.205, -0.100, "brow_eyes"),    # kaş çıkıntısı + göz bölgesi
    ( 0.110, 0.215,  0.235, -0.120, "zygomatic"),    # en geniş — elmacık/çene kası (agresif)
    ( 0.225, 0.180,  0.262, -0.105, "cranium"),      # beyin kutusu kubbesi (tepe)
    ( 0.380, 0.150,  0.205, -0.100, "occiput"),      # ense
    ( 0.500, 0.140,  0.150, -0.140, "neck_cut"),     # boyun bağlantı halkası
]

# Alt çene (mandible) — snout altına yaslı, menteşe arkada
JAW_HINGE_Y = 0.130      # menteşe ~ zigomatik/kulak dibi hizası

# Kulak (sivri, dik, üçgen) — agresif: uzun/dik
EAR_BASE = (0.120, 0.205, 0.200)   # x,y,z taban merkezi (sağ kulak; sol mirror)
EAR_HEIGHT = 0.360
EAR_WIDTH = 0.130
EAR_LEAN_OUT = math.radians(16)    # dışa açı
EAR_LEAN_BACK = math.radians(10)   # arkaya açı

SUBSURF_LEVEL = 2

# ------------------------------------------------------------------
# Yardımcılar
# ------------------------------------------------------------------

def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ring_profile(hw, top_z, bot_z, segments):
    """Bir enine kesit halkasının lokal vertex'leri (X-Z düzleminde).

    Üst (top_z) ve alt (bot_z) hattı ayrı alır → snout/kafatası ayrışır.
    Alt yarı (çene/ağız tarafı) hafif düzleştirilir (kurt kafası altta yassı).
    theta=0 üst (top_z), theta=pi alt (bot_z), yanlar ±hw.
    """
    vcenter = 0.5 * (top_z + bot_z)
    vhalf = 0.5 * (top_z - bot_z)
    verts = []
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        x = hw * math.sin(theta)
        z_unit = math.cos(theta)
        if z_unit < 0:          # alt yarıyı düzleştir
            z_unit *= 0.80
        z = vcenter + vhalf * z_unit
        verts.append(Vector((x, 0.0, z)))
    return verts


def build_head_loft(name="KurtKafa"):
    """HEAD_STATIONS'tan enine kesit loft mesh'i kurar (temiz quad topoloji)."""
    bm = bmesh.new()
    rings = []
    for (y, hw, top_z, bot_z, _label) in HEAD_STATIONS:
        ring = []
        for v in ring_profile(hw, top_z, bot_z, RING_SEGMENTS):
            bv = bm.verts.new((v.x, y, v.z))
            ring.append(bv)
        rings.append(ring)
    bm.verts.ensure_lookup_table()

    # halkaları quad'larla bağla
    for r in range(len(rings) - 1):
        a, b = rings[r], rings[r + 1]
        for i in range(RING_SEGMENTS):
            j = (i + 1) % RING_SEGMENTS
            bm.faces.new((a[i], a[j], b[j], b[i]))

    # ön kapak (burun ucu) — fan
    front = rings[0]
    nose_cz = 0.5 * (HEAD_STATIONS[0][2] + HEAD_STATIONS[0][3])
    cf = bm.verts.new((0.0, HEAD_STATIONS[0][0] - 0.02, nose_cz))
    for i in range(RING_SEGMENTS):
        j = (i + 1) % RING_SEGMENTS
        bm.faces.new((front[j], front[i], cf))

    # arka kapak (boyun kesiti) — fan
    back = rings[-1]
    neck_cz = 0.5 * (HEAD_STATIONS[-1][2] + HEAD_STATIONS[-1][3])
    cb = bm.verts.new((0.0, HEAD_STATIONS[-1][0], neck_cz))
    for i in range(RING_SEGMENTS):
        j = (i + 1) % RING_SEGMENTS
        bm.faces.new((back[i], back[j], cb))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    # smooth shading
    for p in me.polygons:
        p.use_smooth = True
    return ob


def build_ear(side_sign, name):
    """Sivri üçgen kulak (basit blockout: yassı 4-yan piramit)."""
    bx, by, bz = EAR_BASE
    bx *= side_sign
    bm = bmesh.new()
    # taban dörtgeni (X-Y düzlemi, kafatasına yaslı), Z kalınlığı ince
    w = EAR_WIDTH
    t = 0.030  # kalınlık
    base = [
        bm.verts.new((bx - w * side_sign, by - w * 0.6, bz)),
        bm.verts.new((bx + w * side_sign, by - w * 0.4, bz)),
        bm.verts.new((bx + w * side_sign, by + w * 0.6, bz + t)),
        bm.verts.new((bx - w * side_sign, by + w * 0.4, bz + t)),
    ]
    # tepe (sivri uç) — yukarı, dışa ve arkaya eğik
    tip = bm.verts.new((
        bx + math.sin(EAR_LEAN_OUT) * EAR_HEIGHT * side_sign,
        by + math.sin(EAR_LEAN_BACK) * EAR_HEIGHT,
        bz + EAR_HEIGHT,
    ))
    bm.faces.new((base[0], base[1], tip))
    bm.faces.new((base[1], base[2], tip))
    bm.faces.new((base[2], base[3], tip))
    bm.faces.new((base[3], base[0], tip))
    bm.faces.new((base[3], base[2], base[1], base[0]))  # taban
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def build_jaw(name="KurtCene"):
    """Alt çene blockout — snout altına yaslı kütle (rig'te jaw bone'a gidecek).

    Üst kenarı kafanın ventral hattına (~-0.08) değer, alt kenar çene/çıkıntı.
    Menteşe arkada (JAW_HINGE_Y), uca doğru daralır.
    """
    bm = bmesh.new()
    y_back = JAW_HINGE_Y
    y_front = -0.450
    def quad(yval, hw, zlo, zhi):
        return [
            bm.verts.new((-hw, yval, zlo)),
            bm.verts.new(( hw, yval, zlo)),
            bm.verts.new(( hw, yval, zhi)),
            bm.verts.new((-hw, yval, zhi)),
        ]
    # (y, hw, z_alt, z_üst) — üst kenar ventral hatta tuttur, alt kenar çene
    back = quad(y_back,   0.120, -0.105,  0.010)   # menteşe (kütleli)
    mid = quad(-0.150,    0.090, -0.130, -0.045)   # ramus orta
    front = quad(y_front, 0.050, -0.120, -0.072)   # çene ucu (chin)
    loops = [back, mid, front]
    for k in range(len(loops) - 1):
        a, b = loops[k], loops[k + 1]
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(tuple(reversed(back)))
    bm.faces.new(tuple(front))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def add_subsurf(ob, level):
    m = ob.modifiers.new("subsurf", "SUBSURF")
    m.levels = level
    m.render_levels = level
    return m


def clay_material(name="KurtClay", color=(0.52, 0.50, 0.48, 1.0)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.62
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    return mat


# ------------------------------------------------------------------
# L1 BLOCKOUT
# ------------------------------------------------------------------

def stage_L1():
    head = build_head_loft()
    jaw = build_jaw()
    ear_r = build_ear(+1.0, "KurtKulak_R")
    ear_l = build_ear(-1.0, "KurtKulak_L")

    mat = clay_material()
    for ob in (head, jaw, ear_r, ear_l):
        ob.data.materials.append(mat)
        add_subsurf(ob, 1 if ob is not head else SUBSURF_LEVEL)

    # tri sayısı raporu
    return [head, jaw, ear_r, ear_l]


# ------------------------------------------------------------------
# RENDER — Cycles CPU, çoklu açı (headless uyumlu)
# ------------------------------------------------------------------

def setup_cycles_cpu(samples=48):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.resolution_x = 800
    sc.render.resolution_y = 800
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    bgn = w.node_tree.nodes["Background"]
    bgn.inputs[0].default_value = (0.045, 0.05, 0.065, 1.0)
    bgn.inputs[1].default_value = 1.0


def add_lights():
    bpy.ops.object.light_add(type="AREA", location=(1.6, -1.4, 1.8))
    k = bpy.context.object
    k.data.energy = 320
    k.data.size = 1.2
    bpy.ops.object.light_add(type="AREA", location=(-1.6, -1.0, 0.8))
    f = bpy.context.object
    f.data.energy = 110
    f.data.size = 1.6
    bpy.ops.object.light_add(type="AREA", location=(0.0, 1.8, 1.4))
    r = bpy.context.object
    r.data.energy = 180
    r.data.size = 1.0


def render_views(tag):
    sc = bpy.context.scene
    target = bpy.data.objects.new("aim", None)
    sc.collection.objects.link(target)
    target.location = (0.0, 0.0, 0.02)
    bpy.ops.object.camera_add(location=(0, -1.6, 0.1))
    cam = bpy.context.object
    cam.data.lens = 55
    sc.camera = cam
    c = cam.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"

    d = 1.45
    # açı -> kamera konumu (origin'e bakar)
    positions = {
        "front":      (0.0, -d, 0.06),
        "side":       (d,  0.0, 0.06),
        "three_q":    (d * 0.72, -d * 0.72, 0.18),
        "top":        (0.0, -0.05, d),
        "muzzle":     (0.0, -d * 0.85, -0.05),
    }
    out = []
    for name, loc in positions.items():
        cam.location = loc
        bpy.context.view_layer.update()
        fp = os.path.join(OUT_DIR, "renders", f"{tag}_{name}.png")
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        sc.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        out.append(fp)
        print("RENDERED", fp)
    return out


def report_stats(objects, stage):
    deps = bpy.context.evaluated_depsgraph_get()
    total = 0
    lines = []
    for ob in objects:
        ev = ob.evaluated_get(deps)
        me = ev.to_mesh()
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        total += tris
        lines.append(f"  {ob.name:16s} {tris:7d} tri")
        ev.to_mesh_clear()
    print(f"\n=== {stage} TRI STATS ===")
    for l in lines:
        print(l)
    print(f"  {'TOPLAM':16s} {total:7d} tri (subsurf uygulanmış)\n")
    return total


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="L1")
    p.add_argument("--render", action="store_true")
    p.add_argument("--save-blend", action="store_true")
    return p.parse_args(argv)


def main():
    args = parse_args()
    fresh_scene()

    if args.stage == "L1":
        objs = stage_L1()
    else:
        raise SystemExit(f"Bilinmeyen stage: {args.stage}")

    report_stats(objs, args.stage)

    if args.save_blend:
        blend = os.path.join(OUT_DIR, "kurt_kafa.blend")
        bpy.ops.wm.save_as_mainfile(filepath=blend)
        print("SAVED", blend)

    if args.render:
        setup_cycles_cpu()
        add_lights()
        render_views(f"{args.stage.lower()}")


if __name__ == "__main__":
    main()
