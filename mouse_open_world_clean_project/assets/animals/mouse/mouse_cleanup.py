#!/usr/bin/env python3
"""Fare rig temizleme: stray sil + mesh parcalarini birlestir + kemik isimlerini
Godot-uyumlu yap (:: -> _) + vgroup'lari esle + temiz rigli .glb export.
blender --background <src.blend> --python mouse_cleanup.py -- <out.blend> <out.glb>
"""
import bpy, sys, os, re
argv=sys.argv[sys.argv.index("--")+1:]
outblend,outglb=argv[0],argv[1]
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
# 1) stray (skinsiz, armature'a bagli olmayan) mesh'leri sil
for o in list(bpy.data.objects):
    if o.type=='MESH' and (len(o.vertex_groups)==0 or not any(m.type=='ARMATURE' for m in o.modifiers)):
        print("STRAY_SIL", o.name); bpy.data.objects.remove(o,do_unlink=True)
    elif o.type=='EMPTY':
        bpy.data.objects.remove(o,do_unlink=True)
# 2) kemik isimlerini sanitize (:: -> _ ; tripo:: prefix kaldir)
def san(n):
    n=n.replace("tripo::","").replace("::","_").replace(":","_")
    n=re.sub(r'[^0-9A-Za-z_]','_',n); return n
bpy.context.view_layer.objects.active=arm; bpy.ops.object.mode_set(mode='EDIT')
rename={}
for eb in arm.data.edit_bones:
    nn=san(eb.name)
    if nn!=eb.name and nn not in arm.data.edit_bones:
        rename[eb.name]=nn; eb.name=nn
bpy.ops.object.mode_set(mode='OBJECT')
# 3) vgroup'lari yeni isimlere esle (tum mesh'lerde)
for o in bpy.data.objects:
    if o.type=='MESH':
        for vg in o.vertex_groups:
            if vg.name in rename: vg.name=rename[vg.name]
print("BONES_RENAMED", len(rename))
# 4) mesh parcalarini birlestir
meshes=[o for o in bpy.data.objects if o.type=='MESH']
bpy.ops.object.select_all(action='DESELECT')
main=max(meshes,key=lambda o:len(o.data.vertices))
for m in meshes: m.select_set(True)
bpy.context.view_layer.objects.active=main
bpy.ops.object.join()
main.name="Mouse"; main.data.name="MouseMesh"
# tek armature modifier garanti
amods=[m for m in main.modifiers if m.type=='ARMATURE']
for extra in amods[1:]: main.modifiers.remove(extra)
if not amods:
    am=main.modifiers.new("Armature",'ARMATURE'); am.object=arm
else:
    amods[0].object=arm
print("JOINED -> Mouse verts", len(main.data.vertices), "vgroups", len(main.vertex_groups))
arm.name="MouseArmature"
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(outblend))
# 5) export glb (skin, anim yok)
bpy.ops.object.select_all(action='DESELECT'); main.select_set(True); arm.select_set(True)
bpy.context.view_layer.objects.active=arm
os.makedirs(os.path.dirname(outglb),exist_ok=True)
bpy.ops.export_scene.gltf(filepath=outglb, export_format='GLB', use_selection=True,
    export_apply=True, export_skins=True, export_animations=False, export_yup=True)
print("EXPORTED", outglb, os.path.getsize(outglb))
print("CLEANUP_DONE")
