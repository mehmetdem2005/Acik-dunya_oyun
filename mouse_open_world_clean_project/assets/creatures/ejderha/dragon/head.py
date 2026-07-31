"""Kafa kabugu (kafatasi + damak), alt cene, dil, gozler, burun delikleri.

Kafa kabugunun kesiti KAPALI bir halkadir:
  dis ark (sol dudak -> tepe -> sag dudak)  +  damak arki (sag dudak -> sol dudak)
Boylece agiz bosluğu gercek geometriyle olusur, hacim kapalı kalır ve arka uc
boyun halkasina birebir koprulenir (64 vertex = 64 vertex).
"""

import math
from mathutils import Vector, Quaternion

from . import config as C
from . import uvmap
from .core import (TAU, pchip_multi, smoothstep, clamp, fbm3, lerp)

HEAD_COLS = 64          # govde tupuyle birebir eslesir
OUTER_N = 43            # dis ark vertex sayisi (iki dudak dahil)
PALATE_N = HEAD_COLS - OUTER_N   # 21 damak ic vertexi
TOP_INDEX = (OUTER_N - 1) // 2   # 21 -> dis arkin tepe indeksi


def head_profile(t, col):
    return pchip_multi(C.HEAD_PROFILE, t, col)


def _scale_bump(u, v, freq_u, freq_v, amp, seed):
    uu = u * freq_u
    vv = v * freq_v
    row = math.floor(vv)
    su = uu + (0.5 if int(row) % 2 else 0.0)
    cu = su - math.floor(su) - 0.5
    cv = vv - row - 0.5
    h = ((cu * 1.1) ** 2 + (cv * 1.35) ** 2)
    j = ((int(math.floor(su)) * 92837111) ^ (int(row) * 689287499) ^ seed) & 0xFFFF
    j = j / 65535.0
    r = h / (0.26 + j * 0.10)
    return amp * max(0.0, 1.0 - r) ** 0.6


def head_cross_section(t, seed=C.SEED):
    """Kafa yerel kesiti: (x, y) listesi, uzunluk HEAD_COLS.

    Yerel y=0 omurga hizasi; dudak cizgisi y_lip'te.
    """
    w = head_profile(t, 1)
    hs = head_profile(t, 2)
    dp = head_profile(t, 3)
    brow = head_profile(t, 4)
    y_lip = -hs * 0.44
    n_exp = 2.9 - 0.5 * t          # burna dogru daha yuvarlak

    pts = []
    # --- dis ark: sol dudak -> tepe -> sag dudak ---
    for i in range(OUTER_N):
        a = i / (OUTER_N - 1)
        th = math.pi * a
        cx = math.cos(th)
        sx = math.sin(th)
        x = -w * (1.0 if cx >= 0 else -1.0) * (abs(cx) ** (2.0 / n_exp))
        y = hs * (abs(sx) ** (2.0 / n_exp))
        # kas kemigi (brow ridge): yanlarda, tepeye yakin degil
        lat = abs(x) / max(w, 1e-6)
        bfac = math.exp(-0.5 * ((lat - 0.74) / 0.17) ** 2)
        y += brow * bfac * 1.35
        x *= (1.0 + brow * 0.55 * bfac / max(w, 0.05))
        # yanak kemigi
        cheek = math.exp(-0.5 * ((lat - 0.93) / 0.13) ** 2) * smoothstep(0.10, 0.34, t) \
            * (1.0 - smoothstep(0.44, 0.66, t))
        x *= (1.0 + 0.11 * cheek)
        # burun kemiksi sirt (nasal ridge)
        nas = math.exp(-0.5 * (lat / 0.22) ** 2) * smoothstep(0.50, 0.66, t) \
            * (1.0 - smoothstep(0.90, 1.0, t))
        y += 0.035 * nas
        # pul kabartisi
        y += _scale_bump(a, t, 26.0, 34.0, 0.0085, seed)
        x += _scale_bump(a + 0.37, t, 26.0, 34.0, 0.0060, seed + 7) * (1.0 if x >= 0 else -1.0)
        pts.append((x, y_lip + y))

    # --- damak arki: sag dudaktan sol dudaga (ic noktalar) ---
    for k in range(1, PALATE_N + 1):
        f = k / (PALATE_N + 1)
        x = w * (1.0 - 2.0 * f)
        rel = abs(x) / max(w, 1e-6)
        y = dp * ((1.0 - rel * rel) ** 0.62)
        # damak sirti (choana / orta oluk)
        y -= dp * 0.16 * math.exp(-0.5 * (x / (w * 0.14 + 1e-6)) ** 2)
        pts.append((x, y_lip + y))
    return pts


def head_surface(spine, t, lat_ratio, side):
    """Kafa dis yuzeyinde nokta + disa bakan normal.

    lat_ratio: 0 = tepe orta hat, 1 = dudak cizgisi.
    """
    s = C.S_HEAD_END * (1.0 - t)
    p, right, up, tan = spine.frame(s)
    pitch = math.radians(C.HEAD_PITCH_DEG) * smoothstep(0.0, 0.45, t)
    rot = Quaternion(right, pitch)
    up_h = rot @ up
    sec = head_cross_section(t)
    a = 0.5 + side * 0.5 * clamp(lat_ratio, 0.0, 1.0)
    k = clamp(a * (OUTER_N - 1), 0.0, OUTER_N - 1.0)
    k0 = int(k)
    k1 = min(k0 + 1, OUTER_N - 1)
    f = k - k0
    x = lerp(sec[k0][0], sec[k1][0], f)
    y = lerp(sec[k0][1], sec[k1][1], f)
    co = p + right * x + up_h * y
    # normal: kesit tegetinin dikey bileseni
    kx = sec[k1][0] - sec[k0][0]
    ky = sec[k1][1] - sec[k0][1]
    n2 = Vector((ky, -kx, 0.0))
    if n2.length < 1e-9:
        n2 = Vector((x, y, 0.0))
    n2.normalize()
    n = (right * n2.x + up_h * n2.y).normalized()
    if n.dot(co - p) < 0:
        n = -n
    return co, n


def build_head(mb, spine, seed=C.SEED):
    """Kafa kabugunu uretir; arka acik halkayi doner (boyuna koprulenecek)."""
    mat_head = mb.mat("M_Dragon_Head")
    mat_mouth = mb.mat("M_Dragon_Mouth")
    r_skull = uvmap.HEAD["skull"]
    r_palate = uvmap.MOUTH["palate"]

    if not hasattr(mb, "vert_s"):
        mb.vert_s = {}
        mb.vert_phi = {}
    if not hasattr(mb, "head_t"):
        mb.head_t = {}

    rings = C.HEAD_RINGS
    grid = []
    pitch = math.radians(C.HEAD_PITCH_DEG)
    for i in range(rings + 1):
        t = i / rings                      # 0 = kafa arkasi, 1 = burun ucu
        s = C.S_HEAD_END * (1.0 - t)
        p, right, up, tan = spine.frame(s)
        # kafanin boyuna gore hafif asagi bakisi
        rot = Quaternion(right, pitch * smoothstep(0.0, 0.45, t))
        up_h = rot @ up
        fwd_h = rot @ (-tan)
        sec = head_cross_section(t, seed)
        row = []
        for k in range(HEAD_COLS):
            x, y = sec[k]
            co = p + right * x + up_h * y
            vi = mb.add_vert(co, "head")
            mb.vert_s[vi] = s
            mb.head_t[vi] = t
            row.append(vi)
        grid.append(row)

    # --- goz cukuru + burun deligi cukurlugu (gercek geometri) ---
    _carve_eye_sockets(mb, grid, spine)
    _carve_nostrils(mb, grid, spine)

    # --- halkalari hizala: index 0 = tepe, +X yonune git (govdeyle ayni) ---
    def align(row):
        return [row[(k + TOP_INDEX) % HEAD_COLS] for k in range(HEAD_COLS)]

    aligned = [align(r) for r in grid]

    # --- yuzler ---
    # aligned indekste: 0..(OUTER_N-1-TOP_INDEX) ve sondan geri = dis yuzey,
    # damak vertexleri orijinal 43..63 -> aligned 22..42
    palate_aligned = set(range(OUTER_N - TOP_INDEX, OUTER_N - TOP_INDEX + PALATE_N))
    for r in range(rings):
        for c in range(HEAD_COLS):
            c2 = (c + 1) % HEAD_COLS
            a, b = aligned[r][c], aligned[r][c2]
            d, e = aligned[r + 1][c], aligned[r + 1][c2]
            in_mouth = (c in palate_aligned and c2 in palate_aligned)
            if in_mouth:
                rect, mat = r_palate, mat_mouth
                lo = (c - (OUTER_N - TOP_INDEX)) / PALATE_N
                hi = (c + 1 - (OUTER_N - TOP_INDEX)) / PALATE_N
            else:
                rect, mat = r_skull, mat_head
                lo = c / HEAD_COLS
                hi = (c + 1) / HEAD_COLS
            u0, v0, u1, v1 = rect
            fu0 = u0 + (u1 - u0) * clamp(lo, 0.0, 1.0)
            fu1 = u0 + (u1 - u0) * clamp(hi, 0.0, 1.0)
            fv0 = v0 + (v1 - v0) * (r / rings)
            fv1 = v0 + (v1 - v0) * ((r + 1) / rings)
            # dis yuzeyde normal disari; damakta ters (bosluga bakar)
            mb.add_face((a, b, e, d),
                        ((fu0, fv0), (fu1, fv0), (fu1, fv1), (fu0, fv1)), mat)

    # --- burun ucu kapagi ---
    tip = spine.pos(0.0) + Vector((0.0, -0.02, -0.04))
    mb.cap_ring(aligned[rings], tip, (0.5, 0.985),
                (r_skull[0], r_skull[3] - 0.02, r_skull[2], r_skull[3]),
                mat_head, "head", flip=True)

    return {"rear_ring": aligned[0], "grid": aligned, "rings": rings}


def _carve_eye_sockets(mb, grid, spine):
    """Goz cukurunu iceri, goz kapagi kenarini disari iter."""
    e = C.EYE
    rings = C.HEAD_RINGS
    t_c = e["t"]
    for i in range(rings + 1):
        t = i / rings
        dt = (t - t_c)
        if abs(dt) > 0.115:
            continue
        for k in range(OUTER_N):
            a = k / (OUTER_N - 1)
            # yanal konum: a=0 sol dudak, 0.5 tepe, 1 sag dudak
            lat = abs(a - 0.5) * 2.0            # 0 tepe, 1 dudak
            dl = lat - e["side"] * 0.86
            if abs(dl) > 0.30:
                continue
            g = (math.exp(-0.5 * (dt / 0.052) ** 2)
                 * math.exp(-0.5 * (dl / 0.135) ** 2))
            rim = (math.exp(-0.5 * (dt / 0.088) ** 2)
                   * math.exp(-0.5 * (dl / 0.215) ** 2)) - g
            vi = grid[i][k]
            co = mb.verts[vi]
            ctr = spine.pos(C.S_HEAD_END * (1.0 - t))
            d = (co - ctr)
            if d.length < 1e-6:
                continue
            n = d.normalized()
            mb.verts[vi] = co - n * (g * 0.085) + n * (max(0.0, rim) * 0.042)


def _carve_nostrils(mb, grid, spine):
    rings = C.HEAD_RINGS
    t_c = 0.885
    for i in range(rings + 1):
        t = i / rings
        dt = t - t_c
        if abs(dt) > 0.075:
            continue
        for k in range(OUTER_N):
            a = k / (OUTER_N - 1)
            lat = abs(a - 0.5) * 2.0
            dl = lat - 0.46
            if abs(dl) > 0.24:
                continue
            g = (math.exp(-0.5 * (dt / 0.028) ** 2)
                 * math.exp(-0.5 * (dl / 0.075) ** 2))
            rim = (math.exp(-0.5 * (dt / 0.050) ** 2)
                   * math.exp(-0.5 * (dl / 0.130) ** 2)) - g
            vi = grid[i][k]
            co = mb.verts[vi]
            ctr = spine.pos(C.S_HEAD_END * (1.0 - t))
            d = (co - ctr)
            if d.length < 1e-6:
                continue
            n = d.normalized()
            mb.verts[vi] = co - n * (g * 0.062) + n * (max(0.0, rim) * 0.026)


# ==================================================================
# ALT CENE
# ==================================================================
JAW_COLS = 40
JAW_TOP_N = 21          # ust ark (dil tabani) - iki kose dahil
JAW_BOT_N = JAW_COLS - JAW_TOP_N   # 19


def jaw_frame(spine):
    """Cene ekleminin dunya konumu ve on yonu."""
    t_joint = 0.115
    s = C.S_HEAD_END * (1.0 - t_joint)
    p, right, up, tan = spine.frame(s)
    hs = head_profile(t_joint, 2)
    y_lip = -hs * 0.44
    origin = p + up * (y_lip - 0.055)
    fwd = (-tan).normalized()
    # cene hafif asagi egimli
    q = Quaternion(right, math.radians(-4.0))
    return origin, (q @ fwd).normalized(), right.normalized(), (q @ up).normalized()


def build_jaw(mb, spine, seed=C.SEED):
    mat_head = mb.mat("M_Dragon_Head")
    mat_mouth = mb.mat("M_Dragon_Mouth")
    r_out = uvmap.HEAD["jaw_outer"]
    r_in = uvmap.MOUTH["jaw_inner"]

    origin, fwd, right, up = jaw_frame(spine)
    rings = C.JAW_RINGS
    t_joint = 0.115
    grid = []
    for i in range(rings + 1):
        t = i / rings
        # cene kesiti KAFANIN DUDAK CIZGISINI takip eder -> bind pozda agiz kapali,
        # dis tasmasi olmaz, cene acilinca eklem etrafinda rijit doner.
        ht = t_joint + (1.0 - t_joint) * t
        lip_l = head_surface(spine, ht, 0.995, 1.0)[0]
        lip_r = head_surface(spine, ht, 0.995, -1.0)[0]
        ctr = (lip_l + lip_r) * 0.5
        span = (lip_l - lip_r)
        w = max(span.length * 0.5 * (1.005 + 0.10 * t), 0.03)
        rgt = span.normalized() if span.length > 1e-6 else right
        sp = spine.frame(C.S_HEAD_END * (1.0 - ht))
        upl = (sp[2] - rgt * sp[2].dot(rgt)).normalized()
        h = pchip_multi(C.JAW_PROFILE, t, 2) * 1.06
        ctr = ctr - upl * 0.002          # dudak cizgisinin hemen altina otur
        row = []
        # ust ark (dil tabani): sol kose -> orta -> sag kose, hafif icbukey
        for k in range(JAW_TOP_N):
            a = k / (JAW_TOP_N - 1)
            x = -w * (1.0 - 2.0 * a)
            rel = abs(x) / max(w, 1e-6)
            y = -h * 0.13 * (1.0 - rel * rel) ** 0.8      # dil yatagi cukuru
            row.append(mb.add_vert(ctr + rgt * x + upl * y, "jaw"))
        # alt ark (dis cene derisi): sag kose -> asagi -> sol kose
        for k in range(1, JAW_BOT_N + 1):
            f = k / (JAW_BOT_N + 1)
            th = math.pi * f
            x = w * math.cos(th)
            y = -h * (math.sin(th) ** (2.0 / 2.6))
            # cene kemigi kosesi belirginlesir
            y -= h * 0.13 * math.exp(-0.5 * ((abs(x) / max(w, 1e-6) - 0.82) / 0.16) ** 2)
            y += _scale_bump(f, t, 20.0, 26.0, 0.0075, seed + 3)
            row.append(mb.add_vert(ctr + rgt * x + upl * y, "jaw"))
        grid.append(row)

    for r in range(rings):
        for c in range(JAW_COLS):
            c2 = (c + 1) % JAW_COLS
            a, b = grid[r][c], grid[r][c2]
            d, e = grid[r + 1][c], grid[r + 1][c2]
            # ust arkin en dis 2 kolonu deri materyali -> agiz ici disaridan
            # gorunmez (kirmizi serit olusmaz)
            inner = (2 <= c < JAW_TOP_N - 3)
            rect = r_in if inner else r_out
            mat = mat_mouth if inner else mat_head
            if inner:
                lo, hi = c / (JAW_TOP_N - 1), (c + 1) / (JAW_TOP_N - 1)
            else:
                lo = (c - (JAW_TOP_N - 1)) / (JAW_BOT_N + 1)
                hi = (c + 1 - (JAW_TOP_N - 1)) / (JAW_BOT_N + 1)
            u0, v0, u1, v1 = rect
            fu0 = u0 + (u1 - u0) * clamp(lo, 0.0, 1.0)
            fu1 = u0 + (u1 - u0) * clamp(hi, 0.0, 1.0)
            fv0 = v0 + (v1 - v0) * (r / rings)
            fv1 = v0 + (v1 - v0) * ((r + 1) / rings)
            mb.add_face((a, b, e, d),
                        ((fu0, fv0), (fu1, fv0), (fu1, fv1), (fu0, fv1)), mat)

    # on kapak (cene ucu) + arka kapak (eklem)
    front_c = Vector((0.0, 0.0, 0.0))
    for vi in grid[rings]:
        front_c = front_c + mb.verts[vi]
    front_c = front_c / len(grid[rings]) + fwd * 0.05
    mb.cap_ring(grid[rings], front_c, (0.5, 0.97),
                (r_out[0], r_out[3] - 0.03, r_out[2], r_out[3]), mat_head, "jaw")
    back_c = Vector((0.0, 0.0, 0.0))
    for vi in grid[0]:
        back_c = back_c + mb.verts[vi]
    back_c = back_c / len(grid[0]) - fwd * 0.09
    mb.cap_ring(grid[0], back_c, (0.5, 0.03),
                (r_out[0], r_out[1], r_out[2], r_out[1] + 0.03), mat_head, "jaw",
                flip=True)
    return {"grid": grid, "origin": origin, "fwd": fwd, "right": right, "up": up}


# ==================================================================
# DIL
# ==================================================================
def build_tongue(mb, spine, jaw):
    mat = mb.mat("M_Dragon_Mouth")
    rect = uvmap.MOUTH["tongue"]
    origin = jaw["origin"] + jaw["fwd"] * 0.16 + jaw["up"] * 0.045
    fwd, right, up = jaw["fwd"], jaw["right"], jaw["up"]
    rings, cols = 24, 16
    L = C.JAW_LENGTH * 0.74
    grid = []
    for i in range(rings + 1):
        t = i / rings
        w = 0.175 * (1.0 - 0.62 * t ** 1.7) * (0.55 + 0.45 * smoothstep(0.0, 0.12, t))
        h = 0.075 * (1.0 - 0.70 * t ** 1.6) * (0.55 + 0.45 * smoothstep(0.0, 0.12, t))
        ctr = origin + fwd * (L * t) + up * (0.018 * math.sin(t * 2.4))
        row = []
        for c in range(cols):
            phi = TAU * c / cols
            x = w * math.sin(phi)
            y = h * math.cos(phi)
            # orta oluk
            y -= h * 0.30 * math.exp(-0.5 * (x / (w * 0.16 + 1e-6)) ** 2) * max(0.0, math.cos(phi))
            row.append(mb.add_vert(ctr + right * x + up * y, "tongue"))
        grid.append(row)
    for r in range(rings):
        mb.bridge_loops(grid[r], grid[r + 1],
                        (rect[0], rect[1] + (rect[3] - rect[1]) * r / rings,
                         rect[2], rect[1] + (rect[3] - rect[1]) * (r + 1) / rings),
                        mat, flip=True)
    mb.cap_ring(grid[0], origin - fwd * 0.05, (0.5, 0.03), rect, mat, "tongue")
    mb.cap_ring(grid[rings], origin + fwd * (L + 0.03), (0.5, 0.97), rect, mat,
                "tongue", flip=True)


# ==================================================================
# GOZLER
# ==================================================================
def eye_world_pos(spine, side):
    e = C.EYE
    t = e["t"]
    s = C.S_HEAD_END * (1.0 - t)
    p, right, up, tan = spine.frame(s)
    w = head_profile(t, 1)
    hs = head_profile(t, 2)
    y_lip = -hs * 0.44
    # dis ark uzerinde lat = side oranina karsilik gelen nokta
    a = 0.5 + side * 0.5 * e["side"]
    th = math.pi * a
    n_exp = 2.9 - 0.5 * t
    cx, sx = math.cos(th), math.sin(th)
    x = -w * (1.0 if cx >= 0 else -1.0) * (abs(cx) ** (2.0 / n_exp))
    y = hs * (abs(sx) ** (2.0 / n_exp))
    ctr = p + right * (x * 0.80) + up * (y_lip + y * 0.86)
    return ctr


def head_landmarks(spine):
    """Rig icin kafa uzerindeki referans noktalari (goz, burun, dudak, kas)."""
    out = {}
    for side, sfx in ((1.0, "L"), (-1.0, "R")):
        e = eye_world_pos(spine, side)
        p, right, up, tan = spine.frame(C.S_HEAD_END * (1.0 - C.EYE["t"]))
        out[sfx] = e
        out["dir_" + sfx] = (right * side * 0.86 + (-tan) * 0.34
                             + up * 0.20).normalized()
        out["nostril_" + sfx] = head_surface(spine, 0.885, 0.46, side)[0]
        out["lip_" + sfx] = head_surface(spine, 0.70, 0.97, side)[0]
        out["brow_" + sfx] = head_surface(spine, 0.20, 0.74, side)[0]
    return out


def build_eyes(mb, spine):
    mat = mb.mat("M_Dragon_Eyes")
    for side, tag in ((1.0, "l"), (-1.0, "r")):
        ctr = eye_world_pos(spine, side)
        rect = uvmap.EYES["eyeball_l" if side > 0 else "eyeball_r"]
        rad = C.EYE["radius"]
        rings, cols = 18, 24
        grid = []
        # kuresel goz + on tarafta kornea sismesi
        p, right, up, tan = spine.frame(C.S_HEAD_END * (1.0 - C.EYE["t"]))
        out = (right * side * 0.86 + (-tan) * 0.30 + up * 0.22).normalized()
        # kutuplar ayri kapatilir -> sifir alanli yuz olusmaz
        for i in range(1, rings):
            th = math.pi * i / rings
            row = []
            for c in range(cols):
                ph = TAU * c / cols
                d = Vector((math.sin(th) * math.cos(ph),
                            math.cos(th),
                            math.sin(th) * math.sin(ph)))
                # kornea: out yonune bakan yarim kurede sisme
                dot = d.dot(out)
                bulge = 1.0 + (C.EYE["cornea_bulge"] - 1.0) * max(0.0, dot) ** 3.0
                row.append(mb.add_vert(ctr + d * rad * bulge, "eye_" + tag))
            grid.append(row)
        nrow = len(grid)
        u0, v0, u1, v1 = rect
        for r in range(nrow - 1):
            for c in range(cols):
                c2 = (c + 1) % cols
                a, b = grid[r][c], grid[r][c2]
                dd, e = grid[r + 1][c], grid[r + 1][c2]
                fu0 = u0 + (u1 - u0) * (c / cols)
                fu1 = u0 + (u1 - u0) * ((c + 1) / cols)
                fv0 = v0 + (v1 - v0) * ((r + 1) / (rings))
                fv1 = v0 + (v1 - v0) * ((r + 2) / (rings))
                mb.add_face((a, b, e, dd),
                            ((fu0, fv0), (fu1, fv0), (fu1, fv1), (fu0, fv1)), mat)
        # kutup kapaklari
        mb.cap_ring(grid[0], ctr + Vector((0.0, rad, 0.0)), (0.5, 0.06),
                    (u0, v0, u1, v0 + (v1 - v0) * 0.10), mat, "eye_" + tag)
        mb.cap_ring(grid[-1], ctr - Vector((0.0, rad, 0.0)), (0.5, 0.94),
                    (u0, v1 - (v1 - v0) * 0.10, u1, v1), mat, "eye_" + tag,
                    flip=True)
