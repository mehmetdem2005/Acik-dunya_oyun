from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from dragon_production.validation import validate_scene


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output).resolve()
    report_path = output_dir / "dragon_qa_reopen_report.json"
    report = validate_scene(report_path)

    required_files = [
        output_dir / "dragon_master.blend",
        output_dir / "dragon_master.glb",
        output_dir / "dragon_asset_manifest.json",
        output_dir / "dragon_qa_report.json",
    ]
    if not args.glb_only:
        required_files.extend([
            output_dir / "dragon_master.gltf",
            output_dir / "dragon_master.bin",
        ])
    missing = [str(path) for path in required_files if not path.exists() or path.stat().st_size == 0]
    if missing:
        report.setdefault("external_file_errors", []).append({"missing_or_empty": missing})
        report["summary"]["errors"] += len(missing)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["errors"]:
        print(f"DRAGON_VALIDATION_FAILED: {report_path}")
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
