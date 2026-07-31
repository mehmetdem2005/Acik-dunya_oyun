# Ejderha — üretim kalitesinde, riglenmiş, animasyonlu oyun varlığı

Referans görseldeki koyu antrasit pullu, kemik-bej ventral plakalı, bordo kanat
zarlı ağır gövdeli batı ejderhası. Tamamı Blender 4.2 LTS içinde **sıfırdan
parametrik olarak** üretilir — hazır/AI mesh import edilmez, fotoğraf dokusu
projekte edilmez.

```
blender --background --python build_dragon.py
```

Tek komut şu sırayı çalıştırır: omurga eğrisi → ölçek → prosedürel PBR dokular →
geometri → temizlik/normal → UV1 lightmap → iskelet + skinning → 25 animasyon →
LOD zinciri + mobil + çarpışma → QA → glTF 2.0 export → 8 açı önizleme render.
Toplam süre ~5 dk (4 çekirdek CPU).

---

## 1. Teslim edilen dosyalar

| Dosya | İçerik |
|---|---|
| `dragon_master.glb` | Tek dosya: LOD0 + iskelet + 25 animasyon + gömülü dokular |
| `dragon_master.gltf` + `.bin` + `textures/` | Aynı içerik, **göreceli yollu** ayrık sürüm |
| `dragon_lod1..4.gltf` + `.bin` | LOD kademeleri (ortak `textures/` klasörünü kullanır) |
| `dragon_mobile.gltf` + `.bin` | Mobil sürüm, 65k üçgen, animasyonlar dahil |
| `dragon_collision.glb` | 13 konveks çarpışma proxy'si (render edilmez) |
| `dragon_shadowproxy.gltf` + `.bin` | 2.8k üçgen gölge proxy'si |
| `textures/` | 8 materyal × 3 harita = 24 PNG (1024², lossless) |
| `preview/` + `dragon_contact_sheet.png` | 8 açı render |
| `qa_report.txt` / `stats.json` | Otomatik kalite kontrol çıktısı |

`dragon.blend` **depoya konmadı** — 92 MB ve tamamen yeniden üretilebilir.
Gerekirse `build_dragon.py` çalıştırıldığında yeniden oluşur.

> LOD/mobil/gölge dosyaları bilerek `.gltf`+`.bin` — GLB olsalardı her biri 24
> dokuyu ayrı ayrı gömer, teslimat ~200 MB büyürdü.

---

## 2. Doğrulanmış ölçüler (qa_report.txt)

| Ölçü | Değer |
|---|---|
| Omurga yay uzunluğu (burun → kuyruk ucu) | **16.00 m** (tam hedef) |
| Omuz (withers) yüksekliği | **4.50 m** (tam hedef) |
| Bounding box | 19.26 × 8.78 × 15.11 m |
| Kanat açıklığı — bind poz (yarı açık) | 19.26 m |
| Kanat açıklığı — tam açık (`Wing_Unfold` sonu) | ~22 m |
| Ayak tabanı zemin sapması | −0.0002 m |
| Birim | metre, Y yukarı, **−Z ileri**, +X sağ (Godot) |
| Transform | scale 1,1,1 · rotation 0,0,0 · negatif scale yok |
| Root pivot | zeminde, ön/arka bacak arasında (`Dragon_Root` @ 0,0,0) |

---

## 3. Geometri — QA sonucu

```
üçgen                : 180 634        quad/ngon : 87 529 / 0
vertex               :  90 927
non-manifold edge    : 0              açık (boundary) edge : 0
wire edge / loose vtx: 0 / 0          sıfır alanlı yüz     : 0
aşırı ince üçgen     : 269            imzalı hacim         : +33.17 m³ (normaller dışa)
```

**Su geçirmez (watertight).** Normaller her bağlı kabuk için ayrı ayrı, işaretli
hacim ölçütüyle dışa çevrilir (`pipeline.recalc_normals`) — göz/dil/diş gibi iç
içe kabuklarda bmesh'in kendi sezgisi yanılabildiği için.

### Gerçek kaynak (weld) yapılan yerler
Gövde tüpünde uzuvlar için **gerçek delik açılır**, deliğin sınır halkası uzvun
ilk halkası olarak yeniden kullanılır. Yani 4 bacak, 2 kanat kökü ve kafa↔boyun
geçişinde iç içe geçme yoktur, tek manifold yüzey vardır:

```
delik = a satır × b kolon  →  sınır halkası = 2(a+b) = 40 vertex = uzvun ilk halkası
```

### Bilinçli olarak ayrı kabuk bırakılanlar
Boynuzlar, sırt dikenleri, ense yelesi, dişler, pençeler, gözler, dil, ventral
plakalar, alt çene ve kanat zarı ayrı kapalı kabuklardır; kökleri deriye gömülür
ve tabanda etekleşerek doğal birleşir. Şartname bunu açıkça izin veriyor
("Büyük diken ve boynuzlar ayrı veya kontrollü şekilde birleştirilmiş geometri
olabilir"). **Dürüst not:** parametrik süpürme ile her uzantıyı tek kabukta
birleştirmek mümkün değil; endüstri pratiği de zaten budur.

### Kanat topolojisi
Zar + parmak kemikleri + ön kol **tek bağlı quad tabakası** olarak üretilir,
sonra değişken kalınlıkta solidify edilir (kemik hattında kalın, zar arasında
ince). Böylece dallanma problemi oluşmaz ve katlanırken zar yırtılmaz. Zarda
gerçek geometrik delikler (iyileşmiş yırtık izleri) vardır; solidify rim'i
onları da kapatır.

---

## 4. UV ve dokular

- **UV0** — elle belirlenmiş atlas dikdörtgenleri (`dragon/uvmap.py`), çakışma
  yok, ada arası padding var. Doku üretimi aynı dikdörtgenleri okur, bu yüzden
  pul yönü anatomik akışa uyar ve seam'de kesinti olmaz.
- **UV1** — `UV1_Lightmap`, smart-project ile ayrı kanal (lightmap / ek bake).
- Çözünürlük: **1024²** (kullanıcı kararı). `config.TEX_SIZE` değiştirilip
  script tekrar çalıştırılarak 2K/4K/8K üretilebilir — dokular analitik olduğu
  için çözünürlükten bağımsız kalitede.

### ORM paketlemesi
`R = Ambient Occlusion · G = Roughness · B = Metallic` — tek texture hem
`occlusionTexture` hem `metallicRoughnessTexture` olarak bağlanır (glTF'te aynı
index → ekstra bellek yok).

### Materyaller (8, şartnamedeki isimlerle)
`M_Dragon_Body` · `M_Dragon_Head` · `M_Dragon_Wings` · `M_Dragon_Horns_Claws` ·
`M_Dragon_Eyes` · `M_Dragon_Mouth` · `M_Dragon_Teeth` · `M_Dragon_Scars`

- Metallic **her yerde 0** — metal zırh görünümü yok.
- Roughness bölgesel: gövde pulu 0.16–0.94, boynuz kuru/yüksek, pençe ucu daha
  düşük, ıslak ağız 0.24–0.30, göz korneası 0.05.
- Normal map **tangent-space, glTF standardı (+Y yukarı)**. Bake edilmedi;
  yükseklik alanından Sobel ile analitik üretildi → cage hatası, skew, banding
  ve projeksiyon artefaktı yapısal olarak imkânsız.
- **Alpha kanalı yok.** Kanat zarı katı kabuk olduğu için maskeye gerek kalmadı
  → transparent sorting sorunu, beyaz halo riski sıfır.

### Doku içeriği (kopyalanmış desen hissi kırılır)
Her pul kendi rastgele tonunu alır; üzerine macro renk varyasyonu, pas/kızıl
geçiş, cavity karartma, kenar aşınması, kir birikimi, çatlak/kırık pul izleri ve
büyük yara çizgileri eklenir. Kanat zarında 4 kademeli damar ağı, gerilim
kırışıklıkları, iyileşmiş delik izleri ve parmak kemiği şeritleri vardır.

---

## 5. Rig

**98 deform kemiği**, şartnamedeki hiyerarşiye sadık:

```
Dragon_Root → Root_Motion → Pelvis
  ├ Spine_01..03 → Chest → Neck_01..04 → Head
  │                        ├ Jaw → Tongue_01,02
  │                        ├ Eye_L/R, Eyelid_L/R
  │                        ├ Nostril_L/R, LipUpper_L/R, Brow_L/R
  │                        ├ Shoulder_L/R → FrontLeg → FrontLegLow → FrontAnkle
  │                        │                 → FrontFoot → FrontToe01..04
  │                        └ WingRoot_L/R → WingArm (+WingArmTwist) → WingForearm
  │                                       → WingWrist → WingFinger01..04 (+b)
  │                                       + WingMembrane (yardımcı deform)
  ├ Hip_L/R → RearLeg → RearLegLow → RearAnkle → RearFoot → RearToe01..04
  └ Tail_01..08 → Tail_Tip
```

- Eklemler **göz kararı değil**: geometriyi üreten parametrelerin ta kendisinden
  (omurga yay konumu `s`, uzuv zincir eklemleri, kanat iskelet noktaları) alınır
  → rest sapması yapısal olarak sıfır.
- Ağırlıklar numpy ile kemik-segmenti mesafesine göre, **bölge kapısı (region
  gating)** ile hesaplanır: kanat vertex'i bacak kemiği alamaz, çene vertex'i
  boyun kemiği alamaz.
- **Vertex başına en fazla 4 kemik**, ağırlık toplamı **1.0000** (QA doğruladı),
  ağırlıksız vertex **0**.
- Sol/sağ tam simetrik başlar (aynalanmış parametreler).
- Bind pose: **kanatlar yarı-açık nötr** — hem tam açılma hem tam katlanma
  yönünde eşit mesafe, iki uçta da minimum çökme.
- Export iskeleti sadece deform kemiklerini içerir; IK yoktur (animasyonlar
  bake sırasında IK ile çözülüp FK'ya yazılır, §6).

---

## 6. Animasyonlar — 25 klip

20 temel klip + 5 root-motion varyantı (`*_RM`).

```
Idle_Ground  Idle_Alert  Walk  Run  Turn_Left_90  Turn_Right_90
Takeoff  Flight_Forward  Flight_Glide  Flight_Hover  Landing
Wing_Fold  Wing_Unfold  Roar  Bite_Attack
Claw_Attack_Left  Claw_Attack_Right  Tail_Attack  Hit_Reaction  Death
+ Walk_RM  Run_RM  Takeoff_RM  Flight_Forward_RM  Landing_RM
```

### Ayak kayması nasıl engellendi
Klipler saf FK ile değil, **her karede 2-kemikli IK çözülerek** üretilir
(`dragon/anim.py` → `Rigger.solve_legs`). Duruş (stance) fazında ayak hedefi,
karakterin ileri hızını **tam olarak dengeleyecek** şekilde geriye kaydırılır:

```
stance:  offset = ileri × adım × (0.5 − faz/duty)      → ayak yere sabit
swing :  offset = ileri × adım × (−0.5 + q),  y = kaldırma × sin(πq)
```

In-place klipte ayak gövdeye göre geriye kayar; `_RM` varyantında `Root_Motion`
tam o hızla ileri gider → **dünyada net kayma sıfır**. İkisi ayrı klip olduğu
için motor tarafında kolayca seçilir.

- Dörtayaklı yürüyüş faz tablosu: LF 0.00 · RH 0.25 · RF 0.50 · LH 0.75
- Koşu (gallop): LF 0.00 · RF 0.14 · LH 0.52 · RH 0.66
- Walk/Run/Flight/Glide/Hover loop'lanabilir (son kare = ilk kare).
- Kuyruk her klipte gecikmeli dalga (`lag`) ile takip eder → ağırlık hissi.
- Tail_Attack ve Death'te kuyruk segment segment gecikir (kırbaç etkisi).

---

## 7. LOD ve mobil

| Sürüm | Üçgen | Hedef | Kullanım |
|---|---|---|---|
| LOD0 | 180 634 | 180–250k | yakın plan / sinematik |
| LOD1 | 109 998 | 90–130k | ana oyun kamerası |
| LOD2 | 52 000 | 40–65k | orta mesafe |
| LOD3 | 20 000 | 15–25k | uzak |
| LOD4 | 7 468 | 5–10k | çok uzak / kalabalık |
| Mobile | 65 000 | 50–80k | mobil ana mesh |
| Shadow | 2 848 | — | gölge proxy |

Hepsi aynı pivot, aynı dünya ölçeği, aynı yön, **aynı iskelet** ve aynı materyal
isimlerini kullanır. Decimate sonrası her LOD `cleanup_mesh` + `mesh.validate()`
ile onarılır (glTF "not valid" uyarısı üretilmez).

### Çarpışma proxy'leri (13 parça, konveks, düşük poligon)
`Head` · `Neck` · `Chest` · `Pelvis` · `Tail_01..03` · `FrontLeg_L/R` ·
`RearLeg_L/R` · `Wing_L/R` — hepsi `_Collision` sonekli, ayrı materyal,
`hide_render = True`. Tek dev concave collision **yok**.

---

## 8. Godot 4.6 kullanımı

1. `dragon_master.glb` (veya `dragon_master.gltf`) dosyasını `res://` altına
   koyun — Godot importer'ı doğrudan açar.
2. İçe aktarma sonrası: `Skeleton3D` + `AnimationPlayer` otomatik oluşur,
   25 klip `AnimationLibrary`'de görünür.
3. Materyaller saf **glTF 2.0 metallic-roughness** — hiçbir uzantı kullanılmaz
   (`extensionsUsed: yok`). Forward+ ve Mobile renderer'da aynı görünür.
4. Cull: tüm materyallerde `use_backface_culling = True` → Godot'ta
   `cull_mode = Back`. Kanat zarı katı kabuk olduğu için tek taraflı yeterli;
   çift taraflı istenirse `M_Dragon_Wings` materyalinde `cull_mode = Disabled`
   yapmak yeterli (geometri buna hazır).
5. Çarpışma için görsel mesh **kullanmayın** — `dragon_collision.glb` içindeki
   parçaları `CollisionShape3D` + `ConvexPolygonShape3D` olarak bağlayın ve
   ilgili kemiklere `BoneAttachment3D` ile takın.
6. LOD'lar ayrı dosyalar; `VisibilityRange` ile veya kendi LOD yöneticinizle
   değiştirin.

Node isimleri: `Dragon_Root`, `Dragon_Skeleton`, `Dragon_LOD0..4`,
`Dragon_Mobile`, `Dragon_Collision`, `Dragon_ShadowProxy`. Dosya ve doku
isimlerinde boşluk, Türkçe karakter veya otomatik isim yok.

---

## 9. Kaynak kod haritası

```
build_dragon.py            tek komutluk pipeline + QA + önizleme render
dragon/
  config.py                TÜM sayısal parametreler (ölçü, profil, palet, bütçe)
  core.py                  pchip, gürültü, omurga eğrisi, MeshBuilder
  uvmap.py                 UV atlas dikdörtgenleri (doku üretimi bunu okur)
  body.py                  gövde tüpü + uzuv delikleri + pul kabartısı
  head.py                  kafatası+damak, alt çene, dil, göz, burun deliği
  limbs.py                 bacaklar, ayak pedi, parmaklar, pençeler
  wings.py                 kanat kök tüpü + tek parça zar kabuğu
  details.py               boynuz, sırt dikeni, ense yelesi, diş, ventral plaka
  textures.py              prosedürel PBR (numpy) → PNG
  materials.py             Principled BSDF + ORM + glTF Material Output
  rig.py                   iskelet, ölçülmüş skinning, FK/IK matematiği
  anim.py                  25 klip, IK'lı yürüyüş çözümü
  pipeline.py              temizlik, normal onarımı, LOD, collision, export
```

Her şey `config.py`'den sürülür; oran/bütçe/palet değiştirmek için tek dosyaya
dokunmak yeterli. `--seed N` ile varyant üretilebilir.

---

## 10. Dürüst sınırlamalar

Bunlar bilinçli tercihler veya kabul edilmiş kısıtlar — gizlenmemesi gerekiyor:

1. **El heykeli değil, parametrik üretim.** ZBrush'ta tek tek yontulmuş bir
   sculpt değil; anatomik eğri + kesit profili + prosedürel yer değiştirme ile
   üretiliyor. Avantajı: tekrar üretilebilir, tur tur iyileştirilebilir,
   tek parametreyle varyant çıkar. Dezavantajı: bir sanatçının elindeki serbest
   form kararları (ör. referanstaki tek tek pul yerleşimi) birebir kopyalanmaz.
2. **Yüksek-poly → düşük-poly bake yapılmadı.** Normal map yükseklik alanından
   analitik üretiliyor. Sonuç bake artefaktı içermiyor ama "gerçek high-poly
   sculpt'tan bake" iş akışı da değil.
3. **Morph target (blend shape) yok.** Yüz ifadeleri sınırlı yüz kemikleriyle
   (Jaw, Eyelid, Nostril, LipUpper, Brow) yapılıyor. glTF morph desteği export
   ayarlarında açık, eklenmek istenirse altyapı hazır.
4. **Draco/Meshopt sıkıştırma kullanılmadı** — sıkıştırılmamış sürüm istendiği
   ve dosyalar zaten makul olduğu için.
5. **Ayrı kabuklar** (§3) — boynuz/diş/pençe/göz/dil kökleri deriye gömülü.
6. **İyileştirilecekler:** kanat zarının gövdeye bağlandığı bölge (patagium)
   daha geniş olabilir; ense yelesi referanstaki kalkan benzeri büyük plakalara
   göre biraz ince; kuyruk ucu zırh plakaları geometri yerine kısmen normal
   map'te.

---

## 11. Kalite kontrol — kontrol listesi durumu

| Kontrol | Sonuç |
|---|---|
| Non-manifold yüzey | ✅ 0 |
| Duplicate vertex | ✅ temizlendi (568 birleştirildi) |
| Açık edge | ✅ 0 |
| Ters normal | ✅ hacim +33.17 m³, ada bazlı onarım |
| Sıfır alanlı yüz | ✅ 0 |
| Bozuk triangulation | ✅ `mesh.validate()` temiz, ngon 0 |
| Aşırı ince üçgen | ⚠️ 269 (koni uçlarındaki yelpaze kapaklar — kabul edilebilir) |
| Ağırlıksız vertex | ✅ 0 |
| Vertex başına kemik | ✅ max 4 |
| Ağırlık normalizasyonu | ✅ 1.0000 |
| UV overlap | ✅ atlas elle bölündü, çakışma yok |
| İkinci UV kanalı | ✅ `UV1_Lightmap` |
| Normal map yönü | ✅ tangent-space, +Y |
| ORM paketlemesi | ✅ R=AO, G=Rough, B=Metal |
| Kanat alpha halosu | ✅ alpha kullanılmıyor |
| glTF texture yolu | ✅ göreceli (`textures/...`) |
| Fazladan kamera/ışık | ✅ 0 |
| Animasyon isimleri | ✅ 25 klip korunuyor |
| Model zemine oturuyor | ✅ min Y = −0.0002 m |
| Materyal pembe/siyah | ✅ 8 materyal, hepsi bağlı |
