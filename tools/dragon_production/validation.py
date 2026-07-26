from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json

import bmesh
import bpy

from .config import COLLISION_PARTS, MATERIAL_NAMES, REQUIRED_ACTIONS, SKELETON_NAME


@dataclass
class Finding:
    severity: str
    code: str
    subject: str
    message: str


def validate_scene(output_path: Path | None = None) -> dict:
    findings: list[Finding] = []
    required_objects = {
        "Dragon_Root",
        SKELETON_NAME,
        "Dragon_LOD0",
        "Dragon_LOD1",
        "Dragon_LOD2",
        "Dragon_LOD3",
        "Dragon_LOD4",
        "Dragon_Mobile",
        "Dragon_Eyes",
        "Dragon_Teeth",
        "Dragon_Tongue",
        "Dragon_Horns",
        "Dragon_Collision",
        "Dragon_ShadowProxy",
    }

    missing_objects = sorted(required_objects - set(bpy.data.objects.keys()))
    for name in missing_objects:
        findings.append(Finding("ERROR", "MISSING_OBJECT", name, "Required asset node is missing."))

    missing_materials = sorted(set(MATERIAL_NAMES) - set(bpy.data.materials.keys()))
    for name in missing_materials:
        findings.append(Finding("ERROR", "MISSING_MATERIAL", name, "Required PBR material is missing."))

    missing_actions = sorted(set(REQUIRED_ACTIONS) - set(bpy.data.actions.keys()))
    for name in missing_actions:
        findings.append(Finding("ERROR", "MISSING_ACTION", name, "Required animation clip is missing."))

    for collision_name in COLLISION_PARTS:
        if collision_name not in bpy.data.objects:
            findings.append(Finding("ERROR", "MISSING_COLLISION", collision_name, "Required collision proxy is missing."))

    triangle_counts: dict[str, int] = {}
    vertex_counts: dict[str, int] = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.name.startswith("Preview_"):
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        triangle_counts[obj.name] = len(mesh.loop_triangles)
        vertex_counts[obj.name] = len(mesh.vertices)

        if obj.name.startswith("Dragon_LOD") or obj.name in {"Dragon_Mobile", "Dragon_Eyes", "Dragon_Teeth", "Dragon_Tongue", "Dragon_Horns"}:
            findings.extend(_validate_mesh(obj))
            findings.extend(_validate_skin(obj))

    lod_names = ["Dragon_LOD0", "Dragon_LOD1", "Dragon_LOD2", "Dragon_LOD3", "Dragon_LOD4"]
    lod_counts = [triangle_counts.get(name, 0) for name in lod_names]
    if any(count <= 0 for count in lod_counts):
        findings.append(Finding("ERROR", "LOD_EMPTY", "LODs", f"Invalid LOD triangle counts: {lod_counts}"))
    elif any(lod_counts[i] <= lod_counts[i + 1] for i in range(len(lod_counts) - 1)):
        findings.append(Finding("ERROR", "LOD_ORDER", "LODs", f"LOD triangle counts are not strictly descending: {lod_counts}"))

    if triangle_counts.get("Dragon_LOD0", 0) < 18000:
        findings.append(Finding(
            "WARNING",
            "LOD0_DETAIL_DENSITY",
            "Dragon_LOD0",
            f"LOD0 has {triangle_counts.get('Dragon_LOD0', 0)} triangles; visual review is required for close cinematic use.",
        ))

    armature = bpy.data.objects.get(SKELETON_NAME)
    bone_count = 0
    if armature is None or armature.type != "ARMATURE":
        findings.append(Finding("ERROR", "MISSING_ARMATURE", SKELETON_NAME, "Deformation armature is missing."))
    else:
        bone_count = len(armature.data.bones)
        if bone_count < 60:
            findings.append(Finding("WARNING", "LOW_BONE_COUNT", SKELETON_NAME, f"Skeleton has only {bone_count} bones."))

    action_stats = {}
    for name in REQUIRED_ACTIONS:
        action = bpy.data.actions.get(name)
        if action is None:
            continue
        keyframes = [
            float(point.co.x)
            for fcurve in action.fcurves
            for point in fcurve.keyframe_points
        ]
        frame_start = min(keyframes) if keyframes else 0.0
        frame_end = max(keyframes) if keyframes else 0.0
        action_stats[name] = {
            "frame_start": frame_start,
            "frame_end": frame_end,
            "duration_frames": max(0.0, frame_end - frame_start),
            "fcurves": len(action.fcurves),
            "keyframes": len(keyframes),
            "loop": bool(action.get("loop", False)),
        }
        if len(action.fcurves) == 0 or not keyframes:
            findings.append(Finding("ERROR", "EMPTY_ACTION", name, "Animation action contains no keyed curves."))
        elif frame_end <= frame_start:
            findings.append(Finding("ERROR", "ZERO_DURATION_ACTION", name, f"Invalid frame range {frame_start}..{frame_end}."))

    errors = sum(1 for finding in findings if finding.severity == "ERROR")
    warnings = sum(1 for finding in findings if finding.severity == "WARNING")
    report = {
        "asset": "Dragon_Master",
        "target_engine": "Godot 4.6",
        "format": "glTF 2.0 metallic-roughness",
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "mesh_objects": len(triangle_counts),
            "bones": bone_count,
            "actions": len(action_stats),
        },
        "triangle_counts": triangle_counts,
        "vertex_counts": vertex_counts,
        "actions": action_stats,
        "materials": sorted(name for name in bpy.data.materials.keys() if name.startswith("M_Dragon_")),
        "findings": [asdict(finding) for finding in findings],
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _validate_mesh(obj: bpy.types.Object) -> list[Finding]:
    findings: list[Finding] = []
    mesh = obj.data
    if "UV0" not in mesh.uv_layers:
        findings.append(Finding("ERROR", "MISSING_UV0", obj.name, "UV0 is required."))
    if "UV1" not in mesh.uv_layers:
        findings.append(Finding("ERROR", "MISSING_UV1", obj.name, "UV1 is required."))

    if any(abs(value - 1.0) > 1e-5 for value in obj.scale):
        findings.append(Finding("ERROR", "UNAPPLIED_SCALE", obj.name, f"Scale is {tuple(obj.scale)}"))
    if obj.scale.x < 0 or obj.scale.y < 0 or obj.scale.z < 0:
        findings.append(Finding("ERROR", "NEGATIVE_SCALE", obj.name, "Negative scale is forbidden."))

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    zero_area = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
    if zero_area:
        findings.append(Finding("ERROR", "ZERO_AREA_FACE", obj.name, f"{zero_area} zero-area faces detected."))
    wire_edges = sum(1 for edge in bm.edges if len(edge.link_faces) == 0)
    if wire_edges:
        findings.append(Finding("ERROR", "WIRE_EDGES", obj.name, f"{wire_edges} wire edges detected."))
    bm.free()
    return findings


def _validate_skin(obj: bpy.types.Object) -> list[Finding]:
    findings: list[Finding] = []
    group_names = {group.index: group.name for group in obj.vertex_groups}
    unweighted = 0
    too_many = 0
    non_normalized = 0
    for vertex in obj.data.vertices:
        influences = [(group_names.get(entry.group, ""), entry.weight) for entry in vertex.groups if entry.weight > 1e-6]
        if not influences:
            unweighted += 1
            continue
        if len(influences) > 4:
            too_many += 1
        total = sum(weight for _, weight in influences)
        if abs(total - 1.0) > 0.025:
            non_normalized += 1
    if unweighted:
        findings.append(Finding("ERROR", "UNWEIGHTED_VERTICES", obj.name, f"{unweighted} vertices have no skin influence."))
    if too_many:
        findings.append(Finding("ERROR", "TOO_MANY_INFLUENCES", obj.name, f"{too_many} vertices exceed four bone influences."))
    if non_normalized:
        findings.append(Finding("WARNING", "NON_NORMALIZED_WEIGHTS", obj.name, f"{non_normalized} vertices have non-normalized weights."))
    return findings
