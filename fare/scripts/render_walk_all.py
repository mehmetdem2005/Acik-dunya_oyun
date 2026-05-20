"""Render ALL 24 frames + perspective camera for GIF building."""

import bpy, os
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(ROOT, "out", "mouse_walk.blend")
OUT = os.path.join(ROOT, "out", "qa_walk")
os.makedirs(OUT, exist_ok=True)

def log(m): print(f"[rwa] {m}", flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.resolution_x = 480
sc.render.resolution_y = 360
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_cavity = True
sc.display.shading.show_object_outline = True
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.12, 0.13, 0.15, 1.0)

mw = mesh.matrix_world
xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    wp = mw @ v.co
    xs.append(wp.x); ys.append(wp.y); zs.append(wp.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
d = size * 1.4

cd = bpy.data.cameras.new("cs"); cd.lens = 50
cam = bpy.data.objects.new("cs", cd)
cam.location = (cx + d, cy, cz + size*0.15)
bpy.context.collection.objects.link(cam)
tgt = bpy.data.objects.new("cs_tgt", None); tgt.location=(cx,cy,cz)
bpy.context.collection.objects.link(tgt)
c = cam.constraints.new('TRACK_TO'); c.target=tgt
c.track_axis='TRACK_NEGATIVE_Z'; c.up_axis='UP_Y'
sc.camera = cam

for f in range(1, 25):
    sc.frame_set(f)
    sc.render.filepath = os.path.join(OUT, f"all_{f:02d}.png")
    bpy.ops.render.render(write_still=True)
log("DONE")
