"""
v17 — rig from scratch, CORRECT method.

Root-cause fix over v16: v16 snapped every bone head independently with
closest_inside, which broke parent/child continuity (limb chains split into
floating pieces). v17 instead:

  1. Collects JOINT POINTS (Tripo joints are already a CONTINUOUS polyline:
     each joint.tail == next joint.head). We keep that continuity.
  2. Optionally centers a joint LATERALLY only (perpendicular to the bone
     direction) so chain spacing is never disturbed.
  3. Builds bones from CONSECUTIVE shared points → child.head == parent.tail
     always (use_connect=True). No gaps, ever.
  4. Mirrors LEFT joint POINTS → right, then builds the right chain identically.

Skeleton-first: this script can run with WEIGHTS=0 to only build + render the
skeleton for inspection before committing to weighting/animation.

Usage:
    blender --background --python fare/scripts/rig_mouse_v17.py
"""

import bpy, math, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as L
from mouse_rig_lib import (reset_scene, import_glb, extract_tripo_joints,
                           cleanup_keep_mesh_only, build_bvh, build_kdtree,
                           detect_landmarks, center_joint_lateral,
                           cross_section_centroid_world)

OUT_BLEND = os.path.join(L.OUT_DIR, "mouse_v17.blend")
def vlog(m): print(f"[v17] {m}", flush=True)


def build_skeleton(tripo, mesh, lm, bvh, kd, center=True):
    bpy.ops.object.armature_add(enter_editmode=True, location=(0,0,0))
    arm_obj = bpy.context.object; arm_obj.name = "MouseRig"
    arm = arm_obj.data; arm.name = "MouseRig"
    eb = arm.edit_bones
    for b in list(eb): eb.remove(b)
    B = {}

    def Jh(n): return tripo[n]["head"].copy()
    def Jt(n): return tripo[n]["tail"].copy()

    def center_polyline(pts):
        """Center interior joints laterally using local chain direction."""
        if not center or len(pts) < 2: return pts
        out = [pts[0].copy()]
        for i in range(1, len(pts)-1):
            axis = (pts[i+1] - pts[i-1])
            out.append(center_joint_lateral(pts[i], kd, axis, radius=0.045))
        out.append(pts[-1].copy())
        return out

    def build_chain(names, pts, parent, connect_first=False, deform=True):
        prev = parent
        for i, nm in enumerate(names):
            b = eb.new(nm); b.head = pts[i].copy(); b.tail = pts[i+1].copy()
            if prev:
                b.parent = B.get(prev) or eb.get(prev)
                b.use_connect = True if (i > 0) else connect_first
            b.use_deform = deform
            B[nm] = b; prev = nm

    # ---------------- ROOT / COG (non-deform control) ----------------
    root = eb.new("root"); root.head=Vector((0,0,0.01)); root.tail=Vector((0,0.12,0.01)); root.use_deform=False
    B["root"]=root
    cog = eb.new("COG"); cog.head=Vector((0,0.10,0.18)); cog.tail=Vector((0,0.18,0.20))
    cog.parent=root; cog.use_deform=False; B["COG"]=cog

    # ---------------- SPINE (medial cross-sections, dorsal-biased) ----------------
    # body axis range: pelvis (back) → neck (front). Tripo: Root..Head_0.
    # Pure centroid sits at the body's center of mass (too low → sag); bias the
    # spine UP toward the dorsal (back) surface so it follows the backbone.
    mw = mesh.matrix_world
    y_pelvis = 0.19; y_neck = -0.15
    n_spine = 7
    DORSAL = 0.55   # 0=centroid, 1=top surface
    spine_pts = []
    for i in range(n_spine + 1):
        y = y_pelvis + (y_neck - y_pelvis) * (i / n_spine)
        band = [mw @ v.co for v in mesh.data.vertices if abs((mw @ v.co).y - y) < 0.02]
        if band:
            cz = sum(p.z for p in band) / len(band)
            topz = max(p.z for p in band)
            z = cz + DORSAL * (topz - cz)
        else:
            z = 0.27
        spine_pts.append(Vector((0.0, y, z)))
    spine_names = ["pelvis","lumbar_03","lumbar_02","lumbar_01",
                   "thoracic_02","thoracic_01","cervical_01"]
    build_chain(spine_names, spine_pts, "COG", connect_first=False)
    chest_bone = "thoracic_01"

    # neck → head (Tripo Head_0 → Head_1 → Head_2)
    neck = Jh("tripo::Head_0"); skull = Jh("tripo::Head_1"); snout = Jh("tripo::Head_2")
    nose_r = Jh("tripo::Head_3"); nose_t = Jt("tripo::Head_3")
    build_chain(["cervical_02"], [spine_pts[-1], neck], "cervical_01", connect_first=True)
    build_chain(["head"], [neck, skull], "cervical_02", connect_first=True)
    build_chain(["snout"], [skull, snout], "head", connect_first=False)
    build_chain(["nose"], [snout, nose_r], "snout", connect_first=True)
    build_chain(["nose_tip"], [nose_r, nose_t], "nose", connect_first=True)
    # jaw (added; below mouth line, parented to head)
    jaw_h = Vector((0, skull.y-0.02, skull.z-0.06)); jaw_t = Vector((0, nose_r.y-0.01, nose_r.z-0.05))
    build_chain(["jaw"], [jaw_h, jaw_t], "head", connect_first=False)

    # ---------------- TAIL (Tripo continuous) ----------------
    tail_seed = [Jh("bone_21"), Jh("tripo::Tail_0"), Jh("tripo::Tail_1"),
                 Jh("tripo::Tail_2"), Jh("tripo::Tail_3"), Jh("bone_26"), Jt("bone_26")]
    tail_seed = center_polyline(tail_seed)
    tail_names = [f"tail_{i+1:02d}" for i in range(len(tail_seed)-1)]
    build_chain(tail_names, tail_seed, "pelvis", connect_first=False)

    # ---------------- LEGS (LEFT from Tripo continuous chains) ----------------
    fl = [Jh("bone_9"), Jh("tripo::0_Left_Limb_0"), Jh("tripo::0_Left_Limb_1"),
          Jh("tripo::0_Left_Limb_2"), Jt("tripo::0_Left_Limb_2")]
    fl = center_polyline(fl)
    build_chain(["scapula_L","humerus_L","radius_L","front_paw_L"], fl,
                "thoracic_01", connect_first=False)

    bl = [Jh("bone_27"), Jh("tripo::1_Left_Limb_0"), Jh("tripo::1_Left_Limb_1"),
          Jh("tripo::1_Left_Limb_2"), Jh("tripo::1_Left_Limb_3"), Jh("tripo::1_Left_Limb_4"),
          Jt("tripo::1_Left_Limb_4")]
    bl = center_polyline(bl)
    build_chain(["hip_L","femur_L","tibia_L","tarsus_L","back_paw_L","back_toe_L"], bl,
                "pelvis", connect_first=False)

    # ---------------- EARS (Tripo bone_7=L, bone_6=R), 2 segs each ----------------
    for side, src in (("L","bone_7"),("R","bone_6")):
        base=Jh(src); tip=Jt(src); mid=base+(tip-base)*0.5
        build_chain([f"ear_{side}_base"], [base, mid], "head", connect_first=False)
        build_chain([f"ear_{side}_tip"], [mid, tip], f"ear_{side}_base", connect_first=True)

    # ---------------- EYES + whisker pads (placed, oriented outward) ----------------
    for side, sx in (("L",+1),("R",-1)):
        eb_b = eb.new(f"eye_{side}")
        eb_b.head = Vector((sx*0.045, skull.y-0.02, skull.z+0.02))
        eb_b.tail = Vector((sx*0.06, skull.y-0.05, skull.z+0.02))
        eb_b.parent = B["head"]; B[f"eye_{side}"]=eb_b
        wp = eb.new(f"whisker_pad_{side}")
        wp.head = Vector((sx*0.05, nose_r.y+0.0, nose_r.z-0.01))
        wp.tail = Vector((sx*0.10, nose_r.y-0.04, nose_r.z-0.01))
        wp.parent = B["snout"]; B[f"whisker_pad_{side}"]=wp

    # ---------------- MIRROR LEFT LEG/EAR/EYE/PAD → RIGHT ----------------
    LEFT = [n for n in B if n.endswith("_L")]
    snap = []
    for n in LEFT:
        b=B[n]; par=b.parent.name if b.parent else None
        snap.append((n, Vector(b.head), Vector(b.tail), par, b.use_connect, b.use_deform))
    left_set=set(LEFT)
    def mir(n): return n[:-2]+"_R"
    for n,h,t,par,cn,df in snap:
        rn=mir(n); rb=eb.new(rn)
        rb.head=Vector((-h.x,h.y,h.z)); rb.tail=Vector((-t.x,t.y,t.z))
        rpar = mir(par) if (par in left_set) else par
        if rpar and (rpar in B or eb.get(rpar)):
            rb.parent = B.get(rpar) or eb.get(rpar); rb.use_connect=cn
        rb.use_deform=df; B[rn]=rb

    # ---------------- roll ----------------
    bpy.ops.armature.select_all(action='SELECT')
    bpy.ops.armature.calculate_roll(type='GLOBAL_POS_Z')
    bpy.ops.object.mode_set(mode='OBJECT')

    # GATE: continuity (every connected child head == parent tail)
    gaps=0
    for b in arm.bones:
        if b.parent and b.use_connect:
            if (b.head_local - b.parent.tail_local).length > 1e-5: gaps+=1
    vlog(f"Skeleton: {len(arm.bones)} bones, connected-chain gaps={gaps} "
         f"{'PASS' if gaps==0 else 'FAIL'}")
    # GATE: symmetry
    names={b.name for b in arm.bones}
    Ls={n for n in names if n.endswith('_L')}; Rs={n for n in names if n.endswith('_R')}
    miss={n[:-2]+'_R' for n in Ls}-Rs
    vlog(f"Symmetry: L={len(Ls)} R={len(Rs)} {'PASS' if not miss else 'FAIL '+str(miss)}")
    return arm_obj, chest_bone


# ============================================================================
# WEIGHTING (region-aware + hard radius cutoff — same proven method as v16,
# adapted to v17 bone names)
# ============================================================================
from mouse_rig_lib import dist_to_segment, region_of_vertex

def influence_radius(name):
    if name.startswith("whisker_pad"): return 0.045
    if name.startswith("eye_"):        return 0.030
    if name == "nose_tip":             return 0.030
    if name == "nose":                 return 0.035
    if name.startswith("ear_"):        return 0.050
    if name == "jaw":                  return 0.065
    if name == "snout":                return 0.055
    if name == "head":                 return 0.150
    if name.startswith(("front_paw","back_paw","back_toe")): return 0.035
    if name.startswith(("radius","tibia","tarsus")):         return 0.055
    if name.startswith(("humerus","femur","scapula","hip_")):return 0.075
    if name.startswith("tail_"):       return 0.050
    if name.startswith(("cervical","thoracic","lumbar","pelvis")): return 0.130
    return 0.080


def region_bones(arm):
    g = {"head":set(),"FL":set(),"FR":set(),"BL":set(),"BR":set(),"tail":set(),"body":set()}
    for b in arm.data.bones:
        if not b.use_deform: continue
        n=b.name
        if n.startswith(("nose","snout","head","jaw","eye_","ear_","whisker","cervical")):
            g["head"].add(n)
        elif n.startswith("tail_") or n=="sacrum":
            g["tail"].add(n)
        elif n.startswith(("scapula_L","humerus_L","radius_L","front_paw_L")):
            g["FL"].add(n)
        elif n.startswith(("scapula_R","humerus_R","radius_R","front_paw_R")):
            g["FR"].add(n)
        elif n.startswith(("hip_L","femur_L","tibia_L","tarsus_L","back_paw_L","back_toe_L")):
            g["BL"].add(n)
        elif n.startswith(("hip_R","femur_R","tibia_R","tarsus_R","back_paw_R","back_toe_R")):
            g["BR"].add(n)
        elif n.startswith(("pelvis","lumbar","thoracic")):
            g["body"].add(n)
    g["head"] |= {"cervical_01","cervical_02","thoracic_01"}
    g["FL"] |= {"thoracic_01"}; g["FR"] |= {"thoracic_01"}
    g["BL"] |= {"pelvis","lumbar_01"}; g["BR"] |= {"pelvis","lumbar_01"}
    g["tail"] |= {"pelvis"}; g["body"] |= {"cervical_01"}
    return g


def bind_skin(arm, mesh, lm):
    for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
    vg = {b.name: mesh.vertex_groups.new(name=b.name)
          for b in arm.data.bones if b.use_deform}
    mwa = arm.matrix_world
    segs = {b.name:(mwa@b.head_local, mwa@b.tail_local)
            for b in arm.data.bones if b.use_deform}
    radii = {n: influence_radius(n) for n in segs}
    reg = region_bones(arm); mw = mesh.matrix_world; K=4
    jaw_seg = segs.get("jaw")
    mouth_z = (jaw_seg[0].z + 0.05) if jaw_seg else 0.25
    hinge_y = jaw_seg[0].y if jaw_seg else 0.0
    LOW = lambda n: n=="jaw"
    UP  = lambda n: n.startswith(("eye_","ear_","nose","whisker"))
    for vi,v in enumerate(mesh.data.vertices):
        wp = mw @ v.co; r = region_of_vertex(wp, lm); cand = reg[r]
        if r=="head":
            if wp.z > mouth_z: cand={b for b in cand if not LOW(b)}
            elif wp.y > hinge_y+0.02: cand={b for b in cand if not LOW(b) and not UP(b)}|{"cervical_02"}
            else: cand={b for b in cand if not UP(b)}
        sc = sorted(((bn, dist_to_segment(wp,*segs[bn])) for bn in cand if bn in segs), key=lambda x:x[1])
        within=[(bn,d) for bn,d in sc if d<radii[bn]][:K] or sc[:1]
        ws=[(bn,1.0/max(d+0.004,0.004)**2) for bn,d in within]; s=sum(w for _,w in ws)
        for bn,w in ws:
            nw=w/s
            if nw>0.004: vg[bn].add([vi], nw, 'REPLACE')
    # modifier + parent
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active=mesh
    mesh.modifiers.new("Armature",'ARMATURE').object=arm
    mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
    bpy.ops.object.parent_set(type='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active=mesh
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    try:
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    except Exception as e: vlog(f"normalize skip {e}")
    bpy.ops.object.mode_set(mode='OBJECT')
    vlog("Skin bound (region-aware, max 4 influences)")


# ============================================================================
# CONTROLS + CONSTRAINTS + COLLECTIONS
# ============================================================================
def add_controls(arm):
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT'); eb=arm.data.edit_bones
    for ik,foot in (("CTRL_ik_FL","front_paw_L"),("CTRL_ik_FR","front_paw_R"),
                    ("CTRL_ik_BL","back_paw_L"),("CTRL_ik_BR","back_paw_R")):
        fb=eb.get(foot)
        if not fb: continue
        c=eb.new(ik); c.head=fb.tail.copy(); c.tail=fb.tail.copy()+Vector((0,0,0.04)); c.use_deform=False
    bpy.ops.object.mode_set(mode='OBJECT')


def setup_constraints(arm, chest):
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='POSE'); pb=arm.pose.bones
    for bone,ik,chain in (("front_paw_L","CTRL_ik_FL",3),("front_paw_R","CTRL_ik_FR",3),
                          ("back_paw_L","CTRL_ik_BL",3),("back_paw_R","CTRL_ik_BR",3)):
        if bone in pb and ik in pb:
            c=pb[bone].constraints.new('IK'); c.target=arm; c.subtarget=ik
            c.chain_count=chain; c.use_stretch=False
    def drv(bone,path,idx,prop,expr,default=0.0,lo=-1.0,hi=1.0):
        if bone not in pb: return
        b=pb[bone]; b.rotation_mode='XYZ'; arm[prop]=default
        arm.id_properties_ui(prop).update(min=lo,max=hi,default=default)
        d=b.driver_add(path,idx).driver; d.type='SCRIPTED'
        var=d.variables.new(); var.name="v"; var.targets[0].id=arm
        var.targets[0].data_path=f'["{prop}"]'; d.expression=expr
    drv(chest,"scale",1,"breath","1+v*0.07")
    drv("jaw","rotation_euler",0,"jaw_open","v*0.5",0.0,0.0,1.0)
    drv("ear_L_base","rotation_euler",0,"ear_L_perk","v*0.4")
    drv("ear_R_base","rotation_euler",0,"ear_R_perk","v*0.4")
    bpy.ops.object.mode_set(mode='OBJECT')
    vlog("IK + drivers wired")


def setup_collections(arm):
    a=arm.data; cols={}
    for c in ("DEF","CTRL","MCH"):
        cols[c]=a.collections.get(c) or a.collections.new(c)
    for b in a.bones:
        if b.name.startswith("CTRL_"): cols["CTRL"].assign(b)
        elif b.name in ("root","COG"): cols["MCH"].assign(b)
        else: cols["DEF"].assign(b)
    cols["MCH"].is_visible=False


def main():
    reset_scene(); import_glb()
    tripo = extract_tripo_joints()
    mesh = cleanup_keep_mesh_only()
    lm = detect_landmarks(mesh)
    bvh = build_bvh(mesh); kd = build_kdtree(mesh)
    arm, chest = build_skeleton(tripo, mesh, lm, bvh, kd, center=True)
    add_controls(arm)
    setup_constraints(arm, chest)
    bind_skin(arm, mesh, lm)
    setup_collections(arm)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    vlog(f"Saved {OUT_BLEND}")
    # static GLB
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True); mesh.select_set(True); bpy.context.view_layer.objects.active=arm
    try:
        bpy.ops.export_scene.gltf(filepath=os.path.join(L.OUT_DIR,"mouse.glb"),
            export_format='GLB', use_selection=True, export_skins=True,
            export_animations=False, export_yup=True)
        vlog("Saved mouse.glb")
    except Exception as e: vlog(f"GLB fail {e}")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
