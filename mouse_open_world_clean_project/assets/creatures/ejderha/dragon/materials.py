"""glTF 2.0 metallic-roughness materyalleri (Principled BSDF + ORM paketi).

Godot 4.6 uyumlulugu icin:
  - Sadece standart Principled BSDF kullanilir (proprietary node yok),
  - ORM tek texture: R=AO (glTF Material Output grubuna), G=Roughness, B=Metallic,
  - Normal harita tangent-space, glTF standardi (+Y),
  - Alpha yok (kanat zari kati kabuk) -> transparent sorting sorunu yok,
  - Backface culling acik (Godot: cull_mode = back).
"""

import os
import bpy

from . import config as C


def _gltf_output_group():
    """glTF exporter'in occlusion'i tanimasi icin ozel node grubu."""
    name = "glTF Material Output"
    if name in bpy.data.node_groups:
        return bpy.data.node_groups[name]
    g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    g.interface.new_socket("Occlusion", in_out='INPUT',
                           socket_type='NodeSocketFloat')
    inp = g.nodes.new("NodeGroupInput")
    inp.location = (-200, 0)
    return g


def _img(path, non_color):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'Non-Color' if non_color else 'sRGB'
    img.alpha_mode = 'NONE'
    return img


def build_material(name, tex_paths, double_sided=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = not double_sided
    mat.blend_method = 'OPAQUE'
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (340, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    # Cekirdek glTF metallic-roughness disinda uzanti uretmemek icin IOR ve
    # specular varsayilanda birakilir -> KHR_materials_ior / _specular yazilmaz.
    bsdf.inputs["IOR"].default_value = 1.5
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.5

    # --- base color ---
    t_base = nodes.new("ShaderNodeTexImage")
    t_base.location = (-380, 260)
    t_base.image = _img(tex_paths["base"], non_color=False)
    t_base.label = "BaseColor"
    links.new(t_base.outputs["Color"], bsdf.inputs["Base Color"])

    # --- ORM ---
    t_orm = nodes.new("ShaderNodeTexImage")
    t_orm.location = (-380, -40)
    t_orm.image = _img(tex_paths["orm"], non_color=True)
    t_orm.label = "ORM"
    sep = nodes.new("ShaderNodeSeparateColor")
    sep.location = (-120, -40)
    links.new(t_orm.outputs["Color"], sep.inputs["Color"])
    links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])

    # --- occlusion -> glTF Material Output ---
    grp = nodes.new("ShaderNodeGroup")
    grp.node_tree = _gltf_output_group()
    grp.location = (340, -320)
    links.new(sep.outputs["Red"], grp.inputs["Occlusion"])

    # --- normal ---
    t_nrm = nodes.new("ShaderNodeTexImage")
    t_nrm.location = (-380, -360)
    t_nrm.image = _img(tex_paths["normal"], non_color=True)
    t_nrm.label = "Normal"
    nmap = nodes.new("ShaderNodeNormalMap")
    nmap.location = (-120, -360)
    nmap.space = 'TANGENT'
    links.new(t_nrm.outputs["Color"], nmap.inputs["Color"])
    links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def build_all(tex_result):
    mats = {}
    for name in C.MATERIALS:
        # kanat zari kati kabuk; yine de motorda cift tarafli istenirse
        # M_Dragon_Wings tek yerden acilabilir.
        mats[name] = build_material(name, tex_result[name],
                                    double_sided=(name == "M_Dragon_Wings"))
    return mats
