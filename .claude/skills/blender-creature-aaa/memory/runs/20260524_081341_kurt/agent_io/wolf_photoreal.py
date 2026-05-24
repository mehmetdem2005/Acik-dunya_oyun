#!/usr/bin/env python3
"""Foto-real kurt: taranmis kurk (hair-dynamics + arkaya ruzgar comb) + SSS deri
+ Nishita gercek gokyuzu + pupilli amber goz + islak burun. Cycles yuksek ornek.
blender --background <mesh.blend> --python wolf_photoreal.py -- <outdir> [samples] [shots]
"""
import bpy, math, sys, os
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
outdir=argv[0]; SAMP=int(argv[1]) if len(argv)>1 else 72
SHOTS=argv[2] if len(argv)>2 else "hero,head,side"
os.makedirs(outdir,exist_ok=True)
mesh=None; arm=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
    if o.type=='ARMATURE': arm=o
if arm: arm.hide_render=True; arm.hide_viewport=True
me=mesh.data
def sstep(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a+1e-9))); return t*t*(3-2*t)
# ---- SSS deri ----
for m in list(me.materials): me.materials.clear()
skin=bpy.data.materials.new("skin"); skin.use_nodes=True; sb=skin.node_tree.nodes.get("Principled BSDF")
sb.inputs['Base Color'].default_value=(0.10,0.088,0.078,1); sb.inputs['Roughness'].default_value=0.92
if 'Subsurface Weight' in sb.inputs: sb.inputs['Subsurface Weight'].default_value=0.12
if 'Subsurface Radius' in sb.inputs: sb.inputs['Subsurface Radius'].default_value=(0.18,0.09,0.06)
me.materials.append(skin)
# ---- micro displacement (deri/kil kabartisi) ----
try:
    dtex=bpy.data.textures.new("micro",'CLOUDS'); dtex.noise_scale=0.02; dtex.noise_depth=2
    dm=mesh.modifiers.new("disp",'DISPLACE'); dm.texture=dtex; dm.strength=0.004; dm.mid_level=0.5; dm.texture_coords='LOCAL'
except Exception as ex: print("DISP_FAIL",ex)
# ---- fur length/density vgroups ----
xs=[v.co.x for v in me.vertices]; ys=[v.co.y for v in me.vertices]; zs=[v.co.z for v in me.vertices]
vg_len=mesh.vertex_groups.new(name="fl"); vg_den=mesh.vertex_groups.new(name="fd")
for v in me.vertices:
    x,y,z=v.co.x,v.co.y,v.co.z; L=0.42
    if -0.36<y<0.32 and z>0.48: L=0.55          # govde orta
    if 0.30<y<0.50 and z>0.46: L=0.78           # yele
    if y<-0.40: L=1.0                            # kuyruk gur
    if y>0.55 and z>0.66: L=0.10                 # yuz cok kisa
    if z<0.28: L=min(L,0.22)                     # alt bacak
    vg_len.add([v.index],max(0.06,min(1.0,L)),'REPLACE')
    den=1.0
    if y>0.62 and z>0.68: den=0.55
    vg_den.add([v.index],den,'REPLACE')
# ---- agouti hair shader ----
hair=bpy.data.materials.new("fur"); hair.use_nodes=True; ht=hair.node_tree; ht.nodes.clear()
ho=ht.nodes.new('ShaderNodeOutputMaterial'); ho.location=(500,0)
try:
    hb=ht.nodes.new('ShaderNodeBsdfHairPrincipled'); hb.location=(220,0)
    if hasattr(hb,'parametrization'): hb.parametrization='COLOR'
    hi=ht.nodes.new('ShaderNodeHairInfo'); hi.location=(-420,0)
    rmp=ht.nodes.new('ShaderNodeValToRGB'); rmp.location=(-200,0)
    el=rmp.color_ramp.elements
    el[0].position=0.0; el[0].color=(0.028,0.025,0.022,1)
    el[1].position=1.0; el[1].color=(0.04,0.036,0.032,1)
    for p,c in [(0.28,(0.14,0.12,0.095,1)),(0.55,(0.37,0.32,0.255,1)),(0.82,(0.10,0.09,0.078,1))]:
        e=rmp.color_ramp.elements.new(p); e.color=c
    ht.links.new(hi.outputs['Intercept'],rmp.inputs['Fac'])
    if 'Color' in hb.inputs: ht.links.new(rmp.outputs['Color'],hb.inputs['Color'])
    if 'Roughness' in hb.inputs: hb.inputs['Roughness'].default_value=0.45
    ht.links.new(hb.outputs[0],ho.inputs['Surface'])
except Exception as ex:
    print("HAIRBSDF_FALLBACK",ex)
    d=ht.nodes.new('ShaderNodeBsdfDiffuse'); d.inputs['Color'].default_value=(0.2,0.17,0.13,1); ht.links.new(d.outputs[0],ho.inputs['Surface'])
me.materials.append(hair); hslot=len(me.materials)-1
# ---- particle hair (yogun) ----
bpy.context.view_layer.objects.active=mesh
mesh.modifiers.new("fur",'PARTICLE_SYSTEM'); psys=mesh.particle_systems[-1]; ps=psys.settings
ps.type='HAIR'; ps.count=15000; ps.hair_length=0.058; ps.use_advanced_hair=True
ps.emit_from='FACE'; ps.distribution='RAND'; ps.use_modifier_stack=True
ps.child_type='INTERPOLATED'; ps.child_percent=30; ps.rendered_child_count=60
ps.clump_factor=0.66; ps.clump_shape=0.4
ps.roughness_1=0.06; ps.roughness_1_size=0.8; ps.roughness_endpoint=0.14; ps.roughness_end_shape=1.0
ps.use_hair_bspline=True; ps.render_step=3; ps.display_step=3
psys.vertex_group_length="fl"; psys.vertex_group_density="fd"
ps.material=hslot+1; ps.child_length=1.0; ps.child_radius=0.009
# ---- COMB: arkaya+asagi ruzgar + hair dynamics ----
try:
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.effector_add(type='WIND', location=(0,1.6,0.6))
    wind=bpy.context.active_object; wind.name="comb_wind"
    wind.field.strength=7.0; wind.field.flow=0.0; wind.field.noise=0.0
    dvec=Vector((0,-1.0,-0.45)).normalized()
    wind.rotation_euler=dvec.to_track_quat('Z','Y').to_euler()
    bpy.context.view_layer.objects.active=mesh
    ps.use_hair_dynamics=True
    cs=psys.cloth.settings
    cs.mass=0.018; cs.bending_stiffness=0.18; cs.pin_stiffness=1.0; cs.air_damping=1.5; cs.quality=6
    sc=bpy.context.scene; sc.frame_start=1; sc.frame_end=24
    for f in range(1,25): sc.frame_set(f)
    print("COMBED", flush=True)
except Exception as ex:
    print("COMB_FAIL",ex)
# ---- goz (amber+pupil+yas) + burun ----
def sph(name,loc,r,color,rough,emit=0.0,coat=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r,location=loc,segments=20,ring_count=16)
    s=bpy.context.view_layer.objects.active; s.name=name; bpy.ops.object.shade_smooth()
    mt=bpy.data.materials.new(name+"m"); mt.use_nodes=True; bb=mt.node_tree.nodes.get("Principled BSDF")
    bb.inputs['Base Color'].default_value=(*color,1); bb.inputs['Roughness'].default_value=rough
    if emit>0 and 'Emission Color' in bb.inputs: bb.inputs['Emission Color'].default_value=(*color,1); bb.inputs['Emission Strength'].default_value=emit
    if coat>0 and 'Coat Weight' in bb.inputs: bb.inputs['Coat Weight'].default_value=coat
    s.data.materials.append(mt); return s
for sgn in (1,-1):
    sph(f"eye{sgn}",(sgn*0.047,0.662,0.797),0.0145,(0.46,0.29,0.06),0.12,0.25,1.0)
    sph(f"pup{sgn}",(sgn*0.047,0.676,0.798),0.007,(0.01,0.01,0.01),0.05)
sph("nose",(0.0,0.892,0.732),0.016,(0.013,0.013,0.016),0.08,coat=1.0)
# ---- Nishita gokyuzu + gunes ----
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
wt=w.node_tree; wt.nodes.clear()
wout=wt.nodes.new('ShaderNodeOutputWorld'); wbg=wt.nodes.new('ShaderNodeBackground')
try:
    sky=wt.nodes.new('ShaderNodeTexSky'); sky.sky_type='NISHITA'
    if hasattr(sky,'sun_elevation'): sky.sun_elevation=math.radians(22); sky.sun_rotation=math.radians(40)
    wt.links.new(sky.outputs[0],wbg.inputs[0])
except Exception as ex:
    print("SKY_FAIL",ex); wbg.inputs[0].default_value=(0.45,0.52,0.62,1)
wbg.inputs[1].default_value=0.45; wt.links.new(wbg.outputs[0],wout.inputs['Surface'])
sd=bpy.data.lights.new("sun",'SUN'); sd.energy=1.25; sd.angle=math.radians(1.5); sd.color=(1.0,0.95,0.86)
so=bpy.data.objects.new("sun",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(58),math.radians(6),math.radians(45))
# ---- zemin (toprak) ----
bpy.ops.mesh.primitive_plane_add(size=14,location=(0,0,0)); gp=bpy.context.view_layer.objects.active
gm=bpy.data.materials.new("ground"); gm.use_nodes=True; gnt=gm.node_tree; gpb=gnt.nodes.get("Principled BSDF")
gpb.inputs['Base Color'].default_value=(0.10,0.09,0.07,1); gpb.inputs['Roughness'].default_value=1.0
gnz=gnt.nodes.new('ShaderNodeTexNoise'); gnz.inputs['Scale'].default_value=12.0
gbump=gnt.nodes.new('ShaderNodeBump'); gbump.inputs['Strength'].default_value=0.3
gnt.links.new(gnz.outputs['Fac'],gbump.inputs['Height']); gnt.links.new(gbump.outputs['Normal'],gpb.inputs['Normal'])
gp.data.materials.append(gm)
# ---- kamera + render ----
bb=[mesh.matrix_world@Vector(c) for c in mesh.bound_box]
ctr=sum(bb,Vector())/8; size=max((max(v[i] for v in bb)-min(v[i] for v in bb)) for i in range(3))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co; cam.lens=90
tg=bpy.data.objects.new("t",None); bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=SAMP; sc.cycles.use_denoising=True
sc.render.resolution_x=720; sc.render.resolution_y=560
# pozlama/tonemap (asiri parlakligi engelle)
try:
    looks=[x.name for x in bpy.types.ColorManagedViewSettings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform='AgX' if 'AgX' in looks else 'Filmic'
except Exception as ex: print("VT_FAIL",ex)
sc.view_settings.exposure=-0.6; sc.view_settings.gamma=1.0
allshots={"hero":(40,9,1.0,ctr+Vector((0,0,-0.02))),"head":(54,4,0.46,Vector((0,0.78,0.80))),"side":(90,6,1.0,ctr+Vector((0,0,-0.02)))}
d=size*1.95
for nm in SHOTS.split(","):
    az,el,fac,tgt=allshots[nm]; a=math.radians(az); e=math.radians(el)
    co.location=(ctr.x+d*fac*math.sin(a)*math.cos(e),ctr.y-d*fac*math.cos(a)*math.cos(e),ctr.z+d*fac*math.sin(e))
    tg.location=tgt; sc.render.filepath=os.path.join(outdir,nm+".png"); bpy.ops.render.render(write_still=True); print("RENDERED",nm)
print("PHOTOREAL_DONE")
