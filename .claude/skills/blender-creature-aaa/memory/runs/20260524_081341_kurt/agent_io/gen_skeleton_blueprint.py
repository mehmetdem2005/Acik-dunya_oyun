#!/usr/bin/env python3
"""P03 Skeleton Architect (kod formu) - Canis lupus full-anatomy rig blueprint uretir.
Koordinatlar: X=+sol/-sag, Y=+ileri, Z=+yukari, metre. Wolf +Y'ye bakar.
Cikti: SkeletonBlueprint.json (build_skeleton.py tuketir).
"""
import json, math, sys
from pathlib import Path

OUT = sys.argv[1] if len(sys.argv) > 1 else "SkeletonBlueprint.json"

bones = []          # deform
control_bones = []
twist_bones = []

def B(name, head, tail, parent=None, roll=0.0, connect=False, deform=True):
    bones.append({"name": name, "head_local": [round(c,4) for c in head],
                  "tail_local": [round(c,4) for c in tail], "roll_radians": roll,
                  "parent": parent, "use_connect": connect, "use_deform": deform})

def C(name, head, tail, parent=None):
    control_bones.append({"name": name, "head_local": [round(c,4) for c in head],
                          "tail_local": [round(c,4) for c in tail], "roll_radians": 0.0,
                          "parent": parent, "use_connect": False, "use_deform": False})

def T(name, head, tail, parent_bone, share=0.5):
    twist_bones.append({"name": name, "head_local": [round(c,4) for c in head],
                        "tail_local": [round(c,4) for c in tail], "roll_radians": 0.0,
                        "parent_bone": parent_bone, "twist_share": share, "use_deform": True})

# ---- root control ----
C("root", [0,0,0.02], [0,0,0.18], None)

# ---- spine (rear -> front) ----
B("sacrum",        [0,-0.40,0.580],[0,-0.34,0.585], "root")
B("spine_lumbar",  [0,-0.34,0.585],[0,-0.14,0.600], "sacrum", connect=True)
B("spine_thorax",  [0,-0.14,0.600],[0, 0.10,0.615], "spine_lumbar", connect=True)
B("spine_chest",   [0, 0.10,0.615],[0, 0.30,0.620], "spine_thorax", connect=True)
B("spine_shoulder",[0, 0.30,0.620],[0, 0.40,0.630], "spine_chest", connect=True)
# neck
B("neck_1",[0,0.40,0.630],[0,0.47,0.690], "spine_shoulder", connect=True)
B("neck_2",[0,0.47,0.690],[0,0.53,0.760], "neck_1", connect=True)
B("neck_3",[0,0.53,0.760],[0,0.575,0.800],"neck_2", connect=True)
# head + jaw + ears
B("head",[0,0.575,0.800],[0,0.720,0.780], "neck_3", connect=True)
B("jaw", [0,0.600,0.760],[0,0.710,0.730], "head")
B("ear_L",[ 0.045,0.585,0.840],[ 0.060,0.550,0.920],"head")
B("ear_R",[-0.045,0.585,0.840],[-0.060,0.550,0.920],"head")

# ---- tail (12 segments, gentle droop) ----
TAIL_N = 12
prev = "sacrum"
y0, z0 = -0.40, 0.580
for i in range(TAIL_N):
    t0 = i/TAIL_N; t1 = (i+1)/TAIL_N
    y_a = y0 - 0.42*t0; y_b = y0 - 0.42*t1
    z_a = z0 - 0.20*t0;  z_b = z0 - 0.20*t1
    nm = f"tail_{i}"
    B(nm, [0,round(y_a,4),round(z_a,4)], [0,round(y_b,4),round(z_b,4)], prev, connect=(i>0))
    prev = nm

# ---- legs (mirrored): s=+1 -> _L (+X), s=-1 -> _R (-X) ----
def leg(side, suf):
    s = side
    # FRONT
    B(f"scapula_{suf}",   [s*0.050,0.30,0.605],[s*0.100,0.30,0.460], "spine_shoulder")
    B(f"upper_arm_{suf}", [s*0.100,0.30,0.460],[s*0.105,0.34,0.290], f"scapula_{suf}", connect=True)
    B(f"forearm_{suf}",   [s*0.105,0.34,0.290],[s*0.100,0.30,0.130], f"upper_arm_{suf}", connect=True)
    B(f"front_paw_{suf}", [s*0.100,0.30,0.130],[s*0.100,0.37,0.020], f"forearm_{suf}", connect=True)
    B(f"front_toe_{suf}", [s*0.100,0.37,0.020],[s*0.100,0.43,0.000], f"front_paw_{suf}", connect=True)
    # REAR
    B(f"pelvis_{suf}",    [s*0.050,-0.36,0.580],[s*0.100,-0.30,0.500], "sacrum")
    B(f"thigh_{suf}",     [s*0.100,-0.30,0.500],[s*0.110,-0.22,0.330], f"pelvis_{suf}", connect=True)
    B(f"shin_{suf}",      [s*0.110,-0.22,0.330],[s*0.110,-0.32,0.170], f"thigh_{suf}", connect=True)
    B(f"metatarsus_{suf}",[s*0.110,-0.32,0.170],[s*0.110,-0.27,0.020], f"shin_{suf}", connect=True)
    B(f"rear_toe_{suf}",  [s*0.110,-0.27,0.020],[s*0.110,-0.21,0.000], f"metatarsus_{suf}", connect=True)
    # TWIST (3 per side)
    T(f"upperarm_twist_{suf}",[s*0.100,0.30,0.460],[s*0.105,0.34,0.290], f"upper_arm_{suf}")
    T(f"forearm_twist_{suf}", [s*0.105,0.34,0.290],[s*0.100,0.30,0.130], f"forearm_{suf}")
    T(f"shin_twist_{suf}",    [s*0.110,-0.22,0.330],[s*0.110,-0.32,0.170], f"shin_{suf}")
    # CONTROLS: foot IK + poles
    C(f"foot_ik_front_{suf}",[s*0.100,0.37,0.000],[s*0.100,0.47,0.000], "root")
    C(f"foot_ik_rear_{suf}", [s*0.110,-0.27,0.000],[s*0.110,-0.17,0.000], "root")
    C(f"elbow_pole_{suf}",   [s*0.110,0.05,0.300],[s*0.110,0.05,0.400], "root")
    C(f"knee_pole_{suf}",    [s*0.110,0.05,0.330],[s*0.110,0.05,0.430], "root")

leg(+1,"L"); leg(-1,"R")
C("head_target",[0,0.95,0.80],[0,1.05,0.80],"root")

ik_chains = []
for suf in ("L","R"):
    ik_chains.append({"chain_id":f"front_{suf}","end_bone":f"front_paw_{suf}",
        "ik_target_bone":f"foot_ik_front_{suf}","pole_target_bone":f"elbow_pole_{suf}",
        "chain_length":3,"pole_angle_radians":-math.pi/2})
    ik_chains.append({"chain_id":f"rear_{suf}","end_bone":f"metatarsus_{suf}",
        "ik_target_bone":f"foot_ik_rear_{suf}","pole_target_bone":f"knee_pole_{suf}",
        "chain_length":3,"pole_angle_radians":-math.pi/2})

deform_names = [b["name"] for b in bones]
collections = {
    "spine":[n for n in deform_names if n.startswith(("sacrum","spine","neck"))],
    "head":["head","jaw","ear_L","ear_R","head_target"],
    "tail":[n for n in deform_names if n.startswith("tail_")],
    "legs_front":[n for n in deform_names if n.startswith(("scapula","upper_arm","forearm","front_"))],
    "legs_rear":[n for n in deform_names if n.startswith(("pelvis","thigh","shin","metatarsus","rear_"))],
    "twist":[b["name"] for b in twist_bones],
    "controls":[c["name"] for c in control_bones],
}

blueprint = {
    "blueprint_version":"1.0","creature_id":"kurt_001","scientific_name":"Canis lupus",
    "anatomy_class":"mammalia_quadruped","stance":"digitigrade","body_length_meters":0.80,
    "bone_naming_convention":"underscore_LR","up_axis":"Z","forward_axis":"Y",
    "bones":bones,"control_bones":control_bones,"twist_bones":twist_bones,
    "ik_chains":ik_chains,"bone_collections":collections,
    "counts":{"deform":len(bones),"twist":len(twist_bones),"control":len(control_bones),
              "total":len(bones)+len(twist_bones)+len(control_bones)},
}

Path(OUT).write_text(json.dumps(blueprint, indent=2, ensure_ascii=False))
print(f"OK blueprint -> {OUT}")
print(f"deform={len(bones)} twist={len(twist_bones)} control={len(control_bones)} total={blueprint['counts']['total']} ik_chains={len(ik_chains)}")
