#!/usr/bin/env python3
"""Yeni fare mesh'ini SIFIRDAN rigle: landmark tespiti -> iskelet (5 omurga, 12 kuyruk, 4x2 bacak,
bas+kulak+burun) -> proximity skinning (gaussian, top-4) -> skill smooth_weights + cap4 + normalize.
Test poz + verify render + rest-poz rigged glb.
blender --background --python mouse_new_rig.py -- <clean.blend> <out.blend> <out.glb> <renderdir>
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:]
inblend,outblend,outglb,rdir=argv[0],argv[1],argv[2],argv[3]; os.makedirs(rdir,exist_ok=True)
SKILL="/home/user/Acik-dunya_oyun/.claude/skills/blender-creature-aaa/scripts/production/build_skinning.py"

bpy.ops.wm.open_mainfile(filepath=inblend)
mesh=max((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
me=mesh.data; M=mesh.matrix_world
co=np.array([(M@v.co)[:] for v in me.vertices],dtype=np.float64)
X,Y,Z=co[:,0],co[:,1],co[:,2]
minY,maxY,minZ,maxZ=Y.min(),Y.max(),Z.min(),Z.max()
print("BBOX Y",round(minY,3),round(maxY,3),"Z",round(minZ,3),round(maxZ,3))

def core_z(y,hw=0.03,q=0.62):
    m=(Y>=y-hw)&(Y<y+hw)
    if m.sum()<5: return (minZ+maxZ)/2
    return float(np.quantile(Z[m],q))
def width_at(y,hw=0.02):
    m=(Y>=y-hw)&(Y<y+hw)
    if m.sum()<3: return 0.0
    return float(X[m].max()-X[m].min())

# --- LANDMARKS ---
nose_tip=co[np.argmin(Y)]                                  # en on (-Y)
# kuyruk dibi: +Y'de govdenin daraldigi yer (X-genislik < 0.20)
tailbaseY=maxY-0.02
for y in np.arange(0.0,maxY,0.02):
    if width_at(y)<0.20: tailbaseY=float(y); break
# omurga uc Y'leri: pelvis (kuyruk dibinin biraz onu) -> boyun
hipY=tailbaseY-0.04
neckY=minY+0.20                                            # boyun ~ kafadan sonra
print("nose_tip",[round(c,3) for c in nose_tip],"tailbaseY",round(tailbaseY,3),"hipY",round(hipY,3),"neckY",round(neckY,3))

# kuyruk izi: tailbase'den uca Y-binleri centroid (X,Z)
tpath=[]
b=tailbaseY
while b<maxY+0.001:
    m=(Y>=b)&(Y<b+0.025)
    if m.sum()>=2: tpath.append(Vector((float(X[m].mean()),float((b+0.0125)),float(Z[m].mean()))))
    b+=0.025
if len(tpath)<3:  # fallback duz
    tpath=[Vector((0,tailbaseY+ (maxY-tailbaseY)*k/6, core_z(tailbaseY,q=0.5))) for k in range(7)]
# arc-length resample 12 segment (13 nokta)
def resample(pts,nseg):
    seg=[(pts[i+1]-pts[i]).length for i in range(len(pts)-1)]; tot=sum(seg) or 1e-6
    out=[pts[0]]
    for k in range(1,nseg+1):
        d=tot*k/nseg; acc=0; p=pts[-1]
        for i in range(len(pts)-1):
            if acc+seg[i]>=d or i==len(pts)-2:
                t=(d-acc)/seg[i] if seg[i]>1e-9 else 0; p=pts[i].lerp(pts[i+1],min(max(t,0),1)); break
            acc+=seg[i]
        out.append(p)
    return out
NT=12; tp=resample(tpath,NT)
print("tail pts",len(tp),"tip",[round(c,3) for c in tp[-1]])

# bacak ayak tespiti: en alt %16 bant -> 4 grup
band=Z<(minZ+0.16*(maxZ-minZ))
def foot(front,left):
    m=band & ((Y<0) if front else (Y>=0)) & ((X>0) if left else (X<0))
    if m.sum()<3: return None
    return Vector((float(np.median(X[m])),float(np.median(Y[m])),float(Z[m].min()+0.01)))
feet={'FL':foot(True,True),'FR':foot(True,False),'RL':foot(False,True),'RR':foot(False,False)}
for k,v in feet.items(): print("foot",k,[round(c,3) for c in v] if v else None)

# kulak ucu: kafa bolgesi (Y<neckY) max Z, sol/sag
headm=Y<neckY
def eartip(left):
    m=headm & ((X>0.03) if left else (X<-0.03))
    if m.sum()<3: return None
    idx=np.where(m)[0]; j=idx[np.argmax(Z[idx])]; return Vector((float(X[j]),float(Y[j]),float(Z[j])))
earL=eartip(True); earR=eartip(False)
head_cz=core_z((neckY+minY)/2,hw=0.05,q=0.55)
print("earL",[round(c,3) for c in earL] if earL else None,"earR",[round(c,3) for c in earR] if earR else None,"head_cz",round(head_cz,3))

# ================= ISKELET =================
arm_data=bpy.data.armatures.new("MouseArm"); arm=bpy.data.objects.new("MouseArm",arm_data)
bpy.context.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
eb=arm_data.edit_bones
def mk(name,h,t,parent=None,deform=True):
    b=eb.new(name); b.head=Vector(h); b.tail=Vector(t); b.use_deform=deform
    if parent and parent in eb: b.parent=eb[parent]
    return b
# Root (deform yok) pelviste
rootp=Vector((0,hipY,core_z(hipY))); mk("Root",rootp,rootp+Vector((0,-0.05,0)),None,False)
# OMURGA 5 seg: pelvis(+Y) -> boyun(-Y)
NSP=5; sp_names=[]; ys=[hipY+(neckY-hipY)*i/NSP for i in range(NSP+1)]
prev="Root"
for i in range(NSP):
    h=Vector((0,ys[i],core_z(ys[i]))); t=Vector((0,ys[i+1],core_z(ys[i+1])))
    nm=f"SpineX_{i}"; mk(nm,h,t,prev); prev=nm; sp_names.append(nm)
# BAS zinciri SpineX_4 -> burun
hz=head_cz
hpts=[Vector((0,neckY,core_z(neckY))),Vector((0,(neckY+nose_tip[1])*0.5+0.04,hz)),
      Vector((0,nose_tip[1]*0.55+neckY*0.45,hz)),Vector((0,nose_tip[1]+0.06,hz*0.6+nose_tip[2]*0.4))]
mk("Head_0",hpts[0],hpts[1],"SpineX_4"); mk("Head_1",hpts[1],hpts[2],"Head_0"); mk("Head_2",hpts[2],hpts[3],"Head_1")
mk("Nose",hpts[3],Vector((0,nose_tip[1],nose_tip[2])),"Head_2")
# KULAK
if earL: mk("Ear_L",Vector((earL[0]*0.6,earL[1],hz+0.04)),earL,"Head_1")
if earR: mk("Ear_R",Vector((earR[0]*0.6,earR[1],hz+0.04)),earR,"Head_1")
# KUYRUK 12
prev="Root"; tail_names=[]
for i in range(NT):
    nm=f"Tail_{i:02d}"; mk(nm,tp[i],tp[i+1],prev); prev=nm; tail_names.append(nm)
# BACAKLAR 2 kemik; en yakin omurga bonuna parentle
def nearest_spine(y):
    best=sp_names[0]; bd=1e9
    for nm in sp_names:
        mid=(eb[nm].head.y+eb[nm].tail.y)/2; dd=abs(mid-y)
        if dd<bd: bd=dd; best=nm
    return best
LEGUP={}; LEGLO={}
for k,fp in feet.items():
    if fp is None: continue
    root=Vector((fp.x*0.55, fp.y, core_z(fp.y)-0.02))
    knee=root.lerp(fp,0.55)+Vector((fp.x*0.06,0,0))
    par=nearest_spine(fp.y)
    up=f"Leg{k}_up"; lo=f"Leg{k}_lo"
    mk(up,root,knee,par); mk(lo,knee,fp,up); LEGUP[k]=up; LEGLO[k]=lo
bpy.ops.object.mode_set(mode='OBJECT')
bone_world={b.name:(M.inverted()@(arm.matrix_world@b.head_local), M.inverted()@(arm.matrix_world@b.tail_local)) for b in arm_data.bones}
# NOT: arm world = identity (link edildi), mesh world = M. Segmentleri MESH-LOCAL'a degil WORLD'e gore hesapla:
bw={b.name:(arm.matrix_world@b.head_local, arm.matrix_world@b.tail_local) for b in arm_data.bones}
print("BONES",len(arm_data.bones))

# ================= PROXIMITY SKINNING =================
SIGMA_DEF=0.05
def sigma(n):
    if n.startswith("Tail"): return 0.024
    if n.startswith("Leg"): return 0.034
    if n.startswith("Ear") or n=="Nose": return 0.028
    if n.startswith("Head"): return 0.045
    return SIGMA_DEF
deform=[b.name for b in arm_data.bones if b.use_deform]
H=np.array([list(bw[n][0]) for n in deform]); T=np.array([list(bw[n][1]) for n in deform])
AB=T-H; L2=np.einsum('ij,ij->i',AB,AB)+1e-9
W=np.zeros((len(co),len(deform)),dtype=np.float64)
for bi,n in enumerate(deform):
    h=H[bi]; ab=AB[bi]; l2=L2[bi]
    tt=np.clip(((co-h)@ab)/l2,0,1)
    proj=h[None,:]+tt[:,None]*ab[None,:]
    d=np.linalg.norm(co-proj,axis=1)
    W[:,bi]=np.exp(-(d/sigma(n))**2)
# top-4 + normalize
order=np.argsort(-W,axis=1)
Wt=np.zeros_like(W)
for vi in range(len(co)):
    top=order[vi,:4]; Wt[vi,top]=W[vi,top]
s=Wt.sum(axis=1,keepdims=True); s[s<1e-9]=1.0; Wt/=s
# garanti: hic agirlik almayan vertex en yakin bona
nz=Wt.sum(axis=1)<1e-6
for vi in np.where(nz)[0]: Wt[vi,order[vi,0]]=1.0
# vertex group olustur + ata
for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
vgs={n:mesh.vertex_groups.new(name=n) for n in deform}
for bi,n in enumerate(deform):
    col=Wt[:,bi]; idxs=np.where(col>1e-4)[0]
    for vi in idxs: vgs[n].add([int(vi)],float(col[vi]),'REPLACE')
# armature modifier
mod=next((m for m in mesh.modifiers if m.type=='ARMATURE'),None) or mesh.modifiers.new("Armature",'ARMATURE')
mod.object=arm; mesh.parent=arm
print("SKINNED groups",len(mesh.vertex_groups))

# ===== skill smooth_weights + cap4 + normalize =====
import importlib.util as ilu
spec=ilu.spec_from_file_location("bs",SKILL); bs=ilu.module_from_spec(spec); spec.loader.exec_module(bs)
bpy.context.view_layer.objects.active=mesh
try: bs.smooth_weights(mesh,factor=0.5,iterations=2); print("SMOOTH ok")
except Exception as e: print("smooth fail",e)
try: bs.cap_weights_to_n(mesh,n=4); print("CAP ok")
except Exception as e: print("cap fail",e)
bpy.context.view_layer.objects.active=mesh; bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL')
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))

# ================= TEST POZ + VERIFY RENDER =================
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE')
def rotq(n,axis,deg):
    pb=arm.pose.bones.get(n)
    if not pb: return
    from mathutils import Quaternion
    M3=arm.matrix_world.to_3x3(); la=(M3@pb.bone.matrix_local.to_3x3()).inverted()@Vector(axis)
    pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=Quaternion(la.normalized(),math.radians(deg))
def rote(n,rx=0,ry=0,rz=0):
    pb=arm.pose.bones.get(n)
    if pb: pb.rotation_mode='XYZ'; pb.rotation_euler=(math.radians(rx),math.radians(ry),math.radians(rz))
for n in sp_names: rote(n,rx=6)                       # omurga kambur (pulse test)
for i,n in enumerate(tail_names): rote(n,rz=10*(0.4+0.6*i/11))   # kuyruk yumusak egri
for k in ('FL','FR'):
    if k in LEGUP: rotq(LEGUP[k],(1,0,0),18); rotq(LEGLO[k],(1,0,0),-12)
for k in ('RL','RR'):
    if k in LEGUP: rotq(LEGUP[k],(1,0,0),-16); rotq(LEGLO[k],(1,0,0),14)
rote("Head_0",rz=8)
if earL: rote("Ear_L",rz=-12)
if earR: rote("Ear_R",rz=12)
bpy.ops.object.mode_set(mode='OBJECT')
arm.hide_render=True
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.42,0.46,0.52,1)
sd=bpy.data.lights.new("k",'SUN'); sd.energy=3.3; so=bpy.data.objects.new("k",sd)
bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(55),math.radians(10),math.radians(45))
bb=[M@Vector(c) for c in mesh.bound_box]
mn=Vector((min(v.x for v in bb),min(v.y for v in bb),min(v.z for v in bb)))
mx=Vector((max(v.x for v in bb),max(v.y for v in bb),max(v.z for v in bb)))
ctr=(mn+mx)/2; size=max((mx-mn)[i] for i in range(3))
cam=bpy.data.cameras.new("c"); cobj=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(cobj)
bpy.context.scene.camera=cobj; cam.lens=50
tg=bpy.data.objects.new("t",None); tg.location=ctr; bpy.context.collection.objects.link(tg)
cobj.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=680; sc.render.resolution_y=560
d=size*2.2
for nm,(ox,oy,oz) in {"rig_side":(d,0,0.1),"rig_top":(0.01,0.01,d),"rig_q34":(d*0.8,d*0.7,d*0.5),"rig_tail":(d*0.5,d*0.7,0.2)}.items():
    cobj.location=(ctr.x+ox,ctr.y+oy,ctr.z+oz)
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True)
# rest poz + rigged glb
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT'); bpy.ops.pose.transforms_clear(); bpy.ops.object.mode_set(mode='OBJECT')
arm.hide_render=False
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.gltf(filepath=outglb,export_format='GLB',use_selection=True,export_apply=False,
    export_skins=True,export_animations=False,export_yup=True)
print("RIG_DONE bones",len(arm_data.bones),"glb",os.path.getsize(outglb))
