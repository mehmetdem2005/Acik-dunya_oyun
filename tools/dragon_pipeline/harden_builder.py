#!/usr/bin/env python3
"""Apply asserted production QA upgrades to the reconstructed Blender builder."""
from __future__ import annotations

from pathlib import Path
import argparse
import py_compile


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return source.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    path = args.path
    source = path.read_text(encoding="utf-8")

    source = replace_once(
        source,
        '    "Dragon_LOD4": 0.035,',
        '    "Dragon_LOD4": 0.032,',
        "LOD4 ratio",
    )
    source = replace_once(
        source,
        '        36, lod0, materials["M_Dragon_Head"], cap_start=False,',
        '        36, lod0, materials["M_Dragon_Head"], cap_start=True,',
        "closed snout topology",
    )

    duplicate_block = '''def duplicate_object(obj: bpy.types.Object, collection: bpy.types.Collection, name: str) -> bpy.types.Object:\n    clone = obj.copy()\n    if obj.data:\n        clone.data = obj.data.copy()\n    clone.name = name\n    collection.objects.link(clone)\n    return clone\n\n\n# -----------------------------------------------------------------------------\n# Material system\n# -----------------------------------------------------------------------------\n'''
    hardened_duplicate_block = '''def duplicate_object(obj: bpy.types.Object, collection: bpy.types.Collection, name: str) -> bpy.types.Object:\n    clone = obj.copy()\n    if obj.data:\n        clone.data = obj.data.copy()\n    clone.name = name\n    collection.objects.link(clone)\n    return clone\n\n\ndef limit_vertex_influences(obj: bpy.types.Object, maximum: int = 4, epsilon: float = 1e-6) -> None:\n    \"\"\"Prune decimation-interpolated weights and normalize the survivors.\"\"\"\n    if obj.type != \"MESH\" or not obj.vertex_groups:\n        return\n    for vertex in obj.data.vertices:\n        active = [(ref.group, ref.weight) for ref in vertex.groups if ref.weight > epsilon]\n        if not active:\n            continue\n        active.sort(key=lambda item: item[1], reverse=True)\n        keep = active[:maximum]\n        for group_index, _weight in active[maximum:]:\n            obj.vertex_groups[group_index].remove([vertex.index])\n        total = sum(weight for _group_index, weight in keep)\n        if total <= epsilon:\n            continue\n        for group_index, weight in keep:\n            obj.vertex_groups[group_index].add([vertex.index], weight / total, \"REPLACE\")\n\n\n# -----------------------------------------------------------------------------\n# Material system\n# -----------------------------------------------------------------------------\n'''
    source = replace_once(source, duplicate_block, hardened_duplicate_block, "influence limiter")

    source = replace_once(
        source,
        '                decimate.use_collapse_triangulate = True\n                bpy.context.view_layer.objects.active = clone',
        '                decimate.use_collapse_triangulate = True\n                decimate_index = clone.modifiers.find(decimate.name)\n                if decimate_index > 0:\n                    clone.modifiers.move(decimate_index, 0)\n                bpy.context.view_layer.objects.active = clone',
        "decimate modifier ordering",
    )
    source = replace_once(
        source,
        '            clone["lod_group"] = lod_name\n            clones.append(clone)',
        '            limit_vertex_influences(clone, maximum=4)\n            clone["lod_group"] = lod_name\n            clones.append(clone)',
        "LOD influence cleanup",
    )
    source = replace_once(
        source,
        '            findings.append(Finding("WARNING", "NON_MANIFOLD", obj.name, f"{non_manifold} non-manifold edges."))',
        '            findings.append(Finding("ERROR", "NON_MANIFOLD", obj.name, f"{non_manifold} non-manifold edges."))',
        "non-manifold quality gate",
    )

    triangle_block = '''    triangle_counts = {}\n    for key in ("LOD0", "Dragon_LOD1", "Dragon_LOD2", "Dragon_LOD3", "Dragon_LOD4", "Dragon_Mobile"):\n        collection = collections[key]\n        triangle_counts[key] = sum(object_triangle_count(obj) for obj in collection.objects if obj.type == "MESH")\n\n    return {\n'''
    hardened_triangle_block = '''    triangle_counts = {}\n    for key in ("LOD0", "Dragon_LOD1", "Dragon_LOD2", "Dragon_LOD3", "Dragon_LOD4", "Dragon_Mobile"):\n        collection = collections[key]\n        triangle_counts[key] = sum(object_triangle_count(obj) for obj in collection.objects if obj.type == "MESH")\n\n    lod_budgets = {\n        "LOD0": (180_000, 250_000),\n        "Dragon_LOD1": (90_000, 130_000),\n        "Dragon_LOD2": (40_000, 65_000),\n        "Dragon_LOD3": (15_000, 25_000),\n        "Dragon_LOD4": (5_000, 10_000),\n        "Dragon_Mobile": (50_000, 80_000),\n    }\n    for lod_name, (minimum, maximum) in lod_budgets.items():\n        count = triangle_counts[lod_name]\n        if not minimum <= count <= maximum:\n            findings.append(Finding(\n                "ERROR", "LOD_BUDGET", lod_name,\n                f"{count} triangles outside required range {minimum}-{maximum}."\n            ))\n\n    return {\n'''
    source = replace_once(source, triangle_block, hardened_triangle_block, "LOD budget gate")

    path.write_text(source, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    print(f"Hardened Blender builder: {path}")


if __name__ == "__main__":
    main()
