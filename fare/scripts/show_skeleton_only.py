"""Bones-only skeleton render (mesh hidden) + faint-mesh context — clear diagnosis."""
import bpy, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as Lib
BLEND = os.path.join(Lib.OUT_DIR, "mouse_v16.blend")
OUT = os.path.join(Lib.OUT_DIR, "qa_skel"); os.makedirs(OUT, exist_ok=True)
def log(m): print(f"[skel] {m}", flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
rig  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
mw=rig.matrix_world

COL={"spine":(0.95,0.85,0.15,1),"front":(0.65,0.40,0.95,1),"back":(0.20,0.90,0.35,1),
     "tail":(0.95,0.55,0.15,1),"face":(0.15,0.85,0.95,1),"whisker":(0.95,0.95,0.98,1),"other":(0.6,0.6,0.6,1)}
def cat(n):
    n=n.lower()
    if n.startswith("ctrl") or n in("root","cog"): return None
    if "tail" in n or n=="sacrum": return "tail"
    if "whisker" in n: return "whisker"
    if n.startswith(("nose","snout","head","jaw","eye_","ear_","cheek","upper_lip","lower_lip","cervical")): return "face"
    if n.startswith(("scapula","humerus","radius","carpus","front_paw","front_toe")): return "front"
    if n.startswith(("hip","femur","tibia","tarsus","back_paw","back_toe")): return "back"
    if n.startswith(("pelvis","lumbar","thoracic")): return "spine"
    return "other"
def mat(name,rgba):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes=True
    m.diffuse_color=rgba
    b=m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value=rgba
        if "Emission Color" in b.inputs: b.inputs["Emission Color"].default_value=rgba
        if "Emission Strength" in b.inputs: b.inputs["Emission Strength"].default_value=0.4
    return m
mats={k:mat(f"sm_{k}",v) for k,v in COL.items()}

for b in rig.data.bones:
    c=cat(b.name)
    if not c: continue
    h=mw@b.head_local; t=mw@b.tail_local; L=(t-h).length
    if L<1e-5: continue
    rad=max(L*0.08,0.0035)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=rad,depth=L)
    o=bpy.context.object; dr=(t-h).normalized(); o.rotation_mode='QUATERNION'
    o.rotation_quaternion=Vector((0,0,1)).rotation_difference(dr)
    o.location=h+(t-h)*0.5; o.data.materials.append(mats[c])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=rad*1.5,location=h,segments=8,ring_count=6)
    bpy.context.object.data.materials.append(mats[c])

sc=bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'
sc.render.resolution_x=1400; sc.render.resolution_y=1000
sc.display.shading.light='STUDIO'; sc.display.shading.color_type='MATERIAL'
sc.display.shading.show_object_outline=False
w=bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world=w
w.use_nodes=True; w.node_tree.nodes["Background"].inputs[0].default_value=(0.06,0.07,0.09,1)

xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    p=mesh.matrix_world@v.co; xs.append(p.x);ys.append(p.y);zs.append(p.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)); d=size*1.25
def cam(n,loc,lens=55):
    cd=bpy.data.cameras.new(n); cd.lens=lens
    c=bpy.data.objects.new(n,cd); c.location=loc; bpy.context.collection.objects.link(c)
    tg=bpy.data.objects.new(n+"t",None); tg.location=(cx,cy,cz); bpy.context.collection.objects.link(tg)
    k=c.constraints.new('TRACK_TO'); k.target=tg; k.track_axis='TRACK_NEGATIVE_Z'; k.up_axis='UP_Y'
    return c
cs={nm:cam(nm,loc) for nm,loc in (("side",(cx+d,cy,cz)),("top",(cx,cy,cz+d)),
                                  ("front",(cx,cy-d,cz)),("persp",(cx+d*0.7,cy-d*0.6,cz+size*0.3)))}
# bones-only
mesh.hide_render=True
for nm,c in cs.items():
    sc.camera=c; sc.render.filepath=os.path.join(OUT,f"skel_{nm}.png")
    bpy.ops.render.render(write_still=True); log(f"skel_{nm}.png")
log("DONE")
