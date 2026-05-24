"""
Stage 6 — isolated pose-test + leak audit.

Loads mouse_v16.blend, applies ONE bone pose at a time, renders, and measures
how far vertices OUTSIDE the expected region move (weight-bleed = leak).
GATE: leak displacement below threshold for every test.
"""

import bpy, os, sys, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as L
from mouse_rig_lib import region_of_vertex, detect_landmarks

BLEND = os.path.join(L.OUT_DIR, "mouse_v16.blend")
OUT = os.path.join(L.OUT_DIR, "qa_posetest")
os.makedirs(OUT, exist_ok=True)

def log(m): print(f"[pt] {m}", flush=True)


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x = 700; sc.render.resolution_y = 560
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.display.shading.show_object_outline = True
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.12,0.13,0.15,1.0)


def add_cam(name, loc, look):
    cd = bpy.data.cameras.new(name); cd.lens = 55
    cam = bpy.data.objects.new(name, cd); cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new(name+"_t", None); tgt.location = look
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO'); c.target = tgt
    c.track_axis='TRACK_NEGATIVE_Z'; c.up_axis='UP_Y'
    return cam


def eval_positions(mesh):
    """World-space evaluated vertex positions (after armature deform)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = mesh.evaluated_get(dg)
    mw = mesh.matrix_world
    return [mw @ v.co for v in me.data.vertices]


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    mesh = next(o for o in bpy.data.objects if o.type=='MESH')
    arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
    lm = detect_landmarks(mesh)
    setup_render()

    # rest positions + region tag per vertex
    bpy.context.scene.frame_set(0)
    rest = eval_positions(mesh)
    regions = [region_of_vertex(p, lm) for p in rest]

    # camera
    xs=[p.x for p in rest]; ys=[p.y for p in rest]; zs=[p.z for p in rest]
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
    size=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)); d=size*1.3
    cam_side = add_cam("side",(cx+d,cy,cz+size*0.05),(cx,cy,cz))
    cam_persp= add_cam("persp",(cx+d*0.7,cy-d*0.7,cz+size*0.4),(cx,cy,cz))
    sc = bpy.context.scene

    # rest render
    for nm,cam in (("side",cam_side),("persp",cam_persp)):
        sc.camera = cam
        sc.render.filepath = os.path.join(OUT, f"rest_{nm}.png")
        bpy.ops.render.render(write_still=True)
    log("rest rendered")

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    pb = arm.pose.bones

    # Pose tests: (bone, axis_deg, expected_regions, label)
    tests = [
        ("femur_L",   ('X', 35),  {"BL"},        "thigh_L_swing"),
        ("femur_R",   ('X', 35),  {"BR"},        "thigh_R_swing"),
        ("humerus_L", ('X', 30),  {"FL"},        "arm_L_swing"),
        ("jaw_base",  ('X', 25),  {"head"},      "jaw_open"),
        ("tail_10",   ('Z', 40),  {"tail"},      "tail_curl"),
        ("whisker_pad_L",('Z',30),{"head"},      "whisker_move"),
    ]

    def reset_pose():
        for b in pb:
            b.rotation_mode='XYZ'; b.rotation_euler=(0,0,0)
            b.location=(0,0,0); b.scale=(1,1,1)

    report = []
    for bone, (axis, deg), exp, label in tests:
        reset_pose()
        if bone not in pb:
            log(f"  SKIP {label}: bone {bone} missing"); continue
        b = pb[bone]; b.rotation_mode='XYZ'
        r = math.radians(deg)
        b.rotation_euler = (r if axis=='X' else 0,
                            r if axis=='Y' else 0,
                            r if axis=='Z' else 0)
        bpy.context.view_layer.update()
        posed = eval_positions(mesh)
        # leak: max displacement among verts NOT in expected region (and not head-adjacent body)
        leak = 0.0; leak_region={}
        moved_in = 0
        for i,(rp,pp) in enumerate(zip(rest, posed)):
            disp = (pp-rp).length
            if regions[i] in exp:
                if disp > 0.002: moved_in += 1
            else:
                if disp > leak:
                    leak = disp
                if disp > 0.01:
                    leak_region[regions[i]] = leak_region.get(regions[i],0)+1
        report.append((label, moved_in, leak, leak_region))
        # render
        sc.camera = cam_persp
        sc.render.filepath = os.path.join(OUT, f"pose_{label}.png")
        bpy.ops.render.render(write_still=True)
        log(f"  {label}: moved_in_region={moved_in}, max_leak={leak*1000:.1f}mm, "
            f"leak_regions={leak_region}")

    reset_pose()
    bpy.ops.object.mode_set(mode='OBJECT')

    log("=== GATE SUMMARY ===")
    LEAK_THRESH = 0.015  # 15mm — beyond this = visible weight bleed
    ok = True
    for label, mi, leak, lr in report:
        status = "PASS" if leak < LEAK_THRESH else "FAIL"
        if leak >= LEAK_THRESH: ok = False
        log(f"  {label}: {status} (leak={leak*1000:.1f}mm, moved_in={mi})")
    log(f"GATE posetest: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback; traceback.print_exc(); sys.exit(1)
