"""Render walk animation — 24 frames from side view + 1 perspective frame strip."""

import bpy, os
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(ROOT, "out", "mouse_walk.blend")
OUT = os.path.join(ROOT, "out", "qa_walk")
os.makedirs(OUT, exist_ok=True)

def log(m): print(f"[rw] {m}", flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = 800
sc.render.resolution_y = 600
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_cavity = True
sc.display.shading.show_object_outline = True
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.12, 0.13, 0.15, 1.0)

# Camera AABB
mw = mesh.matrix_world
xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    wp = mw @ v.co
    xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
d = size * 1.4

def add_cam(name, loc, look_at, lens=50):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    cam = bpy.data.objects.new(name, cd); cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new(f"{name}_tgt", None); tgt.location = look_at
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO')
    c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam

cam = add_cam("c_side", (cx + d, cy, cz + size*0.15), (cx, cy, cz))
sc.camera = cam

# Render every other frame for an 8-up strip
for f in (1, 4, 7, 10, 13, 16, 19, 22):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f"walk_f{f:02d}.png")
    bpy.ops.render.render(write_still=True)
    log(f"  → walk_f{f:02d}.png")

log("DONE")
