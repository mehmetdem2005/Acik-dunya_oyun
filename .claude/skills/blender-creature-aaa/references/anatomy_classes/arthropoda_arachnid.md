# Anatomy Class: Arthropoda Arachnid

8 bacaklı eklem bacaklılar. Vücut iki ana parça: **cephalothorax** (baş+göğüs birleşik) + **abdomen** (karın).

**Örnekler:** Örümcek, akrep, kene, harvestman (uzun bacaklı).

---

## Proportions

```yaml
# Body length = cephalothorax_length + abdomen_length
cephalothorax_length: 0.30  # ön gövde
cephalothorax_width: 0.30
cephalothorax_height: 0.20

abdomen_length: 0.70  # arka, daha büyük (spider'da yumru)
abdomen_width: 0.45
abdomen_height: 0.45  # neredeyse küresel

leg_count: 8
leg_length_ratio: 1.5-3.0  # body_length'in 1.5-3 katı (çıkık)
leg_segments_per_leg: 7  # koksa-trochanter-femur-patella-tibia-metatarsus-tarsus

# Chelicerae (ön çene-pençeler)
chelicerae_present: true
chelicerae_length_ratio: 0.10

# Akrep özel:
# - Tail (metasoma) varsa: body_length'in %80'i, 5-6 segment + telson (stinger)
# - Pedipalp (ön kıskaç): büyük, foreleg-like
```

---

## Skeleton Structure

```yaml
bones:
  - {name: root_master, type: control, parent: null}
  
  # İki ana gövde parçası
  - {name: cephalothorax, type: deform, parent: root_master}
  - {name: abdomen, type: deform, parent: cephalothorax}  # connected by petiole
  
  # Akrep tail (varsa)
  - {name: metasoma_00, type: deform, parent: abdomen}
  - {name: metasoma_01, type: deform, parent: metasoma_00}
  - {name: metasoma_02, type: deform, parent: metasoma_01}
  - {name: metasoma_03, type: deform, parent: metasoma_02}
  - {name: metasoma_04, type: deform, parent: metasoma_03}
  - {name: telson, type: deform, parent: metasoma_04}  # stinger
  
  # 8 bacak: leg_<N>_<L|R>, N=1..4 (front to rear)
  # Her bacak 4 control bone (basitleştirilmiş, gerçekte 7 segment ama oyun için 4 yeter)
  # leg_1 = ön, leg_4 = arka
  
  # Sadece L tarafı örneği, R simetri:
  - {name: leg_1_coxa_L, type: deform, parent: cephalothorax}
  - {name: leg_1_femur_L, type: deform, parent: leg_1_coxa_L}
  - {name: leg_1_tibia_L, type: deform, parent: leg_1_femur_L}
  - {name: leg_1_tarsus_L, type: deform, parent: leg_1_tibia_L}
  - {name: leg_1_ik_L, type: control_ik_target}
  - {name: leg_1_pole_L, type: control_pole}
  # ... leg_2_, leg_3_, leg_4_
  
  # Pedipalp (örümcek ön sensör/kıskaç bacak)
  - {name: pedipalp_L, type: deform, parent: cephalothorax}
  - {name: pedipalp_R, type: deform, parent: cephalothorax}
  
  # Chelicerae (ön çene)
  - {name: chelicera_L, type: deform, parent: cephalothorax}
  - {name: chelicera_R, type: deform, parent: cephalothorax}

bone_count_estimate: 50-70  # 8 bacak × 4 + body + tail varsa + chelicerae
```

---

## Locomotion

```yaml
gaits:
  walk_arachnid:
    # 8 bacaklı yürüyüş: 4 set'ten 2'si havada, 2'si yerde (alternating tetrapod)
    pattern: alternating_tetrapod
    # Aynı anda yerde: leg_1_L, leg_3_L, leg_2_R, leg_4_R (diagonal grup)
    # Diğer set: leg_2_L, leg_4_L, leg_1_R, leg_3_R
    phase_offsets:
      leg_1_L: 0.0
      leg_3_L: 0.0
      leg_2_R: 0.0
      leg_4_R: 0.0
      leg_2_L: 0.5
      leg_4_L: 0.5
      leg_1_R: 0.5
      leg_3_R: 0.5
    cycle_duration_seconds: 0.6
    stride_length_ratio: 0.10
    foot_lift_height_ratio: 0.06
  
  run_arachnid:
    pattern: alternating_tetrapod_fast
    cycle_duration_seconds: 0.25
    foot_lift_height_ratio: 0.15
  
  scorpion_stinger_strike:
    pattern: tail_overhead_arc
    cycle_duration_seconds: 0.4
    tail_position: arch_over_back_then_forward_strike
  
  ambush_pose:
    pattern: static_with_subtle_breathing
    legs_spread: true
    body_low_to_ground: true
```

---

## Mesh Hints

```yaml
mesh_shape_hints:
  cephalothorax: rounded_rectangular
  abdomen: spherical_or_teardrop
  legs: tapered_cylinder_with_kink_at_patella
  hair_present: optional  # tarantula has visible setae

radius_profiles:
  abdomen:
    - {t: 0.0, r: 0.20}  # peduncle connection
    - {t: 0.4, r: 0.40}  # bulk peak
    - {t: 1.0, r: 0.05}  # tail end
  leg:
    - {t: 0.0, r: 0.04}   # coxa
    - {t: 0.3, r: 0.025}  # femur
    - {t: 0.6, r: 0.015}  # tibia
    - {t: 1.0, r: 0.008}  # tarsus tip
```

---

## Stylization Knobs

```yaml
spider_tarantula:
  legs_thick: true
  hair_setae_visible: true
  body_size_multiplier: 1.5

spider_orb_weaver:
  abdomen_size_multiplier: 1.5  # büyük yumru karın
  leg_length_multiplier: 1.2

scorpion:
  has_tail: true
  pedipalp_size_multiplier: 2.0  # kıskaç büyük
  body_armor_segmented: true

harvestman:
  leg_length_multiplier: 5.0  # ÇOK uzun bacaklar
  body_size_multiplier: 0.5
```

---

## Common Defects

- 6 bacak görünmesi (insect ile karıştırma); arachnid 8 olmalı
- Bacak segmentleri düz çizgi (oysa eklem yerlerinde belirgin köşeler)
- Cephalothorax + abdomen arasında peduncle (ince bel) yok
- Gait sync hatası — 8 bacak alternating tetrapod karmaşık

---

## Recommended Clips

```yaml
recommended_clips:
  - {name: idle_ambush, duration: 4.0, loop: true}
  - {name: walk_loop, duration: 0.6, loop: true}
  - {name: run_loop, duration: 0.25, loop: true}
  - {name: pounce_attack, duration: 0.5, loop: false}    # leap forward + legs grab
  - {name: bite_chelicerae, duration: 0.5, loop: false}
  - {name: scorpion_sting, duration: 0.6, loop: false}   # opsiyonel akrep
  - {name: defensive_threat, duration: 1.5, loop: false} # ön bacaklar yukarda
  - {name: hit_react, duration: 0.4, loop: false}
  - {name: death_curl, duration: 2.0, loop: false}       # bacaklar içeri kıvrılır
```
