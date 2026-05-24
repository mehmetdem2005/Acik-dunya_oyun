#!/usr/bin/env python3
"""P04 v2 — Metaball-tabanli organik kurt mesh uretici.
Iskelet eklemlerine metaball yerlestirir (otomatik kaynasir), kafa/burun/bacak/pati/kuyruk/kulak
olusturur, voxel remesh ile temiz kabuk, pati tabani duzlestir, decimate.

Kullanim: blender --background <skeleton.blend> --python gen_wolf_mesh.py -- \
    --blueprint <SkeletonBlueprint.json> --budget <BudgetSpec.json> \
    --output-blend <out.blend> [--radius-scale 1.5] [--threshold 0.5] [--voxel 0.009]
"""
import bpy, bmesh, json, sys, math, argparse
from pathlib import Path
from mathutils import Vector

def args():
    a = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--blueprint", required=True)
    p.add_argument("--budget", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--radius-scale", type=float, default=1.55)
    p.add_argument("--threshold", type=float, default=0.55)
    p.add_argument("--voxel", type=float, default=0.009)
    p.add_argument("--target-tris", type=int, default=None)
    return p.parse_args(a)

A = args()
bp = json.loads(Path(A.blueprint).read_text())
budget = json.loads(Path(A.budget).read_text())
TARGET = A.target_tris or budget["polygon_budget"]["lod0_tris_target"]
RS = A.radius_scale

bones = {b["name"]: b for b in bp["bones"]}
def H(n): return Vector(bones[n]["head_local"])
def T(n): return Vector(bones[n]["tail_local"])

# ---- region radii (gorunur yari-cap, metre). RS ile metaball field'a olceklenir ----
# (segment_bone, r_head, r_tail)
SEGMENTS = [
    ("sacrum",        0.130, 0.140),
    ("spine_lumbar",  0.140, 0.150),
    ("spine_thorax",  0.150, 0.160),   # gogus en genis
    ("spine_chest",   0.160, 0.150),
    ("spine_shoulder",0.150, 0.120),
    ("neck_1",        0.105, 0.090),
    ("neck_2",        0.090, 0.080),
    ("neck_3",        0.080, 0.078),
    ("head",          0.090, 0.045),   # kafa -> sivri burun
]
# tail (gur, yavas incelir)
for i in range(12):
    r0 = 0.065 - 0.0033*i; r1 = 0.065 - 0.0033*(i+1)
    SEGMENTS.append((f"tail_{i}", max(r0,0.02), max(r1,0.018)))
# bacaklar
for suf in ("L","R"):
    SEGMENTS += [
        (f"scapula_{suf}",   0.080, 0.062),
        (f"upper_arm_{suf}", 0.062, 0.050),
        (f"forearm_{suf}",   0.050, 0.038),
        (f"front_paw_{suf}", 0.044, 0.050),  # pati hafif sisman
        (f"front_toe_{suf}", 0.050, 0.040),
        (f"pelvis_{suf}",    0.095, 0.080),
        (f"thigh_{suf}",     0.090, 0.058),  # but kasli
        (f"shin_{suf}",      0.055, 0.040),
        (f"metatarsus_{suf}",0.044, 0.044),
        (f"rear_toe_{suf}",  0.050, 0.040),
    ]

# ---- metaball objesi ----
mb = bpy.data.metaballs.new("wolf_mb")
mb.resolution = 0.022
mb.render_resolution = 0.018
mb.threshold = A.threshold
mbo = bpy.data.objects.new("wolf_meta", mb)
bpy.context.collection.objects.link(mbo)

def add_ball(co, r):
    e = mb.elements.new(type='BALL')
    e.co = co
    e.radius = max(r,0.012) * RS
    e.stiffness = 2.0

STEP = 0.030
for name, rh, rt in SEGMENTS:
    if name not in bones:
        continue
    h, t = H(name), T(name)
    L = (t-h).length
    n = max(1, int(math.ceil(L/STEP)))
    for k in range(n+1):
        f = k/n
        co = h.lerp(t, f)
        r = rh + (rt-rh)*f
        add_ball(co, r)

print(f"[wolf_mesh] {len(mb.elements)} metaball element")

# convert -> mesh
bpy.context.view_layer.objects.active = mbo
bpy.ops.object.select_all(action='DESELECT'); mbo.select_set(True)
bpy.ops.object.convert(target='MESH')
body = bpy.context.view_layer.objects.active
body.name = "creature_mesh"
print(f"[wolf_mesh] metaball->mesh verts={len(body.data.vertices)}")

# ---- kulaklar (dik ucgen flaplar, skull ustune bindir) ----
skull = H("head")  # skull base
def add_ear(side):
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.040, radius2=0.004, depth=0.105,
                                     location=(side*0.052, skull.y-0.01, skull.z+0.085))
    ear = bpy.context.view_layer.objects.active
    ear.rotation_euler = (math.radians(-12), side*math.radians(10), 0)
    # hafif geriye yatik dik kulak
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return ear
ear_L = add_ear(1); ear_R = add_ear(-1)

# join body + ears
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True); ear_L.select_set(True); ear_R.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()

# ---- voxel remesh (kulaklari kaynastir + temiz topoloji) ----
body.data.remesh_mode = 'VOXEL'
body.data.remesh_voxel_size = A.voxel
body.data.use_remesh_preserve_volume = True
body.data.use_remesh_fix_poles = True
bpy.ops.object.voxel_remesh()
print(f"[wolf_mesh] remesh verts={len(body.data.vertices)}")

# ---- pati tabanlarini duzlestir + yere otur ----
me = body.data
zmin = min(v.co.z for v in me.vertices)
floor = zmin + 0.05
for v in me.vertices:
    if v.co.z < floor:
        v.co.z = floor - 0.005   # duz taban
# yere otur
zmin2 = min(v.co.z for v in me.vertices)
for v in me.vertices:
    v.co.z -= zmin2

# ---- shade smooth + decimate ----
bpy.ops.object.shade_smooth()
def tris():
    bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm,faces=bm.faces); n=len(bm.faces); bm.free(); return n
cur = tris()
if cur > TARGET:
    d = body.modifiers.new("dec", 'DECIMATE'); d.ratio = TARGET/cur
    bpy.ops.object.modifier_apply(modifier=d.name)
final = tris()

# ---- validate ----
bm=bmesh.new(); bm.from_mesh(me); bm.edges.ensure_lookup_table()
nm=sum(1 for e in bm.edges if not e.is_manifold); bd=sum(1 for e in bm.edges if len(e.link_faces)<2)
bb=[Vector(c) for c in body.bound_box]
bbmin=[min(v[i] for v in bb) for i in range(3)]; bbmax=[max(v[i] for v in bb) for i in range(3)]
bm.free()
print(f"[wolf_mesh] FINAL tris={final} verts={len(me.vertices)} nonmanifold={nm} boundary={bd}")
print(f"[wolf_mesh] bbox size = {[round(bbmax[i]-bbmin[i],3) for i in range(3)]}")

out = Path(A.output_blend).resolve(); out.parent.mkdir(parents=True, exist_ok=True)
manifest = {"creature_id":"kurt_001","tris":final,"verts":len(me.vertices),
            "non_manifold":nm,"boundary":bd,"bbox_size":[round(bbmax[i]-bbmin[i],4) for i in range(3)],
            "method":"metaball_organic","radius_scale":RS,"threshold":A.threshold,"voxel":A.voxel,
            "generated_by":"P04_mesh_sculptor_v2"}
out.with_suffix(".mesh_manifest.json").write_text(json.dumps(manifest,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print(f"[wolf_mesh] SAVED {out}")
