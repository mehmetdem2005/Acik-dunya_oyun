#!/usr/bin/env python3
"""Fare rig gelistirme (skill mantigi): omurga/kaburga + uzun kuyruk + burun kemigi ekle,
KULAKLARI birebir koru (agirliklari kaydet/geri yukle), sonra re-skin.
blender --background <clean.blend> --python mouse_rig_enhance.py -- <out.blend> <out.glb> <renderdir>
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:]
outblend,outglb,rdir=argv[0],argv[1],argv[2]; os.makedirs(rdir,exist_ok=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh=max((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
me=mesh.data
Marm=arm.matrix_world; Minv=Marm.inverted(); Mmesh=mesh.matrix_world
def wh(n): return Marm @ arm.data.bones[n].head_local
def wt(n): return Marm @ arm.data.bones[n].tail_local
EAR_BONES=['bone_6','bone_7']

# ---------- 1) KULAK agirliklarini kaydet (bone_6/7 etkili vert'ler) ----------
ear_vg_idx={vg.name:vg.index for vg in mesh.vertex_groups}
ear_saved={}  # vidx -> {bonename:weight}
ear_set=set()
for v in me.vertices:
    we={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
    if we.get('bone_6',0)>0.08 or we.get('bone_7',0)>0.08:
        ear_saved[v.index]=we; ear_set.add(v.index)
print("EAR_VERTS", len(ear_set))

# ---------- 2) kuyruk polyline (world) ----------
tail_names=['bone_21','Tail_0','Tail_1','Tail_2','Tail_3','bone_26']
tail_pts=[wh('bone_21')]+[wt(n) for n in tail_names if n in arm.data.bones]
s0=wh('Spine_0')

# ---------- 3) EDIT: yeni kemikler ----------
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
eb=arm.data.edit_bones
def addbone(name,hw,tw,parent):
    b=eb.new(name); b.head=Minv@Vector(hw); b.tail=Minv@Vector(tw); b.use_deform=True
    if parent and parent in eb: b.parent=eb[parent]
    return b
# kuyruk: eskileri sil, 12-segment ince zincir
pts=[Vector(p) for p in tail_pts]; seg=[(pts[i+1]-pts[i]).length for i in range(len(pts)-1)]; tot=sum(seg)
def samp(d):
    acc=0
    for i in range(len(pts)-1):
        if acc+seg[i]>=d or i==len(pts)-2:
            t=(d-acc)/seg[i] if seg[i]>1e-9 else 0; return pts[i].lerp(pts[i+1],min(max(t,0),1))
        acc+=seg[i]
    return pts[-1]
NT=12; tp=[samp(tot*k/NT) for k in range(NT+1)]
for n in tail_names:
    if n in eb: eb.remove(eb[n])
prev='Root'
for i in range(NT): addbone(f"Tail_{i:02d}",tp[i],tp[i+1],prev); prev=f"Tail_{i:02d}"
# omurga: Root ile Spine_0 arasi 2 kemik (arka sirt/kaburga-bel)
sA_h=Vector((s0.x,s0.y+0.20,s0.z-0.01)); sA_t=Vector((s0.x,s0.y+0.10,s0.z-0.005))
addbone("Spine_A",sA_h,sA_t,"Root")
addbone("Spine_B",sA_t,Vector(s0),"Spine_A")
eb['Spine_0'].parent=eb['Spine_B']
# burun: snout ucu (Head_2 cocugu)
addbone("Nose",Vector((0,-0.42,0.21)),Vector((0,-0.50,0.19)),"Head_2")
NEW_BONES=[f"Tail_{i:02d}" for i in range(NT)]+["Spine_A","Spine_B","Nose"]
bpy.ops.object.mode_set(mode='OBJECT')
print("YENI_KEMIK", len(NEW_BONES), "toplam", len(arm.data.bones))

# ---------- 4) re-skin: bone heat (temiz mesh) ----------
for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active=arm
heat_ok=True
try:
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
except Exception as e:
    print("HEAT_EXC",e); heat_ok=False
# orphan kontrol
orph=sum(1 for v in me.vertices if not v.groups)
print("HEAT orphans", orph)
if orph>50 or not heat_ok:
    print("PROXIMITY fallback")
    # proximity skin: tum deform kemiklere mesafe gaussian top4
    segs=[]
    for b in arm.data.bones:
        if b.use_deform: segs.append((b.name, np.array(Marm@b.head_local), np.array(Marm@b.tail_local)))
    names=[s[0] for s in segs]; H=np.array([s[1] for s in segs]); T=np.array([s[2] for s in segs]); AB=T-H; AB2=(AB*AB).sum(1)+1e-9
    V=np.array([Mmesh@v.co for v in me.vertices])
    D=np.empty((len(V),len(segs)))
    for j in range(len(segs)):
        ap=V-H[j]; t=np.clip((ap@AB[j])/AB2[j],0,1); proj=H[j]+np.outer(t,AB[j]); D[:,j]=np.linalg.norm(V-proj,axis=1)
    W=np.exp(-(D/0.05)**2); idx=np.argsort(-W,axis=1); mask=np.zeros_like(W,bool)
    rows=np.arange(len(V))[:,None]; mask[rows,idx[:,:4]]=True; W=np.where(mask,W,0)
    rs=W.sum(1); empty=rs<1e-9
    if empty.any(): W[np.where(empty)[0],np.argmin(D[empty],1)]=1; rs=W.sum(1)
    W/=rs[:,None]
    for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
    gs={n:mesh.vertex_groups.new(name=n) for n in names}
    for j,n in enumerate(names):
        col=W[:,j]; nz=np.where(col>1e-4)[0]
        for vi in nz: gs[n].add([int(vi)],float(col[vi]),'REPLACE')
# armature modifier garanti
if not any(m.type=='ARMATURE' for m in mesh.modifiers):
    mesh.modifiers.new("Armature",'ARMATURE').object=arm

# ---------- 5) KULAK agirliklarini geri yukle ----------
have={vg.name for vg in mesh.vertex_groups}
for vi,we in ear_saved.items():
    for vg in mesh.vertex_groups: vg.remove([vi])
    for bn,w in we.items():
        if bn not in have:
            mesh.vertex_groups.new(name=bn); have.add(bn)
        mesh.vertex_groups[bn].add([vi],w,'REPLACE')
print("KULAK_RESTORE_DONE", len(ear_saved))
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))

# ---------- 6) POZ TESTI: kuyruk kivir + omurga buk + burun + KULAK oynat ----------
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE')
def rot(n,rx,ry,rz):
    pb=arm.pose.bones.get(n)
    if pb: pb.rotation_mode='XYZ'; pb.rotation_euler=(math.radians(rx),math.radians(ry),math.radians(rz))
for i in range(NT): rot(f"Tail_{i:02d}", 0,0, 14)         # kuyruk yana kivir
rot("Spine_A",6,0,0); rot("Spine_B",6,0,0)                 # sirt buk
rot("Nose",10,0,0)
rot("bone_6",0,0,25); rot("bone_7",0,0,-25)                # KULAKLARI oynat (kontrol)
bpy.ops.object.mode_set(mode='OBJECT')
for o in bpy.data.objects:
    if o.type=='ARMATURE': o.hide_render=True
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.4,0.44,0.5,1); w.node_tree.nodes["Background"].inputs[1].default_value=1.0
sd=bpy.data.lights.new("k",'SUN'); sd.energy=3.2; so=bpy.data.objects.new("k",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(50),math.radians(10),math.radians(45))
bb=[Mmesh@Vector(c) for c in mesh.bound_box]; mn=Vector((min(v.x for v in bb),min(v.y for v in bb),min(v.z for v in bb))); mx=Vector((max(v.x for v in bb),max(v.y for v in bb),max(v.z for v in bb)))
ctr=(mn+mx)/2; size=max((mx-mn)[i] for i in range(3))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co; cam.lens=55
tg=bpy.data.objects.new("t",None); tg.location=ctr; bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=720; sc.render.resolution_y=600
d=size*2.1
for nm,az,el in [("posed_side",92,12),("posed_back34",140,18),("posed_head",55,16)]:
    a=math.radians(az);e=math.radians(el); fac=0.6 if nm=="posed_head" else 1.0
    co.location=(ctr.x+d*fac*math.sin(a)*math.cos(e),ctr.y-d*fac*math.cos(a)*math.cos(e),ctr.z+d*fac*math.sin(e))
    tg.location=ctr if nm!="posed_head" else Vector((ctr.x,mn.y+size*0.12,ctr.z+size*0.18))
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True)
# rest-pose export icin pozu sifirla
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE'); bpy.ops.pose.select_all(action='SELECT'); bpy.ops.pose.transforms_clear(); bpy.ops.object.mode_set(mode='OBJECT')
for o in bpy.data.objects:
    if o.type=='ARMATURE': o.hide_render=False
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.gltf(filepath=outglb, export_format='GLB', use_selection=True, export_apply=True, export_skins=True, export_animations=False, export_yup=True)
print("ENHANCE_DONE", outglb, os.path.getsize(outglb))
