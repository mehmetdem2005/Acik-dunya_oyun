#!/usr/bin/env python3
"""Animasyon onizleme: bir klibin belirli karelerini yan gorunumden render eder.
blender --background <animated.blend> --python anim_preview.py -- <outdir> <clip> <f1,f2,...>"""
import bpy, math, sys, os
from mathutils import Vector
argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
outdir,clip,frames=argv[0],argv[1],[int(x) for x in argv[2].split(",")]
os.makedirs(outdir,exist_ok=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE'); arm.hide_render=True
mesh=max((o for o in bpy.data.objects if o.type=='MESH'),key=lambda o:len(o.data.vertices))
# klibi aktif et, NLA'yi sustur
ad=arm.animation_data
for t in ad.nla_tracks: t.mute=True
ad.action=bpy.data.actions[clip]
# isik+kamera+zemin
bpy.ops.mesh.primitive_plane_add(size=14); gp=bpy.context.view_layer.objects.active
gm=bpy.data.materials.new("g"); gm.use_nodes=True; gm.node_tree.nodes.get("Principled BSDF").inputs['Base Color'].default_value=(0.13,0.13,0.12,1); gp.data.materials.append(gm)
w=bpy.context.scene.world or bpy.data.worlds.new("W"); bpy.context.scene.world=w; w.use_nodes=True
w.node_tree.nodes["Background"].inputs[0].default_value=(0.32,0.36,0.42,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.6
sd=bpy.data.lights.new("k",'SUN'); sd.energy=3.2; so=bpy.data.objects.new("k",sd); bpy.context.collection.objects.link(so); so.rotation_euler=(math.radians(52),math.radians(8),math.radians(46))
# kamera (yan, sabit - hareketi gormek icin)
ctr=Vector((0,0,0.45))
cam=bpy.data.cameras.new("c"); co=bpy.data.objects.new("c",cam); bpy.context.collection.objects.link(co); bpy.context.scene.camera=co; cam.lens=55
co.location=(2.6,-1.0,0.6); tg=bpy.data.objects.new("t",None); tg.location=Vector((0.15,0.2,0.42)); bpy.context.collection.objects.link(tg); co.constraints.new('TRACK_TO').target=tg
sc=bpy.context.scene; sc.render.engine='BLENDER_EEVEE_NEXT'; sc.render.resolution_x=560; sc.render.resolution_y=440
sc.view_settings.view_transform='Standard'
for f in frames:
    sc.frame_set(f)
    sc.render.filepath=os.path.join(outdir,f"{clip}_f{f:02d}.png"); bpy.ops.render.render(write_still=True); print("RENDERED",clip,f)
print("PREVIEW_DONE")
