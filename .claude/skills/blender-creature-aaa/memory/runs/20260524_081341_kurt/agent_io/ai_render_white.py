#!/usr/bin/env python3
"""TripoSR mesh -> import + auto-orient + BEYAZ kil materyali + render (geometri degerlendirme).
blender --background --factory-startup --python ai_render_white.py -- <mesh.obj> <out.blend> <renderdir> [samples]
"""
import bpy, math, sys, os
import numpy as np
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
mesh_path,outblend,rdir=argv[0],argv[1],argv[2]
samples=int(argv[3]) if len(argv)>3 else 48
os.makedirs(rdir,exist_ok=True)
for o in list(bpy.data.objects): bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.wm.obj_import(filepath=mesh_path)
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
mesh.name="creature_mesh"; bpy.context.view_layer.objects.active=mesh
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
me=mesh.data
co=np.empty(len(me.vertices)*3,dtype=np.float32); me.vertices.foreach_get("co",co); co=co.reshape(-1,3)
ext=co.max(0)-co.min(0); order=list(np.argsort(ext)); small,mid,lng=order
new=np.empty_like(co); new[:,0]=co[:,small]; new[:,1]=co[:,lng]; new[:,2]=-co[:,mid]
me.vertices.foreach_set("co",new.reshape(-1)); me.update()
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
def bbox():
    b=[mesh.matrix_world@Vector(c) for c in mesh.bound_box]
    return Vector((min(v.x for v in b),min(v.y for v in b),min(v.z for v in b))),Vector((max(v.x for v in b),max(v.y for v in b),max(v.z for v in b)))
mn,mx=bbox(); size=mx-mn
sf=1.2/max(size.x,size.y,size.z); mesh.scale=(sf,sf,sf); bpy.ops.object.transform_apply(scale=True)
mn,mx=bbox(); ctr=(mn+mx)/2; mesh.location=(-ctr.x,-ctr.y,-mn.z); bpy.ops.object.transform_apply(location=True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.shade_smooth()
import bmesh
bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm,faces=bm.faces); tris=len(bm.faces); bm.free()
# BEYAZ kil
for m in list(me.materials): me.materials.clear()
mat=bpy.data.materials.new("clay"); mat.use_nodes=True
b=mat.node_tree.nodes.get("Principled BSDF"); b.inputs['Base Color'].default_value=(0.8,0.8,0.8,1); b.inputs['Roughness'].default_value=0.5
me.materials.append(mat)
print("WHITE tris",tris,"verts",len(me.vertices))
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))
bpy.ops.mesh.primitive_plane_add(size=10); gp=bpy.context.view_layer.objects.active
gm=bpy.data.materials.new("g"); gm.use_nodes=True; gm.node_tree.nodes.get("Principled BSDF").inputs['Base Color'].default_value=(0.18,0.18,0.2,1); gp.data.materials.append(gm)
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.35,0.39,0.45,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.8
sd=bpy.data.lights.new("k",'SUN'); sd.energy=3.2; so=bpy.data.objects.new("k",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(52),math.radians(8),math.radians(46))
rd=bpy.data.lights.new("r",'SUN'); rd.energy=2.2; rd.color=(0.7,0.8,1); ro=bpy.data.objects.new("r",rd); bpy.context.collection.objects.link(ro); ro.rotation_euler=(math.radians(64),0,math.radians(215))
mn,mx=bbox(); ctr=(mn+mx)/2; size=max((mx-mn)[i] for i in range(3))
cam=bpy.data.cameras.new("c"); co2=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co2); bpy.context.scene.camera=co2; cam.lens=72
tg=bpy.data.objects.new("t",None); tg.location=ctr; bpy.context.collection.objects.link(tg); co2.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=samples; sc.cycles.use_denoising=True
sc.render.resolution_x=800; sc.render.resolution_y=640
d=size*1.85
for nm,az,el,fac in [("side",90,6,1.0),("front34",38,10,1.0),("head",58,7,0.5),("back34",140,10,1.0)]:
    a=math.radians(az); e=math.radians(el)
    co2.location=(ctr.x+d*fac*math.sin(a)*math.cos(e),ctr.y-d*fac*math.cos(a)*math.cos(e),ctr.z+d*fac*math.sin(e))
    tg.location=ctr if nm!="head" else Vector((ctr.x, mx.y-size*0.16, ctr.z+size*0.18))
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True); print("RENDERED",nm)
print("WHITE_DONE")
