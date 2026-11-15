"""Export portable, texture-embedded glTF 2.0 binary (GLB) tree assets. Requires trimesh + Pillow + numpy.
Usage: python scripts/generate_textures.py && python scripts/export_glb.py
"""
from pathlib import Path
import sys
import numpy as np
import trimesh
from PIL import Image
from trimesh.visual.material import PBRMaterial
from trimesh.visual.texture import TextureVisuals
from tree_geometry import generate
ROOT=Path(__file__).resolve().parent.parent
ASSETS=ROOT/'assets'
OUTPUT=ROOT/'output'
OUTPUT.mkdir(exist_ok=True)

def build(lod):
    d=generate(lod=lod)
    bark=Image.open(ASSETS/'bark_original_256.png').convert('RGBA')
    leaf_file=ASSETS/'leaf_texture.png'
    if not leaf_file.exists(): leaf_file=ASSETS/'leaf_PLACEHOLDER.png'
    leaves=Image.open(leaf_file).convert('RGBA')
    woodmat=PBRMaterial(name='Bark_Original_LowPoly',baseColorTexture=bark,
                        metallicFactor=0.0,roughnessFactor=1.0,doubleSided=False,alphaMode='OPAQUE')
    leafmat=PBRMaterial(name='Leaf_Replace_Texture',baseColorTexture=leaves,
                        metallicFactor=0.0,roughnessFactor=.95,doubleSided=True,alphaMode='MASK',alphaCutoff=.45)
    sc=trimesh.Scene()
    for name,mat,k in [('Wood',woodmat,'wood'),('Leaf_Cards',leafmat,'leaves')]:
        mesh=d[k]
        # glTF UV v axis needs flip relative to OpenGL image lookup.
        uv=np.asarray(mesh.uv,dtype=np.float32).copy()
        uv[:,1]=1-uv[:,1]
        geo=trimesh.Trimesh(vertices=np.asarray(mesh.vertices),faces=np.asarray(mesh.faces),process=False,validate=False)
        geo.visual=TextureVisuals(uv=uv,material=mat)
        sc.add_geometry(geo,node_name=name,geom_name=name)
    path=OUTPUT/f'Tree_LowPoly_LOD{lod}.glb'
    sc.export(file_obj=str(path),file_type='glb')
    loaded=trimesh.load(path,force='scene')
    assert len(loaded.geometry)==2, list(loaded.geometry)
    print(path, 'bytes', path.stat().st_size,'triangles', sum(len(m.faces) for m in loaded.geometry.values()),'bounds',np.round(loaded.bounds,2).tolist())
    for g in loaded.geometry.values():
        assert np.isfinite(g.vertices).all()
        assert g.visual.kind=='texture', g.visual.kind
    return path

if __name__=='__main__':
    for lod in (0,1): build(lod)