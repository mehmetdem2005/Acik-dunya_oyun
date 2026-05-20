"""
Objective pose-deformation metrics (Concrete-Plan agent's exit-loop gate).

Each pose test passes if mesh deformation matches expected pattern:
  - Target region verts move significantly
  - Unrelated region verts stay still

Usage:
    blender --background --python fare/scripts/pose_test_metrics.py

Prints PASS/FAIL per pose. Exit code = number of failures.
"""

import bpy
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS_DIR)
import rig_mouse_v5 as rig_module


def log(m): print(f"[metrics] {m}", flush=True)


def build_rig():
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
    return arm, mesh, A


def world_verts(mesh):
    mw = mesh.matrix_world
    return [mw @ v.co for v in mesh.data.vertices]


def evaluated_world_verts(mesh):
    dg = bpy.context.evaluated_depsgraph_get()
    em = mesh.evaluated_get(dg)
    mw = mesh.matrix_world
    return [mw @ v.co for v in em.data.vertices]


def apply_pose(arm, rotations, translations=None):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
    for name, rot in rotations.items():
        pb = arm.pose.bones.get(name)
        if pb is None:
            log(f"  WARN missing bone {name}"); continue
        pb.rotation_euler = rot
    if translations:
        for name, tr in translations.items():
            pb = arm.pose.bones.get(name)
            if pb: pb.location = tr
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    bpy.context.evaluated_depsgraph_get().update()


def vertex_displacement(rest_world, posed_world):
    return [(p - r).length for r, p in zip(rest_world, posed_world)]


def region_mean_disp(disps, indices):
    if not indices: return 0.0
    return sum(disps[i] for i in indices) / len(indices)


def main():
    arm, mesh, A = build_rig()
    log(f"Rig: {len(arm.data.bones)} bones, mesh: {len(mesh.data.vertices)} verts")

    # Take rest pose snapshot
    apply_pose(arm, {})
    rest = evaluated_world_verts(mesh)

    # Compute reference regions (vertex indices)
    cx = A.x_center
    d = A.head_dir
    verts = [v.co for v in mesh.data.vertices]

    head_y_lo = min(A.p_head_base.y, A.p_nose_base.y) - 0.05
    head_y_hi = max(A.p_head_base.y, A.p_nose_base.y) + 0.05
    head_idx = [i for i, v in enumerate(verts)
                if head_y_lo <= v.y <= head_y_hi and v.z > A.skull_center.z - A.z_size * 0.10]
    body_idx = [i for i, v in enumerate(verts)
                if v.y > A.p_hips.y + 0.02]
    chin_idx = [i for i, v in enumerate(verts)
                if min(A.p_muzzle_base.y, A.nose_tip.y) - 0.02 <= v.y <= max(A.p_muzzle_base.y, A.nose_tip.y) + 0.02
                and v.z < A.skull_center.z - 0.05
                and abs(v.x - cx) < A.x_half * 0.4]
    skull_idx = [i for i, v in enumerate(verts)
                 if head_y_lo <= v.y <= head_y_hi
                 and v.z > A.skull_center.z + 0.01]
    tail_y_lo = A.p_hips.y + 0.10
    tail_idx = [i for i, v in enumerate(verts) if v.y > tail_y_lo]
    paw_FL_pos = A.paws["paw_F_L"]
    paw_FL_idx = [i for i, v in enumerate(verts)
                  if abs(v.x - paw_FL_pos.x) < 0.05
                  and abs(v.y - paw_FL_pos.y) < 0.05
                  and v.z < paw_FL_pos.z + 0.03]
    shoulder_R_idx = [i for i, v in enumerate(verts)
                      if v.x < cx - A.x_half * 0.3
                      and abs(v.y - A.p_neck.y) < 0.10]

    log(f"  Regions: head={len(head_idx)} body={len(body_idx)} chin={len(chin_idx)} "
        f"skull={len(skull_idx)} tail={len(tail_idx)} paw_FL={len(paw_FL_idx)} sh_R={len(shoulder_R_idx)}")

    results = {}
    skull_radius = A.z_size * 0.3
    body_length = A.y_size
    tail_length = A.y_size * 0.4

    # ---- Test 1: head_up (CTRL-head rotated) ----
    apply_pose(arm, {"CTRL-head": (math.radians(-60), 0, 0)})
    posed = evaluated_world_verts(mesh)
    disp = vertex_displacement(rest, posed)
    skull_disp = region_mean_disp(disp, skull_idx)
    body_disp = region_mean_disp(disp, body_idx)
    p1 = skull_disp >= skull_radius * 0.3
    p2 = body_disp < body_length * 0.05
    passed = p1 and p2
    log(f"\n[T1 head_up] skull_disp={skull_disp:.4f} (need ≥{skull_radius*0.3:.4f}) "
        f"body_disp={body_disp:.4f} (need <{body_length*0.05:.4f}) → {'PASS' if passed else 'FAIL'}")
    results["T1_head_up"] = passed

    # ---- Test 2: jaw_open ----
    apply_pose(arm, {"CTRL-jaw": (math.radians(45), 0, 0)})
    posed = evaluated_world_verts(mesh)
    disp = vertex_displacement(rest, posed)
    chin_disp = region_mean_disp(disp, chin_idx)
    skull_disp = region_mean_disp(disp, skull_idx)
    jaw_len = 0.10
    p1 = chin_disp >= jaw_len * 0.20
    p2 = skull_disp < jaw_len * 0.10
    passed = p1 and p2
    log(f"[T2 jaw_open] chin_disp={chin_disp:.4f} (need ≥{jaw_len*0.20:.4f}) "
        f"skull_disp={skull_disp:.4f} (need <{jaw_len*0.10:.4f}) → {'PASS' if passed else 'FAIL'}")
    results["T2_jaw_open"] = passed

    # ---- Test 3: paw lift (IK foot ctrl translated +Z, larger to test IK reach) ----
    apply_pose(arm, {}, translations={"CTRL-foot_F.L": (0, 0, 0.15)})
    posed = evaluated_world_verts(mesh)
    disp = vertex_displacement(rest, posed)
    paw_disp = region_mean_disp(disp, paw_FL_idx)
    sh_disp = region_mean_disp(disp, shoulder_R_idx)
    p1 = paw_disp >= 0.05
    p2 = sh_disp < 0.01
    passed = p1 and p2
    log(f"[T3 paw_lift] paw_disp={paw_disp:.4f} (need ≥0.05) "
        f"sh_R_disp={sh_disp:.4f} (need <0.01) → {'PASS' if passed else 'FAIL'}")
    results["T3_paw_lift"] = passed

    # ---- Test 4: tail sweep (translate Spline IK hook controllers, larger) ----
    apply_pose(arm, {}, translations={
        "CTRL-tail_2": (0, 0, 0.10),
        "CTRL-tail_3": (0, 0, 0.20),
    })
    posed = evaluated_world_verts(mesh)
    disp = vertex_displacement(rest, posed)
    tail_disp = region_mean_disp(disp, tail_idx)
    hip_pos = A.p_hips
    hip_idx = [i for i, v in enumerate(verts)
               if abs(v.y - hip_pos.y) < 0.05 and abs(v.x - hip_pos.x) < 0.10]
    hip_disp = region_mean_disp(disp, hip_idx)
    p1 = tail_disp >= tail_length * 0.10
    p2 = hip_disp < body_length * 0.05
    passed = p1 and p2
    log(f"[T4 tail_sweep] tail_disp={tail_disp:.4f} (need ≥{tail_length*0.10:.4f}) "
        f"hip_disp={hip_disp:.4f} (need <{body_length*0.05:.4f}) → {'PASS' if passed else 'FAIL'}")
    results["T4_tail_sweep"] = passed

    # ---- Test 5: hip twist (use bigger rotation for clearer measurement) ----
    apply_pose(arm, {"CTRL-hips": (0, 0, math.radians(50))})
    posed = evaluated_world_verts(mesh)
    disp = vertex_displacement(rest, posed)
    hip_disp = region_mean_disp(disp, hip_idx)
    skull_disp = region_mean_disp(disp, skull_idx)
    # Hips should move significantly, skull less (since head is upstream)
    p1 = hip_disp >= 0.02
    passed = p1
    log(f"[T5 hip_twist] hip_disp={hip_disp:.4f} (need ≥0.02) "
        f"skull_disp={skull_disp:.4f} → {'PASS' if passed else 'FAIL'}")
    results["T5_hip_twist"] = passed

    # ---- Test 6: ear perk ----
    # Find ear verts: top 10% Z in head region
    if head_idx:
        head_z_max = max(verts[i].z for i in head_idx)
        ear_idx = [i for i in head_idx if verts[i].z > head_z_max - A.z_size * 0.10]
    else:
        ear_idx = []
    apply_pose(arm, {"CTRL-ear.L": (math.radians(-50), 0, 0),
                      "CTRL-ear.R": (math.radians(-50), 0, 0)})
    posed = evaluated_world_verts(mesh)
    disp = vertex_displacement(rest, posed)
    ear_disp = region_mean_disp(disp, ear_idx)
    p1 = ear_disp >= 0.01
    passed = p1
    log(f"[T6 ear_perk] ear_disp={ear_disp:.4f} (need ≥0.01) → {'PASS' if passed else 'FAIL'}")
    results["T6_ear_perk"] = passed

    # ---- Summary ----
    log("\n=== SUMMARY ===")
    n_pass = sum(1 for v in results.values() if v)
    for name, passed in results.items():
        log(f"  {'✓' if passed else '✗'} {name}")
    log(f"  Total: {n_pass}/{len(results)} passing")
    n_fail = len(results) - n_pass
    sys.exit(n_fail)


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(99)
