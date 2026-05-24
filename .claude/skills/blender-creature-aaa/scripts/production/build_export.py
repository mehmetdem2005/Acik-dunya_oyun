#!/usr/bin/env python3
"""
build_export.py — P13 Exporter'ın executable component

Animated .blend dosyasını Godot 4 mobile-friendly glTF (.glb) formatına
export eder, LOD chain üretir, opsiyonel Godot smoke test yapar.

Kullanım:
    blender --background <animated_v1.blend> --python build_export.py -- \
        --budget <BudgetSpec.json> \
        --anim-manifest <AnimationManifest.json> \
        --output-dir <final/> \
        --creature-id <name> \
        [--run-godot-test]
"""

import bpy
import json
import re
import shutil
import subprocess
import sys
import argparse
from pathlib import Path


def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser()
    p.add_argument("--budget", required=True)
    p.add_argument("--anim-manifest", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--creature-id", required=True)
    p.add_argument("--run-godot-test", action="store_true")
    p.add_argument("--godot-binary", default="godot")
    return p.parse_args(argv)


# =============================================================================
# Bone naming sanitize
# =============================================================================

def sanitize_name(name):
    """Godot 4-friendly: ASCII, underscore, no dots."""
    tr_map = str.maketrans("şŞıİğĞüÜöÖçÇ", "sSiIgGuUoOcC")
    name = name.translate(tr_map)
    name = re.sub(r'[^\x00-\x7F]+', '_', name)
    name = name.replace('.', '_').replace(' ', '_')
    name = re.sub(r'_+', '_', name)
    return name


def sanitize_armature_bones(armature_obj):
    """Tüm bone'ları rename, vertex group'ları da güncelle."""
    rename_map = {}
    
    # Edit mode'da bone rename
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    for ebone in armature_obj.data.edit_bones:
        new_name = sanitize_name(ebone.name)
        if new_name != ebone.name:
            rename_map[ebone.name] = new_name
            ebone.name = new_name
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Mesh vertex group'ları güncelle
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for vg in obj.vertex_groups:
            if vg.name in rename_map:
                vg.name = rename_map[vg.name]
    
    return rename_map


# =============================================================================
# Apply transforms
# =============================================================================

def apply_all_transforms_recursive(obj):
    """Object'in transform'unu apply et (kullandığı modifier'lar dahil)."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    
    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except Exception as e:
        print(f"  ⚠️ Transform apply fail for {obj.name}: {e}")


# =============================================================================
# LOD üretimi
# =============================================================================

def create_lod_copy(source_mesh_obj, ratio, lod_name):
    """Source mesh'ten Decimate'lenmiş LOD kopyası."""
    new_data = source_mesh_obj.data.copy()
    new_data.name = lod_name + "_data"
    new_obj = bpy.data.objects.new(lod_name, new_data)
    bpy.context.collection.objects.link(new_obj)
    
    # Transform'u kopyala (skeleton'a alignment için)
    new_obj.matrix_world = source_mesh_obj.matrix_world.copy()
    
    # Decimate
    dec = new_obj.modifiers.new("LOD_Decimate", 'DECIMATE')
    dec.ratio = ratio
    dec.decimate_type = 'COLLAPSE'
    dec.use_collapse_triangulate = False
    
    bpy.context.view_layer.objects.active = new_obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
    
    return new_obj


def count_tris(mesh_obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    n = len(bm.faces)
    bm.free()
    return n


# =============================================================================
# glTF Export
# =============================================================================

def export_glb_selected(filepath, selected_objects):
    """
    Sadece selected_objects'ları glb'ye export et.
    Diğer obj'leri geçici olarak hide et.
    """
    # Önce her şeyi deselect, hide
    bpy.ops.object.select_all(action='DESELECT')
    hidden_objs = []
    
    for obj in bpy.data.objects:
        if obj not in selected_objects:
            if not obj.hide_viewport:
                obj.hide_viewport = True
                hidden_objs.append(obj)
    
    # Selected'ları seç
    for obj in selected_objects:
        obj.select_set(True)
    if selected_objects:
        bpy.context.view_layer.objects.active = selected_objects[0]
    
    # Export
    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_animations=True,
        export_animation_mode='NLA_TRACKS',
        export_force_sampling=True,
        export_nla_strips=True,
        export_optimize_animation_size=True,
        export_skins=True,
        export_morph=True,
        export_morph_normal=False,  # mobil için skip
        export_morph_tangent=False,
        export_yup=True,
        export_image_format='AUTO',
    )
    
    # Geri yükle
    for obj in hidden_objs:
        obj.hide_viewport = False


# =============================================================================
# Godot smoke test
# =============================================================================

def run_godot_smoke_test(glb_path, godot_binary="godot", timeout=60):
    """Godot 4 headless ile glb import test."""
    # Geçici test project + scene
    import tempfile
    
    project_dir = Path(tempfile.mkdtemp(prefix="godot_smoke_"))
    
    # project.godot (minimum)
    (project_dir / "project.godot").write_text(
        '[application]\nconfig/name="SmokeTest"\nconfig/features=PackedStringArray("4.0")\n'
    )
    
    # smoke_test.gd
    test_gd = f"""extends SceneTree

func _init():
    var gltf := GLTFDocument.new()
    var state := GLTFState.new()
    var err := gltf.append_from_file("{glb_path}", state)
    if err != OK:
        print("ERR_IMPORT_FAILED:", err)
        quit(1)
        return
    
    var scene := gltf.generate_scene(state)
    if scene == null:
        print("ERR_SCENE_NULL")
        quit(1)
        return
    
    var bones := _count_bones(scene)
    var anims := _count_animations(scene)
    var shapes := _count_shape_keys(scene)
    
    print("BONES:", bones)
    print("ANIMATIONS:", anims)
    print("SHAPES:", shapes)
    print("OK")
    quit(0)

func _count_bones(node) -> int:
    var n := 0
    if node is Skeleton3D:
        n += node.get_bone_count()
    for child in node.get_children():
        n += _count_bones(child)
    return n

func _count_animations(node) -> int:
    var n := 0
    if node is AnimationPlayer:
        n += node.get_animation_list().size()
    for child in node.get_children():
        n += _count_animations(child)
    return n

func _count_shape_keys(node) -> int:
    var n := 0
    if node is MeshInstance3D:
        if node.mesh != null:
            n += node.mesh.get_blend_shape_count()
    for child in node.get_children():
        n += _count_shape_keys(child)
    return n
"""
    
    test_script_path = project_dir / "smoke_test.gd"
    test_script_path.write_text(test_gd)
    
    # Çalıştır
    try:
        result = subprocess.run(
            [godot_binary, "--headless", "--path", str(project_dir),
             "--script", "smoke_test.gd"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        shutil.rmtree(project_dir, ignore_errors=True)
        return {"imported_successfully": False, "errors": [str(e)],
                "actual_bones": None, "actual_animations": None, "actual_shape_keys": None}
    
    # Output parse
    out = result.stdout
    
    if "ERR_" in out or result.returncode != 0:
        shutil.rmtree(project_dir, ignore_errors=True)
        return {"imported_successfully": False, "errors": [out], "stdout": out,
                "actual_bones": None, "actual_animations": None, "actual_shape_keys": None}
    
    bones_m = re.search(r"BONES:(\d+)", out)
    anims_m = re.search(r"ANIMATIONS:(\d+)", out)
    shapes_m = re.search(r"SHAPES:(\d+)", out)
    
    shutil.rmtree(project_dir, ignore_errors=True)
    
    return {
        "imported_successfully": True,
        "actual_bones": int(bones_m.group(1)) if bones_m else 0,
        "actual_animations": int(anims_m.group(1)) if anims_m else 0,
        "actual_shape_keys": int(shapes_m.group(1)) if shapes_m else 0,
        "errors": [],
    }


# =============================================================================
# Find objects
# =============================================================================

def find_mesh_and_armature():
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
# Ana
# =============================================================================

def main():
    args = parse_args()
    
    budget = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    anim_manifest = json.loads(Path(args.anim_manifest).read_text(encoding='utf-8'))
    
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    creature_id = args.creature_id
    
    # 1. Mesh + armature bul
    mesh_obj, armature_obj = find_mesh_and_armature()
    if mesh_obj is None or armature_obj is None:
        print(f"❌ Mesh ({mesh_obj}) veya armature ({armature_obj}) yok", file=sys.stderr)
        sys.exit(1)
    
    print(f"[exporter] Mesh: {mesh_obj.name}")
    print(f"[exporter] Armature: {armature_obj.name}")
    
    # 2. Bone naming sanitize
    print("[exporter] Bone naming sanitize...")
    rename_map = sanitize_armature_bones(armature_obj)
    if rename_map:
        print(f"  ✓ {len(rename_map)} bone renamed")
    else:
        print("  ✓ Tüm bone'lar zaten Godot-friendly")
    
    # 3. Apply transforms (mesh + armature)
    print("[exporter] Transforms apply...")
    apply_all_transforms_recursive(armature_obj)
    # Mesh için armature modifier varsa apply ETME (skinning korunmalı)
    # Sadece location/rotation/scale apply, modifier'ları korumak için manuel
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except Exception as e:
        print(f"  ⚠️ Mesh transform apply: {e}")
    
    # 4. LOD üret
    lod_config = budget.get("lod_config", {})
    lod_levels = lod_config.get("levels", 3)
    lod_ratios = [
        ("LOD0", 1.0),
        ("LOD1", lod_config.get("lod1_ratio", 0.5)),
        ("LOD2", lod_config.get("lod2_ratio", 0.25)),
    ]
    if lod_levels >= 4 and lod_config.get("lod3_ratio") is not None:
        lod_ratios.append(("LOD3", lod_config["lod3_ratio"]))
    
    # LOD0 = orijinal mesh
    # LOD1+ = kopya + decimate
    
    exports_info = []
    
    # LOD0 — orijinal mesh ile export
    lod0_path = output_dir / f"{creature_id}.glb"
    print(f"[exporter] LOD0 export: {lod0_path}")
    export_glb_selected(lod0_path, [armature_obj, mesh_obj])
    
    tris_lod0 = count_tris(mesh_obj)
    
    exports_info.append({
        "level": "LOD0",
        "filepath": str(lod0_path),
        "tris_count": tris_lod0,
        "file_size_bytes": lod0_path.stat().st_size if lod0_path.exists() else 0,
        "decimate_ratio": 1.0,
    })
    
    # LOD1, LOD2, LOD3
    for level_name, ratio in lod_ratios[1:]:
        if ratio is None:
            continue
        
        lod_path = output_dir / f"{creature_id}_{level_name}.glb"
        print(f"[exporter] {level_name} (ratio {ratio}) export: {lod_path}")
        
        # Mesh kopyası + decimate
        lod_mesh = create_lod_copy(mesh_obj, ratio, f"{mesh_obj.name}_{level_name}")
        
        # LOD mesh'i export (armature ile birlikte)
        export_glb_selected(lod_path, [armature_obj, lod_mesh])
        
        tris_lod = count_tris(lod_mesh)
        
        exports_info.append({
            "level": level_name,
            "filepath": str(lod_path),
            "tris_count": tris_lod,
            "file_size_bytes": lod_path.stat().st_size if lod_path.exists() else 0,
            "decimate_ratio": ratio,
        })
        
        # LOD mesh'i sil (memory cleanup)
        bpy.data.objects.remove(lod_mesh, do_unlink=True)
    
    # 5. Godot smoke test (opsiyonel)
    smoke_result = {"imported_successfully": False, "skipped": True}
    
    if args.run_godot_test:
        print("[exporter] Godot smoke test...")
        expected_bones = sum(1 for b in armature_obj.data.bones if b.use_deform)
        # Godot bone count tüm bone'ları döndürür (deform + non-deform)
        expected_bones_total = len(armature_obj.data.bones)
        expected_anims = len(anim_manifest.get("clips", []))
        expected_shapes = len([k for k in (mesh_obj.data.shape_keys.key_blocks
                                            if mesh_obj.data.shape_keys else []) if k.name != "Basis"])
        
        smoke_result = run_godot_smoke_test(lod0_path, args.godot_binary)
        smoke_result["expected_bones"] = expected_bones_total
        smoke_result["expected_animations"] = expected_anims
        smoke_result["expected_shape_keys"] = expected_shapes
        
        if smoke_result["imported_successfully"]:
            print(f"  ✓ Imported: {smoke_result['actual_bones']} bone, "
                  f"{smoke_result['actual_animations']} anim, "
                  f"{smoke_result['actual_shape_keys']} blend shape")
        else:
            print(f"  ⚠️ Smoke test fail: {smoke_result.get('errors', [])}")
    
    # 6. ExportManifest yaz
    export_manifest = {
        "manifest_version": "1.0",
        "creature_id": creature_id,
        "exports": exports_info,
        "bone_naming_check": {
            "godot_compatible": True,
            "renamed_count": len(rename_map),
            "rename_map": rename_map,
        },
        "godot_smoke_test": smoke_result,
        "generated_by": "P13_exporter",
    }
    
    manifest_path = output_dir / "ExportManifest.json"
    manifest_path.write_text(json.dumps(export_manifest, indent=2, ensure_ascii=False))
    
    print(f"\n[exporter] ✅ Export tamamlandı")
    print(f"   • Klasör: {output_dir}")
    for exp in exports_info:
        print(f"   • {exp['level']}: {exp['tris_count']} tris, "
              f"{exp['file_size_bytes']/1024:.1f} KB")


if __name__ == "__main__":
    main()
