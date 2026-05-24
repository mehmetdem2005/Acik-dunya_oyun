#!/usr/bin/env python3
"""Finalize hazirligi: armature unhide + ORM paketle (R=AO,G=rough,B=metal0) +
build_material konvansiyonuna gore texture'lari yeniden adlandir (kurt_001_*).
blender --background <textured_v1.blend> --python finalize_prep.py -- <texdir> <out.blend>
"""
import bpy, sys, os, shutil
import numpy as np
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
texdir, outb = argv[0], argv[1]
gdir=os.path.join(texdir,"godot"); os.makedirs(gdir,exist_ok=True)
# unhide armature
for o in bpy.data.objects:
    if o.type=='ARMATURE': o.hide_viewport=False; o.hide_render=False; o.hide_set(False)
# ORM pack
ao=bpy.data.images.load(os.path.join(texdir,"wolf_body_ao.png"))
ro=bpy.data.images.load(os.path.join(texdir,"wolf_body_roughness.png"))
w,h=ao.size
apx=np.empty(w*h*4,dtype=np.float32); ao.pixels.foreach_get(apx)
rpx=np.empty(w*h*4,dtype=np.float32); ro.pixels.foreach_get(rpx)
orm=np.ones(w*h*4,dtype=np.float32)
orm[0::4]=apx[0::4]   # R=AO
orm[1::4]=rpx[0::4]   # G=roughness
orm[2::4]=0.0         # B=metallic
orm[3::4]=1.0
oimg=bpy.data.images.new("kurt_001_orm",w,h); oimg.colorspace_settings.name='Non-Color'
oimg.pixels.foreach_set(orm); oimg.filepath_raw=os.path.join(gdir,"kurt_001_orm.png"); oimg.file_format='PNG'; oimg.save()
# copy renamed albedo/normal
shutil.copy(os.path.join(texdir,"wolf_body_albedo.png"), os.path.join(gdir,"kurt_001_albedo.png"))
shutil.copy(os.path.join(texdir,"wolf_body_normal.png"), os.path.join(gdir,"kurt_001_normal.png"))
print("ORM packed + renamed ->", gdir)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outb))
print("SAVED", outb)
