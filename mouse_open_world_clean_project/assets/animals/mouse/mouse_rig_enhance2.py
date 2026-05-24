#!/usr/bin/env python3
"""Fare rig gelistirme v2 — CERRAHI: orijinal Tripo agirliklarini KORU, sadece yeni
kemikler (kuyruk 12-segment, omurga A/B, burun) icin parent bolgeden agirlik aktar.
Bacaklar/kulaklar/govde orijinal kalir -> deformasyon bozulmaz.
blender --background <clean.blend> --python mouse_rig_enhance2.py -- <out.blend> <out.glb> <renderdir>
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:]
outblend,outglb,rdir=argv[0],argv[1],argv[2]; os.makedirs(rdir,exist_ok=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
mesh=max((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
me=mesh.data; Marm=arm.matrix_world; Minv=Marm.inverted(); Mmesh=mesh.matrix_world
def wh(n): return Marm@arm.data.bones[n].head_local
def wt(n): return Marm@arm.data.bones[n].tail_local

# ---------- 1) ORIJINAL agirliklari + vert dunya konumlarini kaydet ----------
orig=[None]*len(me.vertices)
for v in me.vertices:
    orig[v.index]={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
Vw=[Mmesh@v.co for v in me.vertices]
# kuyruk zinciri (eski) — world head/tail
tail_chain=['bone_21','Tail_0','Tail_1','Tail_2','Tail_3','bone_26']
tail_chain=[n for n in tail_chain if n in arm.data.bones]
tailgeo={n:(wh(n),wt(n)) for n in tail_chain}
s0=wh('Spine_0')

# ---------- 2) EDIT: yeni kemikler ----------
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
eb=arm.data.edit_bones
def addbone(name,hw,tw,parent):
    b=eb.new(name); b.head=Minv@Vector(hw); b.tail=Minv@Vector(tw); b.use_deform=True
    if parent: b.parent=eb[parent] if parent in eb else None
    return b
# kuyruk: her eski kemigi 2'ye bol -> 12 segment
tail_sub={}   # eski_kemik -> [(yeni_a, t0,t1),(yeni_b,...)]
idx=0; prev=None
for old in tail_chain:
    h,t=tailgeo[old]; mid=(Vector(h)+Vector(t))*0.5
    na=f"Tail_{idx:02d}"; idx+=1; nb=f"Tail_{idx:02d}"; idx+=1
    par = prev if prev else (arm.data.bones[old].parent.name if arm.data.bones[old].parent else 'Root')
    addbone(na,h,mid,par); addbone(nb,mid,t,na)
    tail_sub[old]=[(na,0.0,0.5),(nb,0.5,1.0)]; prev=nb
# eski kuyruk kemiklerini sil
for old in tail_chain:
    if old in eb: eb.remove(eb[old])
# omurga A/B (Root ile Spine_0 arasi, arka sirt)
sA_h=Vector((s0.x,s0.y+0.20,s0.z-0.01)); sA_t=Vector((s0.x,s0.y+0.10,s0.z-0.005))
addbone("Spine_A",sA_h,sA_t,"Root"); addbone("Spine_B",sA_t,Vector(s0),"Spine_A")
if 'Spine_0' in eb: eb['Spine_0'].parent=eb['Spine_B']
# burun
addbone("Nose",Vector((0,-0.42,0.21)),Vector((0,-0.50,0.19)),"Head_2")
bpy.ops.object.mode_set(mode='OBJECT')

# ---------- 3) Agirliklari yeniden kur (KORU + remap) ----------
for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
allbones={b.name for b in arm.data.bones}
groups={}
def G(n):
    if n not in groups: groups[n]=mesh.vertex_groups.new(name=n)
    return groups[n]
def segt(p, hw, tw):
    h=Vector(hw); t=Vector(tw); ab=t-h; L2=ab.dot(ab)+1e-9
    return max(0.0,min(1.0,(Vector(p)-h).dot(ab)/L2))
SA_h,SA_t=sA_h,sA_t; SB_h,SB_t=sA_t,Vector(s0)
nose_h=Vector((0,-0.42,0.21)); nose_t=Vector((0,-0.50,0.19))
def ss(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a+1e-9))); return t*t*(3-2*t)
for vi,we in enumerate(orig):
    p=Vw[vi]; out={}
    for bn,w in we.items():
        if bn in tail_sub:               # kuyruk -> 2 sub-bone'a t ile bol
            h,t=tailgeo[bn]; tt=segt(p,h,t); f=max(0.0,min(1.0,(tt-0.25)/0.5))
            a,b=tail_sub[bn][0][0],tail_sub[bn][1][0]
            out[a]=out.get(a,0)+w*(1-f); out[b]=out.get(b,0)+w*f
        else:
            out[bn]=out.get(bn,0)+w
    # OMURGA: Root agirligini arka-sirt bolgesinde Spine_A/B'ye kismi aktar
    if 'Root' in out and out['Root']>0:
        wy=p.y; wz=p.z
        back = ss(0.16,0.26,wz) * ( ss(s0.y+0.02, s0.y+0.06, wy) )  # z>0.16 (bacak ustu) ve y>s0 (arka)
        back = back * ss(s0.y+0.34, s0.y+0.24, wy)                   # cok arka pelvis ucunu disla
        if back>0.02:
            move=out['Root']*0.6*back
            out['Root']-=move
            # y'ye gore A(arka) / B(on) dagit
            fb=ss(s0.y+0.06, s0.y+0.18, wy)   # 0=B(on), 1=A(arka)
            out['Spine_A']=out.get('Spine_A',0)+move*fb
            out['Spine_B']=out.get('Spine_B',0)+move*(1-fb)
    # BURUN: snout ucu verts'te kafa agirligindan Nose'a aktar
    if p.y<-0.40 and 0.13<p.z<0.30:
        nf=ss(-0.40,-0.49,p.y) * ss(0.30,0.26,p.z) if p.z>0.26 else ss(-0.40,-0.49,p.y)
        nf=min(nf,0.85)
        if nf>0.02:
            taken=0
            for hb in ('Head_3','Head_2','Head_1'):
                if hb in out and out[hb]>0:
                    mv=out[hb]*nf; out[hb]-=mv; taken+=mv
            out['Nose']=out.get('Nose',0)+taken
    # normalize + ata
    s=sum(out.values())
    if s<1e-9: out={ min(we,key=we.get) if we else 'Root': 1.0} if we else {'Root':1.0}; s=1.0
    for bn,w in out.items():
        if w>1e-5 and bn in allbones: G(bn).add([vi], w/s, 'REPLACE')
if not any(m.type=='ARMATURE' for m in mesh.modifiers):
    mesh.modifiers.new("Armature",'ARMATURE').object=arm
else:
    [m for m in mesh.modifiers if m.type=='ARMATURE'][0].object=arm
print("REBUILT vgroups", len(mesh.vertex_groups), "bones", len(arm.data.bones))
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))

# ---------- 4) POZ TESTI: bacak + kuyruk + omurga + burun + kulak ----------
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE')
def rot(n,rx,ry,rz):
    pb=arm.pose.bones.get(n)
    if pb: pb.rotation_mode='XYZ'; pb.rotation_euler=(math.radians(rx),math.radians(ry),math.radians(rz))
for i in range(12): rot(f"Tail_{i:02d}",0,0,13)
rot("Spine_A",7,0,0); rot("Spine_B",7,0,0)
rot("0_Left_Limb_1",35,0,0); rot("1_Left_Limb_1",30,0,0)   # BACAK buk (kontrol!)
rot("bone_6",0,0,22); rot("bone_7",0,0,-22)                 # kulak
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
for nm,az,el in [("posed_side",92,12),("posed_front34",42,16)]:
    a=math.radians(az);e=math.radians(el)
    co.location=(ctr.x+d*math.sin(a)*math.cos(e),ctr.y-d*math.cos(a)*math.cos(e),ctr.z+d*math.sin(e))
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True)
# rest pose'a don + export
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE'); bpy.ops.pose.select_all(action='SELECT'); bpy.ops.pose.transforms_clear(); bpy.ops.object.mode_set(mode='OBJECT')
for o in bpy.data.objects:
    if o.type=='ARMATURE': o.hide_render=False
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.gltf(filepath=outglb, export_format='GLB', use_selection=True, export_apply=True, export_skins=True, export_animations=False, export_yup=True)
print("ENHANCE2_DONE", os.path.getsize(outglb))
