"""On/arka bacaklar, ayak yastiklari, parmaklar, penceler.

Bacak tupu, govdede acilan gercek deligin sinir halkasindan baslar -> ic ice
gecme yok. Ilk %20'de dikdortgen delik kesitinden dairesel bacak kesitine
yumusak gecis yapilir (deformasyon loop'lari korunur).
"""

import math
from mathutils import Vector

from . import config as C
from . import uvmap
from .core import TAU, smoothstep, clamp, lerp


def loop_angles(mb, loop, center, ref_r, ref_u):
    """Sinir halkasinin aci dizisi + donus yonu."""
    angs = []
    for vi in loop:
        v = mb.verts[vi] - center
        angs.append(math.atan2(v.dot(ref_u), v.dot(ref_r)))
    # yonu belirle
    d = 0.0
    for i in range(len(angs)):
        a = angs[(i + 1) % len(angs)] - angs[i]
        while a > math.pi:
            a -= TAU
        while a < -math.pi:
            a += TAU
        d += a
    return angs, (1.0 if d >= 0 else -1.0)


def chain_path(origin, base_frame, chain, scale=1.0, steps_per=14):
    """Zinciri dunya uzayinda yol + yaricap listesine cevirir.

    base_frame: (lat_out, world_up, forward)
    """
    lat, up, fwd = base_frame
    pts = [Vector(origin)]
    radii = []
    joints = [Vector(origin)]
    cur = Vector(origin)
    for (name, L, pitch, yaw, r0, r1) in chain:
        p = math.radians(pitch)
        y = math.radians(yaw)
        d = (lat * (math.cos(p) * math.cos(y))
             + fwd * (math.cos(p) * math.sin(y))
             + up * math.sin(p)).normalized()
        for k in range(1, steps_per + 1):
            t = k / steps_per
            pts.append(cur + d * (L * scale * t))
        cur = cur + d * (L * scale)
        joints.append(cur.copy())
    # yaricaplar
    n_seg = len(chain)
    radii.append((chain[0][4], chain[0][4]))
    for si, (name, L, pitch, yaw, r0, r1) in enumerate(chain):
        for k in range(1, steps_per + 1):
            t = k / steps_per
            r = lerp(r0, r1, t)
            # eklem bolgesinde hafif sisme (hacim korumasi)
            joint_bulge = 1.0 + 0.14 * math.exp(-0.5 * ((t - 1.0) / 0.16) ** 2) \
                if si < n_seg - 1 else 1.0
            radii.append((r * joint_bulge, r * joint_bulge * 0.92))
    return pts, radii, joints


def build_leg(mb, spine, loop, side, spec, uv_leg, uv_foot, tag, ground_y=0.0,
              seed=C.SEED):
    """Tek bacagi uretir. loop: govde deliginin sinir halkasi (40 vertex)."""
    mat_body = mb.mat("M_Dragon_Body")
    mat_claw = mb.mat("M_Dragon_Horns_Claws")

    center = Vector((0.0, 0.0, 0.0))
    for vi in loop:
        center += mb.verts[vi]
    center /= len(loop)

    p, right, up, tan = spine.frame(spec["attach_s"])
    lat = (right * side).normalized()
    lat = Vector((lat.x, lat.y * 0.25, lat.z)).normalized()
    wup = Vector((0.0, 1.0, 0.0))
    fwd = Vector((-tan.x, 0.0, -tan.z)).normalized()
    frame = (lat, wup, fwd)

    # --- bacak uzunlugunu ayarla: taban tam yere bassin ---
    pts, radii, joints = chain_path(center, frame, spec["chain"], 1.0)
    sole_natural = min(q.y for q in pts) - spec["chain"][-1][5] * 0.7
    drop_needed = center.y - (ground_y + spec["chain"][-1][5] * 1.15)
    drop_natural = center.y - sole_natural
    raw = drop_needed / max(drop_natural, 1e-6)
    scale = clamp(raw, 0.60, 1.55)
    if abs(raw - scale) > 1e-6:
        print("  ! bacak %s olcek siniri: istenen %.3f -> %.3f" % (tag, raw, scale))
    pts, radii, joints = chain_path(center, frame, spec["chain"], scale)

    # --- tup: sinir halkasindan dairesel kesite gecis ---
    n = len(pts)
    cols = len(loop)
    rings = [list(loop)]
    ref_r = lat
    ref_u = wup
    angs, direction = loop_angles(mb, loop, center, ref_r, ref_u)
    a0 = angs[0]
    rel = [mb.verts[vi] - center for vi in loop]

    prev_r = None
    for j in range(1, n):
        t = j / (n - 1)
        d = (pts[min(j + 1, n - 1)] - pts[j - 1]).normalized()
        r = wup.cross(d)
        if r.length < 1e-5:
            r = fwd.cross(d)
        if prev_r is not None:
            r = prev_r - d * prev_r.dot(d)
            if r.length < 1e-5:
                r = wup.cross(d)
        r.normalize()
        u = d.cross(r).normalized()
        prev_r = r
        rx, ry = radii[j]
        blend = smoothstep(0.0, 0.20, t)
        ring = []
        for i in range(cols):
            th = a0 + direction * TAU * i / cols
            circ = pts[j] + r * (rx * math.cos(th)) + u * (rx * math.sin(th))
            # baslangicta delik sinirinin sekli tasinir
            shaped = pts[j] + rel[i] * (1.0 - 0.35 * t)
            co = shaped.lerp(circ, blend)
            ring.append(mb.add_vert(co, "leg_" + tag))
        rings.append(ring)

    u0, v0, u1, v1 = uv_leg
    for j in range(n - 1):
        mb.bridge_loops(rings[j], rings[j + 1],
                        (u0, v0 + (v1 - v0) * (j / (n - 1)) * 0.72,
                         u1, v0 + (v1 - v0) * ((j + 1) / (n - 1)) * 0.72),
                        mat_body)

    # --- ayak yastigi ---
    ankle_ring = rings[-1]
    ankle_pos = pts[-1]
    fdir = Vector((fwd.x, 0.0, fwd.z)).normalized()
    foot = build_foot(mb, ankle_ring, ankle_pos, fdir, wup, lat, spec,
                      uv_foot, tag, ground_y, seed)
    # --- parmaklar + penceler ---
    toes = build_toes(mb, foot, spec, uv_foot, tag, ground_y, seed,
                      mat_body, mat_claw)
    return {"joints": joints, "sole_y": foot["sole_y"], "foot": foot,
            "toes": toes, "ankle": pts[-1], "fdir": fdir}


def build_foot(mb, ankle_ring, ankle_pos, fdir, wup, lat, spec, uv, tag,
               ground_y, seed):
    """Bilekten yere kadar yassilasan ayak pedi."""
    mat_body = mb.mat("M_Dragon_Body")
    cols = len(ankle_ring)
    L = spec["foot_len"]
    steps = 10
    rings = [list(ankle_ring)]
    base_r = spec["chain"][-1][5]
    # bilekten yere inen + one uzanan yol
    drop = max(0.05, ankle_pos.y - ground_y - base_r * 0.55)
    pts = []
    for k in range(1, steps + 1):
        t = k / steps
        y = ankle_pos.y - drop * (t ** 0.78)
        f = L * (t ** 1.25)
        pts.append(Vector((ankle_pos.x + fdir.x * f, y, ankle_pos.z + fdir.z * f)))

    prev = ankle_pos
    for k, ctr in enumerate(pts):
        t = (k + 1) / steps
        rx = base_r * lerp(1.0, 1.72, t ** 0.85)          # yanlara yayilir
        ry = base_r * lerp(1.0, 0.46, t ** 0.9)           # dikeyde yassilasir
        ring = []
        rr = Vector((fdir.z, 0.0, -fdir.x)).normalized()
        for i in range(cols):
            th = TAU * i / cols
            x = rx * math.cos(th)
            y = ry * math.sin(th)
            # taban duzlestirme + yastikcik kabartisi
            if y < 0:
                y *= 0.62
                pad = 0.055 * max(0.0, math.cos(th * 3.0)) * t
                y -= pad * base_r * 2.2
            ring.append(mb.add_vert(ctr + rr * x + wup * y, "foot_" + tag))
        rings.append(ring)
        prev = ctr

    u0, v0, u1, v1 = uv
    for j in range(len(rings) - 1):
        mb.bridge_loops(rings[j], rings[j + 1],
                        (u0, v0 + (v1 - v0) * (0.10 + 0.55 * j / (len(rings) - 1)),
                         u1, v0 + (v1 - v0) * (0.10 + 0.55 * (j + 1) / (len(rings) - 1))),
                        mat_body)
    front = pts[-1] + Vector((fdir.x, 0.0, fdir.z)) * (base_r * 0.55)
    mb.cap_ring(rings[-1], front, (0.5, 0.72),
                (u0, v0 + (v1 - v0) * 0.66, u1, v0 + (v1 - v0) * 0.74),
                mat_body, "foot_" + tag)
    sole_y = min(mb.verts[vi].y for r in rings for vi in r)
    return {"front": front, "center": pts[-1], "fdir": fdir, "wup": wup,
            "lat": lat, "base_r": base_r, "sole_y": sole_y, "rings": rings}


def build_toes(mb, foot, spec, uv, tag, ground_y, seed, mat_body, mat_claw):
    """Parmaklar (kapali tup) + kavisli penceler."""
    fdir = foot["fdir"]
    wup = foot["wup"]
    rr = Vector((fdir.z, 0.0, -fdir.x)).normalized()
    base_r = foot["base_r"]
    u0, v0, u1, v1 = uv
    toe_info = []
    for ti in range(spec["toe_count"]):
        L = spec["toe_len"][ti]
        yaw = math.radians(spec["toe_yaw"][ti])
        d = (fdir * math.cos(yaw) + rr * math.sin(yaw)).normalized()
        start = foot["center"] + d * (base_r * 0.55) + wup * (base_r * 0.10)
        r0 = base_r * 0.42 * (0.82 + 0.22 * math.cos(yaw))
        r1 = base_r * 0.24 * (0.82 + 0.22 * math.cos(yaw))
        steps = 12
        cols = 12
        rings = []
        for k in range(steps + 1):
            t = k / steps
            ctr = start + d * (L * t)
            ctr.y = max(ground_y + r1 * 0.55,
                        start.y - (start.y - (ground_y + r1 * 0.6)) * (t ** 1.4))
            r = lerp(r0, r1, t ** 0.85)
            # eklem bogumu
            knuck = 1.0 + 0.20 * math.exp(-0.5 * ((t - 0.40) / 0.12) ** 2) \
                + 0.16 * math.exp(-0.5 * ((t - 0.74) / 0.10) ** 2)
            ring = []
            for i in range(cols):
                th = TAU * i / cols
                x = r * knuck * math.cos(th)
                y = r * knuck * 0.86 * math.sin(th)
                if y < 0:
                    y *= 0.70
                ring.append(mb.add_vert(ctr + rr * x + wup * y, "toe_" + tag))
            rings.append(ring)
        cell = uvmap.sub(uv, 0.06 + ti * 0.23, 0.78, 0.06 + ti * 0.23 + 0.20, 0.99)
        for j in range(steps):
            mb.bridge_loops(rings[j], rings[j + 1],
                            (cell[0], cell[1] + (cell[3] - cell[1]) * j / steps,
                             cell[2], cell[1] + (cell[3] - cell[1]) * (j + 1) / steps),
                            mat_body)
        mb.cap_ring(rings[0], start - d * (r0 * 0.5), (0.5, 0.04), cell,
                    mat_body, "toe_" + tag)
        tip_center = rings[-1]
        tip_pos = Vector((0.0, 0.0, 0.0))
        for vi in tip_center:
            tip_pos += mb.verts[vi]
        tip_pos /= len(tip_center)
        mb.cap_ring(tip_center, tip_pos + d * (r1 * 0.4), (0.5, 0.96), cell,
                    mat_body, "toe_" + tag, flip=True)
        # --- pence ---
        base = {"fl": 0, "fr": 4, "rl": 8, "rr": 12}[tag]
        build_claw(mb, tip_pos, d, wup, rr, spec["claw_len"][ti], r1 * 1.12,
                   mat_claw, tag, base + ti, ground_y)
        toe_info.append({"start": start, "tip": tip_pos, "dir": d})
    return toe_info


def build_claw(mb, origin, d, wup, rr, length, base_r, mat, tag, cell_index,
               ground_y):
    """Uzun, kavisli, asinmis pence. cell_index: UV atlasindaki benzersiz hucre."""
    steps, cols = 12, 10
    rect = uvmap.cell(uvmap.HORNS["claw_grid"], uvmap.CLAW_CELLS, cell_index)
    rings = []
    # kavis: asagi + hafif ice
    curve = (-wup * 0.55 + d * 0.10).normalized()
    for k in range(steps + 1):
        t = k / steps
        ctr = origin + d * (length * t) + curve * (length * 0.52 * (t ** 1.9))
        if ground_y > -900.0:
            ctr.y = max(ctr.y, ground_y + base_r * 0.55)
        r = base_r * (1.0 - t) ** 0.72
        r = max(r, base_r * 0.045)
        ring = []
        for i in range(cols):
            th = TAU * i / cols
            # kesit: ustten basik, altta keskin (gercek pence kesiti)
            x = r * math.cos(th) * 0.80
            y = r * math.sin(th)
            if y < 0:
                y *= 1.28
            q = ctr + rr * x + wup * y
            if ground_y > -900.0:
                q.y = max(q.y, ground_y + 0.006)
            ring.append(mb.add_vert(q, "claw_" + tag))
        rings.append(ring)
    for j in range(steps):
        mb.bridge_loops(rings[j], rings[j + 1],
                        (rect[0], rect[1] + (rect[3] - rect[1]) * j / steps,
                         rect[2], rect[1] + (rect[3] - rect[1]) * (j + 1) / steps),
                        mat)
    mb.cap_ring(rings[0], origin - d * (base_r * 0.35), (0.5, 0.04), rect, mat,
                "claw_" + tag)
    tip = origin + d * (length * 1.03) + curve * (length * 0.56)
    if ground_y > -900.0:
        tip.y = max(tip.y, ground_y + 0.006)
    mb.cap_ring(rings[-1], tip, (0.5, 0.97), rect, mat, "claw_" + tag, flip=True)


def build_all_legs(mb, spine, holes, ground_y=0.0, seed=C.SEED):
    out = {}
    jobs = [
        ("legF_L", C.FRONT_LEG,  1.0, uvmap.BODY["leg_fl"], uvmap.BODY["foot_fl"], "fl"),
        ("legF_R", C.FRONT_LEG, -1.0, uvmap.BODY["leg_fr"], uvmap.BODY["foot_fr"], "fr"),
        ("legR_L", C.REAR_LEG,   1.0, uvmap.BODY["leg_rl"], uvmap.BODY["foot_rl"], "rl"),
        ("legR_R", C.REAR_LEG,  -1.0, uvmap.BODY["leg_rr"], uvmap.BODY["foot_rr"], "rr"),
    ]
    for key, spec, side, uvl, uvf, tag in jobs:
        out[key] = build_leg(mb, spine, holes[key], side, spec, uvl, uvf, tag,
                             ground_y, seed)
    return out
