#!/usr/bin/env python3
"""Kurt materyali: vertex-color countershading (gri kurt agouti) + Principled BSDF.
Koyu sirt, acik karin, koyu alt bacak (corap), koyu burun/kulak ucu, tuy benekleri.
glTF'e COLOR_0 olarak temiz export olur.
Kullanim: blender --background <in.blend> --python wolf_material.py -- <out.blend>
"""
import bpy, sys, math, random
from pathlib import Path
out = (sys.argv[sys.argv.index("--")+1:] or ["mat.blend"])[0]

mesh=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
me = mesh.data

xs=[v.co.x for v in me.vertices]; ys=[v.co.y for v in me.vertices]; zs=[v.co.z for v in me.vertices]
zmin,zmax=min(zs),max(zs); ymin,ymax=min(ys),max(ys); xmax=max(abs(x) for x in xs) or 1.0

def sstep(a,b,x):
    t=max(0.0,min(1.0,(x-a)/(b-a))); return t*t*(3-2*t)
def mix(c1,c2,t): return tuple(c1[i]+(c2[i]-c1[i])*t for i in range(3))
def h3(x,y,z):
    s=math.sin(x*12.9898+y*78.233+z*37.719)*43758.5453; return s-math.floor(s)

# gri kurt paleti
BACK   =(0.085,0.080,0.078)   # koyu sirt
MIDF   =(0.205,0.185,0.165)   # govde yan (agouti)
BELLY  =(0.62,0.585,0.54)     # acik karin/gerdan
SNOUT  =(0.055,0.05,0.048)    # koyu burun
SOCK   =(0.10,0.092,0.088)    # koyu alt bacak

# color attribute (CORNER -> glTF COLOR_0)
for ca in list(me.color_attributes):
    me.color_attributes.remove(ca)
col = me.color_attributes.new(name="Col", type='BYTE_COLOR', domain='CORNER')

for li,loop in enumerate(me.loops):
    v = me.vertices[loop.vertex_index].co
    h = (v.z - zmin)/(zmax-zmin+1e-6)        # 0 alt .. 1 ust
    yf = (v.y - ymin)/(ymax-ymin+1e-6)        # 0 arka .. 1 on
    # dikey countershade: ust koyu, orta agouti, alt acik
    if h > 0.55:
        c = mix(MIDF, BACK, sstep(0.55,0.92,h))
    else:
        c = mix(BELLY, MIDF, sstep(0.12,0.58,h))
    # burun/agiz (on + orta-ust): koyu
    snout = sstep(0.80,0.97,yf) * sstep(0.35,0.75,h)
    c = mix(c, SNOUT, 0.85*snout)
    # alt bacak corap (cok alt + yana acik)
    sock = sstep(0.22,0.05,h) * sstep(0.45,0.75,abs(v.x)/xmax)
    c = mix(c, SOCK, 0.7*sock)
    # kulak ucu (cok ust + on)
    eartip = sstep(0.90,1.0,h) * sstep(0.55,0.9,yf)
    c = mix(c, SNOUT, 0.6*eartip)
    # tuy benekleri (pozisyon-temelli noise)
    n = (h3(v.x*9, v.y*9, v.z*9)-0.5)*0.10 + (h3(v.x*31,v.y*31,v.z*31)-0.5)*0.05
    c = tuple(max(0.0,min(1.0, c[i]*(1.0+n))) for i in range(3))
    col.data[li].color = (c[0],c[1],c[2],1.0)

me.color_attributes.active_color = col
me.attributes.active_color = col

# material
for m in list(me.materials): me.materials.clear()
mat = bpy.data.materials.new("kurt_001_main"); mat.use_nodes=True
nt=mat.node_tree; nt.nodes.clear()
out_n=nt.nodes.new('ShaderNodeOutputMaterial'); out_n.location=(600,0)
bsdf=nt.nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location=(250,0)
bsdf.inputs['Roughness'].default_value=0.92
if 'Metallic' in bsdf.inputs: bsdf.inputs['Metallic'].default_value=0.0
if 'Specular IOR Level' in bsdf.inputs: bsdf.inputs['Specular IOR Level'].default_value=0.25
attr=nt.nodes.new('ShaderNodeAttribute'); attr.location=(-150,0)
attr.attribute_type='GEOMETRY'; attr.attribute_name="Col"
nt.links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(bsdf.outputs['BSDF'], out_n.inputs['Surface'])
me.materials.append(mat)
print(f"[wolf_material] vertex-color countershade OK, loops={len(me.loops)}")

Path(out).parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(Path(out).resolve()))
print(f"[wolf_material] SAVED {out}")
