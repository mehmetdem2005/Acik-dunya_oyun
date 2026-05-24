#!/usr/bin/env python3
"""Fare 7 animasyon: idle, walk, sneak, attack, eat, hole_slow, hole_panic.
Hepsinde dogal gecikmeli KUYRUK dalgasi. FK, olculmus local eksenler.
blender --background <enh2.blend> --python mouse_animate.py -- <out.blend> [fps]
"""
import bpy, sys, os, math
from mathutils import Quaternion, Vector
argv=sys.argv[sys.argv.index("--")+1:]
outblend=argv[0]; FPS=int(argv[1]) if len(argv)>1 else 30
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
bpy.context.view_layer.objects.active=arm
R=math.radians
TAIL=[f"Tail_{i:02d}" for i in range(12)]
LEGR={'FL':'bone_9','FR':'bone_13','RL':'bone_27','RR':'bone_17'}
LEGM={'FL':'0_Left_Limb_1','FR':'0_Right_Limb_1','RL':'1_Left_Limb_1','RR':'1_Right_Limb_1'}
# bacak kemiklerinin DUNYA-X (salinim ekseni) local karsiligi -> burkulmadan don
_M3=arm.matrix_world.to_3x3()
LEGAXIS={}
for n in list(LEGR.values())+list(LEGM.values()):
    if n in arm.pose.bones:
        Rbw=_M3@arm.pose.bones[n].bone.matrix_local.to_3x3()
        LEGAXIS[n]=(Rbw.inverted()@Vector((1,0,0))).normalized()
def kwx(n,f,deg):   # bacak: dunya-X ekseni etrafinda temiz don (quaternion)
    pb=arm.pose.bones.get(n)
    if not pb or n not in LEGAXIS: return
    pb.rotation_mode='QUATERNION'
    pb.rotation_quaternion=Quaternion(LEGAXIS[n], R(deg))
    pb.keyframe_insert('rotation_quaternion',frame=f)
def has(n): return n in arm.pose.bones
def kr(n,f,rx=0,ry=0,rz=0):
    pb=arm.pose.bones.get(n)
    if not pb: return
    pb.rotation_mode='XYZ'; pb.rotation_euler=(R(rx),R(ry),R(rz)); pb.keyframe_insert('rotation_euler',frame=f)
def kroot(f,up=0,fwd=0,yaw=0,roll=0):
    pb=arm.pose.bones['Root']
    pb.location=(-fwd,up,0); pb.keyframe_insert('location',frame=f)
    pb.rotation_mode='XYZ'; pb.rotation_euler=(R(roll),R(yaw),0); pb.keyframe_insert('rotation_euler',frame=f)
def ktail(f,t,side=10,up=0,freq=1.0,delay=0.55,curl=0):
    # dogal gecikmeli dalga: her segment oncekini gecikmeli takip eder
    for i,tn in enumerate(TAIL):
        ph=2*math.pi*freq*t - i*delay
        rz=side*math.sin(ph)*(0.6+0.4*i/11)        # uca dogru artan genlik
        rx=up*math.sin(ph*0.7)+curl                # dikey/curl
        kr(tn,f,rx,0,rz)
def newact(name):
    if arm.animation_data is None: arm.animation_data_create()
    if name in bpy.data.actions: bpy.data.actions.remove(bpy.data.actions[name])
    a=bpy.data.actions.new(name); a.use_fake_user=True; arm.animation_data.action=a; return a
def clearpose():
    for pb in arm.pose.bones:
        pb.location=(0,0,0); pb.rotation_euler=(0,0,0); pb.rotation_quaternion=(1,0,0,0)

def gait(f,t,phases,swing=14,bend=18,lift_bend=22):
    for leg,ph in phases.items():
        p=(t+ph)%1.0
        sw=swing*math.sin(2*math.pi*p)
        kwx(LEGR[leg],f, sw)
        # diz: salinim(swing) tepe noktasinda bukulme
        kn=bend + lift_bend*max(0,math.sin(2*math.pi*p))
        kwx(LEGM[leg],f, kn)

DIAG={'FL':0.0,'RR':0.0,'FR':0.5,'RL':0.5}

# ============ 1 IDLE ============
def idle():
    a=newact("idle"); N=90
    for f in range(1,N+2,3):
        t=(f-1)/N
        kroot(f, up=0.004*math.sin(2*math.pi*t*2), yaw=3*math.sin(2*math.pi*t*0.5))   # nefes + hafif yon
        kr('Head_0',f, rz=4*math.sin(2*math.pi*t*0.5+1), rx=6*math.sin(2*math.pi*t*0.7))  # nod+turn
        kr('Nose',f, rx=7*max(0,math.sin(2*math.pi*t*5)))                                 # hizli koklama
        ear=18 if (int(t*4)%4==0) else 0
        kr('bone_6',f, rz=ear*0.4); kr('bone_7',f, rz=-ear*0.4)
        ktail(f,t, side=7, up=3, freq=0.6, curl=4)
    return a,N,True

# ============ 2 WALK ============
def walk():
    a=newact("walk"); N=36
    for f in range(1,N+2,2):
        t=(f-1)/N
        gait(f,t,DIAG, swing=15, bend=16, lift_bend=20)
        kroot(f, up=0.006*abs(math.sin(2*math.pi*t*2)), yaw=4*math.sin(2*math.pi*t))
        kr('Spine_A',f, rz=4*math.sin(2*math.pi*t)); kr('Spine_B',f, rz=4*math.sin(2*math.pi*t))
        kr('Head_0',f, rx=6, rz=-3*math.sin(2*math.pi*t*2))
        kr('Nose',f, rx=5*max(0,math.sin(2*math.pi*t*3)))
        ktail(f,t, side=11, up=4, freq=1.0, curl=3)
    return a,N,True

# ============ 3 SNEAK ============
def sneak():
    a=newact("sneak"); N=60
    for f in range(1,N+2,2):
        t=(f-1)/N
        gait(f,t,DIAG, swing=9, bend=24, lift_bend=12)   # alcak, kisa adim
        kroot(f, up=-0.03+0.003*math.sin(2*math.pi*t*2), yaw=3*math.sin(2*math.pi*t))  # govde alcak
        kr('Spine_A',f, rx=8); kr('Spine_B',f, rx=8)                                    # kamburlasma
        kr('Head_0',f, rx=14, rz=6*math.sin(2*math.pi*t*0.7))                            # bas one+sag/sol
        kr('Nose',f, rx=8*max(0,math.sin(2*math.pi*t*4)))
        kr('bone_6',f, rz=10); kr('bone_7',f, rz=-10)                                    # kulak tetikte
        ktail(f,t, side=6, up=2, freq=0.7, curl=2)                                       # alcak yavas
    return a,N,True

# ============ 4 ATTACK ============
def attack():
    a=newact("attack"); N=28
    KF={1:dict(up=0,fwd=0,hd=8,nose=0,ear=0,sp=4,tl=(-8,0,6)),
        7:dict(up=-0.02,fwd=-0.02,hd=16,nose=0,ear=-18,sp=10,tl=(-14,0,-8)),   # cromel, kulak geri, kuyruk geri
        13:dict(up=0.01,fwd=0.10,hd=22,nose=10,ear=-20,sp=2,tl=(-6,12,0)),     # atilim, agiz/burun one
        18:dict(up=0,fwd=0.12,hd=18,nose=4,ear=-14,sp=4,tl=(0,16,0)),          # temas, kuyruk whip
        28:dict(up=0,fwd=0,hd=8,nose=0,ear=0,sp=4,tl=(-8,0,6))}                # toparla
    for f,d in KF.items():
        kroot(f, up=d['up'], fwd=d['fwd'])
        kr('Head_0',f, rx=d['hd']); kr('Head_1',f, rx=d['hd']*0.5)
        kr('Nose',f, rx=d['nose'])
        kr('bone_6',f, rz=d['ear']*0.4); kr('bone_7',f, rz=-d['ear']*0.4)
        kr('Spine_A',f, rx=d['sp']); kr('Spine_B',f, rx=d['sp'])
        # kuyruk: (side base, whip side, curl) -> tum segment
        sb,whip,curl=d['tl']
        for i,tn in enumerate(TAIL):
            kr(tn,f, rx=curl*(0.5+0.5*i/11), rz=(sb+whip*(i/11)))
    return a,N,False

# ============ 5 EAT ============
def eat():
    a=newact("eat"); N=120
    for f in range(1,N+2,3):
        t=(f-1)/N
        nib=math.sin(2*math.pi*t*6)            # hizli kemirme
        kroot(f, up=0.02, fwd=-0.02)            # hafif dik otur
        kr('Spine_A',f, rx=-10); kr('Spine_B',f, rx=-12)   # govde dikilir
        kr('Head_0',f, rx=10+4*nib)             # bas kemirme bob
        kr('Nose',f, rx=6*abs(nib))
        # on patiler agiza: front leg root yukari + diz buk (dunya-X)
        for leg in ('FL','FR'):
            kwx(LEGR[leg],f, -32); kwx(LEGM[leg],f, 58+5*nib)
        kr('bone_6',f, rz=8*math.sin(2*math.pi*t*0.5)); kr('bone_7',f, rz=-8*math.sin(2*math.pi*t*0.5))
        ktail(f,t, side=5, up=2, freq=0.5, curl=14)   # kuyruk yana kivrik, hafif
    return a,N,True

# ============ 6 HOLE_SLOW ============
def hole_slow():
    a=newact("hole_slow"); N=120
    for f in range(1,N+2,3):
        t=(f-1)/N
        # asama: 0-0.2 kontrol, 0.2-0.85 surunerek girer, 0.85-1 kuyruk iceri
        enter=max(0,(t-0.15)/0.7)               # 0..1 govde ileri
        kroot(f, up=-0.05*min(1,enter*2), fwd=0.34*min(1,enter), yaw=4*math.sin(2*math.pi*t*3)*enter)
        kr('Spine_A',f, rx=12*min(1,enter*2)); kr('Spine_B',f, rx=12*min(1,enter*2))
        kr('Head_0',f, rx=16)
        kr('Nose',f, rx=8*max(0,math.sin(2*math.pi*t*4)))
        # bacaklar surunme: on cek, arka it (dunya-X)
        push=math.sin(2*math.pi*t*4)
        for leg in ('FL','FR'): kwx(LEGR[leg],f, -10*enter); kwx(LEGM[leg],f, 22+8*push)
        for leg in ('RL','RR'): kwx(LEGR[leg],f, 12*push*enter); kwx(LEGM[leg],f, 18+10*max(0,push))
        # kuyruk: once arkada surunur, son %15'te hizla iceri kivrilir
        tin=max(0,(t-0.85)/0.15)
        ktail(f,t, side=8*(1-tin), up=3, freq=0.8, curl=40*tin)
    return a,N,False

# ============ 7 HOLE_PANIC ============
def hole_panic():
    a=newact("hole_panic"); N=50
    for f in range(1,N+2,2):
        t=(f-1)/N
        enter=max(0,(t-0.1)/0.7)
        kroot(f, up=-0.06*min(1,enter*3), fwd=0.40*min(1,enter*1.1), yaw=8*math.sin(2*math.pi*t*5)*enter)  # hizli + kivrilarak
        kr('Spine_A',f, rx=14*min(1,enter*2)); kr('Spine_B',f, rx=14*min(1,enter*2))
        kr('Head_0',f, rx=18)
        kr('bone_6',f, rz=-16); kr('bone_7',f, rz=16)    # kulak geri (panik)
        push=math.sin(2*math.pi*t*7)
        for leg in ('FL','FR'): kwx(LEGR[leg],f, -12*enter); kwx(LEGM[leg],f, 26+10*push)
        for leg in ('RL','RR'): kwx(LEGR[leg],f, 16*push*enter); kwx(LEGM[leg],f, 22+14*max(0,push))
        tin=max(0,(t-0.8)/0.2)
        ktail(f,t, side=14*(1-tin), up=4, freq=1.6, curl=55*tin)   # whip sonra hizla iceri
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
print("CLIPS", [c[0].name for c in clips])
import os as _os
from pathlib import Path
Path(outblend).with_suffix(".animation_manifest.json").write_text(json.dumps({"fps":FPS,"clips":man},indent=2))
bpy.ops.wm.save_as_mainfile(filepath=_os.path.abspath(outblend))
print("ANIM_DONE")
