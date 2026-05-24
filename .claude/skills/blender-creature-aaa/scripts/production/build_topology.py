#!/usr/bin/env python3
"""
build_topology.py — P05 Topology Surgeon

QuadriFlow / Instant Meshes / Decimate Planar zinciri ile retopology.
"""

import bpy
import bmesh
import json
import math
import shutil
import subprocess
import sys
import argparse
import tempfile
from pathlib import Path


def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser()
    p.add_argument("--budget", required=True)
    p.add_argument("--mesh-manifest", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--method", default="auto",
                   choices=["auto", "quadriflow", "instant_meshes", "decimate_planar"])
    p.add_argument("--target-ratio", type=float, default=0.5,
                   help="hedef tris = original × bu oran")
    return p.parse_args(argv)


def find_mesh():
    mesh = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            if mesh is None or len(obj.data.vertices) > len(mesh.data.vertices):
                mesh = obj
    return mesh


def count_topology(mesh_obj):
    """Tris/quad/ngon sayıları + quad ratio."""
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    tri = quad = ngon = 0
    for f in bm.faces:
        n = len(f.verts)
        if n == 3: tri += 1
        elif n == 4: quad += 1
        else: ngon += 1
    total = tri + quad + ngon
    bm.free()
    return {
        "tris": tri, "quads": quad, "ngons": ngon,
        "total_faces": total,
        "quad_ratio": quad / max(1, total),
        "verts": len(mesh_obj.data.vertices),
    }


def detect_method():
    """Hangi method mevcut?"""
    if shutil.which("instant-meshes") or shutil.which("Instant Meshes"):
        return "instant_meshes"
    # QuadriFlow Blender 4.x built-in
    if hasattr(bpy.ops.object, "quadriflow_remesh"):
        return "quadriflow"
    return "decimate_planar"


def retopo_quadriflow(mesh_obj, target_faces):
    """Blender built-in QuadriFlow."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    try:
        bpy.ops.object.quadriflow_remesh(
            target_faces=int(target_faces),
            use_paint_symmetry=True,
            smooth_normals=True,
            preserve_paint_mask=False,
            preserve_sharp=False,
            mode='FACES',
        )
        return True
    except Exception as e:
        print(f"  ⚠️ QuadriFlow fail: {e}")
        return False


def retopo_instant_meshes(mesh_obj, target_verts):
    """Instant Meshes external binary."""
    binary = shutil.which("instant-meshes") or shutil.which("Instant Meshes")
    if not binary:
        return False
    
    tmp_dir = Path(tempfile.mkdtemp(prefix="instant_meshes_"))
    in_path = tmp_dir / "in.obj"
    out_path = tmp_dir / "out.obj"
    
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    
    try:
        bpy.ops.wm.obj_export(
            filepath=str(in_path),
            export_selected_objects=True,
            export_materials=False,
        )
    except Exception as e:
        print(f"  ⚠️ OBJ export fail: {e}")
        return False
    
    try:
        result = subprocess.run(
            [binary, str(in_path), "-o", str(out_path),
             "-v", str(int(target_verts)),
             "-d", "-S", "0",  # deterministic, no smoothing
             "-p", "4"],  # quads
            capture_output=True, text=True, timeout=300,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  ⚠️ Instant Meshes fail: {e}")
        return False
    
    if result.returncode != 0 or not out_path.exists():
        print(f"  ⚠️ Instant Meshes returncode {result.returncode}")
        return False
    
    # Import sonucu
    old_name = mesh_obj.name
    old_matrix = mesh_obj.matrix_world.copy()
    bpy.data.objects.remove(mesh_obj, do_unlink=True)
    
    try:
        bpy.ops.wm.obj_import(filepath=str(out_path))
        new_obj = bpy.context.selected_objects[0]
        new_obj.name = old_name
        new_obj.matrix_world = old_matrix
    except Exception as e:
        print(f"  ⚠️ OBJ import fail: {e}")
        return False
    
    return True


def retopo_decimate_planar(mesh_obj, angle_limit_deg=10):
    """Düşük kalite fallback."""
    dec = mesh_obj.modifiers.new("DecimatePlanar", 'DECIMATE')
    dec.decimate_type = 'DISSOLVE'
    dec.angle_limit = math.radians(angle_limit_deg)
    
    bpy.context.view_layer.objects.active = mesh_obj
    try:
        bpy.ops.object.modifier_apply(modifier=dec.name)
        return True
    except Exception as e:
        print(f"  ⚠️ Decimate Planar fail: {e}")
        return False


def main():
    args = parse_args()
    
    budget = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    mesh_manifest = json.loads(Path(args.mesh_manifest).read_text(encoding='utf-8'))
    
    mesh_obj = find_mesh()
    if mesh_obj is None:
        print("❌ Mesh yok", file=sys.stderr)
        sys.exit(1)
    
    before = count_topology(mesh_obj)
    print(f"[topology] Before: {before['tris']} tris, {before['quads']} quads, "
          f"quad_ratio={before['quad_ratio']:.2f}")
    
    # Method
    method = args.method
    if method == "auto":
        method = detect_method()
    print(f"[topology] Method: {method}")
    
    target_tris = budget["polygon_budget"]["lod0_tris_target"]
    target_faces = int(target_tris * args.target_ratio)
    target_verts = int(before["verts"] * args.target_ratio)
    
    success = False
    
    if method == "instant_meshes":
        success = retopo_instant_meshes(mesh_obj, target_verts)
        if not success:
            print("  ⚠️ Instant Meshes fail, QuadriFlow fallback")
            mesh_obj = find_mesh()
            method = "quadriflow"
    
    if method == "quadriflow":
        success = retopo_quadriflow(mesh_obj, target_faces)
        if not success:
            print("  ⚠️ QuadriFlow fail, Decimate Planar fallback")
            method = "decimate_planar"
    
    if method == "decimate_planar":
        success = retopo_decimate_planar(mesh_obj)
    
    if not success:
        print("❌ Tüm retopo methodları fail", file=sys.stderr)
        sys.exit(2)
    
    mesh_obj = find_mesh()
    after = count_topology(mesh_obj)
    
    print(f"[topology] After: {after['tris']} tris, {after['quads']} quads, "
          f"quad_ratio={after['quad_ratio']:.2f}")
    
    # Manifest
    manifest = {
        "manifest_version": "1.0",
        "method_used": method,
        "before": before,
        "after": after,
        "vertex_count_before": before["verts"],
        "vertex_count_after": after["verts"],
        "improved_quad_ratio": after["quad_ratio"] > before["quad_ratio"],
        "warning_vertex_groups_lost": True,
        "generated_by": "P05_topology_surgeon",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_path = output_path.with_suffix('.topology_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(f"[topology] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print("[topology] ✅ Retopology tamamlandı")
    print("           ⚠️ Vertex groups silindi, P08 Skinner yeniden çalıştırılmalı")


if __name__ == "__main__":
    main()
