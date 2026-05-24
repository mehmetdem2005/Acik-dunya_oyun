"""Clean native-armature inspection — octahedral bones, mesh as wireframe."""
import bpy, os, sys, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as Lib
BLEND = os.path.join(Lib.OUT_DIR, "mouse_v16.blend")
OUT = os.path.join(Lib.OUT_DIR, "qa_rig_clean"); os.makedirs(OUT, exist_ok=True)
def log(m): print(f"[clean] {m}", flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
rig  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
rig.data.display_type='OCTAHEDRAL'; rig.show_in_front=True
rig.data.show_names=False
# hide CTRL collection so only deform bones show
for c in rig.data.collections:
    if c.name in ("CTRL","MCH"): c.is_visible=False
# mesh wireframe
mesh.display_type='WIRE'; mesh.show_wire=True

sc=bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'
sc.render.resolution_x=1400; sc.render.resolution_y=1000
sc.display.shading.light='FLAT'; sc.display.shading.color_type='SINGLE'
sc.display.shading.single_color=(0.5,0.5,0.55)
sc.display.shading.show_xray=False
sc.display.shading.background_type='VIEWPORT';
w=bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world=w
w.use_nodes=True; w.node_tree.nodes["Background"].inputs[0].default_value=(0.08,0.09,0.11,1)

xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    p=mesh.matrix_world@v.co; xs.append(p.x);ys.append(p.y);zs.append(p.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)); d=size*1.3
def cam(n,loc,lens=55):
    cd=bpy.data.cameras.new(n); cd.lens=lens
    c=bpy.data.objects.new(n,cd); c.location=loc; bpy.context.collection.objects.link(c)
    tg=bpy.data.objects.new(n+"t",None); tg.location=(cx,cy,cz); bpy.context.collection.objects.link(tg)
    k=c.constraints.new('TRACK_TO'); k.target=tg; k.track_axis='TRACK_NEGATIVE_Z'; k.up_axis='UP_Y'
    return c
for nm,loc in (("side",(cx+d,cy,cz)),("top",(cx,cy,cz+d)),("front",(cx,cy-d,cz)),
               ("persp",(cx+d*0.75,cy-d*0.65,cz+size*0.3))):
    sc.camera=cam(nm,loc); sc.render.filepath=os.path.join(OUT,f"clean_{nm}.png")
    bpy.ops.render.render(write_still=True); log(f"clean_{nm}.png")
log("DONE")
