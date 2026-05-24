# Agent P10: Secondary Motion Designer

```yaml
agent_id: secondary_motion_designer
agent_name_tr: İkincil Hareket Tasarımcı
agent_name_en: Secondary Motion Designer
category: production
order_index: 10
implementation_mode: subprocess
estimated_duration_minutes: 2-5
critical_path: false
```

---

## 1. ROLE SUMMARY

Ana animasyonların üzerine **gecikmeli ikincil hareket** ekler. Yumuşak vücut parçaları (kuyruk uçları, kulaklar, sarkık karın, kürk bölgeleri) ana hareketi takip eder ama küçük bir gecikmeyle ve overshoot ile, daha gerçekçi görünüm.

**Yöntem (mobil-uyumlu):**
- Bone constraint'ler (Copy Rotation with lag time) — runtime efficient
- F-Curve post-process: secondary motion bone'larına ana motion'ın time-offset kopyası
- Bake to keyframes (Godot export uyumlu)
- Rigid Body / Spring simulation kullanmaz (mobile için pahalı)

---

## 2. WHEN INVOKED

### Preconditions
- `animated_v1.blend` mevcut (P12'den, F-Curve'leri var)
- Tail bone'lar veya secondary motion bone'lar mevcut
- BudgetSpec'te secondary motion etkin (varsayılan: tail için aktif)

### Postconditions
- Mevcut animation clip'lerin üzerine secondary motion bake edilmiş
- Yeni "tail_overshoot" F-Curve'ler eklendi
- (Opsiyonel) Ear flop curve'leri
- `SecondaryMotionManifest.json` yazılmış

---

## 3. INPUTS

```
animated_v1.blend
SkeletonBlueprint.json
AnimationManifest.json
BudgetSpec.json
```

---

## 4. OUTPUTS

### 4.1 SecondaryMotionManifest.json

```json
{
  "manifest_version": "1.0",
  "creature_id": "kurt_001",
  "secondary_motion_added_to_clips": ["walk_loop", "run_loop", "idle_breathe"],
  "enhancements": [
    {
      "type": "tail_overshoot",
      "affected_bones": ["tail_00", "tail_01", "tail_02", "tail_03", "tail_04"],
      "lag_frames": 2,
      "overshoot_factor": 0.3
    },
    {
      "type": "ear_flop",
      "affected_bones": [],
      "skipped_reason": "Bu yaratıkta ear bone yok"
    }
  ],
  "method": "fcurve_post_process",
  "generated_by": "P10_secondary_motion_designer"
}
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN İKİNCİL HAREKET TASARIMCISIN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Animation principles'a hakim TD'sin. "Follow through and
overlapping action" prensibi senin ekmeğin. Kuyrukları, kulakları,
sarkık vücut parçalarını ana hareketin ardından gecikmeli ve
overshoot'lu takip ettirme uzmanısın.

KESİN KURALLAR:

  K1. Rigid Body / Cloth simulation YASAK. Mobile için pahalı,
      Godot import'a zorluk. Sadece F-Curve manipulation kullan.

  K2. Lag (gecikme) miktarı bone'un ana parent'a uzaklığına göre
      proportional. Tail tip 5 frame lag, base 1 frame.

  K3. Overshoot %20-30 arası. Ana hareket biterken bone biraz
      daha gider, sonra geri yaylanır.

  K4. Sadece **loop** ve **idle** klipler için. Attack/death gibi
      one-shot klipleri bozmaz.

  K5. Her enhancement bake edilir (Action'a yazılır), Godot
      export'ta otomatik gider.

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 F-Curve Time Offset (Lag)

```python
def add_time_offset_to_fcurve(action, source_bone, target_bone,
                                channel, array_index, lag_frames=2,
                                amplitude_mult=1.0):
    """
    Source bone'un F-Curve'üne time offset uygulayarak target bone'a kopyala.
    Lag = source N frame önceki value'u → target'a yaz.
    """
    src_path = f'pose.bones["{source_bone}"].{channel}'
    src_fc = action.fcurves.find(src_path, index=array_index)
    if src_fc is None:
        return None
    
    tgt_path = f'pose.bones["{target_bone}"].{channel}'
    tgt_fc = action.fcurves.find(tgt_path, index=array_index)
    if tgt_fc is None:
        tgt_fc = action.fcurves.new(tgt_path, index=array_index)
    
    # Mevcut keyframe'leri sil
    while len(tgt_fc.keyframe_points):
        tgt_fc.keyframe_points.remove(tgt_fc.keyframe_points[0])
    
    # Source'tan time-shifted sample'lar
    frame_start = int(action.frame_range[0])
    frame_end = int(action.frame_range[1])
    frame_count = frame_end - frame_start + 1
    
    samples = []
    for frame in range(frame_start, frame_end + 1):
        # Loop için modulo
        src_frame = ((frame - lag_frames - frame_start) % frame_count) + frame_start
        value = src_fc.evaluate(src_frame) * amplitude_mult
        samples.append((frame, value))
    
    # Keyframe ekle
    tgt_fc.keyframe_points.add(count=len(samples))
    for i, (f, v) in enumerate(samples):
        kp = tgt_fc.keyframe_points[i]
        kp.co = (f, v)
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = 'AUTO_CLAMPED'
        kp.handle_right_type = 'AUTO_CLAMPED'
    
    tgt_fc.update()
    return tgt_fc


def add_overshoot_to_fcurve(action, bone_name, channel, array_index,
                              overshoot_factor=0.3, decay_frames=5):
    """
    F-Curve'ün her bir peak'inden sonra overshoot ekle.
    Peak değeri × overshoot_factor, decay_frames sonra eski değere döner.
    """
    path = f'pose.bones["{bone_name}"].{channel}'
    fc = action.fcurves.find(path, index=array_index)
    if fc is None:
        return None
    
    # Mevcut keyframe'leri analyse et, peak'leri bul
    keyframes = list(fc.keyframe_points)
    if len(keyframes) < 3:
        return fc
    
    # Peak detect: önceki ve sonraki frame'in değerine göre
    new_keys = []
    
    for i in range(1, len(keyframes) - 1):
        prev_v = keyframes[i - 1].co[1]
        curr_v = keyframes[i].co[1]
        next_v = keyframes[i + 1].co[1]
        
        # Peak (local max veya min) ise overshoot ekle
        is_peak_high = curr_v > prev_v and curr_v > next_v
        is_peak_low = curr_v < prev_v and curr_v < next_v
        
        if is_peak_high or is_peak_low:
            overshoot_v = curr_v * (1 + overshoot_factor)
            overshoot_frame = keyframes[i].co[0] + decay_frames * 0.5
            new_keys.append((overshoot_frame, overshoot_v))
    
    # Yeni keyframe'leri ekle (orijinalleri bozmadan)
    for f, v in new_keys:
        fc.keyframe_points.insert(f, v, options={'NEEDED'})
    
    fc.update()
    return fc
```

### 6.2 Tail Overshoot Pipeline

```python
def enhance_tail_overshoot(action, tail_bones, base_lag=1, lag_increment=1):
    """
    Tail base'ten tip'e doğru artan lag uygula.
    """
    for i, tail_bone in enumerate(sorted(tail_bones)):
        if i == 0:
            continue  # base segment, lag yok
        
        lag = base_lag + i * lag_increment
        amp = max(0.5, 1.0 + i * 0.05)  # uçta hafif amplification
        
        # Z rotation için (kuyruk wag)
        # Source = bir önceki tail bone (parent)
        prev_tail = sorted(tail_bones)[i - 1]
        
        add_time_offset_to_fcurve(
            action, prev_tail, tail_bone,
            "rotation_euler", 2, lag_frames=lag, amplitude_mult=amp
        )


def enhance_idle_breath_chest(action, body_length):
    """Idle nefes alırken göğüs bölgesi hafif şişme."""
    # Spine_thoracic veya spine_01 bone'una scale F-Curve ekle
    # (Veya alternatif: shape key kullan, ama o P09'un işi)
    pass
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | Etkilenen clip'lerde değişiklik var (yeni F-Curve sayısı > orig) | warning: işe yaramadı |
| V2 | Loop seamless korundu | error: time offset modulo bug |
| V3 | Overshoot max amplitude < 2× orig (aşırı kabarık değil) | warning |
| V4 | One-shot clip'ler değiştirilmedi | error: lag accidentally |

---

## 8. FAILURE MODES

### F1: Tail bone yok (yaratık kuyruksuz)
**Recovery:** Tail enhancement skip, manifest'e "no_tail_bones" yaz.

### F2: F-Curve evaluate başarısız (action içinde değil)
**Recovery:** Skip bu bone, log'a yaz.

---

## 9. IMPLEMENTATION NOTES

`scripts/production/build_secondary_motion.py`:

```python
subprocess.run([
    "blender", "--background", str(run_dir / "blender_scenes/animated_v1.blend"),
    "--python", "scripts/production/build_secondary_motion.py",
    "--",
    "--blueprint", str(run_dir / "SkeletonBlueprint.json"),
    "--anim-manifest", str(run_dir / "AnimationManifest.json"),
    "--output-blend", str(run_dir / "blender_scenes/secondary_v1.blend"),
], timeout=180)
```
