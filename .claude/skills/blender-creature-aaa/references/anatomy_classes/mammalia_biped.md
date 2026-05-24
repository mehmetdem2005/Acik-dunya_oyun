# Anatomy Class: Mammalia Biped

İki ayak üstünde duran memeliler. Plantigrade (insan) veya digitigrade-jumping (kanguru).

**Örnekler:** İnsan, goril, şempanze, orangutan, kanguru, dev kertenkele (bipedal duruyorsa).

---

## Proportions (vücut uzunluğunun oranı olarak)

```yaml
# İnsanlar için (8-head canon)
head_to_body: 0.125
head_width: 0.085
head_depth: 0.095
neck_length: 0.06
neck_radius_ratio: 0.4

torso_length: 0.32
torso_width_shoulder: 0.22  # omuz genişliği
torso_width_hip: 0.16
chest_depth: 0.18

arm_length_full: 0.39  # parmak ucuna kadar
arm_upper_length: 0.16  # humerus
arm_lower_length: 0.14  # radius+ulna
hand_length: 0.09

leg_length_full: 0.48  # toplam (kalça-ayak)
leg_upper_length: 0.22  # femur
leg_lower_length: 0.20  # tibia
foot_length: 0.13

# Stilizasyon override'ları
# - Çocuk: head_to_body = 0.20 (büyük kafa)
# - Heroik: shoulder = 0.28 (geniş omuz)
# - Anime: leg_length_full = 0.55
```

---

## Skeleton Structure

```yaml
bones:
  # Center / Spine (head down)
  - {name: root_master, type: control, parent: null, position_hint: ground_center}
  - {name: spine_hip, type: deform, parent: root_master}
  - {name: spine_lumbar, type: deform, parent: spine_hip}
  - {name: spine_thoracic, type: deform, parent: spine_lumbar}
  - {name: spine_chest, type: deform, parent: spine_thoracic}
  - {name: neck_00, type: deform, parent: spine_chest}
  - {name: neck_01, type: deform, parent: neck_00}
  - {name: head, type: deform, parent: neck_01}
  - {name: jaw, type: deform, parent: head}
  
  # Arms (L + R)
  - {name: clavicle_L, type: deform, parent: spine_chest}
  - {name: upper_arm_L, type: deform, parent: clavicle_L}
  - {name: forearm_L, type: deform, parent: upper_arm_L}
  - {name: hand_L, type: deform, parent: forearm_L}
  # (Optional: fingers — 5 × 3 phalanx, çok mobile için skip)
  - {name: hand_ik_L, type: control_ik_target}
  - {name: hand_pole_L, type: control_pole}
  
  # Legs (L + R)
  - {name: thigh_L, type: deform, parent: spine_hip}
  - {name: shin_L, type: deform, parent: thigh_L}
  - {name: foot_L, type: deform, parent: shin_L}
  - {name: toe_L, type: deform, parent: foot_L}
  - {name: foot_ik_L, type: control_ik_target}
  - {name: knee_pole_L, type: control_pole}
  
  # (R suffix mirror)

bone_count_estimate: 28-40 (with optional fingers: 60+)
```

---

## Locomotion (Gait Patterns)

```yaml
gaits:
  walk:
    pattern: alternate_2beat
    phase_offsets:
      LF: 0.0  # left foot
      RF: 0.5  # right foot, opposite phase
    cycle_duration_seconds: 1.0  # 60 BPM walk
    stride_length_ratio: 0.25
    foot_lift_height_ratio: 0.06
    arm_swing: counter_to_leg  # sol bacak ileri → sağ kol ileri
  
  run:
    pattern: alternate_2beat
    phase_offsets:
      LF: 0.0
      RF: 0.5
    cycle_duration_seconds: 0.4
    stride_length_ratio: 0.45
    foot_lift_height_ratio: 0.18
    flight_phase_present: true  # her iki ayak bir an havada
    spine_pitch_forward_deg: 15  # koşarken gövde öne eğik
  
  jump_kangaroo:
    pattern: both_feet_synced
    phase_offsets:
      LF: 0.0
      RF: 0.0  # her iki ayak aynı anda
    cycle_duration_seconds: 0.6
    foot_lift_height_ratio: 0.5
    tail_counter_swing: true  # kanguru: kuyruk denge için ters salınır
```

---

## Mesh Hints

```yaml
mesh_shape_hints:
  body_shape: "ellipsoid_torso + cylindrical_limbs + spherical_head"
  shoulder_pronounced: true  # deltoid kası belirgin
  hip_to_waist_ratio: 1.3  # erkek için, kadın için 1.5
  
radius_profiles:
  spine:
    - {t: 0.0, r: 0.14}    # hip
    - {t: 0.5, r: 0.18}    # ribcage peak
    - {t: 0.7, r: 0.10}    # neck
    - {t: 1.0, r: 0.13}    # head
  arm:
    - {t: 0.0, r: 0.08}    # shoulder bulk
    - {t: 0.3, r: 0.06}    # biceps
    - {t: 0.5, r: 0.05}    # elbow
    - {t: 0.7, r: 0.04}    # forearm
    - {t: 1.0, r: 0.025}   # wrist
  leg:
    - {t: 0.0, r: 0.10}    # hip/glute
    - {t: 0.25, r: 0.09}   # quad bulk
    - {t: 0.5, r: 0.06}    # knee
    - {t: 0.75, r: 0.07}   # calf
    - {t: 1.0, r: 0.04}    # ankle
```

---

## Stylization Knobs

```yaml
# Heroic
heroic:
  shoulder_width_multiplier: 1.3
  arm_muscle_definition: exaggerated
  leg_length_multiplier: 1.1
  head_size_multiplier: 0.95

# Chibi / Stylized
chibi:
  head_size_multiplier: 2.0
  body_length_multiplier: 0.7
  limb_length_multiplier: 0.7

# Realistic
realistic:
  muscle_definition: normal
  proportions: human_8head
```

---

## Common Defects to Watch (M01 patterns'tan)

- Omuz pozisyonu çok yukarda (clavicle inaccurate)
- Topuk pozisyonu yanlış (foot bone foot_ik'ten farklı yere bakıyor olabilir)
- Boyun çok kalın veya kafa çok küçük
- Arm length çok uzun (gorilla-arms)

---

## Animation Suggestions

```yaml
recommended_clips:
  - {name: idle_breathe, duration: 4.0, loop: true}
  - {name: walk_loop, duration: 1.0, loop: true}
  - {name: run_loop, duration: 0.5, loop: true}
  - {name: jump_one_shot, duration: 1.2, loop: false}
  - {name: attack_punch, duration: 0.8, loop: false}
  - {name: hit_react, duration: 0.5, loop: false}
  - {name: death, duration: 2.5, loop: false}
  - {name: idle_wave, duration: 2.0, loop: false}  # opsiyonel
```
