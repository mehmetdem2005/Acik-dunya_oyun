#!/usr/bin/env python3
"""
build_material.py — P11 Material Alchemist

Mesh'e PBR Principled BSDF material + (placeholder veya provided) texture'lar.
ORM packing strategy. Godot .tres üretir.
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
    p.add_argument("--budget", required=True)
    p.add_argument("--creature-id", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-tres", default=None)
    p.add_argument("--textures-dir", default=None)
    return p.parse_args(argv)


def find_mesh():
    mesh = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            if mesh is None or len(obj.data.vertices) > len(mesh.data.vertices):
                mesh = obj
    return mesh


def create_placeholder_image(name, resolution, color):
    """Düz renkli image."""
    # Mevcut varsa sil
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    
    img = bpy.data.images.new(name, width=resolution, height=resolution, alpha=True)
    
    # Pixels: flat list [R, G, B, A, R, G, B, A, ...]
    pixel_data = list(color) * (resolution * resolution)
    img.pixels[:] = pixel_data
    img.pack()
    
    return img


def load_or_placeholder(textures_dir, slot_name, creature_id, resolution, placeholder_color):
    """Texture dir'den yükle, yoksa placeholder."""
    if textures_dir is not None:
        tex_dir = Path(textures_dir)
        candidates = [
            tex_dir / f"{creature_id}_{slot_name}.png",
            tex_dir / f"{slot_name}.png",
        ]
        for cand in candidates:
            if cand.exists():
                img = bpy.data.images.load(str(cand))
                return img, False  # not placeholder
    
    img = create_placeholder_image(
        f"{creature_id}_{slot_name}", resolution, placeholder_color
    )
    return img, True


def setup_pbr_material(mesh_obj, creature_id, atlas_resolution, textures_dir=None):
    """PBR material kur."""
    mat_name = f"{creature_id}_main"
    
    # Mevcut varsa sil
    if mat_name in bpy.data.materials:
        bpy.data.materials.remove(bpy.data.materials[mat_name])
    
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    
    nt = mat.node_tree
    nt.nodes.clear()
    
    # Nodes
    out_node = nt.nodes.new('ShaderNodeOutputMaterial')
    out_node.location = (700, 0)
    
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    
    # Defaults (fallback colors if texture'lar boş)
    bsdf.inputs['Base Color'].default_value = (0.5, 0.45, 0.4, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.7
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = 0.0
    
    nt.links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    
    # UV map
    uv_node = nt.nodes.new('ShaderNodeUVMap')
    uv_node.location = (-900, 0)
    uv_node.uv_map = "UVMap"
    
    # Albedo
    albedo_tex = nt.nodes.new('ShaderNodeTexImage')
    albedo_tex.location = (-500, 300)
    albedo_tex.label = "Albedo"
    albedo_img, albedo_placeholder = load_or_placeholder(
        textures_dir, "albedo", creature_id, atlas_resolution,
        (0.5, 0.45, 0.4, 1.0)
    )
    albedo_tex.image = albedo_img
    if albedo_img:
        albedo_img.colorspace_settings.name = 'sRGB'
    
    nt.links.new(uv_node.outputs['UV'], albedo_tex.inputs['Vector'])
    nt.links.new(albedo_tex.outputs['Color'], bsdf.inputs['Base Color'])
    
    # Normal
    normal_tex = nt.nodes.new('ShaderNodeTexImage')
    normal_tex.location = (-500, 0)
    normal_tex.label = "Normal"
    normal_img, normal_placeholder = load_or_placeholder(
        textures_dir, "normal", creature_id, atlas_resolution,
        (0.5, 0.5, 1.0, 1.0)  # flat normal
    )
    normal_tex.image = normal_img
    if normal_img:
        normal_img.colorspace_settings.name = 'Non-Color'
    
    normal_map_node = nt.nodes.new('ShaderNodeNormalMap')
    normal_map_node.location = (-100, 0)
    normal_map_node.uv_map = "UVMap"
    
    nt.links.new(uv_node.outputs['UV'], normal_tex.inputs['Vector'])
    nt.links.new(normal_tex.outputs['Color'], normal_map_node.inputs['Color'])
    nt.links.new(normal_map_node.outputs['Normal'], bsdf.inputs['Normal'])
    
    # ORM packed (R=AO, G=Roughness, B=Metallic)
    orm_tex = nt.nodes.new('ShaderNodeTexImage')
    orm_tex.location = (-500, -350)
    orm_tex.label = "ORM"
    orm_img, orm_placeholder = load_or_placeholder(
        textures_dir, "orm", creature_id, atlas_resolution,
        (1.0, 0.7, 0.0, 1.0)  # AO=1, R=0.7, M=0
    )
    orm_tex.image = orm_img
    if orm_img:
        orm_img.colorspace_settings.name = 'Non-Color'
    
    nt.links.new(uv_node.outputs['UV'], orm_tex.inputs['Vector'])
    
    # Separate ORM channels
    sep_node = nt.nodes.new('ShaderNodeSeparateColor')
    sep_node.location = (-100, -350)
    sep_node.mode = 'RGB'
    
    nt.links.new(orm_tex.outputs['Color'], sep_node.inputs['Color'])
    # R = Occlusion (export only, no Blender BSDF input directly in Cycles)
    # G = Roughness
    nt.links.new(sep_node.outputs['Green'], bsdf.inputs['Roughness'])
    # B = Metallic
    if 'Metallic' in bsdf.inputs:
        nt.links.new(sep_node.outputs['Blue'], bsdf.inputs['Metallic'])
    
    # Mesh'e ata
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)
    
    return mat, {
        "albedo_placeholder": albedo_placeholder,
        "normal_placeholder": normal_placeholder,
        "orm_placeholder": orm_placeholder,
    }


def write_godot_tres(output_path, creature_id):
    """Godot 4 StandardMaterial3D .tres."""
    tres_content = f"""[gd_resource type="StandardMaterial3D" load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://creatures/{creature_id}/textures/{creature_id}_albedo.png" id="1_albedo"]
[ext_resource type="Texture2D" path="res://creatures/{creature_id}/textures/{creature_id}_normal.png" id="2_normal"]
[ext_resource type="Texture2D" path="res://creatures/{creature_id}/textures/{creature_id}_orm.png" id="3_orm"]

[resource]
resource_name = "{creature_id}_main"

; Albedo
albedo_texture = ExtResource("1_albedo")

; Normal map
normal_enabled = true
normal_texture = ExtResource("2_normal")
normal_scale = 1.0

; Ambient Occlusion (ORM.R)
ao_enabled = true
ao_texture = ExtResource("3_orm")
ao_texture_channel = 0
ao_light_affect = 0.0

; Roughness (ORM.G)
roughness = 1.0
roughness_texture = ExtResource("3_orm")
roughness_texture_channel = 1

; Metallic (ORM.B)
metallic = 1.0
metallic_texture = ExtResource("3_orm")
metallic_texture_channel = 2
metallic_specular = 0.5

; Mobile-friendly
shading_mode = 1  ; per_pixel
diffuse_mode = 0  ; burley
"""
    Path(output_path).write_text(tres_content, encoding='utf-8')


def main():
    args = parse_args()
    
    budget = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    creature_id = args.creature_id
    
    atlas_res = budget["texture_budget"].get("main_atlas_resolution", 2048)
    
    mesh_obj = find_mesh()
    if mesh_obj is None:
        print("❌ Mesh yok", file=sys.stderr)
        sys.exit(1)
    
    print(f"[material] Mesh: {mesh_obj.name}")
    print(f"[material] Atlas resolution: {atlas_res}")
    
    # UV check
    if not mesh_obj.data.uv_layers:
        print("  ⚠️ UV layer yok, Smart UV Project ile fallback")
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # PBR material
    print("[material] PBR material setup...")
    mat, placeholders = setup_pbr_material(
        mesh_obj, creature_id, atlas_res,
        textures_dir=args.textures_dir,
    )
    
    print(f"  ✓ Material: {mat.name}")
    for slot, is_ph in placeholders.items():
        print(f"  {'⚠️ placeholder' if is_ph else '✓ provided'}: {slot}")
    
    # Godot .tres
    if args.output_tres:
        tres_path = Path(args.output_tres).resolve()
        tres_path.parent.mkdir(parents=True, exist_ok=True)
        write_godot_tres(tres_path, creature_id)
        print(f"  ✓ Godot .tres: {tres_path}")
    
    # Manifest
    manifest = {
        "manifest_version": "1.0",
        "creature_id": creature_id,
        "material_name": mat.name,
        "shader_type": "PrincipledBSDF",
        "texture_strategy": budget["texture_budget"].get("atlas_strategy", "single_atlas"),
        "atlas_resolution": atlas_res,
        "texture_slots": [
            {"slot": "Base Color", "is_placeholder": placeholders["albedo_placeholder"]},
            {"slot": "Normal", "is_placeholder": placeholders["normal_placeholder"]},
            {"slot": "ORM (packed)", "is_placeholder": placeholders["orm_placeholder"]},
        ],
        "godot_tres_path": args.output_tres,
        "user_action_required": [
            "Albedo texture'ı paint et veya sağla",
            "Normal map oluştur (bake veya manuel)",
            "ORM map oluştur (R=AO, G=roughness, B=metallic)",
        ] if any(placeholders.values()) else [],
        "generated_by": "P11_material_alchemist",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_path = output_path.with_suffix('.material_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(f"[material] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print(f"[material] ✅ Tamamlandı")


if __name__ == "__main__":
    main()
