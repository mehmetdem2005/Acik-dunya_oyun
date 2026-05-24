# Agent P12: Animator (Animatör)

```yaml
agent_id: animator
agent_name_tr: Animatör
agent_name_en: Animator
category: production
order_index: 12
implementation_mode: subprocess
estimated_duration_minutes: 5-15
critical_path: true
```

---

## 1. ROLE SUMMARY

Skinning'i tamamlanmış yaratık için **prosedürel animasyon klipleri** üretir. Her klip için F-Curve'ler matematik formüllerden (sinüs, kosinüs, faz offset) hesaplanır, anatomy_class'taki **gait phase pattern**'lerine uyar.

**Kapsam:**
- Walk, trot, run, gallop, bound (gait varianları)
- Idle (nefes alma)
- Attack (saldırı)
- Hit react, death
- Howl / vocalize (opsiyonel)

**Çıktı her klip için:** Blender Action data + NLA strip (Godot import için).

---

## 2. WHEN INVOKED

### Preconditions
- `skinned_v1.blend` mevcut (P08'den), armature + skinned mesh
- IK constraint'ler kurulu (P03)
- `BudgetSpec.animation_clips` listesi tanımlı (hangi klipler)
- `references/anatomy_classes/<class>.md` içinde gait phase offsets var

### Postconditions
- `animated_v1.blend` mevcut, her klip için ayrı Action
- NLA tracks kurulu (export-ready)
- `AnimationManifest.json` yazılmış
- Tüm IK foot bone'ları ground-plane'e yakın frame'lerde Z≈0 (foot sliding yok)

### Sıralama
- **Önceki:** P09 Corrective Sculptor veya P11 Material Alchemist
- **Sonraki:** P13 Exporter
- **Critic:** C01 Vision + C04 Animation Critic (cycle frame'leri üzerinden)

---

## 3. INPUTS

```
skinned_v1.blend                     # P08 çıktısı
SkeletonBlueprint.json               # IK chain ve foot bone isimleri için
BudgetSpec.json                      # animation_clips listesi
anatomy_class.md                     # gait phase offsets, cycle durations
CreatureSpec.json                    # locomotion bilgileri (max speed, gait list)
```

---

## 4. OUTPUTS

### 4.1 AnimationManifest.json

```json
{
  "manifest_version": "1.0",
  "creature_id": "kurt_001",
  "fps": 30,
  "clips": [
    {
      "name": "idle_breathe",
      "frame_start": 1,
      "frame_end": 120,
      "duration_seconds": 4.0,
      "loop": true,
      "type": "breath",
      "action_name": "Action_idle_breathe",
      "nla_track_name": "NLA_idle_breathe",
      "fcurve_count": 12,
      "foot_sliding_max_z_error": 0.002
    },
    {
      "name": "walk_loop",
      "frame_start": 1,
      "frame_end": 30,
      "duration_seconds": 1.0,
      "loop": true,
      "type": "walk_4beat",
      "gait_phase_offsets": {
        "LF": 0.0, "RR": 0.25, "RF": 0.5, "LR": 0.75
      },
      "action_name": "Action_walk_loop",
      "fcurve_count": 38,
      "foot_sliding_max_z_error": 0.001
    }
    // ... her klip
  ],
  "total_actions": 7,
  "total_nla_tracks": 7,
  "validation": {
    "no_jerky_curves": true,
    "no_foot_intersection": true,
    "all_loops_seamless": true,
    "tangent_type": "AUTO_CLAMPED"
  },
  "generated_by": "P12_animator",
  "generated_at": "2026-05-24T..."
}
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN ANİMATÖRSÜN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Sen AAA stüdyolarda 10+ yıl deneyimli karakter animatörsün. Hem
key-frame hem prosedürel animasyon konusunda usta. Naughty Dog,
Rockstar, Insomniac tarzı yaratık animasyonlarından geçen "gait
biomechanics + sinusoidal phase pattern" felsefesini biliyorsun.

GÖREVİN:
Skinning'i tamamlanmış yaratığa anatomi-doğru animasyon klipleri
üret. F-Curve'leri matematik formüllerle hesapla, gait phase
offsetlerine sadık kal, foot sliding'i sıfıra indir.

KESİN KURALLAR:

  K1. ASLA random F-Curve verisi koyma. Her keyframe matematik
      formülünden gelmeli. Sinüs/kosinüs + faz offset + amplitude.

  K2. Her gait'in phase offset pattern'i anatomy class'tan gelir.
      Örnek (mammalia_quadruped, trot):
        LF (sol ön): phase = 0
        RR (sağ arka): phase = 0 (LF ile diagonal pair)
        RF (sağ ön): phase = π
        LR (sol arka): phase = π (RF ile diagonal pair)

  K3. Foot Z trajectory rectified sinüs:
        z(t) = max(0, A * sin(2π * t/T + phase))
        Bu şekilde ayak yerden kalkar (Z>0), yere değer (Z=0).
        Z<0 ASLA olmaz (foot sliding/intersection).

  K4. Foot Y trajectory normal sinüs:
        y(t) = A * sin(2π * t/T + phase + π/2)
        İleri-geri salınım. Faz Z'den π/2 kayık çünkü ayak yerden
        kalktığında ileri gider, yere bastığında geri.

  K5. Body bounce: Z ekseninde 2x gait frequency, küçük amplitude.
        z_body(t) = A_bounce * |sin(2π * 2t/T)|

  K6. Spine roll (yan salınım): bound dışında her gait'te hafif.
        rot_z_spine(t) = A_roll * sin(2π * t/T + π/2)

  K7. Tail wag: idle/walk'ta yavaş, agresif gait'lerde hızlı.
        rot_z_tail(t) = A_wag * sin(2π * t/(T*2))  # walk'ta yarı freq

  K8. Head counter-bounce: gövde Z+ olduğunda hafif Z-, sürekli
      bakış stabilizasyonu için.

  K9. F-Curve tangent'ları AUTO_CLAMPED. Loop seamless olmak zorunda
      (start frame == end frame değeri).

  K10. Foot sliding test: walking sırasında ayak yerde olduğu
       frame'lerde Y velocity ≈ 0 olmalı. Eğer ayak yerdeyken Y
       hareket ediyorsa = foot sliding (kabul edilmez).

YAPMA:

  - Asla manuel keyframe ekleme; tüm keyframe'ler formülden
  - Linear interpolation yasak (auto/bezier zorunlu)
  - Anti-loop tangent (start ≠ end) yasak
  - Foot Z<0 asla
  - Maksimum amplitude'ü anatomi orantılarına bağla, hardcoded etme

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Klip Konfigürasyonu

Her klip kendi parametre setine sahip. BudgetSpec'ten gelen listeye göre dinamik:

```python
clip_configs = {
    "idle_breathe": {
        "frame_count": 120,  # 4 saniye @ 30fps
        "type": "breath",
        "params": {"breath_amplitude": body_length * 0.005, "breath_freq": 0.25},
    },
    "walk_loop": {
        "frame_count": 30,  # 1 saniye
        "type": "walk_4beat",
        "params": {
            "foot_lift_amplitude": body_length * 0.05,
            "stride_length": body_length * 0.15,
            "body_bounce": body_length * 0.01,
            "spine_roll_deg": 3,
            "tail_wag_deg": 5,
            "phase_offsets": {"LF": 0.0, "RR": 0.25, "RF": 0.5, "LR": 0.75},
        },
    },
    "run_loop": {
        "frame_count": 18,  # 0.6 saniye
        "type": "trot_diagonal",
        "params": {
            "foot_lift_amplitude": body_length * 0.10,
            "stride_length": body_length * 0.25,
            "body_bounce": body_length * 0.03,
            "spine_roll_deg": 5,
            "tail_wag_deg": 10,
            "phase_offsets": {"LF": 0.0, "RR": 0.0, "RF": 0.5, "LR": 0.5},
        },
    },
    "attack_bite": {
        "frame_count": 36,  # 1.2 saniye, one-shot
        "type": "lunge_bite",
        "params": {
            "lunge_distance": body_length * 0.2,
            "jaw_open_max_deg": 35,
            "head_attack_pitch_deg": 15,
        },
    },
    "hit_react": {
        "frame_count": 15,  # 0.5 saniye, one-shot
        "type": "jerk",
        "params": {
            "jerk_back_distance": body_length * 0.08,
            "spine_arch_deg": 8,
            "head_jerk_pitch_deg": -10,
        },
    },
    "death": {
        "frame_count": 60,  # 2 saniye, one-shot
        "type": "fall",
        "params": {
            "fall_axis": "lateral",  # yana düşer
            "settle_time_frames": 40,
        },
    },
    "howl": {
        "frame_count": 75,  # 2.5 saniye
        "type": "vocalize",
        "params": {
            "head_pitch_up_deg": 45,
            "jaw_open_amp_deg": 15,
            "neck_extend_amount": body_length * 0.05,
        },
    },
}
```

### 6.2 IK Foot Trajectory (Walk/Trot/Run)

Her IK foot bone için 3-channel F-Curve. Tüm formüller `t ∈ [0, 1]` (cycle ilerlemesi):

```python
import math

def foot_trajectory(t, phase_offset, lift_amp, stride_len):
    """
    Tek bir foot için (x, y, z) pozisyon delta (rest pose'a relative).
    
    t: cycle ilerlemesi 0..1
    phase_offset: bu foot'un faz kaydırması (gait'ten)
    lift_amp: ayak yukarı kalkma yüksekliği (metre)
    stride_len: adım uzunluğu (ileri-geri, metre)
    """
    phi = 2 * math.pi * (t + phase_offset)
    
    # Y (ileri-geri): normal sinüs
    y = stride_len * math.sin(phi + math.pi / 2)
    # Phase + π/2 sebebi: ayak en yüksek noktadayken ileride olmalı
    
    # Z (yukarı): rectified sinüs (negatif yok)
    z_raw = lift_amp * math.sin(phi)
    z = max(0.0, z_raw)
    
    # X (yan): genelde 0, sadece galop'ta hafif lateral
    x = 0.0
    
    return (x, y, z)
```

### 6.3 Body Bounce + Spine Roll

```python
def body_dynamics(t, params):
    """
    Spine root (genelde 'spine_hip' veya 'root_master') için:
    - Z bounce (2x gait freq)
    - Spine roll (gait freq, opposite to foot phase)
    """
    phi = 2 * math.pi * t
    
    # Z bounce: 2x freq, küçük amplitude
    z_bounce = params["body_bounce"] * abs(math.sin(2 * phi))
    
    # Spine roll: opposite to dominant foot's lateral
    # Walk için sin(phi + π/2), trot için sin(2*phi + π/2) (eş zamanlı diagonals)
    spine_roll_rad = math.radians(params["spine_roll_deg"]) * math.sin(phi + math.pi / 2)
    
    return {
        "spine_root_z_delta": z_bounce,
        "spine_root_roll_rad": spine_roll_rad,
    }
```

### 6.4 Tail Wag

```python
def tail_dynamics(t, params, tail_bones):
    """
    Kuyruk bone zincirinde damped wave.
    Her bone'un faz offset'i kendi index'iyle artar (whip-like).
    """
    base_phi = 2 * math.pi * t * 0.5  # walk'ta yarı freq
    amp = math.radians(params["tail_wag_deg"])
    
    wag_per_bone = {}
    for i, bone_name in enumerate(tail_bones):
        delay = i * 0.1  # her segment biraz geç
        wag_per_bone[bone_name] = {
            "rot_z_rad": amp * math.sin(base_phi - delay) * (1 - i * 0.1),  # tip'e doğru azalır
        }
    
    return wag_per_bone
```

### 6.5 Head Counter-Bounce

```python
def head_dynamics(t, params):
    """
    Head/neck stabilizasyon: gövde Z+ olunca kafa Z-.
    Bakış stabilizasyonu.
    """
    phi = 2 * math.pi * t
    
    return {
        "head_z_delta": -0.5 * params["body_bounce"] * abs(math.sin(2 * phi)),
        "neck_pitch_rad": math.radians(2) * math.sin(phi),
    }
```

### 6.6 Action Oluşturma

```python
def create_action_for_clip(armature_obj, clip_name, frame_count, fps=30):
    """Boş Action data ve onu armature'a bağla."""
    action = bpy.data.actions.new(f"Action_{clip_name}")
    
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    
    armature_obj.animation_data.action = action
    
    return action


def add_fcurve_for_bone_channel(action, bone_name, channel, array_index, samples):
    """
    Action'a F-Curve ekle.
    bone_name: kemik adı
    channel: 'location' veya 'rotation_euler' veya 'rotation_quaternion'
    array_index: 0=X, 1=Y, 2=Z (location/euler), 3=W (quat)
    samples: list of (frame, value)
    """
    data_path = f'pose.bones["{bone_name}"].{channel}'
    
    # Mevcut F-Curve'ü ara
    fc = action.fcurves.find(data_path, index=array_index)
    if fc is None:
        fc = action.fcurves.new(data_path, index=array_index)
    
    # Sample'ları ekle
    fc.keyframe_points.add(count=len(samples))
    for i, (frame, value) in enumerate(samples):
        kp = fc.keyframe_points[i]
        kp.co = (frame, value)
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = 'AUTO_CLAMPED'
        kp.handle_right_type = 'AUTO_CLAMPED'
    
    fc.update()
    return fc
```

### 6.7 Generate Walk Cycle

```python
def generate_walk_cycle(armature_obj, params, frame_count, fps=30):
    """
    Complete walk cycle generation. 4-beat phase pattern.
    """
    action = create_action_for_clip(armature_obj, "walk_loop", frame_count, fps)
    
    foot_bones = {
        "LF": "foot_ik_front_L",
        "RF": "foot_ik_front_R",
        "LR": "foot_ik_rear_L",
        "RR": "foot_ik_rear_R",
    }
    
    phase_offsets = params["phase_offsets"]
    lift_amp = params["foot_lift_amplitude"]
    stride_len = params["stride_length"]
    
    # Her foot için F-Curve set
    for foot_id, bone_name in foot_bones.items():
        phase = phase_offsets.get(foot_id, 0.0)
        
        # Frame range için sample'lar
        samples_y = []
        samples_z = []
        
        for frame in range(1, frame_count + 1):
            t = (frame - 1) / frame_count  # 0..1
            x, y, z = foot_trajectory(t, phase, lift_amp, stride_len)
            samples_y.append((frame, y))
            samples_z.append((frame, z))
        
        # Loop seamless: son frame == frame 1
        if samples_y[-1][1] != samples_y[0][1]:
            samples_y[-1] = (samples_y[-1][0], samples_y[0][1])
        if samples_z[-1][1] != samples_z[0][1]:
            samples_z[-1] = (samples_z[-1][0], samples_z[0][1])
        
        # F-Curve ekle
        add_fcurve_for_bone_channel(action, bone_name, "location", 1, samples_y)  # Y
        add_fcurve_for_bone_channel(action, bone_name, "location", 2, samples_z)  # Z
    
    # Body bounce + spine roll
    spine_root_bone = "root_master" if "root_master" in armature_obj.pose.bones else "spine_00"
    
    bounce_samples_z = []
    roll_samples = []
    for frame in range(1, frame_count + 1):
        t = (frame - 1) / frame_count
        dyn = body_dynamics(t, params)
        bounce_samples_z.append((frame, dyn["spine_root_z_delta"]))
        roll_samples.append((frame, dyn["spine_root_roll_rad"]))
    
    # Loop fix
    bounce_samples_z[-1] = (bounce_samples_z[-1][0], bounce_samples_z[0][1])
    roll_samples[-1] = (roll_samples[-1][0], roll_samples[0][1])
    
    add_fcurve_for_bone_channel(action, spine_root_bone, "location", 2, bounce_samples_z)
    # Rotation euler için bone önce euler mode'a alınmalı
    armature_obj.pose.bones[spine_root_bone].rotation_mode = 'XYZ'
    add_fcurve_for_bone_channel(action, spine_root_bone, "rotation_euler", 2, roll_samples)
    
    # Tail wag
    tail_bones = [b.name for b in armature_obj.pose.bones if b.name.startswith("tail_")]
    if tail_bones:
        for i, tail_bone in enumerate(sorted(tail_bones)):
            tail_samples = []
            for frame in range(1, frame_count + 1):
                t = (frame - 1) / frame_count
                tail_dyn = tail_dynamics(t, params, tail_bones)
                tail_samples.append((frame, tail_dyn[tail_bone]["rot_z_rad"]))
            tail_samples[-1] = (tail_samples[-1][0], tail_samples[0][1])
            armature_obj.pose.bones[tail_bone].rotation_mode = 'XYZ'
            add_fcurve_for_bone_channel(action, tail_bone, "rotation_euler", 2, tail_samples)
    
    # Head counter-bounce
    if "head" in armature_obj.pose.bones:
        head_z_samples = []
        for frame in range(1, frame_count + 1):
            t = (frame - 1) / frame_count
            head_dyn = head_dynamics(t, params)
            head_z_samples.append((frame, head_dyn["head_z_delta"]))
        head_z_samples[-1] = (head_z_samples[-1][0], head_z_samples[0][1])
        add_fcurve_for_bone_channel(action, "head", "location", 2, head_z_samples)
    
    return action
```

### 6.8 Idle (Breath)

```python
def generate_idle_breath(armature_obj, params, frame_count=120, fps=30):
    """
    Sadece nefes alma. Gövde Z çok küçük up-down (4 sn'de 1 cycle).
    """
    action = create_action_for_clip(armature_obj, "idle_breathe", frame_count, fps)
    
    breath_amp = params.get("breath_amplitude", 0.005)
    breath_freq = params.get("breath_freq", 0.25)  # 4 sn'lik cycle (= 0.25 Hz)
    
    spine_root = "spine_00" if "spine_00" in armature_obj.pose.bones else "root_master"
    
    # Tek tam cycle = frame_count frame
    samples = []
    for frame in range(1, frame_count + 1):
        t = (frame - 1) / frame_count
        phi = 2 * math.pi * t
        z_delta = breath_amp * math.sin(phi)
        samples.append((frame, z_delta))
    
    samples[-1] = (samples[-1][0], samples[0][1])
    
    add_fcurve_for_bone_channel(action, spine_root, "location", 2, samples)
    
    return action
```

### 6.9 Attack Bite (One-shot)

```python
def generate_attack_bite(armature_obj, params, frame_count=36, fps=30):
    """
    Lunge ileri + çene aç + ısır + çekil. One-shot.
    """
    action = create_action_for_clip(armature_obj, "attack_bite", frame_count, fps)
    
    lunge_dist = params["lunge_distance"]
    jaw_open = math.radians(params["jaw_open_max_deg"])
    head_pitch = math.radians(params["head_attack_pitch_deg"])
    
    # Anahtar frame'ler:
    # 0: rest
    # 25% windup: head back, slight crouch
    # 50% strike: lunge forward, jaw open max, head pitched
    # 75% bite: jaw closed
    # 100%: return to rest
    
    f_windup = int(frame_count * 0.25)
    f_strike = int(frame_count * 0.5)
    f_bite = int(frame_count * 0.75)
    f_end = frame_count
    
    # Root forward lunge
    root_name = "root_master" if "root_master" in armature_obj.pose.bones else "spine_00"
    
    root_y_samples = [
        (1, 0),
        (f_windup, -lunge_dist * 0.1),   # windup geri
        (f_strike, lunge_dist),           # ileri lunge
        (f_bite, lunge_dist * 0.9),       # hafif geri çek
        (f_end, 0),                       # geri dön
    ]
    add_fcurve_for_bone_channel(action, root_name, "location", 1, root_y_samples)
    
    # Jaw open
    if "jaw" in armature_obj.pose.bones:
        armature_obj.pose.bones["jaw"].rotation_mode = 'XYZ'
        jaw_samples = [
            (1, 0),
            (f_windup, jaw_open * 0.3),
            (f_strike, jaw_open),
            (f_bite, jaw_open * 0.1),
            (f_end, 0),
        ]
        add_fcurve_for_bone_channel(action, "jaw", "rotation_euler", 0, jaw_samples)  # X
    
    # Head pitch forward
    if "head" in armature_obj.pose.bones:
        armature_obj.pose.bones["head"].rotation_mode = 'XYZ'
        head_samples = [
            (1, 0),
            (f_windup, -head_pitch * 0.3),  # windup'ta geriye
            (f_strike, head_pitch),
            (f_bite, head_pitch * 0.8),
            (f_end, 0),
        ]
        add_fcurve_for_bone_channel(action, "head", "rotation_euler", 0, head_samples)
    
    return action
```

### 6.10 Hit React + Death + Howl

Hit react: short jerk back. Death: fall lateral + settle. Howl: head up + jaw small open oscillation. Pattern aynı: keyframe sequence + auto bezier tangent.

### 6.11 NLA Strip Setup (Godot Export İçin)

```python
def setup_nla_tracks(armature_obj, actions):
    """
    Her Action için bir NLA track ve onun içinde bir strip.
    Godot import edince her track ayrı clip olarak görür.
    """
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    
    ad = armature_obj.animation_data
    
    # Mevcut track'leri temizle (önceki run'lardan)
    while ad.nla_tracks:
        ad.nla_tracks.remove(ad.nla_tracks[0])
    
    # Action'ı temizle (NLA track'ler kullanılırken active action olmamalı)
    ad.action = None
    
    for action in actions:
        track = ad.nla_tracks.new()
        track.name = f"NLA_{action.name.replace('Action_', '')}"
        
        strip = track.strips.new(
            name=action.name,
            start=1,
            action=action,
        )
        strip.action_frame_start = action.frame_range[0]
        strip.action_frame_end = action.frame_range[1]
        
        # Loop clipler için
        if "loop" in action.name or "breathe" in action.name:
            strip.repeat = 1.0
            strip.use_animated_influence = False
```

### 6.12 Validation: Foot Sliding Test

```python
def validate_foot_sliding(armature_obj, action, foot_bones, fps=30):
    """
    Walk/run sırasında ayak yerde olduğu frame'lerde Y velocity ≈ 0.
    """
    max_slide_error = 0.0
    
    for bone_name in foot_bones:
        # Z F-Curve'ü ve Y F-Curve'ünü oku
        z_fc = action.fcurves.find(
            f'pose.bones["{bone_name}"].location', index=2
        )
        y_fc = action.fcurves.find(
            f'pose.bones["{bone_name}"].location', index=1
        )
        
        if z_fc is None or y_fc is None:
            continue
        
        # Z ≈ 0 olduğu frame'leri bul
        for kp_z in z_fc.keyframe_points:
            frame, z_val = kp_z.co
            if abs(z_val) < 0.005:  # ayak yerde
                # Aynı frame'de Y velocity
                y_val_curr = y_fc.evaluate(frame)
                y_val_next = y_fc.evaluate(frame + 1)
                velocity = abs(y_val_next - y_val_curr)
                
                # Walk cycle'da stride length / cycle frames = max velocity
                # Foot down phase'inde velocity ≈ 0 olmalı
                if velocity > 0.002:
                    max_slide_error = max(max_slide_error, velocity)
    
    return max_slide_error
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | Her klip için Action oluşturulmuş | error: yeniden generate |
| V2 | NLA track'ler kurulu, her action bir track'te | error: setup_nla yeniden |
| V3 | Loop clipler seamless (start == end frame value, ±0.001) | error: loop fix uygula |
| V4 | Foot sliding max < 0.005 birim/frame | warning: stride_length ayarla |
| V5 | Tüm F-Curve tangent'ları AUTO_CLAMPED veya BEZIER | error: tangent rewrite |
| V6 | Foot Z asla negatif değil | error: max(0, ...) kontrol |
| V7 | Jaw bone rotation X'i 90°'den fazla değil | warning: aşırı animasyon |
| V8 | Her clip'in fcurve count > 0 | error: clip boş çıkmış |

---

## 8. FAILURE MODES

### F1: SkeletonBlueprint'te beklenen foot IK bone yok
**Recovery:** Hata: P03'e geri dön, blueprint regenerate. Veya orchestrator'a "Mevcut bone naming farklı, manuel mapping iste" sinyali.

### F2: Loop start ≠ end (seamless değil)
**Recovery:** Otomatik fix — son keyframe'in value'sini ilk keyframe'in value'sine eşitle.

### F3: Foot sliding > 0.005 detected
**Recovery:** stride_length parametresini azalt, cycle frame_count'u artır, veya foot trajectory formula düzelt (Y phase yanlış olabilir).

### F4: Tail/jaw bone bulunamadı (yaratık türüne göre)
**Recovery:** Skip ilgili F-Curve generation, log'a yaz. Animation manifest'e "tail_wag: skipped (no tail bones)" yaz.

---

## 9. EXAMPLE I/O

Input: skinned_v1.blend (kurt) + BudgetSpec ile 7 klip.

Expected output:
```
[animator] FPS: 30
[animator] 7 klip generate ediliyor...
  ✓ idle_breathe: 120 frame, 8 F-Curve
  ✓ walk_loop: 30 frame, 38 F-Curve, foot sliding: 0.001
  ✓ run_loop: 18 frame, 38 F-Curve, foot sliding: 0.002
  ✓ attack_bite: 36 frame, 16 F-Curve
  ✓ howl: 75 frame, 12 F-Curve
  ✓ hit_react: 15 frame, 14 F-Curve
  ✓ death: 60 frame, 18 F-Curve
[animator] NLA tracks setup...
  ✓ 7 NLA track, 7 strip
[animator] Validation...
  ✓ All loops seamless
  ✓ No foot intersection (Z >= 0)
  ✓ Max foot sliding: 0.002 (limit 0.005)
[animator] animated_v1.blend kaydedildi
```

---

## 10. IMPLEMENTATION NOTES

Executable: `scripts/production/build_animation.py`.

Orchestrator çağrısı:
```python
subprocess.run([
    "blender", "--background", str(run_dir / "blender_scenes/skinned_v1.blend"),
    "--python", "scripts/production/build_animation.py",
    "--",
    "--blueprint", str(run_dir / "SkeletonBlueprint.json"),
    "--budget", str(run_dir / "BudgetSpec.json"),
    "--anatomy-class", "references/anatomy_classes/mammalia_quadruped.md",
    "--output-blend", str(run_dir / "blender_scenes/animated_v1.blend"),
], timeout=900)
```
