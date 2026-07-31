"""Kanatlar: kok tupu (govde deliginden kaynak) + tek parca zar kabugu.

Zar, parmak kemikleri ve on kol TEK bagli quad tabakasi olarak uretilir; sonra
degisken kalinlikta solidify edilir. Boylece:
  - parmak kemikleri zarla ayni topolojiyi paylasir (katlanirken yirtilma yok),
  - dallanma (branching) problemi olusmaz,
  - sonuc kapali manifold kabuktur.
"""

import math
from mathutils import Vector, Quaternion

from . import config as C
from . import uvmap
from .core import TAU, smoothstep, clamp, lerp, fbm3
from .limbs import loop_angles, build_claw

SPAN_N = 64          # parmak yonunde bolunme
CHORD_M = 18         # panel icinde enine bolunme


def _dir(lat, up, back, elev_deg, sweep_deg):
    """(lat, up, back) bazinda acik yon: elev = yatayin uzeri, sweep = geriye."""
    e = math.radians(elev_deg)
    s = math.radians(sweep_deg)
    return (lat * (math.cos(e) * math.cos(s))
            + back * (math.cos(e) * math.sin(s))
            + up * math.sin(e)).normalized()


def wing_skeleton(spine, side):
    """Bind pozu (yari-acik notr): her eklem ACIKCA elev/sweep ile konur.

    Zincirlenmis quaternion yerine dogrudan yon tanimi kullanilir; boylece
    her segmentin nereye gittigi olculebilir ve isaret hatasi olusmaz.
    """
    w = C.WING
    p, right, up_s, tan = spine.frame(w["attach_s"])
    lat = Vector((right.x * side, 0.0, right.z * side)).normalized()
    up = Vector((0.0, 1.0, 0.0))
    back = Vector((tan.x, 0.0, tan.z)).normalized()

    phi = math.radians(w["attach_yaw"]) * side
    shoulder = p + (right * math.sin(phi) + up_s * math.cos(phi)) * 1.02

    hum_dir = _dir(lat, up, back, *w["humerus_dir"])
    elbow = shoulder + hum_dir * w["humerus"]
    fore_dir = _dir(lat, up, back, *w["forearm_dir"])
    wrist = elbow + fore_dir * w["forearm"]
    hand_dir = _dir(lat, up, back, *w["hand_dir"])
    hand_end = wrist + hand_dir * w["wrist"]

    # kanat duzlemi: humerus + parmak yayilimini iceren duzlem
    f0 = _dir(lat, up, back, *w["fingers"][0][1])
    f3 = _dir(lat, up, back, *w["fingers"][3][1])
    nrm = f0.cross(f3)
    if nrm.length < 1e-5:
        nrm = hum_dir.cross(back)
    nrm.normalize()
    if nrm.dot(Vector((0.0, 1.0, 0.0))) < 0:
        nrm = -nrm
    chord = nrm.cross(hum_dir).normalized()
    if chord.dot(back) < 0:
        chord = -chord

    origins, dirs, lens = [], [], []
    spacing = 0.13
    for k, (L, ang, tipr) in enumerate(w["fingers"]):
        d = _dir(lat, up, back, *ang)
        o = hand_end + chord * (k * spacing) - hand_dir * (k * spacing * 0.30)
        origins.append(o)
        dirs.append(d)
        lens.append(L)

    # zarin govdeye baglandigi nokta (bogum / flank)
    pb, rb, ub, tb = spine.frame(w["body_anchor_s"])
    anchor = pb + (rb * side * 0.94 + ub * (-0.36)).normalized() * 1.02

    return {
        "shoulder": shoulder, "elbow": elbow, "wrist": wrist,
        "hand_end": hand_end,
        "hum_dir": hum_dir, "fore_dir": fore_dir, "hand_dir": hand_dir,
        "normal": nrm, "chord": chord,
        "origins": origins, "dirs": dirs, "lens": lens,
        "anchor": anchor,
    }


# ==================================================================
# ZAR TABAKASI
# ==================================================================
def _arm_point(sk, f):
    """Bilek -> dirsek -> omuz polilinesi uzerinde f in [0,1]."""
    a = sk["wrist"]
    b = sk["elbow"]
    c = sk["shoulder"]
    l1 = (b - a).length
    l2 = (c - b).length
    tot = l1 + l2
    d = f * tot
    if d <= l1:
        return a.lerp(b, d / max(l1, 1e-6))
    return b.lerp(c, (d - l1) / max(l2, 1e-6))


def build_membrane_sheet(sk, side, seed=C.SEED):
    """Tek bagli quad tabakasi uretir (pozisyon + yuz + parametre bilgisi)."""
    w = C.WING
    nrm = sk["normal"]
    pos = []
    uvp = []          # (panel_u 0..1 kanat genelinde, alpha)
    bonew = []        # kemik yakinligi 0..1
    key = {}          # (rib_id, i) -> index  ; ortak kaburga vertexleri
    quads = []

    n_panels = 4
    ribs = []
    for k in range(4):
        ribs.append({"o": sk["origins"][k], "d": sk["dirs"][k], "L": sk["lens"][k],
                     "bone": True})
    # 5. kaburga: govde baglantisi (kemik degil)
    ribs.append({"o": sk["shoulder"], "d": (sk["anchor"] - sk["shoulder"]).normalized(),
                 "L": (sk["anchor"] - sk["shoulder"]).length, "bone": False})

    def emit(p, u, alpha, bw):
        pos.append(p)
        uvp.append((u, alpha))
        bonew.append(bw)
        return len(pos) - 1

    for pi in range(n_panels):
        A = ribs[pi]
        B = ribs[pi + 1]
        grid = []
        for i in range(SPAN_N + 1):
            alpha = i / SPAN_N
            row = []
            for j in range(CHORD_M + 1):
                fj = j / CHORD_M
                # ortak kaburga vertexleri tekrar kullanilir
                if j == 0 and ("rib", pi, i) in key:
                    row.append(key[("rib", pi, i)])
                    continue
                # yon / uzunluk / kok noktasi enterpolasyonu
                if pi < 3:
                    o = A["o"].lerp(B["o"], fj)
                else:
                    o = A["o"].lerp(_arm_point(sk, fj), fj)
                d = (A["d"] * (1.0 - fj) + B["d"] * fj)
                if d.length < 1e-6:
                    d = A["d"]
                d = d.normalized()
                L = lerp(A["L"], B["L"], fj)
                # arka kenar oyugu (scallop)
                scal = 1.0 - w["scallop_depth"] * math.sin(math.pi * fj) ** 1.3
                p = o + d * (L * scal * alpha)

                # zar sarkmasi (kagit gibi duz degil)
                sag = math.sin(math.pi * fj) * math.sin(math.pi * alpha ** 0.75)
                p = p - nrm * (sag * 0.34 * L * 0.10)
                # gerilim kirisiklari
                wr = fbm3(fj * 7.0, alpha * 9.0, 3.1, octaves=3, seed=seed + 51)
                p = p + nrm * (wr * 0.022 * math.sin(math.pi * fj))
                # ana damarlar (hafif geometri, gerisi normal map)
                vein = math.exp(-0.5 * ((math.sin(fj * math.pi * 3.0)) / 0.16) ** 2)
                p = p + nrm * (vein * 0.010 * alpha * (1.0 - alpha * 0.4)) * side

                # kemik yakinligi
                bw = 0.0
                if A["bone"]:
                    bw = max(bw, math.exp(-0.5 * (fj / 0.075) ** 2))
                if B["bone"]:
                    bw = max(bw, math.exp(-0.5 * ((1.0 - fj) / 0.075) ** 2))
                bw *= (1.0 - 0.72 * alpha ** 1.6)      # uca dogru incelir
                u_glob = (pi + fj) / n_panels
                idx = emit(p, u_glob, alpha, bw)
                if j == 0:
                    key[("rib", pi, i)] = idx
                if j == CHORD_M:
                    key[("rib", pi + 1, i)] = idx
                row.append(idx)
            grid.append(row)

        # --- yuzler (bazi kucuk delikler: iyilesmis yirtiklar) ---
        tears = _tear_cells(pi, seed)
        for i in range(SPAN_N):
            for j in range(CHORD_M):
                if (i, j) in tears:
                    continue
                quads.append((grid[i][j], grid[i][j + 1],
                              grid[i + 1][j + 1], grid[i + 1][j]))
    return pos, quads, uvp, bonew


def _tear_cells(panel, seed):
    """Zarda kucuk gercek delikler (iyilesmis yirtik izleri)."""
    out = set()
    spec = {
        0: [(52, 14, 2, 1)],
        1: [(58, 3, 2, 2)],
        2: [(44, 12, 1, 2), (61, 6, 2, 1)],
        3: [(49, 9, 2, 1)],
    }
    for (i0, j0, di, dj) in spec.get(panel, []):
        for i in range(i0, min(i0 + di, SPAN_N)):
            for j in range(j0, min(j0 + dj, CHORD_M)):
                out.add((i, j))
    return out


def _vertex_normals(pos, quads):
    nrm = [Vector((0.0, 0.0, 0.0)) for _ in pos]
    for q in quads:
        a, b, c, d = (pos[i] for i in q)
        n = (b - a).cross(d - a) + (d - c).cross(b - c)
        for i in q:
            nrm[i] += n
    out = []
    for n in nrm:
        if n.length < 1e-9:
            out.append(Vector((0.0, 1.0, 0.0)))
        else:
            out.append(n.normalized())
    return out


def _boundary_edges(quads):
    cnt = {}
    for q in quads:
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            e = (min(a, b), max(a, b))
            cnt[e] = cnt.get(e, 0) + 1
    # yonlu sinir kenarlari (yuz sirasina gore)
    bnd = []
    for q in quads:
        for k in range(4):
            a, b = q[k], q[(k + 1) % 4]
            if cnt[(min(a, b), max(a, b))] == 1:
                bnd.append((a, b))
    return bnd


def build_wing(mb, spine, loop, side, tag, seed=C.SEED):
    """Kok tupu + solidify edilmis zar kabugu + parmak uc penceleri."""
    w = C.WING
    mat_wing = mb.mat("M_Dragon_Wings")
    mat_body = mb.mat("M_Dragon_Body")
    mat_claw = mb.mat("M_Dragon_Horns_Claws")
    rect = uvmap.WINGS["wing_l" if side > 0 else "wing_r"]

    sk = wing_skeleton(spine, side)

    # ---------------- kok tupu: govde deliginden bilege ----------------
    center = Vector((0.0, 0.0, 0.0))
    for vi in loop:
        center += mb.verts[vi]
    center /= len(loop)
    cols = len(loop)

    path = [center]
    radii = [(w["humerus_r"][0] * 1.25, w["humerus_r"][0] * 1.25)]
    steps = 16
    for k in range(1, steps + 1):
        t = k / steps
        path.append(center.lerp(sk["elbow"], t))
        r = lerp(w["humerus_r"][0], w["humerus_r"][1], t)
        r *= 1.0 + 0.16 * math.exp(-0.5 * ((t - 1.0) / 0.18) ** 2)
        radii.append((r, r * 0.86))
    for k in range(1, steps + 1):
        t = k / steps
        path.append(sk["elbow"].lerp(sk["wrist"], t))
        r = lerp(w["forearm_r"][0], w["forearm_r"][1], t)
        r *= 1.0 + 0.12 * math.exp(-0.5 * ((t - 1.0) / 0.20) ** 2)
        radii.append((r, r * 0.84))

    up_w = Vector((0.0, 1.0, 0.0))
    angs, direction = loop_angles(mb, loop, center, sk["normal"], sk["chord"])
    a0 = angs[0]
    rel = [mb.verts[vi] - center for vi in loop]
    rings = [list(loop)]
    prev_r = None
    n = len(path)
    for j in range(1, n):
        t = j / (n - 1)
        d = (path[min(j + 1, n - 1)] - path[j - 1]).normalized()
        r = sk["normal"] - d * sk["normal"].dot(d)
        if prev_r is not None:
            r = prev_r - d * prev_r.dot(d)
        if r.length < 1e-5:
            r = up_w.cross(d)
        r.normalize()
        u = d.cross(r).normalized()
        prev_r = r
        rx, ry = radii[j]
        blend = smoothstep(0.0, 0.22, t)
        ring = []
        for i in range(cols):
            th = a0 + direction * TAU * i / cols
            circ = path[j] + r * (rx * math.cos(th)) + u * (ry * math.sin(th))
            shaped = path[j] + rel[i] * (1.0 - 0.4 * t)
            ring.append(mb.add_vert(shaped.lerp(circ, blend), "wing_" + tag))
        rings.append(ring)

    arm_rect = uvmap.sub(rect, 0.0, 0.0, 0.14, 1.0)
    for j in range(n - 1):
        mb.bridge_loops(rings[j], rings[j + 1],
                        (arm_rect[0], arm_rect[1] + (arm_rect[3] - arm_rect[1]) * j / (n - 1),
                         arm_rect[2], arm_rect[1] + (arm_rect[3] - arm_rect[1]) * (j + 1) / (n - 1)),
                        mat_body)
    mb.cap_ring(rings[-1], sk["wrist"] + sk["hand_dir"] * 0.10, (0.5, 0.97),
                arm_rect, mat_body, "wing_" + tag)

    # ---------------- zar tabakasi ----------------
    pos, quads, uvp, bonew = build_membrane_sheet(sk, side, seed)
    vn = _vertex_normals(pos, quads)
    thick = []
    for i in range(len(pos)):
        thick.append(w["membrane_thickness"] + w["bone_thickness"] * bonew[i])

    sheet_rect = uvmap.sub(rect, 0.16, 0.0, 1.0, 1.0)
    top_rect = uvmap.sub(sheet_rect, 0.0, 0.52, 1.0, 1.0)
    bot_rect = uvmap.sub(sheet_rect, 0.0, 0.0, 1.0, 0.48)

    top_idx, bot_idx = [], []
    for i, p in enumerate(pos):
        h = thick[i] * 0.5
        top_idx.append(mb.add_vert(p + vn[i] * h, "wingmem_" + tag))
        bot_idx.append(mb.add_vert(p - vn[i] * h, "wingmem_" + tag))

    def uv_of(i, rct):
        u, v = uvp[i]
        return (rct[0] + (rct[2] - rct[0]) * u, rct[1] + (rct[3] - rct[1]) * v)

    for q in quads:
        mb.add_face(tuple(top_idx[i] for i in q),
                    tuple(uv_of(i, top_rect) for i in q), mat_wing)
        mb.add_face(tuple(bot_idx[i] for i in reversed(q)),
                    tuple(uv_of(i, bot_rect) for i in reversed(q)), mat_wing)

    for (a, b) in _boundary_edges(quads):
        mb.add_face((top_idx[b], top_idx[a], bot_idx[a], bot_idx[b]),
                    (uv_of(b, top_rect), uv_of(a, top_rect),
                     uv_of(a, bot_rect), uv_of(b, bot_rect)), mat_wing)

    # ---------------- parmak uc penceleri ----------------
    rr = sk["chord"]
    base_cell = 16 if side > 0 else 20
    for k in range(4):
        tip = sk["origins"][k] + sk["dirs"][k] * sk["lens"][k]
        L = 0.42 - k * 0.055
        build_claw(mb, tip, sk["dirs"][k], sk["normal"], rr, L,
                   w["fingers"][k][2] * 2.6, mat_claw, "w" + tag,
                   base_cell + k, -999.0)

    return sk


def build_wings(mb, spine, holes, seed=C.SEED):
    out = {}
    out["L"] = build_wing(mb, spine, holes["wing_L"], 1.0, "l", seed)
    out["R"] = build_wing(mb, spine, holes["wing_R"], -1.0, "r", seed)
    return out
