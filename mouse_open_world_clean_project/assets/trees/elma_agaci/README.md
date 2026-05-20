# Elma Ağacı (Malus domestica) — Procedural Blender Asset

Mobil hedefli (~15k tri) elma ağacı GLB asset'i. 50-ajan araştırma paneli sonrası
**per-leaf 8-vert ovate mesh** stratejisi kullanır (mobile cluster card yaklaşımı
texture olmadan silüet veremediği için terkedildi).

## Regenerate

```bash
blender --background --python elma_agaci_generator.py -- \
    --seed 42 --render --export-glb --round 22
```

Çıktılar:
- `elma_agaci.blend` — Blender sahne
- `elma_agaci.glb` — Godot import için GLB (vertex colors + embedded leaf texture)
- `preview_round_22_*.png` — 4 açı render (three_quarter / front / side / close)
- `textures/leaf/leaf_placeholder.png` — Procedural baked leaf alpha (512×512)

Flag'ler:
- `--seed N` — RNG seed (default 42)
- `--render` — 4 açı preview render üret
- `--export-glb` — GLB export (default kapalı)
- `--no-bake` — Procedural leaf texture bake'i atla (varolan kullan)
- `--no-save` — .blend save'i atla (test için)
- `--round N` — preview dosya adı suffix'i

## Mimari

| Component | Tri | Materyal |
|---|---|---|
| Wood (trunk + scaffold + secondary + twig + spur) | ~6500 | `M_Bark` |
| Leaves (~1800 ovate mesh × 4 tri) | ~7100 | `M_Leaf` |
| Apples (~30 adet × ~76 tri) + stems | ~2300 | `M_Apple`, `M_AppleStem` |
| **TOTAL** | **~15.9k** | 4 material slot |

**Leaf system:**
- 6 vertex per leaf (1 base + 2 mid + 2 upper + 1 tip)
- 4 triangle topology
- V-fold (midrib adaxial convexity) + tip droop baked into geometry
- Phyllotaxis: long shoots = 137.5° spiral (9 yaprak/twig), spurs = decussate opposite pairs (6 yaprak/spur)
- Hollow-core: 0.55m'den derin canopy bölgelerinde %35 yaprak atlanır (LAI gradient)
- Vertex color: RGB = leaf tint (Z + radius driven, 3 palette tier blend), A = AO darkening

**Materyal:**
- Tek `M_Leaf` material + per-vertex color (RGB tint × texture × AO)
- `ALPHA_CLIP` (Godot import: ALPHA_SCISSOR 0.5)
- Backface culling AÇIK (mesh ovate olduğundan tek-yön yeterli)
- Bake edilmiş 512×512 placeholder texture GLB'ye gömülü

## Texture Swap (Kullanıcı Photo İle)

Kullanıcı gerçek apple leaf texture'i sağlarsa:

1. Yeni PNG'yi `textures/leaf/leaf_placeholder.png` üzerine yaz (aynı dosya adı + 512×512 RGBA + alpha kanalı)
2. Generator'ı `--no-bake` ile çalıştır → bake'i atlar, varolan PNG'yi kullanır
3. VEYA Godot tarafında material override ile runtime swap

## Parametreler (Tweaking)

`elma_agaci_generator.py` CONFIG bölümü — önemli paramateler:

```python
TOTAL_HEIGHT = 4.2               # ağaç yüksekliği (m)
LEAF_LENGTH = 0.105              # yaprak uzunluğu (m) — 75mm real, 105mm stylized
LEAF_WIDTH_RATIO = 0.62          # genişlik/uzunluk
LEAVES_PER_TWIG = 9              # twig başına yaprak
LEAVES_PER_SPUR = 6              # spur başına yaprak (opposite pairs)
LEAF_HOLLOW_SKIP_PROB = 0.35     # interior leaf seyreltme oranı
APPLE_COUNT_TARGET = 30          # toplam meyve hedefi
APPLE_DIAMETER = 0.100           # meyve çapı (m)
APPLE_CLUSTER_WEIGHTS = [0.15, 0.50, 0.25, 0.08, 0.02]  # 1-5 elmalı küme oranları
```

## Bağımlılıklar

- Blender 4.0+ (test edildi: 4.0.2)
- numpy (GLB exporter için — `python3.12 -m pip install --break-system-packages numpy`)
