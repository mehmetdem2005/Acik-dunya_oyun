"""Armature (iskelet) kurulumu + olculmus skinning.

Eklemler goz karariyla degil, geometriyi ureten parametrelerden (omurga yay
konumu, uzuv zincir eklemleri, kanat iskeleti) DOGRUDAN alinir -> kayma yok.
Agirliklar numpy ile kemik-segmenti mesafesine gore, bolge kapisiyla (region
gating) hesaplanir; vertex basina en fazla 4 kemik, toplam 1.0.
"""

import math
import numpy as np
from mathutils import Vector, Matrix

from . import config as C

# ------------------------------------------------------------------
# omurga bone sinirlari (s degerleri)
# ------------------------------------------------------------------
SPINE_CHAIN = [
    ("Pelvis",   0.615, 0.575),
    ("Spine_01", 0.575, 0.510),
    ("Spine_02", 0.510, 0.445),
    ("Spine_03", 0.445, 0.385),
    ("Chest",    0.385, 0.331),
    ("Neck_01",  0.331, 0.281),
    ("Neck_02",  0.281, 0.231),
    ("Neck_03",  0.231, 0.176),
    ("Neck_04",  0.176, 0.119),
    ("Head",     0.119, 0.020),
]
SPINE_PARENT = {
    "Pelvis": "Root_Motion", "Spine_01": "Pelvis", "Spine_02": "Spine_01",
    "Spine_03": "Spine_02", "Chest": "Spine_03", "Neck_01": "Chest",
    "Neck_02": "Neck_01", "Neck_03": "Neck_02", "Neck_04": "Neck_03",
    "Head": "Neck_04",
}
TAIL_S = [0.615, 0.663, 0.711, 0.758, 0.804, 0.849, 0.893, 0.936, 0.978, 1.0]


class BoneDef:
    __slots__ = ("name", "parent", "head", "tail", "up", "connect")

    def __init__(self, name, parent, head, tail, up=(0, 1, 0), connect=False):
        self.name = name
        self.parent = parent
        self.head = Vector(head)
        self.tail = Vector(tail)
        self.up = Vector(up)
        self.connect = connect


def build_skeleton(spine, legs, wings, jaw, eyes):
    """Tum deform kemiklerini dunya koordinatlarinda tanimlar."""
    B = []
    ground = Vector((0.0, 0.0, 0.0))
    root_z = spine.pos(0.594).z
    B.append(BoneDef("Dragon_Root", None, (0.0, 0.0, root_z),
                     (0.0, 0.55, root_z)))
    B.append(BoneDef("Root_Motion", "Dragon_Root", (0.0, 0.0, root_z),
                     (0.0, 0.40, root_z)))

    # --- omurga zinciri ---
    for name, s0, s1 in SPINE_CHAIN:
        p0 = spine.pos(s0)
        p1 = spine.pos(s1)
        B.append(BoneDef(name, SPINE_PARENT[name], p0, p1, connect=True))

    # --- kuyruk ---
    for i in range(len(TAIL_S) - 1):
        nm = "Tail_Tip" if i == len(TAIL_S) - 2 else "Tail_%02d" % (i + 1)
        par = "Pelvis" if i == 0 else ("Tail_%02d" % i)
        B.append(BoneDef(nm, par, spine.pos(TAIL_S[i]), spine.pos(TAIL_S[i + 1]),
                         connect=(i > 0)))

    # --- cene / dil ---
    jo, jf = jaw["origin"], jaw["fwd"]
    B.append(BoneDef("Jaw", "Head", jo, jo + jf * (C.JAW_LENGTH * 0.92),
                     up=jaw["up"]))
    t0 = jo + jf * 0.16 + jaw["up"] * 0.045
    B.append(BoneDef("Tongue_01", "Jaw", t0, t0 + jf * (C.JAW_LENGTH * 0.36)))
    B.append(BoneDef("Tongue_02", "Tongue_01", t0 + jf * (C.JAW_LENGTH * 0.36),
                     t0 + jf * (C.JAW_LENGTH * 0.70)))

    # --- goz / goz kapagi / yuz ---
    for side, sfx in ((1.0, "L"), (-1.0, "R")):
        e = eyes[sfx]
        d = eyes["dir_" + sfx]
        B.append(BoneDef("Eye_" + sfx, "Head", e, e + d * 0.16))
        B.append(BoneDef("Eyelid_" + sfx, "Head", e + Vector((0, 0.02, 0)),
                         e + d * 0.13 + Vector((0, 0.09, 0))))
    # sinirli yuz kemikleri (burun kivirma / dudak kaldirma / kas kemigi)
    for side, sfx in ((1.0, "L"), (-1.0, "R")):
        n0 = eyes["nostril_" + sfx]
        B.append(BoneDef("Nostril_" + sfx, "Head", n0, n0 + Vector((0.0, 0.10, -0.05))))
        l0 = eyes["lip_" + sfx]
        B.append(BoneDef("LipUpper_" + sfx, "Head", l0, l0 + Vector((0.0, 0.11, 0.0))))
        b0 = eyes["brow_" + sfx]
        B.append(BoneDef("Brow_" + sfx, "Head", b0, b0 + Vector((0.0, 0.12, 0.0))))

    # --- bacaklar ---
    leg_defs = [
        ("legF_L", "L", "Front", "Shoulder_L", "Chest"),
        ("legF_R", "R", "Front", "Shoulder_R", "Chest"),
        ("legR_L", "L", "Rear", "Hip_L", "Pelvis"),
        ("legR_R", "R", "Rear", "Hip_R", "Pelvis"),
    ]
    for key, sfx, pre, root_name, parent in leg_defs:
        j = legs[key]["joints"]
        B.append(BoneDef(root_name, parent, j[0], j[1]))
        B.append(BoneDef("%sLeg_%s" % (pre, sfx), root_name, j[1], j[2], connect=True))
        B.append(BoneDef("%sLegLow_%s" % (pre, sfx), "%sLeg_%s" % (pre, sfx),
                         j[2], j[3], connect=True))
        B.append(BoneDef("%sAnkle_%s" % (pre, sfx), "%sLegLow_%s" % (pre, sfx),
                         j[3], j[4], connect=True))
        foot = legs[key]["foot"]
        B.append(BoneDef("%sFoot_%s" % (pre, sfx), "%sAnkle_%s" % (pre, sfx),
                         j[4], foot["center"], connect=True))
        for ti, t in enumerate(legs[key]["toes"]):
            B.append(BoneDef("%sToe%02d_%s" % (pre, ti + 1, sfx),
                             "%sFoot_%s" % (pre, sfx), t["start"], t["tip"]))

    # --- kanatlar ---
    for sfx, key in (("L", "L"), ("R", "R")):
        sk = wings[key]
        sh, el, wr = sk["shoulder"], sk["elbow"], sk["wrist"]
        root_head = sh - sk["hum_dir"] * 0.55
        B.append(BoneDef("WingRoot_" + sfx, "Chest", root_head, sh,
                         up=sk["normal"]))
        B.append(BoneDef("WingArm_" + sfx, "WingRoot_" + sfx, sh, el,
                         up=sk["normal"], connect=True))
        B.append(BoneDef("WingArmTwist_" + sfx, "WingArm_" + sfx,
                         sh.lerp(el, 0.42), sh.lerp(el, 0.86), up=sk["normal"]))
        B.append(BoneDef("WingForearm_" + sfx, "WingArm_" + sfx, el, wr,
                         up=sk["normal"], connect=True))
        hand_end = wr + sk["hand_dir"] * (C.WING["wrist"] + 0.30)
        B.append(BoneDef("WingWrist_" + sfx, "WingForearm_" + sfx, wr, hand_end,
                         up=sk["normal"], connect=True))
        for k in range(4):
            o = sk["origins"][k]
            d = sk["dirs"][k]
            L = sk["lens"][k]
            n1 = "WingFinger%02d_%s" % (k + 1, sfx)
            n2 = "WingFinger%02db_%s" % (k + 1, sfx)
            B.append(BoneDef(n1, "WingWrist_" + sfx, o, o + d * (L * 0.52),
                             up=sk["normal"]))
            B.append(BoneDef(n2, n1, o + d * (L * 0.52), o + d * L,
                             up=sk["normal"], connect=True))
        # zar katlanmasini kontrol eden yardimci kemik
        B.append(BoneDef("WingMembrane_" + sfx, "WingRoot_" + sfx, sh,
                         sk["anchor"], up=sk["normal"]))
    return B


# ==================================================================
# BLENDER ARMATURE
# ==================================================================
def create_armature(bonedefs, name="Dragon_Skeleton"):
    import bpy
    arm_data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    made = {}
    for bd in bonedefs:
        b = eb.new(bd.name)
        h, t = bd.head.copy(), bd.tail.copy()
        if (t - h).length < 1e-4:
            t = h + Vector((0.0, 0.05, 0.0))
        b.head = h
        b.tail = t
        b.use_deform = True
        made[bd.name] = b
    for bd in bonedefs:
        if bd.parent:
            made[bd.name].parent = made[bd.parent]
            if bd.connect and (made[bd.parent].tail - made[bd.name].head).length < 1e-4:
                made[bd.name].use_connect = True
    for bd in bonedefs:
        try:
            made[bd.name].align_roll(bd.up)
        except Exception:
            pass
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm


# ==================================================================
# BOLGE KAPISI (region gating)
# ==================================================================
def _spine_names():
    return [n for n, _, _ in SPINE_CHAIN]


def _tail_names():
    return ["Tail_%02d" % i for i in range(1, 9)] + ["Tail_Tip"]


def gating(bonedefs):
    """bolge etiketi -> izin verilen kemik adlari."""
    names = [b.name for b in bonedefs]
    spine = _spine_names()
    tail = _tail_names()
    core = spine + tail + ["Shoulder_L", "Shoulder_R", "Hip_L", "Hip_R",
                           "WingRoot_L", "WingRoot_R", "Root_Motion"]
    head_grp = ["Head", "Neck_04", "Neck_03"] + \
        [n for n in names if n.startswith(("Eye_", "Eyelid_", "Nostril_",
                                           "LipUpper_", "Brow_"))]
    jaw_grp = ["Jaw", "Head"]
    tongue_grp = ["Tongue_01", "Tongue_02", "Jaw"]

    def leg(pre, sfx, root):
        return [root, "%sLeg_%s" % (pre, sfx), "%sLegLow_%s" % (pre, sfx),
                "%sAnkle_%s" % (pre, sfx), "%sFoot_%s" % (pre, sfx)] + \
            ["%sToe%02d_%s" % (pre, i, sfx) for i in range(1, 5)]

    def wing(sfx):
        out = ["WingRoot_" + sfx, "WingArm_" + sfx, "WingArmTwist_" + sfx,
               "WingForearm_" + sfx, "WingWrist_" + sfx,
               "WingMembrane_" + sfx, "Chest"]
        for k in range(4):
            out += ["WingFinger%02d_%s" % (k + 1, sfx),
                    "WingFinger%02db_%s" % (k + 1, sfx)]
        return out

    g = {
        "body": core, "ventral": core, "crest": core, "frill": core,
        "head": head_grp + ["Neck_04"], "horn_l": head_grp, "horn_r": head_grp,
        "teeth_u": ["Head"], "eye_l": ["Eye_L"], "eye_r": ["Eye_R"],
        "jaw": jaw_grp, "teeth_l": ["Jaw"], "tongue": tongue_grp,
    }
    for pre, sfx, root, tag in (("Front", "L", "Shoulder_L", "fl"),
                                ("Front", "R", "Shoulder_R", "fr"),
                                ("Rear", "L", "Hip_L", "rl"),
                                ("Rear", "R", "Hip_R", "rr")):
        ln = leg(pre, sfx, root) + ["Chest" if pre == "Front" else "Pelvis"]
        for p in ("leg_", "foot_", "toe_", "claw_"):
            g[p + tag] = ln
    for sfx, tag in (("L", "l"), ("R", "r")):
        wn = wing(sfx)
        g["wing_" + tag] = wn
        g["wingmem_" + tag] = wn
        g["claw_w" + tag] = wn
    return g


# ==================================================================
# AGIRLIK HESABI
# ==================================================================
def compute_weights(mb, bonedefs, max_infl=4):
    """(N, max_infl) kemik indeksi + agirlik matrisleri dondurur."""
    names = [b.name for b in bonedefs]
    idx_of = {n: i for i, n in enumerate(names)}
    heads = np.array([[b.head.x, b.head.y, b.head.z] for b in bonedefs], np.float32)
    tails = np.array([[b.tail.x, b.tail.y, b.tail.z] for b in bonedefs], np.float32)
    lens = np.linalg.norm(tails - heads, axis=1)
    lens = np.maximum(lens, 1e-4)

    P = np.array([[v.x, v.y, v.z] for v in mb.verts], np.float32)
    N = P.shape[0]
    gmap = gating(bonedefs)

    # bolge -> vertex maskesi
    regions = mb.regions
    uniq = {}
    for i, r in enumerate(regions):
        uniq.setdefault(r, []).append(i)

    W = np.zeros((N, len(names)), np.float32)

    for reg, vidx in uniq.items():
        allowed = gmap.get(reg)
        if allowed is None:
            allowed = gmap["body"]
        vi = np.array(vidx, np.int64)
        pts = P[vi]
        for bn in allowed:
            bi = idx_of.get(bn)
            if bi is None:
                continue
            a = heads[bi]
            b = tails[bi]
            ab = b - a
            L2 = float(ab.dot(ab))
            t = np.clip(((pts - a) @ ab) / max(L2, 1e-8), 0.0, 1.0)
            proj = a[None, :] + t[:, None] * ab[None, :]
            d = np.linalg.norm(pts - proj, axis=1)
            # etki yaricapi: kemik boyuyla olceklenir
            sigma = 0.55 * lens[bi] + 0.18
            w = np.exp(-(d / sigma) ** 2)
            W[vi, bi] = np.maximum(W[vi, bi], w)

    # --- en guclu max_infl kemik ---
    order = np.argsort(-W, axis=1)[:, :max_infl]
    vals = np.take_along_axis(W, order, axis=1)
    ssum = vals.sum(axis=1, keepdims=True)
    # hicbir kemige baglanmayan vertex kalmasin
    dead = (ssum[:, 0] < 1e-8)
    if dead.any():
        d_all = np.linalg.norm(P[dead][:, None, :] - heads[None, :, :], axis=2)
        nearest = np.argmin(d_all, axis=1)
        order[dead, 0] = nearest
        vals[dead, :] = 0.0
        vals[dead, 0] = 1.0
        ssum[dead] = 1.0
    vals = vals / np.maximum(ssum, 1e-8)
    return order, vals, names


def apply_weights(obj, order, vals, names, quant=400):
    """Vertex gruplarini toplu (kuantalanmis) yazar - tek tek yazmaktan cok hizli."""
    groups = {}
    for n in names:
        groups[n] = obj.vertex_groups.new(name=n)
    N = order.shape[0]
    K = order.shape[1]
    buckets = {}
    q = np.clip((vals * quant + 0.5).astype(np.int32), 0, quant)
    for k in range(K):
        oo = order[:, k]
        qq = q[:, k]
        keep = qq > 0
        for bi in np.unique(oo[keep]):
            m = keep & (oo == bi)
            qs = qq[m]
            vs = np.nonzero(m)[0]
            for level in np.unique(qs):
                sel = vs[qs == level]
                buckets.setdefault((int(bi), int(level)), []).extend(sel.tolist())
    for (bi, level), vlist in buckets.items():
        groups[names[bi]].add(vlist, level / quant, 'ADD')
    return groups


def bind(obj, arm):
    import bpy
    mod = obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = arm
    mod.use_vertex_groups = True
    obj.parent = arm
    obj.matrix_parent_inverse = arm.matrix_world.inverted()
    return mod


# ==================================================================
# FK / IK (animasyon icin, saf Python - Blender'a bagimli degil)
# ==================================================================
class Kinematics:
    """Rest matrislerinden FK zinciri; pose local rotasyonlariyla degerlendirir."""

    def __init__(self, bonedefs):
        self.defs = {b.name: b for b in bonedefs}
        self.order = [b.name for b in bonedefs]
        self.parent = {b.name: b.parent for b in bonedefs}
        self.rest_world = {}
        self.rest_local = {}
        for b in bonedefs:
            self.rest_world[b.name] = self._bone_matrix(b)
        for b in bonedefs:
            if b.parent:
                self.rest_local[b.name] = (self.rest_world[b.parent].inverted()
                                           @ self.rest_world[b.name])
            else:
                self.rest_local[b.name] = self.rest_world[b.name].copy()

    @staticmethod
    def _bone_matrix(b):
        y = (b.tail - b.head)
        if y.length < 1e-6:
            y = Vector((0.0, 1.0, 0.0))
        y.normalize()
        up = b.up.normalized() if b.up.length > 1e-6 else Vector((0.0, 1.0, 0.0))
        x = y.cross(up)
        if x.length < 1e-5:
            x = y.cross(Vector((1.0, 0.0, 0.0)))
            if x.length < 1e-5:
                x = y.cross(Vector((0.0, 0.0, 1.0)))
        x.normalize()
        z = x.cross(y).normalized()
        m = Matrix((
            (x.x, y.x, z.x, b.head.x),
            (x.y, y.y, z.y, b.head.y),
            (x.z, y.z, z.z, b.head.z),
            (0.0, 0.0, 0.0, 1.0),
        ))
        return m

    def evaluate(self, pose_local):
        """pose_local: {ad: Matrix (4x4 local delta)} -> {ad: dunya matrisi}."""
        out = {}
        for n in self.order:
            d = pose_local.get(n)
            loc = self.rest_local[n] @ d if d is not None else self.rest_local[n]
            p = self.parent[n]
            out[n] = (out[p] @ loc) if p else loc
        return out

    def head_world(self, world, name):
        m = world[name]
        return Vector((m[0][3], m[1][3], m[2][3]))

    def tail_world(self, world, name):
        b = self.defs[name]
        L = (b.tail - b.head).length
        m = world[name]
        y = Vector((m[0][1], m[1][1], m[2][1]))
        return self.head_world(world, name) + y * L


def two_bone_ik(root, target, L1, L2, pole):
    """Iki kemikli IK: (orta_eklem, uc) dunya pozisyonlari."""
    d = target - root
    dist = d.length
    dist = max(min(dist, (L1 + L2) * 0.999), abs(L1 - L2) + 1e-4)
    dirv = d.normalized() if d.length > 1e-8 else Vector((0.0, -1.0, 0.0))
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2.0 * dist)
    h2 = max(L1 * L1 - a * a, 0.0)
    h = math.sqrt(h2)
    p = Vector(pole) - dirv * Vector(pole).dot(dirv)
    if p.length < 1e-6:
        p = dirv.cross(Vector((1.0, 0.0, 0.0)))
        if p.length < 1e-6:
            p = dirv.cross(Vector((0.0, 0.0, 1.0)))
    p.normalize()
    mid = root + dirv * a + p * h
    end = root + dirv * dist
    return mid, end


def aim_matrix(head, tail_dir, up_hint):
    """Verilen yon ve up ile kemik dunya matrisi (Blender: Y = kemik ekseni)."""
    y = Vector(tail_dir).normalized()
    up = Vector(up_hint)
    x = y.cross(up)
    if x.length < 1e-5:
        x = y.cross(Vector((1.0, 0.0, 0.0)))
        if x.length < 1e-5:
            x = y.cross(Vector((0.0, 0.0, 1.0)))
    x.normalize()
    z = x.cross(y).normalized()
    return Matrix((
        (x.x, y.x, z.x, head.x),
        (x.y, y.y, z.y, head.y),
        (x.z, y.z, z.z, head.z),
        (0.0, 0.0, 0.0, 1.0),
    ))
