#!/usr/bin/env python3
"""P04 v3 — kafa + kuyruk + kulak iyilestirilmis anatomik kurt govdesi.
v2'den farklar: daha belirgin kafa (kafatasi/stop/nazal kopru/cene), daha buyuk
dik kulaklar, daha kalin kuyruk tabani.
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
    p.add_argument("--voxel",type=float,default=0.0072)
    p.add_argument("--target-tris",type=int,default=None)
    return p.parse_args(a)
A=args()
bp=json.loads(Path(A.blueprint).read_text()); budget=json.loads(Path(A.budget).read_text())
TARGET=A.target_tris or budget["polygon_budget"]["lod0_tris_target"]
RS=A.radius_scale
bones={b["name"]:b for b in bp["bones"]}
def H(n): return Vector(bones[n]["head_local"])
def T(n): return Vector(bones[n]["tail_local"])
mb=bpy.data.metaballs.new("wolf"); mb.resolution=0.018; mb.render_resolution=0.014; mb.threshold=A.threshold
mbo=bpy.data.objects.new("wolf_meta",mb); bpy.context.collection.objects.link(mbo)
def ball(co,r):
    e=mb.elements.new(type='BALL'); e.co=Vector(co); e.radius=max(r,0.01)*RS; e.stiffness=2.0
def ellip(co,r,sx,sy,sz):
    e=mb.elements.new(type='ELLIPSOID'); e.co=Vector(co); e.radius=max(r,0.01)*RS
    e.size_x=sx; e.size_y=sy; e.size_z=sz; e.stiffness=2.0
# ===== GOVDE =====
ellip((0, 0.34,0.62), 0.085, 1.05, 1.25, 1.55)
ellip((0, 0.20,0.575),0.10,  1.15, 1.35, 1.95)
ellip((0, 0.05,0.575),0.095, 1.15, 1.35, 1.70)
ellip((0,-0.13,0.585),0.075, 1.05, 1.30, 1.30)
ellip((0,-0.28,0.585),0.092, 1.10, 1.30, 1.45)
ellip((0,-0.37,0.585),0.10,  1.15, 1.20, 1.55)
# ===== BOYUN + YELE =====
ellip((0,0.42,0.585),0.105, 1.30, 1.25, 1.50)
ball((0,0.47,0.655),0.085)
ball((0,0.53,0.72),0.075)
# ===== KAFA (iyilestirilmis) =====
ball((0,0.585,0.79),0.082)                          # kafatasi (buyuk)
ball((0,0.55,0.805),0.058)                          # arka kafa/stop
ball(( 0.042,0.612,0.812),0.030); ball((-0.042,0.612,0.812),0.030)  # kas/brow
ball(( 0.052,0.60,0.748),0.040); ball((-0.052,0.60,0.748),0.040)    # yanak (dolgun)
ball((0,0.655,0.778),0.047)                         # burun tabani / nazal kopru
ball((0,0.715,0.764),0.038)                         # burun orta
ball((0,0.775,0.749),0.030)                         # burun
ball((0,0.83,0.736),0.024)                          # burun uc
ball((0,0.862,0.727),0.018)                         # nose pad
ball((0,0.72,0.719),0.030)                          # alt cene
ball((0,0.79,0.713),0.022)                          # cene on/chin
# ===== BACAKLAR =====
def seg(name,rh,rt,step=0.026):
    if name not in bones: return
    h,t=H(name),T(name); L=(t-h).length; n=max(1,int(math.ceil(L/step)))
    for k in range(n+1):
        f=k/n; ball(h.lerp(t,f), rh+(rt-rh)*f)
for suf in ("L","R"):
    seg(f"scapula_{suf}",0.058,0.045); seg(f"upper_arm_{suf}",0.045,0.036)
    seg(f"forearm_{suf}",0.036,0.026); seg(f"front_paw_{suf}",0.028,0.030)
    ball(T(f"front_paw_{suf}"),0.034); ball(T(f"front_toe_{suf}"),0.030)
    seg(f"pelvis_{suf}",0.075,0.062); seg(f"thigh_{suf}",0.07,0.045)
    seg(f"shin_{suf}",0.04,0.03); seg(f"metatarsus_{suf}",0.028,0.028)
    ball(T(f"metatarsus_{suf}"),0.032); ball(T(f"rear_toe_{suf}"),0.028)
# ===== KUYRUK (daha kalin taban) =====
for i in range(12):
    nm=f"tail_{i}"
    if nm in bones:
        seg(nm, max(0.074-0.0040*i,0.024), max(0.074-0.0040*(i+1),0.022))
print(f"[meshv3] {len(mb.elements)} element")
bpy.context.view_layer.objects.active=mbo; bpy.ops.object.select_all(action='DESELECT'); mbo.select_set(True)
bpy.ops.object.convert(target='MESH')
body=bpy.context.view_layer.objects.active; body.name="creature_mesh"
# kulaklar (daha buyuk dik ucgen)
sk=Vector((0,0.585,0.79))
def ear(side):
    bpy.ops.mesh.primitive_cone_add(vertices=14,radius1=0.046,radius2=0.003,depth=0.125,
        location=(side*0.058, sk.y-0.012, sk.z+0.10))
    e=bpy.context.view_layer.objects.active
    e.rotation_euler=(math.radians(-8),side*math.radians(15),0)
    bpy.ops.object.transform_apply(rotation=True,scale=True); return e
eL=ear(1); eR=ear(-1)
bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); eL.select_set(True); eR.select_set(True)
bpy.context.view_layer.objects.active=body; bpy.ops.object.join()
body.data.remesh_mode='VOXEL'; body.data.remesh_voxel_size=A.voxel
body.data.use_remesh_preserve_volume=True; body.data.use_remesh_fix_poles=True
bpy.ops.object.voxel_remesh()
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
print(f"[meshv3] FINAL tris={final} verts={len(me.vertices)} nonmanifold={nm} boundary={bd}")
print(f"[meshv3] bbox={[round(bbmax[i]-bbmin[i],3) for i in range(3)]}")
out=Path(A.output_blend).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print(f"[meshv3] SAVED {out}")
