#!/usr/bin/env python3
"""Profesyonel kurt render: kisa-yogun yalin kurk + agouti renk + amber goz +
islak siyah burun + sinematik 3-nokta isik. Opsiyonel hair-dynamics.
blender --background <mesh.blend> --python wolf_fur_pro.py -- <outdir> [samples] [dyn0|dyn1]
"""
import bpy, math, sys, os
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
outdir=argv[0]; samples=int(argv[1]) if len(argv)>1 else 64
DYN = (len(argv)>2 and argv[2]=="dyn1")
mesh=None; arm=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
    if o.type=='ARMATURE': arm=o
if arm:
    arm.hide_render=True; arm.hide_viewport=True
    if arm.animation_data:
        for t in arm.animation_data.nla_tracks: t.mute=True
me=mesh.data
def sstep(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a+1e-9))); return t*t*(3-2*t)
# skin (koyu, kurk arasindan)
for m in list(me.materials): me.materials.clear()
skin=bpy.data.materials.new("skin"); skin.use_nodes=True
bs=skin.node_tree.nodes.get("Principled BSDF")
bs.inputs['Base Color'].default_value=(0.09,0.08,0.072,1); bs.inputs['Roughness'].default_value=0.95
me.materials.append(skin)
# vgroups
vg_len=mesh.vertex_groups.new(name="fur_len"); vg_den=mesh.vertex_groups.new(name="fur_den")
for v in me.vertices:
    x,y,z=v.co.x,v.co.y,v.co.z; L=0.30
    if -0.36<y<0.32 and z>0.50: L+=0.05    # govde yalin
    if 0.30<y<0.50 and z>0.46: L+=0.42*sstep(0.46,0.66,z)   # yele (boyun)
    if y<-0.40: L=max(L,0.92)              # kuyruk gur
    if y>0.52 and z>0.64: L=0.035          # yuz cok kisa
    if z<0.30: L=min(L,0.13)               # alt bacak kisa
    L=max(0.03,min(1.0,L)); vg_len.add([v.index],L,'REPLACE')
    den=1.0
    if y>0.60 and z>0.66: den=0.6
    vg_den.add([v.index],den,'REPLACE')
# hair material (agouti banding)
hair=bpy.data.materials.new("fur"); hair.use_nodes=True; ht=hair.node_tree; ht.nodes.clear()
ho=ht.nodes.new('ShaderNodeOutputMaterial'); ho.location=(500,0)
ok=False
try:
    hb=ht.nodes.new('ShaderNodeBsdfHairPrincipled'); hb.location=(220,0)
    if hasattr(hb,'parametrization'): hb.parametrization='COLOR'
    hi=ht.nodes.new('ShaderNodeHairInfo'); hi.location=(-420,0)
    ramp=ht.nodes.new('ShaderNodeValToRGB'); ramp.location=(-200,0)
    el=ramp.color_ramp.elements
    el[0].position=0.0; el[0].color=(0.030,0.027,0.025,1)
    el[1].position=1.0; el[1].color=(0.045,0.040,0.036,1)
    a=ramp.color_ramp.elements.new(0.30); a.color=(0.155,0.135,0.105,1)
    b=ramp.color_ramp.elements.new(0.55); b.color=(0.36,0.32,0.255,1)
    c=ramp.color_ramp.elements.new(0.80); c.color=(0.11,0.10,0.085,1)
    ht.links.new(hi.outputs['Intercept'], ramp.inputs['Fac'])
    if 'Color' in hb.inputs: ht.links.new(ramp.outputs['Color'], hb.inputs['Color'])
    if 'Roughness' in hb.inputs: hb.inputs['Roughness'].default_value=0.5
    ht.links.new(hb.outputs[0], ho.inputs['Surface']); ok=True
except Exception as ex:
    print("HAIR_FALLBACK",ex)
if not ok:
    d=ht.nodes.new('ShaderNodeBsdfDiffuse'); d.inputs['Color'].default_value=(0.18,0.16,0.12,1)
    ht.links.new(d.outputs[0],ho.inputs['Surface'])
me.materials.append(hair); hair_slot=len(me.materials)-1
# particle hair (kisa-yogun)
bpy.context.view_layer.objects.active=mesh
mesh.modifiers.new("fur",'PARTICLE_SYSTEM'); psys=mesh.particle_systems[-1]; ps=psys.settings
ps.type='HAIR'; ps.count=22000; ps.hair_length=0.052; ps.use_advanced_hair=True
ps.emit_from='FACE'; ps.distribution='RAND'; ps.use_modifier_stack=True
ps.child_type='INTERPOLATED'; ps.child_percent=28; ps.rendered_child_count=80
ps.clump_factor=0.62; ps.clump_shape=0.4
ps.roughness_1=0.08; ps.roughness_1_size=0.7; ps.roughness_endpoint=0.18; ps.roughness_end_shape=1.0
ps.kink='WAVE'; ps.kink_amplitude=0.003; ps.kink_frequency=1.2
ps.use_hair_bspline=True; ps.render_step=3; ps.display_step=2
psys.vertex_group_length="fur_len"; psys.vertex_group_density="fur_den"
ps.material=hair_slot+1; ps.child_length=1.0; ps.child_radius=0.010; ps.child_roundness=1.0
if DYN:
    try:
        ps.use_hair_dynamics=True; cs=psys.cloth.settings
        cs.mass=0.03; cs.bending_stiffness=0.4; cs.pin_stiffness=0.95; cs.air_damping=3.0; cs.quality=5
        bpy.context.scene.frame_start=1; bpy.context.scene.frame_end=22
        for f in range(1,23):
            bpy.context.scene.frame_set(f)
        print("DYN_BAKED")
    except Exception as ex:
        print("DYN_FAIL",ex)
# gozler + burun
def sph(name,loc,r,color,rough,emit=0.0,clear=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r,location=loc,segments=18,ring_count=14)
    s=bpy.context.view_layer.objects.active; s.name=name; bpy.ops.object.shade_smooth()
    m=bpy.data.materials.new(name+"_m"); m.use_nodes=True; bb=m.node_tree.nodes.get("Principled BSDF")
    bb.inputs['Base Color'].default_value=(*color,1); bb.inputs['Roughness'].default_value=rough
    if emit>0 and 'Emission Color' in bb.inputs:
        bb.inputs['Emission Color'].default_value=(*color,1); bb.inputs['Emission Strength'].default_value=emit
    if clear>0 and 'Coat Weight' in bb.inputs: bb.inputs['Coat Weight'].default_value=clear
    s.data.materials.append(m); return s
sph("eye_L",( 0.047,0.662,0.797),0.0145,(0.55,0.34,0.06),0.12,0.35)
sph("eye_R",(-0.047,0.662,0.797),0.0145,(0.55,0.34,0.06),0.12,0.35)
sph("nose",(0.0,0.864,0.726),0.017,(0.015,0.015,0.018),0.10,clear=1.0)
# zemin
bpy.ops.mesh.primitive_plane_add(size=12,location=(0,0,0))
gp=bpy.context.view_layer.objects.active; gm=bpy.data.materials.new("g"); gm.use_nodes=True
gp_b=gm.node_tree.nodes.get("Principled BSDF"); gp_b.inputs['Base Color'].default_value=(0.13,0.135,0.125,1); gp_b.inputs['Roughness'].default_value=1.0
gp.data.materials.append(gm)
# world soft sky
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
bgn=w.node_tree.nodes["Background"]; bgn.inputs[0].default_value=(0.42,0.48,0.57,1); bgn.inputs[1].default_value=0.55
# 3-nokta isik
sd=bpy.data.lights.new("key",'SUN'); sd.energy=3.6; sd.angle=math.radians(3); sd.color=(1.0,0.96,0.9)
so=bpy.data.objects.new("key",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(52),math.radians(8),math.radians(46))
rd=bpy.data.lights.new("rim",'SUN'); rd.energy=2.4; rd.color=(0.7,0.8,1.0)
ro=bpy.data.objects.new("rim",rd); bpy.context.collection.objects.link(ro); ro.rotation_euler=(math.radians(64),0,math.radians(210))
fd=bpy.data.lights.new("fill",'AREA'); fd.energy=90; fd.size=5
fo=bpy.data.objects.new("fill",fd); fo.location=(-2.6,-1.8,1.4); bpy.context.collection.objects.link(fo)
ft=bpy.data.objects.new("ft",None); ft.location=(0,0,0.5); bpy.context.collection.objects.link(ft); fo.constraints.new('TRACK_TO').target=ft
# kamera
bb=[mesh.matrix_world@Vector(c) for c in mesh.bound_box]
ctr=sum(bb,Vector())/8; size=max((max(v[i] for v in bb)-min(v[i] for v in bb)) for i in range(3))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co; cam.lens=85
tg=bpy.data.objects.new("t",None); bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=samples
sc.cycles.use_denoising=True; sc.render.resolution_x=860; sc.render.resolution_y=640
sc.view_settings.look='AgX - Medium High Contrast' if 'AgX - Medium High Contrast' in [x.name for x in __import__('bpy').types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items] else 'None'
os.makedirs(outdir,exist_ok=True)
d=size*1.95
shots=[("hero",38,9,1.0,ctr+Vector((0,0,-0.02))),
       ("head",54,4,0.52,Vector((0.0,0.74,0.80))),
       ("side",90,7,1.0,ctr+Vector((0,0,-0.02)))]
for nm,az,el,fac,target in shots:
    a=math.radians(az); e=math.radians(el)
    co.location=(ctr.x+d*fac*math.sin(a)*math.cos(e), ctr.y-d*fac*math.cos(a)*math.cos(e), ctr.z+d*fac*math.sin(e))
    tg.location=target
    sc.render.filepath=os.path.join(outdir,nm+".png"); bpy.ops.render.render(write_still=True)
    print("RENDERED",nm)
print("FUR_PRO_DONE")
