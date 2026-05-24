#!/usr/bin/env python3
"""
build_uv.py — P06 UV Cartographer

Mesh için seam yerleştirme + Smart UV Project + pack islands.
"""

import bpy
import bmesh
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
    p.add_argument("--budget", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--angle-limit", type=float, default=66)
    p.add_argument("--island-margin", type=float, default=0.015)
    p.add_argument("--method", default="smart", choices=["smart", "marked_seams"])
    return p.parse_args(argv)


def find_mesh():
    mesh = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            if mesh is None or len(obj.data.vertices) > len(mesh.data.vertices):
                mesh = obj
    return mesh


def mark_symmetry_seam(mesh_obj):
    """X=0 ekseninde simetri seam'i mark et."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    
    seam_count = 0
    for edge in bm.edges:
        v1, v2 = edge.verts
        # X=0'a çok yakın iki vertex varsa edge seam
        if abs(v1.co.x) < 0.005 and abs(v2.co.x) < 0.005:
            edge.seam = True
            seam_count += 1
    
    bmesh.update_edit_mesh(mesh_obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    return seam_count


def mark_belly_seam(mesh_obj, body_length=1.2):
    """Karın altı boyunca seam (X≈0 + Z minimum civarı)."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    
    z_min = min(v.co.z for v in bm.verts)
    z_thresh = z_min + body_length * 0.1  # alt %10 zone
    
    seam_count = 0
    for edge in bm.edges:
        v1, v2 = edge.verts
        center_band = abs(v1.co.x) < 0.05 and abs(v2.co.x) < 0.05
        belly_zone = v1.co.z < z_thresh and v2.co.z < z_thresh
        if center_band and belly_zone:
            edge.seam = True
            seam_count += 1
    
    bmesh.update_edit_mesh(mesh_obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    return seam_count


def smart_uv_project(mesh_obj, angle_limit=66, island_margin=0.02):
    """Otomatik unwrap."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    bpy.ops.uv.smart_project(
        angle_limit=angle_limit,
        island_margin=island_margin,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=False,
    )
    
    bpy.ops.object.mode_set(mode='OBJECT')


def unwrap_with_seams(mesh_obj, margin=0.01):
    """Marked seam'leri kullanan unwrap."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=margin)
    
    bpy.ops.object.mode_set(mode='OBJECT')


def pack_islands(mesh_obj, margin=0.005):
    """Pack islands."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    except Exception as e:
        print(f"  ⚠️ pack_islands fail: {e}")
    
    bpy.ops.object.mode_set(mode='OBJECT')


def rename_uv_layer(mesh_obj, new_name="UVMap"):
    """UV layer'ı standart isme rename."""
    if not mesh_obj.data.uv_layers:
        return False
    
    active = mesh_obj.data.uv_layers.active
    if active and active.name != new_name:
        # Aynı isimde yoksa rename
        if new_name not in [u.name for u in mesh_obj.data.uv_layers]:
            active.name = new_name
            return True
    return False


def measure_utilization(mesh_obj):
    """UV space utilization tahmini."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    uv_layer = bm.loops.layers.uv.active
    
    if uv_layer is None:
        bpy.ops.object.mode_set(mode='OBJECT')
        return 0.0
    
    total_face_uv_area = 0.0
    
    for face in bm.faces:
        loops = list(face.loops)
        if len(loops) < 3:
            continue
        # Fan triangulation
        uv0 = Vector(loops[0][uv_layer].uv)
        for i in range(1, len(loops) - 1):
            uv1 = Vector(loops[i][uv_layer].uv)
            uv2 = Vector(loops[i + 1][uv_layer].uv)
            e1 = uv1 - uv0
            e2 = uv2 - uv0
            cross = abs(e1.x * e2.y - e1.y * e2.x)
            total_face_uv_area += 0.5 * cross
    
    bpy.ops.object.mode_set(mode='OBJECT')
    return min(1.0, total_face_uv_area)


def count_uv_islands(mesh_obj):
    """Tahmini island count."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    
    # Built-in olmayabilir; alternative: seam count + 1 tahmini
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    seam_count = sum(1 for e in bm.edges if e.seam)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Çok kaba tahmin
    return max(1, seam_count // 12)


def main():
    args = parse_args()
    
    budget = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    
    mesh_obj = find_mesh()
    if mesh_obj is None:
        print("❌ Mesh yok", file=sys.stderr)
        sys.exit(1)
    
    print(f"[uv] Mesh: {mesh_obj.name} ({len(mesh_obj.data.vertices)} vert)")
    
    # Seam marking
    print("[uv] Seam'ler işaretleniyor...")
    sym_seams = mark_symmetry_seam(mesh_obj)
    belly_seams = mark_belly_seam(mesh_obj)
    total_seams = sym_seams + belly_seams
    print(f"  ✓ {total_seams} seam (sym {sym_seams} + belly {belly_seams})")
    
    # Unwrap
    if args.method == "marked_seams" and total_seams > 0:
        print("[uv] Marked seam unwrap...")
        unwrap_with_seams(mesh_obj)
    else:
        print(f"[uv] Smart UV Project (angle {args.angle_limit}°)...")
        smart_uv_project(mesh_obj, args.angle_limit, args.island_margin)
    
    # Pack
    print(f"[uv] Pack islands (margin {args.island_margin})...")
    pack_islands(mesh_obj, margin=args.island_margin / 3)
    
    # Rename UV layer
    renamed = rename_uv_layer(mesh_obj, "UVMap")
    if renamed:
        print("  ✓ UV layer rename → UVMap")
    
    # Measurements
    utilization = measure_utilization(mesh_obj)
    island_count = count_uv_islands(mesh_obj)
    
    print(f"[uv] UV space utilization: {utilization*100:.1f}%")
    print(f"[uv] Island count (approx): {island_count}")
    
    # Manifest
    manifest = {
        "manifest_version": "1.0",
        "uv_layer_name": "UVMap",
        "method_used": args.method,
        "seam_count": total_seams,
        "island_count_approx": island_count,
        "uv_space_utilization": utilization,
        "angle_limit": args.angle_limit,
        "island_margin": args.island_margin,
        "generated_by": "P06_uv_cartographer",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_path = output_path.with_suffix('.uv_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(f"[uv] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print("[uv] ✅ Tamamlandı")


if __name__ == "__main__":
    main()
