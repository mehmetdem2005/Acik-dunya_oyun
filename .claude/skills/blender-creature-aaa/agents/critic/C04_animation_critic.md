# Agent C04: Animation Critic (Animasyon Eleştirmen)

```yaml
agent_id: animation_critic
agent_name_tr: Animasyon Eleştirmen
agent_name_en: Animation Critic
category: critic
order_index: 4
implementation_mode: subprocess
parallel_with: [C01, C02, C03, C05]
estimated_duration_seconds: 60-180  # animation render'ları + analiz
```

---

## 1. ROLE SUMMARY

P12 Animator çıktısını animasyon kalitesi açısından kritik eder:

- **Foot sliding** (ayak yerde olduğu frame'lerde X/Y velocity ≈ 0 mı?)
- **Mesh intersection** (animasyon sırasında mesh kendine giriyor mu?)
- **Jerky motion** (F-Curve'lerin tangent'ları smooth mu yoksa aniden mi sıçrıyor?)
- **Foot lift insufficient** (ayak yere sürtüyor mu?)
- **Anatomical accuracy in motion** (kurt yürüyüşüne benziyor mu yoksa robotik mi?)

---

## 2. WHEN INVOKED

### Preconditions
- `animated_v1.blend` mevcut
- Her klip için **6 örnek frame** render edilmiş:
  - frame 1, 1/6, 2/6, 3/6, 4/6, 5/6, end
- `AnimationManifest.json` mevcut
- (Opsiyonel) Walk cycle animasyonu için referans video varsa, key frame'leri extract edilmiş

### Postconditions
- `critic_reports/animation_<iter>.json` yazılmış
- Foot sliding metric'ler analitik olarak ölçülmüş

---

## 3. INPUTS

```
animated_v1.blend         # F-Curve analizi için
AnimationManifest.json    # her klip için beklenen veriler
renders_dir              # her klip için 6 frame
refs_dir                 # (opsiyonel) referans hareket frame'leri
```

---

## 4. OUTPUTS

```json
{
  "critic_id": "C04_animation_critic",
  "phase": "animation",
  "iteration": 1,
  "overall_assessment": "minor_issues",
  "per_clip_assessment": [
    {
      "clip": "walk_loop",
      "analytical_metrics": {
        "foot_sliding_max_y_velocity": 0.0023,
        "foot_lift_min_height": 0.048,
        "fcurve_jerk_score": 12,
        "loop_seamless_error": 0.001
      },
      "visual_defects": [
        {
          "id": "AN001",
          "severity": "minor",
          "category": "deformation",
          "frame": 15,
          "location": "sol arka pati",
          "description_tr": "Frame 15'te sol arka pati hafif yerine yapışık görünüyor — lift_amplitude artırılabilir.",
          "evidence_image_names": ["walk_loop_frame_15.png"]
        }
      ]
    },
    {
      "clip": "attack_bite",
      "visual_defects": [
        {
          "id": "AN005",
          "severity": "major",
          "category": "intersection",
          "frame": 18,
          "description_tr": "Strike frame'inde alt çene boyun mesh'i ile clipping yapıyor."
        }
      ]
    }
  ]
}
```

---

## 5. SYSTEM PROMPT

```
SEN ANİMASYON ELEŞTİRMENİSİN — character animator + tech anim TD.

Görevin: Yaratığın animasyon klip'lerinden alınmış frame
render'larını incele. Hareketin gerçek anatomik biomechanics'e
uyup uymadığını, mesh deformasyon kalitesini, ve teknik
sorunları (foot sliding, intersection, jerky motion) tespit et.

DİKKAT EDECEKLERIN:

1. WALK/RUN:
   - Foot sliding: yere değen frame'lerde ayak duruyor mu yoksa
     kayıyor mu? (kayma = artifact)
   - Foot lift: yerden kalkma yüksekliği yeterli mi? Mobil mesafede
     "yere sürtüyor" gözükmeli mi?
   - Body bounce sync: gövde Z+ olunca ayaklar yere değdi mi?
   - Spine roll: yan salınım var mı yoksa robotik mi?
   - Tail wag: kuyruk hareketi yumuşak mı, ana hareketle uyumlu mu?

2. ATTACK/BITE:
   - Windup → strike → recovery üç fazı belirgin mi?
   - Çene açılma maksimum noktada mesh intersection yok mu?
   - Strike frame'inde fizik mantıklı mı?

3. IDLE/BREATH:
   - Çok statik mi (hiç hareket etmiyor) yoksa fazla mı sallanıyor?
   - Nefes alma doğal mı?

4. GENEL:
   - Frame'ler arası geçişler smooth mu (jerky tangent yok)?
   - Loop clip'lerde son frame ile ilk frame benzer mi?

KESİN KURALLAR:
- Frame numarası belirterek defekt rapor et
- Foot sliding için analytical_metrics değerlerini de değerlendir
- Vision + analytical kombinasyonu

ÇIKIŞ: Strict JSON, klip bazlı segmente edilmiş.
```

---

## 6. ANALYTICAL METRICS (Render-bağımsız)

```python
# scripts/critic/compute_animation_metrics.py
def compute_animation_metrics(action, foot_ik_bones, fps=30):
    """
    F-Curve'lerden direkt ölçüm.
    """
    metrics = {}
    
    # 1. Foot sliding
    max_slide = 0
    for foot_id, bone_name in foot_ik_bones.items():
        z_fc = action.fcurves.find(
            f'pose.bones["{bone_name}"].location', index=2
        )
        y_fc = action.fcurves.find(
            f'pose.bones["{bone_name}"].location', index=1
        )
        if z_fc and y_fc:
            frame_start = int(action.frame_range[0])
            frame_end = int(action.frame_range[1])
            for f in range(frame_start, frame_end):
                z = z_fc.evaluate(f)
                if abs(z) < 0.005:  # foot yerde
                    y_velocity = abs(y_fc.evaluate(f + 1) - y_fc.evaluate(f))
                    max_slide = max(max_slide, y_velocity)
    
    metrics["foot_sliding_max_y_velocity"] = max_slide
    
    # 2. Jerk score (F-Curve smoothness)
    jerk_score = 0
    for fc in action.fcurves:
        # F-Curve sample'larının ikinci türev'i
        frame_start = int(fc.range()[0])
        frame_end = int(fc.range()[1])
        if frame_end - frame_start < 4:
            continue
        
        for f in range(frame_start + 1, frame_end - 1):
            v_prev = fc.evaluate(f - 1)
            v_curr = fc.evaluate(f)
            v_next = fc.evaluate(f + 1)
            accel = abs((v_next - v_curr) - (v_curr - v_prev))
            if accel > 0.1:  # sıçrama threshold
                jerk_score += 1
    
    metrics["fcurve_jerk_score"] = jerk_score
    
    # 3. Loop seamless error (sadece loop clipler)
    loop_error = 0
    if action.name.endswith("_loop") or "breathe" in action.name:
        for fc in action.fcurves:
            frame_start = int(fc.range()[0])
            frame_end = int(fc.range()[1])
            if frame_end > frame_start:
                v_first = fc.evaluate(frame_start)
                v_last = fc.evaluate(frame_end)
                loop_error = max(loop_error, abs(v_first - v_last))
    
    metrics["loop_seamless_error"] = loop_error
    
    return metrics
```

---

## 7. SEVERITY KURALLAR

| Bulgu | Severity |
|---|---|
| Foot sliding > 0.01 birim/frame | critical |
| Mesh intersection in motion (görünür clipping) | critical |
| Loop seamless error > 0.01 | major |
| Foot lift = 0 (ayak yerden hiç kalkmıyor) | critical |
| Jerk score > 50 | major |
| Body bounce yok (statik gövde) | minor |

---

## 8. FAILURE MODES

### F1: Render eksik (sadece bazı klipler render edilmiş)
**Recovery:** Eksik klipleri otomatik render et (`render_eval.py --clip <name>`).

### F2: F-Curve evaluate exception (action corrupted)
**Recovery:** Bu klip'i skip, manifest'e error yaz, diğer kliplere geç.

---

## 9. CROSS-CRITIC

C04 + C01'in **deformation** kategorisinde aynı bölgede bulduğu defekt = double-confirmed, critical.

C04 + C03'ün topology problemli bölgesinde deformasyon defekt bulması = "topology root cause" — orchestrator P05 retopology'e geri dön sinyali verir.
