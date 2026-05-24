#!/usr/bin/env python3
"""Robust proximity skinning: her vertex -> en yakin deform kemiklere Gaussian
agirlik (bone-heat'in basarisiz oldugu prosedurel mesh'ler icin). Asla orphan
birakmaz. max 4 influence, normalize, armature modifier ekler.
blender --background <in.blend> --python skin_proximity.py -- <out.blend> [sigma]
"""
import bpy, sys, math
import numpy as np
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
out=argv[0]; SIGMA=float(argv[1]) if len(argv)>1 else 0.06
mesh=None; arm=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
    if o.type=='ARMATURE': arm=o
arm.hide_set(False); arm.hide_viewport=False
me=mesh.data
# deform kemik segmentleri (twist haric, daha temiz deformasyon)
segs=[]
for b in arm.data.bones:
    if not b.use_deform: continue
    if 'twist' in b.name: continue
    segs.append((b.name, np.array(b.head_local), np.array(b.tail_local)))
names=[s[0] for s in segs]
H=np.array([s[1] for s in segs])   # (B,3)
Tl=np.array([s[2] for s in segs])  # (B,3)
AB=Tl-H; AB2=np.sum(AB*AB,axis=1)+1e-9
# vertex koordinatlari (mesh origin=identity, armature origin -> ayni uzay)
N=len(me.vertices)
V=np.empty((N,3),dtype=np.float64)
me.vertices.foreach_get("co", V.ravel())
# her bone icin point-segment mesafesi (vectorized)
B=len(segs)
D=np.empty((N,B),dtype=np.float64)
for j in range(B):
    ap = V - H[j]                       # (N,3)
    t = np.clip((ap@AB[j])/AB2[j], 0.0, 1.0)  # (N,)
    proj = H[j] + np.outer(t, AB[j])    # (N,3)
    D[:,j] = np.linalg.norm(V-proj, axis=1)
# Gaussian agirlik
W = np.exp(-(D/SIGMA)**2)               # (N,B)
# top-4 tut
K=4
idx_sorted = np.argsort(-W, axis=1)
mask = np.zeros_like(W, dtype=bool)
rows = np.arange(N)[:,None]
mask[rows, idx_sorted[:,:K]] = True
W = np.where(mask, W, 0.0)
# bos satir -> en yakin bone weight 1
rs = W.sum(axis=1)
empty = rs<1e-9
if empty.any():
    nearest = np.argmin(D[empty], axis=1)
    W[np.where(empty)[0], nearest] = 1.0
    rs = W.sum(axis=1)
W = W / rs[:,None]
# vertex gruplari olustur + ata
for vg in list(mesh.vertex_groups): mesh.vertex_groups.remove(vg)
groups=[mesh.vertex_groups.new(name=n) for n in names]
for j in range(B):
    col=W[:,j]; nz=np.where(col>1e-4)[0]
    g=groups[j]
    for vi in nz:
        g.add([int(vi)], float(col[vi]), 'REPLACE')
# armature modifier
for m in list(mesh.modifiers):
    if m.type=='ARMATURE': mesh.modifiers.remove(m)
amod=mesh.modifiers.new("Armature",'ARMATURE'); amod.object=arm; amod.use_vertex_groups=True
# parent (transform iliskisi)
mesh.parent=arm
print(f"[prox_skin] verts={N} bones={B} avg_influences={(W>1e-4).sum(axis=1).mean():.2f} orphans={(W.sum(axis=1)<1e-9).sum()}")
bpy.ops.wm.save_as_mainfile(filepath=__import__('os').path.abspath(out))
print("SAVED",out)
