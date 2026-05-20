"""
Stage 3 QA v8 — AAA anatomical mouse rig validator.

Validates 3-layer rig:
  LAYER 1: ANATOMICAL_REFERENCE (C7/T13/L6/S4/Ca28 + 13 ribs + sternum + skull/limbs)
  LAYER 2: ARMATURE_DEFORM (dense deformation skeleton)
  LAYER 3: ARMATURE_CONTROLS (animator controls)
  + RIG_HELPERS

Renders Stage 3 contact sheet (16 views including close-ups).

Usage:
    blender --background --python fare/scripts/stage3_qa_v8.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QA_DIR = os.path.join(ROOT, "out", "qa_stage3_v8")
os.makedirs(QA_DIR, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import rig_mouse_v8 as rig_module


def log(m): print(f"[s3qa8] {m}", flush=True)


def build():
    rig_module.reset_scene()
    rig_module.import_glb(rig_module.SRC)
    tripo = rig_module.extract_tripo_skeleton()
    mesh = rig_module.cleanup_keep_mesh_only()
    arm, meta = rig_module.build_rig(tripo, mesh)
    return arm, mesh, meta


def make_bvh(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.transform(mesh_obj.matrix_world)
    bm.faces.ensure_lookup_table()
    return BVHTree.FromBMesh(bm)


def is_inside(bvh, p):
    d = Vector((0.0, 1.0, 0.05)).normalized()
    hits = 0; origin = p.copy()
    for _ in range(20):
        loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
        if loc is None: break
        hits += 1; origin = loc + d * 1e-5
    return hits % 2 == 1


# ============================================================================
# Bone categorization (for visualizer colors)
# ============================================================================
CATEGORY_COLOR = {
    "ref":         (0.95, 0.95, 0.95, 1.0),  # white = anatomical reference
    "spine_def":   (1.00, 0.55, 0.20, 1.0),  # orange
    "rib":         (1.00, 0.20, 1.00, 1.0),  # magenta
    "belly":       (0.80, 0.40, 0.95, 1.0),
    "head_def":    (1.00, 0.95, 0.50, 1.0),  # pale yellow
    "face":        (1.00, 0.75, 0.30, 1.0),
    "ear":         (0.10, 0.90, 0.90, 1.0),  # cyan
    "tail":        (0.95, 0.45, 0.10, 1.0),
    "limb_F":      (0.50, 0.30, 0.95, 1.0),  # purple
    "limb_B":      (0.20, 0.85, 0.30, 1.0),  # green
    "ctrl":        (0.95, 0.95, 0.20, 1.0),  # yellow
    "ctrl_ik":     (0.20, 0.55, 1.00, 1.0),  # blue
    "ctrl_face":   (0.30, 0.90, 0.45, 1.0),  # green-tint
    "helper":      (0.55, 0.55, 0.55, 1.0),  # grey
    "other":       (0.70, 0.70, 0.70, 1.0),
}


def categorize(name, meta):
    m = meta.get(name, {})
    layer = m.get("layer", "")
    if layer == "ANATOMICAL_REFERENCE":
        return "ref"
    if layer == "RIG_HELPERS":
        return "helper"
    if name.startswith("CTRL"):
        if "paw_IK" in name or "knee_pole" in name or "toe_curl" in name:
            return "ctrl_ik"
        if any(k in name for k in ("jaw", "snout", "nose", "cheek", "whisker",
                                     "lip", "ear_", "head", "skull", "eye")):
            return "ctrl_face"
        return "ctrl"
    n = name
    if n in ("root", "COG", "pelvis", "sacrum") \
       or n.startswith("cervical_") or n.startswith("thoracic_") \
       or n.startswith("lumbar_") or n == "chest":
        return "spine_def"
    if n.startswith("ribcage_") or n == "sternum_ctrl":
        return "rib"
    if n.startswith("belly_"):
        return "belly"
    if n in ("head", "skull"):
        return "head_def"
    if n.startswith("snout_") or n == "nose_tip" or n.startswith("nose_") \
       or n.startswith("cheek_") or n.startswith("whisker_") \
       or n.startswith("upper_lip") or n.startswith("lower_lip") \
       or n.startswith("jaw_") or n.startswith("eye_"):
        return "face"
    if n.startswith("ear_"):
        return "ear"
    if n.startswith("tail_"):
        return "tail"
    if any(k in n for k in ("scapula_", "upper_front", "lower_front", "front_paw", "front_toes")):
        return "limb_F"
    if any(k in n for k in ("hip_", "thigh_", "shin_", "back_paw", "back_toes")):
        return "limb_B"
    return "other"


def make_mat(cat):
    rgba = CATEGORY_COLOR.get(cat, (0.7,0.7,0.7,1.0))
    name = f"BMat_{cat}"
    m = bpy.data.materials.get(name)
    if m is None: m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = rgba
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        try: bsdf.inputs["Roughness"].default_value = 0.4
        except KeyError: pass
    return m


def visualize_bones(arm, meta, include_layers, radius_factor=0.05):
    mw = arm.matrix_world
    mats = {cat: make_mat(cat) for cat in CATEGORY_COLOR}
    objs = []
    for b in arm.data.bones:
        m = meta.get(b.name, {})
        if m.get("layer") not in include_layers: continue
        cat = categorize(b.name, meta)
        h = mw @ b.head_local; t = mw @ b.tail_local
        length = (t - h).length
        if length < 1e-5: continue
        radius = max(length * radius_factor, 0.003)
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius,
                                             depth=length, location=(0,0,0))
        obj = bpy.context.object
        obj.name = f"VIS_{b.name}"
        direction = (t - h).normalized()
        rq = Vector((0,0,1)).rotation_difference(direction)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = rq
        obj.location = h + (t - h) * 0.5
        obj.data.materials.append(mats[cat])
        objs.append(obj)
        # joint sphere only for DEF bones (keep clean)
        if m.get("role") == "DEF":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius*1.3, location=h,
                                                  segments=8, ring_count=6)
            s = bpy.context.object
            s.name = f"VISJ_{b.name}"
            s.data.materials.append(mats[cat])
            objs.append(s)
    return objs


def setup_render(res=1024):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 0.75)
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.display.shading.show_object_outline = True
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)


def add_camera(name, loc, look_at, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new(f"{name}_tgt", None); tgt.location = look_at
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam


def render_at(cam, path):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)


# ============================================================================
# Contact sheet — 16+ views per Stage 11 spec
# ============================================================================
def render_contact_sheet(arm, mesh, meta):
    setup_render(res=1024)
    mw = mesh.matrix_world
    xs=[]; ys=[]; zs=[]
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2; cz = (min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    center = (cx, cy, cz)
    d = size * 1.4

    mwarm = arm.matrix_world
    def bp(name, end="head"):
        b = arm.data.bones.get(name)
        if not b: return None
        return mwarm @ (b.head_local if end == "head" else b.tail_local)

    pelvis_p = bp("pelvis") or Vector(center)
    chest_p = bp("chest") or Vector(center)
    head_p = bp("head", "tail") or Vector(center)
    snout_p = bp("snout_mid") or head_p
    nose_p = bp("nose_tip", "tail") or snout_p
    ear_p = bp("ear_L_base") or head_p
    front_paw_p = bp("front_paw_L", "tail") or Vector(center)
    back_paw_p = bp("back_paw_L", "tail") or Vector(center)
    tail_mid_p = bp("tail_14") or Vector(center)

    full_cams = {
        "full_side":  add_camera("c_full_side",  (cx + d, cy, cz + size*0.05), center),
        "full_front": add_camera("c_full_front", (cx, cy - d, cz + size*0.05), center),
        "full_top":   add_camera("c_full_top",   (cx, cy, cz + d * 0.7), center, lens=45),
        "full_back":  add_camera("c_full_back",  (cx, cy + d, cz + size*0.05), center),
        "full_persp": add_camera("c_full_persp", (cx + d*0.7, cy - d*0.7, cz + size*0.4), center),
    }

    def close_cam(name, subject_pos, offset_dir, lens=70):
        cam_pos = subject_pos + offset_dir
        return add_camera(name, cam_pos, subject_pos, lens=lens)

    close_cams = {
        "close_spine":      close_cam("c_close_spine", chest_p,
                                       Vector((size*0.5, 0, size*0.15)), lens=60),
        "close_ribcage":    close_cam("c_close_ribcage", chest_p,
                                       Vector((size*0.5, 0, size*0.0)), lens=60),
        "close_pelvis":     close_cam("c_close_pelvis", pelvis_p,
                                       Vector((size*0.4, 0, size*0.15)), lens=70),
        "close_head_skull": close_cam("c_close_head", head_p,
                                       Vector((size*0.3, 0, size*0.15)), lens=70),
        "close_jaw":        close_cam("c_close_jaw", snout_p,
                                       Vector((size*0.3, 0, -size*0.05)), lens=80),
        "close_snout_nose": close_cam("c_close_snout", nose_p + Vector((0,0,size*0.05)),
                                       Vector((size*0.2, 0, size*0.1)), lens=85),
        "close_cheek":      close_cam("c_close_cheek", snout_p,
                                       Vector((size*0.35, 0, size*0.05)), lens=80),
        "close_ears":       close_cam("c_close_ears", ear_p,
                                       Vector((size*0.25, 0, size*0.15)), lens=70),
        "close_front_legs": close_cam("c_close_FL", front_paw_p + Vector((0, 0, size*0.15)),
                                       Vector((size*0.4, 0, size*0.05)), lens=60),
        "close_back_legs":  close_cam("c_close_BL", back_paw_p + Vector((0, 0, size*0.15)),
                                       Vector((size*0.4, 0, size*0.05)), lens=60),
        "close_paws":       close_cam("c_close_paws", front_paw_p,
                                       Vector((size*0.3, 0, size*0.1)), lens=80),
        "close_tail":       close_cam("c_close_tail", tail_mid_p,
                                       Vector((size*0.4, 0, size*0.1)), lens=70),
    }
    all_cams = {**full_cams, **close_cams}

    # PASS 1: mesh only
    log("PASS 1: mesh-only (no rig)")
    for name, cam in full_cams.items():
        render_at(cam, os.path.join(QA_DIR, f"mesh_{name}.png"))
        log(f"  → mesh_{name}.png")

    # PASS 2: DEF only overlay
    log("PASS 2: DEF only overlay")
    vis_def = visualize_bones(arm, meta, include_layers={"ARMATURE_DEFORM", "RIG_HELPERS"})
    for name, cam in all_cams.items():
        render_at(cam, os.path.join(QA_DIR, f"overlay_def_{name}.png"))
        log(f"  → overlay_def_{name}.png")

    # PASS 3: REF only overlay (anatomical proof)
    log("PASS 3: REF only overlay (anatomical reference)")
    for o in vis_def: bpy.data.objects.remove(o, do_unlink=True)
    vis_ref = visualize_bones(arm, meta, include_layers={"ANATOMICAL_REFERENCE"},
                                radius_factor=0.04)
    for name, cam in all_cams.items():
        render_at(cam, os.path.join(QA_DIR, f"overlay_ref_{name}.png"))
        log(f"  → overlay_ref_{name}.png")

    # PASS 4: REF only, skeleton (mesh removed)
    log("PASS 4: REF skeleton (mesh removed)")
    bpy.data.objects.remove(mesh, do_unlink=True)
    for name, cam in all_cams.items():
        render_at(cam, os.path.join(QA_DIR, f"skel_ref_{name}.png"))
        log(f"  → skel_ref_{name}.png")

    # PASS 5: DEF only skeleton
    log("PASS 5: DEF skeleton (REF removed)")
    for o in vis_ref: bpy.data.objects.remove(o, do_unlink=True)
    vis_def2 = visualize_bones(arm, meta, include_layers={"ARMATURE_DEFORM", "RIG_HELPERS"})
    for name, cam in all_cams.items():
        render_at(cam, os.path.join(QA_DIR, f"skel_def_{name}.png"))
        log(f"  → skel_def_{name}.png")


# ============================================================================
# QA gates
# ============================================================================
def qa_gates(arm, mesh, meta):
    log("=" * 60)
    log("STAGE 3 v8 PASS/FAIL")
    log("=" * 60)
    checks = []
    mw = arm.matrix_world
    bone_set = {b.name for b in arm.data.bones}

    def check(name, ok, detail=""):
        sym = "✓" if ok else "✗"
        checks.append((name, ok, detail))
        log(f"  {sym} {name}: {detail}")

    # 1. Anatomical reference skeleton complete (vertebral formula)
    cervical_ref = {f"C{i:02d}" for i in (3, 4, 5, 6, 7)} | {"C01_atlas", "C02_axis"}
    thoracic_ref = {f"T{i:02d}" for i in range(1, 14)}
    lumbar_ref = {f"L{i:02d}" for i in range(1, 7)}
    sacral_ref = {f"S{i:02d}" for i in range(1, 5)}
    caudal_ref = {f"Ca{i:02d}" for i in range(1, 29)}
    check("Anatomical cervical C7", cervical_ref <= bone_set,
          f"{len(cervical_ref - bone_set)} missing" if cervical_ref - bone_set else "all 7 present")
    check("Anatomical thoracic T13", thoracic_ref <= bone_set,
          f"{len(thoracic_ref - bone_set)} missing" if thoracic_ref - bone_set else "all 13 present")
    check("Anatomical lumbar L6", lumbar_ref <= bone_set,
          f"{len(lumbar_ref - bone_set)} missing" if lumbar_ref - bone_set else "all 6 present")
    check("Anatomical sacral S4", sacral_ref <= bone_set,
          f"{len(sacral_ref - bone_set)} missing" if sacral_ref - bone_set else "all 4 present")
    check("Anatomical caudal Ca28", caudal_ref <= bone_set,
          f"{len(caudal_ref - bone_set)} missing" if caudal_ref - bone_set else "all 28 present")

    # 2. 13 rib pairs
    ribs_ref = {f"rib_{side}_{i:02d}" for side in ("L","R") for i in range(1, 14)}
    check("13 rib pairs reference", ribs_ref <= bone_set,
          f"{len(ribs_ref - bone_set)} missing" if ribs_ref - bone_set else "26 rib bones present")

    # 3. Sternum
    sternum_ref = {"manubrium", "sternebra_01", "sternebra_02",
                    "sternebra_03", "sternebra_04", "xiphoid"}
    check("Sternum reference", sternum_ref <= bone_set,
          f"{len(sternum_ref - bone_set)} missing" if sternum_ref - bone_set else "6 sternum bones present")

    # 4. Dense deform spine
    def_spine = {f"thoracic_{i:02d}" for i in range(1, 14)} | \
                 {f"lumbar_{i:02d}" for i in range(1, 7)} | \
                 {f"cervical_{i:02d}" for i in (3,4,5,6,7)} | \
                 {"cervical_01_atlas", "cervical_02_axis"}
    check("Dense deform spine (C7+T13+L6=26)", def_spine <= bone_set,
          f"{len(def_spine - bone_set)} missing" if def_spine - bone_set else "26 deform spine bones")

    # 5. Ribcage controls
    rib_ctrls = {"CTRL_ribcage_expand", "CTRL_ribcage_compress",
                  "CTRL_breath_in", "CTRL_breath_out",
                  "CTRL_ribcage_L_squash", "CTRL_ribcage_R_squash",
                  "CTRL_sternum"}
    check("Ribcage controls", rib_ctrls <= bone_set,
          f"missing {sorted(rib_ctrls - bone_set)}" if rib_ctrls - bone_set else "all present")

    # 6. Belly controls
    belly_ctrls = {"CTRL_belly_soft", "belly_center", "belly_L", "belly_R"}
    check("Belly system", belly_ctrls <= bone_set,
          f"missing {sorted(belly_ctrls - bone_set)}" if belly_ctrls - bone_set else "complete")

    # 7. Nose controls
    nose_ctrls = {"CTRL_nose_twitch_L", "CTRL_nose_twitch_R", "CTRL_nose_tip"}
    check("Nose controls", nose_ctrls <= bone_set,
          f"missing {sorted(nose_ctrls - bone_set)}" if nose_ctrls - bone_set else "all present")

    # 8. Cheek controls
    cheek_ctrls = {"CTRL_cheek_puff_L", "CTRL_cheek_puff_R"}
    check("Cheek controls", cheek_ctrls <= bone_set,
          f"missing {sorted(cheek_ctrls - bone_set)}" if cheek_ctrls - bone_set else "L+R present")

    # 9. Whisker pad controls
    wp_ctrls = {"CTRL_whisker_pad_forward_L", "CTRL_whisker_pad_forward_R",
                "CTRL_whisker_pad_up_L", "CTRL_whisker_pad_up_R",
                "CTRL_whisker_spread_L", "CTRL_whisker_spread_R"}
    check("Whisker pad controls", wp_ctrls <= bone_set,
          f"missing {sorted(wp_ctrls - bone_set)}" if wp_ctrls - bone_set else "all present")

    # 10. Jaw hinge correct
    jaw = arm.data.bones.get("jaw_base")
    head = arm.data.bones.get("head")
    if jaw and head:
        jh = mw @ jaw.head_local
        head_mid_z = ((mw @ head.head_local) + (mw @ head.tail_local)).z * 0.5
        ok = jh.z < head_mid_z
        check("Jaw hinge below skull mid", ok, f"jaw.z={jh.z:.3f} skull_mid.z={head_mid_z:.3f}")
    else:
        check("Jaw hinge below skull mid", False, "jaw_base or head missing")

    # 11. 3-part ear cartilage
    ear_chain = {f"ear_{s}_{p}" for s in ("L","R") for p in ("base","mid","tip")}
    check("3-part ear cartilage L+R", ear_chain <= bone_set,
          f"missing {sorted(ear_chain - bone_set)}" if ear_chain - bone_set else "6 ear bones")

    # 12. Scapula helpers
    scap_def = {"scapula_L", "scapula_R"}
    scap_ref = {"scapula_L_ref", "scapula_R_ref"}
    check("Scapula helpers (DEF + REF)", scap_def | scap_ref <= bone_set,
          f"missing {sorted((scap_def | scap_ref) - bone_set)}" if (scap_def | scap_ref) - bone_set else "all present")

    # 13. Paw IK/FK controls
    paw_ctrls = {f"CTRL_{which}_paw_{kind}_{side}"
                  for which in ("front", "back")
                  for kind in ("IK", "FK")
                  for side in ("L", "R")}
    check("Paw IK/FK controls (8 total)", paw_ctrls <= bone_set,
          f"missing {sorted(paw_ctrls - bone_set)[:3]}" if paw_ctrls - bone_set else "all 8 present")

    # 14. Toe controls
    toe_ctrls = {f"CTRL_toe_curl_{which}_{side}"
                  for which in ("front", "back")
                  for side in ("L", "R")}
    toes_def = {f"front_toes_L_{i:02d}" for i in range(1, 6)} | \
                {f"front_toes_R_{i:02d}" for i in range(1, 6)} | \
                {f"back_toes_L_{i:02d}" for i in range(1, 6)} | \
                {f"back_toes_R_{i:02d}" for i in range(1, 6)}
    check("Toe curl controls + 5 toes per paw",
          toe_ctrls <= bone_set and toes_def <= bone_set,
          f"toes missing: {len(toes_def - bone_set)}; ctrls missing: {len(toe_ctrls - bone_set)}")

    # 15. Tail chain density
    tail_n = sum(1 for n in bone_set if n.startswith("tail_") and not n.startswith("CTRL"))
    check("Tail chain dense (18-28)", 18 <= tail_n <= 30, f"{tail_n} bones")

    # 16. Deform/Control/Reference layers separated
    ctrl_using_deform = [b.name for b in arm.data.bones if b.name.startswith("CTRL") and b.use_deform]
    ref_using_deform = [b.name for b in arm.data.bones
                          if meta.get(b.name, {}).get("layer") == "ANATOMICAL_REFERENCE" and b.use_deform]
    layers_clean = not ctrl_using_deform and not ref_using_deform
    check("Layer separation (CTRL+REF use_deform=False)", layers_clean,
          f"CTRL leaks: {len(ctrl_using_deform)}; REF leaks: {len(ref_using_deform)}")

    # 17. Bone names clean (no DEF-/MCH- prefix legacy)
    bad_naming = [b.name for b in arm.data.bones if b.name.startswith(("DEF-", "MCH-"))]
    check("Bone names clean (no legacy prefix)", not bad_naming,
          f"legacy: {bad_naming[:3]}" if bad_naming else "clean")

    # 18. Pelvis/sacrum controls
    psp = {"pelvis", "sacrum", "CTRL_pelvis", "CTRL_sacrum"}
    check("Pelvis/sacrum + ctrls", psp <= bone_set,
          f"missing {sorted(psp - bone_set)}" if psp - bone_set else "all 4 present")

    # 19. Spine controls (curl, arch, stretch, crouch)
    spine_ctrls = {"CTRL_body_curl_L", "CTRL_body_curl_R",
                    "CTRL_body_arch_up", "CTRL_body_arch_down",
                    "CTRL_body_stretch", "CTRL_body_crouch",
                    "CTRL_lumbar_curve", "CTRL_thoracic_curve"}
    check("Spine motion controls", spine_ctrls <= bone_set,
          f"missing {sorted(spine_ctrls - bone_set)}" if spine_ctrls - bone_set else "all present")

    log("")
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_fail = len(checks) - n_pass
    log(f"=== Stage 3 v8 GATE: {n_pass}/{len(checks)} PASS, {n_fail} FAIL ===")
    return checks, n_fail


# ============================================================================
# Main
# ============================================================================
def main():
    arm, mesh, meta = build()
    log(f"Rig: {len(arm.data.bones)} bones total")
    # Per-layer counts
    layer_counts = {}
    for n, m in meta.items():
        layer_counts[m["layer"]] = layer_counts.get(m["layer"], 0) + 1
    for l, c in layer_counts.items():
        log(f"  {l}: {c} bones")
    checks, n_fail = qa_gates(arm, mesh, meta)
    log("")
    log("=" * 60)
    log(f"STAGE 3 v8 GATE: {'PASS ✓' if n_fail == 0 else f'FAIL ({n_fail} issues)'}")
    log("=" * 60)
    log("")
    render_contact_sheet(arm, mesh, meta)
    sys.exit(n_fail)


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(99)
