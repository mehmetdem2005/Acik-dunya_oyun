"""Run IN Blender (bpy) to create a fully editable .blend and export GLB.
    blender -b --python scripts/build_blend.py -- --lod=0
"""
import bpy
from pathlib import Path
import sys
from mathutils import Quaternion
from tree_geometry import generate

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
ASSETS=ROOT/'assets'
ARGS=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
LOD=int(next((x.split('=')[1] for x in ARGS if x.startswith('--lod=')),'0'))

# Only delete objects in the newly created scene.  Never open or modify the user's blend file.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def surface(name,texture_path,leaf=False):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    mat.diffuse_color=(.39,.26,.16,1) if not leaf else (.27,.54,.19,1)
    tree=mat.node_tree
    bsdf=next(n for n in tree.nodes if n.type=='BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value=1.0
    img=tree.nodes.new('ShaderNodeTexImage')
    img.name='REPLACE_THIS_LEAF_IMAGE' if leaf else 'BAKED_ORIGINAL_BARK'
    img.label='YAPRAK PNG BURAYA' if leaf else 'Bark (original procedural)'
    image=bpy.data.images.load(str(texture_path),check_existing=True)
    image.pack()
    img.image=image
    tree.links.new(img.outputs['Color'],bsdf.inputs['Base Color'])
    if leaf:
        tree.links.new(img.outputs['Alpha'],bsdf.inputs['Alpha'])
        mat.use_backface_culling=False
        try: mat.blend_method='CLIP'
        except (AttributeError,TypeError):
            try: mat.surface_render_method='DITHERED'
            except (AttributeError,TypeError): pass
        try: mat.alpha_threshold=.45
        except (AttributeError,TypeError): pass
    return mat

wood=surface('Bark_Original',ASSETS/'bark_original_256.png',False)
leaf_path=ASSETS/'leaf_texture.png'
if not leaf_path.exists(): leaf_path=ASSETS/'leaf_PLACEHOLDER.png'
leaf=surface('Leaf_Replace_Texture',leaf_path,True)
root=bpy.data.objects.new('TREE_ROOT__GRAB_TO_MOVE',None)
bpy.context.collection.objects.link(root)

def make_obj(objname, data, material):
    mesh=bpy.data.meshes.new(objname+'_mesh')
    mesh.from_pydata(data.vertices,[],data.faces)
    mesh.update()
    layer=mesh.uv_layers.new(name='LEAF_FULL_UV_0_TO_1' if material==leaf else 'BARK_UV')
    for p in mesh.polygons:
        for loop_idx in p.loop_indices:
            idx=mesh.loops[loop_idx].vertex_index
            uv=data.uv[idx]
            layer.data[loop_idx].uv=uv
    obj=bpy.data.objects.new(objname,mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent=root
    obj.data.materials.append(material)
    return obj

geo=generate(lod=LOD)
a=make_obj('01_Trunk_and_Branches',geo['wood'],wood)
b=make_obj('02_Leaves_Replace_PNG',geo['leaves'],leaf)
bpy.ops.object.select_all(action='DESELECT')
a.select_set(True)
bpy.context.view_layer.objects.active=a
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=13.0
            # angled perspective, presenting branches and cards
            area.spaces.active.region_3d.view_location=(0,0,3.2)

path=OUT/f'Tree_LowPoly_LOD{LOD}.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path),check_existing=False)
# Blender exporter creates GLB with packed temporary images. On newer versions the
# leaf alpha is wired to the Principled material and uses glTF alpha mode when supported.
bpy.ops.export_scene.gltf(filepath=str(OUT/f'Tree_LowPoly_Blender_LOD{LOD}.glb'),
                          export_format='GLB',use_selection=False,
                          export_yup=True,export_apply=True)
print('Created',path)