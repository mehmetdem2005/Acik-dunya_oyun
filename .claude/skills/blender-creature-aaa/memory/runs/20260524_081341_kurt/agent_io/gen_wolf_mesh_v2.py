#!/usr/bin/env python3
"""P04 v3 — Anatomik kurt govdesi (Canis lupus): derin gogus, tuck-up, withers,
uzun burun+stop, badem goz cukuru, ince uzun bacaklar+pati, boyun yelesi.
Metaball (ball+ellipsoid) sculpt yaklasimi. Kafa/govde elle yerlestirilmis,
bacak/kuyruk iskeletten ornekleme.
blender --background <skeleton.blend> --python gen_wolf_mesh_v2.py -- \
  --blueprint <bp.json> --budget <bud.json> --output-blend <out.blend>
  [--radius-scale 1.5] [--threshold 0.6] [--voxel 0.008]
"""
import bpy, bmesh, json, sys, math, argparse
from pathlib import Path
from mathutils import Vector

def args():
    a=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--blueprint",required=True); p.add_argument("--budget",required=True)
    p.add_argument("--output-blend",required=True)
    p.add_argument("--radius-scale",type=float,default=1.5)
    p.add_argument("--threshold",type=float,default=0.6)
    p.add_argument("--voxel",type=float,default=0.0075)
    p.add_argument("--target-tris",type=int,default=None)
    return p.parse_args(a)
A=args()
bp=json.loads(Path(A.blueprint).read_text()); budget=json.loads(Path(A.budget).read_text())
TARGET=A.target_tris or budget["polygon_budget"]["lod0_tris_target"]
RS=A.radius_scale
bones={b["name"]:b for b in bp["bones"]}
def H(n): return Vector(bones[n]["head_local"])
def T(n): return Vector(bones[n]["tail_local"])

mb=bpy.data.metaballs.new("wolf"); mb.resolution=0.02; mb.render_resolution=0.016; mb.threshold=A.threshold
mbo=bpy.data.objects.new("wolf_meta",mb); bpy.context.collection.objects.link(mbo)

def ball(co,r):
    e=mb.elements.new(type='BALL'); e.co=Vector(co); e.radius=max(r,0.01)*RS; e.stiffness=2.0
def ellip(co,r,sx,sy,sz):
    e=mb.elements.new(type='ELLIPSOID'); e.co=Vector(co); e.radius=max(r,0.01)*RS
    e.size_x=sx; e.size_y=sy; e.size_z=sz; e.stiffness=2.0

# ===== GOVDE (derin gogus, tuck-up, withers) — ellipsoidlerle =====
# (co, r, size_x, size_y, size_z) ellipsoid: x dar, y boyuna, z derinlik
ellip((0, 0.34,0.62), 0.085, 1.05, 1.25, 1.55)   # withers/omuz hörgücü
ellip((0, 0.20,0.575),0.10,  1.15, 1.35, 1.95)   # derin gogus
ellip((0, 0.05,0.575),0.095, 1.15, 1.35, 1.70)   # thorax
ellip((0,-0.13,0.585),0.075, 1.05, 1.30, 1.30)   # tuck-up bel (yukarida, dar)
ellip((0,-0.28,0.585),0.092, 1.10, 1.30, 1.45)   # loin
ellip((0,-0.37,0.585),0.10,  1.15, 1.20, 1.55)   # croup/kalca
# ===== BOYUN + YELE (ruff) =====
ellip((0,0.42,0.585),0.10, 1.25, 1.25, 1.45)     # boyun tabani (kalin, yele)
ball((0,0.47,0.65),0.082)
ball((0,0.53,0.715),0.072)
# ===== KAFA (skull + stop + uzun burun + cene + yanak) =====
ball((0,0.585,0.785),0.072)                       # skull
ball((0,0.55,0.80),0.052)                          # arka kafa/stop
ball(( 0.034,0.605,0.805),0.03); ball((-0.034,0.605,0.805),0.03)  # brow/kas
ball(( 0.045,0.60,0.745),0.035); ball((-0.045,0.60,0.745),0.035)  # yanak
ball((0,0.655,0.765),0.044)                        # burun koku
ball((0,0.715,0.752),0.036)                        # burun orta
ball((0,0.775,0.738),0.029)                        # burun uc
ball((0,0.815,0.725),0.022)                        # nose pad bolge
ball((0,0.71,0.715),0.028)                          # alt cene
ball((0,0.76,0.712),0.022)                          # cene on
# ===== BACAKLAR (ince, uzun) iskeletten ornekleme =====
def seg(name,rh,rt,step=0.028):
    if name not in bones: return
    h,t=H(name),T(name); L=(t-h).length; n=max(1,int(math.ceil(L/step)))
    for k in range(n+1):
        f=k/n; ball(h.lerp(t,f), rh+(rt-rh)*f)
for suf in ("L","R"):
    seg(f"scapula_{suf}",0.058,0.045)
    seg(f"upper_arm_{suf}",0.045,0.036)
    seg(f"forearm_{suf}",0.036,0.026)
    seg(f"front_paw_{suf}",0.028,0.030)
    ball(T(f"front_paw_{suf}"),0.034)              # on pati
    ball(T(f"front_toe_{suf}"),0.030)
    seg(f"pelvis_{suf}",0.075,0.062)
    seg(f"thigh_{suf}",0.07,0.045)                  # but kasli ust
    seg(f"shin_{suf}",0.04,0.03)
    seg(f"metatarsus_{suf}",0.028,0.028)
    ball(T(f"metatarsus_{suf}"),0.032)              # arka pati
    ball(T(f"rear_toe_{suf}"),0.028)
# ===== KUYRUK (taban kalin, fur bushy yapacak) =====
for i in range(12):
    nm=f"tail_{i}"
    if nm in bones:
        seg(nm, max(0.058-0.0032*i,0.02), max(0.058-0.0032*(i+1),0.018))

print(f"[meshv2] {len(mb.elements)} element")
bpy.context.view_layer.objects.active=mbo; bpy.ops.object.select_all(action='DESELECT'); mbo.select_set(True)
bpy.ops.object.convert(target='MESH')
body=bpy.context.view_layer.objects.active; body.name="creature_mesh"
print(f"[meshv2] mesh verts={len(body.data.vertices)}")

# kulaklar (dik, hafif one egik ucgen) skull ustune
sk=Vector((0,0.585,0.785))
def ear(side):
    bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=0.038,radius2=0.003,depth=0.10,
        location=(side*0.050, sk.y-0.005, sk.z+0.085))
    e=bpy.context.view_layer.objects.active
    e.rotation_euler=(math.radians(-10),side*math.radians(13),0)
    bpy.ops.object.transform_apply(rotation=True,scale=True); return e
eL=ear(1); eR=ear(-1)
bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); eL.select_set(True); eR.select_set(True)
bpy.context.view_layer.objects.active=body; bpy.ops.object.join()

# voxel remesh
body.data.remesh_mode='VOXEL'; body.data.remesh_voxel_size=A.voxel
body.data.use_remesh_preserve_volume=True; body.data.use_remesh_fix_poles=True
bpy.ops.object.voxel_remesh()
print(f"[meshv2] remesh verts={len(body.data.vertices)}")

# pati taban duzlestir + yere otur
me=body.data
zmin=min(v.co.z for v in me.vertices); floor=zmin+0.045
for v in me.vertices:
    if v.co.z<floor: v.co.z=floor-0.004
z2=min(v.co.z for v in me.vertices)
for v in me.vertices: v.co.z-=z2

bpy.ops.object.shade_smooth()
def tris():
    bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm,faces=bm.faces); n=len(bm.faces); bm.free(); return n
cur=tris()
if cur>TARGET:
    d=body.modifiers.new("dec",'DECIMATE'); d.ratio=TARGET/cur; bpy.ops.object.modifier_apply(modifier=d.name)
final=tris()
bm=bmesh.new(); bm.from_mesh(me); bm.edges.ensure_lookup_table()
nm=sum(1 for e in bm.edges if not e.is_manifold); bd=sum(1 for e in bm.edges if len(e.link_faces)<2)
bb=[Vector(c) for c in body.bound_box]; bbmin=[min(v[i] for v in bb) for i in range(3)]; bbmax=[max(v[i] for v in bb) for i in range(3)]
bm.free()
print(f"[meshv2] FINAL tris={final} verts={len(me.vertices)} nonmanifold={nm} boundary={bd}")
print(f"[meshv2] bbox={[round(bbmax[i]-bbmin[i],3) for i in range(3)]}")
out=Path(A.output_blend).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
out.with_suffix(".mesh_manifest.json").write_text(json.dumps(
    {"tris":final,"verts":len(me.vertices),"non_manifold":nm,"boundary":bd,
     "bbox":[round(bbmax[i]-bbmin[i],4) for i in range(3)],"method":"metaball_anatomic_v2"},indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print(f"[meshv2] SAVED {out}")
