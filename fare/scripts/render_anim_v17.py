"""Render frames of a chosen action from mouse_anim17.blend → GIF source."""
import bpy, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as Lib

BLEND = os.path.join(Lib.OUT_DIR, "mouse_anim17.blend")
ACTION = sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else "Walk"
NFR = int(sys.argv[sys.argv.index("--")+2]) if "--" in sys.argv else 32
OUT = os.path.join(Lib.OUT_DIR, f"qa_anim_{ACTION.lower()}")
os.makedirs(OUT, exist_ok=True)

def log(m): print(f"[ra] {m}", flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
arm = next(o for o in bpy.data.objects if o.type=='ARMATURE')
act = bpy.data.actions.get(ACTION)
arm.animation_data.action = act
log(f"Action: {ACTION}")

sc = bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'
sc.render.resolution_x=480; sc.render.resolution_y=380
sc.display.shading.light='STUDIO'; sc.display.shading.color_type='TEXTURE'
sc.display.shading.show_cavity=True; sc.display.shading.show_object_outline=True
w=bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
sc.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.12,0.13,0.15,1.0)

mw=mesh.matrix_world
xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    p=mw@v.co; xs.append(p.x);ys.append(p.y);zs.append(p.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)); d=size*1.45

cd=bpy.data.cameras.new("c"); cd.lens=52
cam=bpy.data.objects.new("c",cd); cam.location=(cx+d,cy,cz+size*0.12)
bpy.context.collection.objects.link(cam)
tgt=bpy.data.objects.new("t",None); tgt.location=(cx,cy,cz)
bpy.context.collection.objects.link(tgt)
co=cam.constraints.new('TRACK_TO'); co.target=tgt; co.track_axis='TRACK_NEGATIVE_Z'; co.up_axis='UP_Y'
sc.camera=cam

for f in range(1, NFR+1):
    sc.frame_set(f)
    sc.render.filepath=os.path.join(OUT, f"f{f:02d}.png")
    bpy.ops.render.render(write_still=True)
log("DONE")
