#!/usr/bin/env python3
"""Kurt koreografi animasyonlari: yurume / kosma / surunme / saldiri (cromel+arka-it+sicra+on-pati vur).
Hepsinde kuyruk animasyonu. foot_ik +Y (local~world), root +Z (localY=worldZ, localZ=-worldY).
blender --background <skinned.blend> --python wolf_animate.py -- <out.blend> [fps]
"""
import bpy, math, sys
from pathlib import Path
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
out=argv[0]; FPS=int(argv[1]) if len(argv)>1 else 30
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
bpy.context.view_layer.objects.active=arm
def R(d): return math.radians(d)
def has(n): return n in arm.pose.bones
def krot(n,f,rx=0,ry=0,rz=0):
    if not has(n): return
    pb=arm.pose.bones[n]; pb.rotation_mode='XYZ'; pb.rotation_euler=(R(rx),R(ry),R(rz)); pb.keyframe_insert('rotation_euler',frame=f)
def kfoot(n,f,wx=0,wy=0,wz=0):
    if not has(n): return
    pb=arm.pose.bones[n]; pb.location=(wx,wy,wz); pb.keyframe_insert('location',frame=f)
def kroot(f,wx=0,wy=0,wz=0,rx=0,ry=0,rz=0):
    pb=arm.pose.bones['root']; pb.location=(wx,wz,-wy); pb.keyframe_insert('location',frame=f)
    pb.rotation_mode='XYZ'; pb.rotation_euler=(R(rx),R(ry),R(rz)); pb.keyframe_insert('rotation_euler',frame=f)
TAIL=[f'tail_{i}' for i in range(12)]
def ktail(f,base_pitch=0,side=0,wave=0,phase=0):
    # base_pitch: + asagi / - yukari ; tip'e dogru azalan, dalga rideli
    for i,tn in enumerate(TAIL):
        dec=0.9**i
        rx=base_pitch*dec + wave*math.sin(phase - i*0.5)*dec*0.5
        rz=side*dec + wave*math.cos(phase - i*0.6)*dec
        krot(tn,f,rx,0,rz)
SPINE=['spine_lumbar','spine_thorax','spine_chest']
def kspine(f,pitch=0,roll=0):
    for j,s in enumerate(SPINE): krot(s,f,pitch*(0.8 if j else 1.0),0,roll)
def reset(f=1):
    for pb in arm.pose.bones:
        pb.location=(0,0,0); pb.rotation_mode='XYZ'; pb.rotation_euler=(0,0,0)
        pb.keyframe_insert('location',frame=f); pb.keyframe_insert('rotation_euler',frame=f)
def newact(name):
    if arm.animation_data is None: arm.animation_data_create()
    if name in bpy.data.actions: bpy.data.actions.remove(bpy.data.actions[name])
    a=bpy.data.actions.new(name); a.use_fake_user=True; arm.animation_data.action=a; return a

FRONT=['foot_ik_front_L','foot_ik_front_R']; REAR=['foot_ik_rear_L','foot_ik_rear_R']
def foot_cycle(p,stride,lift):
    p=p%1.0
    if p<0.4:
        u=p/0.4; return (-stride/2+stride*u, lift*math.sin(u*math.pi))
    u=(p-0.4)/0.6; return (stride/2-stride*u, 0.0)

# ============ WALK ============
def clip_walk():
    a=newact("walk"); N=30
    ph={'foot_ik_front_L':0.0,'foot_ik_rear_R':0.25,'foot_ik_front_R':0.5,'foot_ik_rear_L':0.75}
    for f in range(1,N+2,2):
        t=(f-1)/N
        for fb in FRONT+REAR:
            y,z=foot_cycle(t+ph[fb],0.12,0.055); kfoot(fb,f,0,y,z)
        kroot(f, 0,0, 0.008*abs(math.sin(2*2*math.pi*t)), 0,0, 3*math.sin(2*math.pi*t))
        krot('neck_1',f, 4*math.sin(2*math.pi*t+1),0,0); krot('head',f, -3*math.sin(2*2*math.pi*t),0,0)
        ktail(f, base_pitch=-8, side=10, wave=9, phase=2*math.pi*t)
    return a,N

# ============ RUN (gallop) ============
def clip_run():
    a=newact("run"); N=16
    ph={'foot_ik_rear_L':0.0,'foot_ik_rear_R':0.10,'foot_ik_front_L':0.48,'foot_ik_front_R':0.58}
    for f in range(1,N+2,2):
        t=(f-1)/N
        for fb in FRONT+REAR:
            y,z=foot_cycle(t+ph[fb],0.22,0.10); kfoot(fb,f,0,y,z)
        kroot(f, 0,0, 0.05*max(0,math.sin(2*math.pi*t+0.5)), -4*math.sin(2*math.pi*t),0,0)
        kspine(f, 6*math.sin(2*math.pi*t),0)
        krot('neck_1',f, -6,0,0); krot('head',f, -4,0,0)
        ktail(f, base_pitch=-16, side=4, wave=12, phase=2*math.pi*t*1.5)
    return a,N

# ============ CRAWL / SURUNME ============
def clip_crawl():
    a=newact("crawl"); N=40
    ph={'foot_ik_front_L':0.0,'foot_ik_rear_R':0.25,'foot_ik_front_R':0.5,'foot_ik_rear_L':0.75}
    for f in range(1,N+2,2):
        t=(f-1)/N
        for fb in FRONT+REAR:
            y,z=foot_cycle(t+ph[fb],0.06,0.018)
            sx=0.03 if fb.endswith('_L') else -0.03  # bacaklar yana acik
            kfoot(fb,f,sx,y,z)
        kroot(f, 0,0, -0.16+0.006*math.sin(2*math.pi*t), 0,0, 2*math.sin(2*math.pi*t))
        kspine(f, 4, 3*math.sin(2*math.pi*t))
        krot('neck_1',f, 16,0,0); krot('neck_2',f,10,0,0); krot('head',f, 10,0,0)
        ktail(f, base_pitch=14, side=12, wave=6, phase=2*math.pi*t*0.5)
    return a,N

# ============ ATTACK (cromel -> arka it -> sicra -> on pati vur -> toparla) ============
def clip_attack():
    a=newact("attack"); N=48
    # frame: (rootwx? sadece wy,wz + rot, front feet (y,z), rear feet (y,z), neck,head,jaw, spine, tail(base,wave))
    KF={
     1:  dict(rw=(0,0),fr=(0,0),re=(0,0),nk=0,hd=0,jw=0,sp=0,tl=(-6,0)),
     8:  dict(rw=(-0.04,-0.12),fr=(-0.02,0),re=(0.05,0),nk=14,hd=18,jw=0,sp=10,tl=(-34,0)),   # cromel
     14: dict(rw=(0.02,-0.05),fr=(-0.03,0),re=(-0.05,0),nk=10,hd=12,jw=5,sp=6,tl=(-26,0)),     # arka yukle/it
     20: dict(rw=(0.30,0.20),fr=(0.16,0.10),re=(-0.02,0.12),nk=4,hd=6,jw=20,sp=-6,tl=(-12,6)), # sicra apex
     26: dict(rw=(0.40,0.05),fr=(0.20,-0.02),re=(0.04,0.05),nk=10,hd=26,jw=38,sp=2,tl=(-22,12)),# vurus
     32: dict(rw=(0.42,-0.02),fr=(0.20,0),re=(-0.05,0),nk=8,hd=20,jw=16,sp=4,tl=(-4,6)),        # temas/inis
     40: dict(rw=(0.20,0),fr=(0.06,0),re=(-0.02,0),nk=2,hd=6,jw=4,sp=2,tl=(2,3)),               # toparla
     48: dict(rw=(0,0),fr=(0,0),re=(0,0),nk=0,hd=0,jw=0,sp=0,tl=(-6,0)),                        # neutral
    }
    for f,d in KF.items():
        wy,wz=d['rw']; kroot(f,0,wy,wz)
        for fb in FRONT: kfoot(fb,f,0,d['fr'][0],d['fr'][1])
        for fb in REAR: kfoot(fb,f,0,d['re'][0],d['re'][1])
        krot('neck_1',f,d['nk'],0,0); krot('neck_2',f,d['nk']*0.6,0,0); krot('head',f,d['hd'],0,0)
        krot('jaw',f,d['jw'],0,0); kspine(f,d['sp'],0)
        ktail(f, base_pitch=d['tl'][0], side=0, wave=d['tl'][1], phase=f*0.4)
    return a,N

clips=[clip_walk(),clip_run(),clip_crawl(),clip_attack()]
# NLA tracks (her klip ayri glTF animasyonu)
ad=arm.animation_data
while ad.nla_tracks: ad.nla_tracks.remove(ad.nla_tracks[0])
ad.action=None
manifest=[]
for act,n in clips:
    tr=ad.nla_tracks.new(); tr.name="NLA_"+act.name
    st=tr.strips.new(act.name,1,act);
    if act.name in ("walk","run","crawl"): st.repeat=1.0
    manifest.append({"name":act.name,"frame_start":1,"frame_end":n,"loop":act.name in ("walk","run","crawl")})
import json
Path(out).with_suffix(".animation_manifest.json").write_text(json.dumps({"fps":FPS,"clips":manifest,"total_actions":len(clips)},indent=2))
bpy.context.scene.render.fps=FPS
print("[animate] clips:", [c[0].name for c in clips])
Path(out).parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(Path(out).resolve()))
print("[animate] SAVED",out)
