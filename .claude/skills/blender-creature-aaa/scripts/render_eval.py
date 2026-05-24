#!/usr/bin/env python3
"""
render_eval.py — Skill vision-feedback için eval render üretici

Bu script Blender içinden çalıştırılır:
    blender --background <scene.blend> --python render_eval.py -- \
        --output-dir <path> \
        --target-object <name> \
        [--stress-poses] \
        [--wireframe-only] \
        [--width 1024] \
        [--height 1024]

Çıktı:
    <output-dir>/
        rest_front.png
        rest_back.png
        rest_left.png
        rest_right.png
        rest_top.png
        rest_bottom.png
        rest_34_front.png
        rest_34_back.png
        wire_*.png        (wireframe overlay 8 angle)
        stress_squat_*.png
        stress_twist_*.png
        stress_runstride_*.png
        ingame_camera.png (mobil silüet)
        render_manifest.json

Skill bu render'ları sonra vision_call.py ile Claude'a gönderir.

ÖNEMLİ NOTLAR:
- Blender 4.2 LTS uyumlu yazıldı. Eski API farkları varsa skill self-critique ile yamar.
- Headless modda çalışacak (no GUI), EEVEE Next engine kullanır.
- Material override: tüm mesh'lere geçici "neutral matcap" bind edilir.
  Eğer kullanıcı texture'lı render istiyorsa --keep-materials flag'ı.
- Stres pozlar sadece rig (armature) varsa çalışır, yoksa skip.
"""

import bpy
import json
import math
import sys
import os
import argparse
from pathlib import Path
from mathutils import Vector, Euler


# -----------------------------------------------------------------------------
# Argument parsing (Blender argv'sinden -- sonrasını al)
# -----------------------------------------------------------------------------

def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser(description="Skill eval render üretici")
    p.add_argument("--output-dir", required=True, help="Render'ların yazılacağı klasör")
    p.add_argument("--target-object", default=None, help="Hedef mesh objesi adı (auto-detect ediyor yoksa)")
    p.add_argument("--stress-poses", action="store_true", help="Stres pozları da render et")
    p.add_argument("--wireframe-only", action="store_true", help="Sadece wireframe render")
    p.add_argument("--keep-materials", action="store_true", help="Mesh'in mevcut materyalini kullan (default: neutral override)")
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--ingame-width", type=int, default=720, help="Mobil silüet render genişliği")
    p.add_argument("--ingame-height", type=int, default=1280, help="Mobil silüet render yüksekliği (portrait)")
    p.add_argument("--ingame-distance", type=float, default=10.0, help="In-game camera distance (Blender unit)")
    p.add_argument("--samples", type=int, default=32, help="EEVEE samples")
    
    return p.parse_args(argv)


# -----------------------------------------------------------------------------
# Hedef objeyi ve bounding box'unu bul
# -----------------------------------------------------------------------------

def find_target_object(name_hint=None):
    """
    Hedef mesh objesini tespit eder. Önce hint, sonra en büyük mesh.
    """
    if name_hint:
        obj = bpy.data.objects.get(name_hint)
        if obj and obj.type == 'MESH':
            return obj
    
    # Auto-detect: en büyük mesh (vertex count)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_get()]
    if not meshes:
        raise RuntimeError("Sahnede hiç mesh yok. Önce mesh oluşturulmalı.")
    
    meshes.sort(key=lambda o: len(o.data.vertices), reverse=True)
    return meshes[0]


def find_armature(mesh_obj):
    """
    Mesh'e bağlı armature'ı bulur (varsa).
    """
    # Armature modifier'dan bul
    for mod in mesh_obj.modifiers:
        if mod.type == 'ARMATURE' and mod.object is not None:
            return mod.object
    
    # Parent armature
    if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
        return mesh_obj.parent
    
    return None


def get_world_bbox_center_and_radius(obj):
    """
    Obje'nin world space bounding box merkezi ve "çapı" (kameranın ne kadar
    uzakta olması gerektiğini hesaplamak için).
    """
    world_corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    
    min_v = Vector((
        min(c.x for c in world_corners),
        min(c.y for c in world_corners),
        min(c.z for c in world_corners),
    ))
    max_v = Vector((
        max(c.x for c in world_corners),
        max(c.y for c in world_corners),
        max(c.z for c in world_corners),
    ))
    
    center = (min_v + max_v) * 0.5
    radius = (max_v - min_v).length * 0.5
    
    return center, radius, min_v, max_v


# -----------------------------------------------------------------------------
# Sahne hazırlığı: ışıklandırma, kamera, materyal override
# -----------------------------------------------------------------------------

def clean_scene_lighting():
    """Mevcut ışıkları temizle, sıfırla."""
    for obj in list(bpy.data.objects):
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)


def setup_3point_lighting(target_center, target_radius):
    """
    Klasik 3-point ışıklandırma. Hedefin etrafında.
    """
    d = target_radius * 4.0
    
    # Key light (sağ üst ön)
    bpy.ops.object.light_add(type='AREA', location=(d, -d, d * 0.8))
    key = bpy.context.object
    key.name = "EvalKey"
    key.data.energy = 800
    key.data.size = target_radius * 1.5
    key.rotation_euler = Euler((math.radians(45), 0, math.radians(45)), 'XYZ')
    # Hedefe doğrult
    key.constraints.new('TRACK_TO').target = bpy.data.objects.get("EvalTrackTarget") or _make_track_target(target_center)
    
    # Fill (sol önden, key'in zayıf yansıması)
    bpy.ops.object.light_add(type='AREA', location=(-d * 0.6, -d * 0.7, d * 0.4))
    fill = bpy.context.object
    fill.name = "EvalFill"
    fill.data.energy = 250
    fill.data.size = target_radius * 2.0
    fill.constraints.new('TRACK_TO').target = bpy.data.objects["EvalTrackTarget"]
    
    # Rim (arkadan, kenarlık ışığı)
    bpy.ops.object.light_add(type='AREA', location=(0, d * 0.8, d * 0.6))
    rim = bpy.context.object
    rim.name = "EvalRim"
    rim.data.energy = 400
    rim.data.size = target_radius * 1.0
    rim.constraints.new('TRACK_TO').target = bpy.data.objects["EvalTrackTarget"]


def _make_track_target(loc):
    """Track-to constraint için boş target."""
    bpy.ops.object.empty_add(type='SPHERE', location=loc, radius=0.1)
    e = bpy.context.object
    e.name = "EvalTrackTarget"
    return e


def setup_world_background():
    """Düz gri arka plan, hafif HDRI yerine sade."""
    world = bpy.data.worlds.get("World")
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.18, 0.18, 0.2, 1.0)  # koyu gri-mavi
    bg.inputs['Strength'].default_value = 0.3
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs[0], out.inputs[0])


def make_eval_material():
    """Eval için nötr matcap-like material."""
    mat = bpy.data.materials.new("EvalMatcap")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.58, 0.58, 0.62, 1.0)  # nötr gri
    bsdf.inputs['Roughness'].default_value = 0.42
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = 0.05
    
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


def apply_eval_material(mesh_obj, mat):
    """Mesh'in tüm materyal slotlarını override et (temp)."""
    mesh_obj["_orig_materials"] = [m.name if m else "" for m in mesh_obj.data.materials]
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)


def restore_materials(mesh_obj):
    """Override öncesi materyalleri geri yükle."""
    orig = mesh_obj.get("_orig_materials")
    if not orig:
        return
    mesh_obj.data.materials.clear()
    for name in orig:
        m = bpy.data.materials.get(name)
        if m:
            mesh_obj.data.materials.append(m)
    del mesh_obj["_orig_materials"]


# -----------------------------------------------------------------------------
# Kamera kurulumu ve 8-açı yerleştirme
# -----------------------------------------------------------------------------

def make_eval_camera(target_center, target_radius):
    """Bir kamera oluşturur, hedefe track-to constraint ekler."""
    bpy.ops.object.camera_add(location=(0, -target_radius * 3.5, target_radius * 0.5))
    cam = bpy.context.object
    cam.name = "EvalCamera"
    cam.data.lens = 50  # mm
    cam.data.clip_end = target_radius * 50
    
    # Track-to
    tt = cam.constraints.new('TRACK_TO')
    tt.target = bpy.data.objects.get("EvalTrackTarget")
    tt.track_axis = 'TRACK_NEGATIVE_Z'
    tt.up_axis = 'UP_Y'
    
    bpy.context.scene.camera = cam
    return cam


def camera_position_for_angle(target_center, target_radius, angle_name):
    """
    Açı adına göre kamera pozisyonu döndürür.
    """
    d = target_radius * 3.5  # mesafe
    cx, cy, cz = target_center
    z_mid = target_center.z
    
    positions = {
        'front':     Vector((cx,        cy - d, z_mid)),
        'back':      Vector((cx,        cy + d, z_mid)),
        'left':      Vector((cx - d,    cy,     z_mid)),
        'right':     Vector((cx + d,    cy,     z_mid)),
        'top':       Vector((cx,        cy,     cz + d)),
        'bottom':    Vector((cx,        cy,     cz - d)),
        '34_front':  Vector((cx - d*0.7, cy - d*0.7, z_mid + target_radius * 0.3)),
        '34_back':   Vector((cx + d*0.7, cy + d*0.7, z_mid + target_radius * 0.3)),
    }
    return positions[angle_name]


# -----------------------------------------------------------------------------
# Render engine ayarları
# -----------------------------------------------------------------------------

def setup_render_engine(width, height, samples=32):
    scene = bpy.context.scene
    
    # EEVEE Next (Blender 4.2+)
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except Exception:
        # Fallback
        scene.render.engine = 'BLENDER_EEVEE'
    
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    
    # EEVEE samples
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_render_samples = samples
        if hasattr(scene.eevee, 'use_gtao'):
            scene.eevee.use_gtao = True


def render_to_file(filepath):
    """Mevcut sahneyi render edip filepath'e yazar."""
    bpy.context.scene.render.filepath = str(filepath)
    bpy.ops.render.render(write_still=True)


# -----------------------------------------------------------------------------
# Wireframe overlay render
# -----------------------------------------------------------------------------

def setup_wireframe_overlay(mesh_obj):
    """
    Mesh'e Wireframe modifier veya geçici wireframe shader uygular.
    Daha basit yöntem: ikinci bir kopya, Wireframe modifier ile.
    """
    # Mevcut nesnenin kopyasını al
    wire_copy = mesh_obj.copy()
    wire_copy.data = mesh_obj.data.copy()
    wire_copy.name = mesh_obj.name + "_WIRE_TEMP"
    bpy.context.collection.objects.link(wire_copy)
    
    # Wireframe modifier
    wm = wire_copy.modifiers.new("Wireframe", 'WIREFRAME')
    wm.thickness = 0.005
    wm.use_replace = False  # original mesh'in üstüne wire çiz
    
    # Siyah materyal
    mat = bpy.data.materials.new("WireMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (0.05, 0.05, 0.05, 1.0)
    emit.inputs['Strength'].default_value = 1.0
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(emit.outputs[0], out.inputs[0])
    
    wire_copy.data.materials.clear()
    wire_copy.data.materials.append(mat)
    
    return wire_copy


def cleanup_wireframe_overlay(wire_obj):
    bpy.data.objects.remove(wire_obj, do_unlink=True)


# -----------------------------------------------------------------------------
# Stres pozları
# -----------------------------------------------------------------------------

def has_meaningful_rig(armature):
    """Armature en az 5 bone içeriyor mu (rig var sayılması için)."""
    return armature is not None and len(armature.data.bones) >= 5


def apply_pose_squat(armature):
    """Tüm IK ayaklarını yukarı, kalçayı aşağı (squat)."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='DESELECT')
    
    for pbone in armature.pose.bones:
        # IK foot bone'larını tespit (naming convention'a göre)
        name_lower = pbone.name.lower()
        if 'foot_ik' in name_lower or 'ik_foot' in name_lower:
            pbone.location.z += 0.3  # yukarı
        elif 'hip' in name_lower or 'spine_hip' in name_lower or pbone.name == 'root':
            pbone.location.z -= 0.4  # aşağı
    
    bpy.context.view_layer.update()


def apply_pose_twist(armature):
    """Omurzayı yana 35 derece bükmeyi dener."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    for pbone in armature.pose.bones:
        name_lower = pbone.name.lower()
        if 'spine' in name_lower and 'hip' not in name_lower:
            pbone.rotation_mode = 'XYZ'
            pbone.rotation_euler[2] = math.radians(35) / max(1, count_spine_bones(armature))
    
    bpy.context.view_layer.update()


def count_spine_bones(armature):
    return sum(1 for b in armature.data.bones if 'spine' in b.name.lower())


def apply_pose_runstride(armature):
    """Çapraz bacaklar ekstrem ileri-geri."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    
    for pbone in armature.pose.bones:
        name_lower = pbone.name.lower()
        # Sol ön + sağ arka ileri
        if 'foot_ik' in name_lower:
            if ('front' in name_lower and '_l' in name_lower) or ('rear' in name_lower and '_r' in name_lower):
                pbone.location.y -= 0.5  # ileri
                pbone.location.z += 0.2  # havada
            elif ('front' in name_lower and '_r' in name_lower) or ('rear' in name_lower and '_l' in name_lower):
                pbone.location.y += 0.5  # geri
    
    bpy.context.view_layer.update()


def reset_pose(armature):
    """Tüm pose'u sıfırla (rest pose'a dön)."""
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.transforms_clear()
    bpy.ops.object.mode_set(mode='OBJECT')


# -----------------------------------------------------------------------------
# Ana akış
# -----------------------------------------------------------------------------

def main():
    args = parse_args()
    
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "renders": [],
        "wireframe": [],
        "stress": [],
        "ingame": None,
        "target_object": None,
        "armature_found": False,
        "skipped_stress": False,
    }
    
    # 1. Hedef bul
    target = find_target_object(args.target_object)
    manifest["target_object"] = target.name
    armature = find_armature(target)
    manifest["armature_found"] = armature is not None
    
    # 2. BBox + ortam
    center, radius, min_v, max_v = get_world_bbox_center_and_radius(target)
    
    # Sahneyi temizle ve kur
    clean_scene_lighting()
    _make_track_target(center)
    setup_3point_lighting(center, radius)
    setup_world_background()
    
    # 3. Material override (eğer keep-materials kapalıysa)
    if not args.keep_materials:
        eval_mat = make_eval_material()
        apply_eval_material(target, eval_mat)
    
    # 4. Kamera
    cam = make_eval_camera(center, radius)
    
    # 5. Render engine
    setup_render_engine(args.width, args.height, args.samples)
    
    # 6. 8 açı rest pose render
    angles = ['front', 'back', 'left', 'right', 'top', 'bottom', '34_front', '34_back']
    
    if not args.wireframe_only:
        for ang in angles:
            cam.location = camera_position_for_angle(center, radius, ang)
            bpy.context.view_layer.update()
            
            fp = out_dir / f"rest_{ang}.png"
            render_to_file(fp)
            manifest["renders"].append(str(fp.name))
    
    # 7. Wireframe overlay
    wire_obj = setup_wireframe_overlay(target)
    for ang in angles:
        cam.location = camera_position_for_angle(center, radius, ang)
        bpy.context.view_layer.update()
        
        fp = out_dir / f"wire_{ang}.png"
        render_to_file(fp)
        manifest["wireframe"].append(str(fp.name))
    cleanup_wireframe_overlay(wire_obj)
    
    # 8. Stres pozları (rig varsa ve istendiyse)
    if args.stress_poses and has_meaningful_rig(armature):
        stress_poses = [
            ('squat', apply_pose_squat),
            ('twist', apply_pose_twist),
            ('runstride', apply_pose_runstride),
        ]
        
        for pose_name, apply_fn in stress_poses:
            reset_pose(armature)
            apply_fn(armature)
            
            # Her stres pozu için 4 açı
            for ang in ['front', 'left', '34_front', 'top']:
                cam.location = camera_position_for_angle(center, radius, ang)
                bpy.context.view_layer.update()
                
                fp = out_dir / f"stress_{pose_name}_{ang}.png"
                render_to_file(fp)
                manifest["stress"].append(str(fp.name))
        
        reset_pose(armature)
    elif args.stress_poses:
        manifest["skipped_stress"] = True  # rig yoktu
    
    # 9. In-game camera (mobil silüet)
    setup_render_engine(args.ingame_width, args.ingame_height, args.samples)
    cam.location = camera_position_for_angle(center, radius, '34_front')
    # In-game distance simulate
    cam_offset = (cam.location - center).normalized() * args.ingame_distance
    cam.location = center + cam_offset
    bpy.context.view_layer.update()
    
    ingame_fp = out_dir / "ingame_camera.png"
    render_to_file(ingame_fp)
    manifest["ingame"] = str(ingame_fp.name)
    
    # 10. Materyal restore (eğer override yapılmıştıysa)
    if not args.keep_materials:
        restore_materials(target)
    
    # 11. Manifest yaz
    manifest_fp = out_dir / "render_manifest.json"
    manifest_fp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(f"\n✅ Render tamamlandı: {out_dir}")
    print(f"   Toplam: {len(manifest['renders'])} rest + "
          f"{len(manifest['wireframe'])} wire + "
          f"{len(manifest['stress'])} stress + "
          f"1 ingame")


if __name__ == "__main__":
    main()
