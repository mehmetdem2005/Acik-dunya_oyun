from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from dragon_production.gltf_validation import validate_gltf_payload
from dragon_production.validation import validate_scene


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output).resolve()
    scene_report_path = output_dir / "dragon_qa_reopen_report.json"
    scene_report = validate_scene(scene_report_path)

    required_files = [
        output_dir / "dragon_master.blend",
        output_dir / "dragon_master.glb",
        output_dir / "dragon_asset_manifest.json",
        output_dir / "dragon_qa_report.json",
        output_dir / "dragon_gltf_qa_report.json",
    ]
    if not args.glb_only:
        required_files.extend([
            output_dir / "dragon_master.gltf",
            output_dir / "dragon_master.bin",
        ])
    missing = [str(path) for path in required_files if not path.exists() or path.stat().st_size == 0]
    if missing:
        scene_report.setdefault("external_file_errors", []).append({"missing_or_empty": missing})
        scene_report["summary"]["errors"] += len(missing)
        scene_report_path.write_text(json.dumps(scene_report, indent=2, ensure_ascii=False), encoding="utf-8")

    gltf_report_path = output_dir / "dragon_gltf_qa_reopen_report.json"
    gltf_report = validate_gltf_payload(
        output_dir / "dragon_master.gltf",
        output_dir / "dragon_master.bin",
        output_dir / "dragon_master.glb",
        gltf_report_path,
    )

    combined = {
        "scene": scene_report["summary"],
        "gltf": gltf_report["summary"],
        "errors": scene_report["summary"]["errors"] + gltf_report["summary"]["errors"],
        "warnings": scene_report["summary"]["warnings"] + gltf_report["summary"]["warnings"],
    }
    print(json.dumps(combined, indent=2))
    if combined["errors"]:
        print(f"DRAGON_VALIDATION_FAILED: {scene_report_path}, {gltf_report_path}")
        return 1
    print("DRAGON_VALIDATION_SUCCESS")
    return 0


def _parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--glb-only", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
