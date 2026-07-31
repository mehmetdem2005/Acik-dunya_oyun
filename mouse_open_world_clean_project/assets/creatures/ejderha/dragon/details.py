"""Boynuzlar, sirt dikenleri, ense yelesi, disler, ventral plakalar.

Hepsi ayri kapali kabuklardir (sartname buna izin veriyor); kokleri deriye
gomulur ve tabanda genisleyerek dogal birlesme verir. Hicbiri tek bir kopyanin
olceklenmis tekrari degildir - her parcada boy/egim/asinma/kirik varyasyonu var.
"""

import math
from mathutils import Vector, Quaternion

from . import config as C
from . import uvmap
from . import head as H
from . import body as B
from .core import TAU, pchip, smoothstep, clamp, lerp, fbm3


def _rnd(i, salt, seed=C.SEED):
    h = (i * 2654435761 ^ salt * 40503 ^ seed * 2246822519) & 0x7FFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0x7FFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


# ==================================================================
# KERATIN PARCA (boynuz / diken / dis ortak uretici)
# ==================================================================
def build_keratin(mb, origin, direction, up_ref, length, base_r, rect, mat,
                  region, idx, curve=0.35, curve_dir=None, cols=12, steps=14,
                  ridges=5, flat=1.0, broken=0.0, sink=0.35, seed=C.SEED):
    """Kavisli, yivli, uca dogru asinmis keratin cikinti.

    sink: tabanin deriye gomulme orani (govdeyle dogal birlesme).
    broken: >0 ise uc kirik/kut biter.
    """
    d = Vector(direction).normalized()
    if curve_dir is None:
        cv = Vector(up_ref) - d * Vector(up_ref).dot(d)
        if cv.length < 1e-6:
            cv = Vector((0.0, 1.0, 0.0))
        cv = -cv.normalized()
    else:
        cv = Vector(curve_dir).normalized()
    r_ax = d.cross(cv)
    if r_ax.length < 1e-6:
        r_ax = d.cross(Vector((1.0, 0.0, 0.0)))
    r_ax.normalize()
    u_ax = d.cross(r_ax).normalized()

    start = Vector(origin) - d * (base_r * sink)
    tip_cut = 1.0 - broken * 0.28
    rings = []
    for k in range(steps + 1):
        t = (k / steps) * tip_cut
        ctr = start + d * (length * t) + cv * (length * curve * (t ** 2.05))
        # yaricap: tabanda genis etek, sonra hizli daralma
        r = base_r * ((1.0 - t) ** 0.78)
        r *= 1.0 + 0.55 * math.exp(-t / 0.10)          # taban eteklenmesi
        if broken > 0.0 and t > tip_cut - 0.06:
            r = max(r, base_r * 0.16 * broken)
        r = max(r, base_r * 0.028)
        ring = []
        for i in range(cols):
            th = TAU * i / cols
            # yivler (keratin cizgileri) + hafif dogal asimetri
            ridge = 1.0 + 0.085 * math.cos(th * ridges) * (1.0 - t * 0.6)
            asym = 1.0 + 0.045 * math.sin(th + idx * 1.7) * (1.0 - t)
            wear = 1.0 - 0.06 * fbm3(math.cos(th) * 2.0, math.sin(th) * 2.0,
                                     t * 6.0, octaves=2, seed=seed + idx * 13)
            rr = r * ridge * asym * wear
            ring.append(ctr + r_ax * (rr * math.cos(th) * flat)
                        + u_ax * (rr * math.sin(th)))
        rings.append(mb.add_ring_verts(ring, region))

    for j in range(steps):
        mb.bridge_loops(rings[j], rings[j + 1],
                        (rect[0], rect[1] + (rect[3] - rect[1]) * j / steps,
                         rect[2], rect[1] + (rect[3] - rect[1]) * (j + 1) / steps),
                        mat)
    mb.cap_ring(rings[0], start - d * (base_r * 0.30), (0.5, 0.03), rect, mat, region)
    tipc = start + d * (length * tip_cut * 1.02) + cv * (length * curve * (tip_cut ** 2.05) * 1.02)
    mb.cap_ring(rings[-1], tipc, (0.5, 0.97), rect, mat, region, flip=True)


# ==================================================================
# BOYNUZLAR
# ==================================================================
def build_horns(mb, spine, seed=C.SEED):
    mat = mb.mat("M_Dragon_Horns_Claws")
    cell_i = 0
    groups = [("main", C.HORN_MAIN), ("cheek", C.HORN_CHEEK), ("nose", C.HORN_NOSE)]
    for side in (1.0, -1.0):
        for gname, spec in groups:
            for hi, (t, lat, L, pitch, yaw, roll, br, curv) in enumerate(spec):
                co, n = H.head_surface(spine, t, lat, side)
                p, right, up, tan = spine.frame(C.S_HEAD_END * (1.0 - t))
                back = tan.normalized()
                # yon: yuzey normalinden pitch kadar geriye, yaw kadar yana
                d = n.copy()
                q1 = Quaternion(right, math.radians(-pitch) * 1.0)
                d = (q1 @ d).normalized()
                q2 = Quaternion(up, math.radians(yaw) * side * -1.0)
                d = (q2 @ d).normalized()
                # geriye tarama (referanstaki geriye uzanan boynuzlar)
                d = (d + back * (0.42 if gname == "main" else 0.20)).normalized()
                # dogal varyasyon
                jitter = _rnd(hi, int(side) + 3, seed)
                Lv = L * (0.90 + 0.20 * jitter)
                brv = br * (0.92 + 0.16 * _rnd(hi, 7, seed))
                broken = 1.0 if (gname == "main" and hi == 3 and side < 0) else 0.0
                rect = uvmap.cell(uvmap.HORNS["horn_grid"], uvmap.HORN_CELLS, cell_i)
                build_keratin(mb, co, d, up, Lv, brv, rect, mat,
                              "horn_" + ("l" if side > 0 else "r"), cell_i,
                              curve=curv * (0.85 + 0.3 * jitter),
                              curve_dir=(back * 0.85 + up * 0.35).normalized(),
                              cols=14, steps=16, ridges=6,
                              broken=broken, sink=0.55, seed=seed)
                cell_i += 1


# ==================================================================
# SIRT DIKENLERI
# ==================================================================
def build_crest(mb, spine, seed=C.SEED):
    mat = mb.mat("M_Dragon_Horns_Claws")
    cfg = C.SPINE_CRest
    n = cfg["count"]
    cell_i = 0
    for i in range(n):
        f = i / (n - 1)
        s = lerp(cfg["s_start"], cfg["s_end"], f)
        hgt = pchip(cfg["height"], s)
        j1 = _rnd(i, 1, seed)
        j2 = _rnd(i, 2, seed)
        j3 = _rnd(i, 3, seed)
        L = hgt * (0.80 + 0.40 * j1)
        br = hgt * cfg["base_r_factor"] * (0.85 + 0.30 * j2)
        co = B.surface_point(spine, s, 0.0)
        p, right, up, tan = spine.frame(s)
        # geriye yatik, hafif yanal sapma
        back = tan.normalized()
        lean = 0.30 + 0.35 * f + 0.12 * j3
        lat = (j3 - 0.5) * 0.16
        d = (up + back * lean + right * lat).normalized()
        broken = 1.0 if j2 > 0.93 else 0.0
        rect = uvmap.cell(uvmap.HORNS["spike_grid"], uvmap.SPIKE_CELLS, cell_i)
        build_keratin(mb, co, d, up, L, br, rect, mat, "crest", cell_i,
                      curve=0.20 + 0.22 * j1,
                      curve_dir=(back * 0.9 + up * 0.1).normalized(),
                      cols=10, steps=9, ridges=4,
                      flat=0.62,             # yanlardan basik (bicak gibi)
                      broken=broken, sink=0.42, seed=seed)
        cell_i += 1
    return cell_i


def build_neck_frill(mb, spine, start_cell, seed=C.SEED):
    """Ense yelesi: referanstaki kalkan benzeri buyuk dikenler."""
    mat = mb.mat("M_Dragon_Horns_Claws")
    cfg = C.NECK_FRILL
    cell_i = start_cell
    for r in range(cfg["rows"]):
        fr = r / max(cfg["rows"] - 1, 1)
        s = lerp(cfg["s_start"], cfg["s_end"], fr)
        for side in (1.0, -1.0):
            for k in range(cfg["per_row"]):
                fk = (k + 1) / cfg["per_row"]
                yaw = lerp(cfg["yaw_range"][0], cfg["yaw_range"][1], fk)
                phi = math.radians(yaw) * side
                co = B.surface_point(spine, s, phi if side > 0 else TAU + phi)
                p, right, up, tan = spine.frame(s)
                nrm = (right * math.sin(phi) + up * math.cos(phi)).normalized()
                back = tan.normalized()
                jj = _rnd(r * 10 + k, int(side) + 5, seed)
                L = lerp(cfg["len_range"][0], cfg["len_range"][1], fk) \
                    * (1.0 - 0.35 * fr) * (0.82 + 0.36 * jj)
                br = L * 0.30
                d = (nrm * 0.55 + up * 0.45 + back * (0.55 + 0.25 * jj)).normalized()
                rect = uvmap.cell(uvmap.HORNS["spike_grid"], uvmap.SPIKE_CELLS, cell_i)
                build_keratin(mb, co, d, up, L, br, rect, mat, "frill", cell_i,
                              curve=0.26 + 0.18 * jj,
                              curve_dir=(back * 0.9 + up * 0.2).normalized(),
                              cols=10, steps=8, ridges=4, flat=0.58,
                              broken=1.0 if jj > 0.94 else 0.0,
                              sink=0.50, seed=seed)
                cell_i += 1
    return cell_i


# ==================================================================
# DISLER
# ==================================================================
def build_teeth(mb, spine, jaw, seed=C.SEED):
    mat = mb.mat("M_Dragon_Teeth")
    from .core import pchip_multi as _pm
    cfg = C.TEETH
    cell_i = 0
    t_joint = 0.115
    # --- ust cene disleri: dudak cizgisi boyunca, asagi bakar ---
    for side in (1.0, -1.0):
        for i in range(cfg["upper_count"]):
            f = (i + 0.5) / cfg["upper_count"]
            t = lerp(0.20, 0.965, f ** 0.92)
            co, n = H.head_surface(spine, t, 0.915, side)
            p, right, up, tan = spine.frame(C.S_HEAD_END * (1.0 - t))
            j1 = _rnd(i, int(side) + 11, seed)
            # koklerde uzun, arkada kisa; duzensiz dagilim
            base_l = lerp(cfg["len_range"][1], cfg["len_range"][0], f ** 0.7)
            L = base_l * (0.70 + 0.55 * j1)
            if i in (1, 4, 9):
                L *= 1.28                     # birkac uzun kopek disi
            # kapali agizda alt cenenin icinden tasmasin
            tj = clamp((t - t_joint) / (1.0 - t_joint), 0.0, 1.0)
            L = min(L, _pm(C.JAW_PROFILE, tj, 2) * 1.06 * 0.66)
            br = lerp(cfg["base_r_range"][1], cfg["base_r_range"][0], f ** 0.7) \
                * (0.85 + 0.30 * j1)
            d = (-up * 0.94 - n * 0.16 + tan * (0.08 - 0.16 * f)).normalized()
            rect = uvmap.cell(uvmap.TEETH["grid"], uvmap.TEETH_CELLS, cell_i)
            build_keratin(mb, co, d, up, L, br, rect, mat,
                          "teeth_u", cell_i, curve=0.16 + 0.14 * j1,
                          curve_dir=(tan * 0.8 + up * 0.2).normalized(),
                          cols=8, steps=7, ridges=3, flat=0.86,
                          broken=1.0 if j1 > 0.95 else 0.0, sink=0.62, seed=seed)
            cell_i += 1
    # --- alt cene disleri: cene ust arkinin dis kenarinda, yukari bakar ---
    origin, fwd, right, up = jaw["origin"], jaw["fwd"], jaw["right"], jaw["up"]
    from .core import pchip_multi
    for side in (1.0, -1.0):
        for i in range(cfg["lower_count"]):
            f = (i + 0.5) / cfg["lower_count"]
            t = lerp(0.16, 0.955, f ** 0.92)
            # alt disler de KAFANIN dudak cizgisine oturur (cene ile ayni egri)
            ht = t_joint + (1.0 - t_joint) * t
            lip = H.head_surface(spine, ht, 0.995, side)[0]
            mid = H.head_surface(spine, ht, 0.0, side)[0]
            inward = (mid - lip)
            inward = inward.normalized() if inward.length > 1e-6 else right * (-side)
            sp = spine.frame(C.S_HEAD_END * (1.0 - ht))
            up_l = sp[2]
            h = pchip_multi(C.JAW_PROFILE, t, 2) * 1.06
            co = lip + inward * (h * 0.22) - up_l * (h * 0.10)
            j1 = _rnd(i, int(side) + 23, seed)
            base_l = lerp(cfg["len_range"][1] * 0.90, cfg["len_range"][0], f ** 0.7)
            L = base_l * (0.70 + 0.55 * j1)
            if i in (2, 6):
                L *= 1.22
            # kapali agizda damagi delmesin
            ht = t_joint + (1.0 - t_joint) * t
            L = min(L, H.head_profile(ht, 3) * 0.70)
            br = lerp(cfg["base_r_range"][1], cfg["base_r_range"][0], f ** 0.7) \
                * (0.85 + 0.30 * j1)
            d = (up_l * 0.95 - inward * 0.18 - fwd * (0.08 - 0.16 * f)).normalized()
            rect = uvmap.cell(uvmap.TEETH["grid"], uvmap.TEETH_CELLS, cell_i)
            build_keratin(mb, co, d, up_l, L, br, rect, mat,
                          "teeth_l", cell_i, curve=0.16 + 0.14 * j1,
                          curve_dir=(-fwd * 0.8 + up_l * 0.2).normalized(),
                          cols=8, steps=7, ridges=3, flat=0.86,
                          broken=1.0 if j1 > 0.96 else 0.0, sink=0.62, seed=seed)
            cell_i += 1


# ==================================================================
# VENTRAL PLAKALAR
# ==================================================================
def build_ventral_plates(mb, spine, seed=C.SEED):
    """Cene altindan karina uzanan, ust uste binen buyuk plakalar."""
    mat = mb.mat("M_Dragon_Body")
    cfg = C.VENTRAL
    rect = uvmap.BODY["ventral"]
    n = cfg["count"]
    ds = (cfg["s_end"] - cfg["s_start"]) / n
    cols, rows = 9, 4
    for i in range(n):
        s0 = cfg["s_start"] + i * ds
        j1 = _rnd(i, 31, seed)
        j2 = _rnd(i, 37, seed)
        span = ds * cfg["overlap"] * (0.88 + 0.24 * j1)
        half = math.radians(cfg["half_angle"] * (0.80 + 0.40 * j2)
                            * (0.62 + 0.55 * smoothstep(0.14, 0.36, s0)))
        lift = cfg["lift"] * (0.75 + 0.5 * j1)
        pv0 = rect[1] + (rect[3] - rect[1]) * (i / n)
        pv1 = rect[1] + (rect[3] - rect[1]) * ((i + 1) / n)
        cell = (rect[0] + 0.002, pv0 + 0.0004, rect[2] - 0.002, pv1 - 0.0004)

        outer, inner = [], []
        for r in range(rows + 1):
            fr = r / rows
            s = clamp(s0 + span * fr, 0.0, 0.999)
            ro, ri = [], []
            for c in range(cols + 1):
                fc = c / cols
                ang = math.pi + (fc * 2.0 - 1.0) * half
                base = B.surface_point(spine, s, ang, detail=False)
                p, right, up, tan = spine.frame(s)
                nrm = (right * math.sin(ang) + up * math.cos(ang)).normalized()
                # arka kenara dogru kalkik (bindirme), yanlarda incelen
                edge = (1.0 - (2.0 * fc - 1.0) ** 4)
                rise = lift * (0.35 + 0.95 * fr ** 1.5) * edge
                wob = fbm3(fc * 4.0, fr * 3.0 + i * 0.7, 5.0, octaves=2,
                           seed=seed + 91) * 0.006
                ro.append(base + nrm * (rise + 0.010 + wob))
                ri.append(base + nrm * (-0.014))
            outer.append([mb.add_vert(q, "ventral") for q in ro])
            inner.append([mb.add_vert(q, "ventral") for q in ri])

        u0, v0, u1, v1 = cell
        for r in range(rows):
            for c in range(cols):
                fu0 = u0 + (u1 - u0) * (c / cols)
                fu1 = u0 + (u1 - u0) * ((c + 1) / cols)
                fv0 = v0 + (v1 - v0) * (r / rows)
                fv1 = v0 + (v1 - v0) * ((r + 1) / rows)
                uvq = ((fu0, fv0), (fu1, fv0), (fu1, fv1), (fu0, fv1))
                mb.add_face((outer[r][c], outer[r][c + 1],
                             outer[r + 1][c + 1], outer[r + 1][c]), uvq, mat)
                mb.add_face((inner[r + 1][c], inner[r + 1][c + 1],
                             inner[r][c + 1], inner[r][c]), uvq, mat)
        # kenar seridi (rim) -> kapali hacim
        def rim(a0, a1, b0, b1, uvq):
            # dikkat: (a0,a1,b0,b1) sirasi -> kelebek (bowtie) quad olusmaz,
            # plaka kenari gercekten kapanir
            mb.add_face((a0, a1, b0, b1), uvq, mat)
        e = ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
        for c in range(cols):
            rim(outer[0][c + 1], outer[0][c], inner[0][c], inner[0][c + 1], e)
            rim(outer[rows][c], outer[rows][c + 1], inner[rows][c + 1],
                inner[rows][c], e)
        for r in range(rows):
            rim(outer[r][0], outer[r + 1][0], inner[r + 1][0], inner[r][0], e)
            rim(outer[r + 1][cols], outer[r][cols], inner[r][cols],
                inner[r + 1][cols], e)
