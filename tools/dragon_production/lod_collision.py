from __future__ import annotations

import bmesh
import bpy
from mathutils import Vector

from .config import COLLISION_PARTS, LOD_RATIOS, LOD_DISTANCE_HINTS_M, MATERIAL_NAMES
from .geometry import MeshAssembler, MeshBuildResult


def build_lods(
    source: bpy.types.Object,
    lod_collection: bpy.types.Collection,
    armature: bpy.types.Object,
) -> dict[str, bpy.types.Object]:
    lods: dict[str, bpy.types.Object] = {"Dragon_LOD0": source}
    for name, ratio in LOD_RATIOS.items():
        if name == "Dragon_LOD0":
            source["lod_ratio"] = 1.0
            source["distance_hint_m"] = LOD_DISTANCE_HINTS_M[name]
            continue
        duplicate = source.copy()
        duplicate.data = source.data.copy()
        duplicate.name = name
        duplicate.data.name = f"{name}_Mesh"
        lod_collection.objects.link(duplicate)
        duplicate.parent = armature
        duplicate.animation_data_clear()
        for modifier in list(duplicate.modifiers):
            duplicate.modifiers.remove(modifier)

        decimate = duplicate.modifiers.new(name="Production_Decimate", type="DECIMATE")
        decimate.decimate_type = "COLLAPSE"
        decimate.ratio = ratio
        decimate.use_collapse_triangulate = True
        decimate.use_symmetry = True
        decimate.symmetry_axis = "X"

        _apply_modifier(duplicate, decimate.name)
        _remove_loose_geometry(duplicate)
        _limit_and_normalize_influences(duplicate, limit=4)
        arm_mod = duplicate.modifiers.new(name="Armature", type="ARMATURE")
        arm_mod.object = armature
        arm_mod.use_deform_preserve_volume = True

        duplicate["asset_role"] = "render_lod"
        duplicate["lod_index"] = _lod_index(name)
        duplicate["lod_ratio"] = ratio
        duplicate["distance_hint_m"] = LOD_DISTANCE_HINTS_M[name]
        duplicate.hide_render = True
        duplicate.hide_set(True)
        lods[name] = duplicate

    shadow = lods["Dragon_LOD4"].copy()
    shadow.data = lods["Dragon_LOD4"].data.copy()
    shadow.name = "Dragon_ShadowProxy"
    shadow.data.name = "Dragon_ShadowProxy_Mesh"
    lod_collection.objects.link(shadow)
    shadow.parent = armature
    shadow["asset_role"] = "shadow_proxy"
    shadow.hide_render = True
    shadow.hide_set(True)
    lods["Dragon_ShadowProxy"] = shadow
    return lods


def build_collision_proxies(
    collision_collection: bpy.types.Collection,
    collision_root: bpy.types.Object,
    armature: bpy.types.Object,
    materials: dict[str, bpy.types.Material],
) -> dict[str, MeshBuildResult]:
    results: dict[str, MeshBuildResult] = {}

    def ellipsoid(name: str, center: Vector, radii: Vector, bone: str) -> None:
        builder = MeshAssembler(MATERIAL_NAMES)
        builder.add_uv_ellipsoid(
            center,
            radii,
            rings=8,
            segments=12,
            material="M_Dragon_Body",
            weights=lambda co, b=bone: {b: 1.0},
        )
        result = builder.to_object(name, collision_collection, materials, armature)
        _mark_collision(result.object, collision_root, name)
        results[name] = result

    def capsule(name: str, start: Vector, end: Vector, radius: float, bone: str) -> None:
        builder = MeshAssembler(MATERIAL_NAMES)
        builder.add_cylinder_between(
            start,
            end,
            (radius, radius),
            (radius * 0.92, radius * 0.92),
            segments=10,
            material="M_Dragon_Body",
            bone_name=bone,
        )
        result = builder.to_object(name, collision_collection, materials, armature)
        _mark_collision(result.object, collision_root, name)
        results[name] = result

    ellipsoid("Head_Collision", Vector((0.0, -4.02, 6.58)), Vector((0.58, 0.88, 0.58)), "Head")
    capsule("Neck_Collision", Vector((0.0, -1.72, 4.12)), Vector((0.0, -3.20, 6.45)), 0.56, "Neck_03")
    ellipsoid("Chest_Collision", Vector((0.0, -1.12, 3.64)), Vector((1.18, 1.42, 1.18)), "Chest")
    ellipsoid("Pelvis_Collision", Vector((0.0, 0.62, 3.00)), Vector((1.16, 1.15, 1.02)), "Pelvis")
    capsule("Tail_Collision_01", Vector((0.0, 0.72, 2.90)), Vector((0.0, 3.20, 2.54)), 0.48, "Tail_02")
    capsule("Tail_Collision_02", Vector((0.0, 3.20, 2.54)), Vector((0.0, 5.75, 1.72)), 0.31, "Tail_05")
    capsule("Tail_Collision_03", Vector((0.0, 5.75, 1.72)), Vector((0.0, 8.18, 0.73)), 0.16, "Tail_08")

    for side, sign in (("L", 1.0), ("R", -1.0)):
        capsule(
            f"FrontLeg_Collision_{side}",
            Vector((0.90 * sign, -1.55, 3.30)),
            Vector((0.92 * sign, -2.06, 0.35)),
            0.26,
            f"FrontLeg_{side}_Fore",
        )
        capsule(
            f"RearLeg_Collision_{side}",
            Vector((0.95 * sign, 1.12, 2.55)),
            Vector((1.02 * sign, 1.24, 0.25)),
            0.31,
            f"RearLeg_{side}_Lower",
        )
        capsule(
            f"Wing_Collision_{side}",
            Vector((0.75 * sign, -1.02, 4.20)),
            Vector((6.15 * sign, -0.02, 6.30)),
            0.13,
            f"Wing_{side}_Forearm",
        )

    missing = set(COLLISION_PARTS) - set(results)
    if missing:
        raise RuntimeError(f"Collision build incomplete: {sorted(missing)}")
    return results


def _mark_collision(obj: bpy.types.Object, root: bpy.types.Object, shape_name: str) -> None:
    obj.parent = root
    obj["asset_role"] = "collision_proxy"
    obj["collision_shape"] = "convex"
    obj["collision_name"] = shape_name
    obj.display_type = "WIRE"
    obj.hide_render = True
    obj.hide_set(True)



def _remove_loose_geometry(obj: bpy.types.Object) -> None:
    """Remove decimation artifacts without touching valid boundary edges."""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()

    loose_edges = [edge for edge in bm.edges if not edge.link_faces]
    if loose_edges:
        bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")

    loose_vertices = [vertex for vertex in bm.verts if not vertex.link_edges]
    if loose_vertices:
        bmesh.ops.delete(bm, geom=loose_vertices, context="VERTS")

    bm.to_mesh(mesh)
    bm.free()
    mesh.update(calc_edges=True, calc_edges_loose=True)


def _limit_and_normalize_influences(obj: bpy.types.Object, limit: int) -> None:
    """Enforce the glTF/Godot four-influence skinning contract deterministically."""
    groups = {group.index: group for group in obj.vertex_groups}
    for vertex in obj.data.vertices:
        influences = sorted(
            ((entry.group, float(entry.weight)) for entry in vertex.groups if entry.weight > 1e-8),
            key=lambda item: item[1],
            reverse=True,
        )
        kept = influences[:limit]
        discarded = influences[limit:]
        for group_index, _ in discarded:
            group = groups.get(group_index)
            if group is not None:
                group.remove([vertex.index])

        total = sum(weight for _, weight in kept)
        if total <= 1e-8:
            continue
        for group_index, weight in kept:
            group = groups.get(group_index)
            if group is not None:
                group.add([vertex.index], weight / total, "REPLACE")


def _apply_modifier(obj: bpy.types.Object, modifier_name: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=modifier_name)
    obj.select_set(False)


def _lod_index(name: str) -> int:
    if name == "Dragon_Mobile":
        return 2
    try:
        return int(name.rsplit("LOD", 1)[1])
    except (IndexError, ValueError):
        return 0
