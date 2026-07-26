from __future__ import annotations

from pathlib import Path

TARGET = Path("tools/dragon_production/lod_collision.py")


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"Patch anchor {label!r} expected once, found {source.count(old)}")
    return source.replace(old, new, 1)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    source = _replace_once(source, "import bpy\n", "import bmesh\nimport bpy\n", "bmesh import")
    source = _replace_once(
        source,
        '''        _apply_modifier(duplicate, decimate.name)\n        arm_mod = duplicate.modifiers.new(name="Armature", type="ARMATURE")\n''',
        '''        _apply_modifier(duplicate, decimate.name)\n        _remove_loose_geometry(duplicate)\n        _limit_and_normalize_influences(duplicate, limit=4)\n        arm_mod = duplicate.modifiers.new(name="Armature", type="ARMATURE")\n''',
        "LOD cleanup call",
    )
    helpers = '''\n\ndef _remove_loose_geometry(obj: bpy.types.Object) -> None:\n    \"\"\"Remove decimation artifacts without touching valid boundary edges.\"\"\"\n    mesh = obj.data\n    bm = bmesh.new()\n    bm.from_mesh(mesh)\n    bm.normal_update()\n\n    loose_edges = [edge for edge in bm.edges if not edge.link_faces]\n    if loose_edges:\n        bmesh.ops.delete(bm, geom=loose_edges, context=\"EDGES\")\n\n    loose_vertices = [vertex for vertex in bm.verts if not vertex.link_edges]\n    if loose_vertices:\n        bmesh.ops.delete(bm, geom=loose_vertices, context=\"VERTS\")\n\n    bm.to_mesh(mesh)\n    bm.free()\n    mesh.update(calc_edges=True, calc_edges_loose=True)\n\n\ndef _limit_and_normalize_influences(obj: bpy.types.Object, limit: int) -> None:\n    \"\"\"Enforce the glTF/Godot four-influence skinning contract deterministically.\"\"\"\n    groups = {group.index: group for group in obj.vertex_groups}\n    for vertex in obj.data.vertices:\n        influences = sorted(\n            ((entry.group, float(entry.weight)) for entry in vertex.groups if entry.weight > 1e-8),\n            key=lambda item: item[1],\n            reverse=True,\n        )\n        kept = influences[:limit]\n        discarded = influences[limit:]\n        for group_index, _ in discarded:\n            group = groups.get(group_index)\n            if group is not None:\n                group.remove([vertex.index])\n\n        total = sum(weight for _, weight in kept)\n        if total <= 1e-8:\n            continue\n        for group_index, weight in kept:\n            group = groups.get(group_index)\n            if group is not None:\n                group.add([vertex.index], weight / total, \"REPLACE\")\n\n'''
    source = _replace_once(
        source,
        "\ndef _apply_modifier(obj: bpy.types.Object, modifier_name: str) -> None:\n",
        helpers + "\ndef _apply_modifier(obj: bpy.types.Object, modifier_name: str) -> None:\n",
        "LOD helper insertion",
    )
    TARGET.write_text(source, encoding="utf-8")
    print(f"Patched {TARGET}")


if __name__ == "__main__":
    main()
