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
from mathutils import Euler, Matrix, Quaternion, Vector, noise as mu_noise

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
DEFAULT_SEED = 42
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Tree macro
TOTAL_HEIGHT = 3.8               # Round 27: trunk relative kısaltıldı (4.2→3.8) — broad spreading hedef
TRUNK_LEAN_DEG = 7.0
TRUNK_S_CURVE_AMP = 0.08
TRUNK_FORK_HEIGHT = 0.75         # ↓ from 0.85 — daha alçak fork → daha yatay spread için yer
TRUNK_GEOM_TOP_FRAC = 0.68       # ↓ from 0.72 — trunk top daha kısa, canopy daha geniş

# Trunk radii (thicker base + stronger flare + gnarl noise)
TRUNK_BASE_R = 0.14
TRUNK_FORK_R = 0.10
TRUNK_TOP_R = 0.025              # taper to near-point inside canopy
ROOT_FLARE_FACTOR = 2.50         # Round 26 AAA: agresif kök yatağı (eskiden 1.55)
ROOT_FLARE_HEIGHT = 0.55         # Round 26 AAA: flare bölgesi genişletildi (eskiden 0.28)
BUTTRESS_LOBES = 5               # Round 26: 5-lobe (asymmetric, AAA standart)
BUTTRESS_AMP = 0.32              # Round 26: lobes daha belirgin (eskiden 0.22)

# Round 26 — Surface roots (yer üstü görünür kök buttress'leri)
N_SURFACE_ROOTS = 5
ROOT_LENGTH_RANGE = (0.45, 0.75)
ROOT_BASE_R = 0.055
ROOT_TIP_R = 0.012
ROOT_PITCH_RANGE_DEG = (-38.0, -22.0)   # toprağa doğru iniş açısı
ROOT_AZIMUTH_JITTER_DEG = 18            # ±18° (72° spacing'den sapma)
ROOT_SEGMENTS = 4
ROOT_RADIAL_SEGS = 5
ROOT_GRAVITY_K = -0.18                  # ters S-curve (uca doğru yere gömül)
ROOT_DARKEN = 0.85                      # bark vcolor ×0.85 (toprağa yakın koyulaşma)

# Round 26 — Gravimorphism (gravity sag) coefficients per tier
GRAVITY_K_SCAFFOLD = 0.22
GRAVITY_K_SECONDARY = 0.18
GRAVITY_K_TWIG = 0.10
GRAVITY_K_SUBTWIG = 0.05

# Round 26 — Branch collar swelling at junction (ilk ring radius bulge)
COLLAR_BULGE_FACTOR = 0.55       # ilk ring radius × (1 + 0.55 × exp(-i/2))
COLLAR_BULGE_RINGS = 2           # kaç ring etkilenir

# Round 26 — Dead snags (kırık kuru dal güdükleri)
N_DEAD_SNAGS_RANGE = (2, 4)
DEAD_SNAG_LENGTH_RANGE = (0.08, 0.18)
DEAD_SNAG_BASE_R = 0.016
DEAD_SNAG_TIP_R = 0.004
DEAD_SNAG_SEGMENTS = 3
DEAD_SNAG_RADIAL_SEGS = 4
DEAD_SNAG_DARKEN = 0.65          # kuru kabuk daha koyu
TRUNK_GNARL_AMP = 0.18           # ↑ stronger
TRUNK_GNARL_FREQ_Z = 6.5
TRUNK_GNARL_FREQ_THETA = 4.0
TRUNK_BURL_COUNT = 3             # one more burl
TRUNK_BURL_AMP = 0.40            # ↑ stronger localized swells
TRUNK_BURL_SIGMA = 0.09          # tighter falloff (was implicit 0.18)
TRUNK_RADIAL_SEGS = 11
TRUNK_HEIGHT_SEGS = 10

# Scaffold branches (primaries)
N_SCAFFOLDS = 6                  # Round 27: 5→6 (daha çok primary spread için)
N_CO_LEADERS = 2
CO_LEADER_R_BOOST = 1.35
CO_LEADER_CROTCH_DEG = (45.0, 56.0)   # ↓ Round 27: co-leaders daha dik (upward growth, tree shape)
SCAFFOLD_PITCH_Z = 0.16          # ↓ from 0.18 — staggered scaffolds daha sıkı band
SCAFFOLD_LENGTH_RANGE = (2.0, 2.7)    # ↑ from (1.7-2.4) — daha geniş spread
SCAFFOLD_CROTCH_RANGE_DEG = (58.0, 74.0)   # ↑ from (42-58°) Round 27: scaffolds daha YATAY (spreading apple form)
SCAFFOLD_R_FACTOR = 0.52
SCAFFOLD_TIP_R_FACTOR = 0.26
SCAFFOLD_SEGMENTS = 5
SCAFFOLD_RADIAL_SEGS = 7
SCAFFOLD_AZIMUTH_MODE = "even"

# Upper crown branches — Round 27: trunk üstünü doldur, "narrow top" sorununu çöz
N_UPPER_BRANCHES = 7             # ↑ from 4 — trunk top kapsama
UPPER_BRANCH_START_FRAC = 0.55   # ↓ from 0.62 — daha geniş z bandı
UPPER_BRANCH_LENGTH_RANGE = (1.30, 1.95)   # ↑ longer reach
UPPER_BRANCH_CROTCH_DEG = (32.0, 55.0)   # daha dik (upward) ama spread için bazı dallar geniş

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
TWIGS_PER_SECONDARY_RANGE = (3, 4)   # ↑ from (2,4) Round 25 — daha cok lateral
TWIG_LENGTH_RANGE = (0.14, 0.38)
TWIG_ANGLE_RANGE_DEG = (35.0, 65.0)
TWIG_R_FACTOR = 0.55
TWIG_TIP_R_FACTOR = 0.30
TWIG_SEGMENTS = 2
TWIG_RADIAL_SEGS = 4
TWIG_START_FRAC = 0.18

# Round 25 — Sub-twigs: yeni dallanma seviyesi (twig'in kendi alt-twig'leri)
SUBTWIGS_PER_TWIG_RANGE = (1, 2)
SUBTWIG_T_POINTS = (0.32, 0.60, 0.85)   # parent twig boyunca yerlesim noktalari
SUBTWIG_LENGTH_FACTOR = (0.50, 0.70)    # parent uzunlugun %50-70'i
SUBTWIG_R_FACTOR = 0.70                 # parent yaricapin %70'i
SUBTWIG_ANGLE_RANGE_DEG = (45.0, 80.0)  # parent'tan ayrilis acisi
SUBTWIG_SEGMENTS = 2
SUBTWIG_RADIAL_SEGS = 3                 # ince dal — 3 yan yeterli

# Spurs
SPURS_PER_SECONDARY_AVG = 5
SPURS_PER_TWIG_AVG = 0.5
SPUR_LENGTH_RANGE = (0.020, 0.038)
SPUR_BASE_R = 0.0050
SPUR_TIP_R = 0.0032
SPUR_RADIAL_SEGS = 4
SPUR_SEGMENTS = 1                # single segment is enough at this scale

# Leaves — Round 23: CLUSTER ALPHA CARD (industry standard, SpeedTree/RDR2/Genshin pattern)
# Cross-quad (X-pattern) cards with baked alpha atlas showing 5-7 leaf silhouettes per cell.
# Card boundary invisible due to soft alpha; multiple cards form spherical cluster volume.
LEAF_CARD_W = 0.22               # cluster card width (m) — covers 5-7 leaves in texture
LEAF_CARD_H = 0.20
USE_CROSS_QUAD = True            # X-pattern: 2 perpendicular quads = 4 tri/cluster
ATLAS_GRID = 3                   # Round 26: 3×3 = 9 cluster variants (tint variation AAA)
ATLAS_RES = 768                  # ↑ 512 → 768 for 3×3 (256px/cell aynı)
LEAVES_PER_ATLAS_CELL = 6        # silhouettes baked into each cell

# Foliage volume placement — clusters at twig tips form spherical bouquets
# Round 24 — Botanist panel: along-twig parametric placement (kills floating bouquets)
CARDS_PER_TWIG_ALONG = 4         # ↓ from 5 Round 27 — trunk-mid puff için yer
CARDS_PER_TWIG_TERMINAL = 2      # ↓ from 3
CARDS_PER_SUBTWIG_ALONG = 2      # sub-twig: hafif yapraklanma
CARDS_PER_SUBTWIG_TERMINAL = 2
CLUSTERS_PER_SPUR = 2            # ↓ from 3 — tri budget için (Stage 1 fix Round 27)

# Round 26 — Multi-shell foliage (AAA dolgunluk)
# Hollow-core INVERTED: sadece trunk axis çevresinde skip (broadleaf canopy dense-cored)
INNER_FILL_CARDS_PER_SECONDARY = 3   # Round 27: 4→3 (tri budget + secondary sayısı arttı)
INNER_FILL_CARD_W = 0.15             # küçük boy (interior shadow)
INNER_FILL_CARD_H = 0.13
INNER_FILL_CROSS_QUAD = False        # single quad (2 tri, fill için derinlik gereksiz)

FORK_PUFFS_PER_SCAFFOLD = 1          # her scaffold base'inde 1 puff
FORK_PUFF_CARDS = 30                 # ↓ 35→30 (Round 27 tri budget)
FORK_PUFF_RADIUS = 0.40              # puff sphere radius
FORK_PUFF_OFFSET = 0.30              # scaffold base'inden radial dışa
FORK_PUFF_CARD_W = 0.20
FORK_PUFF_CARD_H = 0.18
FORK_PUFF_CROSS_QUAD = False         # fill, single quad

# Round 27 — Crown apex puff: trunk üstü merkez vertikal kolonu doldur (Stage 1 silüet fix)
CROWN_APEX_CARDS = 80                # trunk üstüne büyük volumetric clump
CROWN_APEX_RADIUS = 0.55             # apex puff sphere radius
CROWN_APEX_CARD_W = 0.22
CROWN_APEX_CARD_H = 0.20
CROWN_APEX_Z_OFFSET = 0.15           # trunk top'tan ne kadar yukarı

GROUND_LITTER_CARDS = 80             # trunk tabanında dağılmış yaprak hint
GROUND_LITTER_RADIUS = 0.85          # trunk merkezinden max yarıçap
GROUND_LITTER_HEIGHT = 0.08          # zemine yakın hover
GROUND_LITTER_CARD_W = 0.10
GROUND_LITTER_CARD_H = 0.09

# Inverted hollow core: trunk axis yakın küçük gerçek hollow
TRUNK_AXIS_HOLLOW_RADIUS = 0.30      # bu yarıçap içindeki cards skip edilir
TRUNK_AXIS_HOLLOW_SKIP_PROB = 0.65
LEAF_ALONG_T_START = 0.18        # skip basal 18% (sparse basal in reality)
LEAF_ALONG_T_END = 0.92          # skip absolute tip (terminal handles that)
LEAF_PETIOLE_LEN = 0.025         # 2.5 cm petiole — leaves attached visibly
LEAF_TERMINAL_OFFSET = 0.04      # terminal cluster jitter radius (tight)
LEAF_CARD_TILT_JITTER_DEG = 20   # ±20° normal jitter (SpeedTree sweet spot)

# Card transform variation (organic look — user feedback: rotasyon/scale artırılmalı)
LEAF_CARD_SIZE_JITTER = (0.65, 1.20)
LEAF_CARD_YAW_JITTER_DEG = 180   # full random yaw around vertical
LEAF_CARD_PITCH_JITTER_DEG = 60  # wide pitch variation
LEAF_CARD_ROLL_JITTER_DEG = 180  # full roll for X-pattern variation

# Canopy density gradient (LAI: outer dense, inner sparse)
LEAF_HOLLOW_CORE_THRESHOLD = 0.45
LEAF_HOLLOW_SKIP_PROB = 0.40

# Apples — biggers + visible + botanically paired (50-agent panel)
APPLE_COUNT_TARGET = 25          # user feedback Round 23: 12-25 düşük poly elma
APPLE_DIAMETER = 0.130           # ↑ from 0.10 — "elmalar biraz küçük" feedback
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
COLOR_BARK   = (0.26, 0.21, 0.17)   # fallback (used if vcolor missing)
# Round 24 — Botanist panel: cool grey-brown bark by branch order (linear-RGB)
COLOR_BARK_TIERS = [
    (0.18, 0.15, 0.13),    # 0 trunk: dark grey-brown, fissured plates
    (0.26, 0.21, 0.17),    # 1 scaffold: mid grey-brown, lenticels
    (0.34, 0.26, 0.19),    # 2 secondary: warmer smooth brown, no fissures
    (0.42, 0.22, 0.16),    # 3 twig: reddish-mahogany current-year shoot
]
# Crack/fissure parameters (procedural vertex color, trunk + scaffold only)
BARK_CRACK_SCALE_Z = 8.0       # stretches noise vertically → vertical fissures
BARK_CRACK_SCALE_XY = 2.5
BARK_CRACK_THRESHOLD = -0.15
BARK_CRACK_DARKEN = 0.45        # crack vert color = base * 0.45

COLOR_LEAF_VARIANTS = [
    (0.18, 0.42, 0.13),     # darker mature
    (0.24, 0.52, 0.18),     # midtone
    (0.32, 0.58, 0.22),     # lighter young leaves
]
COLOR_APPLE  = (0.85, 0.13, 0.10)
# Round 24 — Pomologist panel: Gala variety (sun/shade gradient)
COLOR_APPLE_SUN    = (0.45, 0.04, 0.03)    # primary red (sun-side)
COLOR_APPLE_SHADE  = (0.55, 0.42, 0.08)    # yellow-green (shade-side)
COLOR_APPLE_STRIPE = (0.28, 0.02, 0.02)    # deep red stripe
COLOR_APPLE_ENDS   = (0.18, 0.06, 0.04)    # calyx/stem-end darkening
COLOR_STEM_BASE    = (0.30, 0.32, 0.10)    # greenish near apple
COLOR_STEM_TIP     = (0.22, 0.14, 0.06)    # corky brown at branch attach
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


def branch_curve(base_pos, base_dir, length, base_r, tip_r, segments, droop_m,
                 lateral_jitter, rng, gravity_k=0.0):
    """Generate ascending-then-arching branch curve with optional gravimorphism.

    Round 26 AAA: gravity_k > 0 adds weight-sag S-curve along branch with
    apical recovery near tip (real branches sag in middle, lift slightly at tip).
    Negative gravity_k inverts curve (used for surface roots: dive then level off).

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
        # Round 26: Gravimorphism — z-offset(t) = -k * length² * t^1.5 * (1 - 0.3*t)
        # Apical recovery: tip kalkar (1 - 0.3*t çarpanı tip'te etkiyi azaltır)
        if abs(gravity_k) > 1e-5:
            sag = -gravity_k * (length ** 2) * (t ** 1.5) * (1.0 - 0.3 * t)
            pos = pos + Vector((0, 0, sag))
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

def build_tube(bm, curve_pts, radial_segs, mat_index, face_index_track, tier=0,
               collar_bulge=0.0):
    """Build a tube along the curve and record face indices for material assignment.

    curve_pts: list of (pos, radius, tangent, radial_mod_or_None).
    `tier` (0=trunk, 1=scaffold, 2=secondary, 3=twig) stamped on every vert
    along with `branch_t` (0=base..1=tip) for later vcolor gradient.

    Round 26 AAA: `collar_bulge` > 0 → ilk COLLAR_BULGE_RINGS halkaları
    radius × (1 + collar_bulge × exp(-i)) bulge (junction shoulder swelling).
    """
    tier_layer = bm.verts.layers.int.get('tier') or bm.verts.layers.int.new('tier')
    t_layer = bm.verts.layers.float.get('branch_t') or bm.verts.layers.float.new('branch_t')
    rings = []
    n_pts = len(curve_pts)
    for i, pt in enumerate(curve_pts):
        pos, r, tangent = pt[0], pt[1], pt[2]
        radial_mod = pt[3] if len(pt) > 3 else None
        # Round 26: Collar bulge at branch base (first 1-2 rings)
        if collar_bulge > 0 and i < COLLAR_BULGE_RINGS:
            r = r * (1.0 + collar_bulge * math.exp(-i))
        ring = cap_disk(bm, pos, tangent, r, radial_segs, radial_mod=radial_mod)
        t_val = i / max(n_pts - 1, 1)
        for v in ring:
            v[tier_layer] = tier
            v[t_layer] = t_val
        rings.append(ring)
    start_face = len(bm.faces)
    for i in range(len(rings) - 1):
        bridge_rings(bm, rings[i], rings[i + 1])
    end_face = len(bm.faces)
    face_index_track.setdefault(mat_index, []).append((start_face, end_face))
    return rings


def make_cluster_card(bm, center, normal, width, height, mat_index, face_index_track,
                      uv_cell=(0, 0), atlas_grid=2, color_layer=None,
                      vcolor=(1.0, 1.0, 1.0, 1.0), roll=0.0, cross_quad=True, rng=None):
    """Cluster alpha card (industry standard: SpeedTree/RDR2/Witcher 3 pattern).

    Cross-quad (X-pattern): 2 perpendicular quads = 4 tri per cluster.
    UV maps to one cell in atlas (atlas_grid × atlas_grid layout).
    Texture cell shows 5-7 organic leaf silhouettes with alpha cutout.
    Card boundary is invisible because alpha at edges fades out.

    `uv_cell`: (col, row) in atlas grid, e.g. (0,0), (0,1), (1,0), (1,1) for 2×2
    """
    n = normal.normalized()
    helper = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    u_base = (helper - helper.dot(n) * n).normalized()
    v_base = n.cross(u_base).normalized()
    cr, sr = math.cos(roll), math.sin(roll)
    u1 = u_base * cr + v_base * sr
    v1 = -u_base * sr + v_base * cr

    # Compute atlas UV range for this cell
    cell_size = 1.0 / atlas_grid
    pad = cell_size * 0.02   # 2% gutter padding to avoid bleed
    cx, cy = uv_cell
    uv_u_min = cx * cell_size + pad
    uv_u_max = (cx + 1) * cell_size - pad
    uv_v_min = cy * cell_size + pad
    uv_v_max = (cy + 1) * cell_size - pad

    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.new()

    def quad(uvec, vvec):
        hw, hh = width * 0.5, height * 0.5
        verts = [
            bm.verts.new(center + (-uvec * hw) + (-vvec * hh)),
            bm.verts.new(center + (uvec * hw) + (-vvec * hh)),
            bm.verts.new(center + (uvec * hw) + (vvec * hh)),
            bm.verts.new(center + (-uvec * hw) + (vvec * hh)),
        ]
        quad_uvs = [
            (uv_u_min, uv_v_min),
            (uv_u_max, uv_v_min),
            (uv_u_max, uv_v_max),
            (uv_u_min, uv_v_max),
        ]
        start = len(bm.faces)
        try:
            f = bm.faces.new(verts)
            for li, loop in enumerate(f.loops):
                loop[uv_layer].uv = quad_uvs[li]
                if color_layer is not None:
                    loop[color_layer] = vcolor
        except ValueError:
            pass
        end = len(bm.faces)
        face_index_track.setdefault(mat_index, []).append((start, end))

    quad(u1, v1)
    if cross_quad:
        quad(v1, n)


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
    """Biologically-shaped Malus domestica apple (Round 24 pomologist panel).

    Gala-type cultivar profile:
      - Oblate-globular body (h/d = 0.88-0.92)
      - Stem cavity (top concave dimple, depth ~7% diameter)
      - Calyx basin (bottom wider deeper dimple, depth ~10%)
      - Asymmetry (±3-5% radial jitter, 2-4° axis tilt)
      - Dual-axis vcolor gradient: sun→shade (horizontal) + ends darken (vertical)
      - Stem: 4-side × 3-ring cylinder, brown→green vcolor

    Per-vertex color "apple" attribute stamped at build time.
    """
    color_layer = bm.loops.layers.color.get("apple") or bm.loops.layers.color.new("apple")

    # Body dimensions
    diameter = APPLE_DIAMETER * rng.uniform(0.92, 1.08)
    r = diameter * 0.5
    h_d_ratio = rng.uniform(0.88, 0.92)
    r_z = r * h_d_ratio
    rings = APPLE_UV_RINGS
    segs = APPLE_UV_SEGS

    # Hang point: apple body below branch attach
    apple_center = center - Vector((0, 0, r_z * 1.05))

    # Random "sun direction" per apple (which side gets more red). Use horizontal direction.
    sun_az = rng.uniform(0, 2 * math.pi)
    sun_dir = Vector((math.cos(sun_az), math.sin(sun_az), 0))
    stripe_seed = rng.random() * 6.28

    # Slight axis tilt for asymmetry
    axis_tilt_rad = math.radians(rng.uniform(2, 4))
    tilt_dir = rng.uniform(0, 2 * math.pi)
    tilt_axis = Vector((math.cos(tilt_dir), math.sin(tilt_dir), 0))

    def _apple_vcolor(local_pos):
        """Dual-axis gradient: sun↔shade horizontal + end-darken vertical + stripes."""
        # Vertical position normalized -1..1 (top=+1, bot=-1)
        v_norm = local_pos.z / max(r_z, 1e-5)
        # Horizontal dot with sun dir → -1..1
        h_norm = (local_pos.xy.normalized().dot(sun_dir.xy)
                  if local_pos.xy.length > 1e-5 else 0.0)
        # Base: lerp sun↔shade
        sun_t = max(0, min(1, (h_norm + 1) * 0.5))      # 0 shade .. 1 sun
        base = [COLOR_APPLE_SHADE[i] * (1 - sun_t) + COLOR_APPLE_SUN[i] * sun_t
                for i in range(3)]
        # Stripe streaks: vertical streaks bias toward stripe color on sun side
        stripe_w = 0.5 + 0.5 * math.sin(math.atan2(local_pos.y, local_pos.x) * 8 + stripe_seed)
        if sun_t > 0.55 and stripe_w > 0.65:
            stripe_blend = (stripe_w - 0.65) * 2.5
            base = [base[i] * (1 - stripe_blend) + COLOR_APPLE_STRIPE[i] * stripe_blend
                    for i in range(3)]
        # End-darken: darker near calyx (z<0) & stem cavity (z>0.7)
        end_t = max(0, abs(v_norm) - 0.65) / 0.35
        if end_t > 0:
            base = [base[i] * (1 - end_t * 0.7) + COLOR_APPLE_ENDS[i] * (end_t * 0.7)
                    for i in range(3)]
        return (base[0], base[1], base[2], 1.0)

    # Build rings — phi 0=top..pi=bot
    ring_verts = []
    ring_locals = []   # local positions for vcolor
    for i in range(1, rings):
        phi = math.pi * i / rings
        z = math.cos(phi) * r_z
        rad_horiz = math.sin(phi) * r
        # Stem cavity (top): pinch ring 1 inward + slight z-pull-down (concave)
        if i == 1:
            rad_horiz *= 0.55
            z -= r_z * 0.08   # 8% depth concave
        # Calyx basin (bottom): wider pinch + deeper z-pull-up
        elif i == rings - 1:
            rad_horiz *= 0.48
            z += r_z * 0.10   # 10% depth concave
        # Equator emphasis (oblate bulge)
        elif i == rings // 2:
            rad_horiz *= 1.04
        verts = []
        locals_row = []
        for j in range(segs):
            ang = 2 * math.pi * j / segs
            # Radial asymmetry jitter
            asym = 1.0 + 0.04 * math.sin(ang * 2 + stripe_seed)
            jitter = rng.uniform(-0.03, 0.03) * rad_horiz
            x = math.cos(ang) * (rad_horiz * asym + jitter)
            y = math.sin(ang) * (rad_horiz * asym + jitter)
            local = Vector((x, y, z))
            # Apply axis tilt
            local = Quaternion(tilt_axis, axis_tilt_rad) @ local
            verts.append(bm.verts.new(apple_center + local))
            locals_row.append(local)
        ring_verts.append(verts)
        ring_locals.append(locals_row)

    # Top pole (stem cavity bottom — deepest point of dimple)
    top_local = Vector((0, 0, r_z * 0.78))    # 22% deeper than ring 1
    top_pole = bm.verts.new(apple_center + Quaternion(tilt_axis, axis_tilt_rad) @ top_local)
    # Bottom pole (calyx basin center — deepest)
    bot_local = Vector((0, 0, -r_z * 0.75))
    bot_pole = bm.verts.new(apple_center + Quaternion(tilt_axis, axis_tilt_rad) @ bot_local)

    start = len(bm.faces)
    # Cap top (stem cavity)
    for j in range(segs):
        jn = (j + 1) % segs
        try:
            bm.faces.new((top_pole, ring_verts[0][jn], ring_verts[0][j]))
        except ValueError:
            pass
    # Bridge body rings
    for i in range(len(ring_verts) - 1):
        bridge_rings(bm, ring_verts[i], ring_verts[i + 1])
    # Cap bottom (calyx basin)
    for j in range(segs):
        jn = (j + 1) % segs
        try:
            bm.faces.new((bot_pole, ring_verts[-1][j], ring_verts[-1][jn]))
        except ValueError:
            pass
    end = len(bm.faces)
    face_index_track.setdefault(mat_apple_idx, []).append((start, end))

    # Apply vcolor per loop on all newly created faces
    bm.faces.ensure_lookup_table()
    for fi in range(start, end):
        f = bm.faces[fi]
        for loop in f.loops:
            local_pos = loop.vert.co - apple_center
            # Un-tilt for color lookup (color in untilted local frame)
            local_pos = Quaternion(tilt_axis, -axis_tilt_rad) @ local_pos
            loop[color_layer] = _apple_vcolor(local_pos)

    # ----- STEM: brown→green corky stem (Pomologist panel: 4 sides × 3 rings) -----
    stem_top = center  # branch attachment
    stem_bot = apple_center + Quaternion(tilt_axis, axis_tilt_rad) @ Vector((0, 0, r_z * 0.95))
    stem_dir = (stem_top - stem_bot)
    stem_len = max(stem_dir.length, APPLE_STEM_LEN * 0.5)
    stem_dir = stem_dir.normalized() if stem_dir.length > 1e-5 else Vector((0, 0, 1))

    stem_pts = []
    n_seg = APPLE_STEM_SEGMENTS + 1
    for i in range(n_seg):
        t = i / (n_seg - 1)
        pos = stem_bot + stem_dir * (stem_len * t)
        r_stem = APPLE_STEM_R * (1.0 - 0.25 * t)
        stem_pts.append((pos, r_stem, stem_dir, t))
    stem_start = len(bm.faces)
    stem_rings = []
    stem_ts = []
    for pos, rr, td, t_val in stem_pts:
        ring = cap_disk(bm, pos, td, rr, APPLE_STEM_RADIAL_SEGS)
        stem_rings.append(ring)
        stem_ts.append(t_val)
    for i in range(len(stem_rings) - 1):
        bridge_rings(bm, stem_rings[i], stem_rings[i + 1])
    stem_end = len(bm.faces)
    face_index_track.setdefault(mat_stem_idx, []).append((stem_start, stem_end))

    # Stem vcolor: t=0 base (greenish) → t=1 tip near branch (corky brown)
    # Build vert→ring lookup
    vert_to_t = {}
    for ring_idx, ring in enumerate(stem_rings):
        for v in ring:
            vert_to_t[v] = stem_ts[ring_idx]
    bm.faces.ensure_lookup_table()
    for fi in range(stem_start, stem_end):
        f = bm.faces[fi]
        for loop in f.loops:
            t_val = vert_to_t.get(loop.vert, 0.5)
            col = [COLOR_STEM_BASE[i] * (1 - t_val) + COLOR_STEM_TIP[i] * t_val for i in range(3)]
            loop[color_layer] = (col[0], col[1], col[2], 1.0)


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
        self.scaffolds = []     # Round 26: {curve, base_pos, tip_pos, base_r, is_co_leader} for fork puffs + snags
        self.secondaries = []   # Round 26: {curve, depth} for inner-fill foliage
        self.surface_roots = [] # Round 26: {curve, base_pos} for vcolor darken
        self.dead_snags = []    # Round 26: {curve} for vcolor darken
        # Canopy center: where leaves cluster vertically (above scaffold zone)
        self.canopy_center = Vector((0, 0, TOTAL_HEIGHT * 0.55))
        self.canopy_radius = 2.6   # estimated; refined after branch build
        # Leaf placeholder texture path (Round 3 — set later by bake_leaf_texture)
        self.leaf_texture_path = None

    # ----- WOOD -----
    def build_trunk_and_branches(self):
        trunk_pts = trunk_curve(self.rng)
        build_tube(self.bm_wood, trunk_pts, TRUNK_RADIAL_SEGS, 0, self.wood_faces, tier=0)
        # Round 26 AAA — surface roots (köklenme): trunk base'inden 5 buttress root
        trunk_base_r = trunk_pts[0][1] * ROOT_FLARE_FACTOR  # flared radius at z=0
        self._build_surface_roots(trunk_base_r)

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
                                 SCAFFOLD_SEGMENTS, droop, lateral_jitter=0.10, rng=self.rng,
                                 gravity_k=GRAVITY_K_SCAFFOLD)
            build_tube(self.bm_wood, curve, SCAFFOLD_RADIAL_SEGS, 0, self.wood_faces, tier=1,
                       collar_bulge=COLLAR_BULGE_FACTOR)
            # Round 26: store scaffold info for fork puffs + dead snags
            self.scaffolds.append({
                "curve": curve, "base_pos": t_pos, "tip_pos": curve[-1][0],
                "base_r": base_r, "is_co_leader": is_co_leader,
            })
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
                                 SCAFFOLD_SEGMENTS - 1, droop, lateral_jitter=0.06, rng=self.rng,
                                 gravity_k=GRAVITY_K_SCAFFOLD * 0.7)
            build_tube(self.bm_wood, curve, SCAFFOLD_RADIAL_SEGS - 2, 0, self.wood_faces, tier=1,
                       collar_bulge=COLLAR_BULGE_FACTOR * 0.8)
            self._build_secondaries(curve, depth=1, count_override=(2, 4))

        # Round 26 AAA — dead snags: scaffold+secondary üzerinde 2-4 kırık güdük
        self._build_dead_snags()

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
                                 SECONDARY_SEGMENTS, droop, lateral_jitter=0.06, rng=self.rng,
                                 gravity_k=GRAVITY_K_SECONDARY)
            build_tube(self.bm_wood, curve, SECONDARY_RADIAL_SEGS, 0, self.wood_faces, tier=2,
                       collar_bulge=COLLAR_BULGE_FACTOR * 0.85)
            # Round 26: store secondaries for inner-fill foliage
            self.secondaries.append({"curve": curve, "depth": depth})
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
                                 TWIG_SEGMENTS, droop, lateral_jitter=0.03, rng=self.rng,
                                 gravity_k=GRAVITY_K_TWIG)
            build_tube(self.bm_wood, curve, TWIG_RADIAL_SEGS, 0, self.wood_faces, tier=3,
                       collar_bulge=COLLAR_BULGE_FACTOR * 0.6)
            self.twigs.append({
                "curve": curve, "depth": depth, "parent_curve": parent_curve,
                "cards_along": CARDS_PER_TWIG_ALONG,
                "cards_terminal": CARDS_PER_TWIG_TERMINAL,
            })
            # Round 25: Sub-twigs (fraktal dallanma) — twig'in kendi alt-twig'leri
            self._build_subtwigs(curve, depth=depth + 1)
            # occasional spurs on twigs (mostly long shoots have leaves, no spurs)
            if self.rng.random() < SPURS_PER_TWIG_AVG:
                self._sprinkle_spurs_on_branch(curve, count=1)

    def _build_subtwigs(self, parent_twig_curve, depth):
        """Round 25 — yeni dallanma seviyesi: twig'lerin kendi alt-twig'leri.

        Parent twig boyunca SUBTWIG_T_POINTS noktalarinda 1-2 sub-twig olusur.
        Sub-twig'ler de yapraklanir (cards_along/cards_terminal daha az).
        """
        n_sub = self.rng.randint(*SUBTWIGS_PER_TWIG_RANGE)
        if n_sub <= 0:
            return
        # Pick random subset of T points
        t_pool = list(SUBTWIG_T_POINTS)
        self.rng.shuffle(t_pool)
        for i in range(min(n_sub, len(t_pool))):
            frac = t_pool[i] + self.rng.uniform(-0.04, 0.04)
            pos, r_parent, tan = self._sample_branch_curve(parent_twig_curve, frac)
            if r_parent < 0.0035:   # parent too thin already, skip
                continue
            azimuth = self.rng.uniform(0, 2 * math.pi)
            up = Vector((0, 0, 1))
            side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
            forward = tan.cross(side).normalized()
            radial = math.cos(azimuth) * side + math.sin(azimuth) * forward
            ang = math.radians(self.rng.uniform(*SUBTWIG_ANGLE_RANGE_DEG))
            base_dir = (math.cos(ang) * tan + math.sin(ang) * radial).normalized()
            # Parent twig length unknown directly; estimate from curve span
            parent_len = (parent_twig_curve[-1][0] - parent_twig_curve[0][0]).length
            length = parent_len * self.rng.uniform(*SUBTWIG_LENGTH_FACTOR)
            base_r = r_parent * SUBTWIG_R_FACTOR
            tip_r = base_r * 0.35
            droop = 0.02 * FRUIT_LOAD
            curve = branch_curve(pos + radial * (r_parent * 0.4), base_dir, length, base_r, tip_r,
                                 SUBTWIG_SEGMENTS, droop, lateral_jitter=0.02, rng=self.rng,
                                 gravity_k=GRAVITY_K_SUBTWIG)
            build_tube(self.bm_wood, curve, SUBTWIG_RADIAL_SEGS, 0, self.wood_faces, tier=3,
                       collar_bulge=COLLAR_BULGE_FACTOR * 0.4)
            self.twigs.append({
                "curve": curve, "depth": depth, "parent_curve": parent_twig_curve,
                "cards_along": CARDS_PER_SUBTWIG_ALONG,
                "cards_terminal": CARDS_PER_SUBTWIG_TERMINAL,
            })

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
            build_tube(self.bm_wood, curve, SPUR_RADIAL_SEGS, 0, self.wood_faces, tier=3)
            # Spur tip = leaf rosette + (sometimes) apple cluster
            tip = curve[-1]
            self.spurs.append({"pos": tip[0], "tangent": tip[2], "parent_curve": parent_curve,
                               "dir": spur_dir})

    def _stamp_wood_kind(self, face_start, face_end, kind):
        """Round 26: Tag wood faces' verts with a custom 'wood_kind' int layer.

        Used by _apply_bark_vcolor() to apply special darken to surface roots
        (kind=1) and dead snags (kind=2). kind=0 = normal wood.
        """
        bm = self.bm_wood
        wood_kind_layer = (bm.verts.layers.int.get('wood_kind')
                           or bm.verts.layers.int.new('wood_kind'))
        bm.faces.ensure_lookup_table()
        for fi in range(face_start, face_end):
            if fi >= len(bm.faces):
                continue
            for loop in bm.faces[fi].loops:
                loop.vert[wood_kind_layer] = kind

    # ----- ROUND 26: SURFACE ROOTS (köklenme) -----
    def _build_surface_roots(self, trunk_base_r):
        """5 buttress root branches from trunk base, fanning outward into ground.

        Round 26 AAA — visible root protrusions for "rooted" tree feel.
        Each root: tapered cylinder, ROOT_SEGMENTS long, S-curve diving downward.
        Bark vcolor will darken these post-build (DEAD_SNAG_DARKEN style).
        """
        # 5 prime-step azimuths with jitter (avoid symmetric look)
        base_step = 2 * math.pi / N_SURFACE_ROOTS
        jitter_max = math.radians(ROOT_AZIMUTH_JITTER_DEG)
        # Trunk attach point — slightly above ground so root emerges visibly
        trunk_attach_z = 0.05  # 5cm above ground
        for i in range(N_SURFACE_ROOTS):
            azimuth = i * base_step + self.rng.uniform(-jitter_max, jitter_max)
            out_dir = Vector((math.cos(azimuth), math.sin(azimuth), 0))
            pitch = math.radians(self.rng.uniform(*ROOT_PITCH_RANGE_DEG))
            # Direction: mostly outward + downward pitch
            base_dir = (out_dir * math.cos(pitch) + Vector((0, 0, math.sin(pitch)))).normalized()
            length = self.rng.uniform(*ROOT_LENGTH_RANGE)
            base_r = ROOT_BASE_R * self.rng.uniform(0.85, 1.15)
            tip_r = ROOT_TIP_R
            # Attach inside flared trunk base (offset radial slightly into trunk surface)
            attach_pos = Vector((0, 0, trunk_attach_z)) + out_dir * (trunk_base_r * 0.85)
            # Surface root uses negative gravity_k for "dive then level" curve
            curve = branch_curve(attach_pos, base_dir, length, base_r, tip_r,
                                 ROOT_SEGMENTS, droop_m=0.0, lateral_jitter=0.02,
                                 rng=self.rng, gravity_k=ROOT_GRAVITY_K)
            # Clamp z to ground (root cannot float above)
            clamped_curve = []
            for pt in curve:
                pos = pt[0]
                # Last 30% of root sinks into ground
                if pos.z < -0.02:
                    pos = Vector((pos.x, pos.y, -0.02))
                clamped_curve.append((pos, pt[1], pt[2], pt[3] if len(pt) > 3 else None))
            face_start = len(self.bm_wood.faces)
            build_tube(self.bm_wood, clamped_curve, ROOT_RADIAL_SEGS, 0, self.wood_faces,
                       tier=0, collar_bulge=COLLAR_BULGE_FACTOR * 1.3)
            face_end = len(self.bm_wood.faces)
            self._stamp_wood_kind(face_start, face_end, kind=1)   # surface_root
            self.surface_roots.append({"curve": clamped_curve, "base_pos": attach_pos})

    # ----- ROUND 26: DEAD SNAGS (kırık kuru dal güdükleri) -----
    def _build_dead_snags(self):
        """2-4 short broken stubs at random scaffold/secondary fork sites.

        Round 26 AAA — "mature tree history" cue. Dark vcolor, jagged tip (last
        ring has slight radius bumpout suggesting break point).
        """
        n_snags = self.rng.randint(*N_DEAD_SNAGS_RANGE)
        if not self.scaffolds and not self.secondaries:
            return
        # Pick parent curves: prefer scaffolds (more visible), some secondaries
        candidates = []
        for s in self.scaffolds:
            candidates.append(("scaffold", s["curve"]))
        for s in self.secondaries:
            candidates.append(("secondary", s["curve"]))
        if not candidates:
            return
        for _ in range(n_snags):
            kind, parent_curve = self.rng.choice(candidates)
            # Place at upper half of parent (more visible against sky)
            frac = self.rng.uniform(0.30, 0.85)
            pos, r_parent, tan = self._sample_branch_curve(parent_curve, frac)
            if r_parent < 0.012:  # parent too thin
                continue
            # Random direction perpendicular to parent + slight upward
            azimuth = self.rng.uniform(0, 2 * math.pi)
            up = Vector((0, 0, 1))
            side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
            forward = tan.cross(side).normalized()
            radial = math.cos(azimuth) * side + math.sin(azimuth) * forward
            ang = math.radians(self.rng.uniform(40, 75))
            snag_dir = (math.cos(ang) * tan + math.sin(ang) * radial).normalized()
            # Bias upward (snags reach toward sky)
            snag_dir = (snag_dir + Vector((0, 0, 0.15))).normalized()
            length = self.rng.uniform(*DEAD_SNAG_LENGTH_RANGE)
            base_r = DEAD_SNAG_BASE_R
            tip_r = DEAD_SNAG_TIP_R
            attach_pos = pos + radial * (r_parent * 0.5)
            curve = branch_curve(attach_pos, snag_dir, length, base_r, tip_r,
                                 DEAD_SNAG_SEGMENTS, droop_m=0.01, lateral_jitter=0.01,
                                 rng=self.rng, gravity_k=0.0)
            # Jagged tip: last ring radius slightly larger (break point ridge)
            if len(curve) >= 2:
                last_pt = curve[-1]
                jagged_r = last_pt[1] * 1.4   # 40% bigger at break tip
                curve[-1] = (last_pt[0], jagged_r, last_pt[2],
                             last_pt[3] if len(last_pt) > 3 else None)
            face_start = len(self.bm_wood.faces)
            build_tube(self.bm_wood, curve, DEAD_SNAG_RADIAL_SEGS, 0, self.wood_faces, tier=3)
            face_end = len(self.bm_wood.faces)
            self._stamp_wood_kind(face_start, face_end, kind=2)   # dead_snag
            self.dead_snags.append({"curve": curve})

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
        """Round 26 INVERTED: deciduous canopies are DENSE-cored.

        Only skip near the trunk axis itself (within TRUNK_AXIS_HOLLOW_RADIUS).
        Everything else (interior + outer shell) is kept. This matches SpeedTree's
        ~70% volume-fill default for broadleaves like apple.
        """
        dx = pos.x - self.canopy_center.x
        dy = pos.y - self.canopy_center.y
        horiz_dist = math.hypot(dx, dy)
        if horiz_dist < TRUNK_AXIS_HOLLOW_RADIUS:
            return self.rng.random() < TRUNK_AXIS_HOLLOW_SKIP_PROB
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

    def _place_card_at(self, pos, twig_axis, scale_mul=1.0, cell_idx=0,
                       card_w=None, card_h=None, cross_quad=None, skip_check=True):
        """Place one cluster card at given position.

        Round 26: opsiyonel card_w/h ve cross_quad override (multi-shell için).
        twig_axis: tangent of the parent twig (card normal points radially outward + jitter).
        Returns 1 if placed, 0 if skipped (hollow-core).
        """
        if skip_check and self._hollow_core_skip(pos):
            return 0
        # Card normal: radial outward from twig axis + ±20° jitter (SpeedTree sweet spot)
        up = Vector((0, 0, 1))
        radial_seed = self.rng.uniform(0, 2 * math.pi)
        side = twig_axis.cross(up).normalized() if abs(twig_axis.z) < 0.95 else Vector((1, 0, 0))
        fwd = twig_axis.cross(side).normalized()
        radial = (math.cos(radial_seed) * side + math.sin(radial_seed) * fwd).normalized()
        # Heliotropic upward bias (+15-25°)
        tilt_up = math.radians(self.rng.uniform(15, 25))
        radial = (radial * math.cos(tilt_up) + up * math.sin(tilt_up)).normalized()
        # ±20° jitter
        jitter_ax = side if self.rng.random() < 0.5 else fwd
        jit = math.radians(self.rng.uniform(-LEAF_CARD_TILT_JITTER_DEG, LEAF_CARD_TILT_JITTER_DEG))
        n = Quaternion(jitter_ax, jit) @ radial
        roll = math.radians(self.rng.uniform(-LEAF_CARD_ROLL_JITTER_DEG, LEAF_CARD_ROLL_JITTER_DEG))
        scale = self.rng.uniform(*LEAF_CARD_SIZE_JITTER) * scale_mul
        w = (card_w if card_w is not None else LEAF_CARD_W) * scale
        h = (card_h if card_h is not None else LEAF_CARD_H) * scale
        cq = cross_quad if cross_quad is not None else USE_CROSS_QUAD
        uv_cell = (cell_idx % ATLAS_GRID, (cell_idx // ATLAS_GRID) % ATLAS_GRID)
        vcolor = self._leaf_vcolor(pos)
        make_cluster_card(self.bm_leaf, pos, n, w, h, 0, self.leaf_faces,
                          uv_cell=uv_cell, atlas_grid=ATLAS_GRID,
                          color_layer=self.leaf_color_layer,
                          vcolor=vcolor, roll=roll,
                          cross_quad=cq, rng=self.rng)
        return 1

    def _place_along_twig(self, curve, n_cards_along, n_cards_terminal):
        """Place leaf cards ALONG twig curve at parametric t values + terminal bouquet.

        Spec from Botanist panel (Agent 3):
        - Along-twig: 6 cards at t=0.15, 0.30, 0.45, 0.60, 0.75, 0.90
        - Terminal bouquet: 2-3 cards at t=1.0 (juvenile slowdown rosette)
        - Radial offset = petiole length (~2.5cm)
        - Azimuth step = 137.5° (golden angle) around twig axis
        - Tip cards 70% scale (juvenile size)
        """
        placed = 0
        if n_cards_along < 1:
            return 0
        # Along-twig cards at parametric t values
        for i in range(n_cards_along):
            t_frac = LEAF_ALONG_T_START + (LEAF_ALONG_T_END - LEAF_ALONG_T_START) * (i / max(n_cards_along - 1, 1))
            t_frac += self.rng.uniform(-0.03, 0.03)
            pos, r_branch, tan = self._sample_branch_curve(curve, t_frac)
            # Azimuth: golden angle spiral around twig
            azimuth = i * GOLDEN_ANGLE + self.rng.uniform(-0.25, 0.25)
            up = Vector((0, 0, 1))
            side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
            fwd = tan.cross(side).normalized()
            radial = (math.cos(azimuth) * side + math.sin(azimuth) * fwd).normalized()
            # Petiole offset: radial out from twig surface (twig radius + petiole length)
            petiole = LEAF_PETIOLE_LEN + self.rng.uniform(-0.005, 0.005)
            attach_pos = pos + radial * (r_branch + petiole)
            # Cards taper to 70% scale toward tip (juvenile leaves)
            scale_mul = 1.0 - 0.30 * t_frac
            placed += self._place_card_at(attach_pos, tan, scale_mul=scale_mul,
                                          cell_idx=i + int(t_frac * 7))
        # Terminal bouquet at tip (small juvenile cluster, NOT a sphere)
        if n_cards_terminal > 0:
            tip_pos, _, tip_tan = self._sample_branch_curve(curve, 1.0)
            for i in range(n_cards_terminal):
                # Tighter cluster: small angular spread around tip
                ang = i * (2 * math.pi / max(n_cards_terminal, 1)) + self.rng.uniform(0, 0.6)
                offset = Vector((math.cos(ang), math.sin(ang), 0.3)).normalized() * LEAF_TERMINAL_OFFSET
                pos = tip_pos + offset
                placed += self._place_card_at(pos, tip_tan, scale_mul=0.75,
                                              cell_idx=(i + 3))
        return placed

    def _place_spur_rosette(self, spur):
        """Place 2-3 cards as tight rosette at spur tip (real apple spur biology).

        Spurs are compressed-internode shoots where leaves cluster in rosette.
        """
        placed = 0
        base_pos = spur["pos"]
        sdir = spur.get("dir", Vector((0, 0, 1)))
        for i in range(CLUSTERS_PER_SPUR):
            ang = i * (2 * math.pi / max(CLUSTERS_PER_SPUR, 1)) + self.rng.uniform(0, 0.5)
            up = Vector((0, 0, 1))
            side = sdir.cross(up).normalized() if abs(sdir.z) < 0.95 else Vector((1, 0, 0))
            fwd = sdir.cross(side).normalized()
            radial = math.cos(ang) * side + math.sin(ang) * fwd
            pos = base_pos + sdir * (i * 0.005) + radial * LEAF_PETIOLE_LEN
            placed += self._place_card_at(pos, sdir, scale_mul=0.85,
                                          cell_idx=i + 1)
        return placed

    # ----- ROUND 26: Multi-shell foliage placement methods -----

    def _place_inner_fill_along_secondary(self, sec_curve):
        """Inner-fill cards along secondary curve (interior canopy density).

        Smaller cards, single-quad (2 tri), shadow tint. Fills the canopy core
        that the outer-shell along-twig misses.
        """
        placed = 0
        for i in range(INNER_FILL_CARDS_PER_SECONDARY):
            t_frac = 0.30 + (0.85 - 0.30) * (i / max(INNER_FILL_CARDS_PER_SECONDARY - 1, 1))
            t_frac += self.rng.uniform(-0.06, 0.06)
            pos, r_branch, tan = self._sample_branch_curve(sec_curve, t_frac)
            azimuth = i * GOLDEN_ANGLE + self.rng.uniform(-0.3, 0.3)
            up = Vector((0, 0, 1))
            side = tan.cross(up).normalized() if abs(tan.z) < 0.95 else Vector((1, 0, 0))
            fwd = tan.cross(side).normalized()
            radial = (math.cos(azimuth) * side + math.sin(azimuth) * fwd).normalized()
            # Inner fill offset: smaller than petiole (closer to branch surface)
            attach_pos = pos + radial * (r_branch + 0.04)
            cell_idx = (i + int(t_frac * 11)) % (ATLAS_GRID * ATLAS_GRID)
            placed += self._place_card_at(attach_pos, tan, scale_mul=1.0,
                                          cell_idx=cell_idx,
                                          card_w=INNER_FILL_CARD_W,
                                          card_h=INNER_FILL_CARD_H,
                                          cross_quad=INNER_FILL_CROSS_QUAD,
                                          skip_check=False)
        return placed

    def _place_fork_puff(self, scaffold_info):
        """Cluster of cards at scaffold-trunk junction (AAA tree silhouette punctuation).

        Witcher 3 hero-tree trick: dense foliage clump at major branch joints
        smooths the silhouette between trunk and canopy.
        """
        placed = 0
        base = scaffold_info["base_pos"]
        # Scaffold direction (first curve segment)
        curve = scaffold_info["curve"]
        if len(curve) < 2:
            return 0
        scaffold_dir = (curve[1][0] - curve[0][0]).normalized() if (curve[1][0] - curve[0][0]).length > 1e-5 else Vector((0, 0, 1))
        # Puff center: scaffold base + offset radial along scaffold dir
        puff_center = base + scaffold_dir * FORK_PUFF_OFFSET
        for i in range(FORK_PUFF_CARDS):
            # Spherical scatter in puff volume
            theta = self.rng.uniform(0, 2 * math.pi)
            phi = math.acos(self.rng.uniform(-1, 1))
            r = FORK_PUFF_RADIUS * (self.rng.random() ** 0.6)
            offset = Vector((
                r * math.sin(phi) * math.cos(theta),
                r * math.sin(phi) * math.sin(theta),
                r * math.cos(phi) * 0.85,
            ))
            pos = puff_center + offset
            cell_idx = (i + int(theta * 3)) % (ATLAS_GRID * ATLAS_GRID)
            placed += self._place_card_at(pos, scaffold_dir, scale_mul=1.0,
                                          cell_idx=cell_idx,
                                          card_w=FORK_PUFF_CARD_W,
                                          card_h=FORK_PUFF_CARD_H,
                                          cross_quad=FORK_PUFF_CROSS_QUAD,
                                          skip_check=False)
        return placed

    def _place_trunk_mid_puff(self):
        """Round 27 Stage 1 fix #2: Volumetric foliage at fork height to hide trunk middle.

        Front-view test fail: bare trunk visible z=0.8-1.8m. Add a puff cluster
        centered just above fork that masks the visible trunk segment between
        root flare and lower scaffolds.
        """
        # Centered slightly above fork
        mid_center = Vector((0, 0, TRUNK_FORK_HEIGHT + 0.35))
        placed = 0
        n_cards = 40
        radius = 0.50
        for i in range(n_cards):
            theta = self.rng.uniform(0, 2 * math.pi)
            phi = math.acos(self.rng.uniform(-1, 1))
            r = radius * (self.rng.random() ** 0.5)
            offset = Vector((
                r * math.sin(phi) * math.cos(theta),
                r * math.sin(phi) * math.sin(theta),
                r * math.cos(phi) * 0.65,
            ))
            pos = mid_center + offset
            yaw = self.rng.uniform(0, 2 * math.pi)
            pitch = math.radians(self.rng.uniform(-40, 40))
            n = Vector((math.cos(yaw) * math.sin(pitch + math.pi/2),
                        math.sin(yaw) * math.sin(pitch + math.pi/2),
                        math.cos(pitch + math.pi/2)))
            n = n.normalized() if n.length > 1e-5 else Vector((0, 0, 1))
            roll = math.radians(self.rng.uniform(-180, 180))
            scale = self.rng.uniform(0.80, 1.10)
            w = 0.18 * scale
            h = 0.16 * scale
            cell_idx = (i + int(theta * 5)) % (ATLAS_GRID * ATLAS_GRID)
            uv_cell = (cell_idx % ATLAS_GRID, (cell_idx // ATLAS_GRID) % ATLAS_GRID)
            vcolor = self._leaf_vcolor(pos)
            make_cluster_card(self.bm_leaf, pos, n, w, h, 0, self.leaf_faces,
                              uv_cell=uv_cell, atlas_grid=ATLAS_GRID,
                              color_layer=self.leaf_color_layer,
                              vcolor=vcolor, roll=roll,
                              cross_quad=False, rng=self.rng)
            placed += 1
        return placed

    def _place_crown_apex_puff(self):
        """Round 27 Stage 1 fix: Volumetric foliage clump above trunk top.

        Apple tree silhouette test: trunk middle/top vertical column was bare
        from front/back views. Apex puff fills crown center, hides trunk top.
        Cards centered at (0, 0, trunk_top + offset) with spherical scatter.
        """
        # Find trunk top z (use TRUNK_FORK_HEIGHT + canopy height estimate)
        geom_top = TOTAL_HEIGHT * TRUNK_GEOM_TOP_FRAC
        apex_z = geom_top + CROWN_APEX_Z_OFFSET
        apex_center = Vector((0, 0, apex_z))
        placed = 0
        for i in range(CROWN_APEX_CARDS):
            # Spherical scatter biased to outer (full crown coverage)
            theta = self.rng.uniform(0, 2 * math.pi)
            phi = math.acos(self.rng.uniform(-1, 1))
            r = CROWN_APEX_RADIUS * (self.rng.random() ** 0.4)   # outer-biased
            offset = Vector((
                r * math.sin(phi) * math.cos(theta),
                r * math.sin(phi) * math.sin(theta),
                r * math.cos(phi) * 0.75,   # slightly flatten vertically
            ))
            pos = apex_center + offset
            # Random tilt around vertical
            yaw = self.rng.uniform(0, 2 * math.pi)
            pitch = math.radians(self.rng.uniform(-30, 30))
            n = Vector((math.cos(yaw) * math.sin(pitch + math.pi/2),
                        math.sin(yaw) * math.sin(pitch + math.pi/2),
                        math.cos(pitch + math.pi/2)))
            n = n.normalized() if n.length > 1e-5 else Vector((0, 0, 1))
            roll = math.radians(self.rng.uniform(-180, 180))
            scale = self.rng.uniform(0.85, 1.15)
            w = CROWN_APEX_CARD_W * scale
            h = CROWN_APEX_CARD_H * scale
            cell_idx = (i + int(theta * 4)) % (ATLAS_GRID * ATLAS_GRID)
            uv_cell = (cell_idx % ATLAS_GRID, (cell_idx // ATLAS_GRID) % ATLAS_GRID)
            vcolor = self._leaf_vcolor(pos)
            make_cluster_card(self.bm_leaf, pos, n, w, h, 0, self.leaf_faces,
                              uv_cell=uv_cell, atlas_grid=ATLAS_GRID,
                              color_layer=self.leaf_color_layer,
                              vcolor=vcolor, roll=roll,
                              cross_quad=False, rng=self.rng)   # single quad fill
            placed += 1
        return placed

    def _place_ground_litter(self):
        """Scattered horizontal leaf cards near root flare base (mature tree ground hint).

        Small flat-tilted cards on/near ground around trunk. Single-quad (2 tri).
        Slight brown-green tint (decaying leaves).
        """
        placed = 0
        for i in range(GROUND_LITTER_CARDS):
            ang = self.rng.uniform(0, 2 * math.pi)
            # Bias away from trunk axis (outer ring of root flare)
            r = self.rng.uniform(0.35, GROUND_LITTER_RADIUS)
            pos = Vector((
                r * math.cos(ang),
                r * math.sin(ang),
                self.rng.uniform(0.01, GROUND_LITTER_HEIGHT),
            ))
            # Tilted flat (normal mostly +Z with slight jitter)
            tilt_ax = Vector((math.cos(ang), math.sin(ang), 0))
            jit = math.radians(self.rng.uniform(-25, 25))
            n = Quaternion(tilt_ax, jit) @ Vector((0, 0, 1))
            roll = math.radians(self.rng.uniform(-180, 180))
            scale = self.rng.uniform(0.75, 1.15)
            w = GROUND_LITTER_CARD_W * scale
            h = GROUND_LITTER_CARD_H * scale
            cell_idx = i % (ATLAS_GRID * ATLAS_GRID)
            uv_cell = (cell_idx % ATLAS_GRID, (cell_idx // ATLAS_GRID) % ATLAS_GRID)
            # Decay tint: dimmer + slightly brown
            vcolor = (0.55, 0.42, 0.18, 0.85)
            make_cluster_card(self.bm_leaf, pos, n, w, h, 0, self.leaf_faces,
                              uv_cell=uv_cell, atlas_grid=ATLAS_GRID,
                              color_layer=self.leaf_color_layer,
                              vcolor=vcolor, roll=roll,
                              cross_quad=False, rng=self.rng)
            placed += 1
        return placed

    def build_leaves(self):
        """Round 26 AAA Multi-shell foliage:
        1. Outer shell — long shoots + sub-twigs (along-twig + terminal)
        2. Spur rosettes
        3. Inner fill — along secondaries (small, single-quad)
        4. Fork puffs — at scaffold-trunk junctions
        5. Ground litter — near root flare base
        """
        self.canopy_radius = self._compute_canopy_radius()
        outer = 0
        spur_n = 0
        inner = 0
        puff = 0
        litter = 0

        # 1. Outer shell: twigs + sub-twigs along + terminal
        for twig in self.twigs:
            curve = twig["curve"]
            n_along = twig.get("cards_along", CARDS_PER_TWIG_ALONG)
            n_terminal = twig.get("cards_terminal", CARDS_PER_TWIG_TERMINAL)
            outer += self._place_along_twig(curve, n_along, n_terminal)

        # 2. Spur rosettes
        for spur in self.spurs:
            spur_n += self._place_spur_rosette(spur)

        # 3. Inner fill: along secondaries (Round 26 AAA)
        for sec in self.secondaries:
            inner += self._place_inner_fill_along_secondary(sec["curve"])

        # 4. Fork puffs at scaffold-trunk junctions (Round 26 AAA)
        for scaffold in self.scaffolds:
            puff += self._place_fork_puff(scaffold)

        # 5. Crown apex puff (Round 27 Stage 1 fix — trunk top vertical column fill)
        apex = self._place_crown_apex_puff()

        # 5b. Trunk mid puff (Round 27 Stage 1 fix #2 — trunk middle fork zone fill)
        apex += self._place_trunk_mid_puff()

        # 6. Ground litter near root flare base (Round 26 AAA)
        litter += self._place_ground_litter()

        total = outer + spur_n + inner + puff + apex + litter
        print(f"LEAVES Round 27 AAA multi-shell: outer={outer} spur={spur_n} "
              f"inner={inner} puff={puff} apex={apex} litter={litter} "
              f"TOTAL={total} (atlas {ATLAS_GRID}×{ATLAS_GRID})")

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

    # ----- BARK VCOLOR (Round 24 botanist panel) -----
    def _apply_bark_vcolor(self):
        """Stamp per-loop vertex color on wood: 4-tier gradient + crack noise on trunk/scaffold.

        Trunk: dark grey-brown with vertical fissure noise (proc cracks).
        Scaffold: warmer with mild cracks.
        Secondary: smooth warm brown, no cracks.
        Twig: reddish-mahogany current shoot, no cracks.
        Gradient: proximal→distal along each branch's own t∈[0,1].
        """
        bm = self.bm_wood
        tier_layer = bm.verts.layers.int.get('tier')
        t_layer = bm.verts.layers.float.get('branch_t')
        wood_kind_layer = bm.verts.layers.int.get('wood_kind')   # Round 26
        if tier_layer is None or t_layer is None:
            print("WARN: bark vcolor — tier/t layers missing, skipping")
            return
        color_layer = bm.loops.layers.color.new("bark")
        bm.faces.ensure_lookup_table()
        n_crack = 0
        n_root_darken = 0
        n_snag_darken = 0
        for face in bm.faces:
            for loop in face.loops:
                v = loop.vert
                tier = max(0, min(3, v[tier_layer]))
                t_val = max(0.0, min(1.0, v[t_layer]))
                c_prox = COLOR_BARK_TIERS[tier]
                c_dist = COLOR_BARK_TIERS[min(tier + 1, 3)]
                col = [c_prox[i] * (1 - t_val) + c_dist[i] * t_val for i in range(3)]
                # Cracks: only trunk + scaffold (tier 0, 1)
                if tier <= 1:
                    n_val = mu_noise.noise((v.co.x * BARK_CRACK_SCALE_XY,
                                            v.co.y * BARK_CRACK_SCALE_XY,
                                            v.co.z * BARK_CRACK_SCALE_Z))
                    if n_val < BARK_CRACK_THRESHOLD:
                        col = [c * BARK_CRACK_DARKEN for c in col]
                        n_crack += 1
                # Round 26: Surface roots (kind=1) — moss-tint darken near ground
                # Round 26: Dead snags (kind=2) — dry bark darken
                if wood_kind_layer is not None:
                    kind = v[wood_kind_layer]
                    if kind == 1:   # surface root
                        # Darken + hafif yeşilimsi (toprak/yosun hint)
                        moss_t = max(0, 1.0 - (max(v.co.z, 0) / 0.30)) * 0.20
                        col = [c * ROOT_DARKEN for c in col]
                        col[1] = col[1] * (1 - moss_t) + 0.18 * moss_t   # G hafif yeşil
                        n_root_darken += 1
                    elif kind == 2:   # dead snag
                        col = [c * DEAD_SNAG_DARKEN for c in col]
                        n_snag_darken += 1
                loop[color_layer] = (col[0], col[1], col[2], 1.0)
        print(f"BARK: vcolor applied — {n_crack} crack, {n_root_darken} root_dark, "
              f"{n_snag_darken} snag_dark loops")

    # ----- ASSEMBLE OBJECTS -----
    def assemble(self):
        # Apply bark vertex color before to_mesh (Round 24)
        self._apply_bark_vcolor()

        # Create wood object with bark material
        wood_mesh = bpy.data.meshes.new("Wood_Mesh")
        self.bm_wood.normal_update()
        self.bm_wood.to_mesh(wood_mesh)
        self.bm_wood.free()
        wood_mesh.update()
        wood_obj = bpy.data.objects.new("AppleTree_Wood", wood_mesh)
        bpy.context.collection.objects.link(wood_obj)
        bark_mat = make_bark_material("M_Bark", COLOR_BARK)
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
        apple_mat = make_apple_material("M_Apple", COLOR_APPLE)
        stem_mat = make_apple_material("M_AppleStem", COLOR_STEM, vcolor_attr="apple", roughness=0.8)
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
# COLLECTIONS / COLLISION / LODS (Round 28 — Stage 7+8)
# ------------------------------------------------------------------

def setup_collections():
    """Create the locked-pipeline collection structure.

    Returns dict of name → collection. Existing collections are reused.
    """
    scene_coll = bpy.context.scene.collection
    structure = [
        "APPLE_TREE_FINAL",
        "TRUNK_BRANCHES",
        "ROOTS",
        "FOLIAGE_CARDS",
        "APPLES",
        "MATERIALS",
        "LODS",
        "COLLISION",
        "DEBUG_VISUALS",
        "EXPORTS",
        "QA_RENDERS",
    ]
    colls = {}
    for name in structure:
        if name in bpy.data.collections:
            colls[name] = bpy.data.collections[name]
        else:
            c = bpy.data.collections.new(name)
            colls[name] = c
            # Link top-level collection to scene
            if name == "APPLE_TREE_FINAL":
                scene_coll.children.link(c)
            else:
                colls["APPLE_TREE_FINAL"].children.link(c)
    return colls


def move_to_collection(obj, target_coll):
    """Move object from current collection(s) to target collection."""
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    target_coll.objects.link(obj)


def build_collision_proxy(trunk_base_r=0.18, trunk_height=2.5):
    """Simple cylinder collision proxy at trunk base.

    Single 8-side cylinder, only large enough to block player from walking
    through the trunk. Smaller than visual trunk (no need to cover flare).
    """
    radius = trunk_base_r * 0.85   # tighter than visual trunk
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=8,
        radius=radius,
        depth=trunk_height,
        location=(0, 0, trunk_height * 0.5),
    )
    obj = bpy.context.object
    obj.name = "AppleTree_Collision"
    # Apply a minimal flat material (no PBR — collision mesh shouldn't render)
    if "M_Collision" not in bpy.data.materials:
        m = bpy.data.materials.new("M_Collision")
        m.diffuse_color = (1.0, 0.0, 1.0, 0.4)   # magenta debug
    obj.data.materials.append(bpy.data.materials["M_Collision"])
    # Hide from final render (collision is invisible in-game)
    obj.hide_render = True
    obj.display_type = 'WIRE'
    return obj


def build_lod1(wood_obj, leaf_obj, apple_obj, lods_coll):
    """LOD1: medium detail. Decimate wood ~40%, halve leaf cards.

    LOD1 strategy:
      - Wood mesh: decimate modifier ratio 0.6 (40% tri reduction)
      - Leaf mesh: delete every second face (single quad/cross-quad cluster)
      - Apple mesh: keep all (apples small, decimation breaks shape)
    Target: ~50-60% of LOD0 tri.
    """
    suffix = "_LOD1"
    # Duplicate wood + decimate
    wood_l1 = wood_obj.copy()
    wood_l1.data = wood_obj.data.copy()
    wood_l1.name = wood_obj.name + suffix
    bpy.context.collection.objects.link(wood_l1)
    move_to_collection(wood_l1, lods_coll)
    # Decimate via modifier + apply
    mod = wood_l1.modifiers.new("Decim", 'DECIMATE')
    mod.ratio = 0.62
    bpy.context.view_layer.objects.active = wood_l1
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Duplicate leaf mesh + delete every 2nd face (halve density)
    leaf_l1 = leaf_obj.copy()
    leaf_l1.data = leaf_obj.data.copy()
    leaf_l1.name = leaf_obj.name + suffix
    bpy.context.collection.objects.link(leaf_l1)
    move_to_collection(leaf_l1, lods_coll)
    # Each cluster card = 4 faces (cross-quad) or 2 faces (single-quad). To halve,
    # delete every other 4-face cluster from cross-quads, every other pair from single.
    # Simple approach: delete every 2nd face starting from index 1 (rough halving)
    bm = bmesh.new()
    bm.from_mesh(leaf_l1.data)
    bm.faces.ensure_lookup_table()
    faces_to_remove = [f for i, f in enumerate(bm.faces) if i % 2 == 1]
    bmesh.ops.delete(bm, geom=faces_to_remove, context='FACES')
    # Remove orphan verts
    bm.verts.ensure_lookup_table()
    orphans = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=orphans, context='VERTS')
    bm.to_mesh(leaf_l1.data)
    bm.free()

    # Duplicate apple mesh (keep — only 25 apples)
    apple_l1 = apple_obj.copy()
    apple_l1.data = apple_obj.data.copy()
    apple_l1.name = apple_obj.name + suffix
    bpy.context.collection.objects.link(apple_l1)
    move_to_collection(apple_l1, lods_coll)

    # Hide LOD1 by default in viewport
    for o in (wood_l1, leaf_l1, apple_l1):
        o.hide_set(True)
        o.hide_render = True
    return wood_l1, leaf_l1, apple_l1


def build_lod2(wood_obj, leaf_obj, lods_coll):
    """LOD2: low detail. Wood decimate 0.35, leaf cards reduce ~75%.

    Apple omitted at this LOD (not visible at distance anyway).
    Target: ~25% of LOD0 tri.
    """
    suffix = "_LOD2"
    wood_l2 = wood_obj.copy()
    wood_l2.data = wood_obj.data.copy()
    wood_l2.name = wood_obj.name + suffix
    bpy.context.collection.objects.link(wood_l2)
    move_to_collection(wood_l2, lods_coll)
    mod = wood_l2.modifiers.new("Decim", 'DECIMATE')
    mod.ratio = 0.35
    bpy.context.view_layer.objects.active = wood_l2
    bpy.ops.object.modifier_apply(modifier=mod.name)

    leaf_l2 = leaf_obj.copy()
    leaf_l2.data = leaf_obj.data.copy()
    leaf_l2.name = leaf_obj.name + suffix
    bpy.context.collection.objects.link(leaf_l2)
    move_to_collection(leaf_l2, lods_coll)
    # Aggressive: keep only every 4th face
    bm = bmesh.new()
    bm.from_mesh(leaf_l2.data)
    bm.faces.ensure_lookup_table()
    faces_to_remove = [f for i, f in enumerate(bm.faces) if i % 4 != 0]
    bmesh.ops.delete(bm, geom=faces_to_remove, context='FACES')
    bm.verts.ensure_lookup_table()
    orphans = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=orphans, context='VERTS')
    bm.to_mesh(leaf_l2.data)
    bm.free()

    for o in (wood_l2, leaf_l2):
        o.hide_set(True)
        o.hide_render = True
    return wood_l2, leaf_l2


def build_contact_sheet(image_paths, out_path, cols=3):
    """Composite multiple preview PNGs into a single contact sheet PNG.

    Uses Blender's bpy.data.images pixel ops (no PIL needed).
    Layout: cols × ceil(len/cols) grid.
    """
    if not image_paths:
        print("contact_sheet: no images provided")
        return False
    images = []
    for p in image_paths:
        if not os.path.exists(p):
            print(f"contact_sheet: skip missing {p}")
            continue
        img = bpy.data.images.load(p, check_existing=True)
        images.append((p, img))
    if not images:
        return False
    # All previews same resolution — use first as reference
    src_w, src_h = images[0][1].size
    n = len(images)
    rows = (n + cols - 1) // cols
    out_w = src_w * cols
    out_h = src_h * rows
    out_img = bpy.data.images.new("ContactSheet", width=out_w, height=out_h, alpha=False)
    # Initialize with grey background
    pix = [0.5, 0.5, 0.5, 1.0] * (out_w * out_h)
    out_img.pixels = pix
    # Read each src and blit into correct cell
    # Source pixels are stored row-major bottom-up in Blender's float array
    out_pix = list(out_img.pixels)
    for idx, (path, src) in enumerate(images):
        sw, sh = src.size
        if (sw, sh) != (src_w, src_h):
            # Scale source — bilinear via temp NumPy not available; resort to skip if mismatch
            print(f"contact_sheet: size mismatch {path} {sw}x{sh}, expected {src_w}x{src_h} — skipping")
            continue
        col = idx % cols
        row = idx // cols
        # In Blender pixel arrays origin is bottom-left
        # We want row 0 (first row of grid) at TOP of contact sheet
        out_row_top = (rows - 1 - row)
        src_pix = list(src.pixels)
        # Blit row-by-row
        for y in range(sh):
            src_y = y
            dst_y = out_row_top * sh + y
            for x in range(sw):
                src_idx = (src_y * sw + x) * 4
                dst_x = col * sw + x
                dst_idx = (dst_y * out_w + dst_x) * 4
                out_pix[dst_idx:dst_idx + 4] = src_pix[src_idx:src_idx + 4]
    out_img.pixels = out_pix
    out_img.filepath_raw = out_path
    out_img.file_format = 'PNG'
    out_img.save()
    bpy.data.images.remove(out_img, do_unlink=True)
    print(f"Contact sheet saved: {out_path}")
    return True


def export_fbx(out_path, include_lods=False):
    """Export tree as FBX with materials + vertex colors.

    By default only LOD0 (main tree objects) exported. Use include_lods=True
    to include LOD1/2 meshes as well.
    """
    for o in bpy.context.scene.objects:
        o.select_set(False)
    targets = []
    main_names = ["AppleTree_Wood", "AppleTree_Leaves", "AppleTree_Apples"]
    if include_lods:
        main_names += ["AppleTree_Wood_LOD1", "AppleTree_Leaves_LOD1", "AppleTree_Apples_LOD1",
                       "AppleTree_Wood_LOD2", "AppleTree_Leaves_LOD2"]
    for name in main_names:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            obj.select_set(True)
            obj.hide_set(False)   # FBX export skips hidden objects
            targets.append(obj)
    if not targets:
        print("export_fbx: no objects found")
        return False
    try:
        bpy.ops.export_scene.fbx(
            filepath=out_path,
            use_selection=True,
            apply_unit_scale=True,
            global_scale=1.0,
            axis_forward='-Z',
            axis_up='Y',
            object_types={'MESH'},
            use_mesh_modifiers=True,
            mesh_smooth_type='FACE',
            colors_type='SRGB',
            embed_textures=True,
            path_mode='COPY',
        )
        size_kb = os.path.getsize(out_path) // 1024
        print(f"Exported FBX: {out_path} ({size_kb} KB)")
        # Re-hide LOD objects
        for o in targets:
            if "_LOD" in o.name:
                o.hide_set(True)
        return True
    except Exception as e:
        print(f"export_fbx failed: {e}")
        import traceback
        traceback.print_exc()
        return False


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


def make_bark_material(name, fallback_color, vcolor_attr="bark", roughness=0.88):
    """Bark material that reads per-vertex color attribute (Round 24).

    Vertex color "bark" → Base Color (tier gradient + crack noise from build-time).
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    # Clear default nodes
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    output = nt.nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.2
    # Attribute node reading vertex color "bark"
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_name = vcolor_attr
    attr.location = (-200, 0)
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs[0], output.inputs[0])
    mat.diffuse_color = (*fallback_color, 1.0)
    return mat


def make_apple_material(name, fallback_color, vcolor_attr="apple", roughness=0.42):
    """Apple material — per-vertex color attribute (sun/shade gradient).

    Vertex color "apple" → Base Color with Gala sun-side/shade-side gradient.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    output = nt.nodes.new('ShaderNodeOutputMaterial')
    output.location = (400, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.55
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.55
    attr = nt.nodes.new('ShaderNodeAttribute')
    attr.attribute_name = vcolor_attr
    attr.location = (-200, 0)
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs[0], output.inputs[0])
    mat.diffuse_color = (*fallback_color, 1.0)
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
    mat.use_backface_culling = False  # cross-quad: both sides visible for cluster cards
    mat.alpha_threshold = 0.4
    return mat


def _ovate_silhouette(x, y, cx, cy, half_w, half_h, rot_rad):
    """Inside-test for rotated ovate silhouette centered at (cx, cy).
    Returns (inside_bool, edge_distance_norm 0..1).
    Used to paint leaf silhouettes into atlas pixels directly (Python image build).
    """
    dx = x - cx
    dy = y - cy
    c, s = math.cos(rot_rad), math.sin(rot_rad)
    lx = dx * c + dy * s   # along leaf axis (-half_h..half_h)
    ly = -dx * s + dy * c  # cross axis
    # Ovate width function: narrows toward base and tip
    t = (lx + half_h) / (2 * half_h)
    if t < 0 or t > 1:
        return (False, 0.0)
    # width(t) = sin(pi*t)^0.6 * half_w (broad in middle, taper at ends)
    wt = (math.sin(math.pi * t) ** 0.6) * half_w
    if wt < 1e-6:
        return (False, 0.0)
    norm = abs(ly) / wt
    if norm > 1.0:
        return (False, 0.0)
    return (True, norm)


def _build_cluster_atlas_pixels(res, grid, rng):
    """Build atlas pixels in Python directly — full control over silhouettes & alpha.

    Returns a list of float RGBA pixels (length res*res*4) ready for image.pixels.
    Each of grid×grid cells contains LEAVES_PER_ATLAS_CELL ovate leaf silhouettes
    randomly placed and rotated. Edges fade to alpha=0 (card boundary invisible).
    """
    cell_px = res // grid
    pixels = [0.0] * (res * res * 4)
    # Leaf color palette (HSV-ish jitter per leaf)
    base_color = COLOR_LEAF_VARIANTS[1]  # midtone
    vein_color = tuple(c * 0.55 for c in COLOR_LEAF_VARIANTS[0])

    for gy in range(grid):
        for gx in range(grid):
            # Generate leaf placements for this cell
            cell_x0 = gx * cell_px
            cell_y0 = gy * cell_px
            n_leaves = LEAVES_PER_ATLAS_CELL + rng.randint(-1, 2)
            leaves = []
            for _ in range(n_leaves):
                # Leaf center within cell (in cell-local pixel coords, with margin)
                margin = cell_px * 0.10
                cx = rng.uniform(margin, cell_px - margin)
                cy = rng.uniform(margin, cell_px - margin)
                # Leaf size (random scale)
                size_frac = rng.uniform(0.22, 0.38)
                half_h = cell_px * size_frac * 0.5
                half_w = half_h * rng.uniform(0.55, 0.70)  # ovate ratio
                rot = rng.uniform(0, 2 * math.pi)
                # Per-leaf tint
                hsv_shift = rng.uniform(-0.10, 0.12)
                color = (
                    max(0, min(1, base_color[0] + hsv_shift * 0.3)),
                    max(0, min(1, base_color[1] + hsv_shift * 0.8)),
                    max(0, min(1, base_color[2] + hsv_shift * 0.4)),
                )
                leaves.append((cx, cy, half_w, half_h, rot, color))

            # Rasterize cell pixels
            for py in range(cell_px):
                for px in range(cell_px):
                    # Find topmost (largest) leaf at this pixel
                    best = None
                    for cx, cy, hw, hh, rot, color in leaves:
                        ok, edge_norm = _ovate_silhouette(px, py, cx, cy, hw, hh, rot)
                        if ok:
                            # Larger leaves on top (z-order by hh)
                            if best is None or hh > best[0]:
                                best = (hh, edge_norm, color, cx, cy, hw, hh, rot)
                    if best is None:
                        continue
                    _, edge_norm, color, lcx, lcy, lhw, lhh, lrot = best
                    # Alpha: soft edge falloff (1.0 at center, 0 at edge)
                    alpha = 1.0 - smooth_step(edge_norm ** 1.5)
                    # Vein darkening: midrib axis (rotated)
                    c, s = math.cos(lrot), math.sin(lrot)
                    lx = (px - lcx) * c + (py - lcy) * s
                    ly_local = -(px - lcx) * s + (py - lcy) * c
                    vein_strength = max(0, 1.0 - abs(ly_local) / max(lhw * 0.10, 0.5))
                    # Mix base color with vein color
                    r = color[0] * (1 - vein_strength * 0.6) + vein_color[0] * vein_strength * 0.6
                    g = color[1] * (1 - vein_strength * 0.6) + vein_color[1] * vein_strength * 0.6
                    b = color[2] * (1 - vein_strength * 0.6) + vein_color[2] * vein_strength * 0.6
                    # Write to image pixels (Blender uses bottom-up)
                    img_x = cell_x0 + px
                    img_y = cell_y0 + py
                    idx = (img_y * res + img_x) * 4
                    pixels[idx + 0] = r
                    pixels[idx + 1] = g
                    pixels[idx + 2] = b
                    pixels[idx + 3] = alpha
    return pixels


def bake_leaf_texture(out_path, res=512):
    """Build cluster leaf atlas (2×2 cells, 5-7 ovate silhouettes per cell) directly in Python.

    Produces a 512×512 RGBA PNG with organic leaf cluster silhouettes — card boundary
    invisible due to alpha fadeout. Each cell is a distinct cluster variant (UV cell pick).

    Returns the path to the saved PNG, or None on failure.
    """
    try:
        rng = random.Random(DEFAULT_SEED)
        print(f"Building cluster atlas ({res}×{res}, {ATLAS_GRID}×{ATLAS_GRID} cells)...")
        pixels = _build_cluster_atlas_pixels(res, ATLAS_GRID, rng)
        img = bpy.data.images.new("_LeafAtlas", width=res, height=res, alpha=True)
        img.pixels = pixels
        img.filepath_raw = out_path
        img.file_format = 'PNG'
        img.save()
        bpy.data.images.remove(img, do_unlink=True)
        print(f"Baked cluster atlas → {out_path}")
        return out_path
    except Exception as e:
        print(f"bake_leaf_texture exception: {e}")
        import traceback
        traceback.print_exc()
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
        cam.rotation_euler = Euler((0, 0, 0))   # straight down
        cam_data.lens = 35    # wider FoV for top view
    elif view_name == "back":
        cam.location = (0, 9, 2.2)
        cam.rotation_euler = Euler((math.radians(86), 0, math.radians(180)))
    elif view_name == "silhouette":
        # Strong backlight silhouette test (Stage 1 QA)
        cam.location = (0, -10, 2.0)
        cam.rotation_euler = Euler((math.radians(88), 0, 0))
        cam_data.lens = 50
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
    # Round 26: AAA esnek bütçe (mobile mid-high + PC)
    print(f"VERIFY: target 17000-22000 tris -> {'OK' if 17000 <= total <= 22000 else 'OUT OF RANGE'}")
    print("=" * 50)
    return {"wood": wood_tri, "leaf": leaf_tri, "apple": apple_tri, "total": total, "bbox": bbox}


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

LEAF_TEXTURE_PATH = os.path.join(OUT_DIR, "textures", "leaf", "leaf_placeholder.png")
OUT_GLB = os.path.join(OUT_DIR, "elma_agaci.glb")
OUT_FBX = os.path.join(OUT_DIR, "elma_agaci.fbx")


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
    p.add_argument("--export-fbx", action="store_true",
                   help="Export tree as FBX at OUT_FBX path (Round 28)")
    p.add_argument("--lods", action="store_true",
                   help="Build LOD1 + LOD2 simplified meshes (Round 28 Stage 7)")
    p.add_argument("--collision", action="store_true",
                   help="Build simple cylinder collision proxy at trunk base (Stage 8)")
    return p.parse_args(argv)


def main():
    args = parse_args()
    reset_scene()

    # Round 3: bake procedural leaf texture (placeholder until user supplies real)
    texture_path = None
    if not args.no_bake:
        os.makedirs(os.path.dirname(LEAF_TEXTURE_PATH), exist_ok=True)
        texture_path = bake_leaf_texture(LEAF_TEXTURE_PATH, res=ATLAS_RES)
        # After bake, reset scene clean for tree build
        reset_scene()
    elif os.path.exists(LEAF_TEXTURE_PATH):
        # --no-bake but texture exists on disk — use it
        texture_path = LEAF_TEXTURE_PATH
        print(f"Using existing texture: {LEAF_TEXTURE_PATH}")

    builder = TreeBuilder(seed=args.seed)
    builder.leaf_texture_path = texture_path
    builder.build_trunk_and_branches()
    builder.build_leaves()
    builder.build_apples()
    wood_obj, leaf_obj, apple_obj = builder.assemble()
    stats = verify_tree(wood_obj, leaf_obj, apple_obj)

    # Round 28 Stage 7+8 — collections + LOD + collision
    colls = setup_collections()
    move_to_collection(wood_obj, colls["TRUNK_BRANCHES"])
    move_to_collection(leaf_obj, colls["FOLIAGE_CARDS"])
    move_to_collection(apple_obj, colls["APPLES"])
    lod_meshes = []
    if args.lods:
        l1 = build_lod1(wood_obj, leaf_obj, apple_obj, colls["LODS"])
        l2 = build_lod2(wood_obj, leaf_obj, colls["LODS"])
        lod_meshes = list(l1) + list(l2)
        # LOD stats
        for o in lod_meshes:
            poly = sum(1 for _ in o.data.polygons)
            tri = sum(len(p.vertices) - 2 for p in o.data.polygons)
            print(f"LOD: {o.name} polys={poly} tris={tri}")
    if args.collision:
        collision = build_collision_proxy(
            trunk_base_r=TRUNK_BASE_R, trunk_height=TOTAL_HEIGHT * 0.7,
        )
        move_to_collection(collision, colls["COLLISION"])
        print(f"Collision proxy: {collision.name}")

    setup_world()
    if not args.no_save:
        bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
        print(f"Saved: {OUT_BLEND}")
    if args.export_glb:
        export_glb(OUT_GLB)
    if args.export_fbx:
        export_fbx(OUT_FBX, include_lods=args.lods)
    if args.render:
        # Round 27 — Stage 1 QA contact sheet (front + side + top + 3/4 silhouette test)
        view_order = ["front", "side", "back", "top", "three_quarter", "close"]
        rendered_paths = []
        for view in view_order:
            render_view(view, args.round)
            rendered_paths.append(RENDER_OUT_TMPL.format(round=args.round, view=view))
            print(f"Rendered: {view}")
        # Round 28: contact sheet (3×2 grid)
        contact_out = os.path.join(OUT_DIR, "apple_tree_contact_sheet.png")
        build_contact_sheet(rendered_paths, contact_out, cols=3)


if __name__ == "__main__":
    main()
