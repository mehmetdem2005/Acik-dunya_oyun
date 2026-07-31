"""Tum sayisal parametreler tek yerde.

Olcu birimi: METRE. Koordinat sistemi: Y yukari, -Z ileri, +X sag (Godot uyumlu).
Referans gorsel: koyu antrasit pullu, kemik-bej ventral plakali, bordo kanat zarli
agir govdeli bati ejderhasi.
"""

import os

# ------------------------------------------------------------------
# YOLLAR
# ------------------------------------------------------------------
ASSET_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX_DIR = os.path.join(ASSET_DIR, "textures")
OUT_DIR = ASSET_DIR
PREVIEW_DIR = os.path.join(ASSET_DIR, "preview")

SEED = 20260726

# ------------------------------------------------------------------
# MAKRO OLCULER (kullanici sartnamesi)
# ------------------------------------------------------------------
TOTAL_LENGTH = 16.0        # burun ucundan kuyruk ucuna, omurga yayi boyunca
SHOULDER_HEIGHT = 4.5      # omuz (withers) tepesi yer seviyesinden
WINGSPAN = 22.0            # kanatlar tam acikken uctan uca

# ------------------------------------------------------------------
# OMURGA: (isim, yay_uzunlugu_m, pitch_derece)
# Burun ucundan geriye dogru yururuz; +Z geri yon, pitch>0 = geri giderken yukari.
# Toplam = 16.00 m
# ------------------------------------------------------------------
SPINE_SEGMENTS = [
    # --- kafa 1.90 ---
    ("snout",    1.10,   4.0),
    ("skull",    0.80,   6.0),
    # --- boyun 3.40 (yukselen S egrisi, referanstaki dik tasima) ---
    ("neck_04",  0.75, -20.0),
    ("neck_03",  0.90, -44.0),
    ("neck_02",  0.90, -54.0),
    ("neck_01",  0.85, -36.0),
    # --- govde 4.20 ---
    ("chest",    1.40,  -5.0),
    ("spine_02", 1.40,   3.0),
    ("spine_01", 1.40,  -2.0),
    # --- kuyruk 6.50 ---
    ("tail_01",  0.95,  -9.0),
    ("tail_02",  0.90, -13.0),
    ("tail_03",  0.85, -17.0),
    ("tail_04",  0.82, -18.0),
    ("tail_05",  0.78, -14.0),
    ("tail_06",  0.75,  -8.0),
    ("tail_07",  0.73,  -2.0),
    ("tail_08",  0.72,   4.0),
]

# Normalize edilmis yay uzunlugu s = 0 (burun) .. 1 (kuyruk ucu) sinirlari
S_HEAD_END = 1.90 / 16.0     # 0.11875
S_NECK_END = 5.30 / 16.0     # 0.33125
S_TORSO_END = 9.50 / 16.0    # 0.59375

# ------------------------------------------------------------------
# GOVDE KESIT PROFILI
# (s, yari_genislik W, yari_yukseklik H, karin_duzlestirme, kesit_ussu)
# karin_duzlestirme: 1.0 = yuvarlak, <1 = duz karin (ventral plaka bolgesi)
# kesit_ussu: 2.0 = elips, >2 = kutumsu (surungen)
# ------------------------------------------------------------------
BODY_PROFILE = [
    (0.11875, 0.58, 0.55, 0.90, 2.55),   # kafa arkasi (boyun tupunun on ucu)
    (0.14000, 0.44, 0.48, 0.88, 2.45),   # boyun daralmasi (atlas)
    (0.18000, 0.46, 0.53, 0.86, 2.40),
    (0.23000, 0.50, 0.59, 0.84, 2.40),
    (0.28000, 0.57, 0.68, 0.82, 2.45),
    (0.31000, 0.69, 0.81, 0.80, 2.50),
    (0.33125, 0.87, 0.97, 0.78, 2.60),   # withers / gogus girisi
    (0.37000, 1.06, 1.10, 0.76, 2.70),
    (0.40500, 1.14, 1.14, 0.74, 2.75),   # gogus kafesi max
    (0.45000, 1.12, 1.11, 0.74, 2.70),
    (0.50000, 1.06, 1.05, 0.76, 2.60),
    (0.55000, 0.99, 0.98, 0.78, 2.55),
    (0.59375, 0.87, 0.89, 0.82, 2.50),   # pelvis
    (0.63000, 0.65, 0.69, 0.88, 2.45),   # kuyruk taban
    (0.68000, 0.53, 0.55, 0.92, 2.40),
    (0.74000, 0.41, 0.43, 0.94, 2.35),
    (0.80000, 0.31, 0.33, 0.96, 2.30),
    (0.86000, 0.225, 0.235, 0.98, 2.25),
    (0.91000, 0.155, 0.163, 1.00, 2.20),
    (0.95000, 0.095, 0.100, 1.00, 2.15),
    (0.98000, 0.052, 0.056, 1.00, 2.10),
    (1.00000, 0.013, 0.015, 1.00, 2.05),
]

# ------------------------------------------------------------------
# COZUNURLUK (LOD0 hedefi ~190k ucgen)
# ------------------------------------------------------------------
BODY_COLS = 64          # govde tupunun cevresel bolunmesi (cift olmali)
BODY_RINGS = 272        # boyun onundan kuyruk ucuna halka sayisi
HEAD_COLS = 48          # kafa kabugu cevresel bolunmesi (cift olmali)
HEAD_RINGS = 62
JAW_COLS = 40
JAW_RINGS = 42
LEG_COLS = 24
WING_SPAN_SEGS = 46     # kanat aciklik yonu bolunmesi (panel basina)
WING_CHORD_SEGS = 14    # kanat kiris yonu bolunmesi (panel basina)

# ------------------------------------------------------------------
# KAFA (yerel koordinat: -Z burun yonu, kafa tabani orijinde)
# ------------------------------------------------------------------
HEAD_LENGTH = 1.90
HEAD_PROFILE = [
    # (t 0=kafa arkasi .. 1=burun ucu, yari_genislik, kafatasi_yuksekligi,
    #  damak_derinligi, kas_kemigi_cikintisi)
    (0.00, 0.66, 0.62, 0.30, 0.00),
    (0.08, 0.68, 0.64, 0.32, 0.06),   # ense / kafatasi arkasi
    (0.18, 0.65, 0.62, 0.31, 0.11),   # kas kemigi tepe
    (0.28, 0.58, 0.55, 0.28, 0.09),   # goz cukuru
    (0.40, 0.49, 0.46, 0.24, 0.04),   # goz onu daralma
    (0.54, 0.43, 0.40, 0.21, 0.01),   # burun ortasi
    (0.68, 0.39, 0.36, 0.19, 0.02),   # burun kemigi cikintisi
    (0.82, 0.34, 0.31, 0.16, 0.03),
    (0.92, 0.26, 0.24, 0.11, 0.01),
    (1.00, 0.11, 0.12, 0.04, 0.00),   # burun ucu
]
HEAD_PITCH_DEG = -6.0       # kafanin boyuna gore hafif asagi bakisi

JAW_LENGTH = 1.66
JAW_PROFILE = [
    (0.00, 0.44, 0.36),   # (t, yari_genislik, dudak altindaki derinlik) eklem
    (0.12, 0.46, 0.38),
    (0.28, 0.44, 0.36),
    (0.45, 0.40, 0.33),
    (0.62, 0.35, 0.29),
    (0.78, 0.29, 0.25),
    (0.90, 0.22, 0.21),
    (1.00, 0.10, 0.15),   # cene ucu (dolgun cene, damak disaridan gorunmez)
]

# ------------------------------------------------------------------
# BACAKLAR  (govde yerel; L tarafi, R aynalanir)
# zincir: (isim, uzunluk, yon_pitch_deg, yon_yaw_deg, bas_yaricap, son_yaricap)
# ------------------------------------------------------------------
FRONT_LEG = {
    "attach_s": 0.372,          # omuz baglanti noktasi (omurga s)
    "attach_yaw": 74.0,         # kesit acisi (0=tepe, 90=yan)
    "chain": [
        ("Scapula",   0.82, -46.0,  10.0, 0.40, 0.34),
        ("Humerus",   1.00, -74.0,   6.0, 0.34, 0.27),
        ("Radius",    1.08, -86.0,  -3.0, 0.27, 0.19),
        ("Metacarp",  0.54, -78.0,  -1.0, 0.19, 0.16),
    ],
    "foot_len": 0.58,
    "toe_count": 4,
    "toe_len": (0.52, 0.62, 0.60, 0.34),
    "toe_yaw": (-42.0, -14.0, 14.0, 52.0),
    "claw_len": (0.34, 0.40, 0.39, 0.26),
}
REAR_LEG = {
    "attach_s": 0.572,
    "attach_yaw": 72.0,
    "chain": [
        ("Hip",       0.74, -40.0,  12.0, 0.50, 0.44),
        ("Femur",     1.05, -68.0,   7.0, 0.44, 0.32),
        ("Tibia",     1.13, -100.0, -4.0, 0.32, 0.21),
        ("Metatars",  0.63, -72.0,  -2.0, 0.21, 0.17),
    ],
    "foot_len": 0.66,
    "toe_count": 4,
    "toe_len": (0.56, 0.68, 0.64, 0.36),
    "toe_yaw": (-40.0, -13.0, 15.0, 54.0),
    "claw_len": (0.36, 0.43, 0.42, 0.28),
}

# ------------------------------------------------------------------
# KANATLAR (bind pose: yari-acik notr, ~45 derece)
# Kanat iskeleti yerel duzlemde tanimlanir, sonra bind pose'a dondurulur.
# ------------------------------------------------------------------
# Bind pose: kanatlar yari-acik notr. Her segment (elevation, sweep) derece:
#   elevation = yatay duzlemin uzerindeki aci (+ yukari)
#   sweep     = yanal eksenden geriye dogru aci (+ geri)
WING = {
    "attach_s": 0.352,           # kanat koku omurga s (omuz kusagi)
    "attach_yaw": 34.0,          # kesit acisi (tepe-yan arasi)
    "humerus": 2.20,
    "forearm": 2.80,
    "wrist": 0.40,
    "humerus_dir": (36.0, 18.0),
    "forearm_dir": (26.0, 33.0),
    "hand_dir":    (20.0, 41.0),
    # her kanat parmagi: (uzunluk, (elevation, sweep), uc kalinligi)
    "fingers": [
        (5.45, (24.0,  26.0), 0.055),   # parmak 1 (on kenar, en uzun, en dik)
        (5.10, (13.0,  56.0), 0.050),
        (4.35, ( 1.0,  84.0), 0.045),
        (3.35, (-13.0, 107.0), 0.040),  # parmak 4 (arka, govdeye en yakin)
    ],
    "finger_base_r": 0.155,
    "humerus_r": (0.42, 0.26),
    "forearm_r": (0.26, 0.13),
    "membrane_thickness": 0.030,
    "bone_thickness": 0.085,
    "body_anchor_s": 0.560,      # zarin govdeye baglandigi nokta (bogum)
    "scallop_depth": 0.20,       # arka kenar oyuklari
}

# ------------------------------------------------------------------
# BOYNUZLAR / DIKENLER / DISLER / PENCELER
# ------------------------------------------------------------------
# Ana boynuz demeti: (t_kafa, yan_ofset_orani, uzunluk, pitch, yaw, roll, taban_r, egrilik)
HORN_MAIN = [
    (0.14, 0.62, 1.35, 26.0,  16.0, 0.0, 0.115, 0.55),   # ana boynuz (en buyuk)
    (0.18, 0.78, 1.02, 14.0,  30.0, 0.0, 0.088, 0.45),
    (0.11, 0.42, 0.86, 44.0,   8.0, 0.0, 0.072, 0.35),
    (0.22, 0.55, 0.68, 30.0,  22.0, 0.0, 0.058, 0.30),
    (0.26, 0.80, 0.54, 10.0,  44.0, 0.0, 0.048, 0.28),
    (0.08, 0.72, 0.62, 20.0,  38.0, 0.0, 0.052, 0.32),
]
# Yanak / cene / ense kucuk boynuzlari
HORN_CHEEK = [
    (0.34, 0.88, 0.40, -12.0,  58.0, 0.0, 0.040, 0.22),
    (0.42, 0.86, 0.34, -20.0,  64.0, 0.0, 0.034, 0.20),
    (0.50, 0.82, 0.27, -26.0,  70.0, 0.0, 0.028, 0.18),
    (0.28, 0.90, 0.33,  -4.0,  62.0, 0.0, 0.030, 0.20),
]
# Burun uzeri kemiksi cikintilar
HORN_NOSE = [
    (0.64, 0.30, 0.16, 52.0, 10.0, 0.0, 0.030, 0.12),
    (0.72, 0.26, 0.13, 56.0,  8.0, 0.0, 0.026, 0.10),
    (0.80, 0.22, 0.10, 60.0,  6.0, 0.0, 0.021, 0.08),
    (0.57, 0.34, 0.14, 48.0, 14.0, 0.0, 0.027, 0.12),
]

# Sirt dikeni zinciri: s araligi ve boy egrisi
SPINE_CRest = {
    "s_start": 0.128,
    "s_end": 0.972,
    "count": 78,
    # boy carpani kontrol noktalari (s, boy_m)
    "height": [
        (0.128, 0.30), (0.16, 0.40), (0.21, 0.46), (0.27, 0.44),
        (0.31, 0.38), (0.34, 0.30), (0.40, 0.24), (0.47, 0.21),
        (0.55, 0.22), (0.60, 0.26), (0.66, 0.30), (0.72, 0.31),
        (0.78, 0.28), (0.84, 0.23), (0.90, 0.16), (0.95, 0.09),
        (0.972, 0.05),
    ],
    "base_r_factor": 0.42,
}
# Ense yelesi (referanstaki kalkan benzeri buyuk dikenler)
NECK_FRILL = {
    "s_start": 0.125,
    "s_end": 0.215,
    "rows": 7,
    "per_row": 4,           # merkezden yana dogru
    "len_range": (0.52, 0.16),
    "yaw_range": (12.0, 78.0),
}

TEETH = {
    "upper_count": 11,      # tek taraf
    "lower_count": 10,
    "len_range": (0.045, 0.135),
    "base_r_range": (0.016, 0.040),
}

# ------------------------------------------------------------------
# VENTRAL PLAKALAR (cene altindan karin bolgesine)
# ------------------------------------------------------------------
VENTRAL = {
    "s_start": 0.135,
    "s_end": 0.615,
    "count": 64,
    "half_angle": 44.0,     # merkezden yana kaplama acisi (derece)
    "lift": 0.028,          # yuzeyden disari tasma
    "overlap": 1.55,        # plaka boyu / adim
}

# ------------------------------------------------------------------
# GOZLER
# ------------------------------------------------------------------
EYE = {
    "t": 0.305,             # kafa uzerindeki konum
    "side": 0.86,           # yanal oran
    "up": 0.42,
    "radius": 0.115,
    "cornea_bulge": 1.14,
    "iris_ratio": 0.52,
    "pupil_ratio": 0.17,
}

# ------------------------------------------------------------------
# RENK PALETI (linear sRGB 0..1) - referans gorselden okundu
# ------------------------------------------------------------------
PALETTE = {
    # Referans: koyu antrasit / komur. Degerler LINEAR; PNG'ye sRGB olarak yazilir.
    "scale_dark":     (0.018, 0.016, 0.015),   # sirt / omuz - siyaha yakin
    "scale_mid":      (0.046, 0.040, 0.034),   # yan govde komur grisi
    "scale_warm":     (0.072, 0.045, 0.028),   # pas / kizil-kahve gecis
    "scale_light":    (0.112, 0.098, 0.080),   # asinmis pul kenari
    "ventral_base":   (0.215, 0.196, 0.158),   # gogus plakalari kirli bej
    "ventral_shadow": (0.098, 0.088, 0.070),
    "ventral_light":  (0.310, 0.288, 0.238),
    "membrane_in":    (0.062, 0.019, 0.017),   # kanat zari ic bordo
    "membrane_out":   (0.038, 0.024, 0.019),   # kanat zari dis kahve
    "membrane_edge":  (0.028, 0.017, 0.014),
    "vein":           (0.048, 0.017, 0.015),
    "horn_base":      (0.038, 0.031, 0.024),   # boynuz koku koyu keratin
    "horn_tip":       (0.185, 0.158, 0.118),   # boynuz ucu asinmis
    "tooth":          (0.310, 0.292, 0.250),
    "claw":           (0.052, 0.043, 0.033),
    "mouth_flesh":    (0.150, 0.055, 0.050),
    "mouth_deep":     (0.062, 0.020, 0.020),
    "tongue":         (0.165, 0.062, 0.058),
    "eye_sclera":     (0.145, 0.112, 0.062),
    "eye_iris":       (0.310, 0.185, 0.048),   # soluk kehribar
    "eye_pupil":      (0.006, 0.005, 0.004),
    "scar":           (0.148, 0.128, 0.106),
}

# ------------------------------------------------------------------
# MATERYALLER
# ------------------------------------------------------------------
MATERIALS = [
    "M_Dragon_Body",
    "M_Dragon_Head",
    "M_Dragon_Wings",
    "M_Dragon_Horns_Claws",
    "M_Dragon_Eyes",
    "M_Dragon_Mouth",
    "M_Dragon_Teeth",
    "M_Dragon_Scars",
]

TEX_SIZE = 1024                 # kullanici karari: 1K atlas
TEX_SIZE_MOBILE = 1024

# ------------------------------------------------------------------
# LOD BUTCELERI (ucgen)
# ------------------------------------------------------------------
LOD_TARGETS = [
    ("LOD0", None),          # kaynak
    ("LOD1", 110_000),
    ("LOD2", 52_000),
    ("LOD3", 20_000),
    ("LOD4", 7_500),
]
MOBILE_TARGET = 65_000

# ------------------------------------------------------------------
# ANIMASYON KLIPLERI: (isim, sure_saniye, loop_mu)
# ------------------------------------------------------------------
ANIM_CLIPS = [
    ("Idle_Ground",       4.00, True),
    ("Idle_Alert",        3.00, True),
    ("Walk",              1.60, True),
    ("Run",               1.00, True),
    ("Turn_Left_90",      1.40, False),
    ("Turn_Right_90",     1.40, False),
    ("Takeoff",           1.80, False),
    ("Flight_Forward",    1.30, True),
    ("Flight_Glide",      4.00, True),
    ("Flight_Hover",      1.10, True),
    ("Landing",           1.60, False),
    ("Wing_Fold",         1.00, False),
    ("Wing_Unfold",       1.00, False),
    ("Roar",              2.60, False),
    ("Bite_Attack",       1.20, False),
    ("Claw_Attack_Left",  1.10, False),
    ("Claw_Attack_Right", 1.10, False),
    ("Tail_Attack",       1.30, False),
    ("Hit_Reaction",      0.70, False),
    ("Death",             3.20, False),
]
# Root motion varyantlari (in-place klibin uzerine kok ilerlemesi eklenir)
ROOT_MOTION_CLIPS = {
    "Walk":           2.20,    # m/s ileri
    "Run":            6.40,
    "Flight_Forward": 14.0,
    "Takeoff":        5.0,
    "Landing":        4.0,
}

FPS = 30
