from __future__ import annotations

from pathlib import Path
import math

import bpy
import numpy as np

from .config import MATERIAL_NAMES


def build_materials(textures_dir: Path, size: int = 1024) -> dict[str, bpy.types.Material]:
    textures_dir.mkdir(parents=True, exist_ok=True)

    body = _dragon_surface_set(textures_dir, "body", size, palette="body")
    ventral = _dragon_surface_set(textures_dir, "ventral", size, palette="ventral")
    membrane = _dragon_surface_set(textures_dir, "wing", size, palette="wing")
    horn = _dragon_surface_set(textures_dir, "horn", max(512, size // 2), palette="horn")
    scar = _dragon_surface_set(textures_dir, "scar", max(512, size // 2), palette="scar")

    materials: dict[str, bpy.types.Material] = {}
    materials["M_Dragon_Body"] = _pbr_material("M_Dragon_Body", body, roughness=0.78)
    materials["M_Dragon_Ventral"] = _pbr_material("M_Dragon_Ventral", ventral, roughness=0.70)
    materials["M_Dragon_WingMembrane"] = _pbr_material(
        "M_Dragon_WingMembrane", membrane, roughness=0.63, double_sided=True, subsurface=0.04
    )
    materials["M_Dragon_Horns_Claws"] = _pbr_material("M_Dragon_Horns_Claws", horn, roughness=0.56)
    materials["M_Dragon_Scars"] = _pbr_material("M_Dragon_Scars", scar, roughness=0.48)
    materials["M_Dragon_Eyes"] = _simple_material(
        "M_Dragon_Eyes", (0.06, 0.012, 0.006, 1.0), metallic=0.0, roughness=0.08,
        emission=(0.18, 0.018, 0.004, 1.0), emission_strength=0.35,
    )
    materials["M_Dragon_Mouth"] = _simple_material(
        "M_Dragon_Mouth", (0.12, 0.014, 0.016, 1.0), metallic=0.0, roughness=0.33,
    )
    materials["M_Dragon_Teeth"] = _simple_material(
        "M_Dragon_Teeth", (0.37, 0.31, 0.23, 1.0), metallic=0.0, roughness=0.50,
    )

    missing = set(MATERIAL_NAMES) - set(materials)
    if missing:
        raise RuntimeError(f"Material build incomplete: {sorted(missing)}")
    return materials


def _dragon_surface_set(directory: Path, stem: str, size: int, palette: str) -> dict[str, Path]:
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    u = x / max(size - 1, 1)
    v = y / max(size - 1, 1)

    # Irregular overlapping-scale field. It is deterministic and tile-friendly enough for mipmapped use.
    phase_x = np.sin((v * 15.0 + np.sin(u * 9.0) * 0.55) * math.tau)
    phase_y = np.cos((u * 19.0 + np.sin(v * 7.0) * 0.42) * math.tau)
    cellular = np.abs(phase_x * phase_y)
    micro = (
        np.sin((u * 71.0 + v * 17.0) * math.tau) * 0.18
        + np.cos((v * 83.0 - u * 13.0) * math.tau) * 0.13
        + np.sin((u + v) * 131.0 * math.tau) * 0.07
    )
    ridges = np.clip((cellular - 0.54) * 2.8, 0.0, 1.0)
    height = np.clip(0.28 + cellular * 0.55 + micro * 0.18, 0.0, 1.0)

    palettes = {
        "body": ((0.035, 0.025, 0.020), (0.19, 0.11, 0.075), (0.34, 0.25, 0.19)),
        "ventral": ((0.085, 0.070, 0.055), (0.31, 0.25, 0.18), (0.52, 0.43, 0.31)),
        "wing": ((0.040, 0.012, 0.012), (0.22, 0.045, 0.035), (0.38, 0.11, 0.075)),
        "horn": ((0.035, 0.026, 0.020), (0.22, 0.16, 0.105), (0.48, 0.38, 0.25)),
        "scar": ((0.055, 0.010, 0.008), (0.30, 0.045, 0.030), (0.48, 0.12, 0.07)),
    }
    low, mid, high = palettes[palette]
    t = np.clip(height * 0.72 + ridges * 0.28, 0.0, 1.0)
    base = np.empty((size, size, 4), dtype=np.float32)
    for channel in range(3):
        c0, c1, c2 = low[channel], mid[channel], high[channel]
        first = c0 + (c1 - c0) * np.clip(t * 1.55, 0.0, 1.0)
        second_mix = np.clip((t - 0.56) / 0.44, 0.0, 1.0)
        base[..., channel] = first + (c2 - c1) * second_mix * 0.55
    base[..., 3] = 1.0

    roughness = np.clip(0.92 - height * 0.25 + micro * 0.04, 0.42, 0.94)
    orm = np.zeros((size, size, 4), dtype=np.float32)
    orm[..., 0] = np.clip(0.62 + height * 0.34, 0.0, 1.0)  # AO
    orm[..., 1] = roughness
    orm[..., 2] = 0.0
    orm[..., 3] = 1.0

    grad_y, grad_x = np.gradient(height)
    normal_strength = 5.8 if palette in {"body", "ventral"} else 3.6
    nx = -grad_x * normal_strength
    ny = -grad_y * normal_strength
    nz = np.ones_like(nx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.empty((size, size, 4), dtype=np.float32)
    normal[..., 0] = nx / length * 0.5 + 0.5
    normal[..., 1] = ny / length * 0.5 + 0.5
    normal[..., 2] = nz / length * 0.5 + 0.5
    normal[..., 3] = 1.0

    paths = {
        "base_color": directory / f"{stem}_base_color.png",
        "normal": directory / f"{stem}_normal.png",
        "orm": directory / f"{stem}_orm.png",
    }
    _write_blender_image(f"T_{stem}_BaseColor", base, paths["base_color"], "sRGB")
    _write_blender_image(f"T_{stem}_Normal", normal, paths["normal"], "Non-Color")
    _write_blender_image(f"T_{stem}_ORM", orm, paths["orm"], "Non-Color")
    return paths


def _write_blender_image(name: str, rgba: np.ndarray, path: Path, colorspace: str) -> None:
    height, width, channels = rgba.shape
    if channels != 4:
        raise ValueError("Texture array must be RGBA")
    existing = bpy.data.images.get(name)
    if existing is not None:
        bpy.data.images.remove(existing)
    image = bpy.data.images.new(name=name, width=width, height=height, alpha=True, float_buffer=False)
    pixels = np.ascontiguousarray(np.clip(rgba, 0.0, 1.0), dtype=np.float32).ravel()
    image.pixels.foreach_set(pixels)
    image.update()
    try:
        image.colorspace_settings.name = colorspace
    except TypeError:
        pass
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    image.reload()

    verification = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(verification)
    rgb = verification.reshape((-1, 4))[:, :3]
    dynamic_range = float(rgb.max() - rgb.min())
    if not np.isfinite(rgb).all() or dynamic_range < 1e-4:
        raise RuntimeError(
            f"Texture write verification failed for {path}: dynamic_range={dynamic_range:.8f}"
        )


def _load_image(path: Path, colorspace: str) -> bpy.types.Image:
    image = bpy.data.images.load(str(path), check_existing=True)
    try:
        image.colorspace_settings.name = colorspace
    except TypeError:
        pass
    return image


def _pbr_material(
    name: str,
    texture_set: dict[str, Path],
    roughness: float,
    double_sided: bool = False,
    subsurface: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.use_backface_culling = not double_sided
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (620, 0)
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (310, 0)
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = 0.0
    if "Subsurface Weight" in principled.inputs:
        principled.inputs["Subsurface Weight"].default_value = subsurface
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    tex_base = nodes.new("ShaderNodeTexImage")
    tex_base.name = f"{name}_BaseColor"
    tex_base.image = _load_image(texture_set["base_color"], "sRGB")
    tex_base.location = (-520, 180)
    links.new(tex_base.outputs["Color"], principled.inputs["Base Color"])

    tex_orm = nodes.new("ShaderNodeTexImage")
    tex_orm.name = f"{name}_ORM"
    tex_orm.image = _load_image(texture_set["orm"], "Non-Color")
    tex_orm.location = (-520, -80)
    separate = nodes.new("ShaderNodeSeparateColor")
    separate.mode = "RGB"
    separate.location = (-260, -70)
    links.new(tex_orm.outputs["Color"], separate.inputs["Color"])
    links.new(separate.outputs["Green"], principled.inputs["Roughness"])
    links.new(separate.outputs["Blue"], principled.inputs["Metallic"])

    tex_normal = nodes.new("ShaderNodeTexImage")
    tex_normal.name = f"{name}_Normal"
    tex_normal.image = _load_image(texture_set["normal"], "Non-Color")
    tex_normal.location = (-520, -330)
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.location = (-235, -320)
    normal_map.inputs["Strength"].default_value = 0.72
    links.new(tex_normal.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
    return material


def _simple_material(
    name: str,
    base_color: tuple[float, float, float, float],
    metallic: float,
    roughness: float,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.use_backface_culling = False
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is None:
        material.node_tree.nodes.clear()
        principled = material.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        output = material.node_tree.nodes.new("ShaderNodeOutputMaterial")
        material.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    principled.inputs["Base Color"].default_value = base_color
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    if emission is not None:
        emission_input = principled.inputs.get("Emission Color") or principled.inputs.get("Emission")
        if emission_input is not None:
            emission_input.default_value = emission
        strength_input = principled.inputs.get("Emission Strength")
        if strength_input is not None:
            strength_input.default_value = emission_strength
    return material
