#!/usr/bin/env python3
"""Kurt kürkü (particle hair, agouti) + göz + burun + Cycles render.
blender --background <mesh.blend> --python wolf_fur_render.py -- <outdir> [samples]
"""
import bpy, math, sys, os
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
outdir=argv[0]; samples=int(argv[1]) if len(argv)>1 else 64
mesh=None; arm=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
    if o.type=='ARMATURE': arm=o
if arm:
    arm.hide_render=True; arm.hide_viewport=True
    if arm.animation_data:
        for t in arm.animation_data.nla_tracks: t.mute=True
me=mesh.data
xs=[v.co.x for v in me.vertices]; ys=[v.co.y for v in me.vertices]; zs=[v.co.z for v in me.vertices]
zmin,zmax=min(zs),max(zs); ymin,ymax=min(ys),max(ys)
def sstep(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a+1e-9))); return t*t*(3-2*t)

# ---- skin material (vertex-color agouti benzeri) ----
for m in list(me.materials): me.materials.clear()
skin=bpy.data.materials.new("kurt_skin"); skin.use_nodes=True
nt=skin.node_tree; nt.nodes.clear()
o1=nt.nodes.new('ShaderNodeOutputMaterial'); o1.location=(400,0)
b1=nt.nodes.new('ShaderNodeBsdfPrincipled'); b1.location=(120,0)
b1.inputs['Base Color'].default_value=(0.12,0.105,0.095,1); b1.inputs['Roughness'].default_value=0.95
nt.links.new(b1.outputs['BSDF'],o1.inputs['Surface'])
me.materials.append(skin)

# ---- fur length / density vertex groups ----
vg_len=mesh.vertex_groups.new(name="fur_len"); vg_den=mesh.vertex_groups.new(name="fur_den")
for v in me.vertices:
    x,y,z=v.co.x,v.co.y,v.co.z
    L=0.30  # kisa yalin post (base)
    # sirt/govde orta (kisa-orta)
    if -0.36<y<0.32 and z>0.50: L+=0.22
    # boyun yelesi: SADECE boyun tabani (mutlak y), kafa haric
    if 0.30<y<0.50 and z>0.46: L+=0.55*sstep(0.46,0.64,z)
    # kuyruk gur (arka)
    if y<-0.40: L+=0.62
    # YUZ/KAFA cok kisa -> muzzle/goz/kulak/burun gorunsun
    if y>0.52 and z>0.64: L=0.05
    # alt bacak/pati kisa
    if z<0.30: L=min(L,0.14)
    L=max(0.04,min(1.0,L))
    vg_len.add([v.index], L, 'REPLACE')
    den=1.0
    if y>0.60 and z>0.66: den=0.65   # yuz biraz seyrek
    vg_den.add([v.index], den, 'REPLACE')

# ---- hair material (agouti: koyu kok, acik bant, koyu uc) ----
hair=bpy.data.materials.new("kurt_fur"); hair.use_nodes=True
ht=hair.node_tree; ht.nodes.clear()
ho=ht.nodes.new('ShaderNodeOutputMaterial'); ho.location=(500,0)
try:
    hb=ht.nodes.new('ShaderNodeBsdfHairPrincipled'); hb.location=(220,0)
    if hasattr(hb,'parametrization'): hb.parametrization='COLOR'
    hi=ht.nodes.new('ShaderNodeHairInfo'); hi.location=(-400,0)
    ramp=ht.nodes.new('ShaderNodeValToRGB'); ramp.location=(-180,0)
    e=ramp.color_ramp.elements
    e[0].position=0.0; e[0].color=(0.035,0.030,0.028,1)     # kok koyu
    e[1].position=1.0; e[1].color=(0.05,0.045,0.04,1)
    m1=ramp.color_ramp.elements.new(0.45); m1.color=(0.34,0.30,0.24,1)  # acik bant (agouti)
    m2=ramp.color_ramp.elements.new(0.75); m2.color=(0.10,0.09,0.08,1)  # uc koyu
    ht.links.new(hi.outputs['Intercept'], ramp.inputs['Fac'])
    if 'Color' in hb.inputs: ht.links.new(ramp.outputs['Color'], hb.inputs['Color'])
    if 'Roughness' in hb.inputs: hb.inputs['Roughness'].default_value=0.55
    ht.links.new(hb.outputs[0], ho.inputs['Surface'])
except Exception as ex:
    print("HAIR_BSDF_FALLBACK", ex)
    d=ht.nodes.new('ShaderNodeBsdfDiffuse'); d.inputs['Color'].default_value=(0.18,0.16,0.13,1)
    ht.links.new(d.outputs[0],ho.inputs['Surface'])
me.materials.append(hair)
hair_slot=len(me.materials)-1

# ---- particle hair ----
bpy.context.view_layer.objects.active=mesh
ms=mesh.modifiers.new("fur",'PARTICLE_SYSTEM'); psys=mesh.particle_systems[-1]; ps=psys.settings
ps.type='HAIR'; ps.count=16000; ps.hair_length=0.042; ps.use_advanced_hair=True
ps.emit_from='FACE'; ps.distribution='RAND'; ps.use_modifier_stack=True
ps.child_type='INTERPOLATED'; ps.child_percent=22; ps.rendered_child_count=66
ps.clump_factor=0.68; ps.clump_shape=0.35
ps.roughness_1=0.10; ps.roughness_1_size=0.6; ps.roughness_endpoint=0.20; ps.roughness_end_shape=1.0
ps.kink='CURL'; ps.kink_amplitude=0.006; ps.kink_frequency=2.0
ps.use_hair_bspline=True; ps.render_step=3; ps.display_step=2
psys.vertex_group_length="fur_len"; psys.vertex_group_density="fur_den"
ps.material=hair_slot+1   # 1-based
ps.child_length=1.0; ps.child_radius=0.012

# ---- gozler (amber) + burun (siyah) ----
def add_sphere(name,loc,r,color,rough,emit=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r,location=loc,segments=16,ring_count=12)
    s=bpy.context.view_layer.objects.active; s.name=name; bpy.ops.object.shade_smooth()
    m=bpy.data.materials.new(name+"_m"); m.use_nodes=True
    bs=m.node_tree.nodes.get("Principled BSDF")
    bs.inputs['Base Color'].default_value=(*color,1); bs.inputs['Roughness'].default_value=rough
    if emit>0 and 'Emission Color' in bs.inputs:
        bs.inputs['Emission Color'].default_value=(*color,1); bs.inputs['Emission Strength'].default_value=emit
    s.data.materials.append(m); return s
add_sphere("eye_L",( 0.040,0.642,0.792),0.0145,(0.42,0.26,0.05),0.18,0.15)
add_sphere("eye_R",(-0.040,0.642,0.792),0.0145,(0.42,0.26,0.05),0.18,0.15)
add_sphere("nose",(0.0,0.842,0.716),0.017,(0.02,0.02,0.022),0.25)

# ---- ground + lighting ----
bpy.ops.mesh.primitive_plane_add(size=8,location=(0,0,0))
gp=bpy.context.view_layer.objects.active; gm=bpy.data.materials.new("ground"); gm.use_nodes=True
gm.node_tree.nodes.get("Principled BSDF").inputs['Base Color'].default_value=(0.16,0.17,0.16,1)
gm.node_tree.nodes.get("Principled BSDF").inputs['Roughness'].default_value=1.0
gp.data.materials.append(gm)
# world sky
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
bgn=w.node_tree.nodes["Background"]; bgn.inputs[0].default_value=(0.40,0.46,0.55,1); bgn.inputs[1].default_value=0.7
# sun (key) + area fill
sd=bpy.data.lights.new("sun",'SUN'); sd.energy=3.0; sd.angle=math.radians(2)
so=bpy.data.objects.new("sun",sd); bpy.context.collection.objects.link(so)
so.rotation_euler=(math.radians(55),math.radians(12),math.radians(40))
fd=bpy.data.lights.new("fill",'AREA'); fd.energy=120; fd.size=4
fo=bpy.data.objects.new("fill",fd); fo.location=(-2.5,-1.5,1.5); bpy.context.collection.objects.link(fo)

mesh.select_set(False)
bb=[mesh.matrix_world@Vector(c) for c in mesh.bound_box]
ctr=sum(bb,Vector())/8; size=max((max(v[i] for v in bb)-min(v[i] for v in bb)) for i in range(3))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co
cam.lens=70
tg=bpy.data.objects.new("t",None); tg.location=ctr+Vector((0,0,-0.03)); bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=samples
sc.cycles.use_denoising=True
sc.render.resolution_x=820; sc.render.resolution_y=620
os.makedirs(outdir,exist_ok=True)
d=size*1.95
for nm,az,el in [("hero",40,9),("headclose",62,5)]:
    a=math.radians(az); e=math.radians(el)
    fac = 1.0 if nm=="hero" else 0.62
    co.location=(ctr.x+d*fac*math.sin(a)*math.cos(e),ctr.y-d*fac*math.cos(a)*math.cos(e),ctr.z+d*fac*math.sin(e))
    tg.location = ctr+Vector((0,0,-0.02)) if nm=="hero" else Vector((0.0,0.72,0.80))
    sc.render.filepath=os.path.join(outdir,nm+".png"); bpy.ops.render.render(write_still=True)
print("FUR_RENDER_DONE")
