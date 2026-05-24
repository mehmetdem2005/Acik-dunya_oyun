#!/usr/bin/env python3
"""Yeni fare mesh'ini temizle + Blender'a al + oryantasyon/landmark tespiti + 4 acidan render.
blender --background --python mouse_new_clean.py -- <in.glb> <out.blend> <renderdir>
"""
import bpy, sys, os, math
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:]
inglb,outblend,rdir=argv[0],argv[1],argv[2]; os.makedirs(rdir,exist_ok=True)

# temiz sahne
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=inglb)
meshes=[o for o in bpy.data.objects if o.type=='MESH']
mesh=max(meshes,key=lambda o:len(o.data.vertices))
mesh.name="Mouse"; mesh.data.name="MouseMesh"
# parent/transform temizle -> apply
bpy.ops.object.select_all(action='DESELECT')
mesh.select_set(True); bpy.context.view_layer.objects.active=mesh
mesh.parent=None
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
# fazlalik objeleri sil
for o in list(bpy.data.objects):
    if o is not mesh: bpy.data.objects.remove(o,do_unlink=True)

me=mesh.data; M=mesh.matrix_world
V=[M@v.co for v in me.vertices]
xs=[p.x for p in V]; ys=[p.y for p in V]; zs=[p.z for p in V]
mn=Vector((min(xs),min(ys),min(zs))); mx=Vector((max(xs),max(ys),max(zs)))
dim=mx-mn
print("BBOX_MIN",[round(c,4) for c in mn]); print("BBOX_MAX",[round(c,4) for c in mx])
print("DIMS",[round(c,4) for c in dim])
# en uzun eksen = govde+kuyruk
longest=max(range(3),key=lambda i:dim[i]); axn=['X','Y','Z'][longest]
print("LONGEST_AXIS",axn,round(dim[longest],4))
# kesit profili: en uzun eksende 24 dilim, her dilimde diger 2 eksen yayilimini olc
NB=24; lo=mn[longest]; hi=mx[longest]; step=(hi-lo)/NB
oth=[i for i in range(3) if i!=longest]
prof=[]
for k in range(NB):
    a=lo+k*step; b=a+step
    sub=[p for p in V if a<=p[longest]<b]
    if sub:
        w0=max(s[oth[0]] for s in sub)-min(s[oth[0]] for s in sub)
        w1=max(s[oth[1]] for s in sub)-min(s[oth[1]] for s in sub)
        zc=sum(s[oth[1]] for s in sub)/len(sub)
        prof.append((round(a,3),round(b,3),len(sub),round(w0,3),round(w1,3)))
    else:
        prof.append((round(a,3),round(b,3),0,0,0))
print("=== CROSS-SECTION PROFILE (en uzun eksen boyunca: a,b,count,width_oth0,width_oth1) ===")
for row in prof: print("  ",row)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))

# ---- RENDER 4+ aci ----
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.42,0.46,0.52,1)
w.node_tree.nodes["Background"].inputs[1].default_value=1.0
sd=bpy.data.lights.new("k",'SUN'); sd.energy=3.3; so=bpy.data.objects.new("k",sd)
bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(55),math.radians(10),math.radians(45))
ctr=(mn+mx)/2; size=max(dim)
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co)
bpy.context.scene.camera=co; cam.lens=50
tg=bpy.data.objects.new("t",None); tg.location=ctr; bpy.context.collection.objects.link(tg)
co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=640; sc.render.resolution_y=560
d=size*2.2
views={"side_pX":(d,0,0.15),"side_nX":(-d,0,0.15),"front_pY":(0,d,0.15),"back_nY":(0,-d,0.15),
       "top":(0.01,0.01,d),"q34":(d*0.8,d*0.8,d*0.5)}
for nm,(ox,oy,oz) in views.items():
    co.location=(ctr.x+ox,ctr.y+oy,ctr.z+oz)
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True)
print("CLEAN_DONE verts",len(me.vertices))
