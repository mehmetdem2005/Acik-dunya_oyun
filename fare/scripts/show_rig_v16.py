"""Show v16 rig — colored bones (by region) over X-ray mesh, multi-angle."""
import bpy, os, sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mouse_rig_lib as Lib

BLEND = os.path.join(Lib.OUT_DIR, "mouse_v16.blend")
OUT = os.path.join(Lib.OUT_DIR, "qa_rig_v16")
os.makedirs(OUT, exist_ok=True)
def log(m): print(f"[show] {m}", flush=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
mesh = next(o for o in bpy.data.objects if o.type=='MESH')
rig  = next(o for o in bpy.data.objects if o.type=='ARMATURE')
log(f"{rig.name}: {len(rig.data.bones)} bones")

sc = bpy.context.scene
sc.render.engine='BLENDER_WORKBENCH'
sc.render.resolution_x=1280; sc.render.resolution_y=960
sc.display.shading.light='STUDIO'; sc.display.shading.color_type='TEXTURE'
sc.display.shading.show_cavity=True; sc.display.shading.show_object_outline=True
sc.display.shading.show_xray=True; sc.display.shading.xray_alpha=0.28
w=bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
sc.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.10,0.11,0.13,1.0)

COL={"spine":(0.95,0.85,0.15,1),"front":(0.55,0.35,0.85,1),"back":(0.20,0.85,0.30,1),
     "tail":(0.95,0.55,0.15,1),"face":(0.15,0.85,0.90,1),"whisker":(0.92,0.92,0.96,1),
     "ctrl":(0.95,0.25,0.35,1),"other":(0.6,0.6,0.6,1)}
def cat(n):
    n=n.lower()
    if n.startswith("ctrl"): return "ctrl"
    if "tail" in n or n=="sacrum": return "tail"
    if "whisker" in n: return "whisker"
    if n.startswith(("nose","snout","head","jaw","eye_","ear_","cheek","upper_lip","lower_lip","cervical")): return "face"
    if n.startswith(("scapula","humerus","radius","carpus","front_paw","front_toe")): return "front"
    if n.startswith(("hip","femur","tibia","tarsus","back_paw","back_toe")): return "back"
    if n.startswith(("pelvis","lumbar","thoracic","cog","root")): return "spine"
    return "other"
def mat(name,rgba):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True; m.diffuse_color=rgba
    b=m.node_tree.nodes.get("Principled BSDF")
    if b: b.inputs["Base Color"].default_value=rgba
    return m
mats={k:mat(f"rm_{k}",v) for k,v in COL.items()}

mw=rig.matrix_world; drawn=0
for b in rig.data.bones:
    c=cat(b.name)
    if c=="ctrl": continue   # skip control bones in the visual
    h=mw@b.head_local; t=mw@b.tail_local; L=(t-h).length
    if L<1e-5: continue
    rad=max(L*0.07,0.004)*(1.3 if c in("front","back","spine","tail") else 1.0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=10,radius=rad,depth=L,location=(0,0,0))
    o=bpy.context.object; o.name=f"VIS_{b.name}"
    d=(t-h).normalized(); o.rotation_mode='QUATERNION'
    o.rotation_quaternion=Vector((0,0,1)).rotation_difference(d)
    o.location=h+(t-h)*0.5; o.data.materials.append(mats[c])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=rad*1.4,location=h,segments=8,ring_count=6)
    s=bpy.context.object; s.name=f"VJ_{b.name}"; s.data.materials.append(mats[c])
    drawn+=1
log(f"drawn {drawn} deform bones")

xs=[];ys=[];zs=[]
for v in mesh.data.vertices:
    p=mesh.matrix_world@v.co; xs.append(p.x);ys.append(p.y);zs.append(p.z)
cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2; cz=(min(zs)+max(zs))/2
size=max(max(xs)-min(xs),max(ys)-min(ys),max(zs)-min(zs)); d=size*1.35
def cam(n,loc,lens=50):
    cd=bpy.data.cameras.new(n); cd.lens=lens
    c=bpy.data.objects.new(n,cd); c.location=loc; bpy.context.collection.objects.link(c)
    tg=bpy.data.objects.new(n+"t",None); tg.location=(cx,cy,cz); bpy.context.collection.objects.link(tg)
    k=c.constraints.new('TRACK_TO'); k.target=tg; k.track_axis='TRACK_NEGATIVE_Z'; k.up_axis='UP_Y'
    return c
cams={"side":cam("s",(cx+d,cy,cz+size*0.05)),
      "side2":cam("s2",(cx-d,cy,cz+size*0.05)),
      "front":cam("f",(cx,cy-d,cz+size*0.05)),
      "top":cam("t",(cx,cy,cz+d*0.8),45),
      "persp":cam("p",(cx+d*0.7,cy-d*0.7,cz+size*0.4))}
for nm,c in cams.items():
    sc.camera=c; sc.render.filepath=os.path.join(OUT,f"rig_{nm}.png")
    bpy.ops.render.render(write_still=True); log(f"  rig_{nm}.png")
log("DONE")
