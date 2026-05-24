#!/usr/bin/env python3
"""Clay detay render: form gosterimi icin yumusak gri kil + 3-nokta isik.
kafa yakin + yan + 3/4. blender --background <mesh.blend> --python clay_detail_render.py -- <outdir> [samples]"""
import bpy, math, sys, os
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
outdir=argv[0]; samples=int(argv[1]) if len(argv)>1 else 48
os.makedirs(outdir,exist_ok=True)
mesh=None
for o in bpy.data.objects:
    if o.type=='ARMATURE': o.hide_render=True; o.hide_viewport=True
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
me=mesh.data
for m in list(me.materials): me.materials.clear()
clay=bpy.data.materials.new("clay"); clay.use_nodes=True
b=clay.node_tree.nodes.get("Principled BSDF"); b.inputs['Base Color'].default_value=(0.45,0.43,0.41,1); b.inputs['Roughness'].default_value=0.62
me.materials.append(clay)
bpy.context.view_layer.objects.active=mesh; bpy.ops.object.shade_smooth()
bb=[mesh.matrix_world@Vector(c) for c in mesh.bound_box]
ctr=sum(bb,Vector())/8; size=max((max(v[i] for v in bb)-min(v[i] for v in bb)) for i in range(3))
bpy.ops.mesh.primitive_plane_add(size=12,location=(0,0,0)); gp=bpy.context.view_layer.objects.active
gm=bpy.data.materials.new("g"); gm.use_nodes=True; gm.node_tree.nodes.get("Principled BSDF").inputs['Base Color'].default_value=(0.12,0.12,0.13,1); gp.data.materials.append(gm)
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.30,0.34,0.40,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.5
sd=bpy.data.lights.new("key",'SUN'); sd.energy=3.5; sd.angle=math.radians(2); sd.color=(1,0.97,0.92)
so=bpy.data.objects.new("key",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(50),math.radians(10),math.radians(50))
rd=bpy.data.lights.new("rim",'SUN'); rd.energy=2.6; rd.color=(0.72,0.8,1.0)
ro=bpy.data.objects.new("rim",rd); bpy.context.collection.objects.link(ro); ro.rotation_euler=(math.radians(65),0,math.radians(215))
fd=bpy.data.lights.new("fill",'AREA'); fd.energy=70; fd.size=5; fo=bpy.data.objects.new("fill",fd); fo.location=(-2.6,-1.6,1.3); bpy.context.collection.objects.link(fo)
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co; cam.lens=90
tg=bpy.data.objects.new("t",None); bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=samples; sc.cycles.use_denoising=True
sc.render.resolution_x=820; sc.render.resolution_y=640
d=size*1.95
for nm,az,el,fac,tgt in [("head",52,3,0.42,Vector((0,0.76,0.80))),("side",90,6,1.0,ctr+Vector((0,0,-0.02))),("hero",40,9,1.0,ctr+Vector((0,0,-0.02)))]:
    a=math.radians(az); e=math.radians(el)
    co.location=(ctr.x+d*fac*math.sin(a)*math.cos(e),ctr.y-d*fac*math.cos(a)*math.cos(e),ctr.z+d*fac*math.sin(e))
    tg.location=tgt; sc.render.filepath=os.path.join(outdir,nm+".png"); bpy.ops.render.render(write_still=True); print("RENDERED",nm)
print("CLAY_DONE")
