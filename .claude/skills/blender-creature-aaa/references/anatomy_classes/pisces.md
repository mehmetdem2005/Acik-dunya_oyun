# Anatomy Class: Pisces (Balık)

Su omurgalıları. Hareket spine wave + tail fin propulsion. Genelde 4-7 fin (yüzgeç).

**Örnekler:** Köpek balığı, somon, sazan, kılıç balığı, anglerfish, tropikal balık.

---

## Proportions

```yaml
# Body length = burun → tail fin başlangıcı (caudal peduncle)
head_length_ratio: 0.20  # genelde body'nin %20'si
body_torso_length: 0.60
caudal_peduncle_length: 0.10  # tail başlangıç ince kısım
caudal_fin_length: 0.10  # ana kuyruk yüzgeç

body_max_width: 0.20  # latere göre
body_max_height: 0.30  # dorso-ventral yüksek (yandan basık)
body_cross_section: lateral_compressed  # yandan basık (çoğu balık)

# Fins
dorsal_fin_present: true  # sırt
ventral_fin_present: true  # karın
pectoral_fin_present: true  # yan göğüs (her iki yan)
pelvic_fin_present: true   # alt göğüs
anal_fin_present: true     # alt kuyruk
caudal_fin_shape: forked_or_homocercal  # çatallı (somon) veya düz (anglerfish)

# Eye
eye_size_ratio: 0.06
eye_position: lateral  # iki yanda
```

---

## Skeleton Structure

```yaml
bones:
  - {name: root_master, type: control, parent: null}
  
  # Spine = uzun chain (balık vücudunun ana yapısı)
  - {name: spine_00, type: deform, parent: root_master}  # tail base
  - {name: spine_01, type: deform, parent: spine_00}
  - {name: spine_02, type: deform, parent: spine_01}
  - {name: spine_03, type: deform, parent: spine_02}
  - {name: spine_04, type: deform, parent: spine_03}
  - {name: spine_05, type: deform, parent: spine_04}
  - {name: spine_06, type: deform, parent: spine_05}
  - {name: spine_07, type: deform, parent: spine_06}
  - {name: spine_08, type: deform, parent: spine_07}  # head birleşim
  
  - {name: head, type: deform, parent: spine_08}
  - {name: jaw, type: deform, parent: head}  # alt çene açılır
  
  # Caudal fin (kuyruk yüzgeç) — spine ucundan ayrı bone
  - {name: caudal_fin, type: deform, parent: spine_00}
  - {name: caudal_fin_upper, type: deform, parent: caudal_fin}  # üst lob
  - {name: caudal_fin_lower, type: deform, parent: caudal_fin}  # alt lob
  
  # Yan yüzgeçler (her iki yan)
  - {name: pectoral_fin_L, type: deform, parent: spine_06}  # göğüs
  - {name: pectoral_fin_R, type: deform, parent: spine_06}
  - {name: pelvic_fin_L, type: deform, parent: spine_04}   # karın
  - {name: pelvic_fin_R, type: deform, parent: spine_04}
  
  # Sırt + karın orta yüzgeçler
  - {name: dorsal_fin_00, type: deform, parent: spine_05}
  - {name: dorsal_fin_01, type: deform, parent: spine_05}
  - {name: anal_fin, type: deform, parent: spine_02}

bone_count_estimate: 18-25
```

---

## Locomotion

```yaml
gaits:
  swim_cruise:
    # Klasik balık yüzme: tail beat sinusoidal + spine wave
    pattern: tail_beat_with_spine_wave
    cycle_duration_seconds: 0.6
    tail_beat_amplitude_deg: 30  # caudal fin sağa-sola
    spine_wave_per_segment_deg: 5  # her segment hafif salınım
    spine_phase_offset_per_segment: 0.08  # head'den tail'e dalga
    propulsion_from: caudal_fin_thrust
  
  swim_burst:
    pattern: rapid_tail_beat
    cycle_duration_seconds: 0.15  # hızlı kaçış
    tail_beat_amplitude_deg: 55  # büyük amplitude
    pectoral_fins_compressed_against_body: true  # streamline
  
  swim_slow_hover:
    pattern: pectoral_fin_dominant
    cycle_duration_seconds: 1.5
    tail_motion: minimal
    pectoral_fin_oscillation_deg: 25  # yan yüzgeçler ana hareket
  
  reef_idle:
    pattern: stationary_with_fin_micro_motion
    cycle_duration_seconds: 3.0
    all_fins_subtle_motion: true
```

---

## Mesh Hints

```yaml
mesh_shape_hints:
  body_cross_section: oval_compressed_laterally  # yandan basık
  head_streamlined: true
  belly_silhouette: smooth_curve
  fins_thin_membrane: true

radius_profiles:
  spine:
    # Spine = body curve, balık head'den tail'e
    - {t: 0.0, r: 0.015}   # tail tip (caudal peduncle)
    - {t: 0.15, r: 0.05}   # tail base widening
    - {t: 0.50, r: 0.10}   # belly bulk peak
    - {t: 0.75, r: 0.09}   # transition to head
    - {t: 0.90, r: 0.10}   # head front (göz seviyesi)
    - {t: 1.0, r: 0.06}    # snout
```

---

## Stylization Knobs

```yaml
shark:
  cartilage_skeleton: true  # özellik notu (mesh same)
  caudal_fin_shape: heterocercal  # asimetrik kuyruk
  body_length_multiplier: 1.5
  mouth_underside: true

salmon:
  body_streamlined: true
  caudal_fin_shape: forked
  color_iridescent: true

anglerfish:
  body_globose: true  # küresel gövde
  lure_present: true  # başın üstünde "balık avcısı" antenne
  teeth_visible: true
  eyes_small: true

tropical_reef_fish:
  body_compressed_extreme: true  # çok basık (angel fish)
  body_height_to_length_ratio: 0.8  # neredeyse dik
  fins_decorative: true
```

---

## Common Defects

- Caudal fin spine ile bağlı değil (ayrı bone uçuyor)
- Body cross-section yuvarlak (oysa lateral compressed)
- Pectoral fin gövdeye yapışık (oysa hafif açılı, kanat gibi)
- Tail beat amplitude yetersiz (gerçekte large amplitude)
- Mouth açılmıyor (ağız ısırma yok)

---

## Recommended Clips

```yaml
recommended_clips:
  - {name: idle_hover, duration: 3.0, loop: true}
  - {name: swim_cruise_loop, duration: 0.6, loop: true}
  - {name: swim_burst_loop, duration: 0.15, loop: true}      # kaçış
  - {name: bite_attack, duration: 0.5, loop: false}
  - {name: turn_left, duration: 0.8, loop: false}            # opsiyonel turn anim
  - {name: turn_right, duration: 0.8, loop: false}
  - {name: surface_jump, duration: 1.5, loop: false}         # opsiyonel salmon
  - {name: death_belly_up, duration: 3.0, loop: false}       # tipik balık ölümü
```
