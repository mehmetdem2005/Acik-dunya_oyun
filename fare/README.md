# Fare (Mouse) Rig — Pipeline v2 (v16)

Bağımsız fare rigi + animasyonlar: yürüme, koşu, idle/nefes, koklama.
Nefes, bıyık, kulak, kuyruk, parmak ve mimik kontrolleri destekler.

## Dosyalar

| Dosya | Açıklama |
|------|----------|
| `source/mouse3dmodel1k.glb` | Tripo AI mesh kaynağı (orijinal, DOKUNULMADI) |
| `source/fare_original.prisma` | Prisma3D referans |
| `scripts/mouse_rig_lib.py` | Ortak kütüphane (BVH, region weighting, medial axis) |
| `scripts/rig_mouse_v16.py` | Rig kurulum (deform + control + skin + GLB) |
| `scripts/stage6_posetest.py` | İzole bone leak-audit (rig GATE) |
| `scripts/anim_v16.py` | 4 animasyon (Walk/Run/Idle/Sniff) + GLB export |
| `scripts/render_anim_v16.py` | Animasyon frame render |
| `out/mouse.glb` | Statik rigli + skinli GLB |
| `out/mouse_anim.glb` | 4 animasyon gömülü GLB (final ürün) |
| `out/mouse_v16.blend` / `out/mouse_anim.blend` | Blender çalışma dosyaları |
| `out/qa_anim_*/` | Animasyon GIF + frame'ler |
| `out/qa_posetest/` | Stage 6 leak-audit renderları |

## Üretim

```bash
sudo apt-get install -y blender
blender --background --python fare/scripts/rig_mouse_v16.py      # rig + skin
blender --background --python fare/scripts/stage6_posetest.py    # GATE: leak audit
blender --background --python fare/scripts/anim_v16.py           # animasyonlar
```

## Rig (138 kemik)

4 katman (Blender bone collections): **DEF** (deform) / **CTRL** (IK target,
pole, kontrol) / **MCH** (root, COG, mekanizma).

```
root → COG → pelvis
  ├─ sacrum → tail_01 … tail_22                     (medial axis kuyruk)
  ├─ hip_L → femur_L → tibia_L → tarsus_L → back_paw_L → back_toe_L_{1..3}_{01,02}
  ├─ hip_R → … (TAM SİMETRİK ayna: tarsus_R, back_paw_R dahil)
  └─ lumbar_01..04 → thoracic_01..05 → cervical_01..03 → head
       ├─ scapula_L → humerus_L → radius_L → carpus_L → front_paw_L → front_toe_L_{1..3}_{01,02}
       ├─ scapula_R → … (TAM SİMETRİK ayna)
       ├─ jaw_base → jaw_tip
       ├─ eye_L/R, cheek_L/R, nose_L/R, upper_lip_L/R, lower_lip_L/R, nose_tip
       ├─ ear_{L,R}_base/mid/tip
       └─ whisker_pad_{L,R} → whisker_{L,R}_{1..4}_{root,mid,tip}
CTRL: CTRL_ik_{FL,FR,BL,BR} (foot-lock IK target), CTRL_tail_tip
```

## Skinning — bölge-bilinçli + bütçeli (weight bleed YOK)

Her vertex anatomik bölgeye atanır (head/FL/FR/BL/BR/tail/body); sadece o
bölgenin kemikleri + sert mesafe-cutoff ile ağırlık alır. Bone başına vertex
bütçesi denetlenir (whisker ≤160, eye ≤360, jaw ≤1400 vb.). Sonuç: **Stage 6
izole pose-test'te leak = 0mm** (bir bone hareket edince başka bölge kımıldamaz).
Max 4 influence/vertex + normalize (Godot/GLB uyumu).

## Animasyonlar (mouse_anim.glb)

| Action | Frame | İçerik |
|---|---|---|
| **Walk** | 32 | 4-beat (Muybridge sırası), IK foot-lock, gövde sway, omurga dalgası, kuyruk gecikmeli sway, nefes |
| **Run** | 16 | Hızlı gallop, omurga stretch/crouch, güçlü arka itiş |
| **Idle** | 60 | Nefes (breath driver), kulak ara perk, bıyık mikro-twitch |
| **Sniff** | 24 | Baş dip, burun+bıyık titreşim |

Custom props (armature): `breath`, `jaw_open`, `ear_{L,R}_perk`.

## Mesh durumu
DOKUNULMADI — sadece import transformu (Y-up→Z-up) bake edildi. Vertex
pozisyonları orijinal Tripo çıkışıyla aynı; eklenen: bone weight + Armature
modifier + animasyon action'ları.

## Doğrulama
- Stage 6 pose-test: tüm izole bone testlerinde leak = 0mm (PASS)
- L/R bacak simetri: PASS (16 = 16)
- mouse_anim.glb: 4 action, 138 kemik, max 4 influence/vertex, 0 ihlal

## Bilinen sınırlamalar
- Headless Blender 4.0'da `ARMATURE_AUTO` (heat) bozuk → bölge-bilinçli +
  mesafe-cutoff weighting kullanıldı.
- Sert bölge ayrımı → bazı bölge sınırlarında hafif dikiş olabilir (cross-region
  smoothing weight bleed'i geri getirdiği için kapalı).
- lower_lip/cheek bölge bütçesini hafif aşıyor (yüzle sınırlı, gövdeyi etkilemez).

## Önceki sürümler
`scripts/rig_mouse_v{1..15}.py` + `fare/1.deneme/` — eski denemeler (referans).
v1-v12 manuel/medial, v13 reddedildi, Rigify wolf-metarig (mesh dışı taştı),
v14/v15 (weight bleed + asimetrik arka bacak). v16 = Pipeline v2 (bu sürüm).
