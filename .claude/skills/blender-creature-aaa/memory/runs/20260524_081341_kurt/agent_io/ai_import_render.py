#!/usr/bin/env python3
"""TripoSR mesh.obj -> Blender import + align + render (vertex renk varsa kullan).
blender --background --factory-startup --python ai_import_render.py -- <mesh.obj> <out.blend> <renderdir> [samples]
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
mesh_path,outblend,rdir=argv[0],argv[1],argv[2]
samples=int(argv[3]) if len(argv)>3 else 40
os.makedirs(rdir,exist_ok=True)
for o in list(bpy.data.objects): bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.wm.obj_import(filepath=mesh_path)
mesh=max((o for o in bpy.context.scene.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
mesh.name="creature_mesh"; bpy.context.view_layer.objects.active=mesh
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True)
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
def bbox():
    b=[mesh.matrix_world@Vector(c) for c in mesh.bound_box]
    return Vector((min(v.x for v in b),min(v.y for v in b),min(v.z for v in b))),Vector((max(v.x for v in b),max(v.y for v in b),max(v.z for v in b)))
# AUTO-ORIENT: vertex koordinat permutasyonu — en uzun eksen->Y(boy), orta->Z(yukari), kisa->X(en)
me=mesh.data
import numpy as np
co=np.empty(len(me.vertices)*3,dtype=np.float32); me.vertices.foreach_get("co",co); co=co.reshape(-1,3)
ext=co.max(0)-co.min(0)
order=list(np.argsort(ext))  # [kisa, orta, uzun]
small,mid,lng=order[0],order[1],order[2]
new=np.empty_like(co)
new[:,0]=co[:,small]    # X = en
new[:,1]=co[:,lng]      # Y = boy
new[:,2]=-co[:,mid]     # Z = yukari (isaret ters cevrildi: bacaklar asagi)
me.vertices.foreach_set("co",new.reshape(-1)); me.update()
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
mn,mx=bbox(); size=mx-mn
# olcek ~1.2m (en uzun eksen)
sf=1.2/max(size.x,size.y,size.z); mesh.scale=(sf,sf,sf); bpy.ops.object.transform_apply(scale=True)
mn,mx=bbox(); ctr=(mn+mx)/2
mesh.location=(-ctr.x,-ctr.y,-mn.z); bpy.ops.object.transform_apply(location=True)
# temizle
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0002); bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT'); bpy.ops.object.shade_smooth()
# vertex renk var mi?
has_col=len(mesh.data.color_attributes)>0
print("VCOL" if has_col else "NOVCOL", "verts", len(mesh.data.vertices))
mat=bpy.data.materials.new("m"); mat.use_nodes=True; nt=mat.node_tree
bsdf=nt.nodes.get("Principled BSDF"); bsdf.inputs['Roughness'].default_value=0.7
if has_col:
    at=nt.nodes.new('ShaderNodeAttribute'); at.attribute_type='GEOMETRY'; at.attribute_name=mesh.data.color_attributes[0].name
    nt.links.new(at.outputs['Color'],bsdf.inputs['Base Color'])
else:
    bsdf.inputs['Base Color'].default_value=(0.4,0.38,0.36,1)
for m in list(mesh.data.materials): mesh.data.materials.clear()
mesh.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))
# render
bpy.ops.mesh.primitive_plane_add(size=10); gp=bpy.context.view_layer.objects.active
gm=bpy.data.materials.new("g"); gm.use_nodes=True; gm.node_tree.nodes.get("Principled BSDF").inputs['Base Color'].default_value=(0.12,0.12,0.12,1); gp.data.materials.append(gm)
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.36,0.4,0.46,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.7
sd=bpy.data.lights.new("k",'SUN'); sd.energy=3.0; so=bpy.data.objects.new("k",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(52),math.radians(8),math.radians(46))
rd=bpy.data.lights.new("r",'SUN'); rd.energy=2.0; rd.color=(0.7,0.8,1); ro=bpy.data.objects.new("r",rd); bpy.context.collection.objects.link(ro); ro.rotation_euler=(math.radians(64),0,math.radians(215))
mn,mx=bbox(); ctr=(mn+mx)/2; size=max((mx-mn)[i] for i in range(3))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co; cam.lens=70
tg=bpy.data.objects.new("t",None); tg.location=ctr; bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=samples; sc.cycles.use_denoising=True
sc.render.resolution_x=720; sc.render.resolution_y=600
d=size*1.9
for nm,az,el in [("side",90,6),("front34",40,10),("head",55,8)]:
    a=math.radians(az); e=math.radians(el); fac=0.55 if nm=="head" else 1.0
    co.location=(ctr.x+d*fac*math.sin(a)*math.cos(e),ctr.y-d*fac*math.cos(a)*math.cos(e),ctr.z+d*fac*math.sin(e))
    tg.location=ctr if nm!="head" else Vector((ctr.x, mx.y-size*0.18, mx.z-size*0.12))
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True); print("RENDERED",nm)
print("AI_RENDER_DONE")
