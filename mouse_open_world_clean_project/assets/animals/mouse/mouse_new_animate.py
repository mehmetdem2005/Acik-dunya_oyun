#!/usr/bin/env python3
"""Yeni fare rig (32 kemik) icin 7 animasyon. Dunya-ekseni quaternion (twist yok),
puruzsuz omurga (5 seg), SKILL kuyruk dalgasi (delay=0.1 + uca falloff -> tek nazik egri),
dolu ama anatomik bacak (notr poz oldugundan gerilmez). Hepsinde dogal kuyruk.
blender --background <rigged.blend> --python mouse_new_animate.py -- <out.blend> [fps]
"""
import bpy, sys, os, math
from mathutils import Quaternion, Vector
argv=sys.argv[sys.argv.index("--")+1:]
outblend=argv[0]; FPS=int(argv[1]) if len(argv)>1 else 30
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); bpy.context.view_layer.objects.active=arm
R=math.radians
TAIL=[f"Tail_{i:02d}" for i in range(12)]
SPX=[f"SpineX_{i}" for i in range(5)]      # 0=pelvis(+Y arka), 4=boyun(-Y on)
LEGUP={'FL':'LegFL_up','FR':'LegFR_up','RL':'LegRL_up','RR':'LegRR_up'}
LEGLO={'FL':'LegFL_lo','FR':'LegFR_lo','RL':'LegRL_lo','RR':'LegRR_lo'}
LEGFT={'FL':'LegFL_ft','FR':'LegFR_ft','RL':'LegRL_ft','RR':'LegRR_ft'}
_M3=arm.matrix_world.to_3x3()
def _bl(n):
    pb=arm.pose.bones[n]; return (_M3@pb.bone.matrix_local.to_3x3()).inverted()
_BL={b.name:_bl(b.name) for b in arm.pose.bones}
def kw(n,f,rx=0,ry=0,rz=0):                # dunya-ekseni rotasyon (kombine)
    pb=arm.pose.bones.get(n)
    if not pb: return
    Bl=_BL[n]; q=Quaternion((1,0,0),0)
    if rz: q=Quaternion((Bl@Vector((0,0,1))).normalized(),R(rz))@q
    if rx: q=Quaternion((Bl@Vector((1,0,0))).normalized(),R(rx))@q
    if ry: q=Quaternion((Bl@Vector((0,1,0))).normalized(),R(ry))@q
    pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=q; pb.keyframe_insert('rotation_quaternion',frame=f)
def kroot(f,up=0,fwd=0,yaw=0,roll=0):
    pb=arm.pose.bones['Root']; Bl=_BL['Root']
    pb.location=Bl@Vector((0,-fwd,up)); pb.keyframe_insert('location',frame=f)
    q=Quaternion((Bl@Vector((0,0,1))).normalized(),R(yaw))@Quaternion((Bl@Vector((0,1,0))).normalized(),R(roll))
    pb.rotation_mode='QUATERNION'; pb.rotation_quaternion=q; pb.keyframe_insert('rotation_quaternion',frame=f)
def kspine(f,pitch=0,sway=0):              # 5 segmente puruzsuz dagit
    for n in SPX: kw(n,f, rx=pitch/5.0, rz=sway/5.0)
def head(f,pitch=0,turn=0,tilt=0):
    kw('Head_0',f, rx=pitch*0.6, rz=turn, ry=tilt); kw('Head_1',f, rx=pitch*0.4, rz=turn*0.4)
def nose(f,a): kw('Nose',f, rx=a)
def ears(f,L,Rr): kw('Ear_L',f, rz=-L); kw('Ear_R',f, rz=Rr)
# SKILL kuyruk dalgasi: kucuk delay + uca falloff -> tek nazik C-egri
def ktail(f,t,side=10,up=0,freq=1.0,curl=0,amp_mod=1.0):
    for i,tn in enumerate(TAIL):
        delay=i*0.1; fall=max(0.12,1.0-i*0.08); ph=2*math.pi*freq*t-delay
        kw(tn,f, rx=up*math.sin(ph*0.7)*fall + curl*(0.35+0.65*i/11),
                 rz=side*math.sin(ph)*fall*amp_mod)
DIAG={'FL':0.0,'RR':0.0,'FR':0.5,'RL':0.5}
def gait(f,t,swing=15,knee=16,lift=10,stance=0):
    for leg,ph in DIAG.items():
        p=(t+ph)%1.0; a=2*math.pi*p; sw=math.sin(a)
        kw(LEGUP[leg],f, rx=swing*sw+stance)
        kw(LEGLO[leg],f, rx=-(knee*0.35 + lift*max(0,sw)))
        kw(LEGFT[leg],f, rx=knee*0.3 + 6*max(0,sw))            # bilek telafi (ayak duz)
def newact(n):
    if arm.animation_data is None: arm.animation_data_create()
    if n in bpy.data.actions: bpy.data.actions.remove(bpy.data.actions[n])
    a=bpy.data.actions.new(n); a.use_fake_user=True; arm.animation_data.action=a; return a
def clearpose():
    for pb in arm.pose.bones: pb.location=(0,0,0); pb.rotation_quaternion=(1,0,0,0); pb.rotation_euler=(0,0,0)

# 1 IDLE
def idle():
    a=newact("idle"); N=120
    for f in range(1,N+2,2):
        t=(f-1)/N
        kroot(f, up=0.004*math.sin(2*math.pi*t*1.5), yaw=4*math.sin(2*math.pi*t*0.4), roll=2*math.sin(2*math.pi*t*0.3))
        kspine(f, pitch=2+1.5*math.sin(2*math.pi*t*1.5))
        tn=8*math.sin(2*math.pi*t*0.4); head(f, pitch=4*math.sin(2*math.pi*t*0.7+1), turn=tn, tilt=3*math.sin(2*math.pi*t*0.5))
        nose(f, 8*max(0,math.sin(2*math.pi*t*6)))
        e=18 if (int(t*5)%5==0) else 4; ears(f, e*0.5+4*math.sin(2*math.pi*t*0.9), e*0.5+4*math.sin(2*math.pi*t*1.1))
        ktail(f,t, side=8, up=3, freq=0.5, curl=4, amp_mod=0.8+0.4*math.sin(2*math.pi*t*0.6))
    return a,N,True

# 2 WALK
def walk():
    a=newact("walk"); N=32
    for f in range(1,N+2,2):
        t=(f-1)/N
        gait(f,t, swing=16, knee=18, lift=12)
        kroot(f, up=0.006*abs(math.sin(2*math.pi*t*2)), yaw=5*math.sin(2*math.pi*t), roll=3*math.sin(2*math.pi*t))
        kspine(f, pitch=3, sway=7*math.sin(2*math.pi*t))
        head(f, pitch=5, turn=4*math.sin(2*math.pi*t*0.5), tilt=-2*math.sin(2*math.pi*t*2))
        nose(f, 5*max(0,math.sin(2*math.pi*t*3)))
        ears(f, 6+3*math.sin(2*math.pi*t*2), 6-3*math.sin(2*math.pi*t*2))
        ktail(f,t, side=12, up=4, freq=1.0, curl=3)
    return a,N,True

# 3 SNEAK
def sneak():
    a=newact("sneak"); N=64
    for f in range(1,N+2,2):
        t=(f-1)/N
        gait(f,t, swing=10, knee=22, lift=7, stance=8)   # alcak: diz bukuk
        kroot(f, up=-0.03+0.003*math.sin(2*math.pi*t*2), yaw=4*math.sin(2*math.pi*t*0.7))
        kspine(f, pitch=12, sway=4*math.sin(2*math.pi*t))
        head(f, pitch=10, turn=8*math.sin(2*math.pi*t*0.6))
        nose(f, 9*max(0,math.sin(2*math.pi*t*5)))
        ears(f, 14+4*math.sin(2*math.pi*t*1.3), 14-4*math.sin(2*math.pi*t*1.3))
        ktail(f,t, side=6, up=2, freq=0.6, curl=3, amp_mod=0.7)
    return a,N,True

# 4 ATTACK
def attack():
    a=newact("attack"); N=26
    KF={1:(0,0,4,0,4,2,(0,6,2)), 7:(0.01,0.02,-10,0,-16,-10,(-8,-6,-4)),
        12:(0.02,0.10,16,12,-18,6,(6,14,0)), 17:(0.01,0.11,12,4,-12,4,(2,10,0)), 26:(0,0,4,0,4,2,(0,6,2))}
    for f,(up,fwd,hd,nse,ear,sp,tl) in KF.items():
        kroot(f, up=up, fwd=fwd); head(f, pitch=hd); nose(f, nse); ears(f, ear*0.4, ear*0.4); kspine(f, pitch=sp)
        sb,whip,curl=tl
        for i,tn in enumerate(TAIL):
            fall=max(0.12,1.0-i*0.08); kw(tn,f, rx=curl*(0.35+0.65*i/11), rz=(sb+whip*i/11)*fall)
        lunge=-22 if fwd>0.05 else (6 if fwd<0 else 0)
        for leg in ('FL','FR'): kw(LEGUP[leg],f, rx=lunge); kw(LEGLO[leg],f, rx=-12 if fwd>0.05 else 0)
    return a,N,False

# 5 EAT — oturur, on patiler agza, kemirme
def eat():
    a=newact("eat"); N=120
    for f in range(1,N+2,3):
        t=(f-1)/N; nib=math.sin(2*math.pi*t*7)
        kroot(f, up=0.005, roll=2*math.sin(2*math.pi*t*0.5))
        kspine(f, pitch=8)                                   # hafif dik oturus
        head(f, pitch=10+6*nib, turn=3*math.sin(2*math.pi*t*0.4))
        nose(f, 7*abs(nib))
        if int(t*4)%4==2: head(f, pitch=-4, turn=10)
        ears(f, 6+4*math.sin(2*math.pi*t*0.6), 6-4*math.sin(2*math.pi*t*0.6))
        for leg in ('FL','FR'): kw(LEGUP[leg],f, rx=-30); kw(LEGLO[leg],f, rx=-40+8*abs(nib))  # patiler agza
        ktail(f,t, side=5, up=2, freq=0.4, curl=12, amp_mod=0.6)
    return a,N,True

# 6 HOLE_SLOW — surunerek girer
def hole_slow():
    a=newact("hole_slow"); N=120
    for f in range(1,N+2,3):
        t=(f-1)/N; enter=max(0,(t-0.15)/0.7)
        kroot(f, up=-0.04*min(1,enter*2), fwd=0.30*min(1,enter), yaw=4*math.sin(2*math.pi*t*3)*enter)
        kspine(f, pitch=12*min(1,enter*2), sway=5*math.sin(2*math.pi*t*2)*enter)
        head(f, pitch=14); nose(f, 8*max(0,math.sin(2*math.pi*t*4)))
        push=math.sin(2*math.pi*t*4)
        for leg in ('FL','FR'): kw(LEGUP[leg],f, rx=-12*enter); kw(LEGLO[leg],f, rx=-(10+8*max(0,push)))
        for leg in ('RL','RR'): kw(LEGUP[leg],f, rx=10*push*enter); kw(LEGLO[leg],f, rx=-(12+10*max(0,push)))
        tin=max(0,(t-0.85)/0.15); ktail(f,t, side=7*(1-tin), up=3, freq=0.8, curl=30*tin)
    return a,N,False

# 7 HOLE_PANIC — hizli dalis
def hole_panic():
    a=newact("hole_panic"); N=46
    for f in range(1,N+2,2):
        t=(f-1)/N; enter=max(0,(t-0.1)/0.7)
        kroot(f, up=-0.05*min(1,enter*3), fwd=0.34*min(1,enter*1.1), yaw=8*math.sin(2*math.pi*t*5)*enter)
        kspine(f, pitch=16*min(1,enter*2), sway=7*math.sin(2*math.pi*t*4)*enter)
        head(f, pitch=16); ears(f, -14, 14)
        push=math.sin(2*math.pi*t*7)
        for leg in ('FL','FR'): kw(LEGUP[leg],f, rx=-16*enter); kw(LEGLO[leg],f, rx=-(14+10*max(0,push)))
        for leg in ('RL','RR'): kw(LEGUP[leg],f, rx=16*push*enter); kw(LEGLO[leg],f, rx=-(14+12*max(0,push)))
        tin=max(0,(t-0.8)/0.2); ktail(f,t, side=13*(1-tin), up=4, freq=1.6, curl=44*tin)
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
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend)); print("ANIM_NEW_DONE")
