from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import struct

from .config import COLLISION_PARTS, MATERIAL_NAMES, REQUIRED_ACTIONS


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    subject: str
    message: str


def validate_gltf_payload(
    gltf_path: Path,
    bin_path: Path,
    glb_path: Path,
    output_path: Path | None = None,
) -> dict:
    findings: list[Finding] = []
    payload: dict = {}

    if not gltf_path.exists() or gltf_path.stat().st_size == 0:
        findings.append(Finding("ERROR", "MISSING_GLTF", gltf_path.name, "Separate glTF payload is missing or empty."))
    else:
        try:
            payload = json.loads(gltf_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(Finding("ERROR", "INVALID_GLTF_JSON", gltf_path.name, str(exc)))

    if not bin_path.exists() or bin_path.stat().st_size < 1024:
        findings.append(Finding("ERROR", "INVALID_GLTF_BIN", bin_path.name, "Binary payload is missing or implausibly small."))

    glb_header = _read_glb_header(glb_path, findings)
    node_names: set[str] = set()
    animation_names: list[str] = []
    material_names: set[str] = set()
    skin_joint_counts: list[int] = []
    image_uris: list[str] = []

    if payload:
        nodes = payload.get("nodes", [])
        node_names = {str(node.get("name")) for node in nodes if node.get("name")}
        required_nodes = {
            "Dragon_Root",
            "Dragon_Skeleton",
            "Dragon_LOD0",
            "Dragon_LOD1",
            "Dragon_LOD2",
            "Dragon_LOD3",
            "Dragon_LOD4",
            "Dragon_Mobile",
            "Dragon_ShadowProxy",
            "Dragon_Eyes",
            "Dragon_Horns",
            "Dragon_Teeth",
            "Dragon_Tongue",
            *COLLISION_PARTS,
        }
        for missing in sorted(required_nodes - node_names):
            findings.append(Finding("ERROR", "MISSING_GLTF_NODE", missing, "Required exported node is missing."))

        materials = payload.get("materials", [])
        material_names = {str(material.get("name")) for material in materials if material.get("name")}
        for missing in sorted(set(MATERIAL_NAMES) - material_names):
            findings.append(Finding("ERROR", "MISSING_GLTF_MATERIAL", missing, "Required exported PBR material is missing."))

        animations = payload.get("animations", [])
        animation_names = [str(animation.get("name", "")) for animation in animations]
        missing_actions = sorted(set(REQUIRED_ACTIONS) - set(animation_names))
        extra_actions = sorted(set(animation_names) - set(REQUIRED_ACTIONS))
        for missing in missing_actions:
            findings.append(Finding("ERROR", "MISSING_GLTF_ANIMATION", missing, "Required animation clip was not exported."))
        if extra_actions:
            findings.append(Finding("WARNING", "EXTRA_GLTF_ANIMATIONS", "animations", f"Unexpected clips: {extra_actions}"))
        if len(animation_names) != len(set(animation_names)):
            findings.append(Finding("ERROR", "DUPLICATE_GLTF_ANIMATION", "animations", "Animation names are not unique."))
        _validate_animation_ranges(payload, findings)

        skins = payload.get("skins", [])
        skin_joint_counts = [len(skin.get("joints", [])) for skin in skins]
        if not skins:
            findings.append(Finding("ERROR", "MISSING_GLTF_SKIN", "skins", "No skin was exported."))
        elif max(skin_joint_counts, default=0) < 60:
            findings.append(Finding("ERROR", "INCOMPLETE_GLTF_SKIN", "skins", f"Joint counts are {skin_joint_counts}."))

        image_uris = [str(image.get("uri")) for image in payload.get("images", []) if image.get("uri")]
        if not image_uris:
            findings.append(Finding("ERROR", "MISSING_GLTF_IMAGES", "images", "No external PBR images were exported."))
        for uri in image_uris:
            path = gltf_path.parent / uri
            if not path.exists() or path.stat().st_size < 512:
                findings.append(Finding("ERROR", "INVALID_GLTF_IMAGE", uri, "Referenced image is missing or implausibly small."))

    errors = sum(1 for finding in findings if finding.severity == "ERROR")
    warnings = sum(1 for finding in findings if finding.severity == "WARNING")
    report = {
        "asset": "Dragon_Master",
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "nodes": len(payload.get("nodes", [])) if payload else 0,
            "meshes": len(payload.get("meshes", [])) if payload else 0,
            "materials": len(payload.get("materials", [])) if payload else 0,
            "animations": len(animation_names),
            "skins": len(skin_joint_counts),
            "images": len(image_uris),
        },
        "animation_names": animation_names,
        "skin_joint_counts": skin_joint_counts,
        "material_names": sorted(material_names),
        "glb_header": glb_header,
        "findings": [asdict(finding) for finding in findings],
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _read_glb_header(path: Path, findings: list[Finding]) -> dict:
    if not path.exists() or path.stat().st_size < 20:
        findings.append(Finding("ERROR", "INVALID_GLB", path.name, "GLB payload is missing or too small."))
        return {}
    try:
        with path.open("rb") as stream:
            magic, version, declared_length = struct.unpack("<4sII", stream.read(12))
    except (OSError, struct.error) as exc:
        findings.append(Finding("ERROR", "INVALID_GLB_HEADER", path.name, str(exc)))
        return {}
    if magic != b"glTF":
        findings.append(Finding("ERROR", "INVALID_GLB_MAGIC", path.name, f"Unexpected magic {magic!r}."))
    if version != 2:
        findings.append(Finding("ERROR", "INVALID_GLB_VERSION", path.name, f"Expected glTF 2, got {version}."))
    actual_length = path.stat().st_size
    if declared_length != actual_length:
        findings.append(Finding("ERROR", "INVALID_GLB_LENGTH", path.name, f"Header={declared_length}, file={actual_length}."))
    return {"magic": magic.decode("ascii", errors="replace"), "version": version, "length": declared_length}


def _validate_animation_ranges(payload: dict, findings: list[Finding]) -> None:
    accessors = payload.get("accessors", [])
    for animation in payload.get("animations", []):
        name = str(animation.get("name", "<unnamed>"))
        sampler_ranges: list[tuple[float, float]] = []
        for sampler in animation.get("samplers", []):
            accessor_index = sampler.get("input")
            if not isinstance(accessor_index, int) or not (0 <= accessor_index < len(accessors)):
                findings.append(Finding("ERROR", "INVALID_ANIMATION_ACCESSOR", name, f"Invalid input accessor {accessor_index}."))
                continue
            accessor = accessors[accessor_index]
            minimum = accessor.get("min")
            maximum = accessor.get("max")
            if not minimum or not maximum:
                findings.append(Finding("ERROR", "MISSING_ANIMATION_RANGE", name, "Time accessor has no min/max bounds."))
                continue
            start = float(minimum[0])
            end = float(maximum[0])
            sampler_ranges.append((start, end))
            if end <= start:
                findings.append(Finding("ERROR", "ZERO_DURATION_ANIMATION", name, f"Invalid time range {start}..{end}."))
        if not sampler_ranges:
            findings.append(Finding("ERROR", "EMPTY_GLTF_ANIMATION", name, "Animation has no valid time samplers."))
