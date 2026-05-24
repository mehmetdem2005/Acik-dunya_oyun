# Anatomy Class: Reptilia Quadruped

Dört bacaklı sürüngenler. Sprawled (yana açık) bacak duruşu, gövde yere yakın.

**Örnekler:** Kertenkele, iguana, komodo, timsah, kaplumbağa, semender (amphibian benzerlik).

---

## Proportions

```yaml
# Body length = burun → kuyruk başlangıcı (kuyruk ayrı)
head_size_ratio: 0.15
snout_length: 0.10  # kafanın %50-70'i snout (timsah)
neck_length: 0.05  # kısa, neredeyse yok
neck_radius_ratio: 0.7  # boyun ile gövde aynı kalın

torso_length: 0.45  # uzun gövde
torso_width: 0.18
chest_depth: 0.15  # düşük profilli
belly_proximity_to_ground: 0.05  # gövde neredeyse yere değer

leg_length: 0.25
leg_upper_length: 0.10  # humerus / femur
leg_lower_length: 0.10  # radius / tibia
foot_length: 0.06
toe_count: 5  # genelde, timsah 4 arka
limb_sprawl_angle_deg: 60  # yana açılma açısı (digitigrade'tan çok farklı)

tail_length: 0.50  # body_length'in %50-150'si (varies wildly)
tail_base_thick: true  # özellikle timsah, monitor lizard

# Stilizasyon
# - Turtle: shell major addition, leg sprawl 80°, tail kısa
# - Crocodile: tail uzun ve kalın (yarısı su tahriki için)
# - Gecko: parmak uçlarında pad
```

---

## Skeleton Structure

```yaml
bones:
  - {name: root_master, type: control, parent: null}
  - {name: spine_00, type: deform, parent: root_master}  # pelvis
  - {name: spine_01, type: deform, parent: spine_00}
  - {name: spine_02, type: deform, parent: spine_01}
  - {name: spine_03, type: deform, parent: spine_02}
  - {name: spine_04, type: deform, parent: spine_03}
  - {name: spine_05, type: deform, parent: spine_04}  # shoulder
  - {name: neck_00, type: deform, parent: spine_05}
  - {name: head, type: deform, parent: neck_00}
  - {name: jaw, type: deform, parent: head}  # büyük açılır
  
  # Front legs (sprawled — yana açık)
  - {name: shoulder_L, type: deform, parent: spine_05}
  - {name: upper_arm_L, type: deform, parent: shoulder_L}
  - {name: forearm_L, type: deform, parent: upper_arm_L}
  - {name: wrist_L, type: deform, parent: forearm_L}
  # Toes (5 × 3) — opsiyonel detay
  
  # Rear legs (sprawled)
  - {name: hip_L, type: deform, parent: spine_00}
  - {name: thigh_L, type: deform, parent: hip_L}
  - {name: shin_L, type: deform, parent: thigh_L}
  - {name: ankle_L, type: deform, parent: shin_L}
  - {name: foot_L, type: deform, parent: ankle_L}
  
  # Tail (uzun zincir, çoğunluğu hareket eder)
  - {name: tail_00, type: deform, parent: spine_00}
  - {name: tail_01, type: deform, parent: tail_00}
  - {name: tail_02, type: deform, parent: tail_01}
  - {name: tail_03, type: deform, parent: tail_02}
  - {name: tail_04, type: deform, parent: tail_03}
  - {name: tail_05, type: deform, parent: tail_04}
  - {name: tail_06, type: deform, parent: tail_05}
  - {name: tail_07, type: deform, parent: tail_06}  # 8 segment tipik

bone_count_estimate: 35-55
```

---

## Locomotion

```yaml
gaits:
  walk_sprawl:
    # Sürüngen yürüyüşü = "diagonal couplet" ama gövde S-bend ile
    pattern: diagonal_2beat_with_body_undulation
    phase_offsets: {LF: 0.0, RR: 0.0, RF: 0.5, LR: 0.5}
    cycle_duration_seconds: 1.5  # yavaş
    stride_length_ratio: 0.10  # kısa adım
    foot_lift_height_ratio: 0.04
    body_lateral_undulation_deg: 25  # gövde sağa-sola dalgalanır (S şekli)
    spine_phase_offset_per_segment: 0.15  # her segment biraz geç başlar
  
  run_lizard:
    # Hızlı kertenkele bipedal koşabilir (basilisk)
    pattern: diagonal_2beat_high_speed
    phase_offsets: {LF: 0.0, RR: 0.0, RF: 0.5, LR: 0.5}
    cycle_duration_seconds: 0.4
    body_lateral_undulation_deg: 40  # daha agresif
    body_z_lift: true  # gövde yerden kalkar (gallop benzeri)
  
  swim_crocodile:
    pattern: tail_lateral_wave
    cycle_duration_seconds: 1.0
    tail_amplitude_deg: 35  # büyük kuyruk salınımı
    legs_tucked_back: true  # bacaklar gövdeye yapışık
    propulsion_from: tail
```

---

## Mesh Hints

```yaml
radius_profiles:
  spine:
    - {t: 0.0, r: 0.10}   # tail base
    - {t: 0.2, r: 0.12}   # pelvis bulge
    - {t: 0.5, r: 0.14}   # belly midpoint
    - {t: 0.8, r: 0.12}   # shoulder
    - {t: 0.9, r: 0.10}   # neck
    - {t: 1.0, r: 0.09}   # head/snout
  tail:
    - {t: 0.0, r: 0.10}   # tail base = belly thickness
    - {t: 0.5, r: 0.05}
    - {t: 1.0, r: 0.005}  # ip ince
  leg:
    - {t: 0.0, r: 0.04}   # shoulder
    - {t: 0.4, r: 0.035}  # elbow
    - {t: 0.8, r: 0.025}  # ankle
    - {t: 1.0, r: 0.04}   # foot pad
```

---

## Stylization Knobs

```yaml
crocodile:
  snout_length_multiplier: 2.0
  tail_length_multiplier: 1.5
  body_armor_scales: true  # geometry nodes scale pattern

turtle:
  shell_present: true
  leg_length_multiplier: 0.5
  body_compressed_z: 0.6
  tail_length_multiplier: 0.2

gecko_realistic:
  toe_pads_present: true  # parmak ucu yapışkan
  eye_size_multiplier: 1.4
```

---

## Common Defects

- Bacak yere bakar (digitigrade gibi); reptiles sprawled (yana açık)
- Gövde yere değmiyor (Z yerden uzak); reptilian belly close to ground
- Kuyruk hareketsiz (oysa kuyruk denge için sürekli salınır)
- Boyun çok uzun (reptilian neck genelde kısa, hareket head-level)

---

## Recommended Clips

```yaml
recommended_clips:
  - {name: idle_breathe_basking, duration: 5.0, loop: true}
  - {name: walk_sprawl, duration: 1.5, loop: true}
  - {name: run_fast, duration: 0.5, loop: true}
  - {name: tail_whip, duration: 0.8, loop: false}      # defansif kuyruk savurma
  - {name: bite_attack, duration: 0.7, loop: false}
  - {name: hiss_threat, duration: 1.2, loop: false}    # ağız açık + body raised
  - {name: hit_react, duration: 0.4, loop: false}
  - {name: death, duration: 2.0, loop: false}
```
