# Apple Tree — User Assets Required

Mevcut ağaç **production-ready geometri + materyal pipeline'a** sahip, ancak texture/asset'ler **PLACEHOLDER**. Aşağıdaki dosyaları sağlarsan placeholder'lar otomatik swap edilebilir.

---

## PRIORITY 1 — Leaf Atlas (en yüksek görsel etki)

**Dosya:** `assets/trees/elma_agaci/textures/leaf/leaf_atlas.png`
**Mevcut yer alacağı placeholder:** `leaf_placeholder.png` (Python-baked, prosedürel)

### Spec:
| Özellik | Gereksinim |
|---|---|
| Çözünürlük | **1024×1024** minimum, **2048×2048** ideal |
| Format | **PNG, RGBA** (alpha kanalı zorunlu) |
| Color space | **sRGB** |
| Layout | **3×3 grid** = 9 farklı cluster varyantı |
| Hücre içeriği | Her hücre 4-7 elma yaprağı kümesi, organik dağınık |
| Alpha sınırı | **Soft falloff** — hücre kenarına doğru alpha 0'a fade. **HARD rectangle olmamalı.** |
| Background | Transparent (alpha=0) |
| Padding | Hücre kenarlarında 2-3% boş alan (UV bleed önleme) |

### İçerik notları:
- Her hücrede yaprak rotasyonu/scale farklı olsun
- Renk: koyu yeşil (mature) → açık yeşil (genç) tonları arası
- Hafif damar (vein) detayı görünür olsun
- 9 hücre arasında VAROYASYON: bazı küçük cluster, bazı büyük, bazı daha kompakt
- Apple leaf shape: ovate (oval, geniş ortada, daralan uç), 1.6:1 height/width

### Opsiyonel:
- `leaf_atlas_normal.png` (aynı layout, normal map, Linear color space)

### Test:
Dosya yerine konulduktan sonra:
```bash
blender --background --python elma_agaci_generator.py -- --no-bake --render --round 31
```
`--no-bake` flag mevcut atlas'ı kullanır (otomatik path: `leaf_atlas.png` varsa onu, yoksa placeholder).

---

## PRIORITY 2 — Bark Texture (orta görsel etki)

**Şu an:** Sadece vertex color (no UV, no texture).
**Eğer eklemek istersen:** Trunk + branches'a UV unwrap + bark texture eklenebilir.

### Dosyalar:
| Dosya | Çözünürlük | Color Space | Notlar |
|---|---|---|---|
| `textures/bark/bark_trunk_albedo.png` | 2048×2048 | sRGB | **Tileable** (seamless top/bottom) |
| `textures/bark/bark_trunk_normal.png` | 2048×2048 | Linear/Non-color | OpenGL convention (+Y up) |
| `textures/bark/bark_trunk_roughness.png` | 1024×1024 | Linear, grayscale | Opsiyonel |

### Spec:
- **Malus domestica** (Gala/Honeycrisp tarzı) bark — gri-kahverengi
- Vertical fissures (dikey çatlaklar) — gerçek apple bark karakteristiği
- Tileable vertical (üst-alt seamless) — trunk boyunca tekrarlanacak
- Renk: warm grey-brown, lighter olduğu için karanlık siyaha düşmesin

### Implementation notu:
Bu eklendiğinde benim yapmam gerekenler:
- Trunk + scaffold + secondary'lere UV unwrap (cylindrical projection)
- `M_Bark` material: vcolor × texture albedo, normal mapping ile detay
- ~3-5 dakika kod değişikliği

---

## PRIORITY 3 — Apple Texture (düşük görsel etki)

**Şu an:** Sadece vcolor (Gala sun/shade gradient).
**Eğer eklemek istersen:** Apple skin texture map.

### Dosya:
- `textures/apple/apple_skin_albedo.png` — **512×512** sRGB
- Opsiyonel: `apple_skin_normal.png` (lenticels/pürüz detayı)

### Spec:
- Gala apple skin pattern: kırmızı zemin + sarı-yeşil striping
- Lenticels (küçük beyaz noktalar) opsiyonel
- Hexagonal/tilable layout veya planar UV projection

---

## PRIORITY 4 — LOD3 Billboard Impostor (uzak mesafe optimizasyon)

**Şu an:** LOD3 implement edilmedi. Sadece LOD0/1/2 mevcut.

### Opsiyon A: Sen verirsen
- `textures/impostor/tree_impostor_atlas.png` — **2048×1024**
- 8 yönden ön-render (45° aralık) ağaç görüntüleri grid'i
- Hex billboard veya single cross-quad olarak kullanılabilir

### Opsiyon B: Ben otomatik üretirim
- `--bake-impostor` flag ekleyebilirim
- Blender renders 8 angles → atlas → LOD3 material
- ~30 dakika geliştirme

---

## PRIORITY 5 — Wind Animation Vertex Weights (animasyon)

**Şu an:** Statik mesh, wind sway yok.

### Eğer wind eklemek istersen:
**Hiç dosya gerekmez** — kod değişikliği:
- Vertex color UV2 layer ekle: R = trunk-to-tip weight, G = twig vs branch weight
- Vertex shader (Godot/Unity): UV2.r * sin(time + position) * wind_strength
- Çalışacağı engine? (Godot 4? Unity URP? Unreal?)

---

## TAM ÖZET (kontrol listesi)

### Şu an mevcut placeholder:
- [x] `leaf_placeholder.png` — Python-baked 768×768 3×3 atlas (procedural cluster silhouettes)

### İhtiyaç (gerçek dosyalar):

**Minimum (sadece görsel iyileşme için):**
- [ ] `textures/leaf/leaf_atlas.png` — 1024-2048 RGBA, 3×3 grid

**Orta (production ready için):**
- [ ] `textures/bark/bark_trunk_albedo.png` — 2048² sRGB tileable
- [ ] `textures/bark/bark_trunk_normal.png` — 2048² Linear

**Tam (AAA için):**
- [ ] `textures/apple/apple_skin_albedo.png` — 512² sRGB
- [ ] `textures/bark/bark_trunk_roughness.png` — 1024² Linear

**Opsiyonel (uzak LOD için):**
- [ ] `textures/impostor/tree_impostor_atlas.png` — 2048×1024 (veya ben üretirim)

---

## Dosya nereye konulacak?

```
mouse_open_world_clean_project/assets/trees/elma_agaci/
├── elma_agaci_generator.py
├── elma_agaci.blend / .glb / .fbx
└── textures/
    ├── leaf/
    │   ├── leaf_placeholder.png        ← mevcut (silinmez, fallback)
    │   └── leaf_atlas.png              ← BURAYA KOY (PRIORITY 1)
    ├── bark/                            ← bu klasörü oluşturacağım
    │   ├── bark_trunk_albedo.png
    │   ├── bark_trunk_normal.png
    │   └── bark_trunk_roughness.png
    ├── apple/                           ← bu klasörü oluşturacağım
    │   └── apple_skin_albedo.png
    └── impostor/                        ← LOD3 için
        └── tree_impostor_atlas.png
```

---

## Asset swap workflow

1. Sen dosyayı doğru yere koy (`textures/leaf/leaf_atlas.png`)
2. Bana de: "leaf atlas eklendi"
3. Ben generator'da:
   - `LEAF_TEXTURE_PATH` var olan dosyayı algılar
   - Material setup texture'i otomatik bağlar
   - UV koordinatları zaten 3×3 grid kullanıyor → bedavaya çalışır
4. Test render: `--render --round 31`
5. Görsel doğrulama
6. Commit

**Bark texture eklenirken** ek olarak UV unwrap + material rewrite gerekecek (~5-10 dk).

---

## Soru: Hangisini önce verebilirsin?

En büyük görsel sıçrama **leaf atlas** ile gelir (mevcut prosedürel placeholder vs gerçek photo atlas farkı çok).
İkinci en büyük: **bark texture** (vertex color renk gradient'ten gerçek texture'a).

Bunlardan birine veya birden fazlasına evet dersen klasörleri hazırlayıp swap kodunu yazarım.
