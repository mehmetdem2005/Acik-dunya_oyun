#!/usr/bin/env python3
"""
build_detail_injection.py — P04b Detail Injector

P04 sonrası blockout mesh'e anatomik landmark'lara dayalı primitive'ler ekler:
- 4 pati (sphere cluster: 1 main pad + 3-4 toe)
- 2 kulak (cone primitives)
- 2 göz çukuru (boolean cut) + 2 göz küresi
- 1 snout (tapered cone)
- 1 nose tip (small sphere)
- 1 tail tuft (sphere at tail end)
- 1 mouth line (edge crease)

Sonra voxel remesh ile hepsini ana mesh'e birleştirir.

Blender içinde çalışır:
    blender --background mesh_v1.blend --python build_detail_injection.py -- \\
        --blueprint SkeletonBlueprint.json \\
        --landmarks LandmarkSpec.json \\
        --creature-spec CreatureSpec.json \\
        --output-blend mesh_v2.blend
"""

import bpy
import bmesh
import json
import math
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
    p.add_argument("--landmarks", required=True,
                   help="LandmarkSpec.json (anatomical landmark koordinatları)")
    p.add_argument("--creature-spec", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--voxel-size", type=float, default=0.008)
    return p.parse_args(argv)


# =============================================================================
# Helpers
# =============================================================================

def find_main_mesh():
    """En büyük mesh'i bul (ana gövde)."""
    main = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            if main is None or len(obj.data.vertices) > len(main.data.vertices):
                main = obj
    return main


def find_armature():
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


def get_bone_world_position(armature_obj, bone_name):
    """Bone'un dünya koordinatındaki head position."""
    if armature_obj is None or bone_name not in armature_obj.data.bones:
        return None
    bone = armature_obj.data.bones[bone_name]
    return armature_obj.matrix_world @ bone.head_local


def get_bone_world_tail(armature_obj, bone_name):
    if armature_obj is None or bone_name not in armature_obj.data.bones:
        return None
    bone = armature_obj.data.bones[bone_name]
    return armature_obj.matrix_world @ bone.tail_local


def get_bone_direction(armature_obj, bone_name):
    """Bone'un baktığı yön (head → tail)."""
    head = get_bone_world_position(armature_obj, bone_name)
    tail = get_bone_world_tail(armature_obj, bone_name)
    if head and tail:
        direction = (tail - head)
        if direction.length > 0:
            return direction.normalized()
    return Vector((0, 1, 0))


# =============================================================================
# Primitive injectors
# =============================================================================

def add_paw_cluster(landmark_pos, species="wolf", size_multiplier=1.0):
    """
    Pati: 1 ana pad sphere + 3-4 toe sphere.
    Wolf/dog: 4 toe, cat: 4 toe, deer/horse: hoof (single ellipsoid).
    """
    pos = Vector(landmark_pos)
    
    if species in ("horse", "deer", "cow", "goat"):
        # Toynak (hoof) — tek ellipsoid
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.04 * size_multiplier, location=pos
        )
        hoof = bpy.context.active_object
        hoof.scale = (1.2, 1.5, 0.8)  # eliptik
        bpy.ops.object.transform_apply(scale=True)
        return [hoof]
    
    # Mammal pati: 1 büyük pad + 4 küçük toe
    objects = []
    
    # Ana pad (alt kısım)
    pad_pos = pos.copy()
    pad_pos.z -= 0.005
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.038 * size_multiplier, location=pad_pos, segments=14, ring_count=8
    )
    pad = bpy.context.active_object
    pad.scale = (1.1, 1.15, 0.55)  # basık oval
    bpy.ops.object.transform_apply(scale=True)
    pad.name = "paw_pad"
    objects.append(pad)
    
    # 4 toe (önde, hafif yayılmış)
    toe_offsets = [
        (0.018, 0.025, 0.005),    # toe 1 sol
        (0.006, 0.030, 0.005),    # toe 2
        (-0.006, 0.030, 0.005),   # toe 3
        (-0.018, 0.025, 0.005),   # toe 4 sağ
    ]
    
    toe_size = 0.013 * size_multiplier
    for i, off in enumerate(toe_offsets):
        toe_pos = pos + Vector(off)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=toe_size, location=toe_pos, segments=10, ring_count=6
        )
        toe = bpy.context.active_object
        toe.scale = (1.0, 1.4, 0.8)  # uzunlamasına oval (parmak şekli)
        bpy.ops.object.transform_apply(scale=True)
        toe.name = f"toe_{i}"
        objects.append(toe)
    
    return objects


def add_ear_cone(landmark_pos, side="L", species="wolf", size_multiplier=1.0,
                  tilt_outward_deg=15):
    """
    Kulak: kişiye/türe özgü cone.
    """
    pos = Vector(landmark_pos)
    
    # Ear type by species
    if species in ("wolf", "dog", "fox", "cat"):
        height = 0.10 * size_multiplier
        base_r = 0.035 * size_multiplier
        tip_r = 0.002  # neredeyse sivri
    elif species == "bear":
        height = 0.06 * size_multiplier
        base_r = 0.040 * size_multiplier
        tip_r = 0.015  # yuvarlak
    elif species == "rabbit":
        height = 0.20 * size_multiplier
        base_r = 0.030 * size_multiplier
        tip_r = 0.020  # uzun ve oval uç
    else:
        height = 0.08 * size_multiplier
        base_r = 0.035 * size_multiplier
        tip_r = 0.005
    
    # Cone primitive
    bpy.ops.mesh.primitive_cone_add(
        vertices=12, radius1=base_r, radius2=tip_r, depth=height,
        location=pos,
    )
    ear = bpy.context.active_object
    
    # Outward tilt
    tilt_rad = math.radians(tilt_outward_deg)
    if side == "L":
        ear.rotation_euler = (0, tilt_rad, 0)
    else:
        ear.rotation_euler = (0, -tilt_rad, 0)
    
    # Üst eksene doğru kaldır (z + height/2)
    ear.location.z += height / 2
    
    bpy.ops.object.transform_apply(rotation=True)
    ear.name = f"ear_{side}"
    
    return ear


def add_snout(landmark_pos, head_direction, species="wolf",
                size_multiplier=1.0):
    """
    Snout: tapered cylinder. Head bone'un baktığı yöne uzanır.
    """
    pos = Vector(landmark_pos)
    direction = Vector(head_direction).normalized()
    
    if species in ("wolf", "dog", "fox"):
        length = 0.12 * size_multiplier
        base_r = 0.060 * size_multiplier
        tip_r = 0.030 * size_multiplier
    elif species == "bear":
        length = 0.10 * size_multiplier
        base_r = 0.075 * size_multiplier
        tip_r = 0.050 * size_multiplier
    elif species == "cat":
        length = 0.06 * size_multiplier
        base_r = 0.045 * size_multiplier
        tip_r = 0.025 * size_multiplier
    else:
        length = 0.10 * size_multiplier
        base_r = 0.055 * size_multiplier
        tip_r = 0.030 * size_multiplier
    
    # Cone primitive (base at pos, tip in direction)
    snout_center = pos + direction * (length / 2)
    bpy.ops.mesh.primitive_cone_add(
        vertices=16, radius1=base_r, radius2=tip_r, depth=length,
        location=snout_center,
    )
    snout = bpy.context.active_object
    
    # Rotate to align with direction
    # Cone default points +Z. Need rotation to align with direction.
    z_axis = Vector((0, 0, 1))
    if direction.length > 0:
        rot = z_axis.rotation_difference(direction)
        snout.rotation_euler = rot.to_euler()
        bpy.ops.object.transform_apply(rotation=True)
    
    snout.name = "snout"
    
    # Nose tip (küçük sphere uçta)
    nose_tip_pos = pos + direction * length
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=tip_r * 0.95, location=nose_tip_pos, segments=10, ring_count=6
    )
    nose = bpy.context.active_object
    nose.name = "nose_tip"
    
    return [snout, nose]


def add_eye_socket_and_ball(landmark_pos, side="L"):
    """
    Göz: socket boolean cut + eye sphere.
    Şimdilik sadece eye sphere ekleyelim (boolean cut voxel remesh sonrası anlamsız)
    """
    pos = Vector(landmark_pos)
    
    # Eye sphere (küçük, head'in içine biraz gömülü)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.015, location=pos, segments=12, ring_count=8
    )
    eye = bpy.context.active_object
    eye.name = f"eye_{side}"
    
    return [eye]


def add_tail_tuft(landmark_pos, species="wolf", size_multiplier=1.0):
    """Kuyruk ucuna gür sphere."""
    pos = Vector(landmark_pos)
    
    species_radius = {
        "wolf": 0.045, "dog": 0.040, "fox": 0.050,
        "cat": 0.025, "lion": 0.055,
        "bear": 0.030, "horse": 0.060, "cow": 0.040,
    }
    
    radius = species_radius.get(species, 0.040) * size_multiplier
    
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius, location=pos, segments=14, ring_count=8
    )
    tuft = bpy.context.active_object
    tuft.scale = (1.0, 1.3, 0.95)  # hafif uzun
    bpy.ops.object.transform_apply(scale=True)
    tuft.name = "tail_tuft"
    
    return tuft


# =============================================================================
# Landmark generation (anatomy class'tan)
# =============================================================================

def generate_landmarks_from_skeleton(armature_obj, creature_spec, anatomy_class):
    """
    Eğer LandmarkSpec.json yoksa, skeleton + anatomy class'tan üret.
    Bu fallback — ideal P03'te landmark üretir.
    """
    landmarks = {}
    species = creature_spec.get("species_common_name", "wolf").lower()
    
    if anatomy_class == "mammalia_quadruped":
        # Eyes — skull/head bone üst kısmı
        head_pos = get_bone_world_position(armature_obj, "head")
        head_dir = get_bone_direction(armature_obj, "head")
        if head_pos:
            # Eye L/R: head'in iki yanı, biraz öne
            forward = head_dir
            right = Vector((1, 0, 0))
            
            eye_offset_forward = 0.04
            eye_offset_side = 0.045
            eye_offset_up = 0.025
            
            landmarks["eye_L"] = list(head_pos + forward * eye_offset_forward
                                       + right * eye_offset_side
                                       + Vector((0, 0, eye_offset_up)))
            landmarks["eye_R"] = list(head_pos + forward * eye_offset_forward
                                       - right * eye_offset_side
                                       + Vector((0, 0, eye_offset_up)))
            
            # Ears: head üstü, biraz arkada
            ear_offset_forward = -0.02
            ear_offset_side = 0.06
            ear_offset_up = 0.06
            landmarks["ear_L"] = list(head_pos + forward * ear_offset_forward
                                       + right * ear_offset_side
                                       + Vector((0, 0, ear_offset_up)))
            landmarks["ear_R"] = list(head_pos + forward * ear_offset_forward
                                       - right * ear_offset_side
                                       + Vector((0, 0, ear_offset_up)))
            
            # Snout: head'in önü
            landmarks["snout_base"] = list(head_pos + forward * 0.03)
            landmarks["snout_direction"] = list(forward)
        
        # Paws: 4 foot bone uçları
        for side in ["L", "R"]:
            for prefix in ["front", "rear"]:
                bone_names = [
                    f"foot_{prefix}_{side}",
                    f"paw_{prefix}_{side}",
                    f"{prefix}_foot_{side}",
                    f"foot_{side}_{prefix}",
                ]
                pos = None
                for bn in bone_names:
                    p = get_bone_world_tail(armature_obj, bn)
                    if p:
                        pos = p
                        break
                
                if pos is None:
                    # Heuristic: shin_<prefix>_<side> bone'unun tail'i
                    for bn in [f"shin_{prefix}_{side}", f"lower_leg_{prefix}_{side}"]:
                        p = get_bone_world_tail(armature_obj, bn)
                        if p:
                            pos = p
                            break
                
                if pos:
                    landmarks[f"paw_{prefix}_{side}"] = list(pos)
        
        # Tail tuft
        tail_bones = ["tail_05", "tail_04", "tail_03", "tail_02", "tail_01", "tail_00"]
        for tb in tail_bones:
            tail_tip = get_bone_world_tail(armature_obj, tb)
            if tail_tip:
                landmarks["tail_tuft"] = list(tail_tip)
                break
    
    return landmarks


# =============================================================================
# Merge with voxel remesh
# =============================================================================

def merge_all_to_main(main_mesh, injection_objects, voxel_size=0.008,
                       final_tris=15000):
    """Join + voxel remesh + decimate."""
    bpy.ops.object.select_all(action='DESELECT')
    
    # Select all injections + main, active = main
    for obj in injection_objects:
        if obj and obj.name in bpy.data.objects:
            obj.select_set(True)
    main_mesh.select_set(True)
    bpy.context.view_layer.objects.active = main_mesh
    
    # Join
    bpy.ops.object.join()
    
    # Voxel remesh
    rem = main_mesh.modifiers.new("FinalRemesh", 'REMESH')
    rem.mode = 'VOXEL'
    rem.voxel_size = voxel_size
    rem.use_smooth_shade = True
    
    try:
        bpy.ops.object.modifier_apply(modifier=rem.name)
    except Exception as e:
        print(f"  ⚠️ Voxel remesh fail: {e}")
        main_mesh.modifiers.remove(rem)
    
    # Decimate to budget
    current = len(main_mesh.data.polygons)
    print(f"  After remesh: {current} faces")
    
    if current > final_tris:
        dec = main_mesh.modifiers.new("FinalDecimate", 'DECIMATE')
        dec.ratio = final_tris / current
        try:
            bpy.ops.object.modifier_apply(modifier=dec.name)
        except Exception as e:
            print(f"  ⚠️ Decimate fail: {e}")
            main_mesh.modifiers.remove(dec)
    
    # Recalc normals
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


# =============================================================================
# Main
# =============================================================================

def main():
    args = parse_args()
    
    blueprint = json.loads(Path(args.blueprint).read_text())
    creature_spec = json.loads(Path(args.creature_spec).read_text())
    
    armature_obj = find_armature()
    main_mesh = find_main_mesh()
    
    if main_mesh is None:
        print("❌ Ana mesh yok", file=sys.stderr)
        sys.exit(1)
    
    print(f"[detail_inject] Main mesh: {main_mesh.name}")
    print(f"[detail_inject] Verts before: {len(main_mesh.data.vertices)}, "
          f"Faces: {len(main_mesh.data.polygons)}")
    
    # Landmarks: dosyadan oku veya skeleton'dan üret
    landmarks_file = Path(args.landmarks)
    if landmarks_file.exists():
        landmarks = json.loads(landmarks_file.read_text()).get("landmarks", {})
        print(f"[detail_inject] {len(landmarks)} landmark dosyadan yüklendi")
    else:
        print(f"[detail_inject] LandmarkSpec.json yok, skeleton'dan üretiliyor...")
        anatomy_class = blueprint.get("anatomy_class", "mammalia_quadruped")
        landmarks = generate_landmarks_from_skeleton(
            armature_obj, creature_spec, anatomy_class
        )
        print(f"[detail_inject] {len(landmarks)} landmark üretildi")
    
    if not landmarks:
        print("❌ Hiç landmark yok, devam edilemez", file=sys.stderr)
        sys.exit(2)
    
    species = creature_spec.get("species_common_name", "wolf").lower()
    print(f"[detail_inject] Species: {species}")
    
    injection_objects = []
    counts = {"paws": 0, "ears": 0, "eyes": 0, "snout": 0, "nose": 0,
                "tail_tuft": 0}
    
    # 1. Eyes
    for side in ["L", "R"]:
        key = f"eye_{side}"
        if key in landmarks:
            objs = add_eye_socket_and_ball(landmarks[key], side=side)
            injection_objects.extend(objs)
            counts["eyes"] += 1
    
    # 2. Ears
    for side in ["L", "R"]:
        key = f"ear_{side}"
        if key in landmarks:
            ear = add_ear_cone(landmarks[key], side=side, species=species)
            injection_objects.append(ear)
            counts["ears"] += 1
    
    # 3. Snout + nose
    if "snout_base" in landmarks and "snout_direction" in landmarks:
        objs = add_snout(landmarks["snout_base"], landmarks["snout_direction"],
                          species=species)
        injection_objects.extend(objs)
        counts["snout"] += 1
        counts["nose"] += 1
    
    # 4. Paws (4 foot)
    for side in ["L", "R"]:
        for prefix in ["front", "rear"]:
            key = f"paw_{prefix}_{side}"
            if key in landmarks:
                objs = add_paw_cluster(landmarks[key], species=species)
                injection_objects.extend(objs)
                counts["paws"] += 1
    
    # 5. Tail tuft
    if "tail_tuft" in landmarks:
        tuft = add_tail_tuft(landmarks["tail_tuft"], species=species)
        injection_objects.append(tuft)
        counts["tail_tuft"] += 1
    
    print(f"[detail_inject] Injections: {counts}")
    
    # Re-find main mesh (active may have changed)
    main_mesh = find_main_mesh()
    if main_mesh is None:
        # injection_objects içinde ana mesh olabilir
        for obj in injection_objects:
            if obj and obj.type == 'MESH' and "paw_pad" not in obj.name and "eye" not in obj.name:
                main_mesh = obj
                break
    
    # Filter out main_mesh from injection_objects to avoid joining with self
    injection_objects = [o for o in injection_objects
                          if o and o != main_mesh and o.name in bpy.data.objects]
    
    # 6. Merge
    print(f"[detail_inject] Merging {len(injection_objects)} primitives into main mesh...")
    merge_all_to_main(main_mesh, injection_objects, voxel_size=args.voxel_size)
    
    final_verts = len(main_mesh.data.vertices)
    final_faces = len(main_mesh.data.polygons)
    
    print(f"[detail_inject] Final: {final_verts} verts, {final_faces} faces")
    
    # Manifest
    manifest = {
        "manifest_version": "1.0",
        "injections_applied": counts,
        "after_remesh": {
            "verts": final_verts,
            "faces": final_faces,
        },
        "voxel_size_used": args.voxel_size,
        "generated_by": "P04b_detail_injector",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.with_suffix('.detail_injection_manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )
    
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    print(f"[detail_inject] ✅ {output_path}")


if __name__ == "__main__":
    main()
