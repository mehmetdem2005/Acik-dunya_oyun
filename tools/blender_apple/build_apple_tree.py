"""Orkestrator (cam pine_tree yansimasi). Headless:
  blender -b --factory-startup --python tools/blender_apple/build_apple_tree.py
Sahneyi temizler -> skeleton->mesh->foliage->fruit->materials ->
.blend kaydeder -> Eevee render (/tmp/apple_check.png). GLB YOK
(yalniz export_glb.py finalde)."""
import sys, os, math
sys.path.insert(0, "/home/user/Acik-dunya_oyun/tools")

import bpy
from mathutils import Vector
from blender_apple import config as C
from blender_apple import skeleton, mesh, materials, foliage, fruit


def _clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _bbox(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            for i in range(3):
                lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    return lo, hi


def _stage(tree_objs):
    lo, hi = _bbox(tree_objs)
    ctr = (lo + hi) * 0.5
    size = (hi - lo)
    rad = max(size.x, size.y, size.z) * 0.5
    # zemin
    if C.GROUND:
        bpy.ops.mesh.primitive_plane_add(size=rad * 8, location=(ctr.x, ctr.y, lo.z))
        g = bpy.context.object
        gm = bpy.data.materials.new("Ground")
        gm.use_nodes = True
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.21, 0.26, 0.16, 1)
        gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
        g.data.materials.append(gm)
    # gunes
    bpy.ops.object.light_add(type='SUN', location=(rad * 2, -rad * 3, rad * 4))
    sun = bpy.context.object
    sun.data.energy = 3.2
    sun.data.angle = math.radians(2.0)
    sun.rotation_euler = (math.radians(52), 0, math.radians(35))
    # kamera (agaci cerceveler)
    dist = rad * 3.0
    cam_pos = Vector((ctr.x + dist * 0.55, ctr.y - dist, ctr.z + size.z * 0.12))
    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.object
    look = Vector((ctr.x, ctr.y, ctr.z + size.z * 0.02))
    dirv = (look - cam_pos)
    cam.rotation_euler = dirv.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 50
    bpy.context.scene.camera = cam
    # dunya isigi (gokyuzu)
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.68, 0.86, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.85
    bpy.context.scene.world = w


def main():
    _clear()
    mats = materials.build()
    skel = skeleton.build()
    wood = mesh.build(skel, mats)
    leaves = foliage.build(skel, mats)
    apples = fruit.build(skel, mats)

    coll = bpy.data.collections.new("AppleTree")
    bpy.context.scene.collection.children.link(coll)
    for ob in (wood, leaves, apples):
        coll.objects.link(ob)

    _stage([wood, leaves, apples])

    bpy.ops.file.pack_all()
    os.makedirs(os.path.dirname(C.BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=C.BLEND_PATH)

    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 48
    sc.eevee.use_soft_shadows = True
    sc.render.resolution_x = C.RES_X
    sc.render.resolution_y = C.RES_Y
    sc.render.film_transparent = False
    sc.render.filepath = C.RENDER_PATH
    bpy.ops.render.render(write_still=True)
    print("APPLE_BUILD_DONE verts_wood=%d leaves_faces=%d apples=%d" % (
        len(wood.data.vertices), len(leaves.data.polygons),
        len(skel["tips"])))


main()
