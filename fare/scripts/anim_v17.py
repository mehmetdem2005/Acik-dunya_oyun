"""
v17 animations — Walk, Run, Idle, Sniff (adapted to v17 bone names).
Foot-lock locomotion via IK targets (CTRL_ik_F/B L/R), same proven method.
"""
import bpy, os, sys, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as Lib

IN_BLEND = os.path.join(Lib.OUT_DIR, "mouse_v17.blend")
OUT_BLEND = os.path.join(Lib.OUT_DIR, "mouse_anim17.blend")
OUT_GLB = os.path.join(Lib.OUT_DIR, "mouse_anim.glb")
def log(m): print(f"[anim] {m}", flush=True)
def deg(x): return math.radians(x)


class Rig:
    def __init__(self, arm):
        self.arm=arm; self.pb=arm.pose.bones; self.ik_rest={}
        for n in ("CTRL_ik_FL","CTRL_ik_FR","CTRL_ik_BL","CTRL_ik_BR"):
            if n in self.pb:
                self.ik_rest[n]=(arm.matrix_world @ self.pb[n].bone.matrix_local).translation.copy()
    def key_ik(self,name,delta,frame):
        if name not in self.pb: return
        pbone=self.pb[name]; m=pbone.matrix.copy(); m.translation=self.ik_rest[name]+delta
        pbone.matrix=m; bpy.context.view_layer.update()
        pbone.keyframe_insert("location",frame=frame)
    def key_rot(self,name,xyz,frame):
        if name not in self.pb: return
        b=self.pb[name]; b.rotation_mode='XYZ'
        b.rotation_euler=(deg(xyz[0]),deg(xyz[1]),deg(xyz[2])); b.keyframe_insert("rotation_euler",frame=frame)
    def key_prop(self,prop,val,frame):
        if prop not in self.arm: return
        self.arm[prop]=val; self.arm.keyframe_insert(data_path=f'["{prop}"]',frame=frame)
    def reset(self):
        for b in self.pb:
            b.rotation_mode='XYZ'; b.rotation_euler=(0,0,0); b.location=(0,0,0); b.scale=(1,1,1)


def new_action(arm,name):
    if arm.animation_data is None: arm.animation_data_create()
    a=bpy.data.actions.new(name); arm.animation_data.action=a; return a
def finalize(arm,cyclic=True):
    for fc in arm.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation='BEZIER'
        if cyclic:
            for m in list(fc.modifiers): fc.modifiers.remove(m)
            md=fc.modifiers.new('CYCLES'); md.mode_before='REPEAT'; md.mode_after='REPEAT'

def foot_delta(phase,stride=0.05,lift=0.045,swing=0.30):
    phase%=1.0
    if phase<(1-swing):
        t=phase/(1-swing); return Vector((0,-stride/2+stride*t,0))
    t=(phase-(1-swing))/swing
    return Vector((0,stride/2-stride*t,lift*math.sin(math.pi*t)))


def make_walk(rig,frames=32):
    new_action(rig.arm,"Walk"); rig.reset()
    ph={"CTRL_ik_BL":0.0,"CTRL_ik_FL":0.25,"CTRL_ik_BR":0.5,"CTRL_ik_FR":0.75}
    nk=12
    for i in range(nk+1):
        fr=1+i*frames/nk; c=i/nk
        for ik,p in ph.items(): rig.key_ik(ik,foot_delta(c+p,0.05,0.045),fr)
    for f,(h,c) in [(1,(0,0)),(1+frames*0.25,(2,-1)),(1+frames*0.5,(0,0)),
                    (1+frames*0.75,(-2,1)),(1+frames,(0,0))]:
        rig.key_rot("COG",(0,h,0),f); rig.key_rot("thoracic_01",(0,c,0),f)
    for i,nm in enumerate(["lumbar_02","thoracic_01","cervical_01"]):
        for f,rz in [(1,1.5),(1+frames*0.5,-1.5),(1+frames,1.5)]:
            rig.key_rot(nm,(0,0,rz*(1 if i%2 else -1)),f+i)
    for i,nm in enumerate(["tail_02","tail_04","tail_05","tail_06"]):
        d=i*1.5
        for f,rz in [(1+d,4),(1+frames*0.5+d,-4),(1+frames+d,4)]:
            rig.key_rot(nm,(0,0,rz),((f-1)%frames)+1)
    rig.key_prop("breath",0.0,1); rig.key_prop("breath",0.5,1+frames*0.5); rig.key_prop("breath",0.0,1+frames)
    finalize(rig.arm); log("Walk done")


def make_run(rig,frames=16):
    new_action(rig.arm,"Run"); rig.reset()
    ph={"CTRL_ik_BL":0.0,"CTRL_ik_BR":0.12,"CTRL_ik_FL":0.5,"CTRL_ik_FR":0.62}
    nk=10
    for i in range(nk+1):
        fr=1+i*frames/nk; c=i/nk
        for ik,p in ph.items(): rig.key_ik(ik,foot_delta(c+p,0.085,0.07,0.45),fr)
    for f,st in [(1,0),(1+frames*0.25,1),(1+frames*0.5,0),(1+frames*0.75,-0.6),(1+frames,0)]:
        rig.key_rot("lumbar_02",(st*9,0,0),f); rig.key_rot("thoracic_01",(-st*6,0,0),f)
    for i,nm in enumerate(["tail_02","tail_04","tail_05","tail_06"]):
        d=i
        for f,rx in [(1+d,-9),(1+frames*0.5+d,5),(1+frames+d,-9)]:
            rig.key_rot(nm,(rx,0,0),((f-1)%frames)+1)
    finalize(rig.arm); log("Run done")


def make_idle(rig,frames=60):
    new_action(rig.arm,"Idle"); rig.reset()
    rig.key_prop("breath",-0.3,1); rig.key_prop("breath",0.7,1+frames*0.5); rig.key_prop("breath",-0.3,1+frames)
    for f,rz in [(1,0),(1+frames*0.5,0.7),(1+frames,0)]: rig.key_rot("cervical_01",(0,0,rz),f)
    rig.key_prop("ear_L_perk",0.0,1); rig.key_prop("ear_L_perk",0.0,1+frames*0.6)
    rig.key_prop("ear_L_perk",0.8,1+frames*0.7); rig.key_prop("ear_L_perk",0.0,1+frames*0.8); rig.key_prop("ear_L_perk",0.0,1+frames)
    import random; random.seed(1)
    for side in ("L","R"):
        for f in (1,frames*0.3,frames*0.6,frames):
            rig.key_rot(f"whisker_pad_{side}",(random.uniform(-3,3),0,random.uniform(-3,3)),1+f if f else 1)
    finalize(rig.arm); log("Idle done")


def make_sniff(rig,frames=24):
    new_action(rig.arm,"Sniff"); rig.reset()
    for f,rx in [(1,0),(1+frames*0.3,7),(1+frames*0.6,4),(1+frames,0)]:
        rig.key_rot("cervical_01",(rx,0,0),f); rig.key_rot("snout",(rx*0.5,0,0),f)
    import random; random.seed(2)
    for side in ("L","R"):
        for f in range(1,frames+1,2):
            rig.key_rot(f"whisker_pad_{side}",(random.uniform(-5,5),random.uniform(-3,3),random.uniform(-5,5)),f)
    for f in range(1,frames+1,3): rig.key_rot("nose_tip",(random.uniform(-4,4),0,0),f)
    rig.key_prop("breath",0.0,1); rig.key_prop("breath",0.4,1+frames*0.5); rig.key_prop("breath",0.0,1+frames)
    finalize(rig.arm); log("Sniff done")


def main():
    bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    mesh=next(o for o in bpy.data.objects if o.type=='MESH')
    bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='POSE')
    rig=Rig(arm)
    for maker in (make_walk,make_run,make_idle,make_sniff):
        maker(rig); arm.animation_data.action.use_fake_user=True
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); mesh.select_set(True); bpy.context.view_layer.objects.active=arm
    try:
        bpy.ops.export_scene.gltf(filepath=OUT_GLB,export_format='GLB',use_selection=True,
            export_skins=True,export_animations=True,export_animation_mode='ACTIONS',
            export_force_sampling=True,export_yup=True)
        log(f"Saved {OUT_GLB}")
    except Exception as e: log(f"GLB fail {e}")
    log("DONE")

if __name__=="__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
