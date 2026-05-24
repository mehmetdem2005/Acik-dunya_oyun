#!/usr/bin/env python3
"""Yeni fare mesh'ini SIFIRDAN rigle (v2): SIRTA UYAN puruzsuz ")" omurga yayi (5 seg),
12 kemik kuyruk, 4 bacak (3'er kemik: ust+alt+ayak -> gercek diz/bilek eklemleri),
bas zinciri + 2 kulak + burun. Proximity skinning (gaussian, top-4) + skill smooth+cap4+normalize.
ISKELET OVERLAY render (kemikler tup olarak govde uzerinde) -> rig'in sirta uydugu gorunur.
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

def zq(y,hw,q):
    m=(Y>=y-hw)&(Y<y+hw)
    if m.sum()<5: return (minZ+maxZ)/2
    return float(np.quantile(Z[m],q))
def width_at(y,hw=0.02):
    m=(Y>=y-hw)&(Y<y+hw)
    return float(X[m].max()-X[m].min()) if m.sum()>=3 else 0.0

# --- LANDMARKS ---
nose_tip=co[np.argmin(Y)]
tailbaseY=maxY-0.02
for y in np.arange(0.0,maxY,0.02):
    if width_at(y)<0.20: tailbaseY=float(y); break
hipY=tailbaseY-0.04; neckY=minY+0.20
print("nose_tip",[round(c,3) for c in nose_tip],"tailbaseY",round(tailbaseY,3),"hipY",round(hipY,3),"neckY",round(neckY,3))

# --- SIRT YAYI (smooth ")" arc): her Y diliminde sirt-ust konturu (q~0.86), yumusatilmis, govde icine ofset
ys_inc=np.linspace(neckY-0.04,hipY+0.02,40)
zs_back=np.array([zq(y,0.022,0.93) for y in ys_inc])   # sirt-ust kontur
k=7; sm=np.convolve(np.pad(zs_back,(k//2,k//2),'edge'),np.ones(k)/k,'valid')[:len(ys_inc)]
sm=sm-0.022                                   # skin'in hemen altinda -> sirta uyan ")" yayi
def spineZ(y): return float(np.interp(y,ys_inc,sm))
# kafa cekirdek Z (burun/ceneye dogru alcalir)
def headZ(y): return zq(y,0.05,0.5)

# kuyruk izi
tpath=[]; b=tailbaseY
while b<maxY+0.001:
    m=(Y>=b)&(Y<b+0.025)
    if m.sum()>=2: tpath.append(Vector((float(X[m].mean()),b+0.0125,float(Z[m].mean()))))
    b+=0.025
if len(tpath)<3: tpath=[Vector((0,tailbaseY+(maxY-tailbaseY)*k/6,spineZ(tailbaseY))) for k in range(7)]
def resample(pts,nseg):
    seg=[(pts[i+1]-pts[i]).length for i in range(len(pts)-1)]; tot=sum(seg) or 1e-6; out=[pts[0]]
    for k in range(1,nseg+1):
        d=tot*k/nseg; acc=0; p=pts[-1]
        for i in range(len(pts)-1):
            if acc+seg[i]>=d or i==len(pts)-2:
                t=(d-acc)/seg[i] if seg[i]>1e-9 else 0; p=pts[i].lerp(pts[i+1],min(max(t,0),1)); break
            acc+=seg[i]
        out.append(p)
    return out
NT=12; tp=resample(tpath,NT)
print("tail tip",[round(c,3) for c in tp[-1]])

# ayaklar: en alt %16 bant -> 4 grup
band=Z<(minZ+0.16*(maxZ-minZ))
def foot(front,left):
    m=band & ((Y<0) if front else (Y>=0)) & ((X>0) if left else (X<0))
    if m.sum()<3: return None
    return Vector((float(np.median(X[m])),float(np.median(Y[m])),float(Z[m].min()+0.008)))
feet={'FL':foot(True,True),'FR':foot(True,False),'RL':foot(False,True),'RR':foot(False,False)}
for k,v in feet.items(): print("foot",k,[round(c,3) for c in v] if v else None)

# kulaklar
headm=Y<neckY
def eartip(left):
    m=headm & ((X>0.02) if left else (X<-0.02))
    if m.sum()<3: return None
    idx=np.where(m)[0]; j=idx[np.argmax(Z[idx])]; return Vector((float(X[j]),float(Y[j]),float(Z[j])))
earL=eartip(True); earR=eartip(False)
print("earL",[round(c,3) for c in earL] if earL else None,"earR",[round(c,3) for c in earR] if earR else None)

# ================= ISKELET =================
arm_data=bpy.data.armatures.new("MouseArm"); arm=bpy.data.objects.new("MouseArm",arm_data)
bpy.context.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
eb=arm_data.edit_bones
def mk(name,h,t,parent=None,deform=True):
    b=eb.new(name); b.head=Vector(h); b.tail=Vector(t); b.use_deform=deform
    if parent and parent in eb: b.parent=eb[parent]
    return b
# Root (pelvis, deform yok)
rootp=Vector((0,hipY,spineZ(hipY))); mk("Root",rootp,Vector((0,hipY-0.05,spineZ(hipY-0.05))),None,False)
# OMURGA 5 seg: pelvis(+Y) -> boyun(-Y), SIRT YAYINDA
NSP=5; sp_names=[]; ys=[hipY+(neckY-hipY)*i/NSP for i in range(NSP+1)]
prev="Root"
for i in range(NSP):
    h=Vector((0,ys[i],spineZ(ys[i]))); t=Vector((0,ys[i+1],spineZ(ys[i+1])))
    nm=f"SpineX_{i}"; mk(nm,h,t,prev); prev=nm; sp_names.append(nm)
# BAS zinciri (boyundan buruna, alcalan)
n0=Vector((0,neckY,spineZ(neckY)))
n1=Vector((0,(neckY+nose_tip[1])*0.5,headZ((neckY+nose_tip[1])*0.5)+0.03))
n2=Vector((0,nose_tip[1]*0.6+neckY*0.4,headZ(nose_tip[1]*0.7)+0.0))
n3=Vector((0,nose_tip[1]+0.05,nose_tip[2]+0.02))
mk("Head_0",n0,n1,"SpineX_4"); mk("Head_1",n1,n2,"Head_0"); mk("Head_2",n2,n3,"Head_1")
mk("Nose",n3,Vector((nose_tip[0],nose_tip[1],nose_tip[2])),"Head_2")
# KULAK (kafa-ust -> kulak ucu)
if earL: mk("Ear_L",Vector((earL[0]*0.55,earL[1],headZ(earL[1])+0.04)),earL,"Head_1")
if earR: mk("Ear_R",Vector((earR[0]*0.55,earR[1],headZ(earR[1])+0.04)),earR,"Head_1")
# KUYRUK 12
prev="Root"; tail_names=[]
for i in range(NT):
    nm=f"Tail_{i:02d}"; mk(nm,tp[i],tp[i+1],prev); prev=nm; tail_names.append(nm)
# BACAKLAR: 3 kemik (ust=femur/humerus, alt=tibia, ayak) -> diz+bilek eklemi
def nearest_spine(y):
    return min(sp_names,key=lambda nm:abs((eb[nm].head.y+eb[nm].tail.y)/2-y))
LEGUP={};LEGLO={};LEGFT={}
for k,fp in feet.items():
    if fp is None: continue
    legY=fp.y; sgn=1 if fp.x>0 else -1
    fwd=-0.02 if k in ('FL','FR') else 0.02     # diz one(on bacak)/arkaya(arka bacak)
    hip  =Vector((fp.x*0.5,  legY,        spineZ(legY)-0.01))
    knee =Vector((fp.x*0.82, legY-fwd,    hip.z*0.42+fp.z*0.58))
    ankle=Vector((fp.x*0.96, legY+fwd*0.5,fp.z+0.055))
    toe  =Vector((fp.x,      legY-0.025,  fp.z))
    par=nearest_spine(legY)
    up=f"Leg{k}_up"; lo=f"Leg{k}_lo"; ft=f"Leg{k}_ft"
    mk(up,hip,knee,par); mk(lo,knee,ankle,up); mk(ft,ankle,toe,lo)
    LEGUP[k]=up;LEGLO[k]=lo;LEGFT[k]=ft
bpy.ops.object.mode_set(mode='OBJECT')
bw={b.name:(arm.matrix_world@b.head_local, arm.matrix_world@b.tail_local) for b in arm_data.bones}
print("BONES",len(arm_data.bones))

# ================= REGION-BASED SKINNING =================
# Govde (karin/yan/sirt) -> OMURGA (eksenel, Y'ye gore tum kesit) ; bacaklar SADECE uzuv verts'i;
# kuyruk/bas kendi zincirleri. Boylece bacak hareketi govdeyi surukleMEZ.
deform=[b.name for b in arm_data.bones if b.use_deform]
bidx={n:i for i,n in enumerate(deform)}
def segd(h,t):
    h=np.array(h);t=np.array(t);ab=t-h;l2=ab@ab+1e-9
    tt=np.clip(((co-h)@ab)/l2,0,1); proj=h[None,:]+tt[:,None]*ab[None,:]
    return np.linalg.norm(co-proj,axis=1)
D={n:segd(bw[n][0],bw[n][1]) for n in deform}
spine_names=sp_names
spineY=np.array([(bw[n][0].y+bw[n][1].y)/2 for n in spine_names])
leg_segs={k:[LEGUP[k],LEGLO[k],LEGFT[k]] for k in feet if feet[k]}
legmin={k:np.min([D[s] for s in segs],axis=0) for k,segs in leg_segs.items()}
dlegmin=np.min(np.stack(list(legmin.values())),axis=0)
core_r,cut_r=0.035,0.085
Lmem=np.clip((cut_r-dlegmin)/(cut_r-core_r),0,1)        # bacak uyeligi 0..1 (uzuvda 1, govdede 0)
headbones=['Head_0','Head_1','Head_2','Nose']+(['Ear_L'] if earL else [])+(['Ear_R'] if earR else [])
def hsig(n): return 0.026 if (n=='Nose' or n.startswith('Ear')) else 0.045
W=np.zeros((len(co),len(deform)))
tail_mask=Y>(tailbaseY-0.012); head_mask=Y<neckY
for vi in range(len(co)):
    y=Y[vi]
    if tail_mask[vi]:
        cand=tail_names+['SpineX_0']
        ww=np.array([math.exp(-(D[n][vi]/(0.024 if n.startswith('Tail') else 0.05))**2) for n in cand])
        if ww.sum()<1e-9: ww[0]=1.0
        ww/=ww.sum()
        for n,wv in zip(cand,ww):
            if wv>1e-4: W[vi,bidx[n]]+=wv
    elif head_mask[vi]:
        cand=headbones+['SpineX_4']
        ww=np.array([math.exp(-(D[n][vi]/(0.06 if n=='SpineX_4' else hsig(n)))**2) for n in cand])
        if ww.sum()<1e-9: ww[0]=1.0
        ww/=ww.sum()
        for n,wv in zip(cand,ww):
            if wv>1e-4: W[vi,bidx[n]]+=wv
    else:
        l=Lmem[vi]
        dY=np.abs(y-spineY); sw=np.exp(-(dY/0.10)**2)
        if sw.sum()<1e-9: sw[np.argmin(dY)]=1.0
        sw=sw/sw.sum()*(1.0-l)
        for i,nm in enumerate(spine_names):
            if sw[i]>1e-4: W[vi,bidx[nm]]+=sw[i]
        if l>1e-3:
            k=min(legmin,key=lambda kk:legmin[kk][vi]); segs=leg_segs[k]
            lw=np.array([math.exp(-(D[s][vi]/0.03)**2) for s in segs])
            if lw.sum()<1e-9: lw=np.ones(len(segs))
            lw=lw/lw.sum()*l
            for j,s in enumerate(segs):
                if lw[j]>1e-4: W[vi,bidx[s]]+=lw[j]
sN=W.sum(axis=1,keepdims=True); sN[sN<1e-9]=1.0; W/=sN
for vi in np.where(W.sum(axis=1)<1e-6)[0]:
    W[vi,bidx[spine_names[int(np.argmin(np.abs(Y[vi]-spineY)))]]]=1.0
Wt=W
for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
vgs={n:mesh.vertex_groups.new(name=n) for n in deform}
for n in deform:
    bi=bidx[n]
    for vi in np.where(Wt[:,bi]>1e-4)[0]: vgs[n].add([int(vi)],float(Wt[vi,bi]),'REPLACE')
mod=next((m for m in mesh.modifiers if m.type=='ARMATURE'),None) or mesh.modifiers.new("Armature",'ARMATURE')
mod.object=arm; mesh.parent=arm
print("SKINNED groups",len(mesh.vertex_groups))
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

# ================= ISKELET OVERLAY RENDER =================
def tube(p0,p1,rgb,rad=0.007):
    cu=bpy.data.curves.new('t','CURVE'); cu.dimensions='3D'; cu.bevel_depth=rad; cu.bevel_resolution=2
    sp=cu.splines.new('POLY'); sp.points.add(1)
    sp.points[0].co=(p0[0],p0[1],p0[2],1); sp.points[1].co=(p1[0],p1[1],p1[2],1)
    ob=bpy.data.objects.new('bone',cu); bpy.context.collection.objects.link(ob)
    m=bpy.data.materials.new('bm'); m.use_nodes=True; nt=m.node_tree
    em=nt.nodes.new('ShaderNodeEmission'); em.inputs[0].default_value=(rgb[0],rgb[1],rgb[2],1); em.inputs[1].default_value=5
    nt.links.new(em.outputs[0],nt.nodes['Material Output'].inputs['Surface'])
    cu.materials.append(m); return ob
def col(n):
    if n.startswith("Spine") or n=="Root": return (1,0.12,0.12)
    if n.startswith("Tail"): return (0.2,0.55,1)
    if n.startswith("Leg"): return (0.15,1,0.2)
    if n.startswith("Ear"): return (1,0.25,1)
    return (1,1,0.2)
tubes=[tube(bw[b.name][0],bw[b.name][1],col(b.name)) for b in arm_data.bones]
# mesh yari saydam (EEVEE Next BLENDED)
mat=mesh.data.materials[0]
try:
    mat.surface_render_method='BLENDED'
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    if bsdf: bsdf.inputs['Alpha'].default_value=0.32
except Exception as e: print("alpha fail",e)
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.05,0.05,0.07,1)
sd=bpy.data.lights.new("k",'SUN'); sd.energy=2.0; so=bpy.data.objects.new("k",sd)
bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(55),math.radians(10),math.radians(45))
bb=[M@Vector(c) for c in mesh.bound_box]
mn=Vector((min(v.x for v in bb),min(v.y for v in bb),min(v.z for v in bb)))
mx=Vector((max(v.x for v in bb),max(v.y for v in bb),max(v.z for v in bb)))
ctr=(mn+mx)/2; size=max((mx-mn)[i] for i in range(3))
cam=bpy.data.cameras.new("c"); cobj=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(cobj)
bpy.context.scene.camera=cobj; cam.lens=50
tg=bpy.data.objects.new("t",None); tg.location=ctr; bpy.context.collection.objects.link(tg)
cobj.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=760; sc.render.resolution_y=560
d=size*2.2
for nm,(ox,oy,oz) in {"skel_side":(d,0,0.05),"skel_top":(0.01,0.01,d),"skel_q34":(d*0.8,d*0.6,d*0.45)}.items():
    cobj.location=(ctr.x+ox,ctr.y+oy,ctr.z+oz)
    sc.render.filepath=os.path.join(rdir,nm+".png"); bpy.ops.render.render(write_still=True)
# overlay temizle + alpha eski haline + rigged glb
for ob in tubes: bpy.data.objects.remove(ob,do_unlink=True)
try:
    mat.surface_render_method='DITHERED'
    if mat.node_tree.nodes.get('Principled BSDF'): mat.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value=1.0
except: pass
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.gltf(filepath=outglb,export_format='GLB',use_selection=True,export_apply=False,
    export_skins=True,export_animations=False,export_yup=True)
print("RIG_DONE bones",len(arm_data.bones),"glb",os.path.getsize(outglb))
