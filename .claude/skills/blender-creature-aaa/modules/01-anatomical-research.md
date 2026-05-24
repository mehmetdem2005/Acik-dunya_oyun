# Modül 01 — Anatomik Araştırma

**Amaç:** Kullanıcının istediği yaratık için **gerçek zoolojik anatomi** verisini toplamak, kullanıcıyla yapılandırılmış bir `CreatureSpec.json` üretmek. Sonraki tüm modüller bu spec'in dışına çıkamaz.

**Felsefe:** Hiçbir yaratık "tahmin" üzerinden modellenmez (§1, §7). Gerçek hayvan ise zoolojiden, fantastik ise base anatomy + style modifiers ile.

---

## 1. GİRİŞ NOKTASI

Bu modüle girişte skill kullanıcının istek cümlesini elinde tutar (örnek: "kurt yap", "büyük korkunç bir akrep").

İlk eylem: **tür tanımlama** ve **sınıf eşleme**.

### 1.1 Tür Tanımlama

Skill kullanıcıdan üç parça bilgi toplar:

```
══════════════════════════════════════════════════
ANATOMİK ARAŞTIRMA — Soru 1/3

İlk önce tam olarak ne yaptığımızı netleştirelim.

SORU: "[kullanıcının ifadesi]" diyorsun. Bunu nasıl yorumlayayım?

SEÇENEKLER:
  [a] Gerçek hayvan (örn: kurt = Canis lupus, gerçek anatomi)
  [b] Stilize hayvan (örn: çizgi film kurdu, abartılı kafa/diş)
  [c] Fantastik / hibrit (örn: ejderha = kertenkele + yarasa + dinozor)
  [d] Tam özel yaratık (sıfırdan tarif edeceğim)

══════════════════════════════════════════════════
```

Sonra:

```
══════════════════════════════════════════════════
ANATOMİK ARAŞTIRMA — Soru 2/3

Bu yaratığı görsel olarak somutlaştıralım.

SORU: Referans görüntü var mı? (En az 1, en fazla 5 foto ya da çizim.
İdeal olan: yan profil + ön + ¾ açı + duruş.)

SEÇENEKLER:
  [a] Evet, ben göndereceğim (ekle ve "hazır" de)
  [b] Hayır, web'den araştır ve bana 5-6 öneri göster, ben seçeyim
  [c] Sadece tarifimle git, foto kullanmasın
  [d] Web'den araştır + ben de göndereceğim (ikisini birleştir)

══════════════════════════════════════════════════
```

Sonra:

```
══════════════════════════════════════════════════
ANATOMİK ARAŞTIRMA — Soru 3/3

Stilize derecesini belirleyelim. (Bu, sonradan da değiştirilebilir
ama başlangıç noktası lazım.)

Türkçe karşılığı: yaratık gerçek hayvana ne kadar benzeyecek?

SORU: Hangi stilizasyon seviyesi?

SEÇENEKLER:
  [a] Fotorealistik (anatomi tam doğru, doğa belgeseli kalitesi)
  [b] Stilize-gerçek (orantılar gerçek, ama kas/kemik biraz abartılı —
      Witcher 3, Horizon Zero Dawn tarzı)
  [c] Yarı-stilize (kafa biraz büyük, gözler büyük, oyun-friendly —
      Genshin Impact, Diablo Immortal tarzı)
  [d] Tam-stilize (çizgi film, abartılı proporsiyonlar —
      Spyro, Crash Bandicoot tarzı)
  [e] Sen karar ver (mobil oyun + Godot bağlamına göre)

══════════════════════════════════════════════════
```

### 1.2 Sınıf Eşleme

Cevaplara göre skill `references/anatomy_classes/` altında uygun sınıfı belirler:

```python
# pseudo
species_to_class = {
    "kurt": "mammalia_quadruped",
    "köpek": "mammalia_quadruped",
    "aslan": "mammalia_quadruped",
    "at": "mammalia_quadruped",
    "ejderha": "chimera",
    "akrep": "arthropoda_arachnid",
    "örümcek": "arthropoda_arachnid",
    "kuş": "aves",
    "kartal": "aves",
    "yılan": "reptilia_serpent",
    # ... vb.
}
```

Eşleme net değilse:
```
"[term]" için anatomi sınıfı belirleyemedim. En yakın gördüklerim:
  [a] Memeli dört-ayaklı (mammalia_quadruped) — kurt, kedi, at gibi
  [b] Eklembacaklı (arthropoda) — örümcek, akrep, böcek
  [c] Hibrit / kimera (chimera) — birden fazla hayvan karışımı
Hangisi yakın?
```

Sınıf belirlenince:
```
✅ Sınıf belirlendi: mammalia_quadruped
Sınıf dosyasını yüklüyorum: references/anatomy_classes/mammalia_quadruped.md
```

Sınıf dosyası yoksa:
```
⚠️ Bu sınıf için anatomi dosyam henüz yok (arthropoda_arachnid yazılmamış).
Şu an yazmamı ister misin? Yaklaşık 15-20 dakika sürer, sonra rest of pipeline çalışır.
[evet, şimdi yaz / sonraya bırak / başka sınıfla simulate et]
```

---

## 2. WEB RESEARCH FAZI

Eğer kullanıcı (b) veya (d) seçtiyse skill **web search** yapar.

### 2.1 Arama Sorgu Stratejisi

3-5 arama paralel (peş peşe) çalışır:

1. `"{species} skeletal anatomy"` — iskelet yapısı
2. `"{species} body proportions"` — orantılar
3. `"{species} side profile photograph"` — yan görünüm referans
4. `"{species} musculature diagram"` — kas yapısı (opsiyonel)
5. `"{species} locomotion biomechanics"` — yürüyüş

Aramalar kullanıcı dilinde değil ingilizce yapılır (daha çok bilimsel kaynak çıkar). Skill sonuçları **Türkçeye çevirip** sunar.

### 2.2 Kaynak Önceliği

Skill bu kaynakları öncelikli kabul eder:
1. Wikipedia (general overview)
2. Veterinary anatomy textbooks (PDF preview'ları)
3. ResearchGate / academic papers (anatomy, biomechanics)
4. DigitalMorphology / MorphoSource (CT scan, varsa)
5. Wildlife photography sites (proporsiyon kontrolü için)

**Reddedilenler:** stock illustration siteleri (orantılar yanlış), DeviantArt fan art (stilizasyon karışıklığı yaratır), AI-generated content.

### 2.3 Çıktı

Her source'tan extract edilecek alanlar:
- **Skeletal landmark sayıları:** vertebra count (servikal, torasik, lumbar, kuyruk), kaburga çifti sayısı
- **Proportional ratios** (gövde uzunluğu = 1 normalize):
  - head_length / body_length
  - shoulder_height / body_length
  - hip_height / body_length
  - leg_length_front / body_length
  - leg_length_rear / body_length
  - tail_length / body_length
- **Locomotion type:**
  - digitigrade / plantigrade / unguligrade (memeliler için)
  - sprawling / parasagittal (sürüngenler için)
  - feature pairs (eklembacaklılarda)
- **Joint angle limits** (range of motion):
  - shoulder_flex, shoulder_extend
  - elbow_flex_max, elbow_extend_max (hyperextension var mı?)
  - hip, knee, ankle, vb.
- **Surface features:** kürk yönü, pul deseni, zırh plakaları, gözlerin pozisyonu, kulak yönü

---

## 3. ARAŞTIRMA ÇIKTISININ KULLANICIYA SUNULMASI

Skill bulguları **uzun rapor değil**, kısa Türkçe özet halinde sunar:

```
══════════════════════════════════════════════════
ANATOMİK ARAŞTIRMA TAMAMLANDI — Canis lupus (Kurt)

📐 İSKELET YAPISI:
  • Toplam omur: 53 (7 servikal + 13 torasik + 7 lumbar + 3 sakral + 18-22 kuyruk)
  • Kaburga: 13 çift
  • Omuz yüksekliği: gövde uzunluğunun ~%55'i
  • Kafa uzunluğu: gövde uzunluğunun ~%12'si
  • Ön bacak: arka bacaktan ~%5 daha kısa

🦴 DURUŞ TİPİ: Digitigrade
  → Parmak uçlarında yürür, topuk yerde değil (kedi, köpekgillerin tipik özelliği)
  → Ayak parmak yastığı (paw pad) görünür ve önemli detay

💪 KAS GRUPLARI (animasyonda kritik olanlar):
  • Boyun: trapezius + sternocleidomastoideus (kafa rotasyonu)
  • Omuz: deltoid + supraspinatus (ön bacak ekstansiyonu)
  • Sırt: longissimus dorsi (omurga eğilimi)
  • Arka bacak: gluteus + quadriceps (sıçrama gücü)
  • Karın: rectus abdominis (kıvrılma)

🏃 LOKOMOSYON:
  • Yürüme: 4-beat gait (her bacak ayrı zamanda)
  • Trot: 2-beat diagonal (LF+RR, RF+LR aynı anda)
  • Galop: 4-beat asimetrik

📸 BULDUĞUM REFERANSLAR (5 foto):
  [1] yan profil — National Geographic
  [2] ön — wildlife photographer Nick Brandt
  [3] ¾ açı — BBC documentary
  [4] iskelet diyagramı — veterinary anatomy textbook
  [5] kas yapısı — academic paper

══════════════════════════════════════════════════

ŞİMDİ KARARIN:

  [a] Bu anatomiyle aynen devam et (fotorealistik kurt)
  [b] Stilize değişiklikler yap (söyle: "kafa %20 büyüt", "diş abartılı",
      "bacaklar daha güçlü" vb.)
  [c] Bana 5 referansı tek tek göster, sonra karar vereyim
  [d] Bazı bilgiler eksik, şunu da araştır: [...]
  [e] Bu kurt değil benim istediğim, başka türlü olsun

══════════════════════════════════════════════════
```

---

## 4. STİLİZE MODIFICATION (kullanıcı b derse)

Kullanıcı stilize değişiklik isterse interaktif düzenleme:

```
══════════════════════════════════════════════════
STİLİZE DEĞİŞİKLİKLER

Hangi parametreleri değiştirelim? (toplu cevap verebilirsin)

  [1] head_length oranı   (şu an %12) → ?
  [2] shoulder_height     (şu an %55) → ?
  [3] leg_length_front    (şu an gövde×0.5) → ?
  [4] tail_length         (şu an gövde×0.4) → ?
  [5] ear_size_multiplier (default 1.0) → ?
  [6] eye_size_multiplier (default 1.0) → ?
  [7] tooth_emphasis      (canine boyutu, default 1.0) → ?
  [8] muscle_definition   (default normal) → [subtle / normal / abartılı / aşırı]
  [9] başka özel istek var mı?

Örnek cevap: "1=%18, 6=2.0, 8=abartılı"

══════════════════════════════════════════════════
```

---

## 5. CREATURESPEC.JSON ÜRETİMİ

Tüm bu süreç sonunda skill `memory/runs/<timestamp>/CreatureSpec.json` üretir. Şema:

```json
{
  "creature_id": "kurt_001",
  "common_name_tr": "Kurt",
  "scientific_name": "Canis lupus",
  "anatomy_class": "mammalia_quadruped",
  "stylization_level": "stylized_realistic",
  "user_modifications": {
    "head_length_ratio": 0.18,
    "eye_size_multiplier": 2.0,
    "muscle_definition": "exaggerated"
  },
  "skeleton": {
    "cervical_vertebrae": 7,
    "thoracic_vertebrae": 13,
    "lumbar_vertebrae": 7,
    "sacral_vertebrae": 3,
    "caudal_vertebrae": 20,
    "rib_pairs": 13
  },
  "proportions": {
    "head_length": 0.18,
    "shoulder_height": 0.55,
    "hip_height": 0.53,
    "leg_length_front": 0.50,
    "leg_length_rear": 0.52,
    "tail_length": 0.40
  },
  "locomotion": {
    "stance": "digitigrade",
    "gaits": ["walk_4beat", "trot_diagonal", "gallop_asymmetric"],
    "max_speed_kmh": 65
  },
  "joint_limits_degrees": {
    "shoulder_flex": [-60, 90],
    "elbow_flex": [0, 140],
    "wrist": [-30, 30],
    "hip_flex": [-45, 110],
    "knee_flex": [0, 130],
    "ankle": [-40, 40],
    "spine_lateral": [-25, 25],
    "neck_twist": [-90, 90]
  },
  "surface_features": {
    "fur": true,
    "fur_direction_map": "default_canid",
    "scales": false,
    "armor_plates": false,
    "claws": true,
    "paw_pads": true,
    "fang_count": 4
  },
  "references": {
    "user_provided_images": [],
    "web_research_images": [
      {"url": "...", "tag": "side_profile", "credit": "..."},
      ...
    ]
  },
  "user_approval_timestamp": "2026-05-24T...",
  "research_sources": ["Wikipedia: Wolf", "..."]
}
```

Bu JSON'ı kullanıcıya **kısa özet** olarak gösterir, raw json **istemezse** vermez:

```
✅ Spec hazır. Onay verirsen sonraki faza geçiyorum: Bütçe ve Tier Belirleme.

Spec özeti:
  • Tür: Kurt (Canis lupus), stilize-gerçekçi
  • İskelet: 53 omur, 13 çift kaburga
  • Duruş: digitigrade (parmak ucu)
  • Senin değişikliklerin: kafa %18, göz 2×, kas abartılı

[devam / spec'i tekrar göster / değişiklik yapacağım / raw json göster]
```

---

## 6. HATA / EKSİK DURUMLARI

- **Web search hiç sonuç döndürmedi:** kullanıcıya bildir, "bu tür çok obscure, referans foto sağlayabilir misin?" diye sor
- **Sınıf dosyası yok:** "şimdi yazayım mı?" sor (§9)
- **Kullanıcı çok kontrastlı stilize istedi (örn: %50 kafa):** uyarı ver ama yine de yap ("bu orantı animasyonda dengesiz görünebilir, yine de devam?")
- **Fantastik yaratık ama base species belirsiz:** "ejderha = kertenkele + yarasa + büyük kedi gibi düşünebilir miyiz?" diye base species önerileri sun

---

## 7. ÇIKTI VE SONRAKİ MODÜL

Bu modül kapanırken:
1. `CreatureSpec.json` yazılır
2. `memory/decisions.jsonl`'a entry eklenir
3. Referans görüntüler `memory/runs/<timestamp>/refs/` altına indirilir
4. Kullanıcıya: *"Faz 2 (Bütçe & Tier) modülüne geçeyim mi?"*

**ÖNEMLİ:** Bütçe modülü (`02-budget-spec.md`) henüz yazılmadı. Skill bunu kullanıcıya bildirip "şimdi yazayım mı, sonra mı?" diye sorar (§3 + canlı self-extension).
