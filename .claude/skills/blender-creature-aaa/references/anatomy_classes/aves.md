# Anatomy Class: Aves (Kuşlar)

İki ayaklı + uçucu omurgalılar. Skeleton birleşik (synsacrum), kemikler içi boş.

**Örnekler:** Kartal, kuzgun, baykuş, tavuk, papağan, leylek, kuğu.

---

## Proportions

```yaml
# Body length = burun ucu → kuyruk ucu (kanat dahil değil)
head_size_ratio: 0.18  # büyük gözlü, kısa boyun
beak_length: 0.08  # tür değişir (uzun: leylek 0.20; kısa: papağan 0.05)
neck_length: 0.20  # esnek, S şeklinde
neck_radius_ratio: 0.4

torso_length: 0.40
torso_width: 0.18  # genelde compact ellipsoid
chest_depth: 0.22  # uçucu kuşlarda derin (sternum büyük)

wing_length_full: 0.85  # body_length'in %85'i, açıkken çift = wingspan 1.7×
wing_upper_arm: 0.30  # humerus
wing_forearm: 0.28  # radius+ulna
wing_primary_feathers: 0.30  # uzun tüyler

leg_length: 0.30  # tibiotarsus + tarsometatarsus
foot_length: 0.10
toe_count: 3-4  # default 4, 3 öne 1 arkaya (anisodactyl)

tail_length: 0.20  # rectrices feather length, kemik kısa (pygostyle)

# Stilizasyon
# - Owl: head_size_ratio 0.30, big eyes
# - Eagle: beak hooked, sharp talons
# - Penguin: wing_length 0.30 (paddle), can't fly
```

---

## Skeleton Structure

```yaml
bones:
  - {name: root_master, type: control, parent: null}
  - {name: spine_synsacrum, type: deform, parent: root_master}  # birleşik pelvis+lumbar
  - {name: spine_thoracic, type: deform, parent: spine_synsacrum}
  - {name: keel, type: deform, parent: spine_thoracic}  # sternum (göğüs kemiği)
  
  # Neck (esnek, S-curve)
  - {name: neck_00, type: deform, parent: spine_thoracic}
  - {name: neck_01, type: deform, parent: neck_00}
  - {name: neck_02, type: deform, parent: neck_01}
  - {name: neck_03, type: deform, parent: neck_02}  # 4 segment yeterli
  - {name: head, type: deform, parent: neck_03}
  - {name: beak_upper, type: deform, parent: head}
  - {name: beak_lower, type: deform, parent: head}  # ağız açma
  
  # Wings (L + R)
  - {name: wing_upper_L, type: deform, parent: spine_thoracic}
  - {name: wing_forearm_L, type: deform, parent: wing_upper_L}
  - {name: wing_hand_L, type: deform, parent: wing_forearm_L}
  # Wing primary feathers (4-6 control bone, opsiyonel)
  - {name: wing_primaries_L_00, type: deform, parent: wing_hand_L}
  - {name: wing_primaries_L_01, type: deform, parent: wing_hand_L}
  
  # Legs (L + R)
  - {name: thigh_L, type: deform, parent: spine_synsacrum}
  - {name: tibiotarsus_L, type: deform, parent: thigh_L}  # alt bacak (birleşik)
  - {name: tarsometatarsus_L, type: deform, parent: tibiotarsus_L}  # ayak bilek (uzun)
  - {name: toes_L, type: deform, parent: tarsometatarsus_L}
  - {name: foot_ik_L, type: control_ik_target}
  
  # Tail feathers (rectrices)
  - {name: tail_pygostyle, type: deform, parent: spine_synsacrum}
  - {name: tail_rect_00, type: deform, parent: tail_pygostyle}  # opsiyonel feather fan

bone_count_estimate: 25-40
```

---

## Locomotion

```yaml
gaits:
  walk_ground:
    pattern: alternate_2beat
    phase_offsets: {LF: 0.0, RF: 0.5}
    cycle_duration_seconds: 0.6  # küçük kuş hızlı
    stride_length_ratio: 0.15
    head_bob_amplitude: 0.04  # tavuk gibi başını ileri-geri sallar
  
  hop:
    pattern: both_feet_synced  # serçe, sıçrayarak yürür
    phase_offsets: {LF: 0.0, RF: 0.0}
    cycle_duration_seconds: 0.3
    foot_lift_height_ratio: 0.10
  
  flap_flight:
    pattern: synchronized_wings
    cycle_duration_seconds: 0.4  # kanat çırpma hızı
    wing_up_down_amplitude_deg: 80
    body_z_oscillation_ratio: 0.05  # gövde hafif yukarı-aşağı
    legs_tucked: true  # uçarken ayaklar gövdeye yapışık
  
  glide:
    pattern: wings_extended_static
    wing_position: spread_horizontal
    body_pitch_deg: -3  # hafif aşağı bakar
```

---

## Mesh Hints

```yaml
radius_profiles:
  spine:
    - {t: 0.0, r: 0.10}   # pygostyle (kuyruk dibi)
    - {t: 0.3, r: 0.14}   # synsacrum bulk
    - {t: 0.5, r: 0.16}   # ribcage peak (chest)
    - {t: 0.7, r: 0.08}   # neck ince
    - {t: 0.9, r: 0.10}   # head
    - {t: 1.0, r: 0.04}   # beak ucu
  wing:
    - {t: 0.0, r: 0.06}   # shoulder
    - {t: 0.5, r: 0.04}   # elbow
    - {t: 1.0, r: 0.02}   # wing tip
  leg:
    - {t: 0.0, r: 0.05}   # thigh
    - {t: 0.5, r: 0.03}   # tibia
    - {t: 1.0, r: 0.02}   # ankle
```

---

## Stylization Knobs

```yaml
owl:
  head_size_multiplier: 1.5
  eye_size_multiplier: 2.0  # büyük gözler
  neck_length_multiplier: 0.7  # kısa boyun
  beak_curve: hooked_short

eagle:
  beak_curve: hooked_sharp
  talon_size_multiplier: 1.5
  wing_length_multiplier: 1.2  # geniş kanat

penguin:
  wing_length_multiplier: 0.3
  can_fly: false
  body_upright: true  # dik durur
```

---

## Common Defects

- Wing membrane (patagium) eksik
- Bacak çok ön/arkada (kuşlarda bacak gövdenin orta-ön)
- Beak open/close animation eksik (head'e parent değil)
- Neck rigid (S-curve esnek olmalı, 4 segment minimum)

---

## Recommended Clips

```yaml
recommended_clips:
  - {name: idle_perch, duration: 3.0, loop: true}        # tünekken
  - {name: walk_ground, duration: 0.8, loop: true}
  - {name: flap_takeoff, duration: 1.5, loop: false}
  - {name: flap_flight_loop, duration: 0.4, loop: true}
  - {name: glide_loop, duration: 2.0, loop: true}
  - {name: landing, duration: 1.0, loop: false}
  - {name: peck_attack, duration: 0.6, loop: false}      # kafa öne dart
  - {name: vocalize_call, duration: 1.5, loop: false}    # beak açık + body shake
```
