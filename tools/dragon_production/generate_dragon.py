from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
import traceback

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from dragon_production.animations import build_all_actions
from dragon_production.config import BuildSettings, ROOT_NAME
from dragon_production.export_asset import export_gltf_assets, save_blend, write_manifest
from dragon_production.gltf_validation import validate_gltf_payload
from dragon_production.lod_collision import build_collision_proxies, build_lods
from dragon_production.materials import build_materials
from dragon_production.model_builder import build_dragon_geometry
from dragon_production.preview import render_previews, setup_preview_scene
from dragon_production.rig import build_armature
from dragon_production.validation import validate_scene


def main() -> int:
    args = _parse_args()
    settings = BuildSettings(
        output_dir=Path(args.output).resolve(),
        texture_size=args.texture_size,
        preview_size=args.preview_size,
        render_previews=not args.no_previews,
        export_gltf_separate=not args.glb_only,
        export_glb=True,
        seed=args.seed,
    )
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.textures_dir.mkdir(parents=True, exist_ok=True)
    settings.previews_dir.mkdir(parents=True, exist_ok=True)

    try:
        _reset_scene()
        collections = _build_collection_tree()
        root = bpy.data.objects.new(ROOT_NAME, None)
        collections["asset"].objects.link(root)
        root.empty_display_type = "PLAIN_AXES"
        root.empty_display_size = 1.0
        root["asset"] = "Dragon_Master"
        root["target_engine"] = "Godot 4.6"
        root["units"] = "meters"
        root["forward"] = "-Y authoring / -Z glTF"
        root["up"] = "+Z authoring / +Y glTF"

        collision_root = bpy.data.objects.new("Dragon_Collision", None)
        collections["collision"].objects.link(collision_root)
        collision_root.parent = root
        collision_root.empty_display_type = "CUBE"
        collision_root.empty_display_size = 0.7
        collision_root["asset_role"] = "collision_container"

        materials = build_materials(settings.textures_dir, settings.texture_size)
        armature = build_armature(collections["rig"], root)
        geometry = build_dragon_geometry(
            collections["render"],
            collections["detail"],
            armature,
            materials,
            settings.seed,
        )
        lods = build_lods(geometry["Dragon_LOD0"].object, collections["lod"], armature)
        collisions = build_collision_proxies(
            collections["collision"],
            collision_root,
            armature,
            materials,
        )
        actions = build_all_actions(armature)

        qa_path = settings.output_dir / "dragon_qa_report.json"
        qa_report = validate_scene(qa_path)
        if qa_report["summary"]["errors"]:
            raise RuntimeError(
                f"Production QA failed with {qa_report['summary']['errors']} errors. "
                f"See {qa_path}."
            )

        blend_path = save_blend(settings.output_dir)
        export_paths = export_gltf_assets(
            settings.output_dir,
            export_separate=settings.export_gltf_separate,
            export_glb=settings.export_glb,
        )
        gltf_qa_path = settings.output_dir / "dragon_gltf_qa_report.json"
        gltf_qa_report = validate_gltf_payload(
            settings.output_dir / "dragon_master.gltf",
            settings.output_dir / "dragon_master.bin",
            settings.output_dir / "dragon_master.glb",
            gltf_qa_path,
        )
        if gltf_qa_report["summary"]["errors"]:
            raise RuntimeError(
                f"glTF QA failed with {gltf_qa_report['summary']['errors']} errors. "
                f"See {gltf_qa_path}."
            )

        preview_paths: list[Path] = []
        if settings.render_previews:
            camera, _ = setup_preview_scene(collections["preview"])
            preview_paths = render_previews(camera, settings.previews_dir, settings.preview_size)
            blend_path = save_blend(settings.output_dir)

        manifest_path = write_manifest(
            settings.output_dir,
            qa_report,
            export_paths,
            gltf_qa_report,
        )

        build_summary = {
            "status": "success",
            "blend": str(blend_path),
            "exports": export_paths,
            "manifest": str(manifest_path),
            "qa": str(qa_path),
            "gltf_qa": str(gltf_qa_path),
            "previews": [str(path) for path in preview_paths],
            "objects": sorted(geometry.keys()),
            "lods": sorted(lods.keys()),
            "collisions": sorted(collisions.keys()),
            "actions": sorted(actions.keys()),
        }
        (settings.output_dir / "dragon_build_summary.json").write_text(
            json.dumps(build_summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print("DRAGON_BUILD_SUCCESS")
        print(json.dumps(build_summary, indent=2, ensure_ascii=False))
        return 0
    except Exception:
        traceback.print_exc()
        failure = {
            "status": "failed",
            "traceback": traceback.format_exc(),
        }
        (settings.output_dir / "dragon_build_failure.json").write_text(
            json.dumps(failure, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return 1


def _reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = 120
    scene.gravity = (0.0, 0.0, -9.81)


def _build_collection_tree() -> dict[str, bpy.types.Collection]:
    scene_root = bpy.context.scene.collection
    asset = bpy.data.collections.new("Dragon_Asset")
    scene_root.children.link(asset)

    collections = {"asset": asset}
    for key, name in (
        ("render", "10_Render"),
        ("detail", "20_Detail"),
        ("rig", "30_Rig"),
        ("lod", "40_LODs"),
        ("collision", "50_Collision"),
    ):
        collection = bpy.data.collections.new(name)
        asset.children.link(collection)
        collections[key] = collection

    preview = bpy.data.collections.new("90_Preview")
    scene_root.children.link(preview)
    collections["preview"] = preview
    return collections


def _parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Build the production dragon asset in Blender.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--texture-size", type=int, default=1024)
    parser.add_argument("--preview-size", type=int, default=768)
    parser.add_argument("--seed", type=int, default=731992)
    parser.add_argument("--no-previews", action="store_true")
    parser.add_argument("--glb-only", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
