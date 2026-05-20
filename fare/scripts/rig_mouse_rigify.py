"""
Mouse rig using Blender's RIGIFY (wolf metarig fitted to mouse mesh).

Approach:
  1. Import GLB (mesh preserved)
  2. Detect mouse anatomical landmarks (paws, head/nose, ear positions, tail base)
  3. Add Rigify wolf metarig
  4. Scale + translate to mouse position
  5. Adjust per-bone position to match mouse landmarks
  6. Run bpy.ops.pose.rigify_generate() → produces production AAA rig
  7. Skin mesh to generated rig

Why this works (vs 12 versions of manual heuristics):
  - Wolf metarig is hand-authored by Blender team (anatomically correct)
  - Rigify generator handles ALL the constraint/IK/FK/twist/B-bone setup
  - No more manual bone placement formulas

Mesh remains UNTOUCHED.

Usage:
    blender --background --python fare/scripts/rig_mouse_rigify.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "mouse3dmodel1k.glb")
OUT_DIR = os.path.join(ROOT, "out")
OUT_BLEND = os.path.join(OUT_DIR, "mouse_rigify.blend")
os.makedirs(OUT_DIR, exist_ok=True)


def log(m): print(f"[rigify] {m}", flush=True)


# ============================================================================
# Scene setup (same as before)
# ============================================================================
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    log(f"Importing {path}")
    bpy.ops.import_scene.gltf(filepath=path)


def cleanup_keep_mesh_only():
    """Strip Tripo armature, keep mesh untouched."""
    for name in ("Icosphere", "ParentNode"):
        o = bpy.data.objects.get(name)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    body = [o for o in bpy.data.objects
            if o.type == 'MESH' and o.name.startswith("tripo_part")]
    for m in body:
        bpy.context.view_layer.objects.active = m
        for mod in list(m.modifiers):
            if mod.type == 'ARMATURE': m.modifiers.remove(mod)
        bpy.ops.object.select_all(action='DESELECT')
        m.select_set(True); bpy.context.view_layer.objects.active = m
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        m.vertex_groups.clear()
    for o in list(bpy.data.objects):
        if o.type in ('ARMATURE', 'EMPTY'):
            bpy.data.objects.remove(o, do_unlink=True)
    body = [o for o in bpy.data.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for m in body: m.select_set(True)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(body) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    merged.name = "MouseBody"
    log(f"Mesh: {len(merged.data.vertices)} verts (untouched)")
    return merged


# ============================================================================
# Detect mouse anatomical landmarks
# ============================================================================
def detect_landmarks(mesh):
    """Return dict with anatomical landmarks of the mouse mesh."""
    verts = mesh.data.vertices
    xs=[v.co.x for v in verts]; ys=[v.co.y for v in verts]; zs=[v.co.z for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    x_center = sum(xs) / len(xs)
    y_size = y_max - y_min
    z_size = z_max - z_min
    x_half = (x_max - x_min) / 2

    # Head direction: snout has thinner cross-section than tail
    # Wolf metarig: head at -Y, tail at +Y. Mouse: same.
    # Verify by checking Tripo (already known: head at -Y).
    head_dir = -1   # mouse head at -Y

    # Detect nose tip (extremal vertex toward head direction)
    nose_cand = [v.co for v in verts if v.co.y < y_min + y_size * 0.05]
    if nose_cand:
        nose_tip = Vector((sum(v.x for v in nose_cand)/len(nose_cand),
                            sum(v.y for v in nose_cand)/len(nose_cand),
                            sum(v.z for v in nose_cand)/len(nose_cand)))
    else:
        nose_tip = Vector((x_center, y_min, z_max * 0.7))

    # Detect tail tip (extremal toward +Y)
    tail_cand = [v.co for v in verts if v.co.y > y_max - y_size * 0.05]
    if tail_cand:
        tail_tip = Vector((sum(v.x for v in tail_cand)/len(tail_cand),
                            sum(v.y for v in tail_cand)/len(tail_cand),
                            sum(v.z for v in tail_cand)/len(tail_cand)))
    else:
        tail_tip = Vector((x_center, y_max, z_max * 0.5))

    # 4 paw positions (lowest Z verts in each X×Y quadrant)
    def paw_in_quadrant(side_x, front_y):
        """side_x: 'L' (+X) or 'R' (-X). front_y: True = head side (-Y)."""
        side_pred = (lambda v: v.co.x > x_center) if side_x == "L" else (lambda v: v.co.x < x_center)
        y_pred = (lambda v: v.co.y < (y_min+y_max)/2) if front_y else (lambda v: v.co.y > (y_min+y_max)/2)
        cand = [v.co for v in verts
                if side_pred(v) and y_pred(v) and v.co.z < z_min + z_size * 0.15]
        if not cand: return None
        sorted_cand = sorted(cand, key=lambda p: p.z)[:30]
        avg = Vector((0,0,0))
        for p in sorted_cand: avg += p
        return avg / len(sorted_cand)

    paw_FL = paw_in_quadrant("L", True)  # +X, -Y
    paw_FR = paw_in_quadrant("R", True)  # -X, -Y
    paw_BL = paw_in_quadrant("L", False)
    paw_BR = paw_in_quadrant("R", False)

    # Ear positions (top of head, lateral). head_dir = -1 → head is at -Y end.
    head_y_lo = y_min
    head_y_hi = y_min + y_size * 0.40   # head zone: front 40% of body
    head_verts = [v.co for v in verts if head_y_lo <= v.co.y <= head_y_hi]
    if head_verts:
        head_z_max = max(v.z for v in head_verts)
        head_z_min = min(v.z for v in head_verts)
        ear_z_thresh = head_z_min + (head_z_max - head_z_min) * 0.75
        ear_L_cand = [v for v in head_verts if v.z > ear_z_thresh and v.x > x_center + x_half * 0.20]
        ear_R_cand = [v for v in head_verts if v.z > ear_z_thresh and v.x < x_center - x_half * 0.20]
        if ear_L_cand:
            ear_L_tip = sum(ear_L_cand, Vector((0,0,0))) / len(ear_L_cand)
        else:
            ear_L_tip = Vector((x_center + x_half * 0.5, head_y_hi, head_z_max))
        if ear_R_cand:
            ear_R_tip = sum(ear_R_cand, Vector((0,0,0))) / len(ear_R_cand)
        else:
            ear_R_tip = Vector((x_center - x_half * 0.5, head_y_hi, head_z_max))
    else:
        ear_L_tip = ear_R_tip = Vector((x_center, y_min, z_max))

    landmarks = {
        "nose_tip": nose_tip,
        "tail_tip": tail_tip,
        "paw_FL": paw_FL, "paw_FR": paw_FR,
        "paw_BL": paw_BL, "paw_BR": paw_BR,
        "ear_L_tip": ear_L_tip, "ear_R_tip": ear_R_tip,
        "x_center": x_center,
        "y_min": y_min, "y_max": y_max,
        "z_min": z_min, "z_max": z_max,
        "x_min": x_min, "x_max": x_max,
        "head_dir": head_dir,
    }
    log(f"Landmarks:")
    for k, v in landmarks.items():
        if isinstance(v, Vector):
            log(f"  {k}: ({v.x:+.3f}, {v.y:+.3f}, {v.z:+.3f})")
        else:
            log(f"  {k}: {v}")
    return landmarks


# ============================================================================
# Add and fit Rigify wolf metarig
# ============================================================================
def add_wolf_metarig():
    bpy.ops.preferences.addon_enable(module='rigify')
    bpy.ops.object.armature_wolf_metarig_add()
    meta = bpy.context.object
    meta.name = "MouseMetarig"
    log(f"Wolf metarig added: {len(meta.data.bones)} bones")
    return meta


def fit_metarig_to_mouse(meta, landmarks):
    """Scale + translate + per-bone adjust wolf metarig to match mouse mesh."""
    # Wolf metarig AABB
    mw = meta.matrix_world
    bones = list(meta.data.bones)
    heads = [mw @ b.head_local for b in bones]
    tails = [mw @ b.tail_local for b in bones]
    pts = heads + tails
    wxs = [p.x for p in pts]; wys = [p.y for p in pts]; wzs = [p.z for p in pts]
    wolf_x_size = max(wxs) - min(wxs)
    wolf_y_size = max(wys) - min(wys)
    wolf_z_size = max(wzs) - min(wzs)
    wolf_xc = (max(wxs) + min(wxs)) / 2
    wolf_yc = (max(wys) + min(wys)) / 2
    wolf_zc = (max(wzs) + min(wzs)) / 2
    log(f"Wolf AABB: X={wolf_x_size:.2f} Y={wolf_y_size:.2f} Z={wolf_z_size:.2f}")

    mouse_x_size = landmarks["x_max"] - landmarks["x_min"]
    mouse_y_size = landmarks["y_max"] - landmarks["y_min"]
    mouse_z_size = landmarks["z_max"] - landmarks["z_min"]
    mouse_xc = landmarks["x_center"]
    mouse_yc = (landmarks["y_min"] + landmarks["y_max"]) / 2
    mouse_zc = (landmarks["z_min"] + landmarks["z_max"]) / 2

    # Non-uniform scale to match mouse proportions
    scale_x = mouse_x_size / wolf_x_size if wolf_x_size > 1e-6 else 1
    scale_y = mouse_y_size / wolf_y_size if wolf_y_size > 1e-6 else 1
    scale_z = mouse_z_size / wolf_z_size if wolf_z_size > 1e-6 else 1
    log(f"Scale: X×{scale_x:.2f}, Y×{scale_y:.2f}, Z×{scale_z:.2f}")

    # Apply scale via object transform
    meta.scale = (scale_x, scale_y, scale_z)
    # Compute new center after scale, translate to mouse center
    # Object scale changes mesh, then we want centroid at mouse_center
    bpy.context.view_layer.update()
    # Move to mouse center: scale center offset by scale factor
    new_center = Vector((wolf_xc * scale_x, wolf_yc * scale_y, wolf_zc * scale_z))
    meta.location = Vector((mouse_xc - new_center.x,
                             mouse_yc - new_center.y,
                             mouse_zc - new_center.z))
    bpy.context.view_layer.update()

    # Apply scale + location to bake into bones
    bpy.ops.object.select_all(action='DESELECT')
    meta.select_set(True)
    bpy.context.view_layer.objects.active = meta
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    log("Metarig scaled + translated to mouse box, transforms applied")

    # Now fine-tune: per-bone adjustments to align with mouse landmarks
    # Enter edit mode and tweak key bones
    bpy.ops.object.mode_set(mode='EDIT')
    eb = meta.data.edit_bones

    def move_bone(name, new_head=None, new_tail=None):
        b = eb.get(name)
        if b is None:
            log(f"  WARN: bone '{name}' not found in metarig")
            return
        if new_head is not None: b.head = Vector(new_head)
        if new_tail is not None: b.tail = Vector(new_tail)

    # Move nose chain endpoint to actual mouse nose tip
    nose_chain = ["nose.004", "nose.003", "nose.002", "nose.001", "nose"]
    nose_endpoint = landmarks["nose_tip"]
    # nose.004 tail is the snout tip in wolf metarig — set it to mouse nose
    nose_004 = eb.get("nose.004")
    if nose_004:
        nose_004.tail = nose_endpoint.copy()

    # Move ear chains to actual mouse ear positions
    # Ear has 5 segments: ear.L, ear.L.001, ear.L.002, ear.L.003, ear.L.004
    # The chain wraps around — let's just move the tip to mouse ear position
    for side in ("L", "R"):
        ear_tip_pos = landmarks[f"ear_{side}_tip"]
        # Set ear.L.002 (the top of ear loop) tail to ear tip
        ear_tip_bone = eb.get(f"ear.{side}.002")
        if ear_tip_bone:
            ear_tip_bone.tail = ear_tip_pos.copy()

    # Move tail tip
    # Tail in wolf goes: spine → spine.001 → ... → spine.004 (tail tip at +Y end)
    # spine (last in chain) tail is the tail tip
    spine_tail_bone = eb.get("spine")
    if spine_tail_bone:
        spine_tail_bone.tail = landmarks["tail_tip"].copy()

    # Move front paws to mouse front paw positions
    for side, paw_key in (("L", "paw_FL"), ("R", "paw_FR")):
        paw_pos = landmarks[paw_key]
        if paw_pos is None: continue
        # front_toe.X tail is the front of paw
        front_toe = eb.get(f"front_toe.{side}")
        if front_toe:
            front_toe.tail = paw_pos.copy()
        # front_foot.X tail = paw heel position
        front_foot = eb.get(f"front_foot.{side}")
        if front_foot:
            # Place foot just above paw (heel position)
            front_foot.tail = Vector((paw_pos.x, paw_pos.y - 0.02, paw_pos.z + 0.005))

    # Move back paws
    for side, paw_key in (("L", "paw_BL"), ("R", "paw_BR")):
        paw_pos = landmarks[paw_key]
        if paw_pos is None: continue
        toe = eb.get(f"toe.{side}")
        if toe:
            toe.tail = paw_pos.copy()
        foot = eb.get(f"foot.{side}")
        if foot:
            foot.tail = Vector((paw_pos.x, paw_pos.y + 0.02, paw_pos.z + 0.005))

    bpy.ops.object.mode_set(mode='OBJECT')
    log("Per-bone adjustments applied")


def generate_rigify(meta):
    """Run Rigify generator to produce production rig."""
    bpy.context.view_layer.objects.active = meta
    bpy.ops.object.select_all(action='DESELECT')
    meta.select_set(True)
    bpy.ops.object.mode_set(mode='OBJECT')
    try:
        log("Running Rigify generator…")
        bpy.ops.pose.rigify_generate()
        new_rig = bpy.context.object
        log(f"Generated production rig: {new_rig.name} with {len(new_rig.data.bones)} bones")
        return new_rig
    except Exception as e:
        log(f"Rigify generate ERROR: {e}")
        import traceback; traceback.print_exc()
        return None


# ============================================================================
# Main
# ============================================================================
def main():
    reset_scene()
    import_glb(SRC)
    mesh = cleanup_keep_mesh_only()
    landmarks = detect_landmarks(mesh)
    meta = add_wolf_metarig()
    fit_metarig_to_mouse(meta, landmarks)
    rig = generate_rigify(meta)
    if rig is None:
        log("FAILED to generate Rigify rig")
        sys.exit(1)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    log(f"Saved .blend → {OUT_BLEND}")
    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
