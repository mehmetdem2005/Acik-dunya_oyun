"""Cekirdek matematik + mesh insa katmani.

Buradaki her sey saf Python + mathutils; bpy'ye sadece to_object() dokunur.
Amac: her yuzey parametrik olarak quad uretilsin, UV uretim aninda atansin,
bolge etiketi (region) her vertex'e yazilsin -> rig ve texture bunu kullanir.
"""

import math
from mathutils import Vector, Matrix, Quaternion

TAU = math.tau


# ==================================================================
# 1. INTERPOLASYON
# ==================================================================
def pchip(table, x):
    """Monoton kubik Hermite interpolasyon (asma/overshoot yapmaz).

    table: [(x0, y0), (x1, y1), ...] artan x.
    """
    n = len(table)
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    xs = [p[0] for p in table]
    ys = [p[1] for p in table]
    i = 0
    for k in range(n - 1):
        if xs[k] <= x <= xs[k + 1]:
            i = k
            break
    h = xs[i + 1] - xs[i]
    if h <= 1e-12:
        return ys[i]
    # sekant egimleri
    def sec(k):
        return (ys[k + 1] - ys[k]) / (xs[k + 1] - xs[k])

    d = []
    for k in range(n):
        if k == 0:
            d.append(sec(0))
        elif k == n - 1:
            d.append(sec(n - 2))
        else:
            s0, s1 = sec(k - 1), sec(k)
            if s0 * s1 <= 0.0:
                d.append(0.0)
            else:
                w1 = 2.0 * (xs[k + 1] - xs[k]) + (xs[k] - xs[k - 1])
                w2 = (xs[k + 1] - xs[k]) + 2.0 * (xs[k] - xs[k - 1])
                d.append((w1 + w2) / (w1 / s0 + w2 / s1))
    t = (x - xs[i]) / h
    t2, t3 = t * t, t * t * t
    h00 = 2 * t3 - 3 * t2 + 1
    h10 = t3 - 2 * t2 + t
    h01 = -2 * t3 + 3 * t2
    h11 = t3 - t2
    return h00 * ys[i] + h10 * h * d[i] + h01 * ys[i + 1] + h11 * h * d[i + 1]


def pchip_multi(table, x, col):
    """Cok kolonlu tablodan tek kolon interpolasyonu."""
    return pchip([(row[0], row[col]) for row in table], x)


def smoothstep(a, b, x):
    if b - a < 1e-9:
        return 0.0 if x < a else 1.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


# ==================================================================
# 2. DETERMINISTIK GURULTU (noise)
# ==================================================================
def _hash3(i, j, k, seed):
    h = (i * 374761393 + j * 668265263 + k * 2147483647 + seed * 982451653) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF) / 16777215.0


def value_noise3(x, y, z, seed=0):
    """Trilineer value noise, 0..1."""
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    xf, yf, zf = x - xi, y - yi, z - zi
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    w = zf * zf * (3 - 2 * zf)
    c = {}
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                c[(dx, dy, dz)] = _hash3(xi + dx, yi + dy, zi + dz, seed)
    x00 = lerp(c[(0, 0, 0)], c[(1, 0, 0)], u)
    x10 = lerp(c[(0, 1, 0)], c[(1, 1, 0)], u)
    x01 = lerp(c[(0, 0, 1)], c[(1, 0, 1)], u)
    x11 = lerp(c[(0, 1, 1)], c[(1, 1, 1)], u)
    y0 = lerp(x00, x10, v)
    y1 = lerp(x01, x11, v)
    return lerp(y0, y1, w)


def fbm3(x, y, z, octaves=4, lac=2.03, gain=0.5, seed=0):
    total, amp, norm = 0.0, 1.0, 0.0
    fx, fy, fz = x, y, z
    for o in range(octaves):
        total += amp * (value_noise3(fx, fy, fz, seed + o * 7717) * 2.0 - 1.0)
        norm += amp
        amp *= gain
        fx *= lac
        fy *= lac
        fz *= lac
    return total / max(norm, 1e-9)


def cyl_noise(phi, s, freq_phi, freq_s, octaves=3, seed=0):
    """Silindirik yuzeyde dikissiz gurultu: phi yonunde periyodik."""
    ang = phi * freq_phi
    return fbm3(math.cos(ang) * 0.5 + 12.3, math.sin(ang) * 0.5 + 41.7,
                s * freq_s, octaves=octaves, seed=seed)


# ==================================================================
# 3. OMURGA EGRISI (arc-length parametrik, paralel tasima frame)
# ==================================================================
class Spine:
    """Yay uzunluguna gore parametrik omurga; s in [0,1] = burun -> kuyruk ucu."""

    def __init__(self, segments, steps=3000):
        total = sum(seg[1] for seg in segments)
        self.total = total
        # segment merkezlerinde pitch kontrol noktalari
        ctrl = []
        acc = 0.0
        ctrl.append((0.0, segments[0][2]))
        for name, L, pitch in segments:
            ctrl.append((acc + L * 0.5, pitch))
            acc += L
        ctrl.append((total, segments[-1][2]))
        ctrl.sort(key=lambda p: p[0])
        # ayni x'leri temizle
        clean = [ctrl[0]]
        for p in ctrl[1:]:
            if p[0] - clean[-1][0] > 1e-6:
                clean.append(p)
        self.pitch_table = clean

        # integrasyon
        ds = total / steps
        pos = Vector((0.0, 0.0, 0.0))
        self.pts = [pos.copy()]
        self.tans = []
        for i in range(steps):
            sc = (i + 0.5) * ds
            p = math.radians(pchip(self.pitch_table, sc))
            d = Vector((0.0, math.sin(p), math.cos(p)))
            self.tans.append(d.copy())
            pos = pos + d * ds
            self.pts.append(pos.copy())
        self.tans.append(self.tans[-1].copy())
        self.ds = ds
        self.steps = steps

        # paralel tasima frame'i (twist yok)
        up = Vector((0.0, 1.0, 0.0))
        self.rights = []
        self.ups = []
        prev_t = self.tans[0]
        r = prev_t.cross(up)
        if r.length < 1e-6:
            r = Vector((1.0, 0.0, 0.0))
        r.normalize()
        u = r.cross(prev_t).normalized()
        for i in range(len(self.tans)):
            t = self.tans[i]
            ax = prev_t.cross(t)
            if ax.length > 1e-9:
                ang = math.asin(clamp(ax.length, -1.0, 1.0))
                q = Quaternion(ax.normalized(), ang)
                r = q @ r
                u = q @ u
            r = (r - t * r.dot(t)).normalized()
            u = t.cross(r).normalized()
            self.rights.append(r.copy())
            self.ups.append(u.copy())
            prev_t = t
        self.offset = Vector((0.0, 0.0, 0.0))

    def _idx(self, s):
        f = clamp(s, 0.0, 1.0) * self.steps
        i = int(f)
        if i >= self.steps:
            i = self.steps - 1
        return i, f - i

    def pos(self, s):
        i, t = self._idx(s)
        return self.pts[i].lerp(self.pts[i + 1], t) + self.offset

    def tan(self, s):
        i, t = self._idx(s)
        return self.tans[i].lerp(self.tans[min(i + 1, self.steps)], t).normalized()

    def frame(self, s):
        """(pos, right, up, tangent) - right = +X tarafi, up = dorsal."""
        i, t = self._idx(s)
        j = min(i + 1, self.steps)
        p = self.pts[i].lerp(self.pts[j], t) + self.offset
        tg = self.tans[i].lerp(self.tans[j], t).normalized()
        r = self.rights[i].lerp(self.rights[j], t)
        r = (r - tg * r.dot(tg)).normalized()
        u = tg.cross(r).normalized()
        # +X sagda olsun (tangent +Z geri yon oldugundan cross duzeltmesi)
        if r.x < 0:
            r = -r
            u = tg.cross(r).normalized()
        if u.y < 0:
            u = -u
        return p, r, u, tg

    def translate(self, v):
        self.offset = self.offset + Vector(v)


# ==================================================================
# 4. MESH BUILDER
# ==================================================================
class MeshBuilder:
    """Vertex/face/UV/materyal/bolge biriktirici."""

    def __init__(self, name):
        self.name = name
        self.verts = []          # Vector
        self.regions = []        # str, vertex basina
        self.faces = []          # (i0,i1,i2,i3) veya (i0,i1,i2)
        self.face_uv = []        # kose basina (u,v)
        self.face_mat = []       # materyal slot indeksi
        self.groups = {}         # ad -> {vidx: agirlik} (solidify maskesi vb.)
        self.mat_names = []      # slot sirasi

    # -- materyal --
    def mat(self, name):
        if name not in self.mat_names:
            self.mat_names.append(name)
        return self.mat_names.index(name)

    # -- vertex --
    def add_vert(self, co, region="body"):
        self.verts.append(Vector(co))
        self.regions.append(region)
        return len(self.verts) - 1

    def add_face(self, idx, uvs, mat_idx):
        self.faces.append(tuple(idx))
        self.face_uv.append(tuple(tuple(u) for u in uvs))
        self.face_mat.append(mat_idx)

    def set_group(self, name, vidx, w):
        self.groups.setdefault(name, {})[vidx] = w

    def vcount(self):
        return len(self.verts)

    def tri_count(self):
        return sum(2 if len(f) == 4 else 1 for f in self.faces)

    # ------------------------------------------------------------------
    # 4.1 Tup / grid uretimi
    # ------------------------------------------------------------------
    def add_grid(self, pts, cols, rows, uv_rect, mat_idx, region,
                 wrap_u=False, flip=False, uv_flip_v=False):
        """pts: (rows+1) x (cols[+1]) vertex indeksleri (satir-major liste listesi).

        wrap_u=True ise her satirin son elemani ilk elemana baglanir (kapali tup).
        uv_rect: (u0, v0, u1, v1)
        """
        u0, v0, u1, v1 = uv_rect
        nu = cols if wrap_u else cols
        for r in range(rows):
            for c in range(nu):
                c2 = (c + 1) % len(pts[r]) if wrap_u else c + 1
                a = pts[r][c]
                b = pts[r][c2]
                d = pts[r + 1][c]
                e = pts[r + 1][c2]
                fu0 = u0 + (u1 - u0) * (c / nu)
                fu1 = u0 + (u1 - u0) * ((c + 1) / nu)
                fv0 = v0 + (v1 - v0) * (r / rows)
                fv1 = v0 + (v1 - v0) * ((r + 1) / rows)
                if uv_flip_v:
                    fv0, fv1 = v1 - (fv0 - v0), v1 - (fv1 - v0)
                quad = (a, b, e, d)
                uvq = ((fu0, fv0), (fu1, fv0), (fu1, fv1), (fu0, fv1))
                if flip:
                    quad = tuple(reversed(quad))
                    uvq = tuple(reversed(uvq))
                self.add_face(quad, uvq, mat_idx)

    def add_ring_verts(self, ring_pts, region):
        return [self.add_vert(p, region) for p in ring_pts]

    def cap_ring(self, ring, center_co, uv_center, uv_rect, mat_idx, region,
                 flip=False):
        """Halkayi merkez vertex'e ucgen yelpaze ile kapatir."""
        ci = self.add_vert(center_co, region)
        n = len(ring)
        u0, v0, u1, v1 = uv_rect
        cu = u0 + (u1 - u0) * uv_center[0]
        cv = v0 + (v1 - v0) * uv_center[1]
        rad_u = (u1 - u0) * 0.5 * 0.92
        rad_v = (v1 - v0) * 0.5 * 0.92
        for i in range(n):
            j = (i + 1) % n
            a0 = TAU * i / n
            a1 = TAU * j / n
            uv0 = (cu + math.cos(a0) * rad_u, cv + math.sin(a0) * rad_v)
            uv1 = (cu + math.cos(a1) * rad_u, cv + math.sin(a1) * rad_v)
            tri = (ci, ring[i], ring[j])
            uvs = ((cu, cv), uv0, uv1)
            if flip:
                tri = tuple(reversed(tri))
                uvs = tuple(reversed(uvs))
            self.add_face(tri, uvs, mat_idx)
        return ci

    def bridge_loops(self, loop_a, loop_b, uv_rect, mat_idx, flip=False,
                     rows=1):
        """Ayni uzunlukta iki kapali halkayi quad'larla birlestirir (manifold)."""
        n = len(loop_a)
        assert n == len(loop_b), "bridge: halka uzunluklari esit olmali"
        u0, v0, u1, v1 = uv_rect
        for i in range(n):
            j = (i + 1) % n
            fu0 = u0 + (u1 - u0) * (i / n)
            fu1 = u0 + (u1 - u0) * ((i + 1) / n)
            quad = (loop_a[i], loop_a[j], loop_b[j], loop_b[i])
            uvq = ((fu0, v0), (fu1, v0), (fu1, v1), (fu0, v1))
            if flip:
                quad = tuple(reversed(quad))
                uvq = tuple(reversed(uvq))
            self.add_face(quad, uvq, mat_idx)

    # ------------------------------------------------------------------
    # 4.2 bpy nesnesine cevir
    # ------------------------------------------------------------------
    def to_object(self, materials_by_name):
        import bpy
        me = bpy.data.meshes.new(self.name)
        me.from_pydata([v[:] for v in self.verts], [], [list(f) for f in self.faces])
        me.update()
        obj = bpy.data.objects.new(self.name, me)
        bpy.context.collection.objects.link(obj)

        for mn in self.mat_names:
            obj.data.materials.append(materials_by_name[mn])

        uv_layer = me.uv_layers.new(name="UVMap")
        li = 0
        for fi, poly in enumerate(me.polygons):
            poly.material_index = self.face_mat[fi]
            uvs = self.face_uv[fi]
            for k, loop_idx in enumerate(poly.loop_indices):
                uv_layer.data[loop_idx].uv = uvs[k]
            li += len(poly.loop_indices)

        for gname, wmap in self.groups.items():
            vg = obj.vertex_groups.new(name=gname)
            for vidx, w in wmap.items():
                vg.add([vidx], w, 'REPLACE')
        return obj


# ==================================================================
# 5. GEOMETRI YARDIMCILARI
# ==================================================================
def superellipse(phi, w, h, exponent, belly_flat=1.0, belly_exp_mul=1.55):
    """Surungen kesiti: ust yarim kutumsu elips, alt yarim duzlestirilmis."""
    c = math.cos(phi)
    s = math.sin(phi)
    e = exponent
    x = w * (1.0 if s >= 0 else -1.0) * (abs(s) ** (2.0 / e))
    if c >= 0:
        y = h * (abs(c) ** (2.0 / e))
    else:
        eb = e * belly_exp_mul
        y = -h * belly_flat * (abs(c) ** (2.0 / eb))
    return x, y


def frame_matrix(origin, forward, up_hint=(0.0, 1.0, 0.0)):
    """forward yonunde -Z bakan ortonormal baz (Blender konvansiyonu icin)."""
    f = Vector(forward).normalized()
    u = Vector(up_hint)
    r = f.cross(u)
    if r.length < 1e-6:
        r = f.cross(Vector((1.0, 0.0, 0.0)))
    r.normalize()
    u = r.cross(f).normalized()
    m = Matrix((
        (r.x, u.x, f.x, origin[0]),
        (r.y, u.y, f.y, origin[1]),
        (r.z, u.z, f.z, origin[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))
    return m


def make_taper_tube(mb, path, radii, cols, uv_rect, mat_idx, region,
                    cap_start=True, cap_end=True, twist=0.0,
                    profile_fn=None, seed=0, up_hint=(0, 1, 0)):
    """Yol boyunca daralan kapali tup uretir. path: [Vector], radii: [(rx, ry)]."""
    n = len(path)
    rings = []
    # her istasyonda frame
    frames = []
    prev_r = None
    for i in range(n):
        if i == 0:
            t = (path[1] - path[0]).normalized()
        elif i == n - 1:
            t = (path[-1] - path[-2]).normalized()
        else:
            t = (path[i + 1] - path[i - 1]).normalized()
        u = Vector(up_hint)
        r = t.cross(u)
        if r.length < 1e-5:
            r = t.cross(Vector((1.0, 0.0, 0.0)))
        if prev_r is not None:
            # paralel tasima ile twist'i minimize et
            r = prev_r - t * prev_r.dot(t)
            if r.length < 1e-5:
                r = t.cross(Vector((0.0, 1.0, 0.0)))
        r.normalize()
        u = t.cross(r).normalized()
        prev_r = r
        frames.append((path[i], r, u, t))

    for i in range(n):
        p, r, u, t = frames[i]
        rx, ry = radii[i]
        tw = twist * (i / max(n - 1, 1))
        ring = []
        for c in range(cols):
            phi = TAU * c / cols + tw
            if profile_fn is not None:
                lx, ly = profile_fn(phi, rx, ry, i / max(n - 1, 1))
            else:
                lx = rx * math.sin(phi)
                ly = ry * math.cos(phi)
            ring.append(p + r * lx + u * ly)
        rings.append(mb.add_ring_verts(ring, region))

    for i in range(n - 1):
        mb.bridge_loops(rings[i], rings[i + 1],
                        (uv_rect[0], uv_rect[1] + (uv_rect[3] - uv_rect[1]) * i / (n - 1),
                         uv_rect[2], uv_rect[1] + (uv_rect[3] - uv_rect[1]) * (i + 1) / (n - 1)),
                        mat_idx, flip=True)
    if cap_start:
        mb.cap_ring(rings[0], path[0] - (path[1] - path[0]).normalized() * radii[0][1] * 0.35,
                    (0.5, 0.06), uv_rect, mat_idx, region, flip=False)
    if cap_end:
        mb.cap_ring(rings[-1], path[-1] + (path[-1] - path[-2]).normalized() * radii[-1][1] * 0.5,
                    (0.5, 0.94), uv_rect, mat_idx, region, flip=True)
    return rings


def curved_path(origin, direction, length, curve_vec, steps, curve_pow=2.0):
    """Baslangictan cikip curve_vec yonunde giderek bukulen yol."""
    o = Vector(origin)
    d = Vector(direction).normalized()
    cv = Vector(curve_vec)
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append(o + d * (length * t) + cv * (length * (t ** curve_pow)))
    return pts


def horn_path(origin, direction, length, curvature_dir, curvature, steps=14):
    return curved_path(origin, direction, length, Vector(curvature_dir) * curvature,
                       steps, curve_pow=2.1)


def spike_profile(phi, rx, ry, t):
    """Diken/boynuz kesiti: hafif ucgenimsi, tabanda genis."""
    k = 1.0 + 0.30 * math.cos(phi * 3.0)
    return rx * math.sin(phi) * k, ry * math.cos(phi) * k
