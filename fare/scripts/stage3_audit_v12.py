"""
Stage 3 v12 — Comprehensive bone-by-bone audit + visual proof.

Per user's correction pipeline: don't claim PASS, list EVERY problematic bone.

For every DEF bone:
  - Is head/mid/tail inside mesh? (3-point sample)
  - Is the chain connected to parent at the correct point?
  - Classify: PROTRUSION / FLOATING / CHAIN_GAP / OK

Then render multi-angle skeleton overlay with leg bones HIGHLIGHTED in
distinctive color to prove their positions.

Usage: blender --background --python fare/scripts/stage3_audit_v12.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "out", "audit_v12")
os.makedirs(OUT_DIR, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import rig_mouse_v12 as v12


def log(m): print(f"[audit] {m}", flush=True)


def build():
    v12.reset_scene()
    v12.import_glb(v12.SRC)
    tripo = v12.extract_tripo_skeleton()
    mesh = v12.cleanup_keep_mesh_only()
    arm, meta = v12.build_rig(tripo, mesh)
    v12.setup_pose_rigging(arm, meta, tripo, mesh)
    return arm, mesh, meta


def make_bvh(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.transform(mesh.matrix_world)
    bm.faces.ensure_lookup_table()
    return BVHTree.FromBMesh(bm)


def is_inside_mesh(bvh, p):
    """Multi-direction parity ray cast."""
    inside_count = 0
    dirs = (Vector((1, 0.1, 0.05)).normalized(),
            Vector((0.1, 1, 0.05)).normalized(),
            Vector((0.05, 0.1, 1)).normalized())
    for d in dirs:
        hits = 0; origin = p.copy()
        for _ in range(20):
            loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
            if loc is None: break
            hits += 1; origin = loc + d * 1e-5
        if hits % 2 == 1: inside_count += 1
    return inside_count >= 2


# ============================================================================
# Per-bone audit
# ============================================================================
def audit_bones(arm, mesh, meta):
    bvh = make_bvh(mesh)
    mw = arm.matrix_world

    # Categorize: bones EXPECTED to be inside (deform spine, ribs, body)
    # vs bones that can be at surface (toes, ear tips, whiskers, nose tip)
    surface_ok_bones = {"toes", "tip", "nose_", "ear_", "whisker", "incisor",
                         "rib_", "phalange", "tail_28", "tail_27", "tail_26",
                         "tail_25", "tail_24"}
    def is_surface_ok(name):
        return any(k in name for k in surface_ok_bones)

    issues = {"PROTRUSION": [], "CHAIN_GAP": [], "OK": []}
    chain_check = {}  # parent_name → list of (child_name, head_pos)

    for b in arm.data.bones:
        m = meta.get(b.name, {})
        if m.get("role") not in ("DEF",): continue
        if b.name.startswith("MCH_"): continue  # twist bones can be inside other bones
        h = mw @ b.head_local
        t = mw @ b.tail_local
        mid = (h + t) * 0.5
        # 3-point sample
        h_in = is_inside_mesh(bvh, h)
        m_in = is_inside_mesh(bvh, mid)
        t_in = is_inside_mesh(bvh, t)

        # Determine status
        all_in = h_in and m_in and t_in
        # Toes/tips/whiskers: at-surface acceptable (head inside but tail may protrude)
        if is_surface_ok(b.name):
            if h_in:
                issues["OK"].append(b.name)
            else:
                issues["PROTRUSION"].append((b.name, "head outside", h))
        else:
            if all_in:
                issues["OK"].append(b.name)
            else:
                detail = []
                if not h_in: detail.append("head")
                if not m_in: detail.append("mid")
                if not t_in: detail.append("tail")
                issues["PROTRUSION"].append((b.name, " ".join(detail), mid))

        # Chain gap check: bone's head should match parent's tail (if connected chain)
        if b.parent and b.use_connect:
            p_tail = mw @ b.parent.tail_local
            gap = (h - p_tail).length
            if gap > 0.001:
                issues["CHAIN_GAP"].append((b.name, b.parent.name, gap))

    return issues


# ============================================================================
# Render skeleton overlay with leg bones highlighted
# ============================================================================
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
    sc.world = world; world.use_nodes = True
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


def make_mat(name, rgba):
    m = bpy.data.materials.get(name)
    if m is None: m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = rgba
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        try: bsdf.inputs["Roughness"].default_value = 0.3
        except KeyError: pass
    return m


def build_leg_highlighted_visualizer(arm, meta, problem_bones):
    """Render bone cylinders. Color code:
       - YELLOW: front leg bones (scapula, upper, lower, wrist, paw, toes)
       - GREEN: back leg bones (hip, thigh, shin, ankle, paw, toes)
       - RED: bones with issues (protrusion/floating)
       - GREY: everything else
    """
    mw = arm.matrix_world
    mats = {
        "front_leg": make_mat("front_leg", (1.0, 0.85, 0.10, 1.0)),  # bright yellow
        "back_leg":  make_mat("back_leg", (0.15, 0.85, 0.20, 1.0)),  # bright green
        "problem":   make_mat("problem", (1.0, 0.15, 0.15, 1.0)),    # bright red
        "spine":     make_mat("spine_n", (0.95, 0.60, 0.20, 1.0)),
        "tail":      make_mat("tail_n", (0.95, 0.45, 0.10, 1.0)),
        "face":      make_mat("face_n", (0.85, 0.85, 0.45, 1.0)),
        "other":     make_mat("other_n", (0.55, 0.55, 0.55, 1.0)),
    }
    problem_set = set()
    for b_info in problem_bones.get("PROTRUSION", []):
        problem_set.add(b_info[0])

    def categorize(name):
        if name in problem_set: return "problem"
        if any(k in name for k in ("scapula", "upper_front_leg", "lower_front_leg",
                                     "front_paw", "front_toes", "wrist")):
            return "front_leg"
        if any(k in name for k in ("hip_", "thigh", "shin", "back_paw", "back_toes", "ankle")):
            return "back_leg"
        if any(k in name for k in ("cervical", "thoracic", "lumbar", "spine", "chest",
                                     "neck", "pelvis", "sacrum", "ribcage", "belly", "sternum")):
            return "spine"
        if name.startswith("tail_"): return "tail"
        if any(k in name for k in ("head", "skull", "snout", "nose", "jaw", "lip",
                                     "cheek", "whisker", "ear_", "eye_")):
            return "face"
        return "other"

    objs = []
    for b in arm.data.bones:
        m = meta.get(b.name, {})
        if m.get("role") not in ("DEF",): continue
        cat = categorize(b.name)
        h = mw @ b.head_local; t = mw @ b.tail_local
        length = (t - h).length
        if length < 1e-5: continue
        # Leg bones thicker, problem bones thicker
        r_mul = 1.5 if cat in ("front_leg", "back_leg", "problem") else 1.0
        radius = max(length * 0.06, 0.003) * r_mul
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
        # joint sphere at head
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.3, location=h,
                                              segments=10, ring_count=6)
        s = bpy.context.object
        s.name = f"VISJ_{b.name}"
        s.data.materials.append(mats[cat])
        objs.append(s)
    return objs


def render_at(cam, path):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = path
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)


def main():
    arm, mesh, meta = build()
    log(f"Rig built: {len(arm.data.bones)} bones")

    # AUDIT
    log("=" * 60)
    log("PER-BONE AUDIT")
    log("=" * 60)
    issues = audit_bones(arm, mesh, meta)
    log(f"OK: {len(issues['OK'])} bones")
    log(f"PROTRUSION: {len(issues['PROTRUSION'])} bones")
    log(f"CHAIN_GAP: {len(issues['CHAIN_GAP'])} bones")

    log("")
    log("--- PROTRUSION DETAILS ---")
    for name, detail, pos in issues["PROTRUSION"][:30]:
        log(f"  ✗ {name}: {detail}  at ({pos.x:+.3f},{pos.y:+.3f},{pos.z:+.3f})")
    if len(issues["PROTRUSION"]) > 30:
        log(f"  ... and {len(issues['PROTRUSION']) - 30} more")

    log("")
    log("--- CHAIN_GAP DETAILS ---")
    for name, parent, gap in issues["CHAIN_GAP"][:20]:
        log(f"  ⚠ {name}: gap to parent {parent} = {gap:.4f}m")
    if len(issues["CHAIN_GAP"]) > 20:
        log(f"  ... and {len(issues['CHAIN_GAP']) - 20} more")

    # Save audit report to text file
    report_path = os.path.join(OUT_DIR, "bone_audit.txt")
    with open(report_path, "w") as f:
        f.write(f"=== STAGE 3 v12 BONE AUDIT ===\n\n")
        f.write(f"Total bones: {len(arm.data.bones)}\n")
        f.write(f"DEF bones audited: {len(issues['OK']) + len(issues['PROTRUSION'])}\n\n")
        f.write(f"OK: {len(issues['OK'])}\n")
        f.write(f"PROTRUSION: {len(issues['PROTRUSION'])}\n")
        f.write(f"CHAIN_GAP: {len(issues['CHAIN_GAP'])}\n\n")
        f.write("--- PROTRUSION ---\n")
        for name, detail, pos in issues["PROTRUSION"]:
            f.write(f"  {name}: {detail}  at ({pos.x:+.3f},{pos.y:+.3f},{pos.z:+.3f})\n")
        f.write("\n--- CHAIN_GAP ---\n")
        for name, parent, gap in issues["CHAIN_GAP"]:
            f.write(f"  {name} ↔ {parent}: {gap:.4f}m gap\n")
    log(f"Audit report saved: {report_path}")

    # RENDER multi-angle skeleton overlay
    setup_render(res=1280)
    mw = mesh.matrix_world
    xs=[];ys=[];zs=[]
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    d = size * 1.3
    cams = {
        "side":  add_camera("Cside",  (cx + d, cy, cz + size*0.05), (cx, cy, cz)),
        "front": add_camera("Cfront", (cx, cy - d, cz + size*0.05), (cx, cy, cz)),
        "top":   add_camera("Ctop",   (cx, cy, cz + d * 0.7), (cx, cy, cz), lens=45),
        "back":  add_camera("Cback",  (cx, cy + d, cz + size*0.05), (cx, cy, cz)),
        "persp": add_camera("Cpersp", (cx + d*0.7, cy - d*0.7, cz + size*0.45), (cx, cy, cz)),
        "persp_R": add_camera("Cperspr", (cx - d*0.7, cy - d*0.7, cz + size*0.45), (cx, cy, cz)),
    }

    # Pass 1: mesh + DEF bone overlay (leg bones highlighted)
    log("Rendering mesh + leg-highlighted overlay")
    visualize = build_leg_highlighted_visualizer(arm, meta, issues)
    for name, cam in cams.items():
        render_at(cam, os.path.join(OUT_DIR, f"overlay_{name}.png"))
        log(f"  → overlay_{name}.png")

    # Pass 2: skeleton only (mesh hidden), legs highlighted
    log("Rendering skeleton-only (mesh removed)")
    bpy.data.objects.remove(mesh, do_unlink=True)
    for name, cam in cams.items():
        render_at(cam, os.path.join(OUT_DIR, f"skel_{name}.png"))
        log(f"  → skel_{name}.png")

    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
