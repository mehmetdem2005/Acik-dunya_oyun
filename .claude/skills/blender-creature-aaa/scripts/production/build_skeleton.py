#!/usr/bin/env python3
"""
build_skeleton.py — P03 Skeleton Architect'in executable component

Bu script Blender içinde çalışır:
    blender --background --python build_skeleton.py -- \
        --blueprint <path/to/SkeletonBlueprint.json> \
        --output-blend <path/to/skeleton_v1.blend> \
        [--validate-only]

SkeletonBlueprint.json'dan armature oluşturur, IK constraint'leri ekler,
twist bone'ları setup eder, validation yapar, .blend dosyasına kaydeder.

ÖNEMLİ:
- Tüm koordinatlar local space (world ile aynı, çünkü armature origin = world origin)
- Bone roll'lar SkeletonBlueprint'te radyan olarak verili, doğrudan uygulanır
- Pole vector matematiği SkeletonBlueprint'te zaten hesaplandı, burada sadece
  pole bone'ları doğru yere koyulur
- IK constraint kurma: Pose mode'da, constraint chain_length parametresi ile

ÇIKTI:
    <output_blend>: Armature içeren Blender dosyası
    <output_blend>.validation.json: Validation raporu
"""

import bpy
import json
import math
import sys
import argparse
from pathlib import Path
from mathutils import Vector, Matrix


# =============================================================================
# Argument parsing
# =============================================================================

def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser()
    p.add_argument("--blueprint", required=True, help="SkeletonBlueprint.json")
    p.add_argument("--output-blend", required=True, help="Çıkış .blend dosyası")
    p.add_argument("--validate-only", action="store_true",
                   help="Sadece validate et, Blender dosyasını yazma")
    p.add_argument("--armature-name", default="CreatureArmature")
    return p.parse_args(argv)


# =============================================================================
# Sahne temizleme ve hazırlık
# =============================================================================

def clean_scene():
    """Sahneyi tamamen temizle."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Orphan data'yı da temizle
    for collection in (bpy.data.armatures, bpy.data.meshes, bpy.data.materials,
                       bpy.data.lights, bpy.data.cameras):
        for item in collection:
            try:
                collection.remove(item)
            except Exception:
                pass


def setup_units():
    """Birim sistemi: meter, Y forward, Z up (Blender default)."""
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'


# =============================================================================
# Armature oluşturma
# =============================================================================

def create_armature(name="CreatureArmature"):
    """Boş bir armature objesi oluştur."""
    armature_data = bpy.data.armatures.new(name)
    armature_obj = bpy.data.objects.new(name, armature_data)
    bpy.context.collection.objects.link(armature_obj)
    
    # Aktif yap
    bpy.context.view_layer.objects.active = armature_obj
    armature_obj.select_set(True)
    
    return armature_obj


def add_edit_bone(armature_obj, name, head, tail, roll=0.0, parent_name=None,
                   use_connect=False, use_deform=True):
    """
    Armature edit mode'unda yeni bone ekler.
    
    armature_obj edit mode'da olmalı çağrılmadan önce.
    """
    ebones = armature_obj.data.edit_bones
    
    if name in ebones:
        # Zaten var, güncelle
        bone = ebones[name]
    else:
        bone = ebones.new(name)
    
    bone.head = Vector(head)
    bone.tail = Vector(tail)
    bone.roll = roll
    bone.use_deform = use_deform
    bone.use_connect = use_connect
    
    if parent_name:
        if parent_name not in ebones:
            print(f"  ⚠️  Parent '{parent_name}' henüz oluşturulmamış, "
                  f"'{name}' için parent şimdilik None kalıyor (sonra atanacak)")
        else:
            bone.parent = ebones[parent_name]
    else:
        bone.parent = None
    
    return bone


# =============================================================================
# Blueprint'ten armature inşa et
# =============================================================================

def build_armature_from_blueprint(blueprint, armature_name="CreatureArmature"):
    """
    Tüm blueprint'i tek seferde inşa eder.
    
    Strateji:
    1. Önce armature objesi oluştur
    2. Edit mode'a geç
    3. Tüm bone'ları (deform + control + twist) ekle (parent ataması sonra)
    4. İkinci geçişte parent'ları ata (bütün bone'lar oluştuktan sonra)
    5. Object mode'a dön
    """
    armature_obj = create_armature(armature_name)
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    # Tüm bone listesini birleştir
    all_bone_defs = []
    
    for b in blueprint.get("bones", []):
        all_bone_defs.append({**b, "_section": "deform"})
    for b in blueprint.get("control_bones", []):
        all_bone_defs.append({**b, "_section": "control"})
    for b in blueprint.get("twist_bones", []):
        # Twist bone'ların parent_bone alanı parent'a karşılık geliyor
        bone_def = {**b, "_section": "twist"}
        if "parent_bone" in bone_def and "parent" not in bone_def:
            bone_def["parent"] = bone_def["parent_bone"]
        all_bone_defs.append(bone_def)
    
    # Pass 1: Tüm bone'ları oluştur, parent yok
    print(f"[build_skeleton] Pass 1: {len(all_bone_defs)} bone oluşturuluyor...")
    for bdef in all_bone_defs:
        add_edit_bone(
            armature_obj,
            name=bdef["name"],
            head=bdef.get("head_local", [0, 0, 0]),
            tail=bdef.get("tail_local", [0, 0.1, 0]),
            roll=bdef.get("roll_radians", 0.0),
            parent_name=None,  # parent'ı pass 2'de set ederiz
            use_connect=bdef.get("use_connect", False),
            use_deform=bdef.get("use_deform", True),
        )
    
    # Pass 2: Parent'ları ata
    print("[build_skeleton] Pass 2: Parent zincirleri kuruluyor...")
    ebones = armature_obj.data.edit_bones
    for bdef in all_bone_defs:
        parent_name = bdef.get("parent")
        if parent_name is not None:
            if parent_name in ebones:
                ebones[bdef["name"]].parent = ebones[parent_name]
            else:
                print(f"  ⚠️  Parent '{parent_name}' bulunamadı for '{bdef['name']}'")
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return armature_obj


# =============================================================================
# IK constraint setup
# =============================================================================

def setup_ik_constraints(armature_obj, ik_chains):
    """
    Pose mode'da her IK chain için constraint ekle.
    
    Constraint: chain'in END bone'una (en alt) IK constraint koyulur.
    Target = IK target bone.
    Pole target = pole bone.
    Chain length = chain'deki bone sayısı.
    """
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='POSE')
    
    pbones = armature_obj.pose.bones
    
    for chain in ik_chains:
        end_bone_name = chain["end_bone"]
        target_bone_name = chain["ik_target_bone"]
        pole_bone_name = chain.get("pole_target_bone")
        chain_length = chain.get("chain_length", 3)
        pole_angle = chain.get("pole_angle_radians", 0.0)
        
        if end_bone_name not in pbones:
            print(f"  ⚠️  IK chain {chain['chain_id']}: end_bone {end_bone_name} yok, skip")
            continue
        
        end_pbone = pbones[end_bone_name]
        
        # IK constraint ekle
        ik_constraint = end_pbone.constraints.new('IK')
        ik_constraint.name = f"IK_{chain['chain_id']}"
        ik_constraint.target = armature_obj
        ik_constraint.subtarget = target_bone_name
        ik_constraint.chain_count = chain_length
        
        # Pole target (varsa)
        if pole_bone_name and pole_bone_name in armature_obj.data.bones:
            ik_constraint.pole_target = armature_obj
            ik_constraint.pole_subtarget = pole_bone_name
            ik_constraint.pole_angle = pole_angle
        else:
            if pole_bone_name:
                print(f"  ⚠️  Pole bone {pole_bone_name} yok (chain {chain['chain_id']})")
        
        print(f"  ✓ IK constraint: {end_bone_name} → target {target_bone_name}, "
              f"pole {pole_bone_name}, chain_length {chain_length}")
    
    bpy.ops.object.mode_set(mode='OBJECT')


# =============================================================================
# Twist bone setup (Copy Rotation constraints)
# =============================================================================

def setup_twist_bones(armature_obj, twist_bone_defs):
    """
    Twist bone'lara Copy Rotation constraint ekle.
    Twist bone parent'ının dönüşünün belirli bir oranını (twist_share) kopyalar.
    """
    if not twist_bone_defs:
        return
    
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='POSE')
    
    pbones = armature_obj.pose.bones
    
    for twist in twist_bone_defs:
        twist_name = twist["name"]
        parent_name = twist.get("parent_bone", twist.get("parent"))
        share = twist.get("twist_share", 0.5)
        
        if twist_name not in pbones:
            continue
        if parent_name is None or parent_name not in pbones:
            continue
        
        pbone = pbones[twist_name]
        
        # Copy Rotation constraint, sadece Y (bone'un kendi ekseni) ekseninde
        cr = pbone.constraints.new('COPY_ROTATION')
        cr.name = f"Twist_{twist_name}"
        cr.target = armature_obj
        cr.subtarget = parent_name
        cr.use_x = False
        cr.use_y = True   # twist Y eksenidir bone local space'te
        cr.use_z = False
        cr.influence = share
        cr.target_space = 'LOCAL'
        cr.owner_space = 'LOCAL'
        
        print(f"  ✓ Twist: {twist_name} → parent {parent_name}, share {share}")
    
    bpy.ops.object.mode_set(mode='OBJECT')


# =============================================================================
# Bone collections (Blender 4.x'te bone groups yerine)
# =============================================================================

def setup_bone_collections(armature_obj, collections_dict):
    """
    Blender 4.x bone collections. Display gruplaması için.
    """
    armature_data = armature_obj.data
    
    for coll_name, bone_names in collections_dict.items():
        # Collection oluştur
        if coll_name not in armature_data.collections:
            coll = armature_data.collections.new(name=coll_name)
        else:
            coll = armature_data.collections[coll_name]
        
        # Bone'ları assign
        for bone_name in bone_names:
            if bone_name in armature_data.bones:
                coll.assign(armature_data.bones[bone_name])


# =============================================================================
# Validation
# =============================================================================

def validate_armature(armature_obj, blueprint):
    """
    Armature inşa edildikten sonra şu kontrolleri yapar.
    """
    results = {
        "checks": [],
        "errors": [],
        "warnings": [],
    }
    
    armature_data = armature_obj.data
    
    # V1: Tüm beklenen bone'lar var mı
    expected_bones = set()
    for b in blueprint.get("bones", []):
        expected_bones.add(b["name"])
    for b in blueprint.get("control_bones", []):
        expected_bones.add(b["name"])
    for b in blueprint.get("twist_bones", []):
        expected_bones.add(b["name"])
    
    actual_bones = set(b.name for b in armature_data.bones)
    missing = expected_bones - actual_bones
    extra = actual_bones - expected_bones
    
    if missing:
        results["errors"].append(f"Eksik bone'lar: {missing}")
    if extra:
        results["warnings"].append(f"Fazladan bone'lar: {extra}")
    
    results["checks"].append({
        "name": "bone_count",
        "expected": len(expected_bones),
        "actual": len(actual_bones),
        "passed": len(missing) == 0,
    })
    
    # V2: Tüm bone'ların geçerli uzunluğu var mı
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    for ebone in armature_data.edit_bones:
        length = (ebone.tail - ebone.head).length
        if length < 0.001:
            results["errors"].append(f"Bone {ebone.name}: sıfır uzunluk")
    
    # V3: Parent zinciri integrity
    for ebone in armature_data.edit_bones:
        if ebone.parent and ebone.parent.name not in armature_data.edit_bones:
            results["errors"].append(f"Bone {ebone.name}: parent referansı kopuk")
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # V4: IK constraint'ler eklenmiş mi
    bpy.ops.object.mode_set(mode='POSE')
    
    expected_ik_count = len(blueprint.get("ik_chains", []))
    actual_ik_count = 0
    for pbone in armature_obj.pose.bones:
        for c in pbone.constraints:
            if c.type == 'IK':
                actual_ik_count += 1
    
    results["checks"].append({
        "name": "ik_constraints",
        "expected": expected_ik_count,
        "actual": actual_ik_count,
        "passed": expected_ik_count == actual_ik_count,
    })
    
    if actual_ik_count != expected_ik_count:
        results["errors"].append(
            f"IK constraint sayısı uyuşmuyor: beklenen {expected_ik_count}, "
            f"gerçek {actual_ik_count}"
        )
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # V5: Simetri spot-check (L/R bone'lar)
    bpy.ops.object.mode_set(mode='EDIT')
    
    left_bones = [b for b in armature_data.edit_bones if b.name.endswith("_L")]
    for left in left_bones:
        right_name = left.name[:-2] + "_R"
        if right_name in armature_data.edit_bones:
            right = armature_data.edit_bones[right_name]
            # X koordinatları mirror olmalı
            if abs(left.head.x + right.head.x) > 0.01:
                results["warnings"].append(
                    f"Simetri sapması: {left.name} head.x={left.head.x:.3f} "
                    f"vs {right_name} head.x={right.head.x:.3f}"
                )
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Overall pass/fail
    results["overall_passed"] = len(results["errors"]) == 0
    
    return results


# =============================================================================
# Ana akış
# =============================================================================

def main():
    args = parse_args()
    
    blueprint_path = Path(args.blueprint).resolve()
    if not blueprint_path.exists():
        print(f"❌ Blueprint yok: {blueprint_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"[build_skeleton] Blueprint yükleniyor: {blueprint_path}")
    blueprint = json.loads(blueprint_path.read_text(encoding='utf-8'))
    
    creature_id = blueprint.get("creature_id", "unknown")
    print(f"[build_skeleton] Yaratık: {creature_id}")
    
    # Sahneyi hazırla
    clean_scene()
    setup_units()
    
    # Armature oluştur
    print("[build_skeleton] Armature inşa ediliyor...")
    armature_obj = build_armature_from_blueprint(
        blueprint,
        armature_name=args.armature_name,
    )
    
    # IK constraints
    ik_chains = blueprint.get("ik_chains", [])
    if ik_chains:
        print(f"[build_skeleton] {len(ik_chains)} IK chain kuruluyor...")
        setup_ik_constraints(armature_obj, ik_chains)
    
    # Twist bones
    twist_bones = blueprint.get("twist_bones", [])
    if twist_bones:
        print(f"[build_skeleton] {len(twist_bones)} twist bone setup...")
        setup_twist_bones(armature_obj, twist_bones)
    
    # Bone collections
    collections = blueprint.get("bone_collections", {})
    if collections:
        print(f"[build_skeleton] Bone collections: {list(collections.keys())}")
        setup_bone_collections(armature_obj, collections)
    
    # Validation
    print("[build_skeleton] Validation çalıştırılıyor...")
    validation = validate_armature(armature_obj, blueprint)
    
    # Validation raporunu yaz
    output_blend_path = Path(args.output_blend).resolve()
    output_blend_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path = output_blend_path.with_suffix('.validation.json')
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False))
    
    print(f"[build_skeleton] Validation:")
    for chk in validation["checks"]:
        status = "✓" if chk["passed"] else "✗"
        print(f"  {status} {chk['name']}: expected {chk['expected']}, actual {chk['actual']}")
    
    for err in validation["errors"]:
        print(f"  ❌ {err}")
    for warn in validation["warnings"]:
        print(f"  ⚠️  {warn}")
    
    if not validation["overall_passed"]:
        print("[build_skeleton] ❌ Validation BAŞARISIZ — yine de Blender dosyası kaydedilecek")
    
    if args.validate_only:
        print("[build_skeleton] --validate-only mode, .blend kaydedilmiyor")
        return
    
    # Kaydet
    print(f"[build_skeleton] Blender dosyası kaydediliyor: {output_blend_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend_path))
    
    print(f"[build_skeleton] ✅ Tamamlandı")
    print(f"   • Blend: {output_blend_path}")
    print(f"   • Validation: {validation_path}")
    print(f"   • Bone sayısı: {len(armature_obj.data.bones)}")
    print(f"   • IK constraint sayısı: {sum(1 for pb in armature_obj.pose.bones for c in pb.constraints if c.type == 'IK')}")


if __name__ == "__main__":
    main()
