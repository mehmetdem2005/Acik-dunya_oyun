#!/usr/bin/env python3
"""
convergence_loop.py — C00 Convergence Driver

Otonom kalite konverjans loop'u. Her major üretim aşaması sonrası çağrılır.

Çağrı yolları:
  1. Blender içinde subprocess olarak (mesh state'ini Blender'dan al)
  2. Pure Python olarak (parametre dict üzerinde)

Demo'da pure Python kanıtlandı (35 → 95.6 in 19 iter).
Gerçek skill'de:
  - state = mesh + manifests dict
  - render: scripts/render_eval.py via Blender subprocess
  - vision check: scripts/vision_call.py via Claude API
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any


# ============================================================================
# Quality scoring
# ============================================================================

class QualityScorer:
    """Geometrik + nicel kalite skoru."""
    
    # Anatomy class'a göre ideal değerler
    IDEAL_BY_CLASS = {
        "mammalia_quadruped": {
            "wolf": {
                "paw_pad_size": 0.040, "paw_toe_count": 4, "paw_toe_size": 0.013,
                "ear_height": 0.10, "ear_tilt": 0.6, "ear_base_radius": 0.030,
                "eye_size": 0.013, "eye_position_forward": -0.04,
                "eye_position_up": 0.03, "eye_position_side": 0.045,
                "snout_length": 0.13, "snout_base_radius": 0.055,
                "nose_size": 0.020, "jaw_width": 0.038, "jaw_length": 0.060,
                "tail_tuft_size": 0.045,
            },
            "dog": {  # benzer ama proportions farklı
                "paw_pad_size": 0.035, "paw_toe_count": 4, "paw_toe_size": 0.012,
                "ear_height": 0.08, "snout_length": 0.10,
                "snout_base_radius": 0.050, "tail_tuft_size": 0.030,
                # ... rest similar
            },
            "horse": {
                "paw_pad_size": 0.060, "paw_toe_count": 0,  # hoof
                "ear_height": 0.07, "snout_length": 0.18,
                "snout_base_radius": 0.080, "tail_tuft_size": 0.080,
                "eye_size": 0.018,
            },
            "cat": {
                "paw_pad_size": 0.025, "paw_toe_count": 4, "paw_toe_size": 0.010,
                "ear_height": 0.06, "snout_length": 0.05,
                "snout_base_radius": 0.040, "tail_tuft_size": 0.020,
            },
        },
        "aves": {
            "eagle": {
                "beak_length": 0.08, "wing_span_ratio": 1.7,
                "eye_size": 0.020, "talon_size": 0.025,
            },
        },
    }
    
    # Her metric için ağırlık
    WEIGHTS = {
        "paw_toe_count": 3.0, "paw_pad_size": 2.5, "ear_height": 2.5,
        "snout_length": 2.0, "snout_base_radius": 2.0, "tail_tuft_size": 2.0,
        "paw_toe_size": 1.5, "eye_size": 1.5, "ear_base_radius": 1.0,
        "eye_position_forward": 1.0, "eye_position_up": 1.0,
        "eye_position_side": 1.0, "ear_tilt": 0.8, "nose_size": 1.0,
        "jaw_width": 1.0, "jaw_length": 1.0,
    }
    
    @classmethod
    def get_ideal(cls, anatomy_class, species):
        ideals = cls.IDEAL_BY_CLASS.get(anatomy_class, {}).get(species)
        if ideals is None:
            # Fallback: anatomy class'ın default ideal'i
            cls_defaults = cls.IDEAL_BY_CLASS.get(anatomy_class, {})
            if cls_defaults:
                # İlk türünü al
                first_species = next(iter(cls_defaults))
                ideals = cls_defaults[first_species]
        return ideals or {}
    
    @classmethod
    def score(cls, state, anatomy_class, species):
        """
        Returns: (score 0-100, breakdown dict per metric)
        """
        ideal = cls.get_ideal(anatomy_class, species)
        if not ideal:
            return 50.0, {}  # fallback
        
        total_err = 0
        total_weight = 0
        breakdown = {}
        
        for metric, ideal_val in ideal.items():
            if metric not in state:
                continue
            
            current = state[metric]
            
            if isinstance(ideal_val, bool):
                err = 0 if current == ideal_val else 1.0
            elif abs(ideal_val) < 1e-6:
                err = abs(current)
            else:
                err = abs(current - ideal_val) / abs(ideal_val)
            
            w = cls.WEIGHTS.get(metric, 1.0)
            total_err += err * w
            total_weight += w
            
            breakdown[metric] = {
                "current": current, "ideal": ideal_val,
                "err_pct": err * 100, "weight": w,
                "severity": err * w * 100,
            }
        
        if total_weight == 0:
            return 100.0, breakdown
        
        norm = total_err / total_weight
        score = max(0.0, 100 - norm * 100)
        return score, breakdown


# ============================================================================
# Defect identification
# ============================================================================

class DefectIdentifier:
    @staticmethod
    def from_breakdown(breakdown, min_err_pct=5.0):
        defects = []
        for metric, info in breakdown.items():
            if info["err_pct"] > min_err_pct:
                defects.append({
                    "source": "geometric",
                    "param": metric,
                    "current": info["current"],
                    "ideal": info["ideal"],
                    "err_pct": info["err_pct"],
                    "severity": info["severity"],
                })
        defects.sort(key=lambda d: -d["severity"])
        return defects
    
    @staticmethod
    def from_vision(vision_result):
        """Claude vision JSON sonucundan defekt çıkar."""
        defects = []
        for vd in vision_result.get("qualitative_defects", []):
            defects.append({
                "source": "vision",
                "description": vd["description"],
                "severity": vd["severity"] * 10,  # 1-10 → 10-100
                "fix_hint": vd.get("fix_hint"),
                "param": vd.get("suggested_param"),
                "delta_direction": vd.get("direction"),
            })
        return defects


# ============================================================================
# Step controller (adaptive)
# ============================================================================

class StepController:
    def __init__(self, initial=0.5, min_=0.3, max_=0.95):
        self.step = initial
        self.min, self.max = min_, max_
        self.no_progress_count = 0
    
    def update(self, delta_score):
        if delta_score < 1.0:
            self.no_progress_count += 1
            if self.no_progress_count >= 2:
                self.step = min(self.max, self.step + 0.15)
                self.no_progress_count = 0
        else:
            self.no_progress_count = 0
        return self.step
    
    def reset(self):
        self.step = 0.5
        self.no_progress_count = 0


# ============================================================================
# Oscillation guard
# ============================================================================

class OscillationGuard:
    def __init__(self):
        self.recent = {}  # param → list of recent deltas
    
    def will_oscillate(self, param, new_direction):
        rc = self.recent.get(param, [])
        if len(rc) >= 2 and rc[-1] != new_direction and rc[-2] == new_direction:
            return True
        return False
    
    def record(self, param, direction):
        self.recent.setdefault(param, []).append(direction)
        if len(self.recent[param]) > 3:
            self.recent[param].pop(0)


# ============================================================================
# Fix application
# ============================================================================

def apply_fix(state, defect, step_factor=0.5):
    """Defekti %step_factor kadar düzelt."""
    new_state = state.copy()
    param = defect.get("param")
    
    if param is None:
        return new_state
    
    if "ideal" in defect and "current" in defect:
        # Geometric defect: hedefe yaklaş
        if param == "paw_toe_count":
            # Integer
            if defect["ideal"] > defect["current"]:
                new_state[param] = state.get(param, 0) + 1
            elif defect["ideal"] < defect["current"]:
                new_state[param] = max(0, state.get(param, 0) - 1)
        else:
            delta = defect["ideal"] - defect["current"]
            new_state[param] = state.get(param, 0) + delta * step_factor
    
    elif defect.get("delta_direction"):
        # Vision defect: yön ile fix
        current = state.get(param, 0)
        dir_factor = 1.15 if defect["delta_direction"] == "increase" else 0.85
        new_state[param] = current * dir_factor
    
    return new_state


# ============================================================================
# Main convergence loop
# ============================================================================

def converge(
    state: Dict[str, Any],
    anatomy_class: str,
    species: str,
    target_score: float = 95.0,
    max_iter: int = 30,
    max_fixes_per_iter: int = 3,
    plateau_window: int = 4,
    plateau_threshold: float = 0.5,
    vision_callback=None,  # opsiyonel callback for Claude vision
    progress_callback=None,
    verbose: bool = False,
):
    """
    Otonom konverjans loop'u.
    
    state: parametre dict (build_mesh için)
    vision_callback(renders) → vision_result dict (opsiyonel)
    progress_callback(iter, score, defects) → None
    
    Returns: (final_state, history, outcome)
    """
    history = []
    step_ctrl = StepController()
    osc_guard = OscillationGuard()
    last_score = -1
    plateau_buffer = []
    
    for it in range(max_iter):
        # Score
        geom_score, breakdown = QualityScorer.score(state, anatomy_class, species)
        
        # Vision (opsiyonel)
        vision_score = None
        vision_defects = []
        if vision_callback is not None:
            try:
                vresult = vision_callback(state)
                vision_score = vresult.get("score_visual", 100)
                vision_defects = DefectIdentifier.from_vision(vresult)
            except Exception as e:
                if verbose:
                    print(f"  ⚠ vision callback fail: {e}")
        
        # Combined score
        if vision_score is not None:
            score = 0.6 * geom_score + 0.4 * vision_score
        else:
            score = geom_score
        
        # Defects
        geom_defects = DefectIdentifier.from_breakdown(breakdown)
        all_defects = vision_defects + geom_defects
        all_defects.sort(key=lambda d: -d["severity"])
        
        delta_score = score - last_score if last_score >= 0 else 0
        step = step_ctrl.update(delta_score) if it > 0 else 0.5
        
        # History
        entry = {
            "iter": it,
            "score": round(score, 2),
            "geom_score": round(geom_score, 2),
            "vision_score": round(vision_score, 2) if vision_score else None,
            "delta": round(delta_score, 2),
            "step_factor": round(step, 3),
            "defects_count": len(all_defects),
            "top_defects": [d.get("param") or d.get("description", "?")
                              for d in all_defects[:3]],
        }
        history.append(entry)
        
        if progress_callback:
            progress_callback(it, score, all_defects)
        
        if verbose:
            top_str = ", ".join(entry["top_defects"][:3])
            print(f"iter {it:>3}  score={score:>5.1f}  Δ={delta_score:>+5.1f}  "
                  f"step={step:.2f}  defects={len(all_defects):>3}  | {top_str}")
        
        # Konverjans
        if score >= target_score:
            return state, history, "converged"
        if not all_defects:
            return state, history, "no_defects"
        
        # Plato
        plateau_buffer.append(score)
        if len(plateau_buffer) > plateau_window:
            plateau_buffer.pop(0)
            if max(plateau_buffer) - min(plateau_buffer) < plateau_threshold:
                if step >= 0.9:
                    return state, history, "plateau"
        
        # Fix apply (multi)
        for fix in all_defects[:max_fixes_per_iter]:
            if fix.get("param") is None: continue
            
            # Oscillation check
            direction = 1 if fix.get("ideal", 0) > fix.get("current", 0) else -1
            if osc_guard.will_oscillate(fix["param"], direction):
                # Daha küçük step ile uygula
                state = apply_fix(state, fix, step_factor=step * 0.4)
            else:
                state = apply_fix(state, fix, step_factor=step)
            osc_guard.record(fix["param"], direction)
        
        last_score = score
    
    return state, history, "max_iter_reached"


# ============================================================================
# CLI
# ============================================================================

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True, help="JSON file: current state dict")
    p.add_argument("--anatomy-class", required=True)
    p.add_argument("--species", required=True)
    p.add_argument("--target", type=float, default=95.0)
    p.add_argument("--max-iter", type=int, default=30)
    p.add_argument("--max-fixes", type=int, default=3)
    p.add_argument("--output-report", required=True)
    p.add_argument("--output-state", default=None,
                   help="Final state'i bu path'e yaz")
    p.add_argument("--verbose", action="store_true")
    
    args = p.parse_args()
    
    state = json.loads(Path(args.state).read_text())
    
    final_state, history, outcome = converge(
        state=state,
        anatomy_class=args.anatomy_class,
        species=args.species,
        target_score=args.target,
        max_iter=args.max_iter,
        max_fixes_per_iter=args.max_fixes,
        verbose=args.verbose,
    )
    
    # Report
    report = {
        "manifest_version": "1.0",
        "target_score": args.target,
        "max_iter": args.max_iter,
        "outcome": outcome,
        "initial_score": history[0]["score"] if history else None,
        "final_score": history[-1]["score"] if history else None,
        "iterations_used": len(history),
        "score_history": [h["score"] for h in history],
        "history_detailed": history,
        "anatomy_class": args.anatomy_class,
        "species": args.species,
        "generated_by": "C00_convergence_driver",
    }
    
    Path(args.output_report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    
    if args.output_state:
        Path(args.output_state).write_text(json.dumps(final_state, indent=2, ensure_ascii=False))
    
    print(f"\n{'='*60}")
    print(f"OUTCOME: {outcome}")
    print(f"Score: {history[0]['score']:.1f} → {history[-1]['score']:.1f}")
    print(f"Iterations: {len(history)}")
    print(f"{'='*60}")
    
    # Exit code: 0 if converged, 1 if not
    sys.exit(0 if outcome == "converged" else 1)


if __name__ == "__main__":
    main()
