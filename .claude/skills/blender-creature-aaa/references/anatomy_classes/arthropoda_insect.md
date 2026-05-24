# Anatomy Class: Arthropoda Insect

6 bacaklı eklem bacaklılar. Vücut üç parça: **head + thorax + abdomen**. Genelde antenler var, bazılarında kanat.

**Örnekler:** Karınca, hamamböceği, çekirge, böcek, kelebek, sinek, arı.

---

## Proportions

```yaml
# Body length = head + thorax + abdomen
head_length: 0.20
head_width: 0.18

thorax_length: 0.30  # bacaklar buradan çıkar
thorax_width: 0.25

abdomen_length: 0.50  # uzun arka kısım
abdomen_width: 0.22

leg_count: 6
legs_attached_to: thorax  # önemli — abdomen'a değil
leg_length_ratio: 0.5-1.5  # body_length'in 0.5-1.5 katı
leg_segments_per_leg: 5  # koksa-trochanter-femur-tibia-tarsus

# Antennae
antenna_count: 2
antenna_length_ratio: 0.3-1.0  # body length'e göre, böcek tipine bağlı

# Wings (varsa)
wings_present: optional
wing_count: 4  # genelde 2 çift (ön + arka), sinek 2 (1 çift)
wing_length_ratio: 0.8  # body_length'in %80'i

# Mandibles (çene)
mandibles_present: true
```

---

## Skeleton Structure

```yaml
bones:
  - {name: root_master, type: control, parent: null}
  
  # Üç ana segment
  - {name: head, type: deform, parent: root_master}
  - {name: thorax, type: deform, parent: head}  # head'in arkasında
  - {name: abdomen, type: deform, parent: thorax}
  
  # Multi-segment abdomen (opsiyonel, esneklik için)
  - {name: abdomen_01, type: deform, parent: abdomen}
  - {name: abdomen_02, type: deform, parent: abdomen_01}
  - {name: abdomen_tip, type: deform, parent: abdomen_02}
  
  # Mandibles
  - {name: mandible_L, type: deform, parent: head}
  - {name: mandible_R, type: deform, parent: head}
  
  # Antennae (her bir antenne 3 segment)
  - {name: antenna_L_00, type: deform, parent: head}
  - {name: antenna_L_01, type: deform, parent: antenna_L_00}
  - {name: antenna_L_02, type: deform, parent: antenna_L_01}
  - {name: antenna_R_00, type: deform, parent: head}
  - {name: antenna_R_01, type: deform, parent: antenna_R_00}
  - {name: antenna_R_02, type: deform, parent: antenna_R_01}
  
  # 6 bacak: leg_1 (front), leg_2 (middle), leg_3 (rear), her biri L+R
  # Her bacak 3 control bone (basitleştirilmiş)
  # leg_<N>_<L|R>:
  - {name: leg_1_coxa_L, type: deform, parent: thorax}
  - {name: leg_1_femur_L, type: deform, parent: leg_1_coxa_L}
  - {name: leg_1_tibia_L, type: deform, parent: leg_1_femur_L}
  - {name: leg_1_ik_L, type: control_ik_target}
  - {name: leg_1_pole_L, type: control_pole}
  # ... leg_2_, leg_3_ (and R)
  
  # Wings (opsiyonel)
  - {name: wing_front_L, type: deform, parent: thorax}
  - {name: wing_front_R, type: deform, parent: thorax}
  - {name: wing_rear_L, type: deform, parent: thorax}
  - {name: wing_rear_R, type: deform, parent: thorax}

bone_count_estimate: 35-50  # without wings
                              # 39-54 with wings
```

---

## Locomotion

```yaml
gaits:
  walk_insect:
    # 6 bacaklı yürüyüş: "tripod gait" — 3 bacak yerde, 3 havada
    # Set A: leg_1_L, leg_3_L, leg_2_R (diagonal triangle)
    # Set B: leg_2_L, leg_1_R, leg_3_R
    pattern: tripod_gait
    phase_offsets:
      leg_1_L: 0.0
      leg_3_L: 0.0
      leg_2_R: 0.0
      leg_2_L: 0.5
      leg_1_R: 0.5
      leg_3_R: 0.5
    cycle_duration_seconds: 0.3  # hızlı
    stride_length_ratio: 0.20
    foot_lift_height_ratio: 0.08
    body_z_oscillation: minimal  # gövde rigid, bacaklar hareket eder
  
  run_insect:
    pattern: tripod_gait_fast
    cycle_duration_seconds: 0.12
    foot_lift_height_ratio: 0.15
  
  jump_grasshopper:
    pattern: rear_legs_synced_explosion
    cycle_duration_seconds: 0.8  # ramp + launch + air + land
    rear_leg_explosion_frame: 0.3
    jump_distance_ratio: 5.0  # body_length'in 5 katı
    body_arc_in_air: true
  
  flap_wings:
    # Sinek, arı, kelebek
    pattern: wings_oscillate
    cycle_duration_seconds: 0.05  # arı: 200Hz, oyun için subsample
    wing_rotation_amplitude_deg: 90  # büyük amplitude
    figure_8_pattern: true  # arı kanat 8 şeklinde çizer
```

---

## Mesh Hints

```yaml
radius_profiles:
  body_combined:
    # Head + thorax + abdomen tek curve gibi
    - {t: 0.0, r: 0.08}    # abdomen tip
    - {t: 0.25, r: 0.15}   # abdomen bulk
    - {t: 0.5, r: 0.12}    # thorax
    - {t: 0.75, r: 0.10}   # head
    - {t: 1.0, r: 0.08}    # head front
  leg:
    - {t: 0.0, r: 0.02}    # coxa
    - {t: 0.3, r: 0.018}   # femur
    - {t: 0.6, r: 0.012}   # tibia
    - {t: 1.0, r: 0.006}   # tarsus
  antenna:
    - {t: 0.0, r: 0.005}
    - {t: 1.0, r: 0.002}
```

---

## Stylization Knobs

```yaml
ant:
  body_segmented_pronounced: true
  petiole_visible: true  # ince bel
  size_class: small

grasshopper:
  rear_legs_giant: true
  rear_leg_femur_ratio: 0.3  # vücudun %30'u kadar femur
  wings_present: true

beetle:
  elytra_present: true  # sert ön kanatlar
  body_shape: rounded_dome
  legs_short: true

butterfly:
  wing_size_giant: true
  wing_length_ratio: 1.2  # body'den uzun
  body_thin: true

bee:
  hair_setae: true
  abdomen_striped_pattern: true
  stinger_present: true
```

---

## Common Defects

- 8 bacak (arachnid ile karıştırma); insect 6 olmalı
- Bacaklar abdomen'dan çıkıyor (oysa thorax'tan)
- Antenne'ler statik (oysa subtle hareket etmeli)
- Mandibles eksik / hareketsiz
- Wing flutter rate gerçekçi değil

---

## Recommended Clips

```yaml
recommended_clips:
  - {name: idle_antenna_twitch, duration: 3.0, loop: true}  # statik + antenne hareket
  - {name: walk_loop, duration: 0.3, loop: true}
  - {name: run_loop, duration: 0.12, loop: true}
  - {name: flap_wings_loop, duration: 0.05, loop: true}     # opsiyonel
  - {name: takeoff, duration: 0.4, loop: false}
  - {name: landing, duration: 0.6, loop: false}
  - {name: bite_attack, duration: 0.4, loop: false}         # mandibles
  - {name: sting_attack, duration: 0.5, loop: false}        # opsiyonel (arı/akrep)
  - {name: jump_explosion, duration: 0.8, loop: false}      # çekirge
  - {name: death_legs_curl, duration: 2.0, loop: false}
```
