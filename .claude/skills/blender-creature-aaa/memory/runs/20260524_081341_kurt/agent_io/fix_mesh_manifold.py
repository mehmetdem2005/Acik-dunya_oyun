#!/usr/bin/env python3
"""Mesh temizleme: merge-by-distance, hole fill, normal recalc, non-manifold azalt.
Kullanim: blender --background <in.blend> --python fix_mesh_manifold.py -- <out.blend>
"""
import bpy, bmesh, sys, math
from pathlib import Path
out = (sys.argv[sys.argv.index("--")+1:] or ["mesh_clean.blend"])[0]

mesh=None
for o in bpy.data.objects:
    if o.type=='MESH' and (mesh is None or len(o.data.vertices)>len(mesh.data.vertices)): mesh=o
bpy.context.view_layer.objects.active=mesh; bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True)

def count_nm():
    bm=bmesh.new(); bm.from_mesh(mesh.data); bm.edges.ensure_lookup_table()
    nm=sum(1 for e in bm.edges if not e.is_manifold); bd=sum(1 for e in bm.edges if len(e.link_faces)<2)
    bm.free(); return nm,bd

print("BEFORE nm,boundary =", count_nm())
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0009)
bpy.ops.mesh.normals_make_consistent(inside=False)
# fill non-manifold/boundary holes
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.mesh.select_non_manifold()
try: bpy.ops.mesh.fill_holes(sides=8)
except Exception as e: print("fill_holes:",e)
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.mesh.select_non_manifold()
try: bpy.ops.mesh.edge_collapse()
except Exception as e: print("edge_collapse:",e)
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.shade_smooth()

nm,bd=count_nm()
print("AFTER nm,boundary =", nm, bd)
tris=sum(len(p.vertices)-2 for p in mesh.data.polygons)
print("TRIS", tris, "VERTS", len(mesh.data.vertices))
Path(out).parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(Path(out).resolve()))
print("SAVED", out)
