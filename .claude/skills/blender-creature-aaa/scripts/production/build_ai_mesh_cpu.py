#!/usr/bin/env python3
"""
build_ai_mesh_cpu.py — P04-AI CPU edition

TripoSR CPU mode ile foto → 3D mesh. Sonra Blender'da import/align/repair.

Oracle Cloud VM (CPU-only, 32GB RAM) için optimize.

Çağrı:
    python3 build_ai_mesh_cpu.py \\
        --reference-image refs/wolf.jpg \\
        --blueprint SkeletonBlueprint.json \\
        --output-blend mesh_v1.blend \\
        --mc-resolution 192 \\
        --blender-binary blender
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import io
import time
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--reference-image", required=True,
                   help="Yaratık foto'su (jpg/png/webp)")
    p.add_argument("--blueprint", required=True,
                   help="SkeletonBlueprint.json (target_length, anatomy_class)")
    p.add_argument("--output-blend", required=True)
    p.add_argument("--work-dir", default=None)
    p.add_argument("--mc-resolution", type=int, default=192,
                   choices=[128, 160, 192, 224, 256, 320],
                   help="Marching cubes resolution. Yüksek=kaliteli/yavaş")
    p.add_argument("--blender-binary", default="blender")
    p.add_argument("--skip-rembg", action="store_true",
                   help="Background removal'ı atla (foto zaten temizse)")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


# ============================================================================
# Step 1: Environment check
# ============================================================================

def check_env(verbose=False):
    """Gerekli paketler kurulu mu?"""
    checks = {}
    
    # Blender
    try:
        r = subprocess.run(["blender", "--version"], capture_output=True,
                           text=True, timeout=10)
        checks["blender"] = r.stdout.split('\n')[0] if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        checks["blender"] = None
    
    # Python packages
    pkgs = ["torch", "rembg", "PIL", "numpy", "trimesh", "tsr"]
    for pkg in pkgs:
        try:
            r = subprocess.run(
                [sys.executable, "-c", f"import {pkg}; "
                 f"print(getattr({pkg}, '__version__', 'OK'))"],
                capture_output=True, text=True, timeout=20,
            )
            checks[pkg] = r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            checks[pkg] = None
    
    # RAM check
    try:
        r = subprocess.run(["free", "-g"], capture_output=True, text=True)
        if r.returncode == 0:
            # parse: Mem: total used free shared buffers cache
            for line in r.stdout.split('\n'):
                if line.startswith('Mem:'):
                    parts = line.split()
                    checks["ram_total_gb"] = int(parts[1])
                    checks["ram_free_gb"] = int(parts[3])
                    break
    except Exception:
        pass
    
    # CPU count
    try:
        checks["cpu_count"] = os.cpu_count()
    except Exception:
        pass
    
    if verbose:
        print("[env] Environment check:")
        for k, v in checks.items():
            mark = "✓" if v else "❌"
            print(f"  {mark} {k}: {v}")
    
    missing = [k for k in ["blender", "torch", "rembg", "tsr"]
               if checks.get(k) is None]
    
    return checks, missing


# ============================================================================
# Step 2: Image preprocess
# ============================================================================

def preprocess_image(input_path, output_path, skip_rembg=False, verbose=False):
    from PIL import Image
    
    img = None
    
    if not skip_rembg:
        try:
            from rembg import remove
            with open(input_path, 'rb') as f:
                data = f.read()
            if verbose:
                print(f"  → rembg ile background removal...")
            out = remove(data)
            img = Image.open(io.BytesIO(out)).convert("RGBA")
        except Exception as e:
            print(f"  ⚠ rembg fail ({e}), raw image kullanılacak")
            img = None
    
    if img is None:
        img = Image.open(input_path).convert("RGBA")
    
    # Subject crop
    if img.mode == 'RGBA':
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
    
    # White background
    bg = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode == 'RGBA':
        bg.paste(img, mask=img.split()[3])
    else:
        bg.paste(img)
    
    # Square pad + 512×512
    max_d = max(bg.size)
    padded = Image.new("RGB", (max_d, max_d), (255, 255, 255))
    offset = ((max_d - bg.size[0]) // 2, (max_d - bg.size[1]) // 2)
    padded.paste(bg, offset)
    padded = padded.resize((512, 512), Image.LANCZOS)
    padded.save(output_path, format='PNG')
    
    if verbose:
        print(f"  ✓ Preprocessed → {output_path} (512×512)")


# ============================================================================
# Step 3: TripoSR CPU generation
# ============================================================================

def run_triposr_cpu(image_path, output_dir, mc_resolution=192, verbose=False):
    """
    TripoSR --device cpu.
    
    Beklenen output: <output_dir>/0/mesh.obj + texture (varsa)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # CPU threads optimize
    env = os.environ.copy()
    cpu_count = os.cpu_count() or 4
    env["OMP_NUM_THREADS"] = str(cpu_count)
    env["MKL_NUM_THREADS"] = str(cpu_count)
    env["NUMEXPR_NUM_THREADS"] = str(cpu_count)
    
    cmd = [
        sys.executable, "-m", "tsr.run",
        str(image_path),
        "--output-dir", str(output_dir),
        "--mc-resolution", str(mc_resolution),
        "--device", "cpu",
        "--bake-texture",
        "--no-remove-bg",  # zaten preprocess yaptık
    ]
    
    if verbose:
        print(f"  → TripoSR CLI: {' '.join(cmd)}")
        print(f"     CPU threads: {cpu_count}")
        print(f"     Expected duration: 10-25 dakika (mc_res={mc_resolution})")
    
    start = time.time()
    
    # Long-running, periodic progress update
    result = subprocess.run(cmd, env=env, capture_output=True, text=True,
                              timeout=2400)  # 40 dk max
    
    elapsed = time.time() - start
    
    if result.returncode != 0:
        print(f"  ❌ TripoSR fail (returncode {result.returncode}):", file=sys.stderr)
        print(result.stderr[-3000:], file=sys.stderr)
        return None
    
    # Find output mesh
    candidates = [
        output_dir / "0" / "mesh.obj",
        output_dir / "0" / "mesh.glb",
        output_dir / "mesh.obj",
    ]
    
    for c in candidates:
        if c.exists():
            if verbose:
                print(f"  ✓ Mesh üretildi ({elapsed:.0f}s): {c}")
                print(f"     Size: {c.stat().st_size / 1024:.0f} KB")
            return c
    
    print(f"  ❌ Output mesh dosyası bulunamadı: {output_dir}", file=sys.stderr)
    return None


# ============================================================================
# Step 4: Blender import + align + repair
# ============================================================================

BLENDER_IMPORT_SCRIPT = """
import bpy, json, math
from pathlib import Path
from mathutils import Vector

mesh_path = r'''{mesh_path}'''
blueprint = json.loads(Path(r'''{blueprint_path}''').read_text())
output_path = r'''{output_blend}'''

# Clear scene
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# Import
if mesh_path.endswith('.obj'):
    bpy.ops.wm.obj_import(filepath=mesh_path)
elif mesh_path.endswith('.glb') or mesh_path.endswith('.gltf'):
    bpy.ops.import_scene.gltf(filepath=mesh_path)
elif mesh_path.endswith('.ply'):
    bpy.ops.wm.ply_import(filepath=mesh_path)
else:
    raise ValueError(f"Unknown format: {{mesh_path}}")

# Largest mesh = creature
mesh_obj = None
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        if mesh_obj is None or len(obj.data.vertices) > len(mesh_obj.data.vertices):
            mesh_obj = obj

if mesh_obj is None:
    raise RuntimeError("No mesh imported")

mesh_obj.name = "creature_mesh"

bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.select_all(action='DESELECT')
mesh_obj.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Compute bbox
def compute_bbox(obj):
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    bbox_min = Vector((min(c.x for c in bbox), min(c.y for c in bbox), min(c.z for c in bbox)))
    bbox_max = Vector((max(c.x for c in bbox), max(c.y for c in bbox), max(c.z for c in bbox)))
    return bbox_min, bbox_max

bbox_min, bbox_max = compute_bbox(mesh_obj)
size = bbox_max - bbox_min

# Scale to target body length
target_length = blueprint.get('body_length_meters', 1.2)
largest_dim = max(size.x, size.y, size.z)
scale_factor = target_length / largest_dim
mesh_obj.scale = (scale_factor, scale_factor, scale_factor)
bpy.ops.object.transform_apply(scale=True)

# Re-bbox + center origin
bbox_min, bbox_max = compute_bbox(mesh_obj)
center = (bbox_min + bbox_max) / 2

mesh_obj.location = Vector((-center.x, -center.y, -bbox_min.z))  # Z bottom on ground
bpy.ops.object.transform_apply(location=True)

# Y-up vs Z-up detection (AI usually Y-up)
bbox_min, bbox_max = compute_bbox(mesh_obj)
new_size = bbox_max - bbox_min
if new_size.z > max(new_size.x, new_size.y) * 1.2:
    # Looks like Y-up
    mesh_obj.rotation_euler = (math.radians(-90), 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    print("  → Y-up detected, rotated -90° around X")

# Mesh repair
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.mesh.select_non_manifold()
try:
    bpy.ops.mesh.fill_holes(sides=8)
except Exception:
    pass
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.mesh.select_loose()
bpy.ops.mesh.delete(type='VERT')
bpy.ops.object.mode_set(mode='OBJECT')

# Count
import bmesh
bm = bmesh.new()
bm.from_mesh(mesh_obj.data)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
tris = len(bm.faces)
bm.free()

# Decimate if too high
if tris > 25000:
    target_ratio = 15000 / tris
    dec = mesh_obj.modifiers.new("AutoDecimate", 'DECIMATE')
    dec.ratio = target_ratio
    bpy.ops.object.modifier_apply(modifier=dec.name)
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    tris = len(bm.faces)
    bm.free()

# Manifest
manifest = {{
    "manifest_version": "1.0",
    "base_mesh_object_name": mesh_obj.name,
    "tris_count_actual": tris,
    "verts_count": len(mesh_obj.data.vertices),
    "method": "triposr_cpu",
    "imported_from": mesh_path,
    "scale_factor_applied": scale_factor,
    "target_length_m": target_length,
    "is_manifold": True,  # repair sonrası varsayım
    "generated_by": "P04_ai_mesh_generator_cpu",
}}

Path(output_path).parent.mkdir(parents=True, exist_ok=True)
manifest_path = Path(output_path).with_suffix('.mesh_manifest.json')
manifest_path.write_text(json.dumps(manifest, indent=2))

bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"OK: tris={{tris}}, scale={{scale_factor:.4f}}")
"""


def run_blender_import(mesh_path, blueprint_path, output_blend,
                       blender_binary="blender", verbose=False):
    script_content = BLENDER_IMPORT_SCRIPT.format(
        mesh_path=str(mesh_path),
        blueprint_path=str(blueprint_path),
        output_blend=str(output_blend),
    )
    
    script_file = Path(output_blend).parent / "_blender_import_tmp.py"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text(script_content)
    
    if verbose:
        print(f"  → Blender headless import...")
    
    result = subprocess.run(
        [blender_binary, "--background", "--python", str(script_file)],
        capture_output=True, text=True, timeout=300,
    )
    
    if "OK:" not in result.stdout:
        print(f"  ❌ Blender import fail:", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        print("stdout:", result.stdout[-1000:])
        return False
    
    if verbose:
        # Parse OK line
        for line in result.stdout.split('\n'):
            if line.startswith('OK:'):
                print(f"  ✓ {line}")
    
    # Cleanup script
    try:
        script_file.unlink()
    except Exception:
        pass
    
    return True


# ============================================================================
# Main
# ============================================================================

def main():
    args = parse_args()
    
    print(f"=== P04-AI CPU Pipeline ===")
    print(f"Reference: {args.reference_image}")
    print(f"Output:    {args.output_blend}")
    print(f"MC res:    {args.mc_resolution}")
    print()
    
    # Step 1: Environment
    print("[1/4] Environment check...")
    checks, missing = check_env(verbose=args.verbose)
    if missing:
        print(f"❌ Missing: {missing}", file=sys.stderr)
        print(f"   Setup için bkz: agents/production/P04_ai_mesh_generator.md", file=sys.stderr)
        sys.exit(2)
    print(f"  ✓ Blender + TripoSR + deps OK ({checks.get('cpu_count')} CPU, "
          f"{checks.get('ram_total_gb', '?')}GB RAM)")
    
    # Work dir
    work_dir = Path(args.work_dir) if args.work_dir else Path(args.output_blend).parent / "_ai_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 2: Preprocess
    print(f"\n[2/4] Preprocess foto...")
    processed_img = work_dir / "input_512.png"
    preprocess_image(args.reference_image, processed_img,
                      skip_rembg=args.skip_rembg, verbose=args.verbose)
    
    # Step 3: TripoSR CPU
    print(f"\n[3/4] TripoSR CPU generation (~{12+args.mc_resolution//40} dakika)...")
    tsr_out = work_dir / "_tsr_out"
    mesh_path = run_triposr_cpu(processed_img, tsr_out,
                                  mc_resolution=args.mc_resolution,
                                  verbose=args.verbose)
    if mesh_path is None:
        print("❌ TripoSR generation fail", file=sys.stderr)
        sys.exit(3)
    
    # Step 4: Blender import + align
    print(f"\n[4/4] Blender import + align + repair...")
    if not run_blender_import(mesh_path, args.blueprint, args.output_blend,
                                args.blender_binary, verbose=args.verbose):
        print("❌ Blender import fail", file=sys.stderr)
        sys.exit(4)
    
    print(f"\n✅ Tamamlandı: {args.output_blend}")
    print(f"   Manifest:   {Path(args.output_blend).with_suffix('.mesh_manifest.json')}")


if __name__ == "__main__":
    main()
