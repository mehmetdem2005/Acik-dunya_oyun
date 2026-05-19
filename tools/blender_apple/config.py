"""Elma agaci jenerator ayarlari (tek kaynak). Tum tunable burada."""

SEED = 20260519

# Govde
TRUNK_HEIGHT = 1.85          # ilk dallanmaya kadar (kisa, kalin -> olgun elma)
TRUNK_RADIUS = 0.26
TRUNK_TOP_RADIUS = 0.19
TRUNK_LEAN = 0.10            # hafif egim
TRUNK_GNARL = 0.06           # budak/kivrim genligi
TRUNK_SEGMENTS = 9

# Ana iskelet dallari (scaffold) -> acik-merkez genis tac
SCAFFOLD_COUNT = 6
SCAFFOLD_ELEV_DEG = (46.0, 70.0)   # dikeyden sapma (yatay-ust)
SCAFFOLD_LEN = 1.5
MAX_DEPTH = 5                # scaffold -> ikincil -> ucuncul -> surgun
CHILD_PER = (3, 4)          # her dalda alt dal sayisi araligi
LEN_FALLOFF = (0.60, 0.74)
RAD_FALLOFF = 0.60
BRANCH_SEGMENTS = 6
DROOP = 0.24                 # dis/uc dallarda yercekimi sarkmasi (semsiye)
WOBBLE = 0.16                # dal organik gurultu

# Yaprak
LEAF_CLUSTERS_PER_TWIG = 4   # surgun boyunca yaprak kume noktasi
LEAF_CARD = 0.075            # yaprak kart yari-boyu (m)
LEAF_PLANES = 2              # capraz duzlem
LEAF_MIN_DEPTH = 3           # bu derinlik ve uzeri dal/surgunde yaprak

# Elma
APPLE_COUNT = 34
APPLE_RADIUS = 0.052
APPLE_SQUASH = 0.86          # dikey basiklik

# Render sahne
GROUND = True
RES_X = 1100
RES_Y = 1300

# Cikti
BLEND_PATH = "/home/user/Acik-dunya_oyun/tools/blender_apple/apple_tree.blend"
RENDER_PATH = "/tmp/apple_check.png"
GEN_DIR = "/home/user/Acik-dunya_oyun/tools/blender_apple/_gen"
GLB_PATH = "/home/user/Acik-dunya_oyun/mouse_open_world_clean_project/assets/trees/apple_ultra_mobile/apple_tree.glb"
