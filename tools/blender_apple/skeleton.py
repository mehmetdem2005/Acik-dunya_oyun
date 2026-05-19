"""Pass 1 — iskelet: ozyinelemeli dal grafigi (cam pine_skeleton yansimasi).

Olgun elma agaci: kisa kalin budakli govde -> dusuk noktadan acilan
birkac ana scaffold -> ikincil/ucuncul dallar -> ince surgun. Dis dallar
yercekimiyle sarkar -> genis yuvarlak/semsiye tac (koni DEGIL).

build() ciktisi:
  stems : [ {pts:[Vector], radii:[float], depth:int, kind:str} ]
  tips  : [ {pos:Vector, dir:Vector, depth:int} ]   # surgun uclari (elma)
"""
import math, random
from mathutils import Vector, Quaternion

from . import config as C


def _rot(v, axis, ang):
    return (Quaternion(axis, ang) @ v).normalized()


def _grow(rng, stems, tips, start, dirn, length, r0, r1, depth):
    segs = C.BRANCH_SEGMENTS if depth > 0 else C.TRUNK_SEGMENTS
    pts = [start.copy()]
    radii = [r0]
    pos = start.copy()
    d = dirn.normalized()
    seg = length / segs
    # govde gnarl ekseni / dal wobble ekseni
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    for s in range(segs):
        f = (s + 1) / segs
        pos = pos + d * seg
        if depth == 0:
            # govde: hafif egim + budak kivrimi
            sway = math.sin(f * 3.1 + rng.random() * 6.28) * C.TRUNK_GNARL
            pos += side * sway * seg
            pos.x += C.TRUNK_LEAN * length * f * f
        else:
            # dal: ic kivrim + uclara dogru artan yercekimi sarkmasi
            g = C.DROOP * (0.15 + 0.85 * f) * (f * f) * (0.5 + 0.18 * depth)
            d = (d + Vector((0, 0, -g))).normalized()
            w = (rng.random() * 2 - 1) * C.WOBBLE
            d = _rot(d, side, w * (1.0 - 0.5 * f))
        pts.append(pos.copy())
        radii.append(r0 + (r1 - r0) * f)
    kind = "trunk" if depth == 0 else ("twig" if depth >= C.MAX_DEPTH - 1 else "branch")
    stems.append({"pts": pts, "radii": radii, "depth": depth, "kind": kind})
    tip_dir = (pts[-1] - pts[-2]).normalized()
    if depth >= C.MAX_DEPTH - 1:
        tips.append({"pos": pts[-1].copy(), "dir": tip_dir, "depth": depth})

    if depth >= C.MAX_DEPTH or length < 0.10:
        return
    # cocuk dallar: uca yakin ve ortada cik
    nch = rng.randint(*C.CHILD_PER) + (1 if depth == 0 else 0)
    az0 = rng.random() * 6.2831
    for i in range(nch):
        u = 0.55 + 0.42 * (i / max(nch - 1, 1))      # govde/dal boyunca cikis
        bi = min(int(u * segs), segs - 1)
        base = pts[bi]
        bdir = (pts[bi + 1] - pts[bi]).normalized() if bi + 1 < len(pts) else d
        if depth == 0:
            # govde -> scaffold: dikeyden 38-60 sapma, esit azimut
            elev = math.radians(rng.uniform(*C.SCAFFOLD_ELEV_DEG))
            az = az0 + (6.2831 / nch) * i + rng.uniform(-0.3, 0.3)
            cd = Vector((math.sin(elev) * math.cos(az),
                         math.sin(elev) * math.sin(az),
                         math.cos(elev))).normalized()
            clen = C.SCAFFOLD_LEN * rng.uniform(0.85, 1.12)
            cr0 = r1 * 0.82
        else:
            # alt dallar: ebeveynden disa ac, derinlikle daha yatay
            spread = math.radians(rng.uniform(28, 52))
            ax = bdir.cross(Vector((0, 0, 1))).normalized()
            if ax.length < 1e-4:
                ax = side
            cd = _rot(bdir, ax, spread)
            cd = _rot(cd, bdir, az0 + (6.2831 / nch) * i + rng.uniform(-0.4, 0.4))
            up = max(0.05, 0.55 - 0.10 * depth)
            cd = (cd + Vector((0, 0, up))).normalized()
            clen = length * rng.uniform(*C.LEN_FALLOFF)
            cr0 = radii[bi] * C.RAD_FALLOFF
        _grow(rng, stems, tips, base, cd, clen, cr0,
              max(cr0 * 0.30, 0.006), depth + 1)


def build(cfg=None):
    rng = random.Random(C.SEED)
    stems, tips = [], []
    _grow(rng, stems, tips, Vector((0, 0, 0)), Vector((0.04, 0, 1)),
          C.TRUNK_HEIGHT, C.TRUNK_RADIUS, C.TRUNK_TOP_RADIUS, 0)
    return {"stems": stems, "tips": tips}
