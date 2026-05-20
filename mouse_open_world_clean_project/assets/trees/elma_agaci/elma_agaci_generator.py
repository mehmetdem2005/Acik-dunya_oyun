"""Procedural Malus domestica apple tree for Acik-dunya_oyun.

Target: ~15k triangles, biologically accurate, low-poly game asset.
2D plane leaves (cluster cards), spherical canopy normals, materials
ready for user-supplied textures (bark, leaf, apple).

Run:
    blender --background --python elma_agaci_generator.py -- [--render] [--seed 42]
"""

import argparse
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
DEFAULT_SEED = 42
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Tree macro
TOTAL_HEIGHT = 4.2               # mature backyard apple — shorter than first try
TRUNK_LEAN_DEG = 7.0
TRUNK_S_CURVE_AMP = 0.08
TRUNK_FORK_HEIGHT = 0.85
TRUNK_GEOM_TOP_FRAC = 0.72       # trunk continues higher (taper to point inside canopy)

# Trunk radii (thicker base + stronger flare + gnarl noise)
TRUNK_BASE_R = 0.14
TRUNK_FORK_R = 0.10
TRUNK_TOP_R = 0.025              # taper to near-point inside canopy
ROOT_FLARE_FACTOR = 1.55         # ↓ less balloon-like
ROOT_FLARE_HEIGHT = 0.28
BUTTRESS_LOBES = 4
BUTTRESS_AMP = 0.22              # ↓ subtler, organic-looking lobes
TRUNK_GNARL_AMP = 0.18           # ↑ stronger
TRUNK_GNARL_FREQ_Z = 6.5
TRUNK_GNARL_FREQ_THETA = 4.0
TRUNK_BURL_COUNT = 3             # one more burl
TRUNK_BURL_AMP = 0.40            # ↑ stronger localized swells
TRUNK_BURL_SIGMA = 0.09          # tighter falloff (was implicit 0.18)
TRUNK_RADIAL_SEGS = 11
TRUNK_HEIGHT_SEGS = 10

# Scaffold branches (primaries)
N_SCAFFOLDS = 5
N_CO_LEADERS = 2                 # first N scaffolds are co-dominant leaders (thicker, wider V)
CO_LEADER_R_BOOST = 1.35
CO_LEADER_CROTCH_DEG = (52.0, 64.0)   # wider V for visible fork
SCAFFOLD_PITCH_Z = 0.18
SCAFFOLD_LENGTH_RANGE = (1.7, 2.4)    # balance crown size vs height
SCAFFOLD_CROTCH_RANGE_DEG = (42.0, 58.0)
SCAFFOLD_R_FACTOR = 0.52
SCAFFOLD_TIP_R_FACTOR = 0.26
SCAFFOLD_SEGMENTS = 5
SCAFFOLD_RADIAL_SEGS = 7
SCAFFOLD_AZIMUTH_MODE = "even"   # "even" (uniform spread) or "golden" (137.5°)

# Upper crown branches
N_UPPER_BRANCHES = 4
UPPER_BRANCH_START_FRAC = 0.62
UPPER_BRANCH_LENGTH_RANGE = (1.10, 1.70)   # longer so crown is taller
UPPER_BRANCH_CROTCH_DEG = (38.0, 62.0)   # wider spread for visible canopy mass

# Secondaries
SECONDARIES_PER_SCAFFOLD_RANGE = (5, 7)
SECONDARY_LENGTH_RANGE = (0.55, 1.15)
SECONDARY_ANGLE_RANGE_DEG = (38.0, 58.0)
SECONDARY_R_FACTOR = 0.55
SECONDARY_TIP_R_FACTOR = 0.30
SECONDARY_SEGMENTS = 4
SECONDARY_RADIAL_SEGS = 5        # reduced
SECONDARY_START_FRAC = 0.18

# Tertiaries / twigs
TWIGS_PER_SECONDARY_RANGE = (2, 4)
TWIG_LENGTH_RANGE = (0.14, 0.38)
TWIG_ANGLE_RANGE_DEG = (35.0, 65.0)
TWIG_R_FACTOR = 0.55
TWIG_TIP_R_FACTOR = 0.30
TWIG_SEGMENTS = 2
TWIG_RADIAL_SEGS = 4
TWIG_START_FRAC = 0.18

# Spurs
SPURS_PER_SECONDARY_AVG = 5
SPURS_PER_TWIG_AVG = 0.5
SPUR_LENGTH_RANGE = (0.020, 0.038)
SPUR_BASE_R = 0.0050
SPUR_TIP_R = 0.0032
SPUR_RADIAL_SEGS = 4
SPUR_SEGMENTS = 1                # single segment is enough at this scale

# Leaves — per-leaf ovate mesh (50-agent panel synthesis: cluster card terkedildi)
# 6-vert diamond layout, 4 triangles, V-fold midrib + tip droop baked into geometry.
# Silhouette geometry-defined; texture only adds vein detail when supplied.
LEAF_LENGTH = 0.105              # ~105mm — stylized-realistic (real 75mm, art director: bigger for visibility)
LEAF_WIDTH_RATIO = 0.62          # 0.62 × 105mm = 65mm width (1.6:1 ovate ratio)
LEAF_V_FOLD = 0.015              # midrib lift (~%14 length) — adaxial convexity
LEAF_TIP_DROOP_DEG = 22          # tip vert bends down (gravity hint)
LEAVES_PER_TWIG = 9              # spiral phyllotaxis along long-shoot
LEAVES_PER_SPUR = 6              # opposite-pair rosette
LEAF_SIZE_JITTER = (0.82, 1.18)  # per-leaf scale variation
LEAF_AZIMUTH_JITTER_DEG = 14     # tight spiral
LEAF_PITCH_BIAS_DEG = 35         # heliotropism: leaves tilt toward sky on upper canopy
LEAF_HOLLOW_CORE_THRESHOLD = 0.55  # leaves deeper than this (m from outer shell) thin out
LEAF_HOLLOW_SKIP_PROB = 0.35     # probability to skip interior leaves (LAI gradient)

# Apples — biggers + visible + botanically paired (50-agent panel)
APPLE_COUNT_TARGET = 30
APPLE_DIAMETER = 0.100           # ↑ from 0.080 — art director: visibility priority
APPLE_OBLATE = 0.84               # oblate "apple" shape
APPLE_UV_SEGS = 7
APPLE_UV_RINGS = 5
APPLE_STEM_LEN = 0.040
APPLE_STEM_R = 0.0030
APPLE_STEM_RADIAL_SEGS = 5
APPLE_STEM_SEGMENTS = 2
# botanist düzeltmesi: pairs/triples dominant, singleton azaltıldı
APPLE_CLUSTER_WEIGHTS = [0.15, 0.50, 0.25, 0.08, 0.02]
APPLE_OUTER_BIAS = 0.70
APPLE_OUTWARD_PUSH = 0.10        # ↑ from 0.07 — push further to outer canopy shell
APPLE_COLOR_JITTER = 0.35
COLOR_APPLE_BLUSH = (0.80, 0.62, 0.12)

# Gravity / fruit-load sag — must read in silhouette
FRUIT_LOAD = 0.65
SCAFFOLD_DROOP_TIP_M = 0.32
SECONDARY_DROOP_TIP_M = 0.22

# Material colors (placeholders, user will supply textures later)
COLOR_BARK   = (0.30, 0.20, 0.13)
COLOR_LEAF_VARIANTS = [
    (0.18, 0.42, 0.13),     # darker mature
    (0.24, 0.52, 0.18),     # midtone
    (0.32, 0.58, 0.22),     # lighter young leaves
]
COLOR_APPLE  = (0.85, 0.13, 0.10)
COLOR_STEM   = (0.42, 0.26, 0.14)

# Output
OUT_BLEND = os.path.join(OUT_DIR, "elma_agaci.blend")
RENDER_OUT_TMPL = os.path.join(OUT_DIR, "preview_round_{round}_{view}.png")
RENDER_RES = (1024, 1024)

GOLDEN_ANGLE = math.radians(137.5)

# ------------------------------------------------------------------
# UTIL
# ------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def cap_disk(bm, center, normal, radius, segs, radial_mod=None):
    """Create a circle of verts around `center` perpendicular to `normal`.

    `radial_mod`: optional callable (angle_rad) -> radius_multiplier for non-circular cross-sections.
    """
    n = normal.normalized()
    helper = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
    t = (helper - helper.dot(n) * n).normalized()
    b = n.cross(t).normalized()
    verts = []
    for i in range(segs):
        ang = 2.0 * math.pi * i / segs
        r = radius
        if radial_mod is not None:
            r *= radial_mod(ang)
        offset = math.cos(ang) * t * r + math.sin(ang) * b * r
        verts.append(bm.verts.new(center + offset))
    return verts


def _hash_noise(x, y, seed=0):
    """Cheap deterministic pseudo-noise on (x,y) pair returning [-1,1]."""
    s = math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453
    return (s - math.floor(s)) * 2.0 - 1.0


def smooth_step(t):
    return t * t * (3 - 2 * t)


def bridge_rings(bm, ring_a, ring_b):
    """Connect two equal-size rings with quad faces. Returns list of created faces."""
    n = len(ring_a)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        try:
            f = bm.faces.new((ring_a[i], ring_a[j], ring_b[j], ring_b[i]))
            faces.append(f)
        except ValueError:
            pass
    return faces


def smooth_bezier3(p0, p1, p2, p3, t):
    """Cubic bezier interpolation."""
    one_t = 1.0 - t
    return (one_t**3) * p0 + 3 * (one_t**2) * t * p1 + 3 * one_t * (t**2) * p2 + (t**3) * p3


def smooth_bezier3_tangent(p0, p1, p2, p3, t):
    """Tangent to cubic bezier."""
    one_t = 1.0 - t
    return (3 * one_t**2) * (p1 - p0) + (6 * one_t * t) * (p2 - p1) + (3 * t**2) * (p3 - p2)


# ------------------------------------------------------------------
# CURVE BUILDERS  — produce list of (point, radius, frame) along axis
# ------------------------------------------------------------------

def trunk_curve(rng):
    """Return list of (pos, radius, up_dir, radial_mod) along trunk.

    radial_mod is a callable (angle) -> multiplier producing buttress lobes
    near the root flare and gnarl noise along the height.
    """
    pts = []
    geom_top = TOTAL_HEIGHT * TRUNK_GEOM_TOP_FRAC
    h = geom_top
    lean = math.radians(TRUNK_LEAN_DEG)
    azimuth = rng.uniform(0, math.pi * 2)
    lean_dir = Vector((math.cos(azimuth), math.sin(azimuth), 0))
    noise_seed = rng.uniform(0, 1000)

    p0 = Vector((0, 0, 0))
    p1 = p0 + Vector((-TRUNK_S_CURVE_AMP * lean_dir.x, -TRUNK_S_CURVE_AMP * lean_dir.y, 0.33 * h))
    p2 = Vector((math.sin(lean) * 0.66 * h * lean_dir.x + TRUNK_S_CURVE_AMP * 0.5 * lean_dir.x,
                 math.sin(lean) * 0.66 * h * lean_dir.y + TRUNK_S_CURVE_AMP * 0.5 * lean_dir.y,
                 0.66 * h))
    p3 = Vector((math.sin(lean) * h * lean_dir.x, math.sin(lean) * h * lean_dir.y, h))

    # pre-pick burl height positions
    burl_zs = [rng.uniform(0.25 * h, 0.85 * h) for _ in range(TRUNK_BURL_COUNT)]
    burl_azimuths = [rng.uniform(0, math.pi * 2) for _ in range(TRUNK_BURL_COUNT)]

    n = TRUNK_HEIGHT_SEGS + 1
    for i in range(n):
        t = i / (n - 1)
        pos = smooth_bezier3(p0, p1, p2, p3, t)
        fork_frac = TRUNK_FORK_HEIGHT / h
        if t < fork_frac:
            r = TRUNK_BASE_R + (TRUNK_FORK_R - TRUNK_BASE_R) * (t / fork_frac)
        else:
            tt = (t - fork_frac) / (1.0 - fork_frac)
            r = TRUNK_FORK_R + (TRUNK_TOP_R - TRUNK_FORK_R) * tt
        if pos.z < ROOT_FLARE_HEIGHT:
            flare_t = 1.0 - smooth_step(pos.z / ROOT_FLARE_HEIGHT)
            r *= 1.0 + (ROOT_FLARE_FACTOR - 1.0) * flare_t
        tangent = smooth_bezier3_tangent(p0, p1, p2, p3, t)
        if tangent.length < 1e-6:
            tangent = Vector((0, 0, 1))

        z_capture = pos.z
        in_flare = z_capture < ROOT_FLARE_HEIGHT
        flare_strength = 0.0
        if in_flare:
            flare_strength = 1.0 - smooth_step(z_capture / ROOT_FLARE_HEIGHT)

        burl_contributions = []
        for bz, baz in zip(burl_zs, burl_azimuths):
            dist = abs(z_capture - bz)
            falloff = max(0, 1.0 - dist / TRUNK_BURL_SIGMA)
            burl_contributions.append((baz, falloff))

        def radial_mod(angle, z=z_capture, fs=flare_strength,
                       burls=burl_contributions, ns=noise_seed):
            mod = 1.0
            # Buttress lobes near root flare (cos(N*theta) modulation)
            if fs > 0:
                lobes = 0.5 * (math.cos(BUTTRESS_LOBES * angle) + 1.0)  # 0..1
                mod += BUTTRESS_AMP * fs * (lobes - 0.5) * 2  # symmetric +/-
            # Gnarl noise: shallow per-angle radial perturbation
            n_val = _hash_noise(z * TRUNK_GNARL_FREQ_Z,
                                angle * TRUNK_GNARL_FREQ_THETA / (2 * math.pi),
                                ns)
            mod += TRUNK_GNARL_AMP * n_val
            # Burls: localized azimuth-aligned bumps
            for baz, fall in burls:
                if fall > 0:
                    azc = math.cos(angle - baz)
                    if azc > 0.4:
                        mod += TRUNK_BURL_AMP * fall * (azc - 0.4) / 0.6
            return max(0.7, mod)

        pts.append((pos, r, tangent.normalized(), radial_mod))
    return pts


def branch_curve(base_pos, base_dir, length, base_r, tip_r, segments, droop_m, lateral_jitter, rng):
    """Generate ascending-then-arching branch curve.

    Returns list of (pos, radius, tangent, radial_mod or None) tuples.
    """
    p0 = Vector(base_pos)
    horiz = Vector((base_dir.x, base_dir.y, 0))
    if horiz.length < 1e-6:
        horiz = Vector((1, 0, 0))
    horiz = horiz.normalized()

    p1 = p0 + base_dir * (length * 0.35)
    p2 = p0 + base_dir * (length * 0.55) + horiz * (length * 0.20) + Vector((0, 0, -droop_m * 0.4))
    p3 = p0 + base_dir * (length * 0.70) + horiz * (length * 0.30) + Vector((0, 0, -droop_m))

    side = base_dir.cross(Vector((0, 0, 1))).normalized() if abs(base_dir.z) < 0.99 else Vector((1, 0, 0))
    p1 += side * lateral_jitter * rng.uniform(-1, 1)
    p2 += side * lateral_jitter * rng.uniform(-1, 1)
    p3 += side * lateral_jitter * 0.5 * rng.uniform(-1, 1)

    pts = []
    n = segments + 1
    for i in range(n):
        t = i / (n - 1)
        pos = smooth_bezier3(p0, p1, p2, p3, t)
        r = base_r + (tip_r - base_r) * (t ** 0.85)
        r *= 1.0 + 0.04 * rng.uniform(-1, 1)
        tangent = smooth_bezier3_tangent(p0, p1, p2, p3, t)
        if tangent.length < 1e-6:
            tangent = base_dir
        pts.append((pos, r, tangent.normalized(), None))
    return pts


# ------------------------------------------------------------------
# MESH BUILDERS
# ------------------------------------------------------------------

def build_tube(bm, curve_pts, radial_segs, mat_index, face_index_track):
    """Build a tube along the curve and record face indices for material assignment.

    curve_pts: list of (pos, radius, tangent, radial_mod_or_None).
    """
    rings = []
    for pt in curve_pts:
        pos, r, tangent = pt[0], pt[1], pt[2]
        radial_mod = pt[3] if len(pt) > 3 else None
        ring = cap_disk(bm, pos, tangent, r, radial_segs, radial_mod=radial_mod)
        rings.append(ring)
    start_face = len(bm.faces)
    for i in range(len(rings) - 1):
        bridge_rings(bm, rings[i], rings[i + 1])
    end_face = len(bm.faces)
    face_index_track.setdefault(mat_index, []).append((start_face, end_face))
    return rings


def make_ovate_leaf_mesh(bm, base_pos, blade_normal, blade_dir, length, width,
                         mat_index, face_index_track, color_layer=None,
                         vcolor=(1.0, 1.0, 1.0, 1.0), roll=0.0, rng=None):
    """Per-leaf ovate mesh: 6 vertices, 4 triangles (50-agent panel synthesis).

    Layout (Malus domestica elliptic-ovate, obtuse tip):
            5 (tip — drooped down)
           / \\
          3   4 (upper shoulder, narrower)
          |   |
          1   2 (mid widest, length*0.30 from base)
           \\ /
            0 (base — petiole anchor)

    `base_pos` is the petiole attachment point on the twig surface.
    `blade_dir` is the direction the blade extends (away from twig).
    `blade_normal` is the "up" of the adaxial surface.
    `roll` rotates the blade around blade_dir axis (per-leaf yaw variation).

    Triangles: (0,2,1), (1,2,3), (2,4,3), (3,4,5) — total 4 tri.
    V-fold: midrib vertices (0, 5) raised in +normal direction (adaxial convexity).
    Tip droop: vertex 5 displaced down along blade_dir (gravity hint).
    """
    bd = blade_dir.normalized()
    bn = blade_normal.normalized()
    # Side axis perpendicular to both
    side = bd.cross(bn).normalized()
    if side.length < 1e-5:
        # Fallback if blade_dir collinear with normal
        side = Vector((1, 0, 0))
    # Apply roll around blade_dir
    cr, sr = math.cos(roll), math.sin(roll)
    side_r = side * cr + bn * sr
    bn_r = -side * sr + bn * cr

    half_w = width * 0.5
    half_w_upper = width * 0.30  # upper shoulder narrower (ovate taper)
    v_fold = LEAF_V_FOLD * (width / max(LEAF_LENGTH * LEAF_WIDTH_RATIO, 0.01))
    tip_droop_dist = length * math.sin(math.radians(LEAF_TIP_DROOP_DEG))

    # Vertices along blade_dir (Y axis local) from base (0) to tip (length)
    p0 = base_pos + bd * 0.0 + bn_r * v_fold              # base — midrib lifted
    p1 = base_pos + bd * (length * 0.30) - side_r * half_w  # left widest
    p2 = base_pos + bd * (length * 0.30) + side_r * half_w  # right widest
    p3 = base_pos + bd * (length * 0.65) - side_r * half_w_upper  # left upper
    p4 = base_pos + bd * (length * 0.65) + side_r * half_w_upper  # right upper
    p5 = base_pos + bd * length + bn_r * v_fold - bn_r * tip_droop_dist  # tip — lifted then drooped

    v0 = bm.verts.new(p0)
    v1 = bm.verts.new(p1)
    v2 = bm.verts.new(p2)
    v3 = bm.verts.new(p3)
    v4 = bm.verts.new(p4)
    v5 = bm.verts.new(p5)

    # UV layout: leaf occupies (0..1, 0..1), base at bottom (V=0), tip at top (V=1)
    uvs = [
        (0.50, 0.00),  # base
        (0.10, 0.30),  # left mid
        (0.90, 0.30),  # right mid
        (0.20, 0.70),  # left upper
        (0.80, 0.70),  # right upper
        (0.50, 1.00),  # tip
    ]

    start = len(bm.faces)
    tri_verts = [
        (v0, v2, v1),  # base wedge
        (v1, v2, v3),  # left mid-quad split
        (v2, v4, v3),  # right mid-quad split
        (v3, v4, v5),  # tip wedge
    ]
    tri_uv_idx = [
        (0, 2, 1),
        (1, 2, 3),
        (2, 4, 3),
        (3, 4, 5),
    ]
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new()
    for face_verts, uv_idx in zip(tri_verts, tri_uv_idx):
        try:
            f = bm.faces.new(face_verts)
            for li, loop in enumerate(f.loops):
                loop[uv_layer].uv = uvs[uv_idx[li]]
                if color_layer is not None:
                    loop[color_layer] = vcolor
        except ValueError:
            pass
    end = len(bm.faces)
    face_index_track.setdefault(mat_index, []).append((start, end))


def make_apple(bm, center, mat_apple_idx, mat_stem_idx, face_index_track, rng):
    """UV sphere ~8x6 squashed, with stem, hanging vertically."""
    # UV sphere construction
    diameter = APPLE_DIAMETER * rng.uniform(0.88, 1.12)
    r = diameter * 0.5
    z_scale = APPLE_OBLATE * rng.uniform(0.95, 1.05)
    rings = APPLE_UV_RINGS
    segs = APPLE_UV_SEGS

    rng_offset = Vector((rng.uniform(-0.005, 0.005), rng.uniform(-0.005, 0.005), 0))
    apple_center = center - Vector((0, 0, r * z_scale)) + rng_offset  # fruit hangs below attach point

    # Build rings (latitude lines)
    ring_verts = []
    for i in range(1, rings):
        phi = math.pi * i / rings  # 0..pi from top
        z = math.cos(phi) * r * z_scale
        rad = math.sin(phi) * r
        # slight stem-end pucker (top) and calyx pucker (bottom)
        if i == 1:
            rad *= 0.42        # stronger top pinch → stem cavity
            z *= 1.04
        elif i == rings - 1:
            rad *= 0.42        # stronger bottom pinch → calyx basin
            z *= 1.04
        verts = []
        for j in range(segs):
            ang = 2 * math.pi * j / segs
            # slight asymmetry per apple
            asym = 1.0 + 0.04 * math.sin(ang * 2 + rng.random() * 6.28)
            x = math.cos(ang) * rad * asym
            y = math.sin(ang) * rad * asym
            verts.append(bm.verts.new(apple_center + Vector((x, y, z))))
        ring_verts.append(verts)

    # Top pole (calyx end up if we orient stem down? no — stem at top, hanging)
    top_pole = bm.verts.new(apple_center + Vector((0, 0, r * z_scale * 1.10)))
    bot_pole = bm.verts.new(apple_center + Vector((0, 0, -r * z_scale * 1.10)))
    # Stronger basin pucker — apple stem cavity + calyx basin
    top_pole.co.z -= r * z_scale * 0.18
    bot_pole.co.z += r * z_scale * 0.16

    start = len(bm.faces)
    # Cap top
    for j in range(segs):
        jn = (j + 1) % segs
        try:
            bm.faces.new((top_pole, ring_verts[0][jn], ring_verts[0][j]))
        except ValueError:
            pass
    # Bridge rings
    for i in range(len(ring_verts) - 1):
        bridge_rings(bm, ring_verts[i], ring_verts[i + 1])
    # Cap bottom
    for j in range(segs):
        jn = (j + 1) % segs
        try:
            bm.faces.new((bot_pole, ring_verts[-1][j], ring_verts[-1][jn]))
        except ValueError:
            pass
    end = len(bm.faces)
    face_index_track.setdefault(mat_apple_idx, []).append((start, end))

    # Stem: tiny cylinder from top pole going up to attachment point
    stem_top = center  # branch attachment
    stem_bot = Vector((apple_center.x, apple_center.y, apple_center.z + r * z_scale * 1.04))
    stem_dir = (stem_top - stem_bot)
    stem_len = max(stem_dir.length, APPLE_STEM_LEN * 0.5)
    stem_dir = stem_dir.normalized() if stem_dir.length > 1e-5 else Vector((0, 0, 1))

    stem_pts = []
    n_seg = APPLE_STEM_SEGMENTS + 1
    for i in range(n_seg):
        t = i / (n_seg - 1)
        pos = stem_bot + stem_dir * (stem_len * t)
        r_stem = APPLE_STEM_R * (1.0 - 0.2 * t)
        stem_pts.append((pos, r_stem, stem_dir))
    stem_start = len(bm.faces)
    stem_rings = []
    for pos, rr, td in stem_pts:
        stem_rings.append(cap_disk(bm, pos, td, rr, APPLE_STEM_RADIAL_SEGS))
    for i in range(len(stem_rings) - 1):
        bridge_rings(bm, stem_rings[i], stem_rings[i + 1])
    stem_end = len(bm.faces)
    face_index_track.setdefault(mat_stem_idx, []).append((stem_start, stem_end))


# ------------------------------------------------------------------
# TREE BUILD
# ------------------------------------------------------------------

class TreeBuilder:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.bm_wood = bmesh.new()
        self.bm_leaf = bmesh.new()
        self.bm_apple = bmesh.new()
        # Vertex color & UV layers for leaves (set up before face creation)
        self.leaf_uv_layer = self.bm_leaf.loops.layers.uv.new("UVMap")
        self.leaf_color_layer = self.bm_leaf.loops.layers.color.new("Col")
        # face_index tracks per bmesh -> {mat_idx: [(start,end), ...]}
        self.wood_faces = {}
        self.leaf_faces = {}
        self.apple_faces = {}
        # Track leaf/apple attachment points for placement bias
        self.twigs = []         # list of dicts {curve_pts, parent_secondary, depth}
        self.spurs = []         # list of dicts {pos, normal, parent}
        # Canopy center: where leaves cluster vertically (above scaffold zone)
        self.canopy_center = Vector((0, 0, TOTAL_HEIGHT * 0.55))
        self.canopy_radius = 2.6   # estimated; refined after branch build
        # Leaf placeholder texture path (Round 3 — set later by bake_leaf_texture)
        self.leaf_texture_path = None

    # ----- WOOD -----
    def build_trunk_and_branches(self):
        trunk_pts = trunk_curve(self.rng)
        build_tube(self.bm_wood, trunk_pts, TRUNK_RADIAL_SEGS, 0, self.wood_faces)

        geom_top = TOTAL_HEIGHT * TRUNK_GEOM_TOP_FRAC

        # SCAFFOLDS: deterministic V-fork visible from camera + uniform azimuth for the rest
        # Co-leaders along +X / -X axis so the V opens toward camera (camera is on -Y axis).
        for i in range(N_SCAFFOLDS):
            is_co_leader = i < N_CO_LEADERS
            # Co-leaders fork from same height (visible V); other scaffolds stagger upward
            if is_co_leader:
                z = TRUNK_FORK_HEIGHT + self.rng.uniform(-0.04, 0.04)
            else:
                stagger_idx = i - N_CO_LEADERS
                z = TRUNK_FORK_HEIGHT + 0.18 + stagger_idx * SCAFFOLD_PITCH_Z + self.rng.uniform(-0.03, 0.03)
            t_pos, t_r, t_tan = self._sample_curve(trunk_pts, z)
            if is_co_leader:
                # Deterministic +X / -X with small jitter — front-camera-friendly V
                base_az = 0.0 if i == 0 else math.pi
                azimuth = base_az + self.rng.uniform(-0.18, 0.18)
            else:
                stagger_idx = i - N_CO_LEADERS
                # Remaining scaffolds fill non-coleader half-spaces
                azimuth = (math.pi * 0.5) + stagger_idx * (math.pi / max(N_SCAFFOLDS - N_CO_LEADERS, 1)) \
                          + self.rng.uniform(-0.35, 0.35)
                if stagger_idx % 2 == 1:
                    azimuth += math.pi   # alternate to the other side
            crotch_range = CO_LEADER_CROTCH_DEG if is_co_leader else SCAFFOLD_CROTCH_RANGE_DEG
            crotch = math.radians(self.rng.uniform(*crotch_range))
            out_dir = Vector((math.cos(azimuth), math.sin(azimuth), 0))
            base_dir = (math.cos(crotch) * Vector((0, 0, 1)) + math.sin(crotch) * out_dir).normalized()
            length = self.rng.uniform(*SCAFFOLD_LENGTH_RANGE)
            r_boost = CO_LEADER_R_BOOST if is_co_leader else 1.0
            base_r = t_r * SCAFFOLD_R_FACTOR * r_boost
            tip_r = base_r * SCAFFOLD_TIP_R_FACTOR
            droop = SCAFFOLD_DROOP_TIP_M * FRUIT_LOAD * (0.7 if is_co_leader else 1.0)
            curve = branch_curve(t_pos + out_dir * (t_r * 0.6), base_dir, length, base_r, tip_r,
                                 SCAFFOLD_SEGMENTS, droop, lateral_jitter=0.10, rng=self.rng)
            build_tube(self.bm_wood, curve, SCAFFOLD_RADIAL_SEGS, 0, self.wood_faces)
            self._build_secondaries(curve, depth=1)

        # UPPER CROWN BRANCHES: near trunk top, more upright, fill crown above scaffolds.
        # Length tapers with height to round off the crown into a dome.
        for i in range(N_UPPER_BRANCHES):
            # spread upper branches over a vertical band, not just one z
            z_frac = UPPER_BRANCH_START_FRAC + (i / max(N_UPPER_BRANCHES - 1, 1)) * (1.0 - UPPER_BRANCH_START_FRAC) * 0.85
            z_frac += self.rng.uniform(-0.04, 0.04)
            z = min(geom_top * z_frac, geom_top - 0.05)
            t_pos, t_r, t_tan = self._sample_curve(trunk_pts, z)
            azimuth = (i + N_SCAFFOLDS) * GOLDEN_ANGLE + self.rng.uniform(-0.3, 0.3)
            crotch = math.radians(self.rng.uniform(*UPPER_BRANCH_CROTCH_DEG))
            out_dir = Vector((math.cos(azimuth), math.sin(azimuth), 0))
            base_dir = (math.cos(crotch) * Vector((0, 0, 1)) + math.sin(crotch) * out_dir).normalized()
            # Top branches shorter → rounded crown
            z_height_frac = (z - TRUNK_FORK_HEIGHT) / max(geom_top - TRUNK_FORK_HEIGHT, 0.1)
            taper_mult = 1.0 - max(0, z_height_frac - 0.4) * 0.55
            length = self.rng.uniform(*UPPER_BRANCH_LENGTH_RANGE) * taper_mult
            base_r = t_r * 0.70
            tip_r = base_r * 0.25
            droop = SECONDARY_DROOP_TIP_M * FRUIT_LOAD * 0.6
            curve = branch_curve(t_pos + out_dir * (t_r * 0.5), base_dir, length, base_r, tip_r,
                                 SCAFFOLD_SEGMENTS - 1, droop, lateral_jitter=0.06, rng=self.rng)
            build_tube(self.bm_wood, curve, SCAFFOLD_RADIAL_SEGS - 2, 0, self.wood_faces)
            self._build_secondaries(curve, depth=1, count_override=(2, 4))

    def _build_secondaries(self, parent_curve, depth, count_override=None):
        count_range = count_override or SECONDARIES_PER_SCAFFOLD_RANGE
        n = self.rng.randint(*count_range)
        used_frac = []
        for i in range(n):
            # distribute helically along parent
            frac = SECONDARY_START_FRAC + (0.85 - SECONDARY_START_FRAC) * (i / max(n - 1, 1))
            frac += self.rng.uniform(-0.04, 0.04)
            used_frac.append(frac)
            # sample point along parent curve
            pos, r_parent, tan = self._sample_branch_curve(parent_curve, frac)
            # azimuth around parent axis (helical)
            azimuth = i * GOLDEN_ANGLE + self.rng.uniform(-0.3, 0.3)
            # build perpendicular frame
            up = Vector((0, 0, 1))
            side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
            forward = tan.cross(side).normalized()
            radial = math.cos(azimuth) * side + math.sin(azimuth) * forward
            ang = math.radians(self.rng.uniform(*SECONDARY_ANGLE_RANGE_DEG))
            base_dir = (math.cos(ang) * tan + math.sin(ang) * radial).normalized()
            length = self.rng.uniform(*SECONDARY_LENGTH_RANGE) * (1.0 - 0.15 * depth)
            base_r = r_parent * SECONDARY_R_FACTOR
            tip_r = base_r * SECONDARY_TIP_R_FACTOR
            droop = SECONDARY_DROOP_TIP_M * FRUIT_LOAD * (1.0 + 0.2 * depth)
            curve = branch_curve(pos + radial * (r_parent * 0.5), base_dir, length, base_r, tip_r,
                                 SECONDARY_SEGMENTS, droop, lateral_jitter=0.06, rng=self.rng)
            build_tube(self.bm_wood, curve, SECONDARY_RADIAL_SEGS, 0, self.wood_faces)
            # twigs
            self._build_twigs(curve, depth=depth + 1)
            # spurs on this secondary
            self._sprinkle_spurs_on_branch(curve, count=int(SPURS_PER_SECONDARY_AVG * self.rng.uniform(0.7, 1.3)))

    def _build_twigs(self, parent_curve, depth):
        n = self.rng.randint(*TWIGS_PER_SECONDARY_RANGE)
        for i in range(n):
            frac = TWIG_START_FRAC + (0.9 - TWIG_START_FRAC) * (i / max(n - 1, 1))
            frac += self.rng.uniform(-0.05, 0.05)
            pos, r_parent, tan = self._sample_branch_curve(parent_curve, frac)
            azimuth = i * GOLDEN_ANGLE + self.rng.uniform(-0.4, 0.4)
            up = Vector((0, 0, 1))
            side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
            forward = tan.cross(side).normalized()
            radial = math.cos(azimuth) * side + math.sin(azimuth) * forward
            ang = math.radians(self.rng.uniform(*TWIG_ANGLE_RANGE_DEG))
            base_dir = (math.cos(ang) * tan + math.sin(ang) * radial).normalized()
            length = self.rng.uniform(*TWIG_LENGTH_RANGE)
            base_r = r_parent * TWIG_R_FACTOR
            tip_r = base_r * TWIG_TIP_R_FACTOR
            droop = 0.03 * FRUIT_LOAD
            curve = branch_curve(pos + radial * (r_parent * 0.4), base_dir, length, base_r, tip_r,
                                 TWIG_SEGMENTS, droop, lateral_jitter=0.03, rng=self.rng)
            build_tube(self.bm_wood, curve, TWIG_RADIAL_SEGS, 0, self.wood_faces)
            self.twigs.append({"curve": curve, "depth": depth})
            # occasional spurs on twigs (mostly long shoots have leaves, no spurs)
            if self.rng.random() < SPURS_PER_TWIG_AVG:
                self._sprinkle_spurs_on_branch(curve, count=1)

    def _sprinkle_spurs_on_branch(self, parent_curve, count):
        for _ in range(count):
            frac = self.rng.uniform(0.15, 0.95)
            pos, r_parent, tan = self._sample_branch_curve(parent_curve, frac)
            azimuth = self.rng.uniform(0, 2 * math.pi)
            up = Vector((0, 0, 1))
            side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
            forward = tan.cross(side).normalized()
            radial = math.cos(azimuth) * side + math.sin(azimuth) * forward
            ang = math.radians(self.rng.uniform(35, 65))
            spur_dir = (math.cos(ang) * tan + math.sin(ang) * radial).normalized()
            spur_len = self.rng.uniform(*SPUR_LENGTH_RANGE)
            # tiny tube
            base = pos + radial * (r_parent * 0.4)
            curve = branch_curve(base, spur_dir, spur_len, SPUR_BASE_R, SPUR_TIP_R,
                                 SPUR_SEGMENTS, 0.0, 0.001, self.rng)
            build_tube(self.bm_wood, curve, SPUR_RADIAL_SEGS, 0, self.wood_faces)
            # Spur tip = leaf rosette + (sometimes) apple cluster
            tip = curve[-1]
            self.spurs.append({"pos": tip[0], "tangent": tip[2], "parent_curve": parent_curve,
                               "dir": spur_dir})

    def _sample_curve(self, curve_pts, target_z):
        """Sample a curve point closest to target_z. Returns (pos, r, tan)."""
        best = curve_pts[0]
        best_d = abs(best[0].z - target_z)
        for p in curve_pts:
            d = abs(p[0].z - target_z)
            if d < best_d:
                best_d = d
                best = p
        return best[0], best[1], best[2]

    def _sample_branch_curve(self, curve_pts, frac):
        """Sample by parameter fraction along the curve. Returns (pos, r, tan)."""
        idx_f = frac * (len(curve_pts) - 1)
        i0 = int(idx_f)
        i1 = min(i0 + 1, len(curve_pts) - 1)
        t = idx_f - i0
        p0, r0, tan0 = curve_pts[i0][0], curve_pts[i0][1], curve_pts[i0][2]
        p1, r1, tan1 = curve_pts[i1][0], curve_pts[i1][1], curve_pts[i1][2]
        pos = p0.lerp(p1, t)
        r = r0 * (1 - t) + r1 * t
        tan = tan0.lerp(tan1, t).normalized()
        return pos, r, tan

    # ----- LEAVES -----
    def _compute_canopy_radius(self):
        """Estimate canopy outer-shell radius from twig+spur positions for hollow-core test."""
        max_r = 0.0
        for t in self.twigs:
            for p in t["curve"]:
                dx = p[0].x - self.canopy_center.x
                dy = p[0].y - self.canopy_center.y
                r = math.hypot(dx, dy)
                if r > max_r:
                    max_r = r
        return max(max_r, 1.5)

    def _hollow_core_skip(self, pos):
        """Returns True if leaf is too deep inside canopy (LAI gradient — sparse interior).

        Outer shell (within HOLLOW_CORE_THRESHOLD meters of shell) = always keep.
        Deeper = probabilistic skip per LEAF_HOLLOW_SKIP_PROB.
        """
        dx = pos.x - self.canopy_center.x
        dy = pos.y - self.canopy_center.y
        horiz_dist = math.hypot(dx, dy)
        shell_depth = max(0.0, self.canopy_radius - horiz_dist)
        if shell_depth > LEAF_HOLLOW_CORE_THRESHOLD:
            return self.rng.random() < LEAF_HOLLOW_SKIP_PROB
        return False

    def _leaf_vcolor(self, pos):
        """Per-leaf RGBA vertex color: RGB = palette tier (height+radius driven), A = AO multiplier."""
        # Height factor 0 (low) → 1 (top)
        z_frac = (pos.z - 0.0) / max(TOTAL_HEIGHT, 0.1)
        z_frac = max(0.0, min(1.0, z_frac))
        # Radial factor 0 (interior) → 1 (outer)
        dx = pos.x - self.canopy_center.x
        dy = pos.y - self.canopy_center.y
        horiz_dist = math.hypot(dx, dy)
        r_frac = min(1.0, horiz_dist / max(self.canopy_radius, 0.1))
        # Pick palette tier: interior = dark, outer mid, top = light young
        if r_frac < 0.35 and z_frac < 0.7:
            tier_low, tier_high = 0, 1   # dark mature → mid
            blend = r_frac / 0.35
        elif z_frac > 0.75:
            tier_low, tier_high = 1, 2   # mid → light young
            blend = (z_frac - 0.75) / 0.25
        else:
            tier_low, tier_high = 0, 2   # spread across palette
            blend = 0.3 + 0.5 * r_frac
        blend = max(0.0, min(1.0, blend + self.rng.uniform(-0.12, 0.12)))
        c_low = COLOR_LEAF_VARIANTS[tier_low]
        c_high = COLOR_LEAF_VARIANTS[tier_high]
        r = c_low[0] + (c_high[0] - c_low[0]) * blend
        g = c_low[1] + (c_high[1] - c_low[1]) * blend
        b = c_low[2] + (c_high[2] - c_low[2]) * blend
        # AO: interior leaves darker (less skylight)
        ao = 0.6 + 0.4 * max(r_frac, z_frac * 0.8)
        ao = max(0.5, min(1.0, ao))
        # Apply AO as vertex color alpha (shader multiplies into albedo)
        # Vertex color RGB normalized 0..1, used as multiplicative tint
        return (r * 2.0, g * 2.0, b * 2.0, ao)  # ×2 to allow shader brightening if needed

    def build_leaves(self):
        """Per-leaf ovate mesh placement: 137.5° spiral on twigs, opposite pairs on spurs."""
        self.canopy_radius = self._compute_canopy_radius()
        skipped_interior = 0
        placed = 0

        # ----- TWIG LEAVES (long shoots): spiral phyllotaxis -----
        for twig in self.twigs:
            curve = twig["curve"]
            n_leaves = LEAVES_PER_TWIG + self.rng.randint(-1, 1)
            for i in range(n_leaves):
                frac = 0.15 + 0.80 * (i / max(n_leaves - 1, 1))
                pos, _, tan = self._sample_branch_curve(curve, frac)
                # Spiral azimuth around twig axis
                azimuth = i * GOLDEN_ANGLE + math.radians(self.rng.uniform(-LEAF_AZIMUTH_JITTER_DEG, LEAF_AZIMUTH_JITTER_DEG))
                up = Vector((0, 0, 1))
                side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
                fwd = tan.cross(side).normalized()
                radial = math.cos(azimuth) * side + math.sin(azimuth) * fwd
                # Petiole base on twig surface
                base_pos = pos + radial * 0.005
                if self._hollow_core_skip(base_pos):
                    skipped_interior += 1
                    continue
                # Blade extends radially outward + slight forward along twig
                blade_dir = (radial * 0.85 + tan * 0.15).normalized()
                # Heliotropism: bias normal upward (toward sun) more for upper canopy
                z_frac = base_pos.z / max(TOTAL_HEIGHT, 0.1)
                pitch_bias = math.radians(LEAF_PITCH_BIAS_DEG * (0.5 + 0.5 * z_frac))
                blade_normal = (radial.cross(tan).normalized() * math.cos(pitch_bias)
                                + up * math.sin(pitch_bias)).normalized()
                # Make blade_normal perpendicular to blade_dir
                blade_normal = (blade_normal - blade_normal.dot(blade_dir) * blade_dir).normalized()
                roll = self.rng.uniform(-0.3, 0.3)
                scale = self.rng.uniform(*LEAF_SIZE_JITTER)
                length = LEAF_LENGTH * scale
                width = LEAF_LENGTH * LEAF_WIDTH_RATIO * scale
                vcolor = self._leaf_vcolor(base_pos)
                make_ovate_leaf_mesh(self.bm_leaf, base_pos, blade_normal, blade_dir,
                                     length, width, 0, self.leaf_faces,
                                     color_layer=self.leaf_color_layer,
                                     vcolor=vcolor, roll=roll, rng=self.rng)
                placed += 1

        # ----- SPUR LEAVES (rosette): opposite pairs (decussate, 180° apart) -----
        for spur in self.spurs:
            base_pos = spur["pos"]
            tan = spur["tangent"]
            sdir = spur.get("dir", Vector((0, 0, 1)))
            up = Vector((0, 0, 1))
            side = sdir.cross(up).normalized() if abs(sdir.z) < 0.95 else Vector((1, 0, 0))
            fwd = sdir.cross(side).normalized()
            for c in range(LEAVES_PER_SPUR):
                # Distribute leaves along the short spur length
                t_frac = 0.20 + 0.70 * (c / max(LEAVES_PER_SPUR - 1, 1))
                # Opposite pairs: alternate 0° / 180° azimuth with 90° rotation between pairs
                pair_idx = c // 2
                in_pair = c % 2
                base_azimuth = pair_idx * math.pi * 0.5  # 0, 90°, 180° between pairs
                azimuth = base_azimuth + in_pair * math.pi  # +180° within pair
                azimuth += self.rng.uniform(-0.20, 0.20)
                radial = math.cos(azimuth) * side + math.sin(azimuth) * fwd
                leaf_base = base_pos - sdir * 0.005 + radial * 0.004 + sdir * (t_frac * 0.015)
                if self._hollow_core_skip(leaf_base):
                    skipped_interior += 1
                    continue
                # Blade extends radially out from spur, mildly upturned
                blade_dir = (radial * 0.7 + Vector((0, 0, 0.3))).normalized()
                blade_normal = (radial.cross(blade_dir).normalized()
                                + Vector((0, 0, 1)) * 0.6).normalized()
                blade_normal = (blade_normal - blade_normal.dot(blade_dir) * blade_dir).normalized()
                roll = self.rng.uniform(-0.2, 0.2)
                scale = self.rng.uniform(0.90, 1.10)
                length = LEAF_LENGTH * scale
                width = LEAF_LENGTH * LEAF_WIDTH_RATIO * scale
                vcolor = self._leaf_vcolor(leaf_base)
                make_ovate_leaf_mesh(self.bm_leaf, leaf_base, blade_normal, blade_dir,
                                     length, width, 0, self.leaf_faces,
                                     color_layer=self.leaf_color_layer,
                                     vcolor=vcolor, roll=roll, rng=self.rng)
                placed += 1

        print(f"LEAVES: placed={placed}, skipped_interior={skipped_interior} (hollow-core)")

    # ----- APPLES -----
    def build_apples(self):
        """Place apples on spurs in clusters, biased to outer canopy with even azimuth coverage."""
        # Bucket spurs into 8 azimuthal wedges, score by outer-radial distance within each
        N_WEDGES = 8
        wedges = [[] for _ in range(N_WEDGES)]
        for spur in self.spurs:
            p = spur["pos"]
            dx = p.x - self.canopy_center.x
            dy = p.y - self.canopy_center.y
            horiz_dist = math.hypot(dx, dy)
            z_above_center = max(0, p.z - self.canopy_center.z + 0.6)
            score = horiz_dist + z_above_center * 0.25
            # widely accept; bottom apples are also realistic (just exclude trunk-level)
            if p.z < TRUNK_FORK_HEIGHT + 0.1:
                continue
            wedge_az = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)  # 0..1
            wedge_idx = int(wedge_az * N_WEDGES) % N_WEDGES
            wedges[wedge_idx].append((score, spur))

        for w in wedges:
            w.sort(reverse=True, key=lambda x: x[0])

        # Take top spurs from each wedge round-robin for even coverage
        apples_per_wedge_target = max(2, APPLE_COUNT_TARGET // N_WEDGES + 1)
        outer = []
        for round_i in range(apples_per_wedge_target):
            for w in wedges:
                if round_i < len(w):
                    outer.append(w[round_i][1])

        self.rng.shuffle(outer)

        target = APPLE_COUNT_TARGET
        placed = 0
        cluster_sizes = [1, 2, 3, 4, 5]
        for spur in outer:
            if placed >= target:
                break
            csize = self.rng.choices(cluster_sizes, weights=APPLE_CLUSTER_WEIGHTS, k=1)[0]
            csize = min(csize, target - placed)
            # Push apple anchor outward along spur direction to lift fruit out of leaf cloud
            spur_dir = spur.get("dir", Vector((0, 0, -1)))
            outward_push = spur_dir * APPLE_OUTWARD_PUSH
            for k in range(csize):
                ang = (2 * math.pi * k / max(csize, 1)) + self.rng.uniform(-0.4, 0.4)
                spread = 0.030
                offset = Vector((math.cos(ang) * spread, math.sin(ang) * spread, 0))
                center = spur["pos"] + outward_push + offset
                make_apple(self.bm_apple, center, 0, 1, self.apple_faces, self.rng)
                placed += 1

    # ----- ASSEMBLE OBJECTS -----
    def assemble(self):
        # Create wood object with bark material
        wood_mesh = bpy.data.meshes.new("Wood_Mesh")
        self.bm_wood.normal_update()
        self.bm_wood.to_mesh(wood_mesh)
        self.bm_wood.free()
        wood_mesh.update()
        wood_obj = bpy.data.objects.new("AppleTree_Wood", wood_mesh)
        bpy.context.collection.objects.link(wood_obj)
        bark_mat = make_pbr_material("M_Bark", COLOR_BARK, alpha=False, roughness=0.85)
        wood_obj.data.materials.append(bark_mat)

        # Leaf object — single M_Leaf material + vertex color tint (50-agent panel)
        leaf_mesh = bpy.data.meshes.new("Leaf_Mesh")
        self.bm_leaf.normal_update()
        self.bm_leaf.to_mesh(leaf_mesh)
        self.bm_leaf.free()
        leaf_mesh.update()
        leaf_obj = bpy.data.objects.new("AppleTree_Leaves", leaf_mesh)
        bpy.context.collection.objects.link(leaf_obj)
        leaf_mat = make_leaf_material("M_Leaf", COLOR_LEAF_VARIANTS[1],
                                      texture_path=self.leaf_texture_path)
        leaf_obj.data.materials.append(leaf_mat)
        # Apply spherical canopy normals (foliage volume hint)
        self._apply_spherical_normals(leaf_obj, self.canopy_center)
        for p in leaf_mesh.polygons:
            p.use_smooth = True

        # Apple object
        apple_mesh = bpy.data.meshes.new("Apple_Mesh")
        self.bm_apple.normal_update()
        self.bm_apple.to_mesh(apple_mesh)
        self.bm_apple.free()
        apple_mesh.update()
        apple_obj = bpy.data.objects.new("AppleTree_Apples", apple_mesh)
        bpy.context.collection.objects.link(apple_obj)
        apple_mat = make_pbr_material("M_Apple", COLOR_APPLE, alpha=False, roughness=0.45)
        stem_mat = make_pbr_material("M_AppleStem", COLOR_STEM, alpha=False, roughness=0.8)
        apple_obj.data.materials.append(apple_mat)
        apple_obj.data.materials.append(stem_mat)
        # Assign material indices using tracked face ranges
        self._assign_material_indices(apple_obj, self.apple_faces)
        for p in apple_mesh.polygons:
            p.use_smooth = True

        return wood_obj, leaf_obj, apple_obj

    def _apply_spherical_normals(self, obj, center):
        """Set per-vertex normals to point radially outward from `center` for fake canopy volume."""
        mesh = obj.data
        if not mesh.has_custom_normals:
            mesh.use_auto_smooth = True
        normals = []
        for v in mesh.vertices:
            world_pos = v.co
            n = (world_pos - center)
            if n.length < 1e-5:
                n = Vector((0, 0, 1))
            else:
                n = n.normalized()
            normals.append(n)
        # Build loop normals matching vertex normals
        loop_normals = []
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                loop_normals.append(normals[vi])
        mesh.normals_split_custom_set(loop_normals)
        mesh.use_auto_smooth = True

    def _assign_material_indices(self, obj, face_track):
        """face_track: {mat_idx: [(start, end), ...]}."""
        mesh = obj.data
        for mat_idx, ranges in face_track.items():
            for start, end in ranges:
                for fi in range(start, end):
                    if fi < len(mesh.polygons):
                        mesh.polygons[fi].material_index = mat_idx


# ------------------------------------------------------------------
# MATERIALS
# ------------------------------------------------------------------

def make_pbr_material(name, color, alpha=False, roughness=0.7):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    if alpha:
        mat.blend_method = 'CLIP'
        mat.shadow_method = 'CLIP'
        mat.use_backface_culling = False
        mat.alpha_threshold = 0.5
    return mat


def make_leaf_material(name, fallback_color, texture_path=None):
    """Single M_Leaf material — vertex color tint × texture × backface culling on.

    If texture_path provided, image is used as base color + alpha mask. Otherwise
    fallback_color is used (vertex color provides per-leaf tint variation).
    Vertex color: RGB tint (×0.5 to compensate for ×2 in _leaf_vcolor), A AO multiplier.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    # Clear default nodes
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    output = nt.nodes.new('ShaderNodeOutputMaterial')
    output.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    bsdf.inputs["Roughness"].default_value = 0.55
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.4
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.4
    nt.links.new(bsdf.outputs[0], output.inputs[0])

    # Vertex color node
    vcol = nt.nodes.new('ShaderNodeVertexColor')
    vcol.layer_name = "Col"
    vcol.location = (-300, 100)

    # Multiply vcolor RGB by 0.5 to compensate for ×2 stored
    color_mult = nt.nodes.new('ShaderNodeMixRGB')
    color_mult.blend_type = 'MULTIPLY'
    color_mult.inputs[0].default_value = 1.0
    color_mult.location = (0, 100)
    half_white = nt.nodes.new('ShaderNodeRGB')
    half_white.outputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    half_white.location = (-300, -50)

    if texture_path and os.path.exists(texture_path):
        tex = nt.nodes.new('ShaderNodeTexImage')
        try:
            tex.image = bpy.data.images.load(texture_path)
        except RuntimeError:
            tex.image = None
        tex.location = (-300, 300)
        # Multiply texture × vertex color
        nt.links.new(tex.outputs["Color"], color_mult.inputs[1])
        nt.links.new(vcol.outputs["Color"], color_mult.inputs[2])
        nt.links.new(color_mult.outputs[0], bsdf.inputs["Base Color"])
        # Alpha from texture
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    else:
        # No texture — use fallback color × vertex color
        fb = nt.nodes.new('ShaderNodeRGB')
        fb.outputs[0].default_value = (*fallback_color, 1.0)
        fb.location = (-300, 300)
        nt.links.new(fb.outputs[0], color_mult.inputs[1])
        nt.links.new(vcol.outputs["Color"], color_mult.inputs[2])
        nt.links.new(color_mult.outputs[0], bsdf.inputs["Base Color"])

    mat.diffuse_color = (*fallback_color, 1.0)
    mat.blend_method = 'CLIP'
    mat.shadow_method = 'CLIP'
    mat.use_backface_culling = True   # cull_back: backface culling AÇIK (eleştirmen)
    mat.alpha_threshold = 0.5
    return mat


def bake_leaf_texture(out_path, res=512):
    """Procedural ovate leaf alpha texture bake — Blender shader nodes → PNG.

    Creates a temp plane with a shader that generates an ovate silhouette + leaf
    color + subtle vein pattern, bakes to image, exports PNG. The texture is then
    used by make_leaf_material() as placeholder until user supplies a real photo.

    Returns the path to the baked PNG, or None on failure.
    """
    try:
        # Create temp plane
        bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
        plane = bpy.context.object
        plane.name = "_LeafBakeTemp"

        # Build shader: super-ellipse alpha mask + leaf color + vein gradient
        mat = bpy.data.materials.new("_BakeLeafMat")
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)

        output = nt.nodes.new('ShaderNodeOutputMaterial')
        output.location = (800, 0)
        emit = nt.nodes.new('ShaderNodeEmission')
        emit.location = (600, 0)
        nt.links.new(emit.outputs[0], output.inputs[0])

        # Generated tex coord centered (0..1, 0..1) → (-0.5..0.5, -0.5..0.5)
        texcoord = nt.nodes.new('ShaderNodeTexCoord')
        texcoord.location = (-800, 0)
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        sep.location = (-600, 0)
        nt.links.new(texcoord.outputs["Generated"], sep.inputs[0])

        # u = (x - 0.5), v = (y - 0.5)
        u_sub = nt.nodes.new('ShaderNodeMath')
        u_sub.operation = 'SUBTRACT'
        u_sub.inputs[1].default_value = 0.5
        u_sub.location = (-400, 100)
        nt.links.new(sep.outputs["X"], u_sub.inputs[0])
        v_sub = nt.nodes.new('ShaderNodeMath')
        v_sub.operation = 'SUBTRACT'
        v_sub.inputs[1].default_value = 0.5
        v_sub.location = (-400, -50)
        nt.links.new(sep.outputs["Y"], v_sub.inputs[0])

        # Ovate silhouette: ellipse stretched in v, narrowing at v→±0.5
        # silhouette = (u / (width(v)))^2 + (v / 0.5)^2 < 1
        # width(v) = base_w * (1 - |v|*2)^0.5 - taper at top
        v_abs = nt.nodes.new('ShaderNodeMath')
        v_abs.operation = 'ABSOLUTE'
        v_abs.location = (-200, -50)
        nt.links.new(v_sub.outputs[0], v_abs.inputs[0])
        # taper = 1 - |v|*0.8  (width narrows toward tip/base)
        taper = nt.nodes.new('ShaderNodeMath')
        taper.operation = 'MULTIPLY'
        taper.inputs[1].default_value = 0.8
        taper.location = (0, -50)
        nt.links.new(v_abs.outputs[0], taper.inputs[0])
        taper_inv = nt.nodes.new('ShaderNodeMath')
        taper_inv.operation = 'SUBTRACT'
        taper_inv.inputs[0].default_value = 1.0
        taper_inv.location = (200, -50)
        nt.links.new(taper.outputs[0], taper_inv.inputs[1])
        # half_width = 0.25 * taper  (max blade width 0.5 at v=0)
        half_w = nt.nodes.new('ShaderNodeMath')
        half_w.operation = 'MULTIPLY'
        half_w.inputs[1].default_value = 0.32
        half_w.location = (400, -50)
        nt.links.new(taper_inv.outputs[0], half_w.inputs[0])
        # u_norm = |u| / half_width
        u_abs = nt.nodes.new('ShaderNodeMath')
        u_abs.operation = 'ABSOLUTE'
        u_abs.location = (-200, 100)
        nt.links.new(u_sub.outputs[0], u_abs.inputs[0])
        u_norm = nt.nodes.new('ShaderNodeMath')
        u_norm.operation = 'DIVIDE'
        u_norm.location = (600, 50)
        nt.links.new(u_abs.outputs[0], u_norm.inputs[0])
        nt.links.new(half_w.outputs[0], u_norm.inputs[1])
        # alpha = 1 - smoothstep(0.85, 1.0, u_norm)  — hard ovate edge
        alpha_ramp = nt.nodes.new('ShaderNodeMapRange')
        alpha_ramp.inputs[1].default_value = 0.85
        alpha_ramp.inputs[2].default_value = 1.0
        alpha_ramp.inputs[3].default_value = 1.0
        alpha_ramp.inputs[4].default_value = 0.0
        alpha_ramp.clamp = True
        alpha_ramp.location = (800, 50)
        nt.links.new(u_norm.outputs[0], alpha_ramp.inputs[0])

        # Leaf color: midtone green with vein pattern (darker midrib)
        leaf_color = nt.nodes.new('ShaderNodeRGB')
        leaf_color.outputs[0].default_value = (*COLOR_LEAF_VARIANTS[1], 1.0)
        leaf_color.location = (0, 300)
        vein_color = nt.nodes.new('ShaderNodeRGB')
        vein_color.outputs[0].default_value = (
            COLOR_LEAF_VARIANTS[0][0] * 0.6,
            COLOR_LEAF_VARIANTS[0][1] * 0.6,
            COLOR_LEAF_VARIANTS[0][2] * 0.6,
            1.0,
        )
        vein_color.location = (0, 150)
        # Vein mask: darken near midrib (small |u|)
        vein_mask = nt.nodes.new('ShaderNodeMapRange')
        vein_mask.inputs[1].default_value = 0.0
        vein_mask.inputs[2].default_value = 0.04
        vein_mask.inputs[3].default_value = 1.0
        vein_mask.inputs[4].default_value = 0.0
        vein_mask.clamp = True
        vein_mask.location = (200, 150)
        nt.links.new(u_abs.outputs[0], vein_mask.inputs[0])
        # Mix leaf_color with vein_color by vein_mask
        col_mix = nt.nodes.new('ShaderNodeMixRGB')
        col_mix.location = (400, 250)
        nt.links.new(vein_mask.outputs[0], col_mix.inputs[0])
        nt.links.new(leaf_color.outputs[0], col_mix.inputs[1])
        nt.links.new(vein_color.outputs[0], col_mix.inputs[2])
        nt.links.new(col_mix.outputs[0], emit.inputs["Color"])

        plane.data.materials.append(mat)

        # Setup bake image
        img = bpy.data.images.new("_LeafBake", width=res, height=res, alpha=True)
        # Add image texture node and select it for bake target
        tex_node = nt.nodes.new('ShaderNodeTexImage')
        tex_node.image = img
        tex_node.location = (-1000, -200)
        nt.nodes.active = tex_node

        # Build alpha-multiplied color: out_rgba = (col.rgb, alpha) — bake combined RGBA
        # Use Combine RGB approach: emit color is RGB, need to bake alpha into image's alpha channel
        # Solution: do 2 passes (color, then alpha), OR set emission strength = alpha
        # Simpler: set image pixels manually after baking color.
        # For now: bake EMIT (color), then write alpha via second pass.

        # Switch to cycles for bake
        scene = bpy.context.scene
        old_engine = scene.render.engine
        scene.render.engine = 'CYCLES'
        scene.cycles.bake_type = 'EMIT'
        scene.cycles.samples = 4
        scene.cycles.use_denoising = False

        # Select plane only
        for o in bpy.context.scene.objects:
            o.select_set(o is plane)
        bpy.context.view_layer.objects.active = plane

        # Bake color
        try:
            bpy.ops.object.bake(type='EMIT')
        except Exception as e:
            print(f"Bake color failed: {e}")
            scene.render.engine = old_engine
            return None

        # Now compute alpha per-pixel via second bake: hook alpha_ramp.Result → emit.Color
        nt.links.new(alpha_ramp.outputs[0], emit.inputs["Color"])
        # Bake alpha (will write grayscale into image)
        alpha_img = bpy.data.images.new("_LeafBakeAlpha", width=res, height=res, alpha=False)
        tex_node.image = alpha_img
        try:
            bpy.ops.object.bake(type='EMIT')
        except Exception as e:
            print(f"Bake alpha failed: {e}")
            scene.render.engine = old_engine
            return None

        # Combine: image rgb from img, alpha from alpha_img
        rgb_pixels = list(img.pixels)
        alpha_pixels = list(alpha_img.pixels)
        n_px = res * res
        combined = [0.0] * (n_px * 4)
        for i in range(n_px):
            combined[i * 4 + 0] = rgb_pixels[i * 4 + 0]
            combined[i * 4 + 1] = rgb_pixels[i * 4 + 1]
            combined[i * 4 + 2] = rgb_pixels[i * 4 + 2]
            combined[i * 4 + 3] = alpha_pixels[i * 4 + 0]
        img.pixels = combined
        img.filepath_raw = out_path
        img.file_format = 'PNG'
        img.save()
        print(f"Baked leaf texture → {out_path}")

        scene.render.engine = old_engine
        # Cleanup
        bpy.data.objects.remove(plane, do_unlink=True)
        bpy.data.materials.remove(mat, do_unlink=True)
        bpy.data.images.remove(img, do_unlink=True)
        bpy.data.images.remove(alpha_img, do_unlink=True)
        return out_path
    except Exception as e:
        print(f"bake_leaf_texture exception: {e}")
        return None


def export_glb(out_path):
    """Export tree as GLB with vertex colors + embedded textures (Round 5 — pipeline fix)."""
    # Select only tree objects (deselect everything else first)
    for o in bpy.context.scene.objects:
        o.select_set(False)
    targets = []
    for name in ["AppleTree_Wood", "AppleTree_Leaves", "AppleTree_Apples"]:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            obj.select_set(True)
            targets.append(obj)
    if not targets:
        print("export_glb: no tree objects found")
        return False

    try:
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format='GLB',
            use_selection=True,
            export_yup=True,
            export_materials='EXPORT',
            export_image_format='AUTO',
            export_apply=True,
            export_attributes=True,
            export_colors=True,
            export_normals=True,
            export_texcoords=True,
            export_animations=False,
            export_lights=False,
            export_cameras=False,
        )
        size_kb = os.path.getsize(out_path) // 1024
        print(f"Exported GLB: {out_path} ({size_kb} KB)")
        return True
    except Exception as e:
        print(f"export_glb failed: {e}")
        return False


# ------------------------------------------------------------------
# RENDER / VERIFY
# ------------------------------------------------------------------

def setup_world():
    """Sky-like background and sun lamp."""
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.66, 0.78, 0.92, 1.0)
        bg.inputs["Strength"].default_value = 0.9

    # Sun
    sun_data = bpy.data.lights.new("Sun", 'SUN')
    sun_data.energy = 4.0
    sun_data.angle = math.radians(8)
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = Euler((math.radians(50), math.radians(15), math.radians(35)))
    bpy.context.collection.objects.link(sun)

    # Ground plane (simple, just for context in renders)
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, -0.001))
    ground = bpy.context.object
    ground.name = "Ground"
    gm = make_pbr_material("M_Ground", (0.30, 0.34, 0.18), roughness=0.95)
    ground.data.materials.append(gm)


def place_camera(view_name):
    """Place camera for given view: 'front', 'side', 'three_quarter', 'top'."""
    cam_data = bpy.data.cameras.new(f"Cam_{view_name}")
    cam_data.lens = 50
    cam = bpy.data.objects.new(f"Cam_{view_name}", cam_data)
    bpy.context.collection.objects.link(cam)

    # Cameras aim slightly below crown centroid (z≈2.0m) at canopy mass
    if view_name == "front":
        cam.location = (0, -9, 2.2)
        cam.rotation_euler = Euler((math.radians(86), 0, 0))
    elif view_name == "side":
        cam.location = (9, 0, 2.2)
        cam.rotation_euler = Euler((math.radians(86), 0, math.radians(90)))
    elif view_name == "three_quarter":
        cam.location = (6.5, -6.5, 2.7)
        cam.rotation_euler = Euler((math.radians(82), 0, math.radians(45)))
    elif view_name == "top":
        cam.location = (0, 0, 9)
        cam.rotation_euler = Euler((0, 0, math.radians(0)))
    elif view_name == "close":
        cam.location = (2.8, -2.8, 1.8)
        cam.rotation_euler = Euler((math.radians(84), 0, math.radians(45)))
        cam_data.lens = 80
    bpy.context.scene.camera = cam


def render_view(view_name, round_n):
    place_camera(view_name)
    scene = bpy.context.scene
    if bpy.app.version >= (4, 2, 0) and bpy.app.version < (5, 0, 0):
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    else:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RES
    scene.render.film_transparent = False
    scene.render.filepath = RENDER_OUT_TMPL.format(round=round_n, view=view_name)
    bpy.ops.render.render(write_still=True)


def verify_tree(wood_obj, leaf_obj, apple_obj):
    def tri_count(obj):
        n = 0
        for p in obj.data.polygons:
            n += max(1, len(p.vertices) - 2)
        return n
    wood_tri = tri_count(wood_obj)
    leaf_tri = tri_count(leaf_obj)
    apple_tri = tri_count(apple_obj)
    total = wood_tri + leaf_tri + apple_tri
    # Bounding box
    all_verts = []
    for o in [wood_obj, leaf_obj, apple_obj]:
        for v in o.data.vertices:
            all_verts.append(v.co)
    if all_verts:
        xs = [v.x for v in all_verts]
        ys = [v.y for v in all_verts]
        zs = [v.z for v in all_verts]
        bbox = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    else:
        bbox = (0, 0, 0)
    print("=" * 50)
    print(f"VERIFY: wood={wood_tri} leaf={leaf_tri} apple={apple_tri} total={total}")
    print(f"VERIFY: bbox W={bbox[0]:.2f} D={bbox[1]:.2f} H={bbox[2]:.2f}")
    print(f"VERIFY: target 13500-16500 tris -> {'OK' if 13500 <= total <= 16500 else 'OUT OF RANGE'}")
    print("=" * 50)
    return {"wood": wood_tri, "leaf": leaf_tri, "apple": apple_tri, "total": total, "bbox": bbox}


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

LEAF_TEXTURE_PATH = os.path.join(OUT_DIR, "textures", "leaf", "leaf_placeholder.png")
OUT_GLB = os.path.join(OUT_DIR, "elma_agaci.glb")


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--render", action="store_true")
    p.add_argument("--round", type=int, default=22)
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--no-bake", action="store_true",
                   help="Skip leaf texture bake (use existing or fallback color)")
    p.add_argument("--export-glb", action="store_true",
                   help="Export tree as GLB at OUT_GLB path")
    return p.parse_args(argv)


def main():
    args = parse_args()
    reset_scene()

    # Round 3: bake procedural leaf texture (placeholder until user supplies real)
    texture_path = None
    if not args.no_bake:
        os.makedirs(os.path.dirname(LEAF_TEXTURE_PATH), exist_ok=True)
        texture_path = bake_leaf_texture(LEAF_TEXTURE_PATH, res=512)
        # After bake, reset scene clean for tree build
        reset_scene()

    builder = TreeBuilder(seed=args.seed)
    builder.leaf_texture_path = texture_path
    builder.build_trunk_and_branches()
    builder.build_leaves()
    builder.build_apples()
    wood_obj, leaf_obj, apple_obj = builder.assemble()
    stats = verify_tree(wood_obj, leaf_obj, apple_obj)
    setup_world()
    if not args.no_save:
        bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
        print(f"Saved: {OUT_BLEND}")
    if args.export_glb:
        export_glb(OUT_GLB)
    if args.render:
        for view in ["three_quarter", "front", "side", "close"]:
            render_view(view, args.round)
            print(f"Rendered: {view}")


if __name__ == "__main__":
    main()
