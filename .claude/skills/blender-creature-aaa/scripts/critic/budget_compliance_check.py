#!/usr/bin/env python3
"""
budget_compliance_check.py — C05 Mobile Perf Critic

Vision YOK. Manifest dosyalarını okur, BudgetSpec'e uyumluluğu kontrol eder.
"""

import json
import sys
import argparse
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--budget", required=True)
    p.add_argument("--run-dir", required=True, help="Manifest dosyalarının bulunduğu klasör")
    p.add_argument("--output", required=True)
    return p.parse_args()


def safe_load(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"  ⚠️ {path} parse fail: {e}")
        return None


def status_for(actual, target, tolerance_pct=15):
    """compliant / warning / violation"""
    if target == 0:
        return "compliant" if actual == 0 else "violation"
    delta_pct = ((actual - target) / target) * 100
    if abs(delta_pct) <= tolerance_pct:
        return "compliant"
    elif delta_pct > tolerance_pct:
        return "warning"  # üstünde
    else:
        return "warning"  # altında (under-budget de warning)


def main():
    args = parse_args()
    
    budget = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    run_dir = Path(args.run_dir)
    
    # Manifest dosyalarını topla
    manifests = {
        "mesh": safe_load(run_dir / "MeshManifest.json"),
        "skeleton": safe_load(run_dir / "SkeletonBlueprint.json"),
        "skinning": safe_load(run_dir / "SkinningManifest.json"),
        "animation": safe_load(run_dir / "AnimationManifest.json"),
        "material": safe_load(run_dir / "MaterialManifest.json"),
        "export": safe_load(run_dir / "final" / "ExportManifest.json"),
        "corrective": safe_load(run_dir / "CorrectiveManifest.json"),
        "uv": safe_load(run_dir / "UVManifest.json"),
    }
    
    compliance = {}
    violations = []
    warnings = []
    
    # 1. Polygon budget
    if manifests["mesh"]:
        actual = manifests["mesh"]["tris_count_actual"]
        target = budget["polygon_budget"]["lod0_tris_target"]
        hard_max = budget["polygon_budget"].get("lod0_tris_hard_max", target * 1.3)
        
        status = "compliant"
        if actual > hard_max:
            status = "violation"
            violations.append({
                "category": "polygon_budget",
                "severity": "critical",
                "description_tr": f"LOD0 tris {actual} > hard_max {hard_max}. P04'e geri dön, decimate ratio düşür.",
                "actual": actual, "limit": hard_max,
            })
        elif actual > target * 1.15:
            status = "warning"
            warnings.append({
                "category": "polygon_budget",
                "description_tr": f"LOD0 tris {actual} hedefin (%{target}) üstünde, %{((actual/target)-1)*100:.1f} aşkın.",
            })
        elif actual < target * 0.7:
            status = "warning"
            warnings.append({
                "category": "polygon_budget",
                "description_tr": f"LOD0 tris {actual} hedefin altında, detay yetersiz olabilir.",
            })
        
        compliance["polygon_budget"] = {
            "lod0_target": target, "lod0_actual": actual, "status": status,
            "delta_percent": ((actual - target) / target) * 100,
        }
    
    # 2. Rig budget
    if manifests["skeleton"]:
        bone_count = manifests["skeleton"].get("bone_count_total",
                                                  len(manifests["skeleton"].get("bones", [])))
        max_b = budget["rig_budget"]["bone_count_max"]
        
        status = "compliant" if bone_count <= max_b else "violation"
        if bone_count > max_b:
            violations.append({
                "category": "rig_budget",
                "severity": "critical",
                "description_tr": f"Bone sayısı {bone_count} > max {max_b}",
            })
        
        compliance["rig_budget"] = {
            "bone_count_max": max_b, "bone_count_actual": bone_count, "status": status,
        }
    
    # 3. Vertex weights
    if manifests["skinning"]:
        max_inf_target = budget["rig_budget"].get("vertex_weights_per_vertex_max", 4)
        max_inf_actual = manifests["skinning"].get("max_influences_per_vertex_target", 4)
        over_count = manifests["skinning"].get("validation", {}).get("over_max_influence_count", 0)
        
        status = "compliant" if over_count == 0 else "violation"
        if over_count > 0:
            violations.append({
                "category": "vertex_weights",
                "severity": "major",
                "description_tr": f"{over_count} vertex'in 4'ten fazla bone influence'ı var. Mobile shader uyumsuz.",
            })
        
        compliance["vertex_weights"] = {
            "max_per_vertex_target": max_inf_target,
            "over_count": over_count,
            "status": status,
        }
    
    # 4. Texture budget
    atlas_res_target = budget["texture_budget"].get("main_atlas_resolution", 2048)
    if manifests["material"]:
        # Material atlas_resolution
        atlas_res_actual = manifests["material"].get("atlas_resolution", atlas_res_target)
        status = "compliant" if atlas_res_actual <= atlas_res_target else "violation"
        if atlas_res_actual > atlas_res_target:
            violations.append({
                "category": "texture_budget",
                "severity": "major",
                "description_tr": f"Texture resolution {atlas_res_actual} > target {atlas_res_target}",
            })
        compliance["texture_budget"] = {
            "atlas_resolution_target": atlas_res_target,
            "atlas_resolution_actual": atlas_res_actual,
            "status": status,
        }
    
    # 5. Animation budget
    if manifests["animation"]:
        actual_clips = manifests["animation"]["total_actions"]
        target_clips = len(budget.get("animation_clips", []))
        
        status = "compliant" if actual_clips >= target_clips else "warning"
        if actual_clips < target_clips:
            warnings.append({
                "category": "animation_budget",
                "description_tr": f"Animasyon klip {actual_clips}/{target_clips}, eksik var",
            })
        
        compliance["animation_budget"] = {
            "total_clips_target": target_clips,
            "total_clips_actual": actual_clips,
            "status": status,
        }
        
        # Foot sliding compliance
        max_slide = max(
            (c.get("foot_sliding_max_z_error", 0) for c in manifests["animation"]["clips"]),
            default=0
        )
        if max_slide > 0.005:
            violations.append({
                "category": "foot_sliding",
                "severity": "major",
                "description_tr": f"Foot sliding max {max_slide:.4f} > 0.005",
            })
    
    # 6. Shape keys
    shape_budget = budget.get("shape_key_budget", {})
    if manifests["corrective"]:
        actual_shapes = len(manifests["corrective"]["shape_keys_created"])
        max_shapes = shape_budget.get("muscle_bulge_count_max", 0)
        
        status = "compliant" if actual_shapes <= max_shapes else "warning"
        compliance["shape_key_budget"] = {
            "muscle_bulge_count_max": max_shapes,
            "muscle_bulge_count_actual": actual_shapes,
            "status": status,
        }
    
    # 7. File size
    if manifests["export"]:
        for exp in manifests["export"]["exports"]:
            if exp["level"] == "LOD0":
                size_kb = exp["file_size_bytes"] / 1024
                limit_kb = 5000  # 5 MB
                status = "compliant" if size_kb <= limit_kb else "violation"
                if size_kb > limit_kb:
                    violations.append({
                        "category": "file_size",
                        "severity": "major",
                        "description_tr": f"LOD0 file {size_kb:.0f} KB > {limit_kb} KB",
                    })
                compliance["file_size"] = {
                    "lod0_max_kb": limit_kb,
                    "lod0_actual_kb": size_kb,
                    "status": status,
                }
                break
    
    # 8. Draw call estimate
    estimated_draw_calls = 1
    if manifests["material"]:
        if manifests["material"].get("texture_strategy") == "single_atlas":
            estimated_draw_calls = 1
        else:
            estimated_draw_calls = len(manifests["material"].get("texture_slots", [1]))
    
    # Overall
    if any(v["severity"] == "critical" for v in violations):
        overall = "violation_critical"
    elif violations:
        overall = "violation_major"
    elif warnings:
        overall = "warning"
    else:
        overall = "compliant"
    
    report = {
        "critic_id": "C05_mobile_perf_critic",
        "phase": "final",
        "overall_assessment": overall,
        "budget_compliance": compliance,
        "violations": violations,
        "warnings": warnings,
        "estimated_draw_calls": estimated_draw_calls,
    }
    
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    
    print(f"[mobile_perf_critic] Overall: {overall}")
    print(f"  Violations: {len(violations)}, Warnings: {len(warnings)}")
    for v in violations:
        print(f"  ❌ {v['category']}: {v['description_tr']}")
    for w in warnings:
        print(f"  ⚠️  {w['category']}: {w['description_tr']}")


if __name__ == "__main__":
    main()
