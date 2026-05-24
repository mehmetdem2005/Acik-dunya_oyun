#!/usr/bin/env python3
"""Fare rig v3b — CERRAHI: orijinal agirliklari KORU; COK-SEGMENTLI puruzsuz omurga (5),
kuyruk 12, burun. Sirt/kaburga verts'leri omurga zincirine yumusak (gaussian) dagitilir.
Bacaklar/kulaklar/govde-yan birebir orijinal kalir.
blender --background <clean.blend> --python mouse_rig_enhance3.py -- <out.blend> <out.glb> <renderdir>
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
orig=[{mesh.vertex_groups[g.group].name:g.weight for g in v.groups} for v in me.vertices]
Vw=[Mmesh@v.co for v in me.vertices]
tail_chain=[n for n in ['bone_21','Tail_0','Tail_1','Tail_2','Tail_3','bone_26'] if n in arm.data.bones]
tailgeo={n:(wh(n),wt(n)) for n in tail_chain}
s0=wh('Spine_0')   # ~ (-0.04,0.08,0.31)

# ---- EDIT: yeni kemikler ----
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT'); eb=arm.data.edit_bones
def addbone(name,hw,tw,parent):
    b=eb.new(name); b.head=Minv@Vector(hw); b.tail=Minv@Vector(tw); b.use_deform=True
    if parent and parent in eb: b.parent=eb[parent]
    return b
# COK-SEGMENTLI OMURGA: pelvis(Y~0.30) -> Spine_0(Y~0.08), 5 segment, Z~0.30 (sirt cizgisi)
NSP=5; y0=s0.y+0.22; y1=s0.y; zspine=s0.z
spine_names=[]; segs_spine=[]
prev='Root'
for i in range(NSP):
    ya=y0+(y1-y0)*i/NSP; yb=y0+(y1-y0)*(i+1)/NSP
    nm=f"SpineX_{i}"; addbone(nm,(s0.x,ya,zspine-0.005),(s0.x,yb,zspine),prev); prev=nm; spine_names.append(nm)
if 'Spine_0' in eb: eb['Spine_0'].parent=eb[spine_names[-1]]
# KUYRUK 12
pts=[Vector(tailgeo[tail_chain[0]][0])]+[Vector(tailgeo[n][1]) for n in tail_chain]
seg=[(pts[i+1]-pts[i]).length for i in range(len(pts)-1)]; tot=sum(seg)
def samp(d):
    acc=0
    for i in range(len(pts)-1):
        if acc+seg[i]>=d or i==len(pts)-2:
            t=(d-acc)/seg[i] if seg[i]>1e-9 else 0; return pts[i].lerp(pts[i+1],min(max(t,0),1))
        acc+=seg[i]
    return pts[-1]
NT=12; tp=[samp(tot*k/NT) for k in range(NT+1)]
for n in tail_chain:
    if n in eb: eb.remove(eb[n])
prev='Root'
tail_new=[]
for i in range(NT): nm=f"Tail_{i:02d}"; addbone(nm,tp[i],tp[i+1],prev); prev=nm; tail_new.append(nm)
# BURUN
addbone("Nose",Vector((0,-0.42,0.21)),Vector((0,-0.50,0.19)),"Head_2")
bpy.ops.object.mode_set(mode='OBJECT')
# omurga segment world geom (reweight icin)
spine_geo=[(n,np.array(wh(n)),np.array(wt(n))) for n in spine_names]

# ---- agirlik yeniden kur: KORU + remap (tail) + smooth spine ----
for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
allb={b.name for b in arm.data.bones}; groups={}
def G(n):
    if n not in groups: groups[n]=mesh.vertex_groups.new(name=n)
    return groups[n]
def segt(p,h,t):
    h=Vector(h);t=Vector(t);ab=t-h;L2=ab.dot(ab)+1e-9; return max(0,min(1,(Vector(p)-h).dot(ab)/L2))
def segdist(p,h,t):
    h=np.array(h);t=np.array(t);p=np.array(p);ab=t-h;L2=ab.dot(ab)+1e-9
    tt=max(0,min(1,(p-h).dot(ab)/L2)); proj=h+tt*ab; return np.linalg.norm(p-proj)
def ss(a,b,x):
    t=max(0,min(1,(x-a)/(b-a+1e-9))); return t*t*(3-2*t)
tail_set=set(tail_chain)
for vi,we in enumerate(orig):
    p=Vw[vi]; out={}
    for bn,w in we.items():
        if bn in tail_set:
            h,t=tailgeo[bn]; tt=segt(p,h,t); f=max(0,min(1,(tt-0.25)/0.5))
            seg_i=min(int(tt*NT),NT-1); a=tail_new[seg_i]
            out[a]=out.get(a,0)+w
        else:
            out[bn]=out.get(bn,0)+w
    # SMOOTH OMURGA: Root agirligini sirt bolgesinde omurga zincirine gaussian dagit
    if out.get('Root',0)>0:
        wz=p.z; wy=p.y
        back = ss(0.17,0.27,wz) * ss(s0.y+0.01,s0.y+0.05,wy) * ss(s0.y+0.30,s0.y+0.22,wy)
        if back>0.02:
            move=out['Root']*0.7*back; out['Root']-=move
            d=np.array([segdist(p,h,t) for _,h,t in spine_geo]); wsp=np.exp(-(d/0.05)**2)
            if wsp.sum()>1e-9:
                wsp/=wsp.sum()
                for k,(n,_,_) in enumerate(spine_geo): out[n]=out.get(n,0)+move*wsp[k]
    # BURUN
    if p.y<-0.40 and 0.13<p.z<0.30:
        nf=min(ss(-0.40,-0.49,p.y),0.85)
        if nf>0.02:
            taken=0
            for hb in ('Head_3','Head_2','Head_1'):
                if out.get(hb,0)>0: mv=out[hb]*nf; out[hb]-=mv; taken+=mv
            out['Nose']=out.get('Nose',0)+taken
    s=sum(out.values())
    if s<1e-9:
        out={(max(we,key=we.get) if we else 'Root'):1.0}; s=1.0
    for bn,w in out.items():
        if w>1e-5 and bn in allb: G(bn).add([vi],w/s,'REPLACE')
if not any(m.type=='ARMATURE' for m in mesh.modifiers): mesh.modifiers.new("Armature",'ARMATURE').object=arm
else: [m for m in mesh.modifiers if m.type=='ARMATURE'][0].object=arm
print("REBUILT vgroups",len(mesh.vertex_groups),"bones",len(arm.data.bones),"spineX",NSP)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))

# ---- VERIFY: guclu omurga bend + KUCUK bacak (gerilmesin) + pati zoom ----
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE')
def rot(n,rx=0,ry=0,rz=0):
    pb=arm.pose.bones.get(n)
    if pb: pb.rotation_mode='XYZ'; pb.rotation_euler=(math.radians(rx),math.radians(ry),math.radians(rz))
for n in spine_names: rot(n, rx=7)         # omurga kambur (her segment -> puruzsuz)
for i in range(NT): rot(f"Tail_{i:02d}", rz=12)
rot('Head_0',rz=10); rot('bone_6',rz=18); rot('bone_7',rz=-18)
bpy.ops.object.mode_set(mode='OBJECT')
arm.hide_render=True
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.42,0.46,0.52,1); w.node_tree.nodes["Background"].inputs[1].default_value=1.0
sd=bpy.data.lights.new("k",'SUN'); sd.energy=3.3; so=bpy.data.objects.new("k",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(50),math.radians(10),math.radians(45))
bb=[Mmesh@Vector(c) for c in mesh.bound_box]; mn=Vector((min(v.x for v in bb),min(v.y for v in bb),min(v.z for v in bb))); mx=Vector((max(v.x for v in bb),max(v.y for v in bb),max(v.z for v in bb)))
ctr=(mn+mx)/2; size=max((mx-mn)[i] for i in range(3))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co; cam.lens=55
tg=bpy.data.objects.new("t",None); tg.location=ctr; bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=700; sc.render.resolution_y=560
d=size*2.1
for nm,az,el in [("spine_side",92,10),("spine_top",30,55)]:
    a=math.radians(az);e=math.radians(el)
    co.location=(ctr.x+d*math.sin(a)*math.cos(e),ctr.y-d*math.cos(a)*math.cos(e),ctr.z+d*math.sin(e))
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True)
# rest + export
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE'); bpy.ops.pose.select_all(action='SELECT'); bpy.ops.pose.transforms_clear(); bpy.ops.object.mode_set(mode='OBJECT')
arm.hide_render=False
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.gltf(filepath=outglb, export_format='GLB', use_selection=True, export_apply=True, export_skins=True, export_animations=False, export_yup=True)
print("ENH3_DONE", os.path.getsize(outglb))
