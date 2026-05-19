"""Pass 3 — materyaller (cam pine_textures yansimasi). 3 PBR materyal:
kabuk / yaprak (alpha doku) / elma. Yaprak maskesi prosedurel uretilir
(numpy) -> PNG -> pack (GLB embed'inde PBR korunur)."""
import os
import math
import bpy

from . import config as C


def _leaf_image():
    """Sivri-oval yaprak: RGBA (yesil + orta damar, A=siluet). numpy YOK."""
    os.makedirs(C.GEN_DIR, exist_ok=True)
    path = os.path.join(C.GEN_DIR, "leaf_mask.png")
    n = 192
    px = [0.0] * (n * n * 4)
    inv = 1.0 / (n - 1)
    for yy in range(n):
        v = yy * inv                       # 0 taban -> 1 uc
        halfw = 0.62 * (math.sin(math.pi * v) ** 0.75)
        r = 0.10 + 0.05 * v
        g = 0.30 + 0.18 * (1.0 - v)
        b = 0.06 + 0.03 * v
        # blender pixels alt-ust ters: satiri tersle
        row = (n - 1 - yy) * n * 4
        for xx in range(n):
            u = xx * inv * 2.0 - 1.0
            au = abs(u)
            edge = (halfw - au) / 0.06
            a = 0.0 if edge <= 0.0 else (1.0 if edge >= 1.0 else edge)
            vein = math.exp(-(u * u) / 0.004) * 0.35
            i = row + xx * 4
            px[i] = max(0.0, r - vein)
            px[i + 1] = max(0.0, g - vein)
            px[i + 2] = max(0.0, b - vein)
            px[i + 3] = a
    bi = bpy.data.images.new("apple_leaf", n, n, alpha=True)
    bi.pixels = px
    bi.filepath_raw = path
    bi.file_format = 'PNG'
    bi.save()
    bi.pack()
    return bi


def _principled(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    return m, nt, bsdf


def build():
    # --- Kabuk ---
    bark, nt, b = _principled("AppleBark")
    b.inputs["Base Color"].default_value = (0.16, 0.10, 0.06, 1)
    b.inputs["Roughness"].default_value = 0.92
    b.inputs["Metallic"].default_value = 0.0
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 14.0
    tex.inputs["Detail"].default_value = 6.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.28
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])

    # --- Yaprak (alpha) ---
    leaf, lnt, lb = _principled("AppleLeaf")
    lb.inputs["Roughness"].default_value = 0.62
    lb.inputs["Metallic"].default_value = 0.0
    img = _leaf_image()
    itex = lnt.nodes.new("ShaderNodeTexImage")
    itex.image = img
    lnt.links.new(itex.outputs["Color"], lb.inputs["Base Color"])
    lnt.links.new(itex.outputs["Alpha"], lb.inputs["Alpha"])
    leaf.blend_method = 'CLIP'
    leaf.shadow_method = 'CLIP'
    leaf.alpha_threshold = 0.5
    leaf.use_backface_culling = False
    leaf.show_transparent_back = False

    # --- Elma ---
    apple, ant, ab = _principled("AppleFruit")
    ab.inputs["Base Color"].default_value = (0.55, 0.035, 0.03, 1)
    ab.inputs["Roughness"].default_value = 0.33
    ab.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in ab.inputs:
        ab.inputs["Specular IOR Level"].default_value = 0.6

    return {"bark": bark, "leaf": leaf, "apple": apple}
