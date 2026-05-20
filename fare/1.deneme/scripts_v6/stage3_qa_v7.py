"""
Stage 3 QA v7 — dense mouse rig per spec.

PASS/FAIL checklist:
  - Spine has 7+ usable segments
  - Ribcage helpers exist
  - Belly helpers exist
  - Sacrum/pelvis control exists
  - Scapula helpers exist
  - Nose twitch controls exist
  - Cheek controls exist
  - Whisker pad controls exist
  - Jaw hinge is correct
  - Each ear has base/mid/tip bones
  - Tail has 12–16 bones
  - All major bones align with mesh anatomy
  - Deform bones and control bones are separated
  - Bone names are clean

Contact sheet views:
  - side full body, front, top, 3/4
  - close-up spine/ribcage, pelvis/sacrum, head/snout/nose,
    cheek/whisker, ears, front legs, back legs, tail

Usage:
    blender --background --python fare/scripts/stage3_qa_v7.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QA_DIR = os.path.join(ROOT, "out", "qa_stage3_v7")
os.makedirs(QA_DIR, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import rig_mouse_v7 as rig_module


def log(m): print(f"[s3qa7] {m}", flush=True)


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
# Bone categorization (for visualizer coloring)
# ============================================================================
CATEGORY_COLOR = {
    "spine":     (1.00, 0.60, 0.20, 1.0),  # orange
    "ribcage":   (1.00, 0.20, 1.00, 1.0),  # magenta — visible
    "belly":     (0.80, 0.40, 0.95, 1.0),  # light magenta
    "neck":      (1.00, 0.85, 0.30, 1.0),
    "head":      (1.00, 0.95, 0.50, 1.0),  # pale yellow
    "face":      (1.00, 0.75, 0.30, 1.0),  # light orange
    "ear":       (0.10, 0.90, 0.90, 1.0),  # cyan
    "tail":      (0.95, 0.45, 0.10, 1.0),
    "limb_F":    (0.50, 0.30, 0.95, 1.0),  # purple
    "limb_B":    (0.20, 0.85, 0.30, 1.0),  # green
    "ctrl":      (0.95, 0.95, 0.20, 1.0),  # yellow
    "helper":    (0.55, 0.55, 0.55, 1.0),  # grey
    "other":     (0.70, 0.70, 0.70, 1.0),
}


def categorize(name, meta):
    if name.startswith("CTRL"): return "ctrl"
    m = meta.get(name, {})
    coll = m.get("collection", "")
    if coll == "RIG_HELPERS": return "helper"
    n = name
    if n in ("root", "COG", "pelvis", "sacrum") or n.startswith("spine_") or n == "chest":
        return "spine"
    if n.startswith("ribcage"): return "ribcage"
    if n.startswith("belly"): return "belly"
    if n.startswith("neck"): return "neck"
    if n == "head" or n == "skull": return "head"
    if n.startswith("snout") or n == "nose_tip" or n.startswith("nose_") \
       or n.startswith("cheek") or n.startswith("whisker") \
       or n.startswith("upper_lip") or n.startswith("lower_lip") \
       or n.startswith("jaw"): return "face"
    if n.startswith("ear_"): return "ear"
    if n.startswith("tail_"): return "tail"
    if "front_" in n or n.startswith("scapula") or n.startswith("upper_front") \
       or n.startswith("lower_front"): return "limb_F"
    if "back_" in n or n.startswith("hip_") or n.startswith("thigh") or n.startswith("shin"):
        return "limb_B"
    return "other"


def make_mat(cat):
    rgba = CATEGORY_COLOR.get(cat, (0.7, 0.7, 0.7, 1.0))
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


def visualize_bones_ctrls_only(arm, meta):
    """Build only CTRL visualizers (thinner)."""
    mw = arm.matrix_world
    mats = {cat: make_mat(cat) for cat in CATEGORY_COLOR}
    objs = []
    for b in arm.data.bones:
        if not b.name.startswith("CTRL"): continue
        h = mw @ b.head_local; t = mw @ b.tail_local
        length = (t - h).length
        if length < 1e-5: continue
        radius = max(length * 0.04, 0.004)
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius,
                                             depth=length, location=(0,0,0))
        obj = bpy.context.object
        obj.name = f"VISC_{b.name}"
        direction = (t - h).normalized()
        rq = Vector((0, 0, 1)).rotation_difference(direction)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = rq
        obj.location = h + (t - h) * 0.5
        obj.data.materials.append(mats["ctrl"])
        objs.append(obj)
    return objs


def visualize_bones(arm, meta, show_ctrls=True):
    log("Building visualizer bones")
    mw = arm.matrix_world
    mats = {cat: make_mat(cat) for cat in CATEGORY_COLOR}
    objs = []
    for b in arm.data.bones:
        cat = categorize(b.name, meta)
        if not show_ctrls and cat == "ctrl": continue
        h = mw @ b.head_local
        t = mw @ b.tail_local
        length = (t - h).length
        if length < 1e-5: continue
        # CTRL bones thinner
        radius_factor = 0.04 if cat == "ctrl" else 0.06
        radius = max(length * radius_factor, 0.004)
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius,
                                             depth=length, location=(0,0,0))
        obj = bpy.context.object
        obj.name = f"VIS_{b.name}"
        direction = (t - h).normalized()
        rq = Vector((0, 0, 1)).rotation_difference(direction)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = rq
        obj.location = h + (t - h) * 0.5
        obj.data.materials.append(mats[cat])
        objs.append(obj)
        # joint sphere
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.3, location=h,
                                              segments=10, ring_count=6)
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


def render(cam, path):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)


# ============================================================================
# Contact sheet
# ============================================================================
def render_contact_sheet(arm, mesh, meta):
    setup_render(res=1024)
    # AABB world
    mw = mesh.matrix_world
    xs=[]; ys=[]; zs=[]
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx = (min(xs)+max(xs))/2; cy = (min(ys)+max(ys))/2; cz = (min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    center = (cx, cy, cz)
    d = size * 1.4

    # Get key positions from armature
    mwarm = arm.matrix_world
    def bp(name, end="head"):
        b = arm.data.bones.get(name)
        if not b: return None
        return mwarm @ (b.head_local if end == "head" else b.tail_local)

    pelvis_p = bp("pelvis", "head") or Vector(center)
    chest_p = bp("chest", "head") or Vector(center)
    head_p = bp("head", "tail") or Vector(center)
    snout_p = bp("snout_mid", "head") or head_p
    nose_p = bp("nose_tip", "tail") or snout_p
    ear_p = bp("ear_L_base", "head") or head_p
    front_paw_p = bp("front_paw_L", "tail") or Vector(center)
    back_paw_p = bp("back_paw_L", "tail") or Vector(center)
    tail_mid_p = bp("tail_07", "head") or Vector(center)

    full_cams = {
        "full_side":  add_camera("c_full_side",  (cx + d, cy, cz + size*0.05), center),
        "full_front": add_camera("c_full_front", (cx, cy - d, cz + size*0.05), center),
        "full_top":   add_camera("c_full_top",   (cx, cy, cz + d * 0.7), center, lens=45),
        "full_back":  add_camera("c_full_back",  (cx, cy + d, cz + size*0.05), center),
        "full_persp": add_camera("c_full_persp", (cx + d*0.7, cy - d*0.7, cz + size*0.4), center),
    }

    # Close-up cameras: position near subject, looking at subject
    def close_cam(name, subject_pos, offset_dir, lens=70):
        cam_pos = subject_pos + offset_dir
        return add_camera(name, cam_pos, subject_pos, lens=lens)

    close_cams = {
        "close_spine":      close_cam("c_close_spine", chest_p,
                                       Vector((size*0.5, 0, size*0.15)), lens=60),
        "close_pelvis":     close_cam("c_close_pelvis", pelvis_p,
                                       Vector((size*0.4, 0, size*0.15)), lens=70),
        "close_head_snout": close_cam("c_close_head", snout_p,
                                       Vector((size*0.2, -head_p.y * 0.0 + size*0.3, size*0.15)), lens=70),
        "close_cheek":      close_cam("c_close_cheek", snout_p,
                                       Vector((size*0.35, 0, size*0.05)), lens=80),
        "close_ears":       close_cam("c_close_ears", ear_p,
                                       Vector((size*0.25, 0, size*0.15)), lens=70),
        "close_front_legs": close_cam("c_close_FL", front_paw_p + Vector((0, 0, size*0.1)),
                                       Vector((size*0.4, 0, size*0.05)), lens=60),
        "close_back_legs":  close_cam("c_close_BL", back_paw_p + Vector((0, 0, size*0.1)),
                                       Vector((size*0.4, 0, size*0.05)), lens=60),
        "close_tail":       close_cam("c_close_tail", tail_mid_p,
                                       Vector((size*0.4, 0, size*0.1)), lens=70),
    }

    all_cams = {**full_cams, **close_cams}

    # Pass 1: mesh-only (no bones)
    log("PASS 1: mesh-only orbit")
    for name, cam in full_cams.items():
        render(cam, os.path.join(QA_DIR, f"mesh_{name}.png"))
        log(f"  → mesh_{name}.png")

    # ---- DEF-only skeleton renders (no CTRL clutter) ----
    log("Building DEF-only visualizers")
    vis_def = visualize_bones(arm, meta, show_ctrls=False)

    log("PASS 2: DEF-only overlay (mesh + DEF bones)")
    for name, cam in all_cams.items():
        render(cam, os.path.join(QA_DIR, f"overlay_def_{name}.png"))
        log(f"  → overlay_def_{name}.png")

    # ---- Now add CTRL visualizers for full overlay ----
    log("Adding CTRL visualizers")
    vis_ctrl = visualize_bones_ctrls_only(arm, meta)

    log("PASS 3: full overlay (mesh + DEF + CTRL)")
    for name, cam in all_cams.items():
        render(cam, os.path.join(QA_DIR, f"overlay_all_{name}.png"))
        log(f"  → overlay_all_{name}.png")

    # ---- Remove mesh, render skeleton only ----
    log("PASS 4: skeleton-only (DEF + CTRL)")
    bpy.data.objects.remove(mesh, do_unlink=True)
    for name, cam in all_cams.items():
        render(cam, os.path.join(QA_DIR, f"skel_all_{name}.png"))
        log(f"  → skel_all_{name}.png")

    # Remove CTRL visualizers, render DEF-only skeleton
    for o in vis_ctrl:
        bpy.data.objects.remove(o, do_unlink=True)
    log("PASS 5: skeleton-only (DEF only)")
    for name, cam in all_cams.items():
        render(cam, os.path.join(QA_DIR, f"skel_def_{name}.png"))
        log(f"  → skel_def_{name}.png")


# ============================================================================
# QA gates
# ============================================================================
def qa_gates(arm, mesh, meta):
    log("=" * 60)
    log("STAGE 3 v7 PASS/FAIL")
    log("=" * 60)
    checks = []
    mw = arm.matrix_world
    bone_set = {b.name for b in arm.data.bones}

    def check(name, ok, detail=""):
        sym = "✓" if ok else "✗"
        checks.append((name, ok, detail))
        log(f"  {sym} {name}: {detail}")

    # 1. Spine has 7+ segments
    spine_count = sum(1 for n in bone_set if n.startswith("spine_") and not n.startswith("CTRL"))
    check("Spine 7+ segments", spine_count >= 7, f"{spine_count} segments")

    # 2. Ribcage helpers exist
    rib_required = {"ribcage_center", "ribcage_L", "ribcage_R"}
    rib_present = rib_required & bone_set
    check("Ribcage helpers", rib_present == rib_required, f"{sorted(rib_present)}")

    # 3. Belly helpers exist
    belly_required = {"belly_center", "belly_L", "belly_R"}
    belly_present = belly_required & bone_set
    check("Belly helpers", belly_present == belly_required, f"{sorted(belly_present)}")

    # 4. Sacrum/pelvis controls exist
    sp_required = {"pelvis", "sacrum", "CTRL_pelvis", "CTRL_sacrum"}
    sp_present = sp_required & bone_set
    check("Pelvis/sacrum + ctrls", sp_present == sp_required, f"{sorted(sp_required - sp_present)}")

    # 5. Scapula helpers exist
    scap_req = {"scapula_L", "scapula_R"}
    check("Scapula helpers", scap_req <= bone_set, f"{sorted(scap_req - bone_set) or 'all present'}")

    # 6. Nose twitch controls exist
    nose_req = {"CTRL_nose_twitch_L", "CTRL_nose_twitch_R"}
    check("Nose twitch ctrls", nose_req <= bone_set, f"{sorted(nose_req - bone_set) or 'present'}")

    # 7. Cheek controls
    cheek_req = {"CTRL_cheek_puff_L", "CTRL_cheek_puff_R"}
    check("Cheek ctrls", cheek_req <= bone_set, f"{sorted(cheek_req - bone_set) or 'present'}")

    # 8. Whisker pad controls
    wp_req = {"CTRL_whisker_pad_forward_L", "CTRL_whisker_pad_forward_R",
              "CTRL_whisker_spread_L", "CTRL_whisker_spread_R"}
    check("Whisker pad ctrls", wp_req <= bone_set, f"{sorted(wp_req - bone_set) or 'present'}")

    # 9. Jaw hinge correct (jaw_base under skull)
    jaw = arm.data.bones.get("jaw_base")
    skull_center_z = None
    head = arm.data.bones.get("head")
    if head:
        h = mw @ head.head_local; t = mw @ head.tail_local
        skull_center_z = (h.z + t.z) / 2
    jaw_ok = False
    if jaw and skull_center_z is not None:
        jh = mw @ jaw.head_local
        jaw_ok = jh.z < skull_center_z
        check("Jaw hinge below skull mid", jaw_ok, f"jaw.head.z={jh.z:.3f} skull_mid={skull_center_z:.3f}")
    else:
        check("Jaw hinge below skull mid", False, "jaw_base or head missing")

    # 10. Each ear has base/mid/tip
    ear_ok = True
    for side in ("L", "R"):
        for part in ("base", "mid", "tip"):
            if f"ear_{side}_{part}" not in bone_set:
                ear_ok = False
    check("Ear base/mid/tip per side", ear_ok, "L+R each have base/mid/tip" if ear_ok else "missing")

    # 11. Tail has 12-16 bones
    tail_count = sum(1 for n in bone_set if n.startswith("tail_") and not n.startswith("CTRL"))
    check("Tail 12-16 bones", 12 <= tail_count <= 16, f"{tail_count} bones")

    # 12. Major bones align with mesh
    bvh = make_bvh(mesh)
    major = ["pelvis", "spine_01", "spine_04", "spine_07", "chest", "neck_01", "head"]
    outside = [n for n in major if (b := arm.data.bones.get(n)) and
                not is_inside(bvh, (mw @ b.head_local + mw @ b.tail_local) * 0.5)]
    check("Major bones aligned with mesh", not outside,
          f"outside: {outside}" if outside else "all inside")

    # 13. DEF / CTRL separation: CTRL bones have use_deform=False
    bad_def = [b.name for b in arm.data.bones if b.name.startswith("CTRL") and b.use_deform]
    check("Deform/Control separation", not bad_def, f"CTRL bones flagged deform: {bad_def[:3]}" if bad_def else "clean")

    # 14. Clean naming (no DEF-/MCH- prefix on deform bones)
    bad_naming = [b.name for b in arm.data.bones
                   if b.name.startswith(("DEF-", "MCH-"))]
    check("Bone names clean", not bad_naming, "clean" if not bad_naming else f"{bad_naming[:3]}")

    log("")
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_fail = len(checks) - n_pass
    log(f"=== Stage 3 v7 GATE: {n_pass}/{len(checks)} PASS, {n_fail} FAIL ===")
    return checks, n_fail


# ============================================================================
# Main
# ============================================================================
def main():
    arm, mesh, meta = build()
    log(f"Rig: {len(arm.data.bones)} bones")
    checks, n_fail = qa_gates(arm, mesh, meta)
    log("")
    log("=" * 60)
    log(f"STAGE 3 v7 GATE: {'PASS ✓' if n_fail == 0 else f'FAIL ({n_fail} issues)'}")
    log("=" * 60)
    log("")
    render_contact_sheet(arm, mesh, meta)
    sys.exit(n_fail)


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(99)
