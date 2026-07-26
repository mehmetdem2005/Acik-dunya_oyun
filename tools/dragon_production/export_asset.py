from __future__ import annotations

from pathlib import Path
import json

import bpy

from .config import REQUIRED_ACTIONS


def save_blend(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    blend_path = output_dir / "dragon_master.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
    return blend_path


def export_gltf_assets(output_dir: Path, export_separate: bool = True, export_glb: bool = True) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected, hidden_states = _select_asset_objects()
    if not selected:
        raise RuntimeError("No Dragon_* objects found for export.")

    result: dict[str, str] = {}
    try:
        if export_separate:
            gltf_path = output_dir / "dragon_master.gltf"
            kwargs = _gltf_kwargs(str(gltf_path), "GLTF_SEPARATE")
            bpy.ops.export_scene.gltf(**kwargs)
            result["gltf"] = str(gltf_path)
            result["bin"] = str(output_dir / "dragon_master.bin")
        if export_glb:
            glb_path = output_dir / "dragon_master.glb"
            kwargs = _gltf_kwargs(str(glb_path), "GLB")
            bpy.ops.export_scene.gltf(**kwargs)
            result["glb"] = str(glb_path)
    finally:
        for obj, (hidden, hidden_viewport, hidden_render) in hidden_states.items():
            obj.hide_set(hidden)
            obj.hide_viewport = hidden_viewport
            obj.hide_render = hidden_render
        bpy.ops.object.select_all(action="DESELECT")
    return result


def write_manifest(
    output_dir: Path,
    qa_report: dict,
    export_paths: dict[str, str],
    gltf_qa_report: dict | None = None,
) -> Path:
    manifest = {
        "asset": "Dragon_Master",
        "version": "1.0.0",
        "target_engine": "Godot 4.6",
        "orientation": {
            "authoring_up": "+Z",
            "authoring_forward": "-Y",
            "gltf_up": "+Y",
            "gltf_forward": "-Z",
            "units": "meters",
        },
        "dimensions_m": {
            "nose_to_tail": 12.7,
            "shoulder_height": 4.05,
            "head_height": 7.95,
            "wingspan_open": 16.9,
        },
        "exports": {key: Path(value).name for key, value in export_paths.items()},
        "required_actions": list(REQUIRED_ACTIONS),
        "qa_summary": qa_report.get("summary", {}),
        "gltf_qa_summary": (gltf_qa_report or {}).get("summary", {}),
        "triangle_counts": qa_report.get("triangle_counts", {}),
        "materials": qa_report.get("materials", []),
        "license_note": "Original procedural production asset generated for this repository from the supplied visual reference.",
    }
    path = output_dir / "dragon_asset_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _select_asset_objects() -> tuple[list[bpy.types.Object], dict[bpy.types.Object, tuple[bool, bool, bool]]]:
    bpy.ops.object.select_all(action="DESELECT")
    selected: list[bpy.types.Object] = []
    hidden_states: dict[bpy.types.Object, tuple[bool, bool, bool]] = {}
    for obj in bpy.data.objects:
        is_named_asset = obj.name.startswith("Dragon_")
        is_collision_proxy = obj.get("asset_role") == "collision_proxy"
        if not (is_named_asset or is_collision_proxy):
            continue
        hidden_states[obj] = (obj.hide_get(), obj.hide_viewport, obj.hide_render)
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_render = False
        obj.select_set(True)
        selected.append(obj)
    if selected:
        bpy.context.view_layer.objects.active = bpy.data.objects.get("Dragon_Root") or selected[0]
    return selected, hidden_states


def _gltf_kwargs(filepath: str, export_format: str) -> dict:
    requested = {
        "filepath": filepath,
        "export_format": export_format,
        "use_selection": True,
        "export_yup": True,
        "export_apply": True,
        "export_cameras": False,
        "export_lights": False,
        "export_extras": True,
        "export_texcoords": True,
        "export_normals": True,
        "export_tangents": True,
        "export_materials": "EXPORT",
        "export_animations": True,
        "export_skins": True,
        "export_morph": True,
        "export_def_bones": True,
        "export_force_sampling": True,
        "export_frame_range": False,
        "export_animation_mode": "ACTIONS",
        "export_nla_strips": True,
        "export_optimize_animation_size": True,
        "export_optimize_animation_keep_anim_armature": True,
        "export_optimize_animation_keep_anim_object": True,
        "export_shared_accessors": True,
        "export_try_sparse_sk": True,
        "export_try_omit_sparse_sk": False,
    }
    operator_type = bpy.ops.export_scene.gltf.get_rna_type()
    supported = {property.identifier for property in operator_type.properties}
    return {key: value for key, value in requested.items() if key in supported}
