"""
Stage 3 v13 — Reference-match QA contact sheet.

User provided AAA mouse rig reference with specific visual style:
  - Spine/Torso = YELLOW
  - Front Legs = PURPLE
  - Hind Legs = GREEN
  - Tail = ORANGE
  - Face/Ear = CYAN

  - Mesh rendered SEMI-TRANSPARENT (X-ray style)
  - Bones VISIBLE through mesh
  - 9-panel layout: 1.side full, 2.front, 3.top, 4.3/4,
    5.head/face, 6.ear, 7.chest+front, 8.pelvis+hind, 9.tail

This file uses the v12 rig (structurally OK per audit) and renders the
contact sheet in the reference's visual style.

Usage:
    blender --background --python fare/scripts/stage3_qa_v13.py
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "out", "qa_v13_reference_match")
os.makedirs(OUT_DIR, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import rig_mouse_v12 as v12


def log(m): print(f"[qa13] {m}", flush=True)


# REFERENCE color palette (from user's AAA guide image)
REF_COLOR = {
    "spine":    (0.95, 0.85, 0.15, 1.0),   # YELLOW — torso/spine
    "front":    (0.55, 0.35, 0.85, 1.0),   # PURPLE — front legs
    "back":     (0.20, 0.85, 0.30, 1.0),   # GREEN — hind legs
    "tail":     (0.95, 0.55, 0.15, 1.0),   # ORANGE — tail
    "face":     (0.15, 0.85, 0.90, 1.0),   # CYAN — face/ears
    "neutral":  (0.65, 0.65, 0.65, 1.0),
}


def build():
    v12.reset_scene()
    v12.import_glb(v12.SRC)
    tripo = v12.extract_tripo_skeleton()
    mesh = v12.cleanup_keep_mesh_only()
    arm, meta = v12.build_rig(tripo, mesh)
    v12.setup_pose_rigging(arm, meta, tripo, mesh)
    return arm, mesh, meta


def categorize(name):
    """Match reference color legend exactly."""
    # Tail first (overlapping with spine prefix)
    if name.startswith("tail_") or name == "sacrum":
        return "tail"
    # Face/ears
    if name.startswith(("ear_", "eye_", "jaw", "snout", "nose", "cheek",
                          "whisker", "upper_lip", "lower_lip")):
        return "face"
    if name in ("head", "skull"): return "face"
    # Front legs
    if any(k in name for k in ("scapula", "upper_front_leg", "lower_front_leg",
                                  "front_paw", "front_toes", "wrist_L", "wrist_R")):
        return "front"
    # Back legs
    if any(k in name for k in ("hip_", "thigh", "shin", "back_paw",
                                  "back_toes", "ankle_L", "ankle_R")):
        return "back"
    # Spine/torso (everything else body)
    if any(k in name for k in ("cervical", "thoracic", "lumbar", "chest",
                                  "neck_", "pelvis", "spine_", "ribcage",
                                  "sternum", "belly", "COG", "root")):
        return "spine"
    return "neutral"


def make_mat(name, rgba):
    m = bpy.data.materials.get(name)
    if m is None: m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = rgba
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        try: bsdf.inputs["Roughness"].default_value = 0.3
        except KeyError: pass
        try: bsdf.inputs["Metallic"].default_value = 0.0
        except KeyError: pass
    return m


def setup_render(res=1280):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 0.75)
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.display.shading.cavity_type = 'BOTH'
    sc.display.shading.curvature_ridge_factor = 1.0
    sc.display.shading.curvature_valley_factor = 1.0
    sc.display.shading.show_object_outline = True
    # X-RAY mode for transparent mesh (so bones are visible through it)
    sc.display.shading.show_xray = True
    sc.display.shading.xray_alpha = 0.35
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.08, 0.09, 0.12, 1.0)


def add_camera(name, loc, look_at, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cam = bpy.data.objects.new(name, cd)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new(f"{name}_tgt", None); tgt.location = look_at
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam


def render_at(cam, path):
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)


def build_visualizer(arm, meta):
    """Render only DEF bones with reference-matched colors."""
    log("Building bone visualizers (reference color palette)")
    mw = arm.matrix_world
    mats = {cat: make_mat(f"refmat_{cat}", rgba) for cat, rgba in REF_COLOR.items()}
    objs = []
    for b in arm.data.bones:
        m = meta.get(b.name, {})
        if m.get("role") not in ("DEF",): continue
        cat = categorize(b.name)
        h = mw @ b.head_local; t = mw @ b.tail_local
        length = (t - h).length
        if length < 1e-5: continue
        # Thicker bones for important regions
        r_mul = 1.4 if cat in ("front", "back") else 1.2
        radius = max(length * 0.06, 0.004) * r_mul
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius,
                                             depth=length, location=(0,0,0))
        obj = bpy.context.object
        obj.name = f"VIS_{b.name}"
        direction = (t - h).normalized()
        rq = Vector((0, 0, 1)).rotation_difference(direction)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = rq
        obj.location = h + (t - h) * 0.5
        obj.data.materials.append(mats[cat])
        objs.append(obj)
        # Joint sphere
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius * 1.3, location=h,
                                              segments=12, ring_count=8)
        s = bpy.context.object
        s.name = f"VISJ_{b.name}"
        s.data.materials.append(mats[cat])
        objs.append(s)
    log(f"  {len(objs)} visualizer parts")
    return objs


def main():
    arm, mesh, meta = build()
    log(f"Rig: {len(arm.data.bones)} bones")
    setup_render(res=1280)

    # AABB world space
    mw = mesh.matrix_world
    xs=[];ys=[];zs=[]
    for v in mesh.data.vertices:
        wp = mw @ v.co
        xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    d = size * 1.3
    center = (cx, cy, cz)

    # Get anatomical landmarks for close-up cameras
    def bone_pos(name, end="head"):
        b = arm.data.bones.get(name)
        if not b: return Vector(center)
        return mw @ (b.head_local if end == "head" else b.tail_local)

    chest_p = bone_pos("thoracic_01")
    pelvis_p = bone_pos("pelvis")
    head_p = bone_pos("head", "tail")
    ear_p = bone_pos("ear_L_base")
    front_paw_p = bone_pos("front_paw_L", "tail")
    back_paw_p = bone_pos("back_paw_L", "tail")
    tail_mid_p = bone_pos("tail_14")
    sacrum_p = bone_pos("sacrum")

    # 9-panel cameras matching reference layout
    cams = {
        "1_side_full":  add_camera("c_side",  (cx + d, cy, cz + size*0.05), center),
        "2_front":      add_camera("c_front", (cx, cy - d, cz + size*0.05), center),
        "3_top":        add_camera("c_top",   (cx, cy, cz + d * 0.7), center, lens=45),
        "4_three_quarter": add_camera("c_34", (cx + d*0.7, cy - d*0.7, cz + size*0.4), center),
        "5_head_face":  add_camera("c_hf",
                                    head_p + Vector((size*0.25, size*0.20, size*0.10)),
                                    head_p, lens=70),
        "6_ear":        add_camera("c_ear",
                                    ear_p + Vector((size*0.18, size*0.15, size*0.10)),
                                    ear_p, lens=80),
        "7_chest_front_leg": add_camera("c_cfl",
                                          chest_p + Vector((size*0.35, -size*0.20, size*0.10)),
                                          (chest_p + front_paw_p) * 0.5, lens=60),
        "8_pelvis_hind_leg": add_camera("c_phl",
                                          pelvis_p + Vector((size*0.35, size*0.20, size*0.10)),
                                          (pelvis_p + back_paw_p) * 0.5, lens=60),
        "9_tail":       add_camera("c_tail",
                                    sacrum_p + Vector((size*0.35, size*0.10, size*0.10)),
                                    tail_mid_p, lens=55),
    }

    # PASS 1: mesh-only baseline (no bones)
    log("PASS 1: mesh-only baseline")
    for name, cam in cams.items():
        render_at(cam, os.path.join(OUT_DIR, f"mesh_{name}.png"))

    # PASS 2: mesh + bones with X-RAY transparency (REFERENCE STYLE)
    log("PASS 2: X-ray overlay with reference colors")
    vis = build_visualizer(arm, meta)
    for name, cam in cams.items():
        render_at(cam, os.path.join(OUT_DIR, f"xray_{name}.png"))
        log(f"  → xray_{name}.png")

    # PASS 3: skeleton-only (mesh removed) — full color skeleton view
    log("PASS 3: skeleton-only (mesh hidden)")
    # Switch off x-ray since mesh is gone
    bpy.context.scene.display.shading.show_xray = False
    bpy.data.objects.remove(mesh, do_unlink=True)
    for name, cam in cams.items():
        render_at(cam, os.path.join(OUT_DIR, f"skel_{name}.png"))
        log(f"  → skel_{name}.png")

    log("DONE")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc()
        sys.exit(1)
