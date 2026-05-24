#!/usr/bin/env python3
"""
anomaly_detector.py — D01 alt bileşen: Auto-flag bad states

Pipeline'a entegre olur, her yeni state için:
  1. Quick metric checks
  2. Visual diff vs parent
  3. Vision Claude consultation (opsiyonel)
  4. Auto-flag + suggestion

Çıkış: anomaly_report.json + kullanıcıya log.

Kullanım:
    python anomaly_detector.py check <state_id>
    python anomaly_detector.py watch  # daemon mode (yeni state her oluştuğunda)
"""

import argparse
import json
import sys
import time
import subprocess
from pathlib import Path


STATES_DIR = Path("memory/states")


# Hard rules: bu durumlarda critical anomaly
HARD_RULES = {
    "manifold_broken": {
        "check": lambda m: not m.get("meshmanifest_is_manifold", True),
        "severity": "critical",
        "description": "Mesh manifold değil — animasyonda yırtılma riski yüksek",
        "suggested_action": "Önceki state'e rollback öneririm",
    },
    "watertight_broken": {
        "check": lambda m: not m.get("meshmanifest_is_watertight", True),
        "severity": "major",
        "description": "Mesh watertight değil (delik var)",
        "suggested_action": "Voxel remesh ile düzelt",
    },
    "tris_count_zero": {
        "check": lambda m: m.get("meshmanifest_tris_count_actual", 1) == 0,
        "severity": "critical",
        "description": "Mesh boş (0 tris)",
        "suggested_action": "Ajan tamamen başarısız, baştan başla",
    },
    "bone_count_zero": {
        "check": lambda m: m.get("skeletonblueprint_bone_count_total", 1) == 0,
        "severity": "critical",
        "description": "Skeleton boş (0 bone)",
        "suggested_action": "P03'ü tekrar çalıştır",
    },
    "weights_not_normalized": {
        "check": lambda m: m.get("skinningmanifest_weights_normalized") is False,
        "severity": "major",
        "description": "Vertex weights normalize edilmemiş",
        "suggested_action": "P08'i normalize=true ile çalıştır",
    },
    "no_animations": {
        "check": lambda m: m.get("animationmanifest_total_actions", 1) == 0,
        "severity": "critical",
        "description": "Hiç animasyon klipi üretilmedi",
        "suggested_action": "P12'yi tekrar çalıştır",
    },
}


# Pair-wise expected behavior (parent → child)
PAIRWISE_RULES = {
    # (parent_agent_substring, child_agent_substring): {check_func, severity, ...}
}


def check_hard_rules(metrics):
    """State'in metric'lerinde hard rule violations."""
    found = []
    for rule_id, rule in HARD_RULES.items():
        try:
            if rule["check"](metrics):
                found.append({
                    "rule_id": rule_id,
                    "severity": rule["severity"],
                    "description": rule["description"],
                    "suggested_action": rule["suggested_action"],
                })
        except Exception:
            pass
    return found


def check_pairwise(parent_metrics, child_metrics, parent_agent, child_agent):
    """Parent-child geçişinde mantık check."""
    found = []
    
    # Tris count büyük değişim mi?
    p_tris = parent_metrics.get("meshmanifest_tris_count_actual")
    c_tris = child_metrics.get("meshmanifest_tris_count_actual")
    if p_tris and c_tris:
        if "topology" not in child_agent.lower() and "decimate" not in child_agent.lower():
            # Topology surgeon dışında tris büyük değişmemeli
            if c_tris < p_tris * 0.5 or c_tris > p_tris * 2.0:
                found.append({
                    "rule_id": "pairwise_tris_jump",
                    "severity": "warning",
                    "description": f"{parent_agent} → {child_agent} arası tris {p_tris} → {c_tris} (× {c_tris/p_tris:.2f})",
                    "suggested_action": "Bu beklenmedik bir değişim, kontrol et",
                })
    
    # Bone count değişti mi (skeleton dışı)?
    p_bones = parent_metrics.get("skeletonblueprint_bone_count_total")
    c_bones = child_metrics.get("skeletonblueprint_bone_count_total")
    if p_bones and c_bones and p_bones != c_bones:
        if "skeleton" not in child_agent.lower():
            found.append({
                "rule_id": "pairwise_bone_count_change",
                "severity": "critical",
                "description": f"{child_agent} bone count'u değiştirdi: {p_bones} → {c_bones}",
                "suggested_action": "Skeleton dışı ajan bone sayısı değiştirmemeli. Bug var.",
            })
    
    # Manifold geriye gitti mi?
    p_manifold = parent_metrics.get("meshmanifest_is_manifold")
    c_manifold = child_metrics.get("meshmanifest_is_manifold")
    if p_manifold is True and c_manifold is False:
        found.append({
            "rule_id": "pairwise_manifold_regression",
            "severity": "critical",
            "description": f"{child_agent} mesh'i non-manifold yaptı",
            "suggested_action": "Geri al, ajan'ın non-destructive olduğunu kontrol et",
        })
    
    return found


def check_state(state_id):
    """
    Tam anomaly check.
    """
    state_dir = STATES_DIR / state_id
    if not state_dir.exists():
        return {"error": f"State {state_id} yok"}
    
    metrics_file = state_dir / "metrics.json"
    if not metrics_file.exists():
        return {"error": "metrics.json yok"}
    
    metrics = json.loads(metrics_file.read_text())
    
    # Hard rules
    anomalies = check_hard_rules(metrics)
    
    # Pairwise (parent varsa)
    parent_file = state_dir / "parent.txt"
    if parent_file.exists():
        parent_id = parent_file.read_text().strip()
        parent_metrics_file = STATES_DIR / parent_id / "metrics.json"
        if parent_metrics_file.exists():
            parent_metrics = json.loads(parent_metrics_file.read_text())
            
            # Agent name from state_id
            parent_agent = "_".join(parent_id.split("_")[2:-1]) if "_" in parent_id else "?"
            child_agent = "_".join(state_id.split("_")[2:-1]) if "_" in state_id else "?"
            
            pairwise = check_pairwise(parent_metrics, metrics, parent_agent, child_agent)
            anomalies.extend(pairwise)
    
    # Optional: visual diff
    # (Bu yavaş, sadece flag varsa çağır)
    if anomalies:
        # Visual diff'i de ekle
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from visual_diff import compare_states
            if parent_file.exists():
                vd = compare_states(parent_id, state_id)
                if vd.get("regression_detected"):
                    anomalies.extend(vd["anomalies"])
        except Exception as e:
            pass
    
    # Aggregate severity
    severities = [a["severity"] for a in anomalies]
    overall = "ok"
    if "critical" in severities:
        overall = "critical"
    elif "major" in severities:
        overall = "major"
    elif "warning" in severities:
        overall = "warning"
    
    return {
        "state_id": state_id,
        "overall_severity": overall,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "metrics": metrics,
    }


def format_user_report(check_result):
    """
    Kullanıcıya gösterilecek format.
    """
    if check_result.get("error"):
        return f"❌ Anomaly check fail: {check_result['error']}"
    
    if check_result["overall_severity"] == "ok":
        return f"✓ {check_result['state_id'][:24]}: anomaly yok"
    
    sev_emoji = {"critical": "❌", "major": "⚠️", "warning": "⚠️"}
    
    lines = [f"{sev_emoji[check_result['overall_severity']]} STATE ANOMALY"]
    lines.append(f"  State: {check_result['state_id']}")
    lines.append(f"  Severity: {check_result['overall_severity']}")
    lines.append("")
    lines.append("  Bulgular:")
    
    for a in check_result["anomalies"]:
        emoji = sev_emoji.get(a["severity"], "•")
        lines.append(f"    {emoji} [{a['severity']}] {a.get('description', a.get('rule_id'))}")
        if "suggested_action" in a:
            lines.append(f"       → {a['suggested_action']}")
    
    return "\n".join(lines)


def watch_for_new_states(poll_interval=2):
    """
    Daemon mode: index file'ı sürekli izle, yeni state olunca check.
    """
    index_file = STATES_DIR / "_index.jsonl"
    if not index_file.exists():
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.touch()
    
    last_size = index_file.stat().st_size
    
    print(f"[anomaly_detector] Watch mode başladı: {index_file}")
    
    while True:
        try:
            time.sleep(poll_interval)
            current_size = index_file.stat().st_size
            
            if current_size > last_size:
                # Yeni satır(lar) var
                with open(index_file) as f:
                    f.seek(last_size)
                    new_lines = f.readlines()
                
                last_size = current_size
                
                for line in new_lines:
                    try:
                        entry = json.loads(line)
                        sid = entry["state_id"]
                        
                        # Check
                        result = check_state(sid)
                        print(format_user_report(result))
                        print()
                    except Exception as e:
                        print(f"[watch] parse fail: {e}")
        except KeyboardInterrupt:
            break


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    
    p_c = sub.add_parser("check")
    p_c.add_argument("state_id")
    p_c.add_argument("--output", default=None)
    p_c.add_argument("--quiet", action="store_true")
    
    p_w = sub.add_parser("watch")
    p_w.add_argument("--poll-interval", type=float, default=2.0)
    
    p_a = sub.add_parser("audit-all")
    p_a.add_argument("--output", default=None)
    
    args = p.parse_args()
    
    if args.cmd == "check":
        result = check_state(args.state_id)
        
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2,
                                                       ensure_ascii=False))
        
        if not args.quiet:
            print(format_user_report(result))
        
        # Exit code: critical = 2, major = 1, ok = 0
        if result.get("overall_severity") == "critical":
            sys.exit(2)
        elif result.get("overall_severity") in ("major", "warning"):
            sys.exit(1)
        else:
            sys.exit(0)
    
    elif args.cmd == "watch":
        watch_for_new_states(args.poll_interval)
    
    elif args.cmd == "audit-all":
        # Tüm state'leri tara
        index_file = STATES_DIR / "_index.jsonl"
        if not index_file.exists():
            print("No states")
            sys.exit(0)
        
        all_results = []
        with open(index_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    result = check_state(entry["state_id"])
                    all_results.append(result)
                except Exception:
                    pass
        
        # Summary
        critical = [r for r in all_results if r.get("overall_severity") == "critical"]
        major = [r for r in all_results if r.get("overall_severity") == "major"]
        warning = [r for r in all_results if r.get("overall_severity") == "warning"]
        
        print(f"Total states: {len(all_results)}")
        print(f"Critical: {len(critical)}")
        print(f"Major: {len(major)}")
        print(f"Warning: {len(warning)}")
        print(f"OK: {len(all_results) - len(critical) - len(major) - len(warning)}")
        
        if args.output:
            Path(args.output).write_text(json.dumps(all_results, indent=2,
                                                       ensure_ascii=False))


if __name__ == "__main__":
    main()
