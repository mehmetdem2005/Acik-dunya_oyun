#!/usr/bin/env python3
"""Fare 7 animasyon v2 (enh3 rig): puruzsuz omurga + INCE bacak (gerilmez) + ZENGIN
ikincil hareket (bas cevirme/tilt, sik burun, kulak flick, nefes, agirlik kaymasi,
nuansli kuyruk). Hepsinde dogal gecikmeli kuyruk.
blender --background <enh3.blend> --python mouse_animate2.py -- <out.blend> [fps]
"""
import bpy, sys, os, math
from mathutils import Quaternion, Vector
argv=sys.argv[sys.argv.index("--")+1:]
outblend=argv[0]; FPS=int(argv[1]) if len(argv)>1 else 30
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); bpy.context.view_layer.objects.active=arm
R=math.radians
TAIL=[f"Tail_{i:02d}" for i in range(12)]
SPX=[f"SpineX_{i}" for i in range(5)]
LEGR={'FL':'bone_9','FR':'bone_13','RL':'bone_27','RR':'bone_17'}
LEGM={'FL':'0_Left_Limb_1','FR':'0_Right_Limb_1','RL':'1_Left_Limb_1','RR':'1_Right_Limb_1'}
_M3=arm.matrix_world.to_3x3(); LEGAXIS={}
for n in list(LEGR.values())+list(LEGM.values()):
    if n in arm.pose.bones:
        Rbw=_M3@arm.pose.bones[n].bone.matrix_local.to_3x3(); LEGAXIS[n]=(Rbw.inverted()@Vector((1,0,0))).normalized()
def kwx(n,f,deg):
    pb=arm.pose.bones.get(n)
    if not pb or n not in LEGAXIS: return
    pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=Quaternion(LEGAXIS[n],R(deg)); pb.keyframe_insert('rotation_quaternion',frame=f)
def kr(n,f,rx=0,ry=0,rz=0):
    pb=arm.pose.bones.get(n)
    if not pb: return
    pb.rotation_mode='XYZ'; pb.rotation_euler=(R(rx),R(ry),R(rz)); pb.keyframe_insert('rotation_euler',frame=f)
def kroot(f,up=0,fwd=0,yaw=0,roll=0):
    pb=arm.pose.bones['Root']; pb.location=(-fwd,up,0); pb.keyframe_insert('location',frame=f)
    pb.rotation_mode='XYZ'; pb.rotation_euler=(R(roll),R(yaw),0); pb.keyframe_insert('rotation_euler',frame=f)
def kspine(f,pitch=0,sway=0):       # 5 segmente puruzsuz dagit
    for i,n in enumerate(SPX): kr(n,f, rx=pitch/5.0, rz=sway/5.0)
def ktail(f,t,side=10,up=0,freq=1.0,delay=0.5,curl=0,amp_mod=1.0):
    for i,tn in enumerate(TAIL):
        ph=2*math.pi*freq*t - i*delay
        g=(0.55+0.45*i/11)*amp_mod
        kr(tn,f, rx=up*math.sin(ph*0.7)+curl*(0.4+0.6*i/11), rz=side*math.sin(ph)*g)
def newact(n):
    if arm.animation_data is None: arm.animation_data_create()
    if n in bpy.data.actions: bpy.data.actions.remove(bpy.data.actions[n])
    a=bpy.data.actions.new(n); a.use_fake_user=True; arm.animation_data.action=a; return a
def clearpose():
    for pb in arm.pose.bones: pb.location=(0,0,0); pb.rotation_euler=(0,0,0); pb.rotation_quaternion=(1,0,0,0)
def head(f,pitch=0,turn=0,tilt=0):
    kr('Head_0',f, rz=pitch, rx=turn, ry=tilt); kr('Head_1',f, rz=pitch*0.4)
def nose(f,a): kr('Nose',f, rx=a)
def ears(f,L,Rr): kr('bone_6',f, rz=L); kr('bone_7',f, rz=-Rr)
DIAG={'FL':0.0,'RR':0.0,'FR':0.5,'RL':0.5}
def gait(f,t,phases,swing=8,bend=8,lift=10):
    for leg,ph in phases.items():
        p=(t+ph)%1.0; kwx(LEGR[leg],f, swing*math.sin(2*math.pi*p)); kwx(LEGM[leg],f, bend+lift*max(0,math.sin(2*math.pi*p)))

# 1 IDLE — zengin: nefes, ara ara bakinma, sik burun, kulak flick, kuyruk yavas
def idle():
    a=newact("idle"); N=120
    for f in range(1,N+2,2):
        t=(f-1)/N
        kroot(f, up=0.004*math.sin(2*math.pi*t*1.5), yaw=4*math.sin(2*math.pi*t*0.4), roll=2*math.sin(2*math.pi*t*0.3))
        kspine(f, pitch=2+1.5*math.sin(2*math.pi*t*1.5))     # nefes (gogus)
        tn=8*math.sin(2*math.pi*t*0.4); head(f, pitch=4*math.sin(2*math.pi*t*0.7+1), turn=tn, tilt=3*math.sin(2*math.pi*t*0.5))
        nose(f, 8*max(0,math.sin(2*math.pi*t*6)))            # surekli koklama
        e=20 if (int(t*5)%5==0) else 4; ears(f, e*0.5+4*math.sin(2*math.pi*t*0.9), e*0.5+4*math.sin(2*math.pi*t*1.1))
        ktail(f,t, side=7, up=3, freq=0.5, curl=3, amp_mod=0.8+0.4*math.sin(2*math.pi*t*0.6))
    return a,N,True

# 2 WALK — ince bacak, govde bob+sway, kafa bob, kuyruk takip
def walk():
    a=newact("walk"); N=32
    for f in range(1,N+2,2):
        t=(f-1)/N
        gait(f,t,DIAG, swing=8, bend=8, lift=10)
        kroot(f, up=0.006*abs(math.sin(2*math.pi*t*2)), yaw=5*math.sin(2*math.pi*t), roll=3*math.sin(2*math.pi*t))
        kspine(f, pitch=3, sway=6*math.sin(2*math.pi*t))
        head(f, pitch=5, turn=4*math.sin(2*math.pi*t*0.5), tilt=-2*math.sin(2*math.pi*t*2))
        nose(f, 5*max(0,math.sin(2*math.pi*t*3)))
        ears(f, 6+3*math.sin(2*math.pi*t*2), 6-3*math.sin(2*math.pi*t*2))
        ktail(f,t, side=12, up=4, freq=1.0, curl=2)
    return a,N,True

# 3 SNEAK — alcak govde (omurga kambur), yavas adim, tetikte
def sneak():
    a=newact("sneak"); N=64
    for f in range(1,N+2,2):
        t=(f-1)/N
        gait(f,t,DIAG, swing=5, bend=12, lift=6)
        kroot(f, up=-0.025+0.003*math.sin(2*math.pi*t*2), yaw=4*math.sin(2*math.pi*t*0.7))
        kspine(f, pitch=14, sway=4*math.sin(2*math.pi*t))    # kambur (puruzsuz 5 seg)
        head(f, pitch=12, turn=8*math.sin(2*math.pi*t*0.6))
        nose(f, 9*max(0,math.sin(2*math.pi*t*5)))
        ears(f, 14+4*math.sin(2*math.pi*t*1.3), 14-4*math.sin(2*math.pi*t*1.3))
        ktail(f,t, side=6, up=2, freq=0.6, curl=2, amp_mod=0.7)
    return a,N,True

# 4 ATTACK — cromel->atilim->isir->toparla, ince bacak
def attack():
    a=newact("attack"); N=26
    KF={1:(0,0,6,0,4,2,(-6,0,6)), 7:(-0.02,-0.02,14,0,-16,12,(-12,0,-6)),
        12:(0.01,0.09,20,12,-18,4,(-4,12,0)), 17:(0,0.10,16,4,-12,6,(0,16,0)), 26:(0,0,6,0,4,2,(-6,0,6))}
    for f,(up,fwd,hd,nse,ear,sp,tl) in KF.items():
        kroot(f, up=up, fwd=fwd); head(f, pitch=hd); nose(f, nse); ears(f, ear*0.4, ear*0.4); kspine(f, pitch=sp)
        sb,whip,curl=tl
        for i,tn in enumerate(TAIL): kr(tn,f, rx=curl*(0.4+0.6*i/11), rz=sb+whip*i/11)
        # on bacak hafif one (atilim) - kucuk
        for leg in ('FL','FR'): kwx(LEGR[leg],f, -6 if fwd>0.05 else 0)
    return a,N,False

# 5 EAT — model ZATEN yeme pozunda; sadece kemirme bob + burun + hafif pati, GERILME YOK
def eat():
    a=newact("eat"); N=120
    for f in range(1,N+2,3):
        t=(f-1)/N; nib=math.sin(2*math.pi*t*7)
        kroot(f, up=0.01, roll=2*math.sin(2*math.pi*t*0.5))
        kspine(f, pitch=4)
        head(f, pitch=8+5*nib, turn=3*math.sin(2*math.pi*t*0.4))   # hizli kemirme bob
        nose(f, 7*abs(nib))
        # ara kontrol: ~her saniye basini kaldir
        if int(t*4)%4==2: head(f, pitch=-6, turn=10)
        ears(f, 6+4*math.sin(2*math.pi*t*0.6), 6-4*math.sin(2*math.pi*t*0.6))
        for leg in ('FL','FR'): kwx(LEGM[leg],f, 6*abs(nib))     # patide kucuk kemirme titremesi
        ktail(f,t, side=5, up=2, freq=0.4, curl=10, amp_mod=0.6)
    return a,N,True

# 6 HOLE_SLOW — surunerek girer, omurga puruzsuz dalga, kuyruk en son
def hole_slow():
    a=newact("hole_slow"); N=120
    for f in range(1,N+2,3):
        t=(f-1)/N; enter=max(0,(t-0.15)/0.7)
        kroot(f, up=-0.04*min(1,enter*2), fwd=0.30*min(1,enter), yaw=4*math.sin(2*math.pi*t*3)*enter)
        kspine(f, pitch=14*min(1,enter*2), sway=5*math.sin(2*math.pi*t*2)*enter)   # surunme dalgasi
        head(f, pitch=14); nose(f, 8*max(0,math.sin(2*math.pi*t*4)))
        push=math.sin(2*math.pi*t*4)
        for leg in ('FL','FR'): kwx(LEGR[leg],f, -8*enter); kwx(LEGM[leg],f, 8+6*push)
        for leg in ('RL','RR'): kwx(LEGR[leg],f, 8*push*enter); kwx(LEGM[leg],f, 8+8*max(0,push))
        tin=max(0,(t-0.85)/0.15); ktail(f,t, side=7*(1-tin), up=3, freq=0.8, curl=35*tin)
    return a,N,False

# 7 HOLE_PANIC — hizli dalis, govde kivrilma, kuyruk whip->iceri
def hole_panic():
    a=newact("hole_panic"); N=46
    for f in range(1,N+2,2):
        t=(f-1)/N; enter=max(0,(t-0.1)/0.7)
        kroot(f, up=-0.05*min(1,enter*3), fwd=0.34*min(1,enter*1.1), yaw=8*math.sin(2*math.pi*t*5)*enter)
        kspine(f, pitch=16*min(1,enter*2), sway=7*math.sin(2*math.pi*t*4)*enter)
        head(f, pitch=16); ears(f, -16, 16)
        push=math.sin(2*math.pi*t*7)
        for leg in ('FL','FR'): kwx(LEGR[leg],f, -9*enter); kwx(LEGM[leg],f, 10+8*push)
        for leg in ('RL','RR'): kwx(LEGR[leg],f, 12*push*enter); kwx(LEGM[leg],f, 10+10*max(0,push))
        tin=max(0,(t-0.8)/0.2); ktail(f,t, side=13*(1-tin), up=4, freq=1.6, curl=48*tin)
    return a,N,False

clips=[idle(),walk(),sneak(),attack(),eat(),hole_slow(),hole_panic()]
clearpose()
ad=arm.animation_data
while ad.nla_tracks: ad.nla_tracks.remove(ad.nla_tracks[0])
ad.action=None
import json; man=[]
for act,n,loop in clips:
    tr=ad.nla_tracks.new(); tr.name="NLA_"+act.name; st=tr.strips.new(act.name,1,act)
    if loop: st.repeat=1.0
    man.append({"name":act.name,"frames":[1,n],"loop":loop})
bpy.context.scene.render.fps=FPS
from pathlib import Path
Path(outblend).with_suffix(".animation_manifest.json").write_text(json.dumps({"fps":FPS,"clips":man},indent=2))
print("CLIPS",[c[0].name for c in clips])
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend)); print("ANIM2_DONE")
