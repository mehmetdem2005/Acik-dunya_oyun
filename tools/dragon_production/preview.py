from __future__ import annotations

from pathlib import Path
import math

import bpy
from mathutils import Vector


def setup_preview_scene(collection: bpy.types.Collection) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.render.use_file_extension = True
    scene.view_settings.look = "AgX - Medium High Contrast"

    world = scene.world or bpy.data.worlds.new("DragonPreviewWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.010, 0.012, 0.016, 1.0)
    background.inputs["Strength"].default_value = 0.28

    bpy.ops.object.camera_add(location=(10.5, -15.5, 8.4))
    camera = bpy.context.object
    camera.name = "Preview_Camera"
    _move_to_collection(camera, collection)
    camera.data.lens = 58.0
    camera.data.sensor_width = 36.0
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 18.0
    camera.data.dof.aperture_fstop = 5.6
    scene.camera = camera

    lights: list[bpy.types.Object] = []
    lights.append(_area_light(collection, "Key_Light", (6.5, -8.0, 11.0), 1800.0, 7.0, (1.0, 0.72, 0.54)))
    lights.append(_area_light(collection, "Fill_Light", (-7.0, -3.0, 7.0), 1000.0, 6.0, (0.45, 0.60, 1.0)))
    lights.append(_area_light(collection, "Rim_Light", (2.5, 7.0, 9.5), 1500.0, 5.0, (0.85, 0.25, 0.12)))

    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "Preview_Floor"
    _move_to_collection(floor, collection)
    floor_material = bpy.data.materials.new("M_Preview_Floor")
    floor_material.use_nodes = True
    bsdf = floor_material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.018, 0.020, 0.024, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.78
    floor.data.materials.append(floor_material)

    return camera, lights + [floor]


def render_previews(camera: bpy.types.Object, output_dir: Path, size: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.resolution_percentage = 100

    shots = {
        "preview_hero.png": ((10.8, -15.8, 8.6), (0.0, 0.1, 3.75), 58.0),
        "preview_side.png": ((14.5, 1.0, 6.6), (0.0, 0.7, 3.35), 62.0),
        "preview_front.png": ((0.0, -18.0, 6.9), (0.0, -0.8, 3.55), 66.0),
    }
    outputs: list[Path] = []
    for filename, (location, target, lens) in shots.items():
        camera.location = location
        camera.data.lens = lens
        _look_at(camera, Vector(target))
        path = output_dir / filename
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs.append(path)
    return outputs


def _area_light(
    collection: bpy.types.Collection,
    name: str,
    location: tuple[float, float, float],
    energy: float,
    size: float,
    color: tuple[float, float, float],
) -> bpy.types.Object:
    data = bpy.data.lights.new(name=f"{name}_Data", type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    _look_at(obj, Vector((0.0, 0.0, 3.6)))
    return obj


def _look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)
