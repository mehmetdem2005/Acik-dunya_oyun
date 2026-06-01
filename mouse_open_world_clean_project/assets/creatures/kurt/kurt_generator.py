"""Kurt (Canis lupus) — TAM GÖVDE prosedürel Blender modeli (sıfırdan).

Acik-dunya_oyun / hiper-realistik sinematik kurt hedefi. Hiçbir mesh import
EDİLMEZ (skill kuralı) — gövde, bacaklar, kuyruk, kafa, kulaklar bpy ile loft'lanır.

Bu dosya "kurt ustası" iteratif eleştiri-iyileştirme döngüsünün ÜZERİNDE çalıştığı
tabandır. Tüm şekil parametreleri `wolf_params.json`'dan okunur (yoksa buradaki
DEFAULTS kullanılır). Her tur bir ajan bu JSON'u (ve gerekirse kodu) düzeltir.

Koordinat: kurt -Y yönüne bakar (ön = -Y), yer z=0, yukarı = +Z, X = sağ/sol.

Çalıştırma (headless):
    blender --background --python kurt_generator.py -- \
        [--params wolf_params.json] [--render] [--save-blend] [--out-tag round_00]
"""

import argparse
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------
# DEFAULT PARAMETRELER (wolf_params.json ile override edilebilir)
# Her body istasyonu: [y, half_width, top_z (dorsal), bottom_z (ventral)]
# ------------------------------------------------------------------
DEFAULTS = {
    "ring_segments": 16,
    "subsurf": 2,
    "body_stations": [
        # y,     hw,    top_z, bot_z   etiket
        [-0.580, 0.050, 0.620, 0.555],   # nose_tip
        [-0.470, 0.072, 0.655, 0.545],   # muzzle
        [-0.350, 0.098, 0.700, 0.548],   # muzzle_base
        [-0.270, 0.120, 0.755, 0.560],   # stop/brow
        [-0.195, 0.130, 0.788, 0.585],   # occiput (kafa arkası)
        [-0.110, 0.140, 0.745, 0.490],   # neck_front
        [ 0.010, 0.185, 0.792, 0.430],   # neck_base
        [ 0.120, 0.240, 0.835, 0.360],   # withers (omuz tepe)
        [ 0.235, 0.250, 0.795, 0.300],   # chest (derin göğüs)
        [ 0.430, 0.225, 0.768, 0.345],   # back_mid
        [ 0.640, 0.190, 0.745, 0.410],   # waist (karın tuck)
        [ 0.830, 0.238, 0.782, 0.360],   # hip
        [ 0.985, 0.180, 0.742, 0.430],   # rump
        [ 1.090, 0.085, 0.700, 0.520],   # tail_base
    ],
    "ear": {
        "base": [0.105, -0.215, 0.792],  # x,y,z (sağ; sol mirror)
        "height": 0.165, "width": 0.095,
        "lean_out_deg": 14, "lean_back_deg": 8,
    },
    # bacak: [x, y_top, z_top, ayak_y, segment_radii...]  (digitigrade)
    "front_leg": {"x": 0.130, "y_top": 0.150, "z_top": 0.560,
                  "knee_y": 0.165, "knee_z": 0.330, "ankle_y": 0.120, "ankle_z": 0.140,
                  "paw_y": 0.150, "r_top": 0.090, "r_knee": 0.060, "r_ankle": 0.040, "r_paw": 0.050},
    "rear_leg": {"x": 0.150, "y_top": 0.840, "z_top": 0.560,
                 "knee_y": 0.760, "knee_z": 0.360, "hock_y": 0.910, "hock_z": 0.170,
                 "paw_y": 0.860, "r_top": 0.105, "r_knee": 0.070, "r_hock": 0.045, "r_paw": 0.052},
    "tail": {"segments": 7, "length": 0.62, "droop": 0.30, "base_r": 0.075, "tip_r": 0.018,
             "bush": 1.7},
    "material": {"fur_color": [0.20, 0.17, 0.14, 1.0], "roughness": 0.78},
}


def load_params(path):
    p = json.loads(json.dumps(DEFAULTS))  # deep copy
    if path and os.path.exists(path):
        user = json.loads(open(path).read())
        def merge(a, b):
            for k, v in b.items():
                if isinstance(v, dict) and isinstance(a.get(k), dict):
                    merge(a[k], v)
                else:
                    a[k] = v
        merge(p, user)
    return p


# ------------------------------------------------------------------
def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ring_xz(hw, top_z, bot_z, segments):
    """XZ düzleminde halka (gövde için, Y boyunca dizilir)."""
    vc = 0.5 * (top_z + bot_z); vh = 0.5 * (top_z - bot_z)
    pts = []
    for i in range(segments):
        th = 2 * math.pi * i / segments
        x = hw * math.sin(th)
        zu = math.cos(th)
        if zu < 0:
            zu *= 0.90
            x *= 1.0 + 0.18 * zu  # ventral (alt) hafif daralt: göğüs/karın keel (V) hissi
        pts.append((x, vc + vh * zu))
    return pts


def build_body(P, name="KurtGovde"):
    seg = P["ring_segments"]
    bm = bmesh.new()
    rings = []
    for st in P["body_stations"]:
        y, hw, tz, bz = st[0], st[1], st[2], st[3]
        ring = [bm.verts.new((x, y, z)) for (x, z) in ring_xz(hw, tz, bz, seg)]
        rings.append(ring)
    for r in range(len(rings) - 1):
        a, b = rings[r], rings[r + 1]
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    # ön kapak (burun) — uç merkezi hafif aşağı, burun topuzu (nose) hissi
    f = rings[0]; s0 = P["body_stations"][0]
    cf = bm.verts.new((0, s0[0] - 0.02, 0.5 * (s0[2] + s0[3]) - 0.022))
    for i in range(seg):
        bm.faces.new((f[(i + 1) % seg], f[i], cf))
    # arka kapak (kuyruk dibi)
    bk = rings[-1]; sN = P["body_stations"][-1]
    cb = bm.verts.new((0, sN[0], 0.5 * (sN[2] + sN[3])))
    for i in range(seg):
        bm.faces.new((bk[i], bk[(i + 1) % seg], cb))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    _brow_ridge(ob, P)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def _brow_ridge(ob, P):
    """Kafatası göz üstü (stop-occiput arası) bölgesine hafif kaş tümseği:
    üst-yan vertekleri hafif yukarı+dışa iter. Sadece kafa bölgesinde, ölçülü."""
    me = ob.data
    y_lo, y_hi = -0.260, -0.150        # stop..occiput arası (göz/kaş bölgesi)
    for v in me.vertices:
        if not (y_lo < v.co.y < y_hi):
            continue
        if v.co.z < 0.78:               # sadece üst yarı (kaş hizası ve üstü)
            continue
        ax = abs(v.co.x)
        if ax < 0.04:                   # tam tepe (orta) hafif, yanlar (kaş) belirgin
            continue
        # y profili: stop-occiput ortasında en güçlü
        ty = 1.0 - abs((v.co.y - 0.5 * (y_lo + y_hi)) / (0.5 * (y_hi - y_lo)))
        bump = 0.026 * ty
        v.co.z += bump * 0.5            # kaş hafif yukarı
        v.co.x += bump * 1.3 * (1.0 if v.co.x > 0 else -1.0)  # kaş dışa (göz üstü çıkıntı)
        v.co.y += 0.010 * ty            # kaş hafif öne (göz üstü kemer)
    return ob


def tube_along_points(points_radii, name, seg=12):
    """Polyline (xyz, r) listesinden konik tüp loft'lar (bacak/kuyruk)."""
    bm = bmesh.new()
    rings = []
    prev_u = None  # parallel transport: bir önceki halkanın u eksenini taşı (twist'i önler)
    for k, (c, r) in enumerate(points_radii):
        c = Vector(c)
        # eksen yönü (komşu noktalardan)
        if k == 0:
            axis = (Vector(points_radii[1][0]) - c)
        elif k == len(points_radii) - 1:
            axis = (c - Vector(points_radii[k - 1][0]))
        else:
            axis = (Vector(points_radii[k + 1][0]) - Vector(points_radii[k - 1][0]))
        axis.normalize()
        # eksene dik iki vektör — ilk halkada sabit referans, sonra parallel transport
        if prev_u is None:
            up = Vector((0, 0, 1))
            if abs(axis.dot(up)) > 0.95:
                up = Vector((0, 1, 0))
            u = axis.cross(up).normalized()
        else:
            # önceki u'yu yeni eksene dik düzleme yansıt (minimum dönme = twist yok)
            u = (prev_u - axis * prev_u.dot(axis))
            if u.length < 1e-6:
                up = Vector((0, 1, 0)) if abs(axis.dot(Vector((0, 0, 1)))) > 0.95 else Vector((0, 0, 1))
                u = axis.cross(up)
            u.normalize()
        v = axis.cross(u).normalized()
        prev_u = u
        ring = []
        for i in range(seg):
            th = 2 * math.pi * i / seg
            off = (u * math.cos(th) + v * math.sin(th)) * r
            ring.append(bm.verts.new(c + off))
        rings.append(ring)
    for rr in range(len(rings) - 1):
        a, b = rings[rr], rings[rr + 1]
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    # uç kapaklar
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(list(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def _paw_points(x, paw_y, r_paw, paw_len):
    """Ayak ucunda öne (-Y) uzanan yatay pati: bilek altı + topuk + öne uzanan parmak ucu."""
    plen = paw_len if paw_len is not None else 0.0
    return [
        ((x, paw_y, 0.075), r_paw * 0.86),            # bilek altı (metacarpus)
        ((x, paw_y - plen * 0.45, 0.030), r_paw),      # pati gövdesi (en geniş)
        ((x, paw_y - plen * 0.85, 0.026), r_paw * 0.95),  # parmak bölgesi (yuvarlak, dolgun)
        ((x, paw_y - plen, 0.024), r_paw * 0.70),      # ön kenar (hafif yuvarlatılmış, bloky)
    ]


def _flatten_paw(ob, z_thresh=0.095, floor=0.016, squash=0.38):
    """Pati bölgesini (z < z_thresh) yere yassılaştır: küre yerine düz taban verir."""
    me = ob.data
    for v in me.vertices:
        if v.co.z < z_thresh:
            v.co.z = floor + (v.co.z - floor) * squash
    return ob


def _toe_grooves(ob, paw_x, paw_y, r_paw, paw_len, n_toes=3, depth=0.030):
    """Pati ön (parmak) bölgesinde parmak araları olukları aç: tabanı X yönünde
    n_toes loba böler. Sadece patinin ön yarısında (y < paw_y - 0.3*paw_len) ve
    yere yakın (z düşük) vertekslere uygulanır; üst geometri etkilenmez."""
    me = ob.data
    y_front = paw_y - 0.30 * paw_len           # parmak bölgesinin başladığı y
    span = r_paw * 1.4                          # parmaklar X yönünde bu genişliğe yayılır
    for v in me.vertices:
        if v.co.z > 0.060:
            continue
        if v.co.y > y_front:                    # sadece ön (parmak) bölge
            continue
        xl = (v.co.x - paw_x)
        if abs(xl) > span:
            continue
        # ön bölgede normalize ilerleme (0=parmak başı, 1=ön kenar)
        t = min(1.0, (y_front - v.co.y) / max(1e-5, paw_len * 0.7))
        # X boyunca n_toes loblu kosinüs profili: oluk hatlarında 0, lob tepesinde 1
        u = (xl / span) * n_toes                # -n..+n
        groove = 0.5 * (1.0 + math.cos(2 * math.pi * u))  # 1 lob merkezi, 0 oluk
        # oluk derinliği parmak ucuna doğru artar
        v.co.z += depth * (1.0 - groove) * (-1.0) * t  # oluklarda tabanı hafif yukarı (girinti)
        # parmak uçlarını öne doğru uzat (lob tepelerinde), oluklarda geri çek
        v.co.y -= 0.045 * groove * t
        v.co.y += 0.018 * (1.0 - groove) * t
    return ob


def build_front_leg(P, side, name):
    L = P["front_leg"]; x = L["x"] * side
    pts = [
        ((x, L["y_top"], L["z_top"]), L["r_top"]),
        ((x, L["knee_y"], L["knee_z"]), L["r_knee"]),
        ((x, L["ankle_y"], L["ankle_z"]), L["r_ankle"]),
    ]
    pl = L.get("paw_len", 0.10)
    pts += _paw_points(x, L["paw_y"], L["r_paw"], pl)
    ob = _flatten_paw(tube_along_points(pts, name, seg=20))
    return _toe_grooves(ob, x, L["paw_y"], L["r_paw"], pl)


def build_rear_leg(P, side, name):
    L = P["rear_leg"]; x = L["x"] * side
    pts = [
        ((x, L["y_top"], L["z_top"]), L["r_top"]),
        ((x, L["knee_y"], L["knee_z"]), L["r_knee"]),
        ((x, L["hock_y"], L["hock_z"]), L["r_hock"]),
    ]
    pl = L.get("paw_len", 0.11)
    pts += _paw_points(x, L["paw_y"], L["r_paw"], pl)
    ob = _flatten_paw(tube_along_points(pts, name, seg=20))
    return _toe_grooves(ob, x, L["paw_y"], L["r_paw"], pl)


def build_tail(P, name="KurtKuyruk"):
    T = P["tail"]; n = T["segments"]
    base = P["body_stations"][-1]
    # Kuyruk dibini rumpa GÖMMEK için başlangıcı gövde içine (öne) ve yukarı al;
    # böylece kopuk muz görünümü yerine rumpla kaynaşan bir base oluşur.
    by = base[0] - 0.11
    bz = 0.5 * (base[2] + base[3]) + 0.05
    pts = []
    for i in range(n + 1):
        t = i / n
        y = by + (T["length"] + 0.11) * t
        # droop ile aşağı sarkar, son ~%30'da uç hafif yukarı kıvrılır (kurt kuyruğu)
        z = bz - T["droop"] * (t ** 1.25) + T.get("tip_lift", 0.0) * max(0.0, t - 0.75)
        r = (T["base_r"] * (1 - t) + T["tip_r"] * t) * (1 + (T["bush"] - 1) * math.sin(math.pi * min(t * 1.2, 1)))
        pts.append(((0.0, y, z), r))
    return tube_along_points(pts, name)


def build_ear(P, side, name):
    E = P["ear"]; bx, by, bz = E["base"]; bx *= side
    w = E["width"]; h = E["height"]
    lo = math.radians(E["lean_out_deg"]); lb = math.radians(E["lean_back_deg"])
    bm = bmesh.new()
    t = 0.025
    base = [
        bm.verts.new((bx - w * side, by - w * 0.6, bz)),
        bm.verts.new((bx + w * side, by - w * 0.4, bz)),
        bm.verts.new((bx + w * side, by + w * 0.6, bz + t)),
        bm.verts.new((bx - w * side, by + w * 0.4, bz + t)),
    ]
    tip = bm.verts.new((bx + math.sin(lo) * h * side, by + math.sin(lb) * h, bz + h))
    bm.faces.new((base[0], base[1], tip)); bm.faces.new((base[1], base[2], tip))
    bm.faces.new((base[2], base[3], tip)); bm.faces.new((base[3], base[0], tip))
    bm.faces.new((base[3], base[2], base[1], base[0]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def fur_material(P):
    M = P["material"]
    mat = bpy.data.materials.new("KurtFur"); mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = tuple(M["fur_color"])
    b.inputs["Roughness"].default_value = M["roughness"]
    return mat


def add_subsurf(ob, lvl):
    m = ob.modifiers.new("subsurf", "SUBSURF"); m.levels = lvl; m.render_levels = lvl


def build_wolf(P):
    parts = [build_body(P)]
    for s, sd in ((+1, "R"), (-1, "L")):
        parts.append(build_front_leg(P, s, f"KurtOnBacak_{sd}"))
        parts.append(build_rear_leg(P, s, f"KurtArkaBacak_{sd}"))
        parts.append(build_ear(P, s, f"KurtKulak_{sd}"))
    parts.append(build_tail(P))
    mat = fur_material(P)
    for ob in parts:
        ob.data.materials.append(mat)
        add_subsurf(ob, P["subsurf"])
    return parts


# ------------------------------------------------------------------
# RENDER — Cycles CPU çoklu açı (headless)
# ------------------------------------------------------------------
def setup_cycles(samples=40):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
    sc.cycles.samples = samples; sc.cycles.use_denoising = False
    sc.render.resolution_x = 900; sc.render.resolution_y = 700
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.05, 0.055, 0.07, 1.0); bg.inputs[1].default_value = 1.0


def add_lights():
    for loc, e, sz in (((2.2, -2.0, 2.4), 600, 1.6),
                       ((-2.2, -1.4, 1.0), 200, 2.0),
                       ((0.0, 2.6, 1.8), 320, 1.2)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        L = bpy.context.object; L.data.energy = e; L.data.size = sz


def render_views(tag):
    sc = bpy.context.scene
    aim = bpy.data.objects.new("aim", None); sc.collection.objects.link(aim)
    aim.location = (0, 0.25, 0.45)
    bpy.ops.object.camera_add(); cam = bpy.context.object; cam.data.lens = 50; sc.camera = cam
    c = cam.constraints.new("TRACK_TO"); c.target = aim
    c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
    d = 2.7
    views = {
        "side":    (d, 0.25, 0.55),
        "front":   (0.0, -d, 0.5),
        "three_q": (d * 0.7, -d * 0.7, 0.7),
        "top":     (0.0, 0.25, d),
        "rear_q":  (d * 0.7, d * 0.7, 0.7),
    }
    out = []
    os.makedirs(os.path.join(DIR, "renders"), exist_ok=True)
    for name, loc in views.items():
        cam.location = loc; bpy.context.view_layer.update()
        fp = os.path.join(DIR, "renders", f"{tag}_{name}.png")
        sc.render.filepath = fp; bpy.ops.render.render(write_still=True)
        out.append(fp); print("RENDERED", fp)
    return out


def report_stats(parts, tag):
    deps = bpy.context.evaluated_depsgraph_get(); total = 0
    for ob in parts:
        ev = ob.evaluated_get(deps); me = ev.to_mesh()
        tris = sum(len(p.vertices) - 2 for p in me.polygons); total += tris
        ev.to_mesh_clear()
    print(f"=== {tag}: {len(parts)} parça, {total} tri (subsurf) ===")
    return total


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--params", default=os.path.join(DIR, "wolf_params.json"))
    p.add_argument("--render", action="store_true")
    p.add_argument("--save-blend", action="store_true")
    p.add_argument("--out-tag", default="round_00")
    return p.parse_args(argv)


def main():
    a = parse_args()
    P = load_params(a.params)
    fresh_scene()
    parts = build_wolf(P)
    report_stats(parts, a.out_tag)
    if a.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIR, "kurt.blend"))
    if a.render:
        setup_cycles(); add_lights(); render_views(a.out_tag)


if __name__ == "__main__":
    main()
