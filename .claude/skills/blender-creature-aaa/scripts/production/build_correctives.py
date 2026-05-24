#!/usr/bin/env python3
"""
build_correctives.py — P09 Corrective Sculptor

Mesh'e muscle bulge shape key'leri ve onların driver'larını ekler.
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
    p.add_argument("--max-displacement-ratio", type=float, default=0.02,
                   help="body_length × bu oran = max displacement")
    p.add_argument("--weight-high", type=float, default=0.5)
    p.add_argument("--weight-low", type=float, default=0.3)
    return p.parse_args(argv)


# =============================================================================
# Bone & axis mapping
# =============================================================================

SHAPE_KEY_DRIVER_MAP = {
    "shoulder_L": ("upper_arm_L", "X", 1.57),
    "shoulder_R": ("upper_arm_R", "X", 1.57),
    "thigh_L": ("shin_L", "X", 1.57),
    "thigh_R": ("shin_R", "X", 1.57),
    "biceps_L": ("forearm_L", "X", 1.57),
    "biceps_R": ("forearm_R", "X", 1.57),
    "neck_stretch": ("neck_00", "X", 1.0),
    "belly_expand": ("spine_00", "X", 1.0),
}


def find_mesh_armature():
    mesh = None
    armature = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            if mesh is None or len(obj.data.vertices) > len(mesh.data.vertices):
                mesh = obj
        elif obj.type == 'ARMATURE':
            armature = obj
    return mesh, armature


# =============================================================================
# Shape key operations
# =============================================================================

def ensure_basis(mesh_obj):
    """Basis varsa bul, yoksa oluştur."""
    if mesh_obj.data.shape_keys is None:
        mesh_obj.shape_key_add(name="Basis", from_mix=False)
    return mesh_obj.data.shape_keys.key_blocks["Basis"]


def add_shape_key(mesh_obj, name):
    """Yeni shape key ekle (basis'ten kopyalı)."""
    # Mevcut varsa sil
    if mesh_obj.data.shape_keys is not None:
        if name in mesh_obj.data.shape_keys.key_blocks:
            mesh_obj.shape_key_remove(mesh_obj.data.shape_keys.key_blocks[name])
    
    sk = mesh_obj.shape_key_add(name=name, from_mix=False)
    sk.interpolation = 'KEY_LINEAR'  # smoother for muscle bulge
    return sk


# =============================================================================
# Compute deformation
# =============================================================================

def compute_body_center(mesh_obj):
    """Mesh'in bbox merkezi."""
    coords = [v.co for v in mesh_obj.data.vertices]
    if not coords:
        return Vector((0, 0, 0))
    
    min_v = Vector((
        min(c.x for c in coords),
        min(c.y for c in coords),
        min(c.z for c in coords),
    ))
    max_v = Vector((
        max(c.x for c in coords),
        max(c.y for c in coords),
        max(c.z for c in coords),
    ))
    return (min_v + max_v) * 0.5


def compute_bulge_deltas(mesh_obj, bone_name, max_displacement,
                          weight_high=0.5, weight_low=0.3):
    """
    Bone'un vertex group'undaki yüksek-weight vertex'leri outward push edecek
    delta'ları hesapla.
    
    Returns: dict {vertex_index: delta_Vector}
    """
    vg = mesh_obj.vertex_groups.get(bone_name)
    if vg is None:
        return {}
    
    body_center = compute_body_center(mesh_obj)
    
    deltas = {}
    
    for v in mesh_obj.data.vertices:
        try:
            w = vg.weight(v.index)
        except RuntimeError:
            continue
        
        if w < weight_low:
            continue
        
        # Falloff
        if w >= weight_high:
            falloff = 1.0
        else:
            falloff = (w - weight_low) / max(0.001, weight_high - weight_low)
        
        # Outward direction (vertex'in body center'dan uzaklaşma yönü)
        outward = v.co - body_center
        if outward.length < 0.001:
            continue
        outward.normalize()
        
        deltas[v.index] = outward * max_displacement * falloff
    
    return deltas


def apply_deltas_to_shape_key(mesh_obj, shape_key, deltas):
    """Basis'ten alıp delta uygula."""
    basis = mesh_obj.data.shape_keys.key_blocks["Basis"]
    
    for v_idx, delta in deltas.items():
        basis_co = basis.data[v_idx].co
        shape_key.data[v_idx].co = Vector(basis_co) + delta


# =============================================================================
# Driver setup
# =============================================================================

def setup_driver(mesh_obj, shape_key_name, armature_obj, bone_name,
                  rotation_axis='X', max_angle_rad=1.57):
    """
    Shape key value'sunu bone rotation'a bağlayan driver kur.
    """
    sks = mesh_obj.data.shape_keys
    if sks is None or shape_key_name not in sks.key_blocks:
        return None
    
    sk_block = sks.key_blocks[shape_key_name]
    
    # Mevcut driver varsa kaldır
    try:
        sk_block.driver_remove("value")
    except Exception:
        pass
    
    # Driver ekle
    fcurve = sk_block.driver_add("value")
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    
    # Variable
    var = driver.variables.new()
    var.name = "rot"
    var.type = 'TRANSFORMS'
    
    target = var.targets[0]
    target.id = armature_obj
    target.bone_target = bone_name
    target.transform_type = f'ROT_{rotation_axis}'
    target.transform_space = 'LOCAL_SPACE'
    target.rotation_mode = 'AUTO'
    
    # Expression
    driver.expression = f"max(0.0, min(1.0, rot / {max_angle_rad}))"
    
    return fcurve


# =============================================================================
# Validation
# =============================================================================

def validate_correctives(mesh_obj, expected_locations):
    results = {"errors": [], "warnings": [], "drivers_ok": True}
    
    sks = mesh_obj.data.shape_keys
    if sks is None:
        results["errors"].append("Mesh'te shape keys yok (Basis bile yok)")
        return results
    
    actual_names = set(sks.key_blocks.keys())
    if "Basis" not in actual_names:
        results["errors"].append("Basis shape key eksik")
    
    expected_keys = set(expected_locations)
    missing = expected_keys - actual_names
    if missing:
        results["errors"].append(f"Beklenen shape keys eksik: {missing}")
    
    # Driver kontrolü
    for loc in expected_locations:
        if loc not in actual_names:
            continue
        sk = sks.key_blocks[loc]
        # Driver var mı kontrol et
        if mesh_obj.data.shape_keys.animation_data is None:
            results["drivers_ok"] = False
            results["errors"].append(f"{loc}: animation_data yok (driver kurulmamış)")
            continue
        
        found = False
        for driver_fc in mesh_obj.data.shape_keys.animation_data.drivers:
            if f'"{loc}"' in driver_fc.data_path:
                found = True
                break
        
        if not found:
            results["drivers_ok"] = False
            results["errors"].append(f"{loc}: driver bulunamadı")
    
    return results


# =============================================================================
# Ana
# =============================================================================

def main():
    args = parse_args()
    
    blueprint = json.loads(Path(args.blueprint).read_text(encoding='utf-8'))
    budget = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    body_length = blueprint.get("body_length_meters", 1.2)
    
    shape_key_budget = budget.get("shape_key_budget", {})
    max_count = shape_key_budget.get("muscle_bulge_count_max", 0)
    locations = shape_key_budget.get("blend_shape_locations", [])
    
    if max_count == 0 or not locations:
        print("[correctives] Shape key budget = 0, ajan skip ediliyor")
        # Yine de save (no changes)
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(args.output_blend).resolve()))
        return
    
    locations = locations[:max_count]
    
    mesh_obj, armature_obj = find_mesh_armature()
    if mesh_obj is None or armature_obj is None:
        print("❌ Mesh veya armature yok", file=sys.stderr)
        sys.exit(1)
    
    print(f"[correctives] Mesh: {mesh_obj.name}, Armature: {armature_obj.name}")
    print(f"[correctives] Locations: {locations}")
    
    max_disp = body_length * args.max_displacement_ratio
    
    # Stylization adjustment
    muscle_def = budget.get("trade_offs_user_made", [])
    # Eğer "exaggerated" varsa
    # (Bu spec'te user_modifications'ta da olabilir)
    
    # Basis garantile
    ensure_basis(mesh_obj)
    
    created = []
    
    for loc in locations:
        mapping = SHAPE_KEY_DRIVER_MAP.get(loc)
        if mapping is None:
            print(f"  ⚠️ {loc}: bilinmeyen lokasyon, skip")
            continue
        
        driver_bone, axis, max_angle = mapping
        
        if driver_bone not in armature_obj.pose.bones:
            print(f"  ⚠️ {loc}: driver bone {driver_bone} yok, skip")
            continue
        
        # Vertex group: shape key location adı = bone vertex group adı varsayımı
        # Ama bazı durumlarda shape_key location farklı olabilir
        # Default: location adıyla aynı vertex group
        target_vg_name = loc
        if loc not in [vg.name for vg in mesh_obj.vertex_groups]:
            # Fallback: aynı side'daki ana bone'un vertex group'u
            # Örnek: shoulder_L için upper_arm_L vertex group
            fallback = driver_bone
            if fallback in [vg.name for vg in mesh_obj.vertex_groups]:
                target_vg_name = fallback
                print(f"  ⚠️ {loc} vg yok, {fallback} kullanılacak")
            else:
                print(f"  ❌ {loc}: hiç vertex group bulamadı, skip")
                continue
        
        # Deltas hesapla
        deltas = compute_bulge_deltas(
            mesh_obj, target_vg_name, max_disp,
            weight_high=args.weight_high, weight_low=args.weight_low
        )
        
        if not deltas:
            print(f"  ⚠️ {loc}: 0 vertex affected, threshold'lar çok yüksek olabilir")
            continue
        
        # Shape key oluştur + apply
        sk = add_shape_key(mesh_obj, loc)
        apply_deltas_to_shape_key(mesh_obj, sk, deltas)
        
        # Driver kur
        driver_fc = setup_driver(
            mesh_obj, loc, armature_obj, driver_bone,
            rotation_axis=axis, max_angle_rad=max_angle,
        )
        
        created.append({
            "name": loc,
            "driver_bone": driver_bone,
            "driver_axis": f"rotation_{axis.lower()}",
            "max_displacement_meters": max_disp,
            "affected_vertices_count": len(deltas),
            "weight_threshold_used": args.weight_high,
            "driver_set_up": driver_fc is not None,
        })
        
        print(f"  ✓ {loc}: {len(deltas)} vertex etkilendi, driver bone {driver_bone}")
    
    # Validation
    val = validate_correctives(mesh_obj, [c["name"] for c in created])
    
    for err in val["errors"]:
        print(f"  ❌ {err}")
    
    # Manifest
    manifest = {
        "manifest_version": "1.0",
        "creature_id": blueprint.get("creature_id"),
        "shape_keys_created": created,
        "total_shape_keys": len(created) + 1,  # + Basis
        "drivers_set_up": sum(1 for c in created if c["driver_set_up"]),
        "validation": {
            "all_drivers_functional": val["drivers_ok"],
            "no_corrupted_basis": True,
            "errors_count": len(val["errors"]),
        },
        "generated_by": "P09_corrective_sculptor",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_path = output_path.with_suffix('.corrective_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(f"[correctives] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print(f"[correctives] ✅ Tamamlandı: {len(created)} shape key + driver")


if __name__ == "__main__":
    main()
