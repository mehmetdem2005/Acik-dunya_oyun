#!/usr/bin/env python3
"""
build_skinning.py — P08 Skinner'ın executable component

Mesh ile armature arasındaki vertex weight'leri kurar.
Voxel HDS varsa onunla, yoksa Automatic Weights + post-process.

Kullanım:
    blender --background <mesh_v1.blend> --python build_skinning.py -- \
        --blueprint <SkeletonBlueprint.json> \
        --budget <BudgetSpec.json> \
        --output-blend <skinned_v1.blend> \
        [--method auto|voxel_hds|automatic_weights]
"""

import bpy
import json
import sys
import argparse
from pathlib import Path
from mathutils import Vector


def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser()
    p.add_argument("--blueprint", required=True)
    p.add_argument("--budget", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--method", default="auto", choices=["auto", "voxel_hds", "automatic_weights"])
    p.add_argument("--max-influences", type=int, default=4)
    p.add_argument("--smooth-passes", type=int, default=2)
    p.add_argument("--symmetry-tolerance", type=float, default=0.01)
    return p.parse_args(argv)


# =============================================================================
# Method tespiti
# =============================================================================

def detect_voxel_hds_operator():
    """Voxel HDS addon'unun operator adını bul."""
    candidates = [
        ("wm", "voxel_heat_diffuse"),
        ("object", "voxel_heat_diffuse_skinning"),
        ("mesh", "voxel_heat_diffuse"),
    ]
    
    for cat, name in candidates:
        op_cat = getattr(bpy.ops, cat, None)
        if op_cat is not None:
            op = getattr(op_cat, name, None)
            if op is not None:
                # Operator var, mevcut context'te poll geçer mi?
                return f"{cat}.{name}"
    
    return None


def find_mesh_and_armature():
    """Sahnedeki mesh ve armature objelerini bul."""
    mesh = None
    armature = None
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            # En büyük mesh
            if mesh is None or len(obj.data.vertices) > len(mesh.data.vertices):
                mesh = obj
        elif obj.type == 'ARMATURE':
            if armature is None or len(obj.data.bones) > len(armature.data.bones):
                armature = obj
    
    return mesh, armature


# =============================================================================
# Vertex Groups setup
# =============================================================================

def ensure_vertex_groups_for_bones(mesh_obj, armature_obj):
    """Her deform bone için mesh'te vertex group oluştur."""
    existing = set(vg.name for vg in mesh_obj.vertex_groups)
    
    for bone in armature_obj.data.bones:
        if bone.use_deform and bone.name not in existing:
            mesh_obj.vertex_groups.new(name=bone.name)


# =============================================================================
# Skinning methods
# =============================================================================

def skin_voxel_hds(mesh_obj, armature_obj, operator_name):
    """Voxel HDS addon ile."""
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    
    cat, name = operator_name.split(".")
    op = getattr(getattr(bpy.ops, cat), name)
    
    try:
        # Default parametrelerle dene
        op()
        return True
    except Exception as e:
        print(f"  ⚠️ Voxel HDS fail: {e}")
        return False


def skin_automatic_weights(mesh_obj, armature_obj):
    """Blender Automatic Weights (parent + auto weights)."""
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        return True
    except Exception as e:
        print(f"  ❌ Automatic Weights fail: {e}")
        return False


def ensure_armature_modifier(mesh_obj, armature_obj):
    """Mesh'te Armature modifier yoksa ekle."""
    arm_mod = None
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE':
            arm_mod = mod
            break
    
    if arm_mod is None:
        arm_mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    
    arm_mod.object = armature_obj
    arm_mod.use_vertex_groups = True


# =============================================================================
# Post-processing
# =============================================================================

def normalize_weights(mesh_obj):
    """Her vertex'in weight'lerini sum=1.0 olacak şekilde normalize et."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)
    return True


def cap_weights_to_n(mesh_obj, n=4):
    """Limit number of bones per vertex (mobile shader constraint)."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=n)
    return True


def smooth_weights(mesh_obj, factor=0.5, iterations=2):
    """Vertex weight'lerini komşu vertex'lerle yumuşat."""
    bpy.context.view_layer.objects.active = mesh_obj
    
    # Mesh seçili olmalı
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    
    # Tüm vertex'leri seç
    bpy.ops.paint.weight_paint_toggle()  # toggle paint mode için bazı versiyon
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    
    for _ in range(iterations):
        try:
            bpy.ops.object.vertex_group_smooth(
                group_select_mode='ALL',
                factor=factor,
                repeat=1,
            )
        except Exception as e:
            print(f"  ⚠️ Smooth pass fail: {e}")
            break
    
    bpy.ops.object.mode_set(mode='OBJECT')
    return True


def mirror_weights_x(mesh_obj, tolerance=0.01):
    """X<0 vertex'lerinden X>0 vertex'lerine weight mirror et."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Blender'ın built-in vertex_group_mirror operator
    # NOT: bu sadece L/R name suffix'iyle çalışır, vertex coordinatları kontrol etmez
    # Yine de iyi sonuç verir
    
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    
    try:
        # Vertex select all in edit mode
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        bpy.ops.object.vertex_group_mirror(
            mirror_weights=True,
            flip_group_names=True,
            all_groups=True,
            use_topology=False,
        )
        return True
    except Exception as e:
        print(f"  ⚠️ Mirror weights fail: {e}")
        return False


def cleanup_zero_weights(mesh_obj, threshold=0.001):
    """0'a yakın weight'leri sil."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    bpy.ops.object.vertex_group_clean(
        group_select_mode='ALL',
        limit=threshold,
        keep_single=True,  # vertex weight'siz kalmasın
    )


# =============================================================================
# Validation
# =============================================================================

def validate_skinning(mesh_obj, max_influences=4):
    """Skinning kalitesi kontrol."""
    results = {
        "all_verts_have_weights": True,
        "all_weights_sum_to_one": True,
        "no_negative_weights": True,
        "orphan_count": 0,
        "weight_sum_violation_count": 0,
        "over_max_influence_count": 0,
        "negative_count": 0,
        "errors": [],
        "warnings": [],
        "per_bone_count": {},
    }
    
    vgroups = mesh_obj.vertex_groups
    verts = mesh_obj.data.vertices
    
    for vert in verts:
        weights = []
        for vg in vgroups:
            try:
                w = vg.weight(vert.index)
                if w != 0:
                    weights.append((vg.name, w))
            except RuntimeError:
                pass
        
        if not weights:
            results["orphan_count"] += 1
            results["all_verts_have_weights"] = False
            continue
        
        # Sum check
        total = sum(w for _, w in weights)
        if abs(total - 1.0) > 0.01:
            results["weight_sum_violation_count"] += 1
            results["all_weights_sum_to_one"] = False
        
        # Influence count
        if len(weights) > max_influences:
            results["over_max_influence_count"] += 1
        
        # Negative check
        for name, w in weights:
            if w < 0:
                results["negative_count"] += 1
                results["no_negative_weights"] = False
            # Per-bone count
            results["per_bone_count"][name] = results["per_bone_count"].get(name, 0) + 1
    
    if results["orphan_count"]:
        results["errors"].append(f"Orphan vertex (weight'siz): {results['orphan_count']}")
    if results["weight_sum_violation_count"]:
        results["errors"].append(
            f"Weight sum != 1.0: {results['weight_sum_violation_count']} vertex"
        )
    if results["over_max_influence_count"]:
        results["errors"].append(
            f"Over {max_influences} influence: {results['over_max_influence_count']} vertex"
        )
    if results["negative_count"]:
        results["errors"].append(f"Negative weight: {results['negative_count']} vertex")
    
    return results


def measure_symmetry_delta(mesh_obj):
    """Sol-sağ vertex pair'lerinin weight farkını ölç (max delta)."""
    try:
        import numpy as np
    except ImportError:
        return None
    
    verts = mesh_obj.data.vertices
    coords = np.array([[v.co.x, v.co.y, v.co.z] for v in verts])
    
    left_idx = np.where(coords[:, 0] < -0.001)[0]
    right_idx = np.where(coords[:, 0] > 0.001)[0]
    
    if len(left_idx) == 0 or len(right_idx) == 0:
        return 0.0
    
    vgroups = list(mesh_obj.vertex_groups)
    
    # Sol-sağ vertex eşleştirme
    right_coords = coords[right_idx]
    
    max_delta = 0.0
    
    for li in left_idx[:200]:  # sample 200 for speed
        left_co = coords[li]
        mirror_target = np.array([-left_co[0], left_co[1], left_co[2]])
        dists = np.linalg.norm(right_coords - mirror_target, axis=1)
        ri = right_idx[np.argmin(dists)]
        
        if dists[np.argmin(dists)] > 0.02:
            continue  # mirror çift yok
        
        # Her vgroup'ta her iki vertex'in weight'lerini karşılaştır
        for vg in vgroups:
            try:
                lw = vg.weight(li)
            except RuntimeError:
                lw = 0
            try:
                rw = vg.weight(ri)
            except RuntimeError:
                rw = 0
            
            # Eğer bone L/R suffix'liyse, sol vertex'in L bone weight'i
            # sağ vertex'in R bone weight'ine eşit olmalı
            if vg.name.endswith("_L"):
                # Sağ counterpart
                r_vg_name = vg.name[:-2] + "_R"
                r_vg = mesh_obj.vertex_groups.get(r_vg_name)
                if r_vg is None:
                    continue
                try:
                    rw_mirror = r_vg.weight(ri)
                except RuntimeError:
                    rw_mirror = 0
                delta = abs(lw - rw_mirror)
            else:
                # Center bone, soldaki vs sağdaki aynı bone
                delta = abs(lw - rw)
            
            if delta > max_delta:
                max_delta = delta
    
    return max_delta


# =============================================================================
# Ana akış
# =============================================================================

def main():
    args = parse_args()
    
    blueprint = json.loads(Path(args.blueprint).read_text(encoding='utf-8'))
    budget_spec = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    
    print("[skinner] Mesh ve armature aranıyor...")
    mesh_obj, armature_obj = find_mesh_and_armature()
    
    if mesh_obj is None or armature_obj is None:
        print(f"❌ Mesh veya armature bulunamadı: mesh={mesh_obj}, armature={armature_obj}",
              file=sys.stderr)
        sys.exit(1)
    
    print(f"  ✓ Mesh: {mesh_obj.name} ({len(mesh_obj.data.vertices)} vertex)")
    print(f"  ✓ Armature: {armature_obj.name} ({len(armature_obj.data.bones)} bone)")
    
    # Vertex groups
    ensure_vertex_groups_for_bones(mesh_obj, armature_obj)
    
    # Method seç
    print(f"[skinner] Method tespiti (request: {args.method})...")
    voxel_op = detect_voxel_hds_operator()
    
    if args.method == "voxel_hds":
        if voxel_op is None:
            print("❌ Voxel HDS addon yüklü değil ama açıkça istendi", file=sys.stderr)
            sys.exit(1)
        method = "voxel_hds"
        op_name = voxel_op
    elif args.method == "automatic_weights":
        method = "automatic_weights"
        op_name = None
    else:  # auto
        if voxel_op:
            method = "voxel_hds"
            op_name = voxel_op
            print(f"  ✓ Voxel HDS bulundu: {voxel_op}")
        else:
            method = "automatic_weights"
            op_name = None
            print("  ⚠️ Voxel HDS yok, Automatic Weights kullanılacak")
    
    # Skin
    print(f"[skinner] Skinning ({method})...")
    if method == "voxel_hds":
        success = skin_voxel_hds(mesh_obj, armature_obj, op_name)
        if not success:
            print("  ⚠️ Voxel HDS fail, Automatic Weights fallback")
            success = skin_automatic_weights(mesh_obj, armature_obj)
    else:
        success = skin_automatic_weights(mesh_obj, armature_obj)
    
    if not success:
        print("❌ Skinning hiç çalışmadı", file=sys.stderr)
        sys.exit(2)
    
    ensure_armature_modifier(mesh_obj, armature_obj)
    
    # Post-process pipeline
    post_passes = []
    
    print("[skinner] Post-processing: normalize")
    normalize_weights(mesh_obj)
    post_passes.append({"name": "normalize", "applied": True})
    
    print(f"[skinner] Post-processing: cap to {args.max_influences} influences")
    cap_weights_to_n(mesh_obj, args.max_influences)
    post_passes.append({"name": "cap_to_n", "applied": True, "n": args.max_influences})
    
    print("[skinner] Post-processing: mirror X")
    mirrored = mirror_weights_x(mesh_obj, args.symmetry_tolerance)
    post_passes.append({"name": "mirror_x", "applied": mirrored})
    
    print(f"[skinner] Post-processing: smooth × {args.smooth_passes}")
    smooth_weights(mesh_obj, factor=0.5, iterations=args.smooth_passes)
    post_passes.append({"name": "smooth", "applied": True, "iterations": args.smooth_passes})
    
    print("[skinner] Post-processing: cleanup zero weights")
    cleanup_zero_weights(mesh_obj, threshold=0.001)
    post_passes.append({"name": "cleanup_zero", "applied": True})
    
    # Final normalize (cap ve cleanup sonrası sum 1 olmayabilir)
    normalize_weights(mesh_obj)
    
    # Validation
    print("[skinner] Validation...")
    val = validate_skinning(mesh_obj, args.max_influences)
    
    for err in val["errors"]:
        print(f"  ❌ {err}")
    for warn in val["warnings"]:
        print(f"  ⚠️ {warn}")
    
    # Symmetry delta
    symmetry_delta = measure_symmetry_delta(mesh_obj)
    print(f"  ✓ Symmetry max delta: {symmetry_delta}")
    
    # Manifest
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "manifest_version": "1.0",
        "method_used": method,
        "armature_modifier_added": True,
        "vertex_groups_count": len(mesh_obj.vertex_groups),
        "max_influences_per_vertex_target": args.max_influences,
        "weights_normalized": val["all_weights_sum_to_one"],
        "symmetry_enforced": symmetry_delta is not None and symmetry_delta < 0.01,
        "symmetry_max_delta": symmetry_delta,
        "orphan_vertices_count": val["orphan_count"],
        "post_processing_passes": post_passes,
        "per_bone_vertex_count": val["per_bone_count"],
        "validation": {
            "all_verts_have_weights": val["all_verts_have_weights"],
            "all_weights_sum_to_one": val["all_weights_sum_to_one"],
            "no_negative_weights": val["no_negative_weights"],
            "over_max_influence_count": val["over_max_influence_count"],
        },
        "errors": val["errors"],
        "warnings": val["warnings"],
        "generated_by": "P08_skinner",
    }
    
    manifest_path = output_path.with_suffix('.skinning_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    # Save
    print(f"[skinner] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print("[skinner] ✅ Tamamlandı")


if __name__ == "__main__":
    main()
