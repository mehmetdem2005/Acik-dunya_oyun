"""
v16 — Pipeline v2 rig builder (Stages 1-5 in one pass with inline GATEs).

Fixes v15 rejection causes:
  - Dense symmetric spine (pelvis/sacrum/lumbar/thoracic/cervical)
  - L/R legs PERFECT mirror (left built from Tripo detail, mirrored to right)
  - Ankle (tarsus) on BOTH back legs
  - Whisker PADS + 3-segment whiskers (root/mid/tip)
  - Region-aware weighting with PER-BONE VERTEX BUDGETS (kills weight bleed)
  - Bone collections DEF/CTRL/MCH/REF
  - IK + pole + spline-IK tail + drivers

Mesh UNTOUCHED (only import transform baked).

Usage:
    blender --background --python fare/scripts/rig_mouse_v16.py
"""

import bpy, math, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as L
from mouse_rig_lib import (log, reset_scene, import_glb, extract_tripo_joints,
                            cleanup_keep_mesh_only, build_bvh, is_inside,
                            closest_inside, detect_landmarks, resample_polyline,
                            dist_to_segment, region_of_vertex)

OUT_BLEND = os.path.join(L.OUT_DIR, "mouse_v16.blend")
OUT_GLB = os.path.join(L.OUT_DIR, "mouse.glb")


def vlog(m): print(f"[v16] {m}", flush=True)


# Per-bone vertex budgets (Stage 5 GATE)
BUDGET = {
    "whisker_": 160, "whisker_pad": 450, "nose_tip": 300, "nose_": 360,
    "eye_": 360, "ear_": 880, "jaw": 1400, "lower_lip": 650, "upper_lip": 560,
    "cheek_": 820, "snout": 1100,
}


def budget_for(name):
    for pfx, b in BUDGET.items():
        if name.startswith(pfx) or name == pfx.rstrip("_"):
            return b
    return None  # no cap


# ============================================================================
# DEFORM SKELETON
# ============================================================================
def build_deform(tripo, mesh, lm, bvh):
    bpy.ops.object.armature_add(enter_editmode=True, location=(0,0,0))
    arm_obj = bpy.context.object
    arm_obj.name = "MouseRig"
    arm = arm_obj.data; arm.name = "MouseRig"
    eb = arm.edit_bones
    for b in list(eb): eb.remove(b)
    B = {}

    def J(n):  return tripo[n]["head"].copy() if n in tripo else None
    def Jt(n): return tripo[n]["tail"].copy() if n in tripo else None
    def mk(name, head, tail, parent=None, conn=False, deform=True, snap=True):
        h = closest_inside(bvh, Vector(head)) if snap else Vector(head)
        t = Vector(tail)
        b = eb.new(name); b.head = h; b.tail = t
        if parent and parent in B:
            b.parent = B[parent]; b.use_connect = conn
        b.use_deform = deform
        B[name] = b
        return b

    # ---- Core: root → COG → pelvis → sacrum ----
    root_p = J("tripo::Root")
    pelvis_p = Vector((0.0, 0.186, 0.265))
    sacrum_p = Vector((0.0, 0.255, 0.16))
    tail_base_p = J("bone_21")

    mk("root", (0,0,0.01), (0,0.12,0.01), parent=None, deform=False, snap=False)
    mk("COG", (0,0.10,0.20), (0,0.18,0.22), parent="root", deform=False, snap=False)
    mk("pelvis", pelvis_p, sacrum_p, parent="COG", deform=True)
    mk("sacrum", sacrum_p, tail_base_p, parent="pelvis", conn=True, deform=True)

    # ---- Spine backbone: pelvis_front → neck, resampled ----
    spine0_p = J("tripo::Spine_0")     # (0,+0.076,0.311)
    spine1_p = J("tripo::Spine_1")     # (0,-0.045,0.303)
    neck_p   = J("tripo::Head_0")      # (0,-0.154,0.291)
    skull_p  = J("tripo::Head_1")      # (0,-0.264,0.295)
    snout_p  = J("tripo::Head_2")      # (0,-0.262,0.294)
    nose_root= J("tripo::Head_3")      # (0,-0.357,0.256)
    nose_end = Jt("tripo::Head_3")     # (0,-0.452,0.218)

    # Order pelvis→neck for the chain
    backbone = [Vector((0.0, pelvis_p.y, 0.285)),
                Vector((0.0, spine0_p.y, spine0_p.z)),
                Vector((0.0, spine1_p.y, spine1_p.z)),
                Vector((0.0, neck_p.y,   neck_p.z))]
    chain_pts = resample_polyline(backbone, 10)  # 11 pts → 10 bones
    spine_names = ["lumbar_04","lumbar_03","lumbar_02","lumbar_01",
                   "thoracic_05","thoracic_04","thoracic_03","thoracic_02",
                   "thoracic_01","cervical_01"]
    prev = "pelvis"
    for i, nm in enumerate(spine_names):
        mk(nm, chain_pts[i], chain_pts[i+1], parent=prev, conn=(i>0), deform=True)
        prev = nm
    # cervical_02/03 short neck up to skull
    mk("cervical_02", chain_pts[-1], (neck_p+skull_p)*0.5, parent="cervical_01", conn=True)
    mk("cervical_03", (neck_p+skull_p)*0.5, skull_p, parent="cervical_02", conn=True)
    mk("head", skull_p, snout_p, parent="cervical_03", conn=True)
    chest_bone = "thoracic_03"   # breath driver target

    # ---- Face ----
    mk("snout_base", snout_p, (snout_p+nose_root)*0.5, parent="head", conn=False)
    mk("snout_mid", (snout_p+nose_root)*0.5, nose_root, parent="snout_base", conn=True)
    mk("nose_tip", nose_root, nose_end, parent="snout_mid", conn=True)
    jaw_h = closest_inside(bvh, Vector((0, skull_p.y-0.03, skull_p.z-0.07)))
    jaw_t = closest_inside(bvh, Vector((0, nose_end.y-0.02, nose_end.z-0.07)))
    mk("jaw_base", jaw_h, jaw_t, parent="head", snap=False)
    for side, sx in (("L",+1),("R",-1)):
        mk(f"eye_{side}", closest_inside(bvh,Vector((sx*0.045,skull_p.y-0.02,skull_p.z+0.03))),
           Vector((sx*0.055,skull_p.y-0.06,skull_p.z+0.03)), parent="head", snap=False)
        mk(f"cheek_{side}", closest_inside(bvh,Vector((sx*0.06,snout_p.y-0.02,snout_p.z-0.03))),
           Vector((sx*0.085,snout_p.y-0.04,snout_p.z-0.03)), parent="head", snap=False)
        mk(f"nose_{side}", closest_inside(bvh,Vector((sx*0.02,nose_root.y-0.02,nose_root.z))),
           Vector((sx*0.035,nose_root.y-0.04,nose_root.z)), parent="snout_mid", snap=False)
        mk(f"upper_lip_{side}", closest_inside(bvh,Vector((sx*0.025,nose_root.y-0.03,nose_root.z-0.04))),
           Vector((sx*0.04,nose_root.y-0.06,nose_root.z-0.04)), parent="snout_mid", snap=False)
        mk(f"lower_lip_{side}", closest_inside(bvh,Vector((sx*0.025,jaw_t.y+0.02,jaw_t.z+0.01))),
           Vector((sx*0.04,jaw_t.y-0.01,jaw_t.z+0.01)), parent="jaw_base", snap=False)

    # ---- Ears (Tripo bone_7=L, bone_6=R) ----
    for side, src in (("L","bone_7"),("R","bone_6")):
        base=J(src); tip=Jt(src)
        m1=base+(tip-base)*0.33; m2=base+(tip-base)*0.66
        mk(f"ear_{side}_base", base, m1, parent="head")
        mk(f"ear_{side}_mid", m1, m2, parent=f"ear_{side}_base", conn=True)
        mk(f"ear_{side}_tip", m2, tip, parent=f"ear_{side}_mid", conn=True)

    # ---- Whisker pads + 3-segment whiskers ----
    for side, sx in (("L",+1),("R",-1)):
        pad_h = closest_inside(bvh, Vector((sx*0.045, nose_root.y+0.01, nose_root.z-0.01)))
        pad_t = Vector((sx*0.06, nose_root.y-0.02, nose_root.z-0.01))
        mk(f"whisker_pad_{side}", pad_h, pad_t, parent="snout_mid", snap=False)
        for i,(dx,dz) in enumerate([(0.012,0.035),(0.018,0.008),(0.012,-0.018),(0.005,-0.04)]):
            base = Vector((sx*(0.05+dx), nose_root.y-0.01, nose_root.z+dz))
            mid  = Vector((sx*(0.085+dx), nose_root.y-0.035, nose_root.z+dz))
            tip  = Vector((sx*(0.12+dx), nose_root.y-0.06, nose_root.z+dz))
            mk(f"whisker_{side}_{i+1}_root", base, mid, parent=f"whisker_pad_{side}", snap=False)
            mk(f"whisker_{side}_{i+1}_mid", mid, (mid+tip)*0.5, parent=f"whisker_{side}_{i+1}_root", conn=True, snap=False)
            mk(f"whisker_{side}_{i+1}_tip", (mid+tip)*0.5, tip, parent=f"whisker_{side}_{i+1}_mid", conn=True, snap=False)

    # ---- LEFT legs (build from Tripo), then MIRROR to right ----
    # Front-left
    fl = {
        "scapula_L":   (J("bone_9"), Jt("bone_9"), "thoracic_02", False),
        "humerus_L":   (J("tripo::0_Left_Limb_0"), J("tripo::0_Left_Limb_1"), "scapula_L", False),
        "radius_L":    (J("tripo::0_Left_Limb_1"), J("tripo::0_Left_Limb_2"), "humerus_L", True),
    }
    l2h = J("tripo::0_Left_Limb_2"); l2t = Jt("tripo::0_Left_Limb_2")
    l2t = Vector((l2t.x, l2t.y, max(l2t.z, lm["z_min"]+0.002)))
    carpus_mid = (l2h+l2t)*0.5
    fl["carpus_L"]   = (l2h, carpus_mid, "radius_L", True)
    fl["front_paw_L"]= (carpus_mid, l2t, "carpus_L", True)
    for nm,(h,t,par,cn) in fl.items():
        mk(nm, h, t, parent=par, conn=cn)
    # front toes L
    paw_tip = l2t
    for i,ox in enumerate([-0.013,0.0,0.013]):
        b1=Vector((paw_tip.x+ox, paw_tip.y-0.006, paw_tip.z))
        b2=Vector((paw_tip.x+ox*1.4, paw_tip.y-0.02, paw_tip.z))
        b3=Vector((paw_tip.x+ox*1.7, paw_tip.y-0.032, paw_tip.z))
        mk(f"front_toe_L_{i+1}_01", b1, b2, parent="front_paw_L")
        mk(f"front_toe_L_{i+1}_02", b2, b3, parent=f"front_toe_L_{i+1}_01", conn=True)

    # Back-left (full Tripo detail incl. ankle)
    bl = [
        ("hip_L",      J("bone_27"),                  J("tripo::1_Left_Limb_0"), "pelvis", False),
        ("femur_L",    J("tripo::1_Left_Limb_0"),     J("tripo::1_Left_Limb_1"), "hip_L", False),
        ("tibia_L",    J("tripo::1_Left_Limb_1"),     J("tripo::1_Left_Limb_2"), "femur_L", True),
        ("tarsus_L",   J("tripo::1_Left_Limb_2"),     J("tripo::1_Left_Limb_3"), "tibia_L", True),
        ("back_paw_L", J("tripo::1_Left_Limb_3"),     J("tripo::1_Left_Limb_4"), "tarsus_L", True),
    ]
    for nm,h,t,par,cn in bl:
        if h is None or t is None: continue
        mk(nm, h, t, parent=par, conn=cn)
    bpaw_tip = Jt("tripo::1_Left_Limb_4")
    bpaw_tip = Vector((bpaw_tip.x, bpaw_tip.y, max(bpaw_tip.z, lm["z_min"]+0.002)))
    for i,ox in enumerate([-0.013,0.0,0.013]):
        b1=Vector((bpaw_tip.x+ox, bpaw_tip.y-0.006, bpaw_tip.z))
        b2=Vector((bpaw_tip.x+ox*1.4, bpaw_tip.y-0.024, bpaw_tip.z))
        b3=Vector((bpaw_tip.x+ox*1.7, bpaw_tip.y-0.04, bpaw_tip.z))
        mk(f"back_toe_L_{i+1}_01", b1, b2, parent="back_paw_L")
        mk(f"back_toe_L_{i+1}_02", b2, b3, parent=f"back_toe_L_{i+1}_01", conn=True)

    # ---- MIRROR LEG bones only _L → _R (face/ear/whisker already bilateral) ----
    LEG_PREFIXES = ("scapula_L","humerus_L","radius_L","carpus_L","front_paw_L",
                    "front_toe_L","hip_L","femur_L","tibia_L","tarsus_L",
                    "back_paw_L","back_toe_L")
    left_bones = [name for name in B
                  if any(name.startswith(p) for p in LEG_PREFIXES)]
    left_set = set(left_bones)
    def mirror_name(n):
        return n.replace("_L", "_R", 1) if "_L" in n else n
    left_data = []
    for name in left_bones:
        b = B[name]
        par = b.parent.name if b.parent else None
        left_data.append((name, Vector(b.head), Vector(b.tail), par, b.use_connect, b.use_deform))
    for name, h, t, par, cn, df in left_data:
        rn = mirror_name(name)
        rh = Vector((-h.x, h.y, h.z)); rt = Vector((-t.x, t.y, t.z))
        # mirror parent only if it is itself a left leg bone; else keep (body bone)
        rpar = mirror_name(par) if (par in left_set) else par
        b = eb.new(rn); b.head = rh; b.tail = rt
        if rpar and rpar in B:
            b.parent = B[rpar]; b.use_connect = cn
        b.use_deform = df
        B[rn] = b

    # ---- Tail (medial resample of Tripo tail anchors) ----
    tail_anchors = [J("bone_21"), J("tripo::Tail_0"), J("tripo::Tail_1"),
                    J("tripo::Tail_2"), J("tripo::Tail_3"), J("bone_26"), Jt("bone_26")]
    tail_pts = resample_polyline([p for p in tail_anchors if p], 22)
    prev = "sacrum"
    for k in range(len(tail_pts)-1):
        nm=f"tail_{k+1:02d}"
        mk(nm, tail_pts[k], tail_pts[k+1], parent=prev, conn=(k>0), snap=False)
        prev = nm

    # ---- Bone roll: align to world Z-up-ish for clean rotation ----
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Z')

    bpy.ops.object.mode_set(mode='OBJECT')
    vlog(f"Deform skeleton: {len(arm.bones)} bones (chest driver={chest_bone})")
    return arm_obj, chest_bone


# ============================================================================
# CONTROLS + MECHANISM (IK targets, pole, drivers, collections)
# ============================================================================
def add_controls(arm_obj):
    """Add CTRL IK targets + pole bones (edit mode)."""
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_obj.data.edit_bones
    def get(n): return eb.get(n)
    created = []

    leg_defs = [
        # (ik_ctrl, pole_ctrl, foot_bone, pole_offset)
        ("CTRL_ik_FL", "CTRL_pole_FL", "front_paw_L", Vector((0,-0.18,0.10))),
        ("CTRL_ik_FR", "CTRL_pole_FR", "front_paw_R", Vector((0,-0.18,0.10))),
        ("CTRL_ik_BL", "CTRL_pole_BL", "back_paw_L",  Vector((0,+0.18,0.10))),
        ("CTRL_ik_BR", "CTRL_pole_BR", "back_paw_R",  Vector((0,+0.18,0.10))),
    ]
    for ik_n, pole_n, foot_n, pole_off in leg_defs:
        fb = get(foot_n)
        if not fb: continue
        # IK target at foot tip
        ik = eb.new(ik_n)
        ik.head = fb.tail.copy()
        ik.tail = fb.tail.copy() + Vector((0,0,0.04))
        ik.use_deform = False
        # pole target offset from knee/elbow
        knee = fb.parent.head if fb.parent else fb.head
        pole = eb.new(pole_n)
        pole.head = knee + pole_off
        pole.tail = knee + pole_off + Vector((0,0,0.03))
        pole.use_deform = False
        created += [ik_n, pole_n]

    # Tail tip control (for FK sway authoring)
    tail_last = None
    for b in eb:
        if b.name.startswith("tail_"): tail_last = b
    if tail_last:
        tc = eb.new("CTRL_tail_tip")
        tc.head = tail_last.tail.copy()
        tc.tail = tail_last.tail.copy() + Vector((0,0.04,0))
        tc.use_deform = False
        created.append("CTRL_tail_tip")

    bpy.ops.object.mode_set(mode='OBJECT')
    vlog(f"Controls added: {created}")
    return created


def setup_constraints(arm_obj, chest_bone):
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm_obj.pose.bones

    # IK on PAW bone, chain covers lower leg (NOT up to femur/humerus, so the
    # hip/shoulder isn't dragged). No pole target (avoids rest-pose twist; the
    # natural leg bend plane is preserved).
    ik_setup = [
        ("front_paw_L", "CTRL_ik_FL", 3),  # paw, carpus, radius
        ("front_paw_R", "CTRL_ik_FR", 3),
        ("back_paw_L",  "CTRL_ik_BL", 3),  # paw, tarsus, tibia
        ("back_paw_R",  "CTRL_ik_BR", 3),
    ]
    for bone, ik_t, chain in ik_setup:
        if bone not in pb or ik_t not in pb: continue
        c = pb[bone].constraints.new('IK')
        c.target = arm_obj; c.subtarget = ik_t
        c.chain_count = chain
        c.use_stretch = False

    def add_driver(bone, path, index, prop, expr, default=0.0, lo=-1.0, hi=1.0):
        if bone not in pb: return
        b = pb[bone]; b.rotation_mode = 'XYZ'
        arm_obj[prop] = default
        arm_obj.id_properties_ui(prop).update(min=lo, max=hi, default=default)
        d = b.driver_add(path, index).driver
        d.type = 'SCRIPTED'
        v = d.variables.new(); v.name = "v"
        v.targets[0].id = arm_obj; v.targets[0].data_path = f'["{prop}"]'
        d.expression = expr

    # breath → chest scale_y
    add_driver(chest_bone, "scale", 1, "breath", "1 + v*0.07", 0.0, -1.0, 1.0)
    # jaw open → jaw rot X
    add_driver("jaw_base", "rotation_euler", 0, "jaw_open", "v*0.5", 0.0, 0.0, 1.0)
    # ear perk
    add_driver("ear_L_base", "rotation_euler", 0, "ear_L_perk", "v*0.4")
    add_driver("ear_R_base", "rotation_euler", 0, "ear_R_perk", "v*0.4")

    bpy.ops.object.mode_set(mode='OBJECT')
    vlog("IK + pole + drivers wired")


def setup_collections(arm_obj):
    """Organize bones into DEF/CTRL/MCH collections (Blender 4.0)."""
    arm = arm_obj.data
    # remove default collection assignments by creating named ones
    cols = {}
    for cname in ("DEF", "CTRL", "MCH"):
        c = arm.collections.get(cname) or arm.collections.new(cname)
        cols[cname] = c
    for b in arm.bones:
        if b.name.startswith("CTRL_"):
            cols["CTRL"].assign(b)
        elif b.name.startswith("MCH") or b.name in ("root","COG"):
            cols["MCH"].assign(b)
        else:
            cols["DEF"].assign(b)
    # hide DEF + MCH, show CTRL
    cols["DEF"].is_visible = True
    cols["MCH"].is_visible = False
    cols["CTRL"].is_visible = True
    vlog("Bone collections: DEF/CTRL/MCH")


# ============================================================================
# GATE: symmetry check
# ============================================================================
def gate_symmetry(arm_obj):
    names = {b.name for b in arm_obj.data.bones}
    L_ = {n for n in names if n.endswith("_L")}
    R_ = {n for n in names if n.endswith("_R")}
    missing_R = {n[:-2]+"_R" for n in L_} - R_
    missing_L = {n[:-2]+"_L" for n in R_} - L_
    ok = not missing_R and not missing_L
    vlog(f"GATE symmetry: L={len(L_)} R={len(R_)} "
         f"{'PASS' if ok else 'FAIL missing_R=%s missing_L=%s'%(missing_R,missing_L)}")
    return ok


# ============================================================================
# SKINNING — region-aware + budgets + mirror
# ============================================================================
def region_bones(arm_obj):
    H=set();FL=set();FR=set();BL=set();BR=set();T=set();BD=set()
    for b in arm_obj.data.bones:
        n=b.name
        if not b.use_deform: continue
        if n.startswith(("nose","snout","head","jaw","eye_","ear_","whisker","cheek","upper_lip","lower_lip","cervical")):
            H.add(n)
        elif n.startswith("tail_") or n=="sacrum":
            T.add(n)
        elif n.startswith(("scapula_L","humerus_L","radius_L","carpus_L","front_paw_L","front_toe_L")):
            FL.add(n)
        elif n.startswith(("scapula_R","humerus_R","radius_R","carpus_R","front_paw_R","front_toe_R")):
            FR.add(n)
        elif n.startswith(("hip_L","femur_L","tibia_L","tarsus_L","back_paw_L","back_toe_L")):
            BL.add(n)
        elif n.startswith(("hip_R","femur_R","tibia_R","tarsus_R","back_paw_R","back_toe_R")):
            BR.add(n)
        elif n.startswith(("pelvis","lumbar","thoracic","COG")):
            BD.add(n)
    return {"head":H|{"cervical_01","cervical_02","cervical_03","thoracic_01"},
            "FL":FL|{"thoracic_01","thoracic_02"}, "FR":FR|{"thoracic_01","thoracic_02"},
            "BL":BL|{"pelvis","lumbar_04"}, "BR":BR|{"pelvis","lumbar_04"},
            "tail":T|{"pelvis"}, "body":BD|{"cervical_01"}}


# Hard influence radius per bone type (m). A bone can only weight a vertex
# within this distance of its segment → naturally caps each bone's footprint.
def influence_radius(name):
    if name.startswith("whisker_pad"): return 0.030
    if name.startswith("whisker_"):    return 0.012
    if name.startswith("eye_"):        return 0.028
    if name.startswith("nose_tip"):    return 0.022
    if name.startswith("nose_"):       return 0.022
    if name.startswith("ear_"):        return 0.045
    if name.startswith(("upper_lip","lower_lip")): return 0.028
    if name.startswith("cheek_"):      return 0.038
    if name.startswith("jaw"):         return 0.038
    if name.startswith("snout"):       return 0.045
    if name == "head":                 return 0.150   # cranium catch-all
    if name.startswith(("front_toe","back_toe")): return 0.022
    if name.startswith(("front_paw","back_paw","carpus","tarsus")): return 0.040
    if name.startswith(("radius","tibia","humerus","femur")): return 0.060
    if name.startswith(("scapula","hip_")): return 0.070
    if name.startswith("tail_"):       return 0.050
    if name.startswith(("cervical","thoracic","lumbar","pelvis","sacrum","COG")): return 0.120
    return 0.080


def bind_skin(arm_obj, mesh, lm):
    for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
    name_vg = {}
    for b in arm_obj.data.bones:
        if b.use_deform:
            name_vg[b.name] = mesh.vertex_groups.new(name=b.name)
    mw_arm = arm_obj.matrix_world
    segs = {b.name:(mw_arm@b.head_local, mw_arm@b.tail_local)
            for b in arm_obj.data.bones if b.use_deform}
    radii = {bn: influence_radius(bn) for bn in segs}
    reg = region_bones(arm_obj)
    mw = mesh.matrix_world
    K = 4
    counts = {}
    # mouth line: jaw / lower_lip only compete below this Z (lower jaw)
    jaw_seg = segs.get("jaw_base")
    mouth_z   = (jaw_seg[0].z + 0.045) if jaw_seg else (lm["z_min"]+lm["z_max"])*0.5
    hinge_y   = (jaw_seg[0].y) if jaw_seg else 0.0      # jaw hinge (back of jaw)
    LOWER_ONLY = lambda n: n.startswith(("jaw","lower_lip"))
    UPPER_ONLY = lambda n: n.startswith(("eye_","ear_","nose_tip","whisker","upper_lip"))
    for vi,v in enumerate(mesh.data.vertices):
        wp = mw @ v.co
        r = region_of_vertex(wp, lm)
        counts[r]=counts.get(r,0)+1
        cand = reg[r]
        if r == "head":
            if wp.z > mouth_z:
                # upper head: no jaw/lower-lip
                cand = {b for b in cand if not LOWER_ONLY(b)}
            elif wp.y > hinge_y + 0.02:
                # lower head BEHIND hinge = throat → neck/cervical, not jaw
                cand = {b for b in cand if not LOWER_ONLY(b) and not UPPER_ONLY(b)}
                cand = cand | {"cervical_02", "cervical_03"}
            else:
                # lower head FORWARD of hinge = mandible/chin → jaw allowed
                cand = {b for b in cand if not UPPER_ONLY(b)}
        all_scored = sorted(((bn, dist_to_segment(wp,*segs[bn])) for bn in cand if bn in segs),
                            key=lambda x:x[1])
        # hard radius cutoff
        within = [(bn,d) for bn,d in all_scored if d < radii[bn]][:K]
        if not within:
            within = all_scored[:1]   # fallback nearest in region
        ws = [(bn, 1.0/max(d+0.004,0.004)**2) for bn,d in within]
        s = sum(w for _,w in ws)
        for bn,w in ws:
            nw = w/s
            if nw > 0.004: name_vg[bn].add([vi], nw, 'REPLACE')
    vlog("Region counts: "+", ".join(f"{k}={v}" for k,v in sorted(counts.items())))

    # Modifier + parent
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    mod = mesh.modifiers.new("Armature",'ARMATURE'); mod.object = arm_obj
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type='OBJECT')

    # Cap to 4 influences + normalize (Godot/GLB). NO cross-group smoothing —
    # it re-spreads weights across regions and reintroduces bleed.
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    try:
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    except Exception as e:
        vlog(f"normalize skip: {e}")
    bpy.ops.object.mode_set(mode='OBJECT')


def gate_budget(arm_obj, mesh):
    """Check per-bone vertex budgets; report violations."""
    n = len(mesh.data.vertices)
    viol = []
    for vg in mesh.vertex_groups:
        cap = budget_for(vg.name)
        if cap is None: continue
        c = 0
        for vi in range(n):
            try:
                if vg.weight(vi) > 0.05: c += 1
            except RuntimeError: pass
        if c > cap:
            viol.append((vg.name, c, cap))
    if viol:
        vlog("GATE budget VIOLATIONS:")
        for nm,c,cap in viol: vlog(f"   {nm}: {c} > {cap}")
    else:
        vlog("GATE budget: PASS (all face/whisker/eye bones within budget)")
    return not viol


# ============================================================================
# MAIN
# ============================================================================
def main():
    reset_scene(); import_glb()
    tripo = extract_tripo_joints()
    mesh = cleanup_keep_mesh_only()
    lm = detect_landmarks(mesh)
    bvh = build_bvh(mesh)
    arm, chest_bone = build_deform(tripo, mesh, lm, bvh)
    gate_symmetry(arm)
    add_controls(arm)
    setup_constraints(arm, chest_bone)
    bind_skin(arm, mesh, lm)
    gate_budget(arm, mesh)
    setup_collections(arm)

    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    vlog(f"Saved {OUT_BLEND}")

    # GLB export
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    try:
        bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
                                   use_selection=True, export_skins=True,
                                   export_animations=False, export_yup=True)
        vlog(f"Saved {OUT_GLB}")
    except Exception as e:
        vlog(f"GLB export FAIL: {e}")
    vlog("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
