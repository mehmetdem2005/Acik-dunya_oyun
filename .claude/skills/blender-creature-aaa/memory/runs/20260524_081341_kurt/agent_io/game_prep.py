#!/usr/bin/env python3
"""Oyun-mesh hazirligi: decimate + vertex-renk agouti kurk materyali (glTF COLOR_0).
blender --background <mesh_hi.blend> --python game_prep.py -- <out.blend> [target_tris]
"""
import bpy, bmesh, sys, math
from pathlib import Path
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
out=argv[0]; TARGET=int(argv[1]) if len(argv)>1 else 28000
mesh=None; arm=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
    if o.type=='ARMATURE': arm=o
if arm: arm.hide_set(False); arm.hide_viewport=False; arm.hide_render=False
me=mesh.data
bpy.context.view_layer.objects.active=mesh; bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True)
# decimate
def tris():
    bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm,faces=bm.faces); n=len(bm.faces); bm.free(); return n
cur=tris()
if cur>TARGET:
    d=mesh.modifiers.new("dec",'DECIMATE'); d.ratio=TARGET/cur; d.decimate_type='COLLAPSE'
    bpy.ops.object.modifier_apply(modifier=d.name)
bpy.ops.object.shade_smooth()
print(f"[game_prep] tris {cur} -> {tris()}  verts={len(me.vertices)}")
# vertex-color agouti
xs=[v.co.x for v in me.vertices]; ys=[v.co.y for v in me.vertices]; zs=[v.co.z for v in me.vertices]
zmin,zmax=min(zs),max(zs); ymin,ymax=min(ys),max(ys); xmax=max(abs(x) for x in xs) or 1.0
def ss(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a+1e-9))); return t*t*(3-2*t)
def mix(c1,c2,t): return tuple(c1[i]+(c2[i]-c1[i])*t for i in range(3))
def h3(x,y,z):
    s=math.sin(x*12.9898+y*78.233+z*37.719)*43758.5453; return s-math.floor(s)
BACK=(0.085,0.075,0.062); MIDF=(0.20,0.175,0.135); BELLY=(0.52,0.475,0.40); DARK=(0.06,0.052,0.045)
for ca in list(me.color_attributes): me.color_attributes.remove(ca)
col=me.color_attributes.new(name="Col",type='BYTE_COLOR',domain='CORNER')
for li,loop in enumerate(me.loops):
    v=me.vertices[loop.vertex_index].co
    h=(v.z-zmin)/(zmax-zmin+1e-9); yf=(v.y-ymin)/(ymax-ymin+1e-9)
    c = mix(MIDF,BACK,ss(0.55,0.92,h)) if h>0.52 else mix(BELLY,MIDF,ss(0.10,0.55,h))
    # yuz/burun koyu
    c=mix(c,DARK,0.8*ss(0.80,0.97,yf)*ss(0.45,0.78,h))
    # alt bacak corap koyu
    c=mix(c,DARK,0.6*ss(0.26,0.06,h)*ss(0.4,0.72,abs(v.x)/xmax))
    # mottle
    n=(h3(v.x*9,v.y*9,v.z*9)-0.5)*0.10+(h3(v.x*31,v.y*31,v.z*31)-0.5)*0.05
    c=tuple(max(0.0,min(1.0,c[i]*(1+n))) for i in range(3))
    col.data[li].color=(c[0],c[1],c[2],1.0)
me.color_attributes.active_color=col; me.attributes.active_color=col
for m in list(me.materials): me.materials.clear()
mat=bpy.data.materials.new("kurt_001_main"); mat.use_nodes=True; nt=mat.node_tree; nt.nodes.clear()
o1=nt.nodes.new('ShaderNodeOutputMaterial'); o1.location=(400,0)
b1=nt.nodes.new('ShaderNodeBsdfPrincipled'); b1.location=(120,0); b1.inputs['Roughness'].default_value=0.9
if 'Specular IOR Level' in b1.inputs: b1.inputs['Specular IOR Level'].default_value=0.25
at=nt.nodes.new('ShaderNodeAttribute'); at.location=(-160,0); at.attribute_type='GEOMETRY'; at.attribute_name="Col"
nt.links.new(at.outputs['Color'],b1.inputs['Base Color']); nt.links.new(b1.outputs['BSDF'],o1.inputs['Surface'])
me.materials.append(mat)
Path(out).parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(Path(out).resolve()))
print(f"[game_prep] SAVED {out}")
