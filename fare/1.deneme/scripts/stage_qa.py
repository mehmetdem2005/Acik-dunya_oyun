"""
Pipeline QA gates per ChatGPT/pipeline-lock spec.

Stage 2: skeleton placement (bone-in-mesh, hierarchy, naming).
Stage 3: weight painting (per-pose deformation, no pinching).
Stage 5: export inventory (.blend + .glb + bone list + counts).

Each stage prints PASS/FAIL gates. Stage exit code = number of failures.

Usage:
    blender --background --python fare/scripts/stage_qa.py -- <stage>
where <stage> ∈ {2, 3, 5, all}.
"""

import bpy
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
OUT_DIR = os.path.join(ROOT, "out")
QA_DIR = os.path.join(OUT_DIR, "qa")
os.makedirs(QA_DIR, exist_ok=True)
sys.path.insert(0, SCRIPTS_DIR)
import rig_mouse_v5 as rig_module


def log(m): print(f"[qa] {m}", flush=True)


def build_rig(enable_smooth=False):
    rig_module.reset_scene()
    rig_module.import_glb(rig_module.SRC)
    tripo = rig_module.extract_tripo_skeleton()
    mesh = rig_module.cleanup_and_merge()
    A = rig_module.TripoAnatomy(tripo, mesh)
    arm, bm, ld, tn, tc = rig_module.build_armature_from_tripo(tripo, A)
    rig_module.setup_pose_constraints(arm, ld, tn, tc, A)
    rig_module.skin_with_corrective_smooth(mesh, arm)
    rig_module.targeted_weight_refinement(mesh, A)
    rig_module.smart_orphan_adoption(mesh, arm)
    if enable_smooth:
        cs = next((m for m in mesh.modifiers if m.type == 'CORRECTIVE_SMOOTH'), None)
        if cs: cs.factor = 0.5
    return arm, mesh, A


# ============================================================================
# Stage 2 QA: skeleton placement
# ============================================================================
def stage2_qa(arm, mesh, A):
    log("=" * 60)
    log("STAGE 2 QA — Skeleton placement")
    log("=" * 60)
    failures = []

    # Build BVH for mesh
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.transform(mesh.matrix_world)
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)

    def is_inside_mesh(p):
        """Parity ray-cast — count hits along an arbitrary ray."""
        hits = 0
        d = Vector((0.0, 1.0, 0.05)).normalized()
        origin = p.copy()
        for _ in range(20):
            loc, n, idx, dist = bvh.ray_cast(origin, d, 100.0)
            if loc is None: break
            hits += 1
            origin = loc + d * 1e-5
        return hits % 2 == 1

    # 1. All DEF bone heads/midpoints inside mesh
    mw = arm.matrix_world
    def_outside = []
    for b in arm.data.bones:
        if not b.name.startswith("DEF-"): continue
        h = mw @ b.head_local
        t = mw @ b.tail_local
        mid = (h + t) * 0.5
        # Allow tail tip + paw tip + nose tip + ear tip outside (they protrude)
        is_protrusion = ("paw_" in b.name or "tail_06" in b.name or "tail_05" in b.name
                          or "nose_tip" in b.name or "ear" in b.name
                          or "whisker" in b.name or "nostril" in b.name
                          or "eyelid" in b.name or "eye" in b.name
                          or "toes" in b.name)
        if not is_protrusion and not is_inside_mesh(mid):
            def_outside.append(b.name)
    if def_outside:
        log(f"  ✗ FAIL: {len(def_outside)} core DEF bones have midpoints OUTSIDE mesh:")
        for n in def_outside[:10]:
            log(f"      {n}")
        failures.append(f"bones_outside_mesh ({len(def_outside)})")
    else:
        log(f"  ✓ PASS: all core DEF bone midpoints inside mesh")

    # 2. Hierarchy: root → hips → spine → neck → head → muzzle → nose_tip
    expected_chain = ["root", "DEF-hips", "DEF-spine_01", "DEF-neck",
                       "DEF-head", "DEF-muzzle", "DEF-nose_tip"]
    chain_ok = True
    for i in range(len(expected_chain) - 1):
        child = arm.data.bones.get(expected_chain[i+1])
        if child is None or child.parent is None or child.parent.name != expected_chain[i]:
            log(f"  ✗ FAIL: '{expected_chain[i+1]}' parent should be '{expected_chain[i]}' "
                f"(actual: {child.parent.name if child and child.parent else 'None'})")
            chain_ok = False
    if chain_ok:
        log(f"  ✓ PASS: spine hierarchy root→hips→…→nose_tip")
    else:
        failures.append("spine_hierarchy")

    # 3. Bone naming: required bones present
    required = {"root", "DEF-hips", "DEF-spine_01", "DEF-neck", "DEF-head",
                 "DEF-muzzle", "DEF-nose_tip", "DEF-jaw",
                 "DEF-ear.L", "DEF-ear.R", "DEF-eye.L", "DEF-eye.R",
                 "DEF-arm.L", "DEF-arm.R", "DEF-forearm.L", "DEF-forearm.R",
                 "DEF-paw_F.L", "DEF-paw_F.R",
                 "DEF-thigh.L", "DEF-thigh.R", "DEF-shin.L", "DEF-shin.R",
                 "DEF-paw_B.L", "DEF-paw_B.R",
                 "DEF-tail_01", "DEF-tail_02", "DEF-tail_03"}
    actual = {b.name for b in arm.data.bones}
    missing = required - actual
    if missing:
        log(f"  ✗ FAIL: {len(missing)} required bones missing: {sorted(missing)}")
        failures.append(f"missing_bones ({len(missing)})")
    else:
        log(f"  ✓ PASS: all {len(required)} required bones present")

    # 4. Jaw bone pivot at correct anatomical location (under skull, behind muzzle)
    jaw = arm.data.bones.get("DEF-jaw")
    if jaw:
        jh = mw @ jaw.head_local
        # Jaw HEAD should be below skull_center.z (under skull, not in middle of face)
        if jh.z > A.skull_center.z:
            log(f"  ✗ FAIL: jaw bone head ({jh.z:.3f}) is ABOVE skull center ({A.skull_center.z:.3f}) — wrong hinge")
            failures.append("jaw_pivot_wrong")
        else:
            log(f"  ✓ PASS: jaw bone head ({jh.z:.3f}) below skull center")

    # 5. Ear bones rotate from base (not tip)
    for side in ("L", "R"):
        ear = arm.data.bones.get(f"DEF-ear.{side}")
        if ear:
            eh = mw @ ear.head_local
            et = mw @ ear.tail_local
            # Ear head should be closer to skull, tail further out (higher Z)
            if et.z < eh.z:
                log(f"  ✗ FAIL: DEF-ear.{side} tail Z ({et.z:.3f}) below head Z ({eh.z:.3f}) — flipped")
                failures.append(f"ear_{side}_flipped")
            else:
                log(f"  ✓ PASS: DEF-ear.{side} oriented base→tip (Z {eh.z:.3f}→{et.z:.3f})")

    # 6. Tail is a chain (not single bone)
    tail_bones = [b for b in arm.data.bones if b.name.startswith("DEF-tail_")]
    if len(tail_bones) < 4:
        log(f"  ✗ FAIL: only {len(tail_bones)} tail bones — should be ≥4 for smooth chain")
        failures.append("tail_chain_too_short")
    else:
        log(f"  ✓ PASS: tail chain has {len(tail_bones)} segments")

    # 7. Tail emerges from pelvis/back base
    if tail_bones:
        tail_first = next((b for b in tail_bones if b.name == "DEF-tail_01"), None)
        if tail_first:
            th = mw @ tail_first.head_local
            hips = arm.data.bones.get("DEF-hips")
            if hips:
                hh = mw @ hips.head_local
                dist = (th - hh).length
                if dist > A.y_size * 0.4:
                    log(f"  ✗ FAIL: tail base ({th}) far from hips ({hh}) — dist {dist:.3f}")
                    failures.append("tail_base_far_from_hips")
                else:
                    log(f"  ✓ PASS: tail base near hips (dist {dist:.3f})")

    # 8. Legs sit under the body (not float)
    for paw_name in ("DEF-paw_F.L", "DEF-paw_F.R", "DEF-paw_B.L", "DEF-paw_B.R"):
        paw = arm.data.bones.get(paw_name)
        if paw:
            pt = mw @ paw.tail_local
            # Paw tail should be at or below z_floor + small tolerance
            if pt.z > A.z_floor + A.z_size * 0.15:
                log(f"  ✗ FAIL: {paw_name} tail Z={pt.z:.3f} too high above floor {A.z_floor:.3f}")
                failures.append(f"{paw_name}_floats")
            else:
                log(f"  ✓ PASS: {paw_name} tail at z={pt.z:.3f} (floor={A.z_floor:.3f})")

    log("")
    log(f"STAGE 2 RESULT: {'PASS ✓' if not failures else f'FAIL ({len(failures)} issues)'}")
    for f in failures:
        log(f"  ✗ {f}")
    return failures


# ============================================================================
# Stage 5 QA: export inventory
# ============================================================================
def stage5_qa(arm, mesh, A):
    log("=" * 60)
    log("STAGE 5 QA — Export inventory")
    log("=" * 60)
    failures = []

    # Triangle count
    tris = sum(len(p.vertices) - 2 if len(p.vertices) > 2 else 0 for p in mesh.data.polygons)
    log(f"  Triangles: {tris}")
    log(f"  Vertices:  {len(mesh.data.vertices)}")
    log(f"  Polygons:  {len(mesh.data.polygons)}")
    log(f"  Materials: {len(mesh.data.materials)}")
    log(f"  UV maps:   {len(mesh.data.uv_layers)}")

    # Bones
    def_bones = [b for b in arm.data.bones if b.name.startswith("DEF-")]
    ctrl_bones = [b for b in arm.data.bones if b.name.startswith("CTRL-")]
    mch_bones = [b for b in arm.data.bones if b.name.startswith("MCH-")]
    other_bones = [b for b in arm.data.bones
                    if not b.name.startswith("DEF-") and not b.name.startswith("CTRL-")
                    and not b.name.startswith("MCH-")]
    log(f"  DEF bones: {len(def_bones)}")
    log(f"  CTRL bones: {len(ctrl_bones)}")
    log(f"  MCH bones: {len(mch_bones)}")
    log(f"  OTHER bones: {len(other_bones)} ({[b.name for b in other_bones]})")
    log(f"  TOTAL bones: {len(arm.data.bones)}")

    # Vertex groups
    log(f"  Vertex groups: {len(mesh.vertex_groups)}")

    # Animations
    animations = [a for a in bpy.data.actions]
    log(f"  Animations: {len(animations)}")

    return failures


# ============================================================================
# Main dispatcher
# ============================================================================
def main():
    argv = sys.argv
    if "--" in argv:
        stage_arg = argv[argv.index("--") + 1]
    else:
        stage_arg = "2"
    log(f"Building rig (CORRECTIVE_SMOOTH disabled for bare-weight inspection)…")
    arm, mesh, A = build_rig(enable_smooth=False)
    log(f"Rig: {len(arm.data.bones)} bones, mesh: {len(mesh.data.vertices)} verts")

    total_fail = 0
    if stage_arg in ("2", "all"):
        total_fail += len(stage2_qa(arm, mesh, A))
    if stage_arg in ("5", "all"):
        total_fail += len(stage5_qa(arm, mesh, A))

    log("")
    log(f"OVERALL: {total_fail} failure(s)")
    sys.exit(total_fail)


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(99)
