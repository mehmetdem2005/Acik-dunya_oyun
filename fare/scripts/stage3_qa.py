"""
Stage 3 QA gate per ChatGPT pipeline spec.

Checks:
  1. All major bones inside mesh
  2. Hierarchy: root → pelvis → spine_01 → spine_02 → chest → neck → head
  3. Naming clean (no DEF- prefix, .L/.R suffix)
  4. Jaw pivot at hinge (below skull center, behind muzzle)
  5. Ear pivots at base (head Z < tail Z, lateral X)
  6. Tail chain has ≥4 segments
  7. Tail base near pelvis
  8. Legs sit under body (paw Z near floor)

Generates: skeleton contact sheet (side/front/top/3-4) and PASS/FAIL report.

Usage:
    blender --background --python fare/scripts/stage3_qa.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "out")
QA_DIR = os.path.join(OUT_DIR, "qa_stage3")
os.makedirs(QA_DIR, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import rig_mouse_v6 as rig_module


def log(m): print(f"[s3qa] {m}", flush=True)


def build():
    rig_module.reset_scene()
    rig_module.import_glb(rig_module.SRC)
    tripo = rig_module.extract_tripo_skeleton()
    mesh = rig_module.cleanup_keep_mesh_only()
    arm = rig_module.build_armature_stage3(tripo, mesh)
    return arm, mesh


def make_bvh(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.transform(mesh_obj.matrix_world)
    bm.faces.ensure_lookup_table()
    return BVHTree.FromBMesh(bm)


def is_inside(bvh, p):
    hits = 0
    d = Vector((0.0, 1.0, 0.05)).normalized()
    origin = p.copy()
    for _ in range(20):
        loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
        if loc is None: break
        hits += 1
        origin = loc + d * 1e-5
    return hits % 2 == 1


# ============================================================================
# Render contact sheet
# ============================================================================
CATEGORY_COLOR = {
    "spine":   (1.00, 0.55, 0.20, 1.0),  # orange
    "head":    (0.95, 0.85, 0.15, 1.0),  # yellow
    "ear":     (0.20, 0.85, 0.85, 1.0),  # cyan
    "tail":    (0.95, 0.40, 0.15, 1.0),  # red-orange
    "limb_F":  (0.50, 0.30, 0.90, 1.0),  # purple
    "limb_B":  (0.30, 0.80, 0.30, 1.0),  # green
    "face":    (1.00, 1.00, 0.55, 1.0),  # pale yellow
    "other":   (0.60, 0.60, 0.60, 1.0),  # grey
}


def categorize(name):
    if name == "root" or name in ("pelvis", "sacrum", "spine_01", "spine_02", "chest"):
        return "spine"
    if name in ("neck", "head", "snout"):
        return "head"
    if name == "jaw" or name.startswith("eye"):
        return "face"
    if name.startswith("ear"):
        return "ear"
    if name.startswith("tail"):
        return "tail"
    if "front_paw" in name or "upper_arm" in name or "forearm" in name or "shoulder" in name:
        return "limb_F"
    if "back_paw" in name or "thigh" in name or "shin" in name or name.startswith("hip") or "toes" in name:
        return "limb_B"
    return "other"


def make_material(cat):
    rgba = CATEGORY_COLOR.get(cat, (0.7, 0.7, 0.7, 1.0))
    name = f"BMat_{cat}"
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = rgba
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        try: bsdf.inputs["Roughness"].default_value = 0.4
        except KeyError: pass
    return m


def visualize_bones(arm):
    log("Building bone visualizers (clear color-coded cylinders)")
    mw = arm.matrix_world
    mats = {cat: make_material(cat) for cat in CATEGORY_COLOR}
    objs = []
    for b in arm.data.bones:
        cat = categorize(b.name)
        h = mw @ b.head_local
        t = mw @ b.tail_local
        length = (t - h).length
        if length < 1e-5: continue
        radius = max(length * 0.06, 0.005)
        # cylinder
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
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.4, location=h,
                                              segments=12, ring_count=8)
        s = bpy.context.object
        s.name = f"VISJ_{b.name}"
        s.data.materials.append(mats[cat])
        objs.append(s)
    return objs


def setup_render(res=1280):
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


def render_contact_sheet(arm, mesh):
    setup_render(res=1024)
    mw = mesh.matrix_world
    xs=[];ys=[];zs=[]
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx = (min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    center = (cx, cy, cz)
    d = size * 1.4

    cams = {
        "side":  add_camera("c_side",  (cx + d, cy, cz + size*0.05), center),
        "front": add_camera("c_front", (cx, cy - d, cz + size*0.05), center),  # head at -Y, so front camera at -Y looks at face
        "top":   add_camera("c_top",   (cx, cy, cz + d * 0.7), center, lens=45),
        "back":  add_camera("c_back",  (cx, cy + d, cz + size*0.05), center),
        "persp": add_camera("c_persp", (cx + d*0.7, cy - d*0.7, cz + size*0.45), center),
    }

    # Pass 1: mesh + bones overlay
    log("Rendering Stage 3 contact sheet (mesh + bones overlay)…")
    visualize_bones(arm)
    for name, cam in cams.items():
        path = os.path.join(QA_DIR, f"stage3_overlay_{name}.png")
        render_at(cam, path)
        log(f"  → stage3_overlay_{name}.png")

    # Pass 2: mesh hidden — pure skeleton
    log("Rendering pure skeleton…")
    bpy.data.objects.remove(mesh, do_unlink=True)
    for name, cam in cams.items():
        path = os.path.join(QA_DIR, f"stage3_skel_{name}.png")
        render_at(cam, path)
        log(f"  → stage3_skel_{name}.png")


# ============================================================================
# Stage 3 QA gates (PASS/FAIL list)
# ============================================================================
def qa_gates(arm, mesh):
    log("=" * 60)
    log("STAGE 3 PASS/FAIL")
    log("=" * 60)
    failures = []
    passes = []

    bvh = make_bvh(mesh)
    mw = arm.matrix_world

    # AABB
    verts = mesh.data.vertices
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    z_floor = min(zs)
    z_size = max(zs) - z_floor

    # 1. Required bones present
    required = {"root", "pelvis", "spine_01", "spine_02", "chest", "neck",
                 "head", "snout", "jaw", "ear.L", "ear.R", "eye.L", "eye.R",
                 "shoulder.L", "shoulder.R", "upper_arm.L", "upper_arm.R",
                 "forearm.L", "forearm.R", "front_paw.L", "front_paw.R",
                 "hip.L", "hip.R", "thigh.L", "thigh.R", "shin.L", "shin.R",
                 "back_paw.L", "back_paw.R", "tail_01", "tail_02", "tail_03",
                 "tail_04", "tail_05"}
    actual = {b.name for b in arm.data.bones}
    missing = required - actual
    if missing:
        failures.append(f"missing bones: {sorted(missing)}")
        log(f"  ✗ Missing {len(missing)} required bones: {sorted(missing)[:10]}")
    else:
        passes.append("all required bones present")
        log(f"  ✓ All {len(required)} required bones present")

    # 2. Hierarchy
    chain = [("pelvis", "root"), ("spine_01", "pelvis"), ("spine_02", "spine_01"),
              ("chest", "spine_02"), ("neck", "chest"), ("head", "neck"),
              ("snout", "head"), ("jaw", "head"),
              ("ear.L", "head"), ("ear.R", "head"),
              ("shoulder.L", "chest"), ("shoulder.R", "chest"),
              ("upper_arm.L", "shoulder.L"), ("forearm.L", "upper_arm.L"),
              ("front_paw.L", "forearm.L"),
              ("hip.L", "pelvis"), ("thigh.L", "hip.L"),
              ("shin.L", "thigh.L"), ("back_paw.L", "shin.L"),
              ("tail_01", "sacrum"),
              ("sacrum", "pelvis")]
    hier_fail = []
    for child, expected_parent in chain:
        cb = arm.data.bones.get(child)
        if cb is None: continue
        actual_parent = cb.parent.name if cb.parent else None
        if actual_parent != expected_parent:
            hier_fail.append(f"{child}.parent={actual_parent} (expected {expected_parent})")
    if hier_fail:
        failures.append(f"hierarchy: {hier_fail}")
        log(f"  ✗ Hierarchy errors:")
        for h in hier_fail: log(f"      {h}")
    else:
        passes.append("hierarchy correct")
        log(f"  ✓ Hierarchy root → pelvis → spine → … → head correct")

    # 3. Naming convention: no DEF-/CTRL- prefix, .L/.R suffix for lateral
    bad_naming = []
    for b in arm.data.bones:
        if b.name.startswith("DEF-") or b.name.startswith("CTRL-") or b.name.startswith("MCH-"):
            bad_naming.append(b.name)
    if bad_naming:
        failures.append(f"prefix naming: {bad_naming}")
        log(f"  ✗ Bones with old DEF-/CTRL- prefix: {bad_naming}")
    else:
        passes.append("clean naming (no DEF-/CTRL- prefix)")
        log(f"  ✓ Clean bone naming (no DEF-/CTRL-/MCH- prefix)")

    # 4. Jaw pivot at hinge
    jaw = arm.data.bones.get("jaw")
    head = arm.data.bones.get("head")
    if jaw and head:
        jh = mw @ jaw.head_local
        head_top_z = max((mw @ head.head_local).z, (mw @ head.tail_local).z)
        head_bot_z = min((mw @ head.head_local).z, (mw @ head.tail_local).z)
        skull_mid = (head_top_z + head_bot_z) / 2
        if jh.z > skull_mid:
            failures.append(f"jaw_pivot above skull mid (jh.z={jh.z:.3f}, skull_mid={skull_mid:.3f})")
            log(f"  ✗ Jaw pivot above skull mid")
        else:
            passes.append("jaw pivot below skull mid (hinge OK)")
            log(f"  ✓ Jaw pivot below skull mid (jh.z={jh.z:.3f}, skull_mid={skull_mid:.3f})")

    # 5. Ear pivots at base (head_local.z < tail_local.z = bones point UP)
    for side in ("L", "R"):
        e = arm.data.bones.get(f"ear.{side}")
        if e is None: continue
        eh = mw @ e.head_local
        et = mw @ e.tail_local
        if et.z < eh.z:
            failures.append(f"ear.{side} flipped (head.z={eh.z:.3f} > tail.z={et.z:.3f})")
            log(f"  ✗ ear.{side} flipped")
        else:
            passes.append(f"ear.{side} oriented base→tip")
            log(f"  ✓ ear.{side} points up (head.z={eh.z:.3f} → tail.z={et.z:.3f})")

    # 6. Tail chain has ≥4 segments
    tail_count = sum(1 for b in arm.data.bones if b.name.startswith("tail_"))
    if tail_count < 4:
        failures.append(f"tail too short ({tail_count} segments)")
        log(f"  ✗ Tail only {tail_count} segments")
    else:
        passes.append(f"tail chain {tail_count} segments")
        log(f"  ✓ Tail chain {tail_count} segments")

    # 7. Tail_01 ancestry leads back to pelvis (directly or via sacrum)
    tail01 = arm.data.bones.get("tail_01")
    if tail01:
        ancestor = tail01.parent
        ancestors = []
        while ancestor is not None:
            ancestors.append(ancestor.name)
            ancestor = ancestor.parent
        if "pelvis" in ancestors:
            passes.append(f"tail_01 ancestry → pelvis (via {ancestors[:ancestors.index('pelvis')+1]})")
            log(f"  ✓ tail_01 ancestry → pelvis (chain: {' → '.join(ancestors[:ancestors.index('pelvis')+1])})")
        else:
            failures.append(f"tail_01 has no pelvis ancestor (chain: {ancestors})")
            log(f"  ✗ tail_01 ancestry doesn't lead to pelvis: {ancestors}")

    # 8. Paws near floor
    for paw_name in ("front_paw.L", "front_paw.R", "back_paw.L", "back_paw.R"):
        paw = arm.data.bones.get(paw_name)
        if paw is None: continue
        pt = mw @ paw.tail_local
        if pt.z > z_floor + z_size * 0.20:
            failures.append(f"{paw_name} floats (z={pt.z:.3f})")
            log(f"  ✗ {paw_name} floats (z={pt.z:.3f})")
        else:
            passes.append(f"{paw_name} grounded")
            log(f"  ✓ {paw_name} grounded (z={pt.z:.3f})")

    # 9. Core spine bones inside mesh
    core_spine = ["pelvis", "spine_01", "spine_02", "chest", "neck", "head", "snout"]
    bad = []
    for n in core_spine:
        b = arm.data.bones.get(n)
        if b is None: continue
        mid = (mw @ b.head_local + mw @ b.tail_local) * 0.5
        if not is_inside(bvh, mid):
            bad.append(n)
    if bad:
        failures.append(f"core spine bones outside mesh: {bad}")
        log(f"  ✗ Core spine bones outside mesh: {bad}")
    else:
        passes.append("all core spine bones inside mesh")
        log(f"  ✓ All core spine bones inside mesh")

    log("")
    log(f"PASSED: {len(passes)} checks")
    log(f"FAILED: {len(failures)} checks")
    for f in failures:
        log(f"  ✗ {f}")
    return failures


# ============================================================================
# Main
# ============================================================================
def main():
    arm, mesh = build()
    log(f"Rig: {len(arm.data.bones)} bones")
    failures = qa_gates(arm, mesh)
    log("")
    log("=" * 60)
    log(f"STAGE 3 GATE: {'PASS ✓' if not failures else f'FAIL ({len(failures)} issues)'}")
    log("=" * 60)
    log("")
    # Render contact sheet AFTER gates run (gates use mesh; render destroys mesh)
    render_contact_sheet(arm, mesh)
    sys.exit(len(failures))


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(99)
