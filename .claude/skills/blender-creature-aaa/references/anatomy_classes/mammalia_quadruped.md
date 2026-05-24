# Anatomy Class: Mammalia Quadruped

**Kapsam:** 4-bacaklı memeli hayvanlar — kurt, köpek, kedi, aslan, at, geyik, sığır, vb.

**Hangi yaratıklar bu sınıfa eşlenir:**
- Köpekgiller (kurt, köpek, çakal, tilki)
- Kedigiller (aslan, kaplan, leopar, ev kedisi)
- Atgiller (at, eşek, zebra)
- Geviş getirenler (geyik, sığır, koyun, keçi)
- Ayılar
- Domuzgiller

---

## 1. ORTAK İSKELET ŞABLONU

Tüm memeli dört-ayaklılar şu genel iskelet yapısını paylaşır. Spec'in `skeleton` alanı bu şablondan başlar, kullanıcı modify edebilir.

```
Spine: cervical(C) + thoracic(T) + lumbar(L) + sacral(S) + caudal(Ca)
```

| Tür | C | T | L | S | Ca | Toplam |
|---|---|---|---|---|---|---|
| Kurt (Canis lupus) | 7 | 13 | 7 | 3 | 20 | 50 |
| Ev kedisi | 7 | 13 | 7 | 3 | 22-23 | 52-53 |
| Aslan | 7 | 13 | 7 | 3 | 23 | 53 |
| At | 7 | 18 | 6 | 5 | 15-21 | 51-58 |
| Geyik | 7 | 13 | 6 | 5 | 6-14 | 37-45 |

Tüm memelilerde **servikal omur sayısı 7** (zürafa bile dahil). Bu sabittir, kullanıcı değiştirmek isterse uyarı.

### 1.1 Kemik Bütçesi (mobil için)

Tam anatomik iskelet ~50-58 deform bone. Mobil için tipik optimization: omurga ve kuyruğun bazı omurları birleştirilir. Skill bu kararı kullanıcıya bırakır:

```
══════════════════════════════════════════════════
İSKELET DETAY SEVİYESİ — kullanıcı kararı

Mobil oyun için tüm omurları ayrı kemik yapmak gereksiz olabilir.

  [a] Full anatomy (50-55 bone)  — tam memeli iskeleti, mobile zorlanabilir
  [b] Game-rig standard (35-40)  — omurga 5-7 omur, kuyruk 5-8 omur (standart)
  [c] Mobile-lite (25-30)        — omurga 3 omur, kuyruk 4 omur, ayak parmak yok
  [d] Hero-mobile (40-50)        — full detay ama gözle birleştirilmiş omurlar
  [e] Sen karar ver

══════════════════════════════════════════════════
```

Default *öneri* (b) game-rig standard ama sayı sabit değil.

---

## 2. ORANTİSAL ŞABLON (Proportional Atlas)

Tüm değerler **gövde uzunluğu = 1.0** olarak normalize. Gövde uzunluğu = omuz (T1) → kalça (S1) arası mesafe.

### 2.1 Köpekgiller (Canidae)

```yaml
head_length: 0.12-0.14        # gövde×0.12 = kurt
head_width: 0.07-0.09
neck_length: 0.10-0.13
shoulder_height: 0.55-0.60    # zemin → omuz tepe
hip_height: 0.52-0.57         # zemin → kalça tepe
leg_length_front: 0.48-0.55
leg_length_rear: 0.50-0.55
chest_width: 0.20-0.25
chest_depth: 0.25-0.30
tail_length: 0.35-0.45
ear_height: 0.05-0.08  # canidae türlerine göre değişir
paw_size: 0.08-0.10
```

### 2.2 Kedigiller (Felidae)

```yaml
head_length: 0.13-0.16   # kedigillerde kafa daha yuvarlak ve büyük
shoulder_height: 0.50-0.55
hip_height: 0.50-0.55    # köpeklerden farklı: omuz≈kalça
leg_length_front: 0.45-0.50
chest_depth: 0.28-0.33    # daha derin göğüs (sıçrama için)
tail_length: 0.45-0.55    # kedigiller daha uzun kuyruk
```

### 2.3 Atgiller (Equidae)

```yaml
head_length: 0.18-0.22    # uzun kafa
neck_length: 0.25-0.30    # uzun boyun
shoulder_height: 0.62-0.68
hip_height: 0.60-0.66
leg_length_front: 0.55-0.62
chest_width: 0.18-0.22
tail_length: 0.35-0.50    # bazıları kıllı, anatomik kemik kısa
```

### 2.4 Geyik / Ungulate

```yaml
head_length: 0.16-0.20
neck_length: 0.18-0.25
shoulder_height: 0.62-0.70
hip_height: 0.58-0.66
leg_length_front: 0.55-0.65   # uzun ve ince
antler_height: 0.20-0.40       # varsa, çok değişken
```

### 2.5 Ayılar (Ursidae)

```yaml
head_length: 0.14-0.18
shoulder_height: 0.50-0.60
hip_height: 0.45-0.55    # ayılarda omuz > kalça (hörgüç görünüm)
leg_length_front: 0.40-0.50  # kısa
chest_width: 0.30-0.40   # geniş
paw_size: 0.12-0.18      # büyük pati
```

---

## 3. DURUŞ TİPLERİ

### 3.1 Digitigrade (Parmak Ucu)

**Kim:** Köpekgiller, kedigiller, tavşan (kısmen)

**Özellik:** Topuk (kalkaneus) yerden ~30° yukarıda, parmak yastığı (paw pad) yerde. Bilek (carpus) "knee" gibi görünür ama aslında orta-bacak eklemidir.

**Rigging implikasyonu:**
- Foot IK target paw pad'in altında, parmaklarda
- Ankle bone yukarıda kalır (görsel olarak "knee")
- Real knee = patella (görsel olarak gövdenin üst kısmında)
- IK chain length = 3 (hip → knee → ankle → foot_ik_target)

```
gövde
  │
  ├── hip joint
       │
       ├── femur (üst bacak, görünmez kürk altında)
            │
            ├── knee (gerçek diz, kürk içinde)
                 │
                 ├── tibia/fibula (alt bacak, "knee" görünümlü)
                      │
                      ├── ankle (görsel "knee", gerçek bilek/hock)
                           │
                           ├── metatarsus (yere paralel)
                                │
                                ├── digits (parmaklar, yere değen)
                                     │
                                     └── claws
```

### 3.2 Plantigrade (Tüm Taban)

**Kim:** Ayılar, insan, raccoon, primat

**Özellik:** Taban + topuk yerde. Bacak eklemleri daha düşük profilde.

**Rigging implikasyonu:**
- Foot IK target topuk + tabanı kapsayan plane
- Ankle gerçek pozisyonda

### 3.3 Unguligrade (Toynak)

**Kim:** Atgiller, geyik, sığır, geviş getirenler

**Özellik:** Sadece toynak (modified nail) yerde. Tüm parmak kemikleri yerden yüksekte.

**Rigging implikasyonu:**
- Foot IK target = toynak ucu
- Bacak çok ince ve uzun
- Knee + hock (ankle) bükülmeler daha keskin

---

## 4. KAS GRUPLARI ANIMASYON İÇİN

Bu kaslar **kas şişmesi (muscle bulge)** shape key'leri için kritik. Her birinin driver'ı ilgili bone rotation'a bağlanır.

### 4.1 Ön Bacak Kasları

| Kas | Driver Bone | Trigger Rotation | Visual Effect |
|---|---|---|---|
| Biceps brachii | upper_arm.L | elbow flex >40° | iç şişme |
| Triceps | upper_arm.L | elbow extend >0° | dış şişme |
| Deltoid | shoulder.L | shoulder flex >30° | omuz tepe şişer |

### 4.2 Arka Bacak Kasları

| Kas | Driver Bone | Trigger Rotation | Visual Effect |
|---|---|---|---|
| Quadriceps | thigh.L | knee extend | ön üst bacak şişer |
| Hamstring | thigh.L | knee flex | arka üst bacak şişer |
| Gluteus | hip.L | hip extend | kalça şişer |
| Gastrocnemius | shin.L | ankle flex | baldır şişer |

### 4.3 Gövde Kasları

| Kas | Driver Bone | Trigger | Visual |
|---|---|---|---|
| Trapezius | neck.head | head yaw/pitch | boyun-omuz birleşimi |
| Pectoralis | spine.shoulder | front legs forward | göğüs şişer |
| Latissimus dorsi | spine.middle | side bend | yan şişer |
| Rectus abdominis | spine.lumbar | spine flex forward | karın sıkışır |

**NOT:** Bütün bu kaslar **opsiyonel**. Kullanıcı "muscle bulge istemiyorum, mobil için ağır" derse atlanır.

---

## 5. LOKOMOSYON GAITS

Her gait için adım frekansı (frekans = tam döngü süresi) ve foot phase offsetleri.

### 5.1 Walk (4-beat)

Her ayak ayrı zamanda yere basar. Phase offsets:

```
LF (left front):   0.00 × 2π
RR (right rear):   0.25 × 2π
RF (right front):  0.50 × 2π
LR (left rear):    0.75 × 2π
```

Cycle period: 0.9-1.2 saniye (kurt için ~1.0s)

### 5.2 Trot (2-beat diagonal)

Çapraz ayaklar aynı anda. Phase offsets:

```
LF: 0.0
RR: 0.0 (LF ile aynı zamanda, diagonal pair)
RF: π
LR: π (RF ile aynı zamanda)
```

Cycle period: 0.5-0.7 saniye

### 5.3 Gallop (asimetrik 4-beat)

Karmaşık. Sequence: LR → RR → (suspension) → LF → RF → (suspension) ...

```
LR: 0.0
RR: 0.10
LF: 0.45
RF: 0.55
suspension_phase: 0.65-0.75 ve 0.95-1.0
```

Cycle period: 0.35-0.50 saniye

### 5.4 Bound (gallop variant — feliform)

Ön bacaklar birlikte, arka bacaklar birlikte (cheetah, hare):
```
LF, RF: 0.0 (eş)
LR, RR: 0.5 (eş, ön bacaklara ters faz)
```

---

## 6. IK CHAIN TOPOLOJİSİ

Skill rigging modülünde bu chain'leri kurar.

```
Ön Bacak IK Chain (her iki taraf için):
  Root: shoulder.L
  Chain bones: upper_arm.L → forearm.L → wrist.L
  IK Target: foot_ik.front.L (paw pad altında, free, parent yok)
  Pole Target: elbow_pole.L (dirseğin önünde, "Cross product" matematiğiyle)
  Chain length: 3

Arka Bacak IK Chain:
  Root: hip.L
  Chain bones: thigh.L → shin.L → ankle.L → metatarsus.L
  IK Target: foot_ik.rear.L
  Pole Target: knee_pole.L (dizin önünde)
  Chain length: 4 (digitigrade için, plantigrade için 3)

Omurga IK (Bezier veya Spline IK):
  Curve: spine_curve
  Bones: spine.0, spine.1, spine.2 (lumbar segments)
  Control bones: spine_hip, spine_shoulder, spine_middle

Boyun IK (opsiyonel):
  Bones: neck.0, neck.1, neck.2
  Control: head_target (kafanın bakacağı noktayı kontrol için)

Kuyruk IK (opsiyonel, animasyon için kullanışlı):
  Bones: tail.0 ... tail.n
  Damped Track + Copy Rotation pattern (procedural physics yerine cheaper)
```

---

## 7. BONE NAMING CONVENTION (Godot 4 uyumlu)

Tüm bone'lar şu kuralı izler:

```
ana_bone.L / .R     (sol/sağ ayrımı, nokta yerine UNDERSCORE)
```

**ÖNEMLİ:** Godot 4 bone import bazen `.L` ekini parse hata olarak görür. Bu yüzden:

```
✅ İYİ:  shoulder_L, shoulder_R, foot_ik_front_L
❌ KÖTÜ: shoulder.L, foot_ik.front.L
```

Skinning modülünde Mirror mode kullanılırken `.L/.R` formatı geçici tutulur, **export öncesi** otomatik rename ile underscore'a dönüştürülür.

---

## 8. VERTEX GROUP'LAR

Her bone için bir vertex group lazım, ayrıca:

- `head` (Skin Mesh head detayları için)
- `eye.L`, `eye.R` (göz materyali için)
- `tongue` (eğer ağız açılıyorsa)
- `fur_zone_*` (kürk grooming için)

---

## 9. KÜRK / TÜYLENME

Memeli quadruped'lerin %95'i kürklü. Mobil için 2 yöntem var:

### 9.1 Yöntem A: Geometry Nodes Hair (Blender 4.2 native)

Pro: gerçekçi
Con: poly bütçeyi katlar, mobil zorlanır

### 9.2 Yöntem B: Texture-based fur (normal map + alpha cards)

Pro: mobile-friendly, ucuz
Con: yakın çekimde fake görünür

Skill kullanıcıya seçtirir.

---

## 10. ÖZEL TÜR EKSTANSİYONLARI

Bu sınıf base. Her tür için ek detaylar:

- **kurt/köpek:** ear position (dik / dolu), tail bushiness, snout length
- **kedi:** retractable claws, longer tail, ear tuft (lynx?)
- **at:** mane (yele), tail hair, hoof detail
- **aslan:** mane (erkek), tail tuft
- **geyik:** antlers (erkek, çift sapı varies), white tail underside

Skill bunları **kullanıcıyla soru-cevap** ile belirler, hardcoded değil.

---

## 11. STİLİZE MODIFICATION ALANLARI

Kullanıcı bu sınıfta şunları stilize edebilir:

- `head_size_multiplier` (default 1.0, kahraman karakterlerde sık ×1.3-1.5)
- `eye_size_multiplier`
- `paw_size_multiplier`
- `muscle_definition` (subtle / normal / exaggerated)
- `silhouette_aggressiveness` (kuyruk yukarı, omuz tepe, vb. attitude)
- `tooth_emphasis` (köpek dişi boyutu)
- `claw_emphasis`

Her birinin range'i ve mantıklı sınırı vardır; aşırı değerlerde skill uyarı verir ama yine de uygular.

---

## 12. BU SINIF DOSYASININ ÖZETİ

Skill bir mammalia_quadruped üretirken bu dosyayı **referans** olarak kullanır. Spec'i bu dosyadaki şablondan başlatır, kullanıcıyla iterate ederek özelleştirir.

İlk test (kurt) için skill bu dosyadan:
- Skeleton template (Canis lupus row)
- Köpekgiller orantı bandı
- Digitigrade stance
- Walk + trot + gallop gaits
- Ön ve arka bacak IK chain'leri
- Bone naming (`_L`/`_R`)
- Fur Method B (texture-based, mobil için)

kombinasyonunu **base** olarak alır, kullanıcı her birini soru-cevap'la modify ederek `CreatureSpec.json`'a yazar.
