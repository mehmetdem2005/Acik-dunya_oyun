"""UV atlas yerlesimi.

Her materyal kendi 0-1 alanini kullanir. Dikdortgenler elle belirlendi:
cakisma yok, kenarlarda mip-bleed'i onleyen padding var.
Texture uretimi (textures.py) ayni dikdortgenleri okur -> desen dogru bolgeye duser.
"""

PAD = 0.004

# ------------------------------------------------------------------
# M_Dragon_Body
# ------------------------------------------------------------------
BODY = {
    # ana govde tupu (boyun -> kuyruk ucu), u = cevre, v = uzunluk
    "tube":        (0.004, 0.004, 0.560, 0.996),
    # ventral plakalar (uzun serit)
    "ventral":     (0.566, 0.004, 0.658, 0.996),
    # on bacaklar
    "leg_fl":      (0.664, 0.504, 0.796, 0.996),
    "leg_fr":      (0.664, 0.004, 0.796, 0.496),
    # arka bacaklar
    "leg_rl":      (0.802, 0.504, 0.934, 0.996),
    "leg_rr":      (0.802, 0.004, 0.934, 0.496),
    # ayaklar + parmaklar (dort ayak, 2x2 hucre)
    "foot_fl":     (0.940, 0.752, 0.996, 0.996),
    "foot_fr":     (0.940, 0.504, 0.996, 0.748),
    "foot_rl":     (0.940, 0.252, 0.996, 0.496),
    "foot_rr":     (0.940, 0.004, 0.996, 0.248),
}

# ------------------------------------------------------------------
# M_Dragon_Head
# ------------------------------------------------------------------
HEAD = {
    "skull":       (0.004, 0.004, 0.620, 0.996),   # dis kafatasi + burun
    "jaw_outer":   (0.626, 0.404, 0.996, 0.996),   # cene dis derisi
    "brow":        (0.626, 0.204, 0.996, 0.396),   # kas kemigi / goz kapagi
    "nostril":     (0.626, 0.004, 0.996, 0.196),
}

# ------------------------------------------------------------------
# M_Dragon_Wings
# ------------------------------------------------------------------
WINGS = {
    "wing_l":      (0.004, 0.504, 0.996, 0.996),
    "wing_r":      (0.004, 0.004, 0.996, 0.496),
}

# ------------------------------------------------------------------
# M_Dragon_Horns_Claws  (her parca kucuk hucreye paketlenir)
# ------------------------------------------------------------------
HORNS = {
    "horn_grid":   (0.004, 0.504, 0.996, 0.996),   # 8x4 hucre
    "spike_grid":  (0.004, 0.254, 0.996, 0.496),   # 16x10 hucre
    "claw_grid":   (0.004, 0.004, 0.996, 0.246),   # 8x4 hucre
}
HORN_CELLS = (8, 4)
SPIKE_CELLS = (16, 10)
CLAW_CELLS = (8, 4)

# ------------------------------------------------------------------
# M_Dragon_Mouth
# ------------------------------------------------------------------
MOUTH = {
    "palate":      (0.004, 0.004, 0.496, 0.996),
    "jaw_inner":   (0.504, 0.504, 0.996, 0.996),
    "tongue":      (0.504, 0.254, 0.996, 0.496),
    "throat":      (0.504, 0.004, 0.996, 0.246),
}

# ------------------------------------------------------------------
# M_Dragon_Teeth (grid paketleme)
# ------------------------------------------------------------------
TEETH = {"grid": (0.004, 0.004, 0.996, 0.996)}
TEETH_CELLS = (10, 8)

# ------------------------------------------------------------------
# M_Dragon_Eyes
# ------------------------------------------------------------------
EYES = {
    "eyeball_l":   (0.004, 0.504, 0.496, 0.996),
    "eyeball_r":   (0.504, 0.504, 0.996, 0.996),
    "cornea_l":    (0.004, 0.004, 0.496, 0.496),
    "cornea_r":    (0.504, 0.004, 0.996, 0.496),
}

# ------------------------------------------------------------------
# M_Dragon_Scars (yara / asinma yamalari)
# ------------------------------------------------------------------
SCARS = {
    "patch_a":     (0.004, 0.504, 0.496, 0.996),
    "patch_b":     (0.504, 0.504, 0.996, 0.996),
    "patch_c":     (0.004, 0.004, 0.496, 0.496),
    "patch_d":     (0.504, 0.004, 0.996, 0.496),
}


def cell(rect, cells, index):
    """Grid paketleme: rect icinde (cols, rows) hucreden index'inci hucreyi ver."""
    cols, rows = cells
    total = cols * rows
    i = index % total
    cx = i % cols
    cy = i // cols
    u0, v0, u1, v1 = rect
    w = (u1 - u0) / cols
    h = (v1 - v0) / rows
    m = min(w, h) * 0.06
    return (u0 + cx * w + m, v0 + cy * h + m,
            u0 + (cx + 1) * w - m, v0 + (cy + 1) * h - m)


def sub(rect, fx0, fy0, fx1, fy1):
    """Dikdortgen icinde oransal alt-dikdortgen."""
    u0, v0, u1, v1 = rect
    return (u0 + (u1 - u0) * fx0, v0 + (v1 - v0) * fy0,
            u0 + (u1 - u0) * fx1, v0 + (v1 - v0) * fy1)
