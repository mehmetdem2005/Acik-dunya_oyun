#!/usr/bin/env python3
"""
build_rigging_polish.py — P07 Rigger Polish

Armature'a custom bone display shapes + bone groups/colors ekler.
Animator UI polish, deformation'a etki etmez.
"""

import bpy
import json
import sys
import argparse
from pathlib import Path


def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser()
    p.add_argument("--output-blend", required=True)
    return p.parse_args(argv)


def find_armature():
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


# =============================================================================
# Widget shape mesh'leri
# =============================================================================

def create_widget_collection():
    """Widget'lar için ayrı collection."""
    col_name = "Widgets"
    if col_name in bpy.data.collections:
        return bpy.data.collections[col_name]
    
    col = bpy.data.collections.new(col_name)
    bpy.context.scene.collection.children.link(col)
    
    # Hide
    layer_col = bpy.context.view_layer.layer_collection.children.get(col_name)
    if layer_col:
        layer_col.hide_viewport = True
    
    return col


def create_widget_sphere(name="WGT_sphere"):
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    
    mesh = bpy.data.meshes.new(name + "_data")
    obj = bpy.data.objects.new(name, mesh)
    
    # Manuel sphere verts
    import math
    segments = 12
    rings = 6
    verts = [(0, 0, 1), (0, 0, -1)]  # poles
    for ri in range(1, rings):
        phi = math.pi * ri / rings
        for si in range(segments):
            theta = 2 * math.pi * si / segments
            x = math.sin(phi) * math.cos(theta)
            y = math.sin(phi) * math.sin(theta)
            z = math.cos(phi)
            verts.append((x, y, z))
    
    # Edges (sadece wire visual için)
    edges = []
    for ri in range(rings - 1):
        for si in range(segments):
            i = 2 + ri * segments + si
            j = 2 + ri * segments + (si + 1) % segments
            edges.append((i, j))
            if ri < rings - 2:
                k = 2 + (ri + 1) * segments + si
                edges.append((i, k))
    
    mesh.from_pydata(verts, edges, [])
    
    col = create_widget_collection()
    col.objects.link(obj)
    obj.hide_render = True
    
    return obj


def create_widget_circle(name="WGT_circle"):
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    
    mesh = bpy.data.meshes.new(name + "_data")
    obj = bpy.data.objects.new(name, mesh)
    
    import math
    segments = 24
    verts = []
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        verts.append((math.cos(theta), math.sin(theta), 0))
    
    edges = [(i, (i + 1) % segments) for i in range(segments)]
    mesh.from_pydata(verts, edges, [])
    
    col = create_widget_collection()
    col.objects.link(obj)
    obj.hide_render = True
    
    return obj


def create_widget_arrow(name="WGT_arrow"):
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    
    mesh = bpy.data.meshes.new(name + "_data")
    obj = bpy.data.objects.new(name, mesh)
    
    verts = [
        (0, 0, 0),       # base
        (0, 0, 1),       # tip
        (-0.2, 0, 0.7),  # left wing
        (0.2, 0, 0.7),   # right wing
    ]
    edges = [(0, 1), (1, 2), (1, 3)]
    mesh.from_pydata(verts, edges, [])
    
    col = create_widget_collection()
    col.objects.link(obj)
    obj.hide_render = True
    
    return obj


def create_widget_cube(name="WGT_cube"):
    if name in bpy.data.objects:
        return bpy.data.objects[name]
    
    mesh = bpy.data.meshes.new(name + "_data")
    obj = bpy.data.objects.new(name, mesh)
    
    verts = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    mesh.from_pydata(verts, edges, [])
    
    col = create_widget_collection()
    col.objects.link(obj)
    obj.hide_render = True
    
    return obj


# =============================================================================
# Bone customization
# =============================================================================

def assign_custom_shape(armature_obj, bone_name, shape_obj, scale=0.15):
    pb = armature_obj.pose.bones.get(bone_name)
    if pb is None:
        return False
    
    try:
        pb.custom_shape = shape_obj
        pb.custom_shape_scale_xyz = (scale, scale, scale)
        if hasattr(pb, "use_custom_shape_bone_size"):
            pb.use_custom_shape_bone_size = False
        return True
    except Exception as e:
        print(f"  ⚠️ {bone_name} shape assign fail: {e}")
        return False


def set_bone_color_4x(bone, theme_name):
    """Blender 4.x bone color API."""
    try:
        bone.color.palette = theme_name
        return True
    except Exception:
        return False


def create_bone_collections_4x(armature_obj, groups):
    """
    Blender 4.0+ bone_collections.
    groups: list of (collection_name, list_of_bone_names)
    """
    arm = armature_obj.data
    
    if not hasattr(arm, "collections"):
        return False
    
    col_api = arm.collections
    
    for group_name, bone_names in groups:
        # Mevcut varsa
        col = col_api.get(group_name)
        if col is None:
            try:
                col = col_api.new(group_name)
            except Exception:
                continue
        
        for bn in bone_names:
            bone = arm.bones.get(bn)
            if bone:
                try:
                    col.assign(bone)
                except Exception:
                    pass
    
    return True


# =============================================================================
# Ana polish
# =============================================================================

def polish_rig(armature_obj):
    """Tüm polish'i uygula."""
    shapes = {
        "sphere": create_widget_sphere(),
        "circle": create_widget_circle(),
        "arrow": create_widget_arrow(),
        "cube": create_widget_cube(),
    }
    
    counts = {"ik_targets": 0, "pole_targets": 0, "spine_controls": 0,
              "head_control": 0, "root_master": 0}
    
    # IK targets → sphere
    for pb in armature_obj.pose.bones:
        name_lower = pb.name.lower()
        
        if "foot_ik" in name_lower or "ik_foot" in name_lower:
            if assign_custom_shape(armature_obj, pb.name, shapes["sphere"], 0.06):
                counts["ik_targets"] += 1
        elif "pole" in name_lower:
            if assign_custom_shape(armature_obj, pb.name, shapes["arrow"], 0.05):
                counts["pole_targets"] += 1
        elif pb.name in ("head", "head_ctrl"):
            if assign_custom_shape(armature_obj, pb.name, shapes["circle"], 0.20):
                counts["head_control"] += 1
        elif pb.name in ("root_master", "root"):
            if assign_custom_shape(armature_obj, pb.name, shapes["cube"], 0.12):
                counts["root_master"] += 1
        elif pb.name.startswith("spine_"):
            if assign_custom_shape(armature_obj, pb.name, shapes["circle"], 0.12):
                counts["spine_controls"] += 1
    
    # Bone colors (4.x)
    print("[rig_polish] Bone colors set ediliyor...")
    color_set_count = 0
    for bone in armature_obj.data.bones:
        success = False
        if "foot_ik" in bone.name.lower() or "ik_foot" in bone.name.lower():
            success = set_bone_color_4x(bone, 'THEME01')  # blue
        elif "pole" in bone.name.lower():
            success = set_bone_color_4x(bone, 'THEME07')  # cyan
        elif bone.name.startswith("spine_"):
            success = set_bone_color_4x(bone, 'THEME03')  # green
        elif bone.name in ("head", "jaw") or bone.name.startswith("neck_"):
            success = set_bone_color_4x(bone, 'THEME09')  # yellow
        elif bone.name.startswith("tail_"):
            success = set_bone_color_4x(bone, 'THEME02')  # orange
        elif bone.name.endswith("_L"):
            success = set_bone_color_4x(bone, 'THEME04')
        elif bone.name.endswith("_R"):
            success = set_bone_color_4x(bone, 'THEME06')
        
        if success:
            color_set_count += 1
    
    # Bone collections
    groups = [
        ("IK Controls", [b.name for b in armature_obj.data.bones
                          if "ik" in b.name.lower() or "pole" in b.name.lower()]),
        ("Spine Chain", [b.name for b in armature_obj.data.bones
                          if b.name.startswith("spine_") or b.name.startswith("neck_")]),
        ("Head + Jaw", [b.name for b in armature_obj.data.bones
                         if b.name in ("head", "jaw")]),
        ("Tail", [b.name for b in armature_obj.data.bones
                   if b.name.startswith("tail_")]),
        ("Deform Bones",
         [b.name for b in armature_obj.data.bones if b.use_deform]),
    ]
    
    bg_ok = create_bone_collections_4x(armature_obj, groups)
    
    return {
        "custom_shapes_added": counts,
        "bone_colors_set": color_set_count,
        "bone_groups_created": bg_ok,
        "total_groups": len(groups) if bg_ok else 0,
    }


def main():
    args = parse_args()
    
    armature_obj = find_armature()
    if armature_obj is None:
        print("❌ Armature yok", file=sys.stderr)
        sys.exit(1)
    
    print(f"[rig_polish] Armature: {armature_obj.name}")
    
    result = polish_rig(armature_obj)
    
    print(f"[rig_polish] Custom shapes: {result['custom_shapes_added']}")
    print(f"[rig_polish] Bone colors set: {result['bone_colors_set']}")
    print(f"[rig_polish] Bone collections: {result['total_groups']}")
    
    manifest = {
        "manifest_version": "1.0",
        "custom_shapes_added": result["custom_shapes_added"],
        "bone_colors_set_count": result["bone_colors_set"],
        "bone_groups_created": result["bone_groups_created"],
        "generated_by": "P07_rigger_polish",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_path = output_path.with_suffix('.rig_polish_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print(f"[rig_polish] ✅ {output_path}")


if __name__ == "__main__":
    main()
