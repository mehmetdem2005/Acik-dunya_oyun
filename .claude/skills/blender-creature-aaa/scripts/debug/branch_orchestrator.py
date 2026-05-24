#!/usr/bin/env python3
"""
branch_orchestrator.py — D01 alt bileşen: A/B Branch Orchestrator

Aynı parent state'ten farklı parametrelerle paralel branch'ler çalıştırır.
Sonuçları vision score'a göre sıralar, en iyiyi öner.

Kullanım örnek:
    P04-AI mesh için TripoSR + Meshy + Hunyuan paralel:
    python branch_orchestrator.py run \\
      --parent <state_id> \\
      --branches branches.json
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


STATES_DIR = Path("memory/states")


def run_branch(parent_state_id, branch_config, base_workspace):
    """
    Bir branch'i izole workspace'te çalıştır.
    
    branch_config:
      {
        "name": "triposr",
        "agent": "P04_ai_mesh_generator",
        "params": {"backend": "triposr"},
        "workspace_suffix": "_branch_triposr"
      }
    """
    branch_workspace = Path(str(base_workspace) + branch_config["workspace_suffix"])
    
    # Replay parent
    sys.path.insert(0, str(Path(__file__).parent))
    from replay_engine import replay_state
    
    replay_state(parent_state_id, branch_workspace, clean=True)
    
    # Run agent with branch params
    # NOT: Bu spec — gerçek invocation orchestrator'a bağlı
    # Burada subprocess olarak agent script'i çağırıyoruz
    
    start = time.time()
    
    agent = branch_config["agent"]
    if agent == "P04_ai_mesh_generator":
        cmd = [
            sys.executable, "scripts/production/build_ai_mesh.py",
            "--ref-manifest", str(branch_workspace / "ReferenceManifest.json"),
            "--blueprint", str(branch_workspace / "SkeletonBlueprint.json"),
            "--budget", str(branch_workspace / "BudgetSpec.json"),
            "--backend", branch_config["params"]["backend"],
            "--output-blend", str(branch_workspace / "blender_scenes/mesh_v1.blend"),
        ]
    elif agent == "P04_mesh_sculptor":
        cmd = [
            "blender", "--background", 
            str(branch_workspace / "blender_scenes/skeleton_v1.blend"),
            "--python", "scripts/production/build_mesh.py", "--",
            "--blueprint", str(branch_workspace / "SkeletonBlueprint.json"),
            "--budget", str(branch_workspace / "BudgetSpec.json"),
            "--creature-spec", str(branch_workspace / "CreatureSpec.json"),
            "--anatomy-class", branch_config["params"].get(
                "anatomy_class", "references/anatomy_classes/mammalia_quadruped.md"),
            "--output-blend", str(branch_workspace / "blender_scenes/mesh_v1.blend"),
        ]
        # Branch-specific params:
        for k, v in branch_config["params"].items():
            if k == "voxel_size":
                cmd.extend(["--voxel-size", str(v)])
            elif k == "subdivision_level":
                cmd.extend(["--subdivision-level", str(v)])
    else:
        return {"name": branch_config["name"], "error": f"Unknown agent: {agent}"}
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=1200)
    except subprocess.TimeoutExpired:
        return {"name": branch_config["name"], "error": "timeout"}
    
    elapsed = time.time() - start
    
    if result.returncode != 0:
        return {
            "name": branch_config["name"],
            "error": result.stderr[-1000:],
            "elapsed_sec": elapsed,
        }
    
    # Yeni state capture
    from snapshot_manager import capture_state
    new_state_id = capture_state(
        agent_name=agent + "_" + branch_config["name"],
        workspace_dir=str(branch_workspace),
        parent_state_id=parent_state_id,
    )
    
    # Render + critic puanı (basit version: metric-based)
    state_dir = STATES_DIR / new_state_id
    metrics_file = state_dir / "metrics.json"
    metrics = json.loads(metrics_file.read_text()) if metrics_file.exists() else {}
    
    # Basit "quality score" — daha sonra vision critic ile yer değiştirir
    score = 0
    if metrics.get("meshmanifest_is_manifold"):
        score += 30
    if metrics.get("meshmanifest_is_watertight"):
        score += 20
    
    tris = metrics.get("meshmanifest_tris_count_actual", 0)
    if 5000 < tris < 20000:
        score += 20
    
    if metrics.get("meshmanifest_method") == "ai_generated":
        score += 30  # AI mesh genelde quality avantajı
    
    return {
        "name": branch_config["name"],
        "state_id": new_state_id,
        "elapsed_sec": elapsed,
        "metrics": metrics,
        "quality_score": score,
        "error": None,
    }


def run_parallel_branches(parent_state_id, branches, base_workspace,
                            max_concurrent=2):
    """
    Multiple branch'i paralel çalıştır.
    
    GPU branch'ler aynı anda 2'den fazla olmamalı (VRAM çakışması).
    API branch'leri unlimited paralel olabilir.
    """
    results = []
    
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(run_branch, parent_state_id, b, base_workspace): b
            for b in branches
        }
        
        for fut in as_completed(futures):
            branch = futures[fut]
            try:
                r = fut.result()
                results.append(r)
                if r.get("error"):
                    print(f"❌ {r['name']}: {r['error']}")
                else:
                    print(f"✓ {r['name']}: score={r['quality_score']}, "
                          f"{r['elapsed_sec']:.0f}s")
            except Exception as e:
                results.append({"name": branch["name"], "error": str(e)})
                print(f"❌ {branch['name']}: {e}")
    
    # Sort by quality_score
    successful = [r for r in results if not r.get("error")]
    successful.sort(key=lambda r: r["quality_score"], reverse=True)
    
    return {
        "all_branches": results,
        "successful_ranked": successful,
        "best": successful[0] if successful else None,
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    
    p_r = sub.add_parser("run")
    p_r.add_argument("--parent", required=True, help="Parent state_id")
    p_r.add_argument("--branches", required=True,
                      help="JSON file: list of branch configs")
    p_r.add_argument("--workspace", default="memory/current")
    p_r.add_argument("--max-concurrent", type=int, default=2)
    p_r.add_argument("--output", default=None)
    
    p_p = sub.add_parser("preset-ai-mesh")
    p_p.add_argument("--parent", required=True)
    p_p.add_argument("--workspace", default="memory/current")
    
    args = p.parse_args()
    
    if args.cmd == "run":
        branches = json.loads(Path(args.branches).read_text())
        result = run_parallel_branches(args.parent, branches, args.workspace,
                                          args.max_concurrent)
        
        out = json.dumps(result, indent=2, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(out)
        else:
            print(out)
        
        if result["best"]:
            print(f"\n🏆 En iyi branch: {result['best']['name']}")
            print(f"   State ID: {result['best']['state_id']}")
            print(f"   Quality: {result['best']['quality_score']}")
    
    elif args.cmd == "preset-ai-mesh":
        # Preset: TripoSR + Meshy + procedural paralel
        branches = [
            {
                "name": "triposr",
                "agent": "P04_ai_mesh_generator",
                "params": {"backend": "triposr"},
                "workspace_suffix": "_triposr",
            },
            {
                "name": "meshy_api",
                "agent": "P04_ai_mesh_generator",
                "params": {"backend": "meshy_api"},
                "workspace_suffix": "_meshy",
            },
            {
                "name": "procedural",
                "agent": "P04_mesh_sculptor",
                "params": {"voxel_size": 0.010, "subdivision_level": 1},
                "workspace_suffix": "_procedural",
            },
        ]
        
        result = run_parallel_branches(args.parent, branches, args.workspace,
                                          max_concurrent=2)
        
        print("\n=== Branch Results ===")
        for r in result["successful_ranked"]:
            print(f"  {r['quality_score']:3d}  {r['name']:15} {r['state_id']}")
        
        if result["best"]:
            print(f"\n🏆 Recommended: {result['best']['name']}")


if __name__ == "__main__":
    main()
