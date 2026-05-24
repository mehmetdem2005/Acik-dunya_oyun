#!/usr/bin/env python3
"""
visual_diff.py — D01 alt bileşen: Vision-based regression detection

İki state'in renderlarını karşılaştırır:
  1. Image embedding distance (CLIP veya pixel-level perceptual)
  2. Metric delta analysis
  3. Vision Claude'a açık soru: "regression var mı?"

Kullanım:
    python visual_diff.py compare <state_a> <state_b>
    python visual_diff.py regression-scan  # tüm chain'i tara
"""

import argparse
import json
import sys
import subprocess
from pathlib import Path


STATES_DIR = Path("memory/states")


# =============================================================================
# Image similarity (CLIP veya hash fallback)
# =============================================================================

def compute_perceptual_hash(image_path):
    """
    pHash (perceptual hash) — kütüphane gerekmez fallback.
    Renderlar görsel olarak benzer ise hash'leri yakın.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    
    img = Image.open(image_path).convert('L').resize((32, 32), Image.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = ''.join('1' if p > avg else '0' for p in pixels)
    return bits


def hamming_distance(h1, h2):
    """İki hash arası bit fark sayısı."""
    if h1 is None or h2 is None or len(h1) != len(h2):
        return -1
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))


def compute_clip_embedding(image_path):
    """
    CLIP image embedding (kütüphane varsa).
    Daha sağlam similarity.
    """
    try:
        import torch
        from PIL import Image
        import clip
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model, preprocess = clip.load("ViT-B/32", device=device)
        
        img = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
        with torch.no_grad():
            emb = model.encode_image(img)
        return emb.cpu().numpy().flatten().tolist()
    except ImportError:
        return None
    except Exception as e:
        print(f"  ⚠️ CLIP fail: {e}", file=sys.stderr)
        return None


def cosine_distance(v1, v2):
    """1 - cosine similarity."""
    if not v1 or not v2:
        return -1
    import math
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return -1
    return 1 - (dot / (n1 * n2))


# =============================================================================
# Metric diff
# =============================================================================

def compute_metric_diff(metrics_a, metrics_b):
    """Hangi metrikler değişti, ne kadar."""
    diffs = {}
    all_keys = set(metrics_a.keys()) | set(metrics_b.keys())
    
    for k in all_keys:
        a = metrics_a.get(k)
        b = metrics_b.get(k)
        
        if a is None or b is None:
            diffs[k] = {"before": a, "after": b, "type": "added_or_removed"}
            continue
        
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            delta = b - a
            pct = (delta / a * 100) if a != 0 else float('inf')
            diffs[k] = {
                "before": a, "after": b, "delta": delta,
                "pct_change": pct,
                "type": "numeric",
            }
        elif a != b:
            diffs[k] = {"before": a, "after": b, "type": "changed"}
    
    return diffs


# =============================================================================
# Anomaly detection logic
# =============================================================================

# Expected vision diff ranges for agent transitions
# Eğer farklılık bu aralık dışında ise anomaly
EXPECTED_VISION_DIFF = {
    ("P03_skeleton_architect", "P04_mesh_sculptor"): (0.30, 0.70),  # büyük değişim normal
    ("P04_mesh_sculptor", "P05_topology_surgeon"): (0.05, 0.25),   # küçük (retopo)
    ("P04_mesh_sculptor", "P06_uv_cartographer"): (0.0, 0.05),     # UV görsel değişmez
    ("P06_uv_cartographer", "P08_skinner"): (0.0, 0.10),           # skinning de görsel değişmez
    ("P08_skinner", "P09_corrective_sculptor"): (0.02, 0.15),      # shape keys (subtle)
    ("P09_corrective_sculptor", "P11_material_alchemist"): (0.10, 0.40),  # material büyük
    ("P11_material_alchemist", "P12_animator"): (0.20, 0.60),      # animation pose
    ("P12_animator", "P13_exporter"): (0.0, 0.10),                 # export bare visual change
}


def detect_anomaly(state_a, state_b, vision_distance):
    """
    Multi-signal anomaly detection.
    Returns: list of anomaly signals.
    """
    signals = []
    
    # 1. Vision distance check
    agent_pair = (state_a["metrics"].get("agent_name", state_a.get("agent")),
                  state_b["metrics"].get("agent_name", state_b.get("agent")))
    expected = EXPECTED_VISION_DIFF.get(agent_pair)
    
    if expected and vision_distance >= 0:
        if vision_distance < expected[0]:
            signals.append({
                "type": "visual_too_similar",
                "severity": "warning",
                "description": f"{agent_pair[1]} sonrası beklenenden az değişim ({vision_distance:.2f} < {expected[0]:.2f}). Ajan etkisiz mi?",
            })
        elif vision_distance > expected[1]:
            signals.append({
                "type": "visual_regression_risk",
                "severity": "critical",
                "description": f"{agent_pair[1]} sonrası beklenenden çok değişim ({vision_distance:.2f} > {expected[1]:.2f}). Bozulma olabilir.",
            })
    
    # 2. Manifold bozuldu mu
    a_manifold = state_a["metrics"].get("meshmanifest_is_manifold", True)
    b_manifold = state_b["metrics"].get("meshmanifest_is_manifold", True)
    if a_manifold and not b_manifold:
        signals.append({
            "type": "manifold_broken",
            "severity": "critical",
            "description": "Mesh önceden manifold idi, şimdi değil",
        })
    
    # 3. Tris jump
    a_tris = state_a["metrics"].get("meshmanifest_tris_count_actual")
    b_tris = state_b["metrics"].get("meshmanifest_tris_count_actual")
    if a_tris and b_tris:
        pct = abs(b_tris - a_tris) / a_tris * 100
        if pct > 50:
            signals.append({
                "type": "tris_count_jump",
                "severity": "warning",
                "description": f"Tris %{pct:.0f} değişti ({a_tris} → {b_tris}). Beklenmedik olabilir.",
            })
    
    # 4. Bone count change (sadece skeleton aşamasında değişmeli)
    a_bones = state_a["metrics"].get("skeletonblueprint_bone_count_total")
    b_bones = state_b["metrics"].get("skeletonblueprint_bone_count_total")
    if a_bones and b_bones and a_bones != b_bones:
        # Skeleton dışı agent ise anomaly
        agent_b = agent_pair[1] or ""
        if "skeleton" not in agent_b.lower():
            signals.append({
                "type": "bone_count_unexpected_change",
                "severity": "critical",
                "description": f"{agent_b} bone sayısını değiştirdi: {a_bones} → {b_bones}",
            })
    
    return signals


# =============================================================================
# State diff (main API)
# =============================================================================

def compare_states(state_a_id, state_b_id):
    """
    Two state'i compare et, comprehensive report dön.
    """
    # Load metrics
    a_metrics_file = STATES_DIR / state_a_id / "metrics.json"
    b_metrics_file = STATES_DIR / state_b_id / "metrics.json"
    
    if not a_metrics_file.exists():
        return {"error": f"State A metrics yok: {state_a_id}"}
    if not b_metrics_file.exists():
        return {"error": f"State B metrics yok: {state_b_id}"}
    
    metrics_a = json.loads(a_metrics_file.read_text())
    metrics_b = json.loads(b_metrics_file.read_text())
    
    # Vision distance (renders varsa)
    a_renders = sorted((STATES_DIR / state_a_id / "renders").glob("*.png")) \
                  if (STATES_DIR / state_a_id / "renders").exists() else []
    b_renders = sorted((STATES_DIR / state_b_id / "renders").glob("*.png")) \
                  if (STATES_DIR / state_b_id / "renders").exists() else []
    
    vision_dist = -1
    method = "none"
    
    if a_renders and b_renders:
        # CLIP varsa ona kullan, yoksa pHash
        a_emb = compute_clip_embedding(a_renders[0])
        if a_emb is not None:
            b_emb = compute_clip_embedding(b_renders[0])
            vision_dist = cosine_distance(a_emb, b_emb)
            method = "clip_cosine"
        else:
            # pHash fallback
            a_hash = compute_perceptual_hash(a_renders[0])
            b_hash = compute_perceptual_hash(b_renders[0])
            if a_hash and b_hash:
                ham = hamming_distance(a_hash, b_hash)
                # Normalize 0-1
                vision_dist = ham / len(a_hash) if len(a_hash) > 0 else -1
                method = "phash_hamming"
    
    # Metric diff
    metric_diffs = compute_metric_diff(metrics_a, metrics_b)
    
    # Anomaly detection
    state_a = {"agent": state_a_id.split("_")[2] if "_" in state_a_id else "?",
               "metrics": metrics_a}
    state_b = {"agent": state_b_id.split("_")[2] if "_" in state_b_id else "?",
               "metrics": metrics_b}
    anomalies = detect_anomaly(state_a, state_b, vision_dist)
    
    return {
        "state_a": state_a_id,
        "state_b": state_b_id,
        "vision_distance": vision_dist,
        "vision_method": method,
        "metric_diffs": metric_diffs,
        "anomalies": anomalies,
        "regression_detected": any(a["severity"] == "critical" for a in anomalies),
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    
    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("state_a")
    p_cmp.add_argument("state_b")
    p_cmp.add_argument("--output", default=None)
    
    p_scan = sub.add_parser("regression-scan")
    p_scan.add_argument("--from", dest="from_state", default=None,
                          help="Start from this state, walk forward in tree")
    
    args = p.parse_args()
    
    if args.cmd == "compare":
        result = compare_states(args.state_a, args.state_b)
        out = json.dumps(result, indent=2, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(out)
        else:
            print(out)
        
        # Exit code: anomaly varsa non-zero
        sys.exit(1 if result.get("regression_detected") else 0)
    
    elif args.cmd == "regression-scan":
        # Tree'yi tarayıp her parent-child çift için anomaly check
        sys.path.insert(0, str(Path(__file__).parent))
        from snapshot_manager import get_tree
        
        tree = get_tree()
        any_anomaly = False
        
        for sid, node in tree["nodes"].items():
            parent = node.get("parent")
            if parent is None:
                continue
            
            result = compare_states(parent, sid)
            if result.get("regression_detected"):
                any_anomaly = True
                print(f"⚠️ REGRESSION: {parent[:20]} → {sid[:20]}")
                for a in result["anomalies"]:
                    if a["severity"] == "critical":
                        print(f"   - {a['type']}: {a['description']}")
        
        if not any_anomaly:
            print("✓ Tree'de regression tespit edilmedi")


if __name__ == "__main__":
    main()
