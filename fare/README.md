# Fare (Mouse) Rig — v14

Bağımsız fare rigi: nefes, bıyık, kulak, kuyruk, yürüme, parmak ve mimik animasyonlarını destekler.

## Dosyalar

| Dosya | Açıklama |
|------|----------|
| `source/mouse3dmodel1k.glb` | Tripo AI mesh kaynağı (orijinal, değiştirilmedi) |
| `source/fare_original.prisma` | Prisma3D referans |
| `scripts/rig_mouse_v14.py` | Aktif rig kurulum script'i (final) |
| `scripts/render_v14.py` | Multi-angle QA render script'i |
| `out/mouse.glb` | Rigli + skinli GLB (final ürün) |
| `out/mouse_v14.blend` | Blender çalışma dosyası |
| `out/qa_v14/` | 6-açılı QA renderları (yan/yan2/ön/arka/üst/perspektif) |

## Kurulum / yeniden üretim

```bash
sudo apt-get install -y blender
cd <repo>
blender --background --python fare/scripts/rig_mouse_v14.py
blender --background --python fare/scripts/render_v14.py
```

## Rig yapısı (86 kemik)

```
root
└─ hips
   ├─ spine_01 → spine_02 → chest → neck → head
   │                                        ├─ snout → nose
   │                                        ├─ jaw
   │                                        ├─ eye_L, eye_R
   │                                        ├─ ear_L_base → ear_L_mid → ear_L_tip
   │                                        ├─ ear_R_base → ear_R_mid → ear_R_tip
   │                                        └─ whisker_{L,R}_{1..4}
   │              chest:
   │                ├─ scapula_L → upper_arm_L → forearm_L → front_paw_L
   │                │                                          └─ finger_F_L_{1..3}_{01,02}
   │                └─ scapula_R → upper_arm_R → forearm_R → front_paw_R
   │                                                           └─ finger_F_R_{1..3}_{01,02}
   ├─ hip_L → thigh_L → shin_L → [ankle_L →] back_paw_L
   │                                       └─ finger_B_L_{1..3}_{01,02}
   ├─ hip_R → thigh_R → shin_R → back_paw_R
   │                              └─ finger_B_R_{1..3}_{01,02}
   └─ tail_01 → tail_02 → ... → tail_19  (kuyruk omurları, mesh eğrisini takip eder)
```

## Constraint stack

- **IK**: `front_paw_L/R`, `back_paw_L/R` (her biri chain_count=3)
- **Driver**: `chest.scale_y = 1 + breath * 0.08` (nefes alıp verme)
- **Driver**: `jaw.rotation_x = jaw_open * 0.6` (çene açma)
- **Driver**: `ear_{L,R}_base.rotation_x = ear_{L,R}_perk * 0.4` (kulak dikme)

## Custom properties (armature object üzerinde)

- `breath` — [-1, 1] nefes alıp verme
- `jaw_open` — [0, 1] çene açma
- `ear_L_perk`, `ear_R_perk` — [-1, 1] kulak dikme

## Anatomik anchor kaynakları

Rig, Tripo AI'nın 33 mesh-içi joint'ini anatomik referans olarak alır
(omuz/kalça/diz/pati pozisyonları doğrudan mesh içinden gelir), eksik
kısımlar (kuyruk uzantısı, kulak kıkırdağı, bıyık, çene, göz, parmak)
mesh landmark'larından + BVH iç-kontrol ile eklenmiştir. Tüm DEF
kemikleri mesh içinde konumlanmıştır.

## Mesh durumu

Mesh DOKUNULMADI — sadece import transformu bake edildi (Y-up → Z-up).
Vertex pozisyonları orijinal Tripo çıkışıyla aynı. Eklenenler sadece:
bone weight'leri (envelope-based skin) ve Armature modifier.

## Bilinen sınırlamalar

- Auto-weight (heat) headless Blender 4.0'da çalışmadığı için
  envelope-binding kullanıldı. 172 vertex (%0.76, çoğu bıyık ucu) en
  yakın kemiğe rigid atandı.
- GUI'de bir sanatçı ayarlamadıkça envelope bazlı ağırlıklar bazı sınır
  bölgelerinde (örn. omuz-çene kesişimi) mükemmel olmayabilir;
  weight-painting bir sonraki aşama (Stage 4) için planlanmıştır.

## Önceki sürümler (1.deneme/, scripts/rig_mouse_v{1-12}.py)

v1-v12 manuel placement + Rigify wolf-metarig denemelerinde kemikler
mesh dışına taşıyordu (anatomik proporsiyonlar uyuşmadı). v14
yaklaşımı: Tripo'nun zaten mesh-içi olan 33 anchor joint'ini koru +
sadece eksikleri ekle — bu sayede tüm kemikler mesh içinde kalır.
