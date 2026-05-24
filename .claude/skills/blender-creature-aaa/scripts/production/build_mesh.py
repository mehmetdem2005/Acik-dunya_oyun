#!/usr/bin/env python3
"""
build_mesh.py — P04 Mesh Sculptor'ın executable component

Blender içinde çalışır:
    blender --background <skeleton_v1.blend> --python build_mesh.py -- \
        --blueprint <SkeletonBlueprint.json> \
        --budget <BudgetSpec.json> \
        --creature-spec <CreatureSpec.json> \
        --anatomy-class <path/to/anatomy_class.md> \
        --output-blend <mesh_v1.blend>

Skeleton'dan curve türetir, Geometry Nodes ile et giydirir, boolean union +
voxel remesh ile dikişsiz mesh üretir, BudgetSpec.tris hedefine indirir.

Çıktı:
    <output_blend>: armature + base_mesh
    <output_blend>.mesh_manifest.json: mesh metadata
"""

import bpy
import bmesh
import json
import math
import re
import sys
import argparse
from pathlib import Path
from mathutils import Vector


# =============================================================================
# Argument parsing
# =============================================================================

def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser()
    p.add_argument("--blueprint", required=True)
    p.add_argument("--budget", required=True)
    p.add_argument("--creature-spec", required=True)
    p.add_argument("--anatomy-class", required=True, help=".md dosyası, YAML parse")
    p.add_argument("--output-blend", required=True)
    p.add_argument("--voxel-size", type=float, default=None,
                   help="Override voxel remesh size (default: body_length/100)")
    p.add_argument("--profile-resolution", type=int, default=12)
    p.add_argument("--segment-resolution", type=int, default=24)
    p.add_argument("--subdivision-level", type=int, default=1)
    return p.parse_args(argv)


# =============================================================================
# Anatomy class parse (markdown'dan oran tablosu çek)
# =============================================================================

def parse_anatomy_class(md_path):
    """
    Anatomy class .md dosyasından oran tablosunu parse et.
    YAML-style key:value blokları arar.
    """
    content = Path(md_path).read_text(encoding='utf-8')
    
    # Yaml-style ratio extraction (basit regex, full parser değil)
    # Örnek satır: "  chest_width: 0.20-0.25"
    pattern = re.compile(r'^\s*([a-z_]+):\s*([\d.\-]+)', re.MULTILINE)
    
    ratios = {}
    for match in pattern.finditer(content):
        key, value = match.group(1), match.group(2)
        if '-' in value:
            # range, ortalama al
            parts = value.split('-')
            try:
                avg = (float(parts[0]) + float(parts[1])) / 2
                ratios[key] = avg
            except ValueError:
                pass
        else:
            try:
                ratios[key] = float(value)
            except ValueError:
                pass
    
    return ratios


# =============================================================================
# Skeleton blueprint'ten curve türet
# =============================================================================

def skeleton_to_curves(blueprint):
    """
    Skeleton bones'tan body part curves türet.
    Returns: {part_name: list_of_point_vectors}
    """
    curves = {}
    bones_by_name = {}
    
    # Bones'u topla (deform + control)
    for section in ("bones", "control_bones", "twist_bones"):
        for b in blueprint.get(section, []):
            bones_by_name[b["name"]] = b
    
    # 1. Spine + neck + head zinciri (ana gövde curve)
    spine_points = []
    
    # Spine bones (sorted by index)
    spine_bones = sorted(
        [b for b in blueprint["bones"] if b["name"].startswith("spine_")],
        key=lambda b: int(re.search(r'\d+', b["name"]).group()) if re.search(r'\d+', b["name"]) else 0
    )
    
    if spine_bones:
        spine_points.append(Vector(spine_bones[0]["head_local"]))
        for sb in spine_bones:
            spine_points.append(Vector(sb["tail_local"]))
    
    # Neck
    neck_bones = sorted(
        [b for b in blueprint["bones"] if b["name"].startswith("neck_")],
        key=lambda b: int(re.search(r'\d+', b["name"]).group()) if re.search(r'\d+', b["name"]) else 0
    )
    for nb in neck_bones:
        spine_points.append(Vector(nb["tail_local"]))
    
    # Head
    head_bone = bones_by_name.get("head")
    if head_bone:
        spine_points.append(Vector(head_bone["tail_local"]))
    
    if len(spine_points) >= 2:
        curves["spine"] = spine_points
    
    # 2. Tail
    tail_bones = sorted(
        [b for b in blueprint["bones"] if b["name"].startswith("tail_")],
        key=lambda b: int(re.search(r'\d+', b["name"]).group()) if re.search(r'\d+', b["name"]) else 0
    )
    if tail_bones:
        tail_points = [Vector(tail_bones[0]["head_local"])]
        for tb in tail_bones:
            tail_points.append(Vector(tb["tail_local"]))
        curves["tail"] = tail_points
    
    # 3. Bacaklar (4 chain)
    leg_chains = {
        "front": ["shoulder", "upper_arm", "forearm", "wrist"],
        "rear": ["hip", "thigh", "shin", "ankle", "foot"],  # digitigrade
    }
    
    for chain_kind, bone_seq in leg_chains.items():
        for side in ["L", "R"]:
            points = []
            for bone_base in bone_seq:
                bone = bones_by_name.get(f"{bone_base}_{side}")
                if bone:
                    if not points:
                        points.append(Vector(bone["head_local"]))
                    points.append(Vector(bone["tail_local"]))
            if len(points) >= 2:
                curves[f"leg_{chain_kind}_{side}"] = points
    
    return curves


# =============================================================================
# Radius profili hesapla
# =============================================================================

def compute_radius_profiles(creature_spec, anatomy_ratios, body_length):
    """
    Her body part için (t, radius) tuple listesi.
    """
    profiles = {}
    
    # Ana radius
    chest_w = anatomy_ratios.get("chest_width", 0.22) * body_length
    chest_d = anatomy_ratios.get("chest_depth", 0.28) * body_length
    body_max_r = (chest_w + chest_d) / 4
    
    # Stylization
    mods = creature_spec.get("user_modifications", {})
    head_mult = mods.get("head_size_multiplier", 1.0)
    muscle_def = mods.get("muscle_definition", "normal")
    muscle_boost = {
        "subtle": 0.85, "normal": 1.0,
        "exaggerated": 1.2, "extreme": 1.4
    }.get(muscle_def, 1.0)
    
    # Spine (kalça → kuyruk başı → omuz → boyun → baş)
    profiles["spine"] = [
        (0.0, body_max_r * 0.85),
        (0.15, body_max_r * 1.0 * muscle_boost),
        (0.45, body_max_r * 0.95 * muscle_boost),
        (0.55, body_max_r * 1.05 * muscle_boost),
        (0.65, body_max_r * 0.85),
        (0.75, body_max_r * 0.55),  # boyun
        (0.85, body_max_r * 0.5),
        (0.92, body_max_r * 0.75 * head_mult),  # kafa
        (1.0, body_max_r * 0.6 * head_mult),
    ]
    
    # Tail (kalın → sıfır)
    profiles["tail"] = [
        (0.0, body_max_r * 0.4),
        (0.3, body_max_r * 0.3),
        (0.7, body_max_r * 0.12),
        (1.0, body_max_r * 0.03),
    ]
    
    # Bacaklar
    leg_upper = body_max_r * 0.4 * muscle_boost
    leg_lower = body_max_r * 0.22
    paw_r = body_max_r * 0.27
    
    for side in ["L", "R"]:
        profiles[f"leg_front_{side}"] = [
            (0.0, body_max_r * 0.5 * muscle_boost),
            (0.15, leg_upper),
            (0.45, leg_upper * 0.8),
            (0.55, leg_lower * 1.05),
            (0.85, leg_lower),
            (0.92, paw_r),
            (1.0, paw_r * 0.7),
        ]
        profiles[f"leg_rear_{side}"] = [
            (0.0, body_max_r * 0.55 * muscle_boost),
            (0.20, leg_upper * 1.1),
            (0.45, leg_upper * 0.7),
            (0.55, leg_lower * 1.0),
            (0.75, leg_lower * 0.9),
            (0.88, leg_lower * 0.95),
            (0.95, paw_r),
            (1.0, paw_r * 0.65),
        ]
    
    return profiles


# =============================================================================
# Bezier curve obj oluştur
# =============================================================================

def create_curve_object(name, points):
    """Bezier curve obj, points = list of Vector."""
    curve_data = bpy.data.curves.new(name=f"{name}_curve", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 12
    
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    
    for i, p in enumerate(points):
        bp = spline.bezier_points[i]
        bp.co = p
        bp.handle_left_type = 'AUTO'
        bp.handle_right_type = 'AUTO'
    
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    return obj


# =============================================================================
# Geometry Nodes graph kur
# =============================================================================

def build_flesh_modifier(curve_obj, radius_profile, profile_resolution=12,
                          segment_resolution=24):
    """
    Curve obj'ye flesh modifier ekle (Curve to Mesh + radius profile).
    """
    mod = curve_obj.modifiers.new(name="FleshGen", type='NODES')
    
    ng = bpy.data.node_groups.new(f"FleshNG_{curve_obj.name}", 'GeometryNodeTree')
    mod.node_group = ng
    
    # Interface
    ng.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    
    nodes = ng.nodes
    links = ng.links
    
    # Group I/O
    n_in = nodes.new('NodeGroupInput')
    n_out = nodes.new('NodeGroupOutput')
    n_in.location = (-900, 0)
    n_out.location = (900, 0)
    
    # Set Spline Resolution
    n_res = nodes.new('GeometryNodeSetSplineResolution')
    n_res.location = (-700, 0)
    n_res.inputs['Resolution'].default_value = segment_resolution
    
    # Spline Parameter
    n_sp = nodes.new('GeometryNodeSplineParameter')
    n_sp.location = (-700, -250)
    
    # Float Curve (radius profile)
    n_fc = nodes.new('ShaderNodeFloatCurve')
    n_fc.location = (-500, -250)
    
    # Profile noktalarını uygula
    fc = n_fc.mapping.curves[0]
    
    # İlk 2 noktayı sil (default)
    while len(fc.points) > 2:
        try:
            fc.points.remove(fc.points[-1])
        except Exception:
            break
    
    if len(radius_profile) >= 2:
        # İlk iki noktayı update
        fc.points[0].location = radius_profile[0]
        fc.points[1].location = radius_profile[1]
        # Geri kalanı ekle
        for t, r in radius_profile[2:]:
            fc.points.new(t, r)
    
    n_fc.mapping.use_clip = False
    n_fc.mapping.update()
    
    # Set Curve Radius
    n_sr = nodes.new('GeometryNodeSetCurveRadius')
    n_sr.location = (-200, 0)
    
    # Curve Primitive Circle (profile)
    n_circle = nodes.new('GeometryNodeCurvePrimitiveCircle')
    n_circle.location = (0, -300)
    n_circle.inputs['Resolution'].default_value = profile_resolution
    n_circle.inputs['Radius'].default_value = 1.0
    
    # Curve to Mesh
    n_ctm = nodes.new('GeometryNodeCurveToMesh')
    n_ctm.location = (300, 0)
    # Fill Caps: tupleri kapali kati yap, yoksa acik tup -> voxel remesh delikli kabuk uretir
    if 'Fill Caps' in n_ctm.inputs:
        n_ctm.inputs['Fill Caps'].default_value = True
    
    # Set Shade Smooth
    n_shade = nodes.new('GeometryNodeSetShadeSmooth')
    n_shade.location = (600, 0)
    
    # Linkler
    links.new(n_in.outputs[0], n_res.inputs['Geometry'])
    links.new(n_res.outputs['Geometry'], n_sr.inputs['Curve'])
    links.new(n_sp.outputs['Factor'], n_fc.inputs['Value'])
    links.new(n_fc.outputs['Value'], n_sr.inputs['Radius'])
    links.new(n_sr.outputs['Curve'], n_ctm.inputs['Curve'])
    links.new(n_circle.outputs['Curve'], n_ctm.inputs['Profile Curve'])
    links.new(n_ctm.outputs['Mesh'], n_shade.inputs['Geometry'])
    links.new(n_shade.outputs['Geometry'], n_out.inputs[0])
    
    return mod


# =============================================================================
# Convert + Boolean Union
# =============================================================================

def convert_to_mesh_and_union(part_objects, target_name="creature_mesh"):
    """
    Tüm curve obj'leri mesh'e convert et, sonra boolean union.
    """
    # Apply modifiers + convert
    for obj in list(part_objects):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.ops.object.convert(target='MESH')
    
    if not part_objects:
        return None
    
    # Base = en büyük (spine)
    base = next((o for o in part_objects if "spine" in o.name), part_objects[0])
    
    # Diğerlerini base'e union et
    for obj in list(part_objects):
        if obj == base:
            continue
        
        bool_mod = base.modifiers.new(name=f"Union_{obj.name}", type='BOOLEAN')
        bool_mod.operation = 'UNION'
        bool_mod.object = obj
        bool_mod.solver = 'EXACT'
        
        bpy.context.view_layer.objects.active = base
        try:
            bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        except Exception as e:
            print(f"  ⚠️ Union {obj.name} fail: {e}, FAST solver deniyorum")
            base.modifiers.remove(bool_mod)
            bool_mod = base.modifiers.new(name=f"Union_{obj.name}", type='BOOLEAN')
            bool_mod.operation = 'UNION'
            bool_mod.object = obj
            bool_mod.solver = 'FAST'
            try:
                bpy.ops.object.modifier_apply(modifier=bool_mod.name)
            except Exception as e2:
                print(f"  ❌ Union {obj.name} kalıcı fail: {e2}")
                base.modifiers.remove(bool_mod)
        
        bpy.data.objects.remove(obj, do_unlink=True)
    
    base.name = target_name
    base.data.name = target_name + "_data"
    
    return base


# =============================================================================
# Voxel Remesh + Subdivision + Decimate
# =============================================================================

def voxel_remesh(mesh_obj, voxel_size):
    bpy.context.view_layer.objects.active = mesh_obj
    mesh_obj.data.remesh_mode = 'VOXEL'
    mesh_obj.data.remesh_voxel_size = voxel_size
    mesh_obj.data.use_remesh_preserve_volume = True
    mesh_obj.data.use_remesh_fix_poles = True
    
    bpy.ops.object.voxel_remesh()


def subdivide(mesh_obj, level):
    if level <= 0:
        return
    sub = mesh_obj.modifiers.new(name="Subsurf", type='SUBSURF')
    sub.levels = level
    sub.render_levels = level
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.modifier_apply(modifier=sub.name)


def get_tris_count(mesh_obj):
    """Triangulated tris count."""
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    n = len(bm.faces)
    bm.free()
    return n


def decimate_to_target(mesh_obj, target_tris):
    current = get_tris_count(mesh_obj)
    if current <= target_tris:
        return current
    
    ratio = target_tris / current
    
    dec = mesh_obj.modifiers.new(name="Decimate", type='DECIMATE')
    dec.ratio = ratio
    dec.decimate_type = 'COLLAPSE'
    dec.use_collapse_triangulate = False
    
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
    
    return get_tris_count(mesh_obj)


# =============================================================================
# Validation
# =============================================================================

def validate_mesh(mesh_obj, budget_spec):
    """Mesh production-ready mi?"""
    results = {"errors": [], "warnings": []}
    
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
    # Manifold
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    if non_manifold:
        results["errors"].append(f"Non-manifold edges: {non_manifold}")
    
    # Boundary (watertight)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    if boundary:
        results["warnings"].append(f"Boundary edges: {boundary} (watertight değil olabilir)")
    
    # NaN check
    nan_count = sum(1 for v in bm.verts
                    if any(c != c or math.isinf(c) for c in v.co))
    if nan_count:
        results["errors"].append(f"NaN/Inf vertex: {nan_count}")
    
    # Tris budget
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    target = budget_spec["polygon_budget"]["lod0_tris_target"]
    hard_max = budget_spec["polygon_budget"]["lod0_tris_hard_max"]
    
    if tris > hard_max:
        results["errors"].append(f"Tris hard_max aşıldı: {tris} > {hard_max}")
    elif tris > target * 1.15:
        results["warnings"].append(f"Tris hedeften fazla: {tris} (hedef {target})")
    elif tris < target * 0.85:
        results["warnings"].append(f"Tris hedeften az: {tris} (hedef {target})")
    
    # Bbox
    bb_min = Vector((min(v.co.x for v in bm.verts),
                     min(v.co.y for v in bm.verts),
                     min(v.co.z for v in bm.verts)))
    bb_max = Vector((max(v.co.x for v in bm.verts),
                     max(v.co.y for v in bm.verts),
                     max(v.co.z for v in bm.verts)))
    
    bm.free()
    
    return {
        "results": results,
        "tris": tris,
        "verts": len(mesh_obj.data.vertices),
        "faces": len(mesh_obj.data.polygons),
        "bbox_min": list(bb_min),
        "bbox_max": list(bb_max),
        "is_manifold": non_manifold == 0,
        "is_watertight": boundary == 0,
    }


# =============================================================================
# Ana akış
# =============================================================================

def main():
    args = parse_args()
    
    # Inputs yükle
    blueprint = json.loads(Path(args.blueprint).read_text(encoding='utf-8'))
    budget_spec = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    creature_spec = json.loads(Path(args.creature_spec).read_text(encoding='utf-8'))
    anatomy_ratios = parse_anatomy_class(args.anatomy_class)
    
    body_length = blueprint.get("body_length_meters", 1.2)
    
    print(f"[mesh_sculptor] Yaratık: {creature_spec.get('common_name_tr', '?')}")
    print(f"[mesh_sculptor] Body length: {body_length}m")
    print(f"[mesh_sculptor] Tris hedef: {budget_spec['polygon_budget']['lod0_tris_target']}")
    
    # 1. Skeleton'dan curve türet
    print("[mesh_sculptor] Curve'ler türetiliyor...")
    curves_points = skeleton_to_curves(blueprint)
    print(f"  ✓ {len(curves_points)} curve: {list(curves_points.keys())}")
    
    # 2. Radius profile
    print("[mesh_sculptor] Radius profilleri hesaplanıyor...")
    profiles = compute_radius_profiles(creature_spec, anatomy_ratios, body_length)
    
    # 3. Curve obj'leri ve modifier'ları
    print("[mesh_sculptor] Curve objeleri + GN modifier kuruluyor...")
    part_objects = []
    for part_name, points in curves_points.items():
        profile = profiles.get(part_name)
        if not profile:
            print(f"  ⚠️ {part_name} için profile yok, atlanıyor")
            continue
        
        curve_obj = create_curve_object(part_name, points)
        build_flesh_modifier(
            curve_obj, profile,
            profile_resolution=args.profile_resolution,
            segment_resolution=args.segment_resolution,
        )
        part_objects.append(curve_obj)
        print(f"  ✓ {part_name}: {len(points)} ctrl points")
    
    # 4. Convert + Union
    print("[mesh_sculptor] Boolean union ile birleştiriliyor...")
    mesh_obj = convert_to_mesh_and_union(part_objects, target_name="creature_mesh")
    
    if mesh_obj is None:
        print("❌ Mesh oluşturulamadı, çıkılıyor", file=sys.stderr)
        sys.exit(1)
    
    # 5. Voxel Remesh
    voxel_size = args.voxel_size if args.voxel_size else body_length / 100
    print(f"[mesh_sculptor] Voxel Remesh (size={voxel_size:.4f})...")
    voxel_remesh(mesh_obj, voxel_size)
    
    # 6. Subdivision
    if args.subdivision_level > 0:
        print(f"[mesh_sculptor] Subdivision Surface level {args.subdivision_level}...")
        subdivide(mesh_obj, args.subdivision_level)
    
    # 7. Decimate to target
    target_tris = budget_spec["polygon_budget"]["lod0_tris_target"]
    print(f"[mesh_sculptor] Decimate to {target_tris} tris...")
    final_tris = decimate_to_target(mesh_obj, target_tris)
    print(f"  ✓ Final tris: {final_tris}")
    
    # 8. Shade smooth
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.shade_smooth()
    
    # 9. Validation
    print("[mesh_sculptor] Validation...")
    val = validate_mesh(mesh_obj, budget_spec)
    
    for err in val["results"]["errors"]:
        print(f"  ❌ {err}")
    for warn in val["results"]["warnings"]:
        print(f"  ⚠️ {warn}")
    
    # 10. Manifest yaz
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "manifest_version": "1.0",
        "creature_id": creature_spec.get("creature_id"),
        "base_mesh_object_name": mesh_obj.name,
        "tris_count_actual": val["tris"],
        "tris_count_target": target_tris,
        "verts_count": val["verts"],
        "faces_count": val["faces"],
        "is_manifold": val["is_manifold"],
        "is_watertight": val["is_watertight"],
        "bbox_min": val["bbox_min"],
        "bbox_max": val["bbox_max"],
        "voxel_remesh_size": voxel_size,
        "subdivision_level_used": args.subdivision_level,
        "profile_resolution": args.profile_resolution,
        "segment_resolution": args.segment_resolution,
        "errors": val["results"]["errors"],
        "warnings": val["results"]["warnings"],
        "generated_by": "P04_mesh_sculptor",
    }
    
    manifest_path = output_path.with_suffix('.mesh_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    # 11. Save
    print(f"[mesh_sculptor] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print(f"[mesh_sculptor] ✅ Tamamlandı")
    print(f"   • Mesh: {mesh_obj.name}")
    print(f"   • Tris: {val['tris']} (hedef {target_tris})")
    print(f"   • Manifold: {val['is_manifold']}, Watertight: {val['is_watertight']}")


if __name__ == "__main__":
    main()
