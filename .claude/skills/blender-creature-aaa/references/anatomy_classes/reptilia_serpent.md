# Anatomy Class: Reptilia Serpent (Yılan)

Bacaksız, uzun gövdeli sürüngenler. Tüm hareket spine wave + body undulation.

**Örnekler:** Yılan, kobra, anakonda, piton, çıngıraklı yılan.

---

## Proportions

```yaml
# Body length: snake için "total length" head + body + tail tek metric
total_length: full_length_meters  # örn: 1.5m (orta boy yılan)
head_size_ratio: 0.04  # küçük başlık (toplam'a göre)
head_width: 0.05  # genişlik genelde body'den biraz fazla
snout_length: 0.03
neck_thin_section_length: 0.03  # baş hemen ardından gövde

body_segment_count: 50-200  # yılanlarda omur sayısı yüksek
tail_proportion: 0.20  # toplam uzunluğun %20'si tail (sınır görsel)

body_thickness_max_ratio: 0.05  # toplam uzunluğun max 5%'i kalın

# Stilizasyon
# - Cobra: hood expand (genişleme), head büyük
# - Python: kalın gövde, body_thickness_max_ratio 0.07
# - Sea snake: tail flattened (paddle)
```

---

## Skeleton Structure

```yaml
bones:
  - {name: root_master, type: control, parent: null}
  
  # Spine = uzun zincir, 20-40 segment (oyun için 20-25 yeterli)
  - {name: spine_00, type: deform, parent: root_master}  # tail tip
  - {name: spine_01, type: deform, parent: spine_00}
  # ... spine_NN (continuous chain)
  - {name: spine_20, type: deform, parent: spine_19}  # head connection
  
  - {name: head, type: deform, parent: spine_20}  # en üstteki spine'a bağlı
  - {name: jaw, type: deform, parent: head}  # ÇOK açılabilir (kemikleri ayrı)
  
  # Tongue (opsiyonel)
  - {name: tongue, type: deform, parent: jaw}

bone_count_estimate: 22-30 (spine yoğunluk + head)
```

**ÖNEMLİ:** Bacak BONE YOKTUR. IK target da yok (no leg control).

---

## Locomotion

```yaml
gaits:
  slither_lateral:
    # Klasik yılan hareketi: lateral undulation
    pattern: spine_wave_propagation
    cycle_duration_seconds: 1.0
    wave_amplitude_per_segment_deg: 12
    wave_wavelength_segments: 8  # her 8 segment'te tam bir sinüs
    propagation_speed: 1.0  # dalga head'den tail'e gider
    direction: tail_to_head_to_propel_forward
  
  sidewind:
    # Çöl yılanı yan kaydırma
    pattern: lateral_loops
    cycle_duration_seconds: 0.8
    body_touches_ground_per_cycle: 2  # gövde iki noktadan yere değer
    forward_progress_at_angle_deg: 45  # body uzunluğuna 45° açıda ilerler
  
  rectilinear:
    # Büyük yılanlar (python): düz çizgi yavaş hareket
    pattern: ventral_scale_ripple
    cycle_duration_seconds: 1.5
    visible_motion: subtle_skin_ripple
    spine_motion: minimal
  
  strike:
    # Saldırı: ileri patlama hareketi
    pattern: head_lunge
    cycle_duration_seconds: 0.2
    distance_traveled_ratio: 0.35  # body length'in %35'i ileri
    body_compresses_then_extends: true
```

---

## Mesh Hints

```yaml
radius_profiles:
  spine:
    # Yılanda spine = tüm body, head + body + tail tek "spine curve"
    # Profile genelde uniform tubular, başta ve sonda incelir
    - {t: 0.0, r: 0.003}   # tail tip
    - {t: 0.1, r: 0.020}   # ince tail
    - {t: 0.4, r: 0.045}   # mid body (max kalın)
    - {t: 0.6, r: 0.045}
    - {t: 0.85, r: 0.040}  # neck
    - {t: 0.92, r: 0.050}  # head wider
    - {t: 1.0, r: 0.025}   # snout

cross_section: round_with_belly_flat
# Yılan altta düz (ventral scales), üstte yuvarlak
```

---

## Stylization Knobs

```yaml
cobra:
  hood_expandable: true  # neck'te shape key var
  hood_width_max_ratio: 0.15
  head_size_multiplier: 1.5

python:
  body_thickness_multiplier: 1.5
  total_length_multiplier: 1.5
  pattern: blocky_scales

sea_snake:
  tail_flat: true  # son %20 segment vertikal olarak basık
  swimming_emphasized: true
```

---

## Common Defects

- Head'in body'den çok bağımsız hareket etmesi (oysa head spine ucu, sürekli aynı yönde)
- Kuyruk ucu çok kalın (tip ince olmalı)
- Hareket sırasında body'nin sliding olması (yılan hareketi spine wave + ground friction)
- Hood (cobra) animation yokken cobra modelleme

---

## Recommended Clips

```yaml
recommended_clips:
  - {name: idle_coiled, duration: 4.0, loop: true}      # kıvrılmış, hafif breathing
  - {name: slither_loop, duration: 1.0, loop: true}     # ana hareket
  - {name: sidewind_loop, duration: 0.8, loop: true}    # opsiyonel (çöl yılanı)
  - {name: strike_attack, duration: 0.4, loop: false}   # ısırma saldırı
  - {name: coil_threat, duration: 1.5, loop: false}     # tehdit pozisyonu (kobra hood)
  - {name: hiss, duration: 1.2, loop: false}            # ağız açık + body raised
  - {name: death, duration: 2.5, loop: false}           # body limp
  - {name: shedding_skin, duration: 5.0, loop: false}   # opsiyonel
```

---

## Skinning Notes

Yılan skinning özel — her vertex'in spine bone'a olan etkisi smoothly distribute edilmeli (rigid bind = "candy wrapper" effect). Voxel HDS bunu otomatik halleder, fallback'ta heavy smoothing pass'i gerekli.
