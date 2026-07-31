"""Ana govde kabugu: boyun -> gogus -> pelvis -> kuyruk (tek manifold sweep).

Uzuv baglanti noktalarinda gercek DELIK acilir; delik sinir halkasi uzvun ilk
halkasi olarak yeniden kullanilir -> govde ile uzuv arasinda ic ice gecme yok,
gercek kaynak var.
"""

import math
from mathutils import Vector

from . import config as C
from . import uvmap
from .core import (TAU, pchip_multi, superellipse, smoothstep, clamp,
                   cyl_noise, fbm3, lerp)

# ------------------------------------------------------------------
# DELIK TANIMLARI  (grid indeksleri; 2*(satir+kolon) = 40 sinir vertex'i)
# ------------------------------------------------------------------
HOLES = {
    "wing_L":     {"rows": (62, 72),   "cols": (1, 11)},
    "wing_R":     {"rows": (62, 72),   "cols": (53, 63)},
    "legF_L":     {"rows": (73, 87),   "cols": (12, 18)},
    "legF_R":     {"rows": (73, 87),   "cols": (46, 52)},
    "legR_L":     {"rows": (133, 147), "cols": (12, 18)},
    "legR_R":     {"rows": (133, 147), "cols": (46, 52)},
}

# Kas sismeleri: (s, phi_derece, s_sigma, phi_sigma_derece, miktar_m)
MUSCLE_BULGES = [
    (0.360,  78.0, 0.045, 40.0,  0.20),   # omuz kasi L
    (0.360, -78.0, 0.045, 40.0,  0.20),   # omuz kasi R
    (0.345,  36.0, 0.040, 34.0,  0.14),   # kanat koku kabartisi L
    (0.345, -36.0, 0.040, 34.0,  0.14),
    (0.400,   0.0, 0.050, 55.0,  0.10),   # sirt / withers
    (0.412, 120.0, 0.055, 45.0,  0.13),   # gogus kafesi alt L
    (0.412,-120.0, 0.055, 45.0,  0.13),
    (0.560,  74.0, 0.048, 42.0,  0.22),   # kalca / but L
    (0.560, -74.0, 0.048, 42.0,  0.22),
    (0.588,  30.0, 0.040, 40.0,  0.10),   # sagri
    (0.588, -30.0, 0.040, 40.0,  0.10),
    (0.630,  90.0, 0.030, 50.0,  0.09),   # kuyruk taban kasi
    (0.630, -90.0, 0.030, 50.0,  0.09),
    (0.230, 180.0, 0.035, 60.0, -0.05),   # bogaz altinda hafif ceklik
    (0.150,  90.0, 0.022, 45.0,  0.06),   # ense kasi
    (0.150, -90.0, 0.022, 45.0,  0.06),
]

# Pul ailesi: (s_baslangic, s_bitis, kolon_frekans, satir_frekans, genlik)
SCALE_FAMILIES = [
    (0.119, 0.200, 2.6, 2.0, 0.0055),  # ense - kucuk sik pullar
    (0.200, 0.330, 1.9, 1.6, 0.0080),  # boyun - orta bindirmeli
    (0.330, 0.480, 1.15, 1.05, 0.0155),  # omuz/gogus - kalin zirh pullari
    (0.480, 0.600, 1.4, 1.3, 0.0110),  # bel
    (0.600, 0.780, 1.7, 1.6, 0.0080),  # kuyruk on
    (0.780, 1.000, 2.4, 2.4, 0.0040),  # kuyruk uc - kucuk yonlu
]


def scale_freqs(s):
    for a, b, fu, fv, amp in SCALE_FAMILIES:
        if a <= s <= b:
            return fu, fv, amp
    return 2.2, 2.1, 0.020


def scale_field(col_f, ring_f, s, seed=0):
    """Bindirmeli pul kabartisi. col_f: 0..1 cevre, ring_f: 0..1 uzunluk."""
    fu, fv, amp = scale_freqs(s)
    nu = C.BODY_COLS / 2.0 * fu * 0.5
    nv = C.BODY_RINGS / 4.0 * fv * 0.35
    u = col_f * nu
    v = ring_f * nv
    row = math.floor(v)
    # tek satirlarda yarim kaydirma -> bindirmeli dizilim
    uu = u + (0.5 if int(row) % 2 else 0.0)
    cu = uu - math.floor(uu) - 0.5
    cv = v - row - 0.5
    # boyut jitter (her pul birazcik farkli)
    jitter = _hash01(int(math.floor(uu)), int(row), seed)
    rr = math.sqrt((cu * 1.06) ** 2 + (cv * 1.34) ** 2) / (0.52 + jitter * 0.16)
    bump = max(0.0, 1.0 - rr * rr)
    bump = bump ** 0.62
    # arka kenari kalkik (bindirme hissi)
    lip = smoothstep(0.18, 0.48, cv) * (1.0 - smoothstep(0.48, 0.50, cv))
    return amp * (bump * 0.85 + lip * 0.55 * bump)


def _hash01(i, j, seed):
    h = (i * 73856093 ^ j * 19349663 ^ seed * 83492791) & 0x7FFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0x7FFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def body_radius(s):
    w = pchip_multi(C.BODY_PROFILE, s, 1)
    h = pchip_multi(C.BODY_PROFILE, s, 2)
    bf = pchip_multi(C.BODY_PROFILE, s, 3)
    ex = pchip_multi(C.BODY_PROFILE, s, 4)
    return w, h, bf, ex


S_BODY_START = 0.150   # boyun tupunun on ucu; 0.11875-0.150 arasi kafa gecis halkalari


def ring_s(i):
    return S_BODY_START + (1.0 - S_BODY_START) * i / C.BODY_RINGS


def surface_point(spine, s, phi, detail=True, seed=0):
    """Govde yuzeyinde tek nokta + normal tahmini."""
    p, right, up, tan = spine.frame(s)
    w, h, bf, ex = body_radius(s)
    x, y = superellipse(phi, w, h, ex, belly_flat=bf)

    if detail:
        # kas sismeleri
        deg = math.degrees(phi)
        if deg > 180.0:
            deg -= 360.0
        bulge = 0.0
        for bs, bphi, ss, sp, amt in MUSCLE_BULGES:
            dd = deg - bphi
            while dd > 180.0:
                dd -= 360.0
            while dd < -180.0:
                dd += 360.0
            g = math.exp(-0.5 * ((s - bs) / ss) ** 2) * math.exp(-0.5 * (dd / sp) ** 2)
            bulge += amt * g
        # sirt keli (dorsal ridge)
        ridge = 0.055 * math.exp(-0.5 * (deg / 12.0) ** 2) * smoothstep(0.12, 0.20, s)
        # organik yuzey dalgalanmasi
        wob = cyl_noise(phi, s, 2.0, 26.0, octaves=3, seed=seed + 11) * 0.016
        wob += cyl_noise(phi, s, 5.0, 70.0, octaves=2, seed=seed + 29) * 0.007
        grow = 1.0 + (bulge + ridge + wob) / max(0.25, (abs(x) + abs(y)) * 0.5 + 0.15)
        x *= grow
        y *= grow

    return p + right * x + up * y


def build_body(mb, spine, seed=C.SEED):
    """Govde tupunu uretir. Doner: dict(grid, holes, front_ring, vert_s)."""
    mat_body = mb.mat("M_Dragon_Body")
    mat_scar = mb.mat("M_Dragon_Scars")
    rect = uvmap.BODY["tube"]
    cols, rings = C.BODY_COLS, C.BODY_RINGS

    if not hasattr(mb, "vert_s"):
        mb.vert_s = {}
        mb.vert_phi = {}

    # ---- vertexler ----
    grid = []
    for i in range(rings + 1):
        s = ring_s(i)
        p, right, up, tan = spine.frame(s)
        w, h, bf, ex = body_radius(s)
        row = []
        for c in range(cols):
            phi = TAU * c / cols
            x, y = superellipse(phi, w, h, ex, belly_flat=bf)

            deg = math.degrees(phi)
            if deg > 180.0:
                deg -= 360.0
            bulge = 0.0
            for bs, bphi, ss, sp, amt in MUSCLE_BULGES:
                dd = deg - bphi
                while dd > 180.0:
                    dd -= 360.0
                while dd < -180.0:
                    dd += 360.0
                if abs(s - bs) > ss * 4.0 or abs(dd) > sp * 4.0:
                    continue
                g = (math.exp(-0.5 * ((s - bs) / ss) ** 2)
                     * math.exp(-0.5 * (dd / sp) ** 2))
                bulge += amt * g
            ridge = 0.060 * math.exp(-0.5 * (deg / 13.0) ** 2) * smoothstep(0.12, 0.21, s)
            wob = cyl_noise(phi, s, 2.0, 24.0, octaves=3, seed=seed + 11) * 0.018
            wob += cyl_noise(phi, s, 5.0, 66.0, octaves=2, seed=seed + 29) * 0.008
            # pul kabartisi (silueti besleyen gercek geometri)
            sc = scale_field(c / cols, i / rings, s, seed=seed)
            # karin bolgesinde pul yerine genis plaka -> kabarti azaltilir
            ventral_mask = smoothstep(118.0, 150.0, abs(deg))
            sc *= (1.0 - 0.72 * ventral_mask)

            radial = (bulge + ridge + wob + sc)
            base = max(0.22, math.hypot(x, y))
            grow = 1.0 + radial / base
            x *= grow
            y *= grow
            vi = mb.add_vert(p + right * x + up * y, "body")
            mb.vert_s[vi] = s
            mb.vert_phi[vi] = phi
            row.append(vi)
        grid.append(row)

    # ---- delik maskesi ----
    skip = set()
    for name, hd in HOLES.items():
        r0, r1 = hd["rows"]
        c0, c1 = hd["cols"]
        for r in range(r0, r1):
            for c in range(c0, c1):
                skip.add((r, c % cols))

    # ---- yara izi yamalari (M_Dragon_Scars) ----
    scar_patches = [
        (95, 104, 20, 26), (118, 125, 44, 49), (52, 58, 26, 31),
        (160, 166, 15, 20), (78, 83, 30, 34),
    ]
    scar_faces = set()
    for r0, r1, c0, c1 in scar_patches:
        for r in range(r0, r1):
            for c in range(c0, c1):
                scar_faces.add((r, c % cols))

    # ---- yuzler ----
    u0, v0, u1, v1 = rect
    for r in range(rings):
        for c in range(cols):
            if (r, c) in skip:
                continue
            c2 = (c + 1) % cols
            a, b = grid[r][c], grid[r][c2]
            d, e = grid[r + 1][c], grid[r + 1][c2]
            fu0 = u0 + (u1 - u0) * (c / cols)
            fu1 = u0 + (u1 - u0) * ((c + 1) / cols)
            fv0 = v0 + (v1 - v0) * (r / rings)
            fv1 = v0 + (v1 - v0) * ((r + 1) / rings)
            m = mat_scar if (r, c) in scar_faces else mat_body
            uvr = uvmap.SCARS["patch_a"] if m == mat_scar else None
            if uvr is not None:
                # yara yamasi kendi atlasina yeniden esleniyor
                su0, sv0, su1, sv1 = uvr
                lu0 = su0 + (su1 - su0) * ((c % 8) / 8.0)
                lu1 = su0 + (su1 - su0) * (((c % 8) + 1) / 8.0)
                lv0 = sv0 + (sv1 - sv0) * ((r % 8) / 8.0)
                lv1 = sv0 + (sv1 - sv0) * (((r % 8) + 1) / 8.0)
                mb.add_face((a, b, e, d),
                            ((lu0, lv0), (lu1, lv0), (lu1, lv1), (lu0, lv1)), m)
            else:
                mb.add_face((a, b, e, d),
                            ((fu0, fv0), (fu1, fv0), (fu1, fv1), (fu0, fv1)), m)

    # ---- kuyruk ucu kapagi ----
    tail_ring = grid[rings]
    tip = spine.pos(1.0) + spine.tan(1.0) * 0.05
    mb.cap_ring(tail_ring, tip, (0.5, 0.985),
                (rect[0], rect[3] - 0.02, rect[2], rect[3]), mat_body, "body")

    # ---- delik sinir halkalari ----
    loops = {}
    for name, hd in HOLES.items():
        loops[name] = hole_boundary(grid, hd["rows"], hd["cols"], cols)

    return {
        "grid": grid,
        "holes": loops,
        "front_ring": grid[0],       # kafaya koprulenecek acik halka
        "cols": cols,
        "rings": rings,
    }


def hole_boundary(grid, rows, cols_rng, ncols):
    """Delik cevresindeki vertexleri sirali dondurur (2*(a+b) adet)."""
    r0, r1 = rows
    c0, c1 = cols_rng
    loop = []
    for c in range(c0, c1):
        loop.append(grid[r0][c % ncols])
    for r in range(r0, r1):
        loop.append(grid[r][c1 % ncols])
    for c in range(c1, c0, -1):
        loop.append(grid[r1][c % ncols])
    for r in range(r1, r0, -1):
        loop.append(grid[r][c0 % ncols])
    return loop


def hole_center_and_axis(mb, loop, spine, s_hint, phi_hint_deg):
    """Delik merkezi + disari bakan eksen."""
    c = Vector((0.0, 0.0, 0.0))
    for vi in loop:
        c += mb.verts[vi]
    c /= len(loop)
    p, right, up, tan = spine.frame(s_hint)
    phi = math.radians(phi_hint_deg)
    n = (right * math.sin(phi) + up * math.cos(phi)).normalized()
    return c, n
