#!/usr/bin/env python3
"""P04 v4 — detayli kafa/kulak/cene/boyun + duzgun topline + subdivision (organik).
Govde+kafa metaball -> ince voxel remesh; kulaklar AYRI ince ucgen olarak
modellenip remesh sonrasi eklenir (sekil korunur); subdivision ile organik yuzey.
blender --background <skeleton.blend> --python gen_wolf_mesh_v4.py -- \
  --blueprint <bp> --budget <bud> --output-blend <out> [--render-res] [--target-tris N]
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
    p.add_argument("--threshold",type=float,default=0.62)
    p.add_argument("--voxel",type=float,default=0.0055)
    p.add_argument("--subdiv",type=int,default=2)
    p.add_argument("--target-tris",type=int,default=0)  # 0 = decimate yok (render icin smooth)
    return p.parse_args(a)
A=args()
bp=json.loads(Path(A.blueprint).read_text()); budget=json.loads(Path(A.budget).read_text())
RS=A.radius_scale
bones={b["name"]:b for b in bp["bones"]}
def H(n): return Vector(bones[n]["head_local"])
def T(n): return Vector(bones[n]["tail_local"])
mb=bpy.data.metaballs.new("w"); mb.resolution=0.014; mb.render_resolution=0.012; mb.threshold=A.threshold
mbo=bpy.data.objects.new("wm",mb); bpy.context.collection.objects.link(mbo)
def ball(co,r,stiff=2.0):
    e=mb.elements.new(type='BALL'); e.co=Vector(co); e.radius=max(r,0.008)*RS; e.stiffness=stiff
def ellip(co,r,sx,sy,sz):
    e=mb.elements.new(type='ELLIPSOID'); e.co=Vector(co); e.radius=max(r,0.008)*RS
    e.size_x=sx; e.size_y=sy; e.size_z=sz; e.stiffness=2.0
# ===== GOVDE — duzgun topline (tepe ~0.69-0.70 sabit) =====
ellip((0, 0.33,0.605),0.088, 1.05,1.25,1.62)   # withers (omuz hörgücü)
ellip((0, 0.18,0.560),0.102, 1.18,1.40,2.05)   # derin gogus
ellip((0, 0.02,0.560),0.097, 1.18,1.40,1.78)   # thorax
ellip((0,-0.14,0.575),0.078, 1.06,1.34,1.40)   # bel (tuck-up, ince)
ellip((0,-0.29,0.578),0.094, 1.12,1.32,1.55)   # loin
ellip((0,-0.38,0.585),0.10,  1.16,1.20,1.60)   # croup
# ===== BOYUN — kafadan omuza akiskan, kalin alt =====
ellip((0,0.40,0.585),0.108, 1.34,1.30,1.55)    # boyun tabani (yele)
ellip((0,0.455,0.64),0.088, 1.15,1.20,1.30)
ball((0,0.51,0.70),0.072); ball((0,0.55,0.745),0.064)
# ===== KAFA — detayli =====
ellip((0,0.595,0.785),0.072, 1.15,1.10,1.05)   # kafatasi
ball((0,0.565,0.80),0.05)                       # arka kafa
ball((0,0.628,0.815),0.045)                     # alin/stop ust
ball(( 0.040,0.628,0.808),0.026); ball((-0.040,0.628,0.808),0.026)  # brow ridge
ball(( 0.052,0.598,0.745),0.038); ball((-0.052,0.598,0.745),0.038)  # yanak
ball(( 0.046,0.605,0.695),0.034); ball((-0.046,0.605,0.695),0.034)  # gonial / cene kosesi (dolgun)
# muzzle UST snout: sik ortusen zincir, hafif daha uzun, ucta yuvarlak burun
_mz=[(0.640,0.782,0.052),(0.670,0.777,0.048),(0.700,0.772,0.044),(0.732,0.767,0.040),
     (0.764,0.762,0.036),(0.796,0.757,0.033),(0.828,0.753,0.030),(0.860,0.749,0.028),
     (0.888,0.745,0.027)]   # uc top biraz buyuk -> yuvarlak burun ucu
for yy,zz,rr in _mz: ball((0,yy,zz),rr,stiff=2.8)
# muzzle ALT cene: DOLGUN + asagi (ust ile arasinda agiz hatti), yuvarlak chin
_jw=[(0.655,0.712,0.043),(0.700,0.709,0.039),(0.745,0.706,0.034),(0.790,0.706,0.029),(0.824,0.708,0.024)]
for yy,zz,rr in _jw: ball((0,yy,zz),rr,stiff=2.8)
# burun pad metaball'dan CIKARILDI (ayri obje olarak render'da eklenir)
# ===== BACAKLAR =====
def seg(name,rh,rt,step=0.022):
    if name not in bones: return
    h,t=H(name),T(name); Ln=(t-h).length; n=max(1,int(math.ceil(Ln/step)))
    for k in range(n+1):
        f=k/n; ball(h.lerp(t,f), rh+(rt-rh)*f)
for suf in ("L","R"):
    seg(f"scapula_{suf}",0.058,0.044); seg(f"upper_arm_{suf}",0.044,0.034)
    seg(f"forearm_{suf}",0.034,0.024); seg(f"front_paw_{suf}",0.027,0.029)
    ball(T(f"front_paw_{suf}"),0.033); ball(T(f"front_toe_{suf}"),0.029)
    seg(f"pelvis_{suf}",0.074,0.060); seg(f"thigh_{suf}",0.069,0.043)
    seg(f"shin_{suf}",0.039,0.029); seg(f"metatarsus_{suf}",0.027,0.027)
    ball(T(f"metatarsus_{suf}"),0.031); ball(T(f"rear_toe_{suf}"),0.027)
# ===== KUYRUK (inceltildi - cok genis degil) =====
for i in range(12):
    nm=f"tail_{i}"
    if nm in bones: seg(nm, max(0.044-0.0028*i,0.013), max(0.044-0.0028*(i+1),0.012))
print(f"[v4] {len(mb.elements)} element")
bpy.context.view_layer.objects.active=mbo; bpy.ops.object.select_all(action='DESELECT'); mbo.select_set(True)
bpy.ops.object.convert(target='MESH')
body=bpy.context.view_layer.objects.active; body.name="creature_mesh"
# voxel remesh (ince)
body.data.remesh_mode='VOXEL'; body.data.remesh_voxel_size=A.voxel
body.data.use_remesh_preserve_volume=True; body.data.use_remesh_fix_poles=True
bpy.ops.object.voxel_remesh()
print(f"[v4] remesh verts={len(body.data.vertices)}")
# ===== KULAKLAR — ince kavisli ucgen (ayri, remesh sonrasi) =====
def make_ear(side):
    # ince ucgen: cone vertices cok, sonra Y(front-back) ekseninde inceltilir + kavis
    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=0.050, radius2=0.004, depth=0.135,
        location=(0,0,0))
    e=bpy.context.view_layer.objects.active; e.name=f"ear_{side}"
    # inceltme (front-back) ve hafif kupa (yana acik)
    e.scale=(1.0,0.34,1.0)
    bpy.ops.object.transform_apply(scale=True)
    # hafif kavis: ust kismi one egmek icin proportional yerine basit rotation
    e.location=(side*0.052, 0.585, 0.875)
    e.rotation_euler=(math.radians(-12), side*math.radians(16), side*math.radians(-4))
    bpy.ops.object.transform_apply(rotation=True)
    # ic kavis (cup): on yuzu hafif icbukey - solidify + biraz scale ile birak
    return e
eL=make_ear(1); eR=make_ear(-1)
bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); eL.select_set(True); eR.select_set(True)
bpy.context.view_layer.objects.active=body; bpy.ops.object.join()
# kucuk birlestirme: ear-body kesisimini kapatmak icin hafif voxel YOK (sekli koru), bunun yerine merge
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0012); bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
# pati taban + yere otur
me=body.data
zmin=min(v.co.z for v in me.vertices); floor=zmin+0.04
for v in me.vertices:
    if v.co.z<floor: v.co.z=floor-0.003
z2=min(v.co.z for v in me.vertices)
for v in me.vertices: v.co.z-=z2
# ===== SUBDIVISION (organik) =====
if A.subdiv>0:
    s=body.modifiers.new("sub",'SUBSURF'); s.levels=A.subdiv; s.render_levels=A.subdiv
    bpy.ops.object.modifier_apply(modifier=s.name)
bpy.ops.object.shade_smooth()
def tris():
    bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm,faces=bm.faces); n=len(bm.faces); bm.free(); return n
if A.target_tris>0:
    cur=tris()
    if cur>A.target_tris:
        d=body.modifiers.new("dec",'DECIMATE'); d.ratio=A.target_tris/cur; bpy.ops.object.modifier_apply(modifier=d.name)
final=tris()
print(f"[v4] FINAL tris={final} verts={len(me.vertices)}")
out=Path(A.output_blend).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print(f"[v4] SAVED {out}")
