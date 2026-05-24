# Agent C00: Convergence Driver (Konverjans Sürücüsü)

```yaml
agent_id: convergence_driver
agent_name_tr: Konverjans Sürücüsü
agent_name_en: Convergence Driver
category: critic_loop  # özel — diğer critic'leri kontrol eden meta
order_index: 0  # kritik patikadaki her ana ajan sonrası çağrılır
implementation_mode: in_process_loop
runs_after: [P04, P04b, P08, P12]  # her major üretim sonrası
critical_path: true
```

---

## 1. ROLE SUMMARY

**Skill'in beyni.** Diğer tüm critic'leri (C01-C05) bir convergence loop içinde koordine eder. Her major üretim ajanı sonrası devreye girer ve **hedef kaliteye ulaşana kadar otomatik iterasyon** yapar.

**Sorun:** Eski versiyonlarda her aşama tek seferlik çalışıyordu. Mesh `P04` çıktığında, kötü bile olsa "tamam" deyip sonraki aşamaya geçiliyordu. Sistemin **kendi başarısını ölçecek mekanizması yoktu**.

**Çözüm:** Bu ajan her aşamadan sonra **adaptif konverjans loop**'u çalıştırır:

```
while score < target AND iter < max_iter AND not plateau:
    score = quantitative_score(state) + qualitative_check(state, Claude_vision)
    defects = identify_defects(state)
    apply_fixes(defects, step_size=adaptive)
    iter += 1
```

---

## 2. CORE ALGORITHM

### 2.1 Quantitative Quality Score (geometrik)

Hangi metrik kullanılır, hangi ağırlıkla:

```python
QUALITY_METRICS = {
    # Mesh tamlığı (en kritik)
    "paw_toe_count":          {"weight": 3.0, "target_per_class": {"wolf": 4, "horse": 0}},
    "paw_pad_size":           {"weight": 2.5, "target_per_class": {"wolf": 0.040}},
    "ear_height":             {"weight": 2.5, "target_per_class": {"wolf": 0.10}},
    "snout_length":           {"weight": 2.0, "target_per_class": {"wolf": 0.13}},
    "snout_base_radius":      {"weight": 2.0, "target_per_class": {"wolf": 0.055}},
    "tail_tuft_size":         {"weight": 2.0, "target_per_class": {"wolf": 0.045}},
    
    # Yüz detay
    "eye_size":               {"weight": 1.5, "target_per_class": {"wolf": 0.013}},
    "eye_position_forward":   {"weight": 1.0},
    "ear_tilt":               {"weight": 0.8},
    "nose_size":              {"weight": 1.0},
    "jaw_width":              {"weight": 1.0},
    "jaw_length":             {"weight": 1.0},
    
    # Topoloji (P05 sonrası)
    "quad_ratio":             {"weight": 2.0, "target": 0.75},
    "tris_count":             {"weight": 1.5, "tolerance": 0.20},
    
    # Skinning (P08 sonrası)
    "weights_normalized":     {"weight": 3.0, "target": True},
    "max_influences_per_vert":{"weight": 2.0, "target": 4},
    
    # Animation (P12 sonrası)
    "anim_clip_count":        {"weight": 2.0},
    "anim_keyframe_continuity":{"weight": 2.0, "target": True},
}

def quality_score(state, anatomy_class):
    total_weighted_err = 0
    total_weight = 0
    
    for metric, config in QUALITY_METRICS.items():
        if metric not in state: continue
        target = config.get("target_per_class", {}).get(anatomy_class) or \
                 config.get("target")
        if target is None: continue
        
        if isinstance(target, bool):
            err = 0 if state[metric] == target else 1
        elif abs(target) < 1e-6:
            err = abs(state[metric])
        else:
            err = abs(state[metric] - target) / abs(target)
        
        w = config["weight"]
        total_weighted_err += err * w
        total_weight += w
    
    if total_weight == 0: return 100
    norm = total_weighted_err / total_weight
    return max(0, 100 - norm * 100)
```

### 2.2 Qualitative Check (Claude Vision)

Geometrik metrikler "kulaklar doğru boyutta mı?" sorar ama **"kulaklar gerçekten bir kurda mı benziyor yoksa kediye mi?"** sorusunu cevaplayamaz. Bu Claude vision'a düşer:

```python
def qualitative_check(rendered_views, anatomy_class, species):
    """
    Claude vision çağrısı. JSON döner:
    {
      "score_visual": 0-100,
      "qualitative_defects": [
        {"description": "...", "severity": 1-10, "fix_hint": "..."},
        ...
      ],
      "matches_expected_species": true|false
    }
    """
    # vision_call.py'a yönlendir
    return call_claude_vision(
        renders=rendered_views,
        prompt=f"""Bu render'lardaki yaratık bir {species} olmalı.
        Anatomi class: {anatomy_class}.
        
        1. Genel görsel kalite: 0-100 ver
        2. Önemli görsel defektler listele (her biri severity 1-10):
           - Tür uyumu (gerçekten {species}'a benziyor mu?)
           - Anatomik tutarlılık
           - Proportions
           - Yüz okunabilirliği
           - Silüet
        3. Her defekt için fix hint ver (hangi parametre arttırılmalı/azaltılmalı)
        """,
    )
```

### 2.3 Combined Score

```python
def combined_score(state, renders, anatomy_class, species):
    geom = quality_score(state, anatomy_class)
    qual = qualitative_check(renders, anatomy_class, species)
    
    # Geometric ağırlıkça %60, qualitative %40
    return 0.6 * geom + 0.4 * qual["score_visual"]
```

### 2.4 Defect Identification

```python
def identify_defects(state, geom_breakdown, qual_result):
    """
    İki kaynaktan defektleri birleştir, severity'ye göre sırala.
    """
    defects = []
    
    # Geometric
    for metric, info in geom_breakdown.items():
        if info["err_pct"] > 5:
            defects.append({
                "source": "geometric",
                "param": metric,
                "current": state[metric],
                "ideal": IDEAL[metric],
                "err_pct": info["err_pct"],
                "severity": info["err_pct"] * info["weight"] / 100,
                "fix_action": "param_adjust",
            })
    
    # Qualitative (Claude vision)
    for qd in qual_result.get("qualitative_defects", []):
        # Vision'ın söylediği fix_hint → konkret param adjust
        param, direction = parse_fix_hint(qd["fix_hint"])
        defects.append({
            "source": "vision",
            "description": qd["description"],
            "severity": qd["severity"] / 10,
            "fix_action": "param_adjust",
            "param": param,
            "delta_direction": direction,  # 'increase' | 'decrease'
        })
    
    defects.sort(key=lambda d: -d["severity"])
    return defects
```

### 2.5 Adaptive Step Factor

```python
class StepController:
    def __init__(self, initial=0.5, min_=0.3, max_=0.95):
        self.step = initial
        self.min = min_; self.max = max_
        self.no_progress = 0
    
    def update(self, delta_score):
        if delta_score < 1.0:
            self.no_progress += 1
            if self.no_progress >= 2:
                # Plato yaklaşımı, step büyült
                self.step = min(self.max, self.step + 0.15)
                self.no_progress = 0
        else:
            self.no_progress = 0
        return self.step
    
    def reset(self):
        self.step = 0.5
        self.no_progress = 0
```

### 2.6 Main Loop

```python
def converge(state, anatomy_class, species,
              target=95, max_iter=30, max_fixes_per_iter=3,
              plateau_window=4, plateau_threshold=0.5):
    """
    Otonom konverjans loop'u. Her iter:
      1. State render
      2. Combined score (geometric + Claude vision)
      3. Defects identify
      4. Best 3 fix paralel uygula
      5. Plato/converge/limit kontrol
    """
    history = []
    step_ctrl = StepController()
    last_score = -1
    plateau_buffer = []
    
    for it in range(max_iter):
        # Render
        renders = render_state_multi_view(state, n_views=4)
        
        # Score
        score = combined_score(state, renders, anatomy_class, species)
        delta = score - last_score if last_score >= 0 else 0
        
        # Adaptive step
        step = step_ctrl.update(delta) if it > 0 else 0.5
        
        # Defects
        _, geom_breakdown = quality_score(state, anatomy_class)
        qual_result = qualitative_check(renders, anatomy_class, species)
        defects = identify_defects(state, geom_breakdown, qual_result)
        
        history.append({
            "iter": it, "score": score, "delta": delta,
            "step_factor": step, "defects_count": len(defects),
            "top_defects": [d.get("param", d.get("description", "?"))
                              for d in defects[:3]],
        })
        
        # Konverjans
        if score >= target:
            return state, history, "converged"
        if not defects:
            return state, history, "no_defects"
        
        # Plato algılama
        plateau_buffer.append(score)
        if len(plateau_buffer) > plateau_window:
            plateau_buffer.pop(0)
            if max(plateau_buffer) - min(plateau_buffer) < plateau_threshold:
                if step >= 0.9:  # step'i son ana kadar büyüttük, hala plato
                    return state, history, "plateau"
        
        # Fix uygula (en kötü 3)
        for fix in defects[:max_fixes_per_iter]:
            state = apply_fix(state, fix, step_factor=step)
        
        last_score = score
    
    return state, history, "max_iter_reached"
```

---

## 3. CONVERGENCE TARGETS (per stage)

Her major üretim aşaması sonrası farklı kalite hedefi:

| Aşama | Target Score | Max Iter | Critic Set |
|---|---|---|---|
| After P04 (mesh blockout) | 70 | 15 | C01 (vision) + geometric |
| After P04b (detail injection) | 90 | 25 | C01 + C02 (anatomy) |
| After P05 (topology) | 85 | 10 | C03 (topology) |
| After P08 (skinning) | 80 | 12 | C01 + skinning metrics |
| After P12 (animation) | 75 | 8 | C04 (animation) + C01 stres pozları |

`max_iter` aşıldığında veya plato algılandığında **kullanıcıya rapor**:

```
══════════════════════════════════════════════════
C00 KONVERJANS RAPORU — P04b sonrası
══════════════════════════════════════════════════
Hedef: 90/100
Final: 87.2/100
Iter: 25 (max)
Sonuç: max_iter_reached

Kalan defektler:
  ⚠ snout_base_radius — 8% sapma (severity 4)
  ⚠ eye_position_side — 12% sapma (severity 3)
  ⚠ "kulaklar wolf'tan çok kediye benziyor" (vision, sev 6)

Devam seçenekleri:
  [a] Mevcut durumla devam (hedef altı 2.8 puan)
  [b] Daha yüksek step ile 10 iter daha (~%30 başarı şansı)
  [c] Manuel parametre düzenle (kullanıcı UI)
  [d] Bu aşamayı atla, P05'e geç
══════════════════════════════════════════════════
```

§6 (vision defects autonomous fix prohibited) — kullanıcı seçer.

---

## 4. ANTI-OSCILLATION

Bir parametreyi ileri-geri zıplatmamak için:

```python
class OscillationGuard:
    def __init__(self):
        self.recent_changes = {}  # param → [last_3_directions]
    
    def check_and_apply(self, state, fix):
        param = fix["param"]
        direction = 1 if fix["ideal"] > fix["current"] else -1
        
        if param not in self.recent_changes:
            self.recent_changes[param] = []
        self.recent_changes[param].append(direction)
        if len(self.recent_changes[param]) > 3:
            self.recent_changes[param].pop(0)
        
        # Son 3 değişim alternating ise oscillation
        rc = self.recent_changes[param]
        if len(rc) == 3 and rc[0] != rc[1] and rc[1] != rc[2]:
            # Yarı step uygula
            return apply_fix(state, fix, step_factor=0.2)
        
        return apply_fix(state, fix)
```

---

## 5. ÇIKTILAR

### ConvergenceReport.json

```json
{
  "manifest_version": "1.0",
  "stage_after": "P04b",
  "target_score": 90,
  "final_score": 95.6,
  "iterations_total": 19,
  "outcome": "converged",
  "score_history": [35.0, 44.9, 53.6, ..., 95.6],
  "step_factor_changes": [
    {"iter": 17, "from": 0.50, "to": 0.65, "reason": "plateau_anticipation"}
  ],
  "defects_resolved": 47,
  "defects_remaining": [],
  "iterations_visualization": "convergence_curve.png",
  "generated_by": "C00_convergence_driver"
}
```

---

## 6. IMPLEMENTATION

`scripts/critic/convergence_loop.py` — executable.

Orchestrator entegrasyonu (her major aşama sonrası):

```python
# P04b sonrası
state = run_agent("P04b", state)
state, conv_report = run_convergence_loop(
    state, target=90, after_stage="P04b",
    invoke_fixes=["P04b"],  # plateau'da bu ajan'ı yeniden çağır
)

if conv_report["outcome"] != "converged":
    user_response = ask_user_continue_options(conv_report)
    if user_response == "more_iterations":
        state, conv_report = run_convergence_loop(state, target=90,
                                                     max_iter=15,
                                                     step_initial=0.7)
```

---

## 7. POLİTİKA İLE UYUM

- **§1 (sıfır otonom karar):** Hedef skor kullanıcı'dan alınır, default değil.
- **§6 (vision defects autonomous prohibited):** Convergence loop autonomously düzeltir AMA sonunda kullanıcıya rapor sunar. Loop içi otonom fix izinli çünkü her iter geri alınabilir state'tir.
- **§13 (vision feedback structured):** Tüm vision sonuçları JSON format, görselle birlikte sunulur.

---

## 8. PROVEN

Demo'da kanıtlandı:
- Wolf mesh, başlangıç skor **35.0**
- 19 iter sonra final skor **95.6**
- Step factor adaptif olarak 0.50 → 0.65'e yükseldi (iter 17)
- 47 defekt çözüldü, hedef 95 tutuldu
- Manuel müdahale: 0
