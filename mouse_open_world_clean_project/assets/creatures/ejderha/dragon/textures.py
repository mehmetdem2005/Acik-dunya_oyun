"""Prosedurel PBR doku uretimi (numpy) -> lossless PNG.

Her materyal icin uc harita uretilir:
  *_BaseColor.png   sRGB
  *_Normal.png      tangent-space, glTF standardi (+Y yukari)
  *_ORM.png         R=AO, G=Roughness, B=Metallic

Desenler UV atlas dikdortgenlerine gore yerlestirilir (uvmap.py ile ayni
koordinatlar) -> pul yonu anatomik akisa uyar, seam'de kesinti olmaz.
Foto doku projeksiyonu YOK; her sey analitik olarak uretilir.
"""

import math
import os
import struct
import zlib

import numpy as np

from . import config as C
from . import uvmap

SZ = C.TEX_SIZE


# ==================================================================
# PNG YAZICI
# ==================================================================
def write_png(path, arr):
    """arr: (H, W, 3|4) float 0..1 veya uint8."""
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0.0, 1.0)
        arr = (arr * 255.0 + 0.5).astype(np.uint8)
    h, w, ch = arr.shape
    ctype = {1: 0, 3: 2, 4: 6}[ch]
    raw = bytearray()
    stride = w * ch
    flat = arr.reshape(h, stride)
    for y in range(h):
        raw.append(0)
        raw.extend(flat[y].tobytes())

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    out += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(out)
    return path


# ==================================================================
# GURULTU
# ==================================================================
def _rng(seed):
    return np.random.default_rng(seed & 0x7FFFFFFF)


def smooth_noise(h, w, cells, seed):
    """Bilineer upsample edilmis rastgele grid (periyodik)."""
    g = _rng(seed).random((cells + 1, cells + 1)).astype(np.float32)
    g[-1, :] = g[0, :]
    g[:, -1] = g[:, 0]
    ys = np.linspace(0, cells, h, endpoint=False, dtype=np.float32)
    xs = np.linspace(0, cells, w, endpoint=False, dtype=np.float32)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy)
            + c * (1 - fx) * fy + d * fx * fy)


def fbm(h, w, base_cells, octaves, seed, gain=0.52):
    tot = np.zeros((h, w), np.float32)
    amp, norm, cells = 1.0, 0.0, base_cells
    for o in range(octaves):
        tot += amp * smooth_noise(h, w, int(cells), seed + o * 7919)
        norm += amp
        amp *= gain
        cells *= 2
    return tot / norm


def blur(a, passes=1):
    for _ in range(passes):
        p = np.pad(a, 1, mode="edge")
        a = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]
             + 4.0 * a) / 8.0
    return a


def scale_pattern(h, w, nu, nv, seed, round_x=1.06, round_y=1.34, radius=0.52):
    """Ust uste binen pul dizilimi -> (yukseklik, hucre_id_rastgele, kenar)."""
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
    vv = v * nv
    row = np.floor(vv)
    uu = u * nu + 0.5 * (row % 2.0)
    col = np.floor(uu)
    cu = uu - col - 0.5
    cv = vv - row - 0.5
    rr = _rng(seed)
    idx = (col.astype(np.int64) * 8191 + row.astype(np.int64) * 131071) & 0xFFFF
    lut = rr.random(0x10000).astype(np.float32)
    cid = lut[idx]
    rad = radius * (0.84 + 0.32 * cid)
    d = np.sqrt((cu * round_x) ** 2 + (cv * round_y) ** 2) / rad
    height = np.clip(1.0 - d * d, 0.0, 1.0) ** 0.60
    # arka kenar kalkikligi (bindirme dudagi)
    lip = np.clip((cv - 0.16) / 0.30, 0.0, 1.0) * np.clip((0.50 - cv) / 0.06, 0.0, 1.0)
    height = height * 0.86 + lip * height * 0.5
    edge = np.clip(1.0 - np.abs(d - 1.0) / 0.16, 0.0, 1.0)
    return height.astype(np.float32), cid, edge.astype(np.float32)


def height_to_normal(hmap, strength=1.0):
    """Tangent-space normal (glTF: +X sag, +Y yukari, +Z disari)."""
    p = np.pad(hmap, 1, mode="edge")
    dx = (p[1:-1, 2:] - p[1:-1, :-2]) * 0.5
    dy = (p[2:, 1:-1] - p[:-2, 1:-1]) * 0.5
    nx = -dx * strength * 8.0
    ny = -dy * strength * 8.0
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    out = np.stack([nx / ln, ny / ln, nz / ln], axis=-1)
    return out * 0.5 + 0.5


def ao_from_height(hmap, radius=3):
    lo = blur(hmap, radius)
    ao = np.clip(0.60 + (hmap - lo) * 2.6, 0.0, 1.0)
    return (ao * 0.72 + 0.28).astype(np.float32)


def rect_px(rect):
    u0, v0, u1, v1 = rect
    x0 = int(round(u0 * SZ))
    x1 = max(x0 + 2, int(round(u1 * SZ)))
    y0 = int(round(v0 * SZ))
    y1 = max(y0 + 2, int(round(v1 * SZ)))
    return x0, y0, min(x1, SZ), min(y1, SZ)


def mix(a, b, t):
    """Renk/gri karisim; (3,), (H,W) ve (H,W,3) sekillerini otomatik yayinlar."""
    a = np.asarray(a, np.float32)
    b = np.asarray(b, np.float32)
    t = np.clip(np.asarray(t, np.float32), 0.0, 1.0)
    if a.ndim == 1:
        a = a[None, None, :]
    if b.ndim == 1:
        b = b[None, None, :]
    if t.ndim == 2 and (a.ndim == 3 or b.ndim == 3):
        t = t[..., None]
    return a * (1.0 - t) + b * t


def col(name):
    return np.array(C.PALETTE[name], dtype=np.float32)


def to_srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92,
                    1.055 * np.power(np.maximum(lin, 1e-8), 1 / 2.4) - 0.055)


class Canvas:
    """Bir materyalin uc haritasini birlikte tasir."""

    def __init__(self, name):
        self.name = name
        self.base = np.zeros((SZ, SZ, 3), np.float32)
        self.height = np.zeros((SZ, SZ), np.float32)
        self.rough = np.full((SZ, SZ), 0.62, np.float32)
        self.metal = np.zeros((SZ, SZ), np.float32)
        self.ao_extra = np.ones((SZ, SZ), np.float32)
        self.nstrength = np.full((SZ, SZ), 1.0, np.float32)

    def region(self, rect):
        x0, y0, x1, y1 = rect_px(rect)
        return (slice(y0, y1), slice(x0, x1), x1 - x0, y1 - y0)

    def save(self, out_dir):
        ao = ao_from_height(self.height) * self.ao_extra
        nrm = height_to_normal(self.height, 1.0)
        # kenar padding: bos alanlar komsu renkle doldurulur (mip bleed onlemi)
        base = to_srgb(self.base)
        orm = np.stack([np.clip(ao, 0, 1), np.clip(self.rough, 0.03, 1.0),
                        np.clip(self.metal, 0, 1)], axis=-1)
        paths = {}
        paths["base"] = write_png(os.path.join(out_dir, self.name + "_BaseColor.png"), base)
        paths["normal"] = write_png(os.path.join(out_dir, self.name + "_Normal.png"), nrm)
        paths["orm"] = write_png(os.path.join(out_dir, self.name + "_ORM.png"), orm)
        return paths


# ==================================================================
# MATERYAL URETICILERI
# ==================================================================
def _scaled_skin(cv, rect, nu, nv, seed, dark, mid, warm, light,
                 rough_lo=0.52, rough_hi=0.80, amp=1.0, wear=1.0):
    ys, xs, w, h = cv.region(rect)
    hgt, cid, edge = scale_pattern(h, w, nu, nv, seed)
    macro = fbm(h, w, 3, 4, seed + 101)
    grime = fbm(h, w, 7, 4, seed + 211)
    rust = fbm(h, w, 5, 3, seed + 307)

    # her pul kendi tonunda -> kopya desen hissi kirilir
    tone = np.clip(0.32 + cid * 0.72 + (macro - 0.5) * 0.75, 0.0, 1.0)
    c = mix(dark, mid, tone)
    c = mix(c, warm, np.clip((rust - 0.52) * 2.4, 0.0, 1.0) * 0.72)
    # kenar asinmasi (acik keratin)
    c = mix(c, light, edge * (0.16 + 0.24 * cid) * wear)
    # cavity karartma
    cav = 1.0 - np.clip(hgt * 1.25, 0.0, 1.0)
    c = c * (1.0 - 0.42 * cav)[..., None]
    # kir birikimi
    c = c * (1.0 - 0.20 * np.clip(grime - 0.45, 0, 1) * 2.0)[..., None]
    # catlak / kirik pul izleri
    crack = np.clip(1.0 - np.abs(fbm(h, w, 11, 3, seed + 401) - 0.5) / 0.026, 0, 1)
    crack *= (cid > 0.72).astype(np.float32)
    c = c * (1.0 - 0.55 * crack)[..., None]

    cv.base[ys, xs] = c
    cv.height[ys, xs] = (hgt * 0.72 + macro * 0.16 + (1.0 - crack) * 0.04) * amp
    r = rough_lo + (rough_hi - rough_lo) * (0.35 + 0.65 * (1.0 - hgt))
    r = r - 0.10 * edge * wear + 0.06 * np.clip(grime - 0.5, 0, 1) * 2.0
    cv.rough[ys, xs] = np.clip(r, 0.12, 0.96)
    cv.metal[ys, xs] = 0.0
    return hgt, cid, edge


def gen_body(seed=C.SEED):
    cv = Canvas("M_Dragon_Body")
    dark, mid = col("scale_dark"), col("scale_mid")
    warm, light = col("scale_warm"), col("scale_light")

    # --- ana govde tupu: u = cevre (0=sirt, 0.5=karin), v = uzunluk ---
    ys, xs, w, h = cv.region(uvmap.BODY["tube"])
    hgt, cid, edge = scale_pattern(h, w, 46, 118, seed + 3)
    fine, _, fedge = scale_pattern(h, w, 138, 354, seed + 13, radius=0.46)
    macro = fbm(h, w, 3, 5, seed + 101)
    grime = fbm(h, w, 8, 4, seed + 211)
    rust = fbm(h, w, 4, 4, seed + 307)

    uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
    vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
    # sirt (u~0 ve u~1) koyu, karin (u~0.5) acik
    ventral = np.clip(1.0 - np.abs(uu - 0.5) / 0.30, 0.0, 1.0) ** 1.6
    ventral = ventral * np.clip((0.62 - vv) / 0.10, 0.0, 1.0)   # kuyrukta biter
    dorsal = np.clip(1.0 - np.abs(np.minimum(uu, 1.0 - uu)) / 0.18, 0.0, 1.0)

    tone = np.clip(0.30 + cid * 0.66 + (macro - 0.5) * 0.85, 0.0, 1.0)
    c = mix(dark, mid, tone)
    c = mix(c, warm, np.clip((rust - 0.50) * 2.2, 0, 1) * 0.66)
    c = c * (1.0 - 0.30 * dorsal)[..., None]
    c = mix(c, light, edge * (0.14 + 0.22 * cid))
    c = mix(c, col("ventral_base"), ventral * 0.88)
    c = mix(c, col("ventral_light"),
            (ventral * edge * 0.5 + ventral * np.clip(cid - 0.55, 0, 1)))
    cav = 1.0 - np.clip(hgt * 1.2 + fine * 0.25, 0.0, 1.0)
    c = c * (1.0 - 0.40 * cav)[..., None]
    c = c * (1.0 - 0.22 * np.clip(grime - 0.46, 0, 1) * 2.0)[..., None]
    crack = np.clip(1.0 - np.abs(fbm(h, w, 13, 3, seed + 401) - 0.5) / 0.022, 0, 1)
    crack *= (cid > 0.74).astype(np.float32)
    c = c * (1.0 - 0.50 * crack)[..., None]
    # birkac buyuk yara izi (acik, purtuklu)
    scarline = np.clip(1.0 - np.abs(fbm(h, w, 2, 2, seed + 555) - 0.47) / 0.010, 0, 1)
    scarline *= np.clip((vv - 0.22) / 0.10, 0, 1) * np.clip((0.72 - vv) / 0.10, 0, 1)
    c = mix(c, col("scar"), scarline * 0.72)

    cv.base[ys, xs] = c
    cv.height[ys, xs] = (hgt * 0.66 + fine * 0.20 + macro * 0.12
                         - crack * 0.10 + scarline * 0.06)
    r = 0.50 + 0.36 * (1.0 - hgt) + 0.10 * np.clip(grime - 0.5, 0, 1) * 2.0
    r = r - 0.12 * edge + 0.08 * dorsal - 0.16 * ventral
    cv.rough[ys, xs] = np.clip(r, 0.16, 0.94)

    # --- ventral plakalar seridi ---
    ys, xs, w, h = cv.region(uvmap.BODY["ventral"])
    pl = fbm(h, w, 3, 4, seed + 71)
    grow = fbm(h, w, 9, 3, seed + 73)
    uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
    vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
    c = mix(col("ventral_shadow"), col("ventral_base"), 0.30 + 0.70 * pl)
    c = mix(c, col("ventral_light"),
            np.clip((vv * 260.0) % 1.0, 0, 1) ** 6 * 0.55)   # plaka arka kenari
    # yanlarda koyulasma (govdeye gecis)
    side = np.clip(np.abs(uu - 0.5) / 0.5, 0, 1) ** 2.2
    c = c * (1.0 - 0.55 * side)[..., None]
    c = c * (1.0 - 0.28 * np.clip(grow - 0.55, 0, 1) * 2.2)[..., None]
    # asinma cizikleri
    scr = np.clip(1.0 - np.abs(fbm(h, w, 16, 2, seed + 77) - 0.5) / 0.030, 0, 1)
    c = mix(c, col("ventral_shadow"), scr * 0.35)
    cv.base[ys, xs] = c
    cv.height[ys, xs] = pl * 0.30 + grow * 0.20 - scr * 0.10
    cv.rough[ys, xs] = np.clip(0.60 + 0.22 * (1.0 - pl) + 0.10 * scr, 0.2, 0.95)

    # --- bacaklar ---
    for k in ("leg_fl", "leg_fr", "leg_rl", "leg_rr"):
        _scaled_skin(cv, uvmap.BODY[k], 22, 62, seed + 17 + hash(k) % 97,
                     dark, mid, warm, light, 0.50, 0.84)
    # --- ayaklar / parmaklar (daha kucuk pul + kalin taban derisi) ---
    for k in ("foot_fl", "foot_fr", "foot_rl", "foot_rr"):
        ys, xs, w, h = cv.region(uvmap.BODY[k])
        hg, cd, eg = scale_pattern(h, w, 26, 26, seed + 23 + hash(k) % 53,
                                   radius=0.48)
        mac = fbm(h, w, 4, 4, seed + 131)
        vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
        pad = np.clip((0.34 - vv) / 0.14, 0, 1)          # taban yastigi bolgesi
        c = mix(dark, mid, np.clip(0.28 + cd * 0.7 + (mac - 0.5) * 0.8, 0, 1))
        c = mix(c, light, eg * 0.30)
        c = mix(c, col("ventral_shadow") * 0.75, pad * 0.70)
        cv.base[ys, xs] = c * (1.0 - 0.35 * (1.0 - hg))[..., None]
        cv.height[ys, xs] = hg * 0.55 + mac * 0.22 + pad * 0.18
        cv.rough[ys, xs] = np.clip(0.58 + 0.26 * (1 - hg) + 0.14 * pad, 0.2, 0.96)
    return cv


def gen_head(seed=C.SEED):
    cv = Canvas("M_Dragon_Head")
    dark, mid = col("scale_dark"), col("scale_mid")
    warm, light = col("scale_warm"), col("scale_light")

    ys, xs, w, h = cv.region(uvmap.HEAD["skull"])
    hgt, cid, edge = scale_pattern(h, w, 54, 96, seed + 5, radius=0.50)
    fine, _, fedge = scale_pattern(h, w, 160, 300, seed + 15, radius=0.44)
    macro = fbm(h, w, 4, 5, seed + 103)
    grime = fbm(h, w, 9, 4, seed + 213)
    uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
    vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
    # v: 0 = kafa arkasi, 1 = burun ucu ; u: 0 = tepe orta hat
    lat = np.abs(((uu + 0.5) % 1.0) - 0.5) * 2.0
    tone = np.clip(0.26 + cid * 0.66 + (macro - 0.5) * 0.9, 0, 1)
    c = mix(dark, mid, tone)
    c = mix(c, warm, np.clip((macro - 0.58) * 2.6, 0, 1) * 0.55)
    # kemiksi cikintilarda acilma (kas kemigi, burun sirti)
    boss = np.clip(1.0 - np.abs(lat - 0.72) / 0.16, 0, 1) * np.clip((0.55 - vv) / 0.25, 0, 1)
    boss += np.clip(1.0 - lat / 0.20, 0, 1) * np.clip((vv - 0.55) / 0.25, 0, 1)
    c = mix(c, light, np.clip(boss, 0, 1) * 0.28)
    c = mix(c, light, edge * (0.15 + 0.20 * cid))
    cav = 1.0 - np.clip(hgt * 1.2 + fine * 0.28, 0, 1)
    c = c * (1.0 - 0.44 * cav)[..., None]
    c = c * (1.0 - 0.24 * np.clip(grime - 0.44, 0, 1) * 2.0)[..., None]
    # goz cevresi koyulasma
    eye = np.exp(-(((vv - 0.31) / 0.055) ** 2 + ((lat - 0.86) / 0.13) ** 2))
    c = c * (1.0 - 0.45 * eye)[..., None]
    cv.base[ys, xs] = c
    cv.height[ys, xs] = hgt * 0.60 + fine * 0.24 + macro * 0.14 + np.clip(boss, 0, 1) * 0.10
    cv.rough[ys, xs] = np.clip(0.52 + 0.34 * (1 - hgt) - 0.10 * edge
                               + 0.10 * np.clip(boss, 0, 1), 0.18, 0.94)

    # --- cene dis derisi ---
    _scaled_skin(cv, uvmap.HEAD["jaw_outer"], 30, 54, seed + 25,
                 dark, mid, warm, light, 0.50, 0.86)
    # --- kas kemigi / goz kapagi ---
    _scaled_skin(cv, uvmap.HEAD["brow"], 40, 26, seed + 35,
                 dark, mid, warm, light, 0.55, 0.88, wear=1.4)
    # --- burun deligi ic yuzeyi (daha nemli, koyu) ---
    ys, xs, w, h = cv.region(uvmap.HEAD["nostril"])
    n = fbm(h, w, 6, 4, seed + 45)
    cv.base[ys, xs] = mix(col("mouth_deep"), col("scale_dark"), n * 0.7)
    cv.height[ys, xs] = n * 0.35
    cv.rough[ys, xs] = 0.34 + 0.2 * n
    return cv


def gen_wings(seed=C.SEED):
    cv = Canvas("M_Dragon_Wings")
    for key, sd in (("wing_l", 0), ("wing_r", 977)):
        rect = uvmap.WINGS[key]
        # ust yari = zar dis yuzu, alt yari = ic yuz (renkleri farkli)
        for half, inner in ((uvmap.sub(rect, 0.16, 0.52, 1.0, 1.0), False),
                            (uvmap.sub(rect, 0.16, 0.0, 1.0, 0.48), True)):
            ys, xs, w, h = cv.region(half)
            uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
            vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
            if inner:
                vv = 1.0 - vv
            base_c = col("membrane_in") if inner else col("membrane_out")
            mott = fbm(h, w, 5, 5, seed + 61 + sd)
            fine = fbm(h, w, 18, 3, seed + 63 + sd)
            c = mix(base_c, base_c * 1.9, mott)
            c = mix(c, col("membrane_edge"), np.clip((vv - 0.72) / 0.28, 0, 1) ** 1.4 * 0.85)

            # --- damar agi: ana + ikincil ---
            vein_field = np.zeros((h, w), np.float32)
            for k, (fu, fv, wdt, amp) in enumerate(
                    ((3.0, 0.35, 0.030, 1.0), (7.0, 0.55, 0.018, 0.72),
                     (15.0, 0.85, 0.010, 0.46), (31.0, 1.20, 0.006, 0.28))):
                warp = (fbm(h, w, 4, 3, seed + 400 + k * 17 + sd) - 0.5) * 0.10
                pat = np.abs(np.sin((uu * fu + warp + vv * fv) * math.pi))
                vein_field += amp * np.clip(1.0 - pat / wdt, 0, 1) \
                    * np.clip(1.0 - vv * 0.55, 0, 1)
            vein_field = np.clip(vein_field, 0, 1)
            c = mix(c, col("vein"), vein_field * (0.70 if inner else 0.45))

            # --- kirisiklik / gerilim cizgileri ---
            wr = np.abs(np.sin((vv * 26.0 + (fbm(h, w, 6, 3, seed + 71 + sd) - 0.5) * 3.0)
                               * math.pi))
            wrink = np.clip(1.0 - wr / 0.28, 0, 1) * np.clip(1.0 - np.abs(uu - 0.5) * 1.1, 0, 1)
            c = c * (1.0 - 0.16 * wrink)[..., None]

            # --- iyilesmis delik / yirtik izleri ---
            spots = fbm(h, w, 12, 2, seed + 81 + sd)
            heal = np.clip((spots - 0.80) / 0.06, 0, 1)
            c = mix(c, col("membrane_edge") * 1.6, heal * 0.8)

            # --- parmak kemigi seritleri (u ekseninde) ---
            bone = np.zeros((h, w), np.float32)
            for bpos in (0.0, 0.25, 0.50, 0.75, 1.0):
                bone += np.clip(1.0 - np.abs(uu - bpos) / 0.028, 0, 1)
            bone = np.clip(bone, 0, 1) * np.clip(1.0 - vv * 0.35, 0, 1)
            c = mix(c, col("scale_dark") * 1.35, bone * 0.88)

            cv.base[ys, xs] = c
            cv.height[ys, xs] = (vein_field * 0.30 + wrink * 0.18 + bone * 0.55
                                 + fine * 0.10 - heal * 0.20)
            r = 0.58 + 0.22 * mott - 0.10 * vein_field + 0.14 * bone
            cv.rough[ys, xs] = np.clip(r, 0.24, 0.92)
        # kok / kol bolgesi (deri gibi)
        _scaled_skin(cv, uvmap.sub(rect, 0.0, 0.0, 0.15, 1.0), 12, 70,
                     seed + 91 + sd, col("scale_dark"), col("scale_mid"),
                     col("scale_warm"), col("scale_light"), 0.52, 0.86)
    return cv


def gen_horns_claws(seed=C.SEED):
    cv = Canvas("M_Dragon_Horns_Claws")
    for key, cells, rough in (("horn_grid", uvmap.HORN_CELLS, (0.62, 0.90)),
                              ("spike_grid", uvmap.SPIKE_CELLS, (0.58, 0.88)),
                              ("claw_grid", uvmap.CLAW_CELLS, (0.40, 0.74))):
        rect = uvmap.HORNS[key]
        ys, xs, w, h = cv.region(rect)
        cols, rows = cells
        uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
        vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
        # hucre ici lokal v: 0 = kok, 1 = uc
        lv = (vv * rows) % 1.0
        lu = (uu * cols) % 1.0
        cell_id = (np.floor(vv * rows) * cols + np.floor(uu * cols))
        rr = _rng(seed + 900)
        lut = rr.random(cols * rows + 4).astype(np.float32)
        cvar = lut[np.clip(cell_id.astype(np.int32), 0, cols * rows)]

        grain = fbm(h, w, 4, 4, seed + 601)
        rings = np.abs(np.sin((lv * (16.0 + 14.0 * cvar)
                               + (grain - 0.5) * 1.4) * math.pi))
        ridge = np.abs(np.sin((lu * (7.0 + 5.0 * cvar)) * math.pi))
        c = mix(col("horn_base"), col("horn_tip"),
                np.clip(lv ** 1.25 * (0.55 + 0.35 * cvar), 0, 1))
        c = c * (1.0 - 0.09 * rings)[..., None]
        c = c * (1.0 - 0.10 * (1.0 - ridge))[..., None]
        # uc asinmasi: acik, cizik
        wearv = np.clip((lv - 0.72) / 0.28, 0, 1)
        c = mix(c, col("horn_tip") * 1.10, wearv * 0.42)
        chip = np.clip((fbm(h, w, 20, 2, seed + 611) - 0.74) / 0.05, 0, 1) * wearv
        c = mix(c, col("horn_tip") * 1.25, chip * 0.5)
        # kokte deriyle karisma
        c = mix(col("scale_dark"), c, np.clip(lv / 0.16, 0, 1))
        if key == "claw_grid":
            c = mix(col("claw"), c, 0.42)
        cv.base[ys, xs] = c
        cv.height[ys, xs] = (0.35 * (1.0 - rings) + 0.42 * (1.0 - ridge)
                             + 0.16 * grain - chip * 0.30)
        r = rough[0] + (rough[1] - rough[0]) * (0.35 + 0.55 * rings)
        r = r - 0.22 * wearv
        cv.rough[ys, xs] = np.clip(r, 0.14, 0.96)
    return cv


def gen_teeth(seed=C.SEED):
    cv = Canvas("M_Dragon_Teeth")
    rect = uvmap.TEETH["grid"]
    ys, xs, w, h = cv.region(rect)
    cols, rows = uvmap.TEETH_CELLS
    uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
    vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
    lv = (vv * rows) % 1.0
    cell_id = (np.floor(vv * rows) * cols + np.floor(uu * cols))
    lut = _rng(seed + 950).random(cols * rows + 4).astype(np.float32)
    cvar = lut[np.clip(cell_id.astype(np.int32), 0, cols * rows)]
    grain = fbm(h, w, 8, 4, seed + 701)
    stain = fbm(h, w, 5, 3, seed + 703)
    c = mix(col("tooth") * 0.72, col("tooth"), np.clip(lv ** 0.7 + cvar * 0.25, 0, 1))
    # dip kismi diseti/kir lekesi
    c = mix(col("mouth_flesh") * 0.85, c, np.clip(lv / 0.22, 0, 1))
    c = c * (1.0 - 0.30 * np.clip(stain - 0.5, 0, 1) * 2.0 * (1.0 - lv))[..., None]
    # uc asinmasi
    c = mix(c, col("tooth") * 1.15, np.clip((lv - 0.80) / 0.20, 0, 1) * 0.6)
    cv.base[ys, xs] = c
    cv.height[ys, xs] = grain * 0.30 + (1.0 - np.abs(np.sin(uu * 40 * math.pi))) * 0.10
    cv.rough[ys, xs] = np.clip(0.30 + 0.34 * (1.0 - lv) + 0.16 * stain, 0.14, 0.85)
    return cv


def gen_mouth(seed=C.SEED):
    cv = Canvas("M_Dragon_Mouth")
    for key in ("palate", "jaw_inner", "tongue", "throat"):
        rect = uvmap.MOUTH[key]
        ys, xs, w, h = cv.region(rect)
        n1 = fbm(h, w, 5, 4, seed + 801 + hash(key) % 71)
        n2 = fbm(h, w, 14, 3, seed + 811 + hash(key) % 71)
        vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
        uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
        if key == "tongue":
            c = mix(col("tongue") * 0.7, col("tongue"), n1)
            papil = np.clip(1.0 - np.abs(np.sin(uu * 90 * math.pi)
                                         * np.sin(vv * 130 * math.pi)), 0, 1)
            c = c * (1.0 - 0.18 * papil)[..., None]
            cv.height[ys, xs] = n2 * 0.35 + papil * 0.25
            cv.rough[ys, xs] = 0.24 + 0.14 * n1
        elif key == "throat":
            c = mix(col("mouth_deep"), col("mouth_flesh") * 0.8, n1 * 0.6)
            cv.height[ys, xs] = n1 * 0.4
            cv.rough[ys, xs] = 0.30 + 0.16 * n1
        else:
            c = mix(col("mouth_deep"), col("mouth_flesh"), np.clip(n1 * 1.3, 0, 1))
            # damak sirtlari (rugae)
            rug = np.clip(1.0 - np.abs(np.sin(vv * 26 * math.pi)) / 0.30, 0, 1)
            rug = rug * np.clip(1.0 - np.abs(uu - 0.5) * 1.6, 0, 1)
            c = mix(c, col("mouth_flesh") * 1.25, rug * 0.5)
            # diseti (kenarlarda acik)
            gum = np.clip(np.abs(uu - 0.5) * 2.0 - 0.72, 0, 1) / 0.28
            c = mix(c, col("mouth_flesh") * 1.15, np.clip(gum, 0, 1) * 0.7)
            cv.height[ys, xs] = rug * 0.45 + n2 * 0.25
            cv.rough[ys, xs] = 0.26 + 0.18 * n1
        cv.base[ys, xs] = c
    return cv


def gen_eyes(seed=C.SEED):
    cv = Canvas("M_Dragon_Eyes")
    for key in ("eyeball_l", "eyeball_r"):
        rect = uvmap.EYES[key]
        ys, xs, w, h = cv.region(rect)
        uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
        vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
        # kure polar map: iris merkezi (0.5, 0.5) civari degil -> kornea yonu
        cx, cy = 0.50, 0.46
        d = np.sqrt(((uu - cx) * 1.0) ** 2 + ((vv - cy) * 1.0) ** 2)
        iris_r = C.EYE["iris_ratio"] * 0.34
        pup_r = C.EYE["pupil_ratio"] * 0.34
        fib = fbm(h, w, 22, 3, seed + 861)
        sclera = mix(col("eye_sclera") * 0.75, col("eye_sclera"), fib)
        # kilcal damarlar
        vein = np.clip(1.0 - np.abs(fbm(h, w, 26, 2, seed + 871) - 0.5) / 0.020, 0, 1)
        sclera = mix(sclera, np.array([0.32, 0.06, 0.05], np.float32), vein * 0.45)
        iris = mix(col("eye_iris") * 0.55, col("eye_iris"),
                   np.clip(0.3 + fib * 1.2, 0, 1))
        # iris lifleri (radyal)
        ang = np.arctan2(vv - cy, uu - cx)
        rad = np.abs(np.sin(ang * 46.0 + fib * 4.0))
        iris = iris * (1.0 - 0.34 * rad)[..., None]
        c = mix(sclera, iris, np.clip((iris_r - d) / 0.012, 0, 1))
        # dikey yarik pupil (surungen)
        slit = np.clip(1.0 - np.abs(uu - cx) / (pup_r * 0.36), 0, 1) \
            * np.clip(1.0 - np.abs(vv - cy) / (pup_r * 1.7), 0, 1)
        c = mix(c, col("eye_pupil"), np.clip(slit * 3.0, 0, 1))
        # limbus (iris kenari koyu halka)
        limb = np.clip(1.0 - np.abs(d - iris_r) / 0.020, 0, 1)
        c = c * (1.0 - 0.55 * limb)[..., None]
        cv.base[ys, xs] = c
        cv.height[ys, xs] = fib * 0.10
        cv.rough[ys, xs] = np.where(d < iris_r + 0.03, 0.08, 0.28)
        cv.metal[ys, xs] = 0.0
    for key in ("cornea_l", "cornea_r"):
        ys, xs, w, h = cv.region(uvmap.EYES[key])
        cv.base[ys, xs] = np.array([0.02, 0.02, 0.02], np.float32)
        cv.rough[ys, xs] = 0.05
    return cv


def gen_scars(seed=C.SEED):
    cv = Canvas("M_Dragon_Scars")
    for key in ("patch_a", "patch_b", "patch_c", "patch_d"):
        rect = uvmap.SCARS[key]
        ys, xs, w, h = cv.region(rect)
        sd = seed + 1000 + hash(key) % 313
        base = fbm(h, w, 6, 4, sd)
        ridge = fbm(h, w, 14, 3, sd + 11)
        uu = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)[None, :]
        vv = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)[:, None]
        # iyilesmis yara dokusu: purtuklu, pulsuz, acik renk
        c = mix(col("scale_dark"), col("scar"), np.clip(0.30 + base * 0.9, 0, 1))
        gash = np.clip(1.0 - np.abs(np.sin((uu * 2.2 + vv * 3.1
                                            + (base - 0.5) * 1.2) * math.pi)) / 0.30, 0, 1)
        c = mix(c, col("scar") * 1.25, gash * 0.7)
        c = c * (1.0 - 0.22 * ridge)[..., None]
        cv.base[ys, xs] = c
        cv.height[ys, xs] = gash * 0.42 + ridge * 0.22
        cv.rough[ys, xs] = np.clip(0.68 + 0.20 * ridge - 0.14 * gash, 0.3, 0.95)
    return cv


GENERATORS = {
    "M_Dragon_Body": gen_body,
    "M_Dragon_Head": gen_head,
    "M_Dragon_Wings": gen_wings,
    "M_Dragon_Horns_Claws": gen_horns_claws,
    "M_Dragon_Eyes": gen_eyes,
    "M_Dragon_Mouth": gen_mouth,
    "M_Dragon_Teeth": gen_teeth,
    "M_Dragon_Scars": gen_scars,
}


def generate_all(out_dir, seed=C.SEED):
    os.makedirs(out_dir, exist_ok=True)
    result = {}
    for name in C.MATERIALS:
        cv = GENERATORS[name](seed)
        result[name] = cv.save(out_dir)
        print("  texture:", name)
    return result
