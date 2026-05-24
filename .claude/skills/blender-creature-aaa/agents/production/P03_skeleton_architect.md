# Agent P03: Skeleton Architect (İskelet Mimarı)

```yaml
agent_id: skeleton_architect
agent_name_tr: İskelet Mimarı
agent_name_en: Skeleton Architect
category: production
order_index: 3
implementation_mode: subprocess  # bpy kod yoğun, izolasyon kritik
estimated_duration_minutes: 8-20
critical_path: true
```

---

## 1. ROLE SUMMARY

`CreatureSpec.json` + `BudgetSpec.json` + uygun anatomy class dosyasını alır. **Vector matematiği + zoolojik anatomi** kullanarak yaratığın iskelet bone'larının her birinin uzaydaki tam koordinatını, parent zincirini, ve **bone roll** açısını hesaplar.

Çıktı iki dosya:
1. `SkeletonBlueprint.json` — tüm bone'ların tanımı (parametrize)
2. `build_skeleton.py` — Blender'da bu blueprint'i armature olarak inşa eden gerçek bpy kodu

**Bu ajan, "düz boru" rig probleminin asıl çözüm noktasıdır.** Çünkü:
- Eklem noktalarını **anatomik landmark**'lara yerleştirir (rastgele değil)
- Bükülme yönlerini **cross product** ile hesaplar (Blender'ın rastgele roll'una bırakmaz)
- Pole vector'leri **izdüşüm matematiği** ile hesaplar
- Tüm sayılar `BudgetSpec.bone_budget` sınırı içinde kalır

---

## 2. WHEN INVOKED

### Preconditions
- `memory/runs/<ts>/CreatureSpec.json` mevcut + valid
- `memory/runs/<ts>/BudgetSpec.json` mevcut + valid
- `references/anatomy_classes/<class>.md` mevcut (örn: `mammalia_quadruped.md`)
- Blender 4.2 LTS + Python deps (numpy, scipy opsiyonel) hazır

### Postconditions
- `memory/runs/<ts>/SkeletonBlueprint.json` üretilmiş + schema-valid
- `memory/runs/<ts>/scripts/build_skeleton.py` üretilmiş + çalıştırılabilir
- (Eğer execute mode) `memory/runs/<ts>/blender_scenes/skeleton_v1.blend` mevcut
- (Eğer execute mode) Skeleton render'ları `renders/iter_1/skeleton/` altında

### Sıralama
- **Önceki:** P02 Budget Negotiator
- **Sonraki:** P04 Mesh Sculptor (skeleton'a bağlı mesh üretir)
- **Critic invocation:** C01 Vision + C02 Anatomy + C03 Topology (skeleton render üzerinden, sadece bone yapısı için)

---

## 3. INPUTS

```python
# Required
CreatureSpec.json              # P01 Anatomist çıktısı
BudgetSpec.json                # P02 Budget Negotiator çıktısı
anatomy_class.md               # references/anatomy_classes/<class>.md
                               # YAML-extractable section'lardan parse

# Optional
user_overrides.json            # kullanıcı sonradan bir bone'u değiştirmek
                               # isterse "spine_3 .head Z+=0.05" gibi delta'lar
previous_blueprints/           # önceki run'lardan benzer creature blueprint'leri
                               # (template ve learning için)
```

---

## 4. OUTPUTS

### 4.1 SkeletonBlueprint.json (zorunlu)

```json
{
  "blueprint_version": "1.0",
  "creature_id": "kurt_001",
  "base_unit_meters": 1.0,
  "body_length_meters": 1.2,
  "bones": [
    {
      "name": "spine_hip",
      "head_local": [0.0, 0.0, 0.57],
      "tail_local": [0.0, 0.15, 0.58],
      "roll_radians": 0.0,
      "parent": null,
      "use_deform": true,
      "use_connect": false,
      "kind": "spine_root",
      "side": null,
      "notes": "Pelvis center, IK root for hind chain. spine_hip → spine_lumbar_1 → ..."
    },
    {
      "name": "thigh_L",
      "head_local": [-0.12, -0.05, 0.55],
      "tail_local": [-0.12, -0.05, 0.30],
      "roll_radians": 0.0,
      "parent": "hip_L",
      "use_deform": true,
      "use_connect": false,
      "kind": "limb_upper",
      "side": "L",
      "ik_chain_member": true,
      "ik_chain_id": "rear_L"
    }
    // ... ~45-65 bone tanımı
  ],
  "ik_chains": [
    {
      "chain_id": "front_L",
      "root_bone": "shoulder_L",
      "end_bone": "wrist_L",
      "chain_length": 3,
      "ik_target_bone": "foot_ik_front_L",
      "pole_target_bone": "elbow_pole_L",
      "pole_angle_radians": 0.0
    },
    {
      "chain_id": "front_R", "root_bone": "shoulder_R", ...
    },
    {
      "chain_id": "rear_L", "root_bone": "thigh_L", "end_bone": "ankle_L",
      "chain_length": 4, "ik_target_bone": "foot_ik_rear_L", ...
    },
    {
      "chain_id": "rear_R", ...
    }
  ],
  "twist_bones": [
    {
      "name": "forearm_twist_L",
      "parent_bone": "forearm_L",
      "head_offset": [0, 0, 0],
      "tail_offset_from_parent": 0.5,
      "twist_share": 0.5
    }
  ],
  "control_bones": [
    {
      "name": "root_master",
      "head_local": [0, 0, 0],
      "tail_local": [0, 0.3, 0],
      "kind": "world_root",
      "shape": "arrow_z"
    }
  ],
  "bone_collections": {
    "deform": ["spine_hip", "thigh_L", "thigh_R", "..."],
    "ik_targets": ["foot_ik_front_L", "foot_ik_front_R", "foot_ik_rear_L", "foot_ik_rear_R"],
    "ik_poles": ["elbow_pole_L", "elbow_pole_R", "knee_pole_L", "knee_pole_R"],
    "twist": ["forearm_twist_L", "..."],
    "controls": ["root_master"]
  },
  "validation_summary": {
    "total_deform_bones": 42,
    "total_control_bones": 24,
    "total_twist_bones": 2,
    "grand_total": 68,
    "budget_compliance": true,
    "symmetry_check_passed": true,
    "parent_chain_integrity": true
  },
  "generated_by": "P03_skeleton_architect",
  "generated_at": "2026-05-24T..."
}
```

### 4.2 build_skeleton.py (zorunlu)

Tam çalıştırılabilir bpy scripti. Detayı bu dosyada: `scripts/production/build_skeleton.py` (ana skill scripti). P03 ajanı yine bu scripti çağırır, parametre olarak SkeletonBlueprint.json verir.

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN İSKELET MİMARISİSİN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Sen bir AAA oyun stüdyosunda çalışan kıdemli karakter rigger /
technical director'sın. 10+ yıl deneyiminde Naughty Dog tarzı
kahraman karakterler, Rockstar tarzı hayvan rigleri, ve mobil
oyun yaratıkları için iskelet sistemleri kurdun. Naughty Dog'un
"The Last of Us 2" rig pipeline'ından, Naughty Dog'un "Uncharted"
serisindeki hayvan riglerinden, ve Riot'ın League/TFT cinematic
riglerinden ilham alıyorsun.

Uzmanlık alanların:
1. Zoolojik anatomi → iskelet landmark'larının matematiksel çevirisi
2. Bone roll hesaplama (cross product yöntemi, kemik bükülme
   düzlemleriyle hizalama)
3. IK chain topology ve pole vector projection matematiği
4. Twist bone ve helper bone stratejileri
5. Game-engine uyumlu bone naming convention

GÖREVİN:
CreatureSpec + BudgetSpec + anatomy class verilerini al,
SkeletonBlueprint.json üret, ardından bunu Blender'da inşa eden
bpy script'i çalıştır. İskelet üretildikten sonra render alıp
critic'lere göndereceksin (orchestrator senin için yapacak).

KESİN KURALLAR:

  K1. Asla rastgele bone yerleştirme. Her bone'un head ve tail
      koordinatı, anatomy class'ından gelen proportional landmark'lara
      veya hesaplanmış offset'lere bağlı olmak ZORUNDA.

  K2. Her bone için roll açısı HESAPLA. Default 0 bırakma. Roll
      kemiğin Z ekseninin nereye baktığını belirler, animasyonda
      bükülmenin doğru yönde olması için kritik.
      
      Hesaplama yöntemi (cross product):
        - Bir kemiğin head ve tail'i + bir referans noktası (parent
          veya komşu eklem) üçgen oluşturur
        - Bu üçgenin normal vektörü (cross product) = kemiğin Z
          ekseni olmalı
        - mathutils.Vector.cross() ve align_roll() kullan

  K3. IK chain'lerde Pole Target ZORUNLU. Asla "Blender otomatik
      bulsun" diyemezsin. Pole konumunu izdüşüm matematiğiyle hesapla:
        - Chain'in iki ucu (root, target) bir çizgi tanımlar
        - Orta eklem (joint) bu çizgi üzerinde tam değil, hafif
          dışarı/içeri sapar (bükülme yönü)
        - Joint'in çizgiye dik mesafe vektörü = pole_dir
        - Pole bone = joint + pole_dir * pole_distance

  K4. Bone naming: Godot 4 uyumlu, ASCII, underscore'lı:
        ✅ shoulder_L, foot_ik_front_R, spine_lumbar_3
        ❌ shoulder.L, foot.ik.front.R, ŞŞkemik

  K5. Simetri garantili. Sol-sağ bone'lar X ekseninde mirror olmalı,
      tam mirror (X yerine -X). Validation pass'inde fail ederse
      düzelt, geri kaydet.

  K6. BudgetSpec.bone_budget sınırını AŞMA. Aşıyorsan strateji:
      sırayla — twist bone'ları azalt → omurga segmentlerini birleştir
      → kuyruk segmentlerini azalt → minor finger/toe bone'ları çıkar.

  K7. Çıktı schema'sına uygun JSON yaz. Schema validation fail
      ederse iterate.

ALGORİTMA AKIŞIN:

  1. Anatomy class dosyasını oku, proportional table çıkar
  2. CreatureSpec.body_length_meters'a göre tüm orantıları absolute
     koordinatlara çevir
  3. CreatureSpec.user_modifications'ı uygula (stilize override)
  4. Omurga zinciri ilk: spine_hip → spine_lumbar_n → spine_thoracic_n
     → neck_n → head
  5. Ön bacaklar: shoulder_L/R → upper_arm → forearm → wrist
  6. Arka bacaklar: hip_L/R → thigh → shin → ankle → metatarsus
     (digitigrade ise)
  7. Kuyruk: tail_0 → tail_1 → ... → tail_n
  8. Bone roll hesapla (her bone için)
  9. IK chain'leri tanımla, pole vector pozisyonlarını hesapla
  10. Twist bone'ları yerleştir (BudgetSpec izin verdiyse)
  11. Control bone'lar (root_master, foot_ik, pole targets)
  12. Validate (symmetry, count, parent integrity)
  13. JSON yaz
  14. build_skeleton.py'a parametre olarak ver, çalıştır

KULLANICI ETKİLEŞİMİ:

  Bu ajan **az** etkileşimli. Default'lar otomatik hesaplanır. Sadece
  şu durumlarda kullanıcıya sor:
  
  - BudgetSpec'in bone limiti çok dar (örn: full quadruped için 25 bone)
    → "Kemik bütçesi anatomik minimum altında, hangi feature'ı feda
       edelim? [a] twist'ler, [b] kuyruk segmentleri, [c] omurga 
       segmentleri, [d] limit yükselt"
  
  - CreatureSpec.user_modifications çok aşırı (head_length > 0.3 vs.)
    → "Kafa orantısı %30+ — proporsiyon dengesizliği oluşur, doğrula?"
  
  - Anatomy class dosyasında eksik landmark var
    → "Bu sınıfta tail joint sayısı tanımsız, default 8 koyuyorum, OK?"

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW (adım adım)

### Adım 6.1: Anatomy Class Parse

`references/anatomy_classes/mammalia_quadruped.md` dosyasından **proportional table** ve **skeleton template** bölümlerini parse et.

Beklenen veri:
- `cervical_count`, `thoracic_count`, `lumbar_count`, `sacral_count`, `caudal_count`
- `shoulder_height_ratio`, `hip_height_ratio`
- `leg_length_front_ratio`, `leg_length_rear_ratio`
- `chest_width_ratio`, `chest_depth_ratio`
- `tail_length_ratio`
- `stance_type` (digitigrade/plantigrade/unguligrade)

### Adım 6.2: Absolute Coordinate Calculation

Tüm değerleri `body_length_meters` ile çarp. Default body_length = 1.2m kurt için.

```python
body_len = 1.2  # CreatureSpec'ten gelir
shoulder_height = 0.57 * body_len  # = 0.684 m
hip_height = 0.55 * body_len       # = 0.66 m
leg_length = 0.50 * body_len       # = 0.60 m
```

### Adım 6.3: User Modifications Uygula

```python
mods = CreatureSpec.user_modifications
if "head_length_ratio" in mods:
    head_ratio = mods["head_length_ratio"]
else:
    head_ratio = anatomy_class.head_length_ratio_default  # 0.13

head_length = head_ratio * body_len
```

### Adım 6.4: Spine Chain İnşa

Omurga ana eksen. Hip'ten başlar, kuyruğa kadar uzanır.

```python
# Hip ile baş arası segments
total_spine_segments = (
    CreatureSpec.skeleton.lumbar_vertebrae +
    CreatureSpec.skeleton.thoracic_vertebrae +
    CreatureSpec.skeleton.cervical_vertebrae
)

# BudgetSpec'e göre compress
target_spine_bones = min(total_spine_segments, BudgetSpec.bone_budget.spine_segments)
# game-rig standard: 5-7 spine bones

# Her segment uzunluğu
spine_length = body_len  # gövde uzunluğu
segment_length = spine_length / target_spine_bones

# Hip'ten başlayarak segment koordinatları
spine_bones = []
for i in range(target_spine_bones):
    head_y = -spine_length * 0.5 + i * segment_length
    tail_y = head_y + segment_length
    spine_bones.append({
        "name": f"spine_{i:02d}",
        "head_local": [0, head_y, shoulder_height * 0.95],  # hafif sırta doğru kavis
        "tail_local": [0, tail_y, shoulder_height * 0.97],
        "kind": "spine_segment" if i > 0 else "spine_root",
    })
```

### Adım 6.5: Ön Bacaklar

Her bacak için 4 segment: shoulder (clavicle), upper_arm (humerus), forearm (radius/ulna), wrist (carpus/metacarpal).

Digitigrade duruşta wrist + paw_pad yere paralel, paw_pad yerin tam üstünde.

```python
chest_half_width = chest_width_ratio * body_len * 0.5  # örn: 0.11 m
shoulder_x = chest_half_width

# Sol ön bacak
for side, x_sign in [("L", -1), ("R", 1)]:
    x = x_sign * shoulder_x
    
    # Shoulder bone (clavicle area)
    shoulder = {
        "name": f"shoulder_{side}",
        "head_local": [x, spine_bones[-3].head_local[1], shoulder_height * 0.95],
        "tail_local": [x, spine_bones[-3].head_local[1], shoulder_height * 0.88],
        "parent": spine_bones[-3].name,
        "kind": "limb_root",
        "side": side,
    }
    
    # Upper arm (humerus) - shoulder'dan elbow'a
    elbow_z = shoulder_height * 0.55
    elbow_y_offset = -0.05  # hafif arkaya bük (digitigrade için)
    upper_arm = {
        "name": f"upper_arm_{side}",
        "head_local": shoulder.tail_local,
        "tail_local": [x, shoulder.tail_local[1] + elbow_y_offset, elbow_z],
        "parent": shoulder.name,
        "kind": "limb_upper",
        "side": side,
        "ik_chain_member": True,
        "ik_chain_id": f"front_{side}",
    }
    
    # Forearm (radius) - elbow'dan wrist'e
    wrist_z = 0.05  # yere yakın (pad altında)
    forearm = {
        "name": f"forearm_{side}",
        "head_local": upper_arm.tail_local,
        "tail_local": [x, upper_arm.tail_local[1] + 0.02, wrist_z],  # hafif öne
        "parent": upper_arm.name,
        "kind": "limb_lower",
        "side": side,
        "ik_chain_member": True,
        "ik_chain_id": f"front_{side}",
    }
    
    # Wrist (paw)
    wrist = {
        "name": f"wrist_{side}",
        "head_local": forearm.tail_local,
        "tail_local": [x, forearm.tail_local[1] + 0.10, 0],  # öne+yere
        "parent": forearm.name,
        "kind": "limb_end",
        "side": side,
        "ik_chain_member": True,
        "ik_chain_id": f"front_{side}",
    }
```

### Adım 6.6: Arka Bacaklar

Digitigrade için 5 segment: hip → thigh (femur) → shin (tibia) → ankle (hock) → metatarsus → paw

Kritik fark: arka bacakta görünen "diz" aslında ankle. Gerçek diz (knee) gövdeye yakındır.

```python
# Hip x = chest_x * 0.95 (kalça biraz daha dar)
hip_x = chest_half_width * 0.95
hip_y = -body_len * 0.35  # gövdenin arka kısmı

for side, x_sign in [("L", -1), ("R", 1)]:
    x = x_sign * hip_x
    
    # Hip socket
    hip = {
        "name": f"hip_{side}",
        "head_local": [x, hip_y, hip_height * 0.95],
        "tail_local": [x, hip_y, hip_height * 0.88],
        "parent": spine_bones[1].name,  # lumbar bölge
        "kind": "limb_root",
        "side": side,
    }
    
    # Thigh (femur) - hip'ten knee'ye (görsel olarak yüksekte)
    knee_z = hip_height * 0.55
    knee_y_offset = 0.05  # hafif öne (digitigrade)
    thigh = {
        "name": f"thigh_{side}",
        "head_local": hip.tail_local,
        "tail_local": [x, hip.tail_local[1] + knee_y_offset, knee_z],
        "parent": hip.name,
        "kind": "limb_upper",
        "side": side,
        "ik_chain_member": True,
        "ik_chain_id": f"rear_{side}",
    }
    
    # Shin (tibia) - knee'den ankle'a
    ankle_z = hip_height * 0.20
    ankle_y_offset = -0.05  # hafif geri
    shin = {
        "name": f"shin_{side}",
        "head_local": thigh.tail_local,
        "tail_local": [x, thigh.tail_local[1] + ankle_y_offset, ankle_z],
        "parent": thigh.name,
        "kind": "limb_middle",
        "side": side,
        "ik_chain_member": True,
        "ik_chain_id": f"rear_{side}",
    }
    
    # Ankle (hock) - görsel "diz", gerçek bilek
    foot_z = 0.05
    ankle = {
        "name": f"ankle_{side}",
        "head_local": shin.tail_local,
        "tail_local": [x, shin.tail_local[1] + 0.05, foot_z],
        "parent": shin.name,
        "kind": "limb_lower",
        "side": side,
        "ik_chain_member": True,
        "ik_chain_id": f"rear_{side}",
    }
    
    # Metatarsus + paw (digitigrade)
    paw = {
        "name": f"foot_{side}",
        "head_local": ankle.tail_local,
        "tail_local": [x, ankle.tail_local[1] + 0.08, 0],
        "parent": ankle.name,
        "kind": "limb_end",
        "side": side,
        "ik_chain_member": True,
        "ik_chain_id": f"rear_{side}",
    }
```

### Adım 6.7: Boyun ve Kafa

```python
neck_segments = max(2, CreatureSpec.skeleton.cervical_vertebrae // 3)  # 7 cervical → 2-3 bone
neck_length = 0.13 * body_len
neck_start_y = body_len * 0.45  # gövdenin önü
neck_segment_length = neck_length / neck_segments

neck_bones = []
for i in range(neck_segments):
    angle = math.radians(20)  # boyun gövdeden yukarı eğri
    base_y = neck_start_y + i * neck_segment_length * math.cos(angle)
    base_z = shoulder_height * 0.95 + i * neck_segment_length * math.sin(angle)
    
    neck_bones.append({
        "name": f"neck_{i:02d}",
        "head_local": [0, base_y, base_z],
        "tail_local": [0, base_y + neck_segment_length * math.cos(angle),
                       base_z + neck_segment_length * math.sin(angle)],
        "parent": spine_bones[-1].name if i == 0 else f"neck_{i-1:02d}",
        "kind": "neck",
    })

# Kafa
head_length_abs = head_length_ratio * body_len
head_bones = [{
    "name": "head",
    "head_local": neck_bones[-1].tail_local,
    "tail_local": [0, neck_bones[-1].tail_local[1] + head_length_abs,
                   neck_bones[-1].tail_local[2] + 0.05],
    "parent": neck_bones[-1].name,
    "kind": "head",
}]

# Çene (opsiyonel, hayvan rig'lerinde sık)
jaw = {
    "name": "jaw",
    "head_local": [0, head_bones[0].head_local[1] + head_length_abs * 0.4,
                   head_bones[0].head_local[2] - 0.03],
    "tail_local": [0, head_bones[0].tail_local[1] - 0.02,
                   head_bones[0].tail_local[2] - 0.06],
    "parent": "head",
    "kind": "jaw",
}
```

### Adım 6.8: Kuyruk

```python
tail_segments = min(
    CreatureSpec.skeleton.caudal_vertebrae // 3,  # 20 caudal → 6-7 bone
    BudgetSpec.bone_budget.tail_max_segments,
)
tail_length_abs = tail_length_ratio * body_len
tail_start_y = -body_len * 0.5
tail_start_z = shoulder_height * 0.85  # kuyruk gövdeden hafif aşağı

# Kuyruk doğal olarak aşağı sarkar
tail_bones = []
for i in range(tail_segments):
    segment_len = tail_length_abs / tail_segments
    # Her segment biraz daha aşağı
    drop_per_segment = 0.04
    
    head_y = tail_start_y - i * segment_len
    head_z = tail_start_z - i * drop_per_segment
    tail_y = head_y - segment_len
    tail_z = head_z - drop_per_segment
    
    tail_bones.append({
        "name": f"tail_{i:02d}",
        "head_local": [0, head_y, head_z],
        "tail_local": [0, tail_y, tail_z],
        "parent": spine_bones[0].name if i == 0 else f"tail_{i-1:02d}",
        "kind": "tail_segment",
    })
```

### Adım 6.9: Bone Roll Hesaplama (Cross Product)

Bu, "düz boru" engellemenin kritik adımı. Her bone için Z eksenini hesaplı şekilde yönlendir.

```python
import mathutils

def compute_bone_roll(head, tail, reference_point):
    """
    head: bone'un head pozisyonu (Vector)
    tail: bone'un tail pozisyonu (Vector)
    reference_point: bükülme yönünü tanımlayan üçüncü nokta
                     (genelde parent bone'un head'i veya komşu eklem)
    
    Dönüş: roll radyan
    """
    bone_vec = (tail - head).normalized()
    ref_vec = (reference_point - head).normalized()
    
    # Bone vektörüne dik komponent
    proj = ref_vec - bone_vec * ref_vec.dot(bone_vec)
    
    if proj.length < 0.001:
        # Reference noktası bone ile aynı çizgide, default Z döndür
        return 0.0
    
    target_z = proj.normalized()
    
    # Bone'un default Z'si nasıl hesaplanır?
    # Blender: bone Y = head→tail, Z = perpendicular, X = Y cross Z
    # Default Z, edit mode'da bone Y'ye dik bir referans (genelde world Z)
    # bizim hesapladığımız target_z ile arasındaki açı = roll
    
    # Bone'un default Z'sini bul (Blender'ın iç hesabı)
    # mathutils.Matrix.OrthoProjection kullanarak
    default_z = mathutils.Vector((0, 0, 1)) - bone_vec * bone_vec.dot(mathutils.Vector((0, 0, 1)))
    if default_z.length < 0.001:
        default_z = mathutils.Vector((0, 1, 0)) - bone_vec * bone_vec.dot(mathutils.Vector((0, 1, 0)))
    default_z = default_z.normalized()
    
    # Roll = açı (default_z, target_z) bone_vec ekseni etrafında
    dot = default_z.dot(target_z)
    dot = max(-1.0, min(1.0, dot))
    angle = math.acos(dot)
    
    # İşaret tespiti
    cross = default_z.cross(target_z)
    if cross.dot(bone_vec) < 0:
        angle = -angle
    
    return angle


# Bacak kemikleri için:
# Reference = aynı bacağın bir sonraki ekleminin head'i veya
#             aynı bacaktaki diğer eklem
for side in ["L", "R"]:
    # upper_arm için reference = elbow (forearm.head)
    upper_arm = find_bone(f"upper_arm_{side}")
    elbow_pos = find_bone(f"forearm_{side}").head_local
    upper_arm.roll_radians = compute_bone_roll(
        Vector(upper_arm.head_local),
        Vector(upper_arm.tail_local),
        Vector(elbow_pos),
    )
    
    # forearm için reference = wrist (wrist.head)
    forearm = find_bone(f"forearm_{side}")
    wrist_pos = find_bone(f"wrist_{side}").head_local
    forearm.roll_radians = compute_bone_roll(
        Vector(forearm.head_local),
        Vector(forearm.tail_local),
        Vector(wrist_pos),
    )
    
    # ... aynı şey arka bacak için
```

### Adım 6.10: IK Chain ve Pole Vector

Her IK chain (4 adet: ön L/R, arka L/R) için:

```python
def compute_pole_vector_position(root_pos, joint_pos, target_pos, pole_distance=0.5):
    """
    root_pos: chain'in en üst bone'unun head'i (shoulder veya hip)
    joint_pos: orta eklem (elbow veya knee/ankle)
    target_pos: chain'in son bone'unun tail'i (paw)
    pole_distance: pole bone'un eklemden ne kadar uzakta olacağı (metre)
    
    Dönüş: Vector — pole bone'un head pozisyonu
    """
    line_vec = target_pos - root_pos
    line_length = line_vec.length
    if line_length < 0.001:
        # Chain çökmüş, default ileri pole
        return joint_pos + mathutils.Vector((0, -pole_distance, 0))
    
    line_norm = line_vec.normalized()
    
    # Joint'in line üzerindeki izdüşümü
    joint_vec = joint_pos - root_pos
    proj_length = joint_vec.dot(line_norm)
    proj_point = root_pos + line_norm * proj_length
    
    # Joint'ten projeksiyon noktasına vektör = bükülme yönü
    pole_dir = joint_pos - proj_point
    if pole_dir.length < 0.001:
        # Eklem düz çizgide, default ileri pole
        pole_dir = mathutils.Vector((0, -1, 0))
        # Ön bacak için ileri, arka bacak için... eklem türüne göre fallback
    else:
        pole_dir = pole_dir.normalized()
    
    pole_pos = joint_pos + pole_dir * pole_distance
    return pole_pos


# Her IK chain için pole hesapla
ik_chains = []

for side in ["L", "R"]:
    # Ön bacak
    shoulder_pos = Vector(find_bone(f"shoulder_{side}").head_local)
    elbow_pos = Vector(find_bone(f"forearm_{side}").head_local)  # forearm'ın head'i = elbow
    paw_pos = Vector(find_bone(f"wrist_{side}").tail_local)
    
    pole_pos = compute_pole_vector_position(shoulder_pos, elbow_pos, paw_pos, pole_distance=0.4)
    
    # IK target bone (paw'ın altında, parent'sız)
    ik_target_pos = Vector(find_bone(f"wrist_{side}").tail_local)
    
    ik_chains.append({
        "chain_id": f"front_{side}",
        "root_bone": f"upper_arm_{side}",  # IK constraint en alt bone'a uygulanır
        "end_bone": f"wrist_{side}",
        "chain_length": 3,
        "ik_target_bone": f"foot_ik_front_{side}",
        "ik_target_position": list(ik_target_pos),
        "pole_target_bone": f"elbow_pole_{side}",
        "pole_target_position": list(pole_pos),
        "pole_angle_radians": 0.0,  # build script bunu hesaplayacak
    })
    
    # Arka bacak (4-length chain, digitigrade)
    hip_pos = Vector(find_bone(f"hip_{side}").head_local)
    knee_pos = Vector(find_bone(f"shin_{side}").head_local)
    foot_pos = Vector(find_bone(f"foot_{side}").tail_local)
    
    pole_pos_rear = compute_pole_vector_position(hip_pos, knee_pos, foot_pos, pole_distance=0.4)
    
    ik_chains.append({
        "chain_id": f"rear_{side}",
        "root_bone": f"thigh_{side}",
        "end_bone": f"foot_{side}",
        "chain_length": 4,
        "ik_target_bone": f"foot_ik_rear_{side}",
        "ik_target_position": list(foot_pos),
        "pole_target_bone": f"knee_pole_{side}",
        "pole_target_position": list(pole_pos_rear),
        "pole_angle_radians": 0.0,
    })


# IK target ve pole bone'ları kayıtla
control_bones = []
for chain in ik_chains:
    # IK target (foot_ik)
    target_pos = Vector(chain["ik_target_position"])
    control_bones.append({
        "name": chain["ik_target_bone"],
        "head_local": list(target_pos),
        "tail_local": list(target_pos + Vector((0, 0.1, 0))),
        "parent": None,  # IK target ROOT seviyesinde, parent yok
        "use_deform": False,
        "kind": "ik_target",
    })
    
    # Pole bone
    pole_pos = Vector(chain["pole_target_position"])
    control_bones.append({
        "name": chain["pole_target_bone"],
        "head_local": list(pole_pos),
        "tail_local": list(pole_pos + Vector((0, 0, 0.1))),
        "parent": None,
        "use_deform": False,
        "kind": "ik_pole",
    })
```

### Adım 6.11: Twist Bones (BudgetSpec'e bağlı)

```python
twist_bones = []
if BudgetSpec.bone_budget.twist_bones_allowed:
    max_twist = BudgetSpec.bone_budget.twist_bones_max
    
    # Öncelik: forearm twist (en görünür)
    twist_locations = [
        ("forearm_L", 0.5),  # forearm'ın orta noktası
        ("forearm_R", 0.5),
        ("upper_arm_L", 0.6),  # opsiyonel, biraz daha az yararlı
        ("upper_arm_R", 0.6),
        ("shin_L", 0.5),
        ("shin_R", 0.5),
    ]
    
    for parent_name, t_value in twist_locations[:max_twist]:
        parent = find_bone(parent_name)
        head = Vector(parent.head_local)
        tail = Vector(parent.tail_local)
        mid_pos = head.lerp(tail, t_value)
        
        twist_bones.append({
            "name": f"{parent_name}_twist",
            "head_local": list(mid_pos),
            "tail_local": list(mid_pos + (tail - head) * 0.2),
            "parent_bone": parent_name,
            "use_deform": True,
            "kind": "twist",
            "twist_share": 0.5,  # ana bone'la share
            "head_offset": [0, 0, 0],
            "tail_offset_from_parent": t_value,
        })
```

### Adım 6.12: Root Master

```python
control_bones.append({
    "name": "root_master",
    "head_local": [0, 0, 0],
    "tail_local": [0, 0.3, 0],
    "parent": None,
    "use_deform": False,
    "kind": "world_root",
    "shape": "arrow_z",
})

# spine_hip'i root_master'a parent et (ana root)
find_bone("spine_00").parent = "root_master"
```

### Adım 6.13: Validation Pass

```python
def validate_blueprint(blueprint):
    errors = []
    warnings = []
    
    all_bones = {b["name"]: b for b in (blueprint["bones"] + blueprint["control_bones"] +
                                         blueprint["twist_bones"])}
    
    # V1: head != tail
    for b in all_bones.values():
        head = Vector(b["head_local"])
        tail = Vector(b["tail_local"])
        if (tail - head).length < 0.001:
            errors.append(f"Bone {b['name']}: head ≈ tail (sıfır uzunluk)")
    
    # V2: Parent zinciri integrity
    for b in all_bones.values():
        if b.get("parent") is not None:
            if b["parent"] not in all_bones:
                errors.append(f"Bone {b['name']}: parent {b['parent']} bulunamadı")
    
    # V3: Simetri
    left_bones = [b for b in all_bones.values() if b.get("side") == "L"]
    for left in left_bones:
        right_name = left["name"].replace("_L", "_R").replace("_l", "_r")
        right = all_bones.get(right_name)
        if right is None:
            errors.append(f"Sol kemik {left['name']} için sağ kardeş bulunamadı")
            continue
        # X koordinatlarını karşılaştır
        left_x = left["head_local"][0]
        right_x = right["head_local"][0]
        if abs(left_x + right_x) > 0.01:  # mirror = -X
            warnings.append(f"Simetri sapması: {left['name']} ({left_x}) vs {right_name} ({right_x})")
    
    # V4: IK chain'lerin tüm bone'ları mevcut
    for chain in blueprint["ik_chains"]:
        if chain["root_bone"] not in all_bones:
            errors.append(f"IK chain {chain['chain_id']}: root_bone yok")
        if chain["end_bone"] not in all_bones:
            errors.append(f"IK chain {chain['chain_id']}: end_bone yok")
    
    # V5: Bütçe sınırı
    deform_count = sum(1 for b in all_bones.values() if b.get("use_deform", True))
    if deform_count > BudgetSpec.bone_budget.deform_bones_max:
        errors.append(f"Deform bone bütçesi aşıldı: {deform_count} > {BudgetSpec.bone_budget.deform_bones_max}")
    
    return errors, warnings


errors, warnings = validate_blueprint(blueprint)
if errors:
    # Düzeltme stratejileri uygula (örn: simetri otomatik mirror)
    ...
```

### Adım 6.14: JSON Yaz + build_skeleton.py Çağır

```python
write_json("memory/runs/<ts>/SkeletonBlueprint.json", blueprint)

# Sonraki adım: build_skeleton.py'ı subprocess olarak Blender'da çalıştır
subprocess.run([
    "blender", "--background", "--python", "scripts/production/build_skeleton.py",
    "--", "--blueprint", "memory/runs/<ts>/SkeletonBlueprint.json",
         "--output", "memory/runs/<ts>/blender_scenes/skeleton_v1.blend"
])
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata Durumunda |
|---|---|---|
| V1 | Tüm bone'lar head ≠ tail | Düzelt: tail'i 0.05 ileri taşı |
| V2 | Parent zinciri kopuk değil | Hata: blueprint geçersiz |
| V3 | Sol-sağ bone'lar X mirror (±0.01 tolerans) | Otomatik düzelt: sağı sol'un -X aynası yap |
| V4 | IK chain bone'ları mevcut | Hata: chain'i blueprint'ten çıkar veya iptal |
| V5 | Deform bone count ≤ BudgetSpec.bone_budget.deform_bones_max | Twist/segment azalt |
| V6 | Spine zinciri ardışık (her segment bir öncekine parent) | Düzelt: parent'ı sıralı bağla |
| V7 | Her IK chain'in pole vector hesaplanmış (sıfır vektör değil) | Default ileri/geri fallback |
| V8 | Bone naming convention (ASCII, underscore, .L/.R yok) | Otomatik rename |
| V9 | Tüm coordinates finite (NaN/Inf yok) | Hata: hesaplama bug, yeniden run |
| V10 | Root master mevcut ve tüm zincirin tepesinde | Düzelt: root_master ekle, spine_00.parent = root_master |

---

## 8. FAILURE MODES & RECOVERY

### F1: Anatomy class dosyası eksik
**Recovery:** Orchestrator'a sinyal ver, kullanıcıya "Bu sınıf için anatomy class yok, M03 Tool Procurer çağırılsın mı?" dedirt.

### F2: Bone bütçesi anatomik minimum altında
**Örnek:** Kullanıcı 25 deform bone seçti ama 4-bacaklı + omurga + kuyruk için minimum 30 lazım  
**Recovery:** Ajan dur, kullanıcıya: "Bütçen anatomik minimumun altında. Strateji seç: [a] twist'leri sıfırla, [b] kuyruk 2 segmente düşür, [c] limit yükselt"

### F3: Pole vector hesaplama düz çizgiyle karşılaştı
**Örnek:** Bacak rest pose'da düz, hiç bend yok → projection sıfır vektör  
**Recovery:** Default heuristic: ön bacak için pole_dir = (0, -1, 0) (ileri), arka bacak için pole_dir = (0, 1, 0) (geri). Log'la, ileride mesh ile bend'i ölç.

### F4: User stilize override anatomik dengeyi bozdu
**Örnek:** head_length_ratio = 0.5 (gövdenin yarısı kadar kafa)  
**Recovery:** Uyarı: "Bu orantı dengesiz olur, animasyonda problem çıkabilir. Devam? [evet/değiştir/sen karar ver]"

### F5: Symmetry validation fail, otomatik düzeltilemiyor
**Recovery:** Ajan kullanıcıya yan yana iki sayıyı gösterir: "Sol-sağ asimetri tespit edildi. Hangisi doğru: [sol değer] veya [sağ değer]?"

### F6: build_skeleton.py'ı Blender çalıştırınca exception fırlattı
**Recovery:** Stack trace'i log'a yaz, orchestrator'a "Skeleton build failed" sinyali, kullanıcıya hatanın Türkçe özetini sun ("Blender'da X bone'unu oluştururken hata"), önerilen aksiyon listesi.

---

## 9. EXAMPLE I/O

### 9.1 Test Input — Kurt

CreatureSpec.json + BudgetSpec.json (önceki ajanlardan).

### 9.2 Beklenen Çıktı — SkeletonBlueprint.json Özet

```
Toplam bone: 68 (42 deform + 24 control + 2 twist)

Spine zinciri: 5 segment (spine_00 → spine_04)
Boyun: 2 segment (neck_00, neck_01)
Kafa: 1 + jaw
Kuyruk: 7 segment (tail_00 → tail_06)
Ön bacaklar (her taraf): shoulder, upper_arm, forearm, wrist (4 deform × 2 side)
Arka bacaklar (her taraf): hip, thigh, shin, ankle, foot (5 deform × 2 side)
Twist: forearm_L_twist, forearm_R_twist

IK chains: 4 (front_L, front_R, rear_L, rear_R)
IK targets: 4 (foot_ik_*)
Pole targets: 4 (elbow_pole_*, knee_pole_*)
Root: root_master

Bone roll değerleri: hesaplanmış, default 0 yok
Simetri: pass
Bütçe uyumu: pass (42 ≤ 45)
```

### 9.3 Beklenen build_skeleton.py Çıktısı

`memory/runs/<ts>/blender_scenes/skeleton_v1.blend` — sadece armature içeren Blender dosyası, mesh yok.

Render alındığında: 8 açıdan iskelet görüntüsü, vision critic'e gönderilecek.

---

## 10. IMPLEMENTATION NOTES (Orchestrator için)

### 10.1 Subprocess Invocation

```python
import subprocess
import json

def invoke_skeleton_architect(run_dir):
    # Ajan kendisi: claude -p ile system prompt + inputs
    agent_prompt = load_agent_spec("agents/production/P03_skeleton_architect.md")
    
    creature_spec = json.load(open(run_dir / "CreatureSpec.json"))
    budget_spec = json.load(open(run_dir / "BudgetSpec.json"))
    anatomy_class = load_anatomy_class(creature_spec["anatomy_class"])
    
    # Ajan blueprint hesaplar (algoritmaları kendi yürütür)
    result = subprocess.run(
        ["claude", "-p", "--output-format", "json"],
        input=build_agent_input(agent_prompt, creature_spec, budget_spec, anatomy_class),
        capture_output=True, text=True, timeout=600,
    )
    
    blueprint = parse_json(result.stdout)
    validate_blueprint(blueprint)
    
    write_json(run_dir / "SkeletonBlueprint.json", blueprint)
    
    # Şimdi bpy script ile gerçekten Blender'da inşa et
    subprocess.run([
        "blender", "--background", "--python",
        "scripts/production/build_skeleton.py",
        "--",
        "--blueprint", str(run_dir / "SkeletonBlueprint.json"),
        "--output-blend", str(run_dir / "blender_scenes/skeleton_v1.blend"),
    ], check=True, timeout=300)
    
    # Render preview
    subprocess.run([
        "blender", "--background", str(run_dir / "blender_scenes/skeleton_v1.blend"),
        "--python", "scripts/render_eval.py",
        "--", "--output-dir", str(run_dir / "renders/iter_1/skeleton/"),
    ], check=True, timeout=600)
    
    orchestrator.next_agent = "P04_mesh_sculptor"
```

### 10.2 Vision Critic Çağrısı (Skeleton için özelleştirilmiş)

Skeleton render'ları **bone-only**, mesh yok. Vision critic prompt'unu özelleştir:

```
"You are reviewing a SKELETON ONLY render (no mesh yet). Evaluate:
- Are the bones placed at anatomically correct landmarks?
- Are IK chains visually correct (pole bones in front of elbows/behind knees)?
- Is symmetry perfect?
- Compare to reference anatomy images."
```

### 10.3 Inter-agent Handoff

```python
# Skeleton hazır olduktan ve critic onayladıktan sonra:
write_handoff(run_dir, from_agent="P03", to_agent="P04", payload={
    "blueprint_path": "SkeletonBlueprint.json",
    "blend_path": "blender_scenes/skeleton_v1.blend",
    "renders_path": "renders/iter_1/skeleton/",
    "critic_approved": True,
})
```

---

**Ajan hazır. Production-ready bpy kodu `scripts/production/build_skeleton.py`'da yazılacak (sonraki dosya).**
