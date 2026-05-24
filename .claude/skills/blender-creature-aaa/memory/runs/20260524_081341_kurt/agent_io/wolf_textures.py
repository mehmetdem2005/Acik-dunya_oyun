#!/usr/bin/env python3
"""Kurt PBR texture seti: UV unwrap + prosedurel kurk materyali -> bake
albedo/normal/roughness/AO/height (PNG). Sonra baked-texture Principled materyali
atar ve textured beauty render alir.
blender --background <mesh.blend> --python wolf_textures.py -- <texdir> <renderdir> <res> [samples]
"""
import bpy, sys, os, math
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
texdir, rdir = argv[0], argv[1]
RES=int(argv[2]) if len(argv)>2 else 2048
SAMP=int(argv[3]) if len(argv)>3 else 48
os.makedirs(texdir,exist_ok=True); os.makedirs(rdir,exist_ok=True)
mesh=None; arm=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
    if o.type=='ARMATURE': arm=o
if arm: arm.hide_render=True; arm.hide_viewport=True
me=mesh.data
bpy.context.view_layer.objects.active=mesh; bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True)

# ---------- UV ----------
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.012, area_weight=0.0, correct_aspect=True)
bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
bpy.ops.object.mode_set(mode='OBJECT')
if me.uv_layers.active: me.uv_layers.active.name="UVMap"

# ---------- prosedurel kurk materyali ----------
for m in list(me.materials): me.materials.clear()
mat=bpy.data.materials.new("wolf_proc"); mat.use_nodes=True; nt=mat.node_tree; nt.nodes.clear()
N=nt.nodes; L=nt.links
out=N.new('ShaderNodeOutputMaterial'); out.location=(1400,0)
bsdf=N.new('ShaderNodeBsdfPrincipled'); bsdf.location=(1100,0); L.new(bsdf.outputs[0],out.inputs['Surface'])
geo=N.new('ShaderNodeNewGeometry'); geo.location=(-1200,400)
sep=N.new('ShaderNodeSeparateXYZ'); sep.location=(-1000,400); L.new(geo.outputs['Position'],sep.inputs[0])
tc=N.new('ShaderNodeTexCoord'); tc.location=(-1200,-200)

# --- countershade: Z -> renk ---
zmap=N.new('ShaderNodeMapRange'); zmap.location=(-820,500)
zmap.inputs['From Min'].default_value=0.0; zmap.inputs['From Max'].default_value=0.93
L.new(sep.outputs['Z'], zmap.inputs['Value'])
cramp=N.new('ShaderNodeValToRGB'); cramp.location=(-620,520)
e=cramp.color_ramp.elements
e[0].position=0.0; e[0].color=(0.42,0.37,0.30,1)     # karin/gerdan krem
e[1].position=1.0; e[1].color=(0.085,0.075,0.060,1)  # sirt koyu
m1=cramp.color_ramp.elements.new(0.42); m1.color=(0.26,0.225,0.175,1)  # agouti tan yan
m2=cramp.color_ramp.elements.new(0.70); m2.color=(0.135,0.115,0.092,1) # ust-orta koyu-gri
L.new(zmap.outputs['Result'], cramp.inputs['Fac'])

# --- fur mottle (orta-olcek noise) ---
nz=N.new('ShaderNodeTexNoise'); nz.location=(-820,150); nz.inputs['Scale'].default_value=42.0; nz.inputs['Detail'].default_value=6.0
L.new(tc.outputs['Object'], nz.inputs['Vector'])
nzr=N.new('ShaderNodeValToRGB'); nzr.location=(-620,150)
nzr.color_ramp.elements[0].position=0.35; nzr.color_ramp.elements[0].color=(0.75,0.75,0.75,1)
nzr.color_ramp.elements[1].position=0.70; nzr.color_ramp.elements[1].color=(1.18,1.18,1.18,1)
L.new(nz.outputs['Fac'], nzr.inputs['Fac'])
mott=N.new('ShaderNodeMixRGB'); mott.location=(-380,350); mott.blend_type='MULTIPLY'; mott.inputs['Fac'].default_value=0.6
L.new(cramp.outputs['Color'], mott.inputs['Color1']); L.new(nzr.outputs['Color'], mott.inputs['Color2'])

# --- yuz maskesi (burun koyu) + bacak koyu: Y ve Z ile ---
yposm=N.new('ShaderNodeMapRange'); yposm.location=(-820,-80)
yposm.inputs['From Min'].default_value=0.55; yposm.inputs['From Max'].default_value=0.9
L.new(sep.outputs['Y'], yposm.inputs['Value'])
# muzzle koyu mix (sadece kafa bolgesi Z>0.65 & Y>0.55)
face_dark=N.new('ShaderNodeMixRGB'); face_dark.location=(-150,250); face_dark.blend_type='MIX'
face_dark.inputs['Color2'].default_value=(0.07,0.06,0.05,1)
# fac = ymask * (z high)
zhi=N.new('ShaderNodeMapRange'); zhi.location=(-820,-260); zhi.inputs['From Min'].default_value=0.64; zhi.inputs['From Max'].default_value=0.80
L.new(sep.outputs['Z'], zhi.inputs['Value'])
facemul=N.new('ShaderNodeMath'); facemul.location=(-560,-150); facemul.operation='MULTIPLY'
L.new(yposm.outputs['Result'], facemul.inputs[0]); L.new(zhi.outputs['Result'], facemul.inputs[1])
L.new(mott.outputs['Color'], face_dark.inputs['Color1']); L.new(facemul.outputs['Value'], face_dark.inputs['Fac'])
L.new(face_dark.outputs['Color'], bsdf.inputs['Base Color'])

# --- fur strand bump: anizotropik wave + ince noise ---
wv=N.new('ShaderNodeTexWave'); wv.location=(-820,-520); wv.wave_type='BANDS'; wv.inputs['Scale'].default_value=2.0
wv.inputs['Distortion'].default_value=18.0; wv.inputs['Detail'].default_value=3.0
mapw=N.new('ShaderNodeMapping'); mapw.location=(-1000,-520); mapw.inputs['Scale'].default_value=(2.0,2.0,60.0)
L.new(tc.outputs['Object'], mapw.inputs['Vector']); L.new(mapw.outputs['Vector'], wv.inputs['Vector'])
fine=N.new('ShaderNodeTexNoise'); fine.location=(-820,-720); fine.inputs['Scale'].default_value=300.0; fine.inputs['Detail'].default_value=8.0
L.new(tc.outputs['Object'], fine.inputs['Vector'])
hmix=N.new('ShaderNodeMath'); hmix.location=(-560,-620); hmix.operation='MULTIPLY_ADD'
L.new(wv.outputs['Color'], hmix.inputs[0]); hmix.inputs[1].default_value=0.7
L.new(fine.outputs['Fac'], hmix.inputs[2])
bump=N.new('ShaderNodeBump'); bump.location=(700,-300); bump.inputs['Strength'].default_value=0.45; bump.inputs['Distance'].default_value=0.012
L.new(hmix.outputs['Value'], bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

# --- roughness varyasyon ---
rr=N.new('ShaderNodeMapRange'); rr.location=(700,-560); rr.inputs['From Min'].default_value=0.0; rr.inputs['From Max'].default_value=1.0
rr.inputs['To Min'].default_value=0.62; rr.inputs['To Max'].default_value=0.88
L.new(nz.outputs['Fac'], rr.inputs['Value']); L.new(rr.outputs['Result'], bsdf.inputs['Roughness'])
bsdf.inputs['Metallic'].default_value=0.0
me.materials.append(mat)

# ---------- BAKE ----------
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=SAMP
rb=sc.render.bake; rb.use_selected_to_active=False; rb.margin=8
def newimg(name, noncolor=False):
    img=bpy.data.images.new(name, RES, RES, alpha=False, float_buffer=False)
    if noncolor: img.colorspace_settings.name='Non-Color'
    return img
def set_target(img):
    tex=N.new('ShaderNodeTexImage'); tex.image=img; N.active=tex; tex.select=True; return tex
def savepng(img,path):
    img.filepath_raw=path; img.file_format='PNG'; img.save()

results={}
# 1 ALBEDO (diffuse color)
img_a=newimg("wolf_body_albedo"); t=set_target(img_a)
rb.use_pass_direct=False; rb.use_pass_indirect=False; rb.use_pass_color=True
bpy.ops.object.bake(type='DIFFUSE'); savepng(img_a, os.path.join(texdir,"wolf_body_albedo.png")); N.remove(t)
print("BAKED albedo")
# 2 NORMAL (tangent)
img_n=newimg("wolf_body_normal", noncolor=True); t=set_target(img_n)
bpy.ops.object.bake(type='NORMAL'); savepng(img_n, os.path.join(texdir,"wolf_body_normal.png")); N.remove(t)
print("BAKED normal")
# 3 ROUGHNESS
img_r=newimg("wolf_body_roughness", noncolor=True); t=set_target(img_r)
bpy.ops.object.bake(type='ROUGHNESS'); savepng(img_r, os.path.join(texdir,"wolf_body_roughness.png")); N.remove(t)
print("BAKED roughness")
# 4 AO
img_o=newimg("wolf_body_ao", noncolor=True); t=set_target(img_o)
bpy.ops.object.bake(type='AO'); savepng(img_o, os.path.join(texdir,"wolf_body_ao.png")); N.remove(t)
print("BAKED ao")
# 5 HEIGHT (emit hmix) -> gecici emit material yerine: bake EMIT after wiring height to emission
emit=N.new('ShaderNodeEmission'); emit.location=(1100,-400)
L.new(hmix.outputs['Value'], emit.inputs['Color'])
tmpout=N.new('ShaderNodeOutputMaterial'); tmpout.location=(1400,-400); tmpout.is_active_output=True
L.new(emit.outputs[0], tmpout.inputs['Surface'])
img_h=newimg("wolf_body_height", noncolor=True); t=set_target(img_h)
bpy.ops.object.bake(type='EMIT'); savepng(img_h, os.path.join(texdir,"wolf_body_height.png")); N.remove(t)
out.is_active_output=True; tmpout.is_active_output=False
print("BAKED height")

# ---------- baked-texture materyali (export/render icin) ----------
fm=bpy.data.materials.new("kurt_001_main"); fm.use_nodes=True; fn=fm.node_tree; fn.nodes.clear()
fo=fn.nodes.new('ShaderNodeOutputMaterial'); fo.location=(700,0)
fb=fn.nodes.new('ShaderNodeBsdfPrincipled'); fb.location=(350,0); fn.links.new(fb.outputs[0],fo.inputs['Surface'])
def imgnode(path,loc,noncolor=False):
    im=bpy.data.images.load(path); n=fn.nodes.new('ShaderNodeTexImage'); n.image=im; n.location=loc
    if noncolor: im.colorspace_settings.name='Non-Color'
    return n
na=imgnode(os.path.join(texdir,"wolf_body_albedo.png"),(-400,300))
# AO * albedo
nao=imgnode(os.path.join(texdir,"wolf_body_ao.png"),(-400,560),True)
mul=fn.nodes.new('ShaderNodeMixRGB'); mul.blend_type='MULTIPLY'; mul.inputs['Fac'].default_value=0.7; mul.location=(0,400)
fn.links.new(na.outputs['Color'],mul.inputs['Color1']); fn.links.new(nao.outputs['Color'],mul.inputs['Color2'])
fn.links.new(mul.outputs['Color'], fb.inputs['Base Color'])
nr=imgnode(os.path.join(texdir,"wolf_body_roughness.png"),(-400,0),True)
fn.links.new(nr.outputs['Color'], fb.inputs['Roughness'])
nn=imgnode(os.path.join(texdir,"wolf_body_normal.png"),(-400,-300),True)
nm=fn.nodes.new('ShaderNodeNormalMap'); nm.location=(-100,-300)
fn.links.new(nn.outputs['Color'],nm.inputs['Color']); fn.links.new(nm.outputs['Normal'],fb.inputs['Normal'])
for m in list(me.materials): me.materials.clear()
me.materials.append(fm)
_rundir=os.path.dirname(os.path.abspath(texdir))
_bs=os.path.join(_rundir,"blender_scenes"); os.makedirs(_bs,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(_bs,"textured_v1.blend"))

# ---------- textured beauty render ----------
bb=[mesh.matrix_world@Vector(c) for c in mesh.bound_box]
ctr=sum(bb,Vector())/8; size=max((max(v[i] for v in bb)-min(v[i] for v in bb)) for i in range(3))
bpy.ops.mesh.primitive_plane_add(size=12,location=(0,0,0)); gp=bpy.context.view_layer.objects.active
gmm=bpy.data.materials.new("g"); gmm.use_nodes=True; gmm.node_tree.nodes.get("Principled BSDF").inputs['Base Color'].default_value=(0.14,0.14,0.13,1); gp.data.materials.append(gmm)
w=sc.world or bpy.data.worlds.new("W"); sc.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.42,0.48,0.57,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.6
sd=bpy.data.lights.new("key",'SUN'); sd.energy=3.4; sd.angle=math.radians(3); sd.color=(1,0.96,0.9)
so=bpy.data.objects.new("key",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(52),math.radians(8),math.radians(46))
rd=bpy.data.lights.new("rim",'SUN'); rd.energy=2.2; rd.color=(0.7,0.8,1.0)
ro=bpy.data.objects.new("rim",rd); bpy.context.collection.objects.link(ro); ro.rotation_euler=(math.radians(64),0,math.radians(210))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); sc.camera=co; cam.lens=85
tg=bpy.data.objects.new("t",None); bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc.cycles.samples=max(SAMP,48); sc.cycles.use_denoising=True; sc.render.resolution_x=900; sc.render.resolution_y=640
d=size*1.95
for nm_,az,el,fac,tgt in [("hero",40,9,1.0,ctr+Vector((0,0,-0.02))),("head",55,4,0.5,Vector((0,0.74,0.80))),("side",90,7,1.0,ctr+Vector((0,0,-0.02)))]:
    a=math.radians(az); e=math.radians(el)
    co.location=(ctr.x+d*fac*math.sin(a)*math.cos(e),ctr.y-d*fac*math.cos(a)*math.cos(e),ctr.z+d*fac*math.sin(e))
    tg.location=tgt; sc.render.filepath=os.path.join(rdir,nm_+".png"); bpy.ops.render.render(write_still=True); print("RENDERED",nm_)
print("TEX_DONE", texdir)
