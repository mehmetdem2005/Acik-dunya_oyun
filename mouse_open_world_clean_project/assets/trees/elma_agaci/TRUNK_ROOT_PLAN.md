# Gövde + Kök Dev Mimari Plan (Round 33)

## Bağlam
3 uzman ajan (dendrolog + kök biyoloğu + AAA technical artist) paralel araştırma yaptı, **güçlü konsensüs** çıktı. Mevcut sorun: trunk fazla temiz/CGI, kökler ya yok ya "spike". Çözüm geometri-odaklı (bark texture henüz yok → ASSETS_NEEDED priority 2).

## KONSENSÜS — En kritik içgörü (3 ajan da aynı)
**Trunk base = loblu yıldız ring.** Her lob bir buttress crest. Lob, dışarı+aşağı **loft** edilerek sürekli yüzey köküne dönüşür — trunk derisiyle AYNI yüzey, paylaşılan/çakışan vertex, **dikiş yok**. Önceki "ayrı silindir spike" yaklaşımı kavramsal olarak yanlıştı.

## Botanik Spec (sayılar)

### Trunk (Dendrolog)
- Cross-section: dairesel DEĞİL — 3-5 lob (4 tipik), flute derinlik base'de %8-15 radius, fork'a kadar %30-50 azalarak sürer
- Axial twist: 10-25° (loblar yukarı spiral)
- Taper base→fork: 1.3-1.6:1 (stout, az konik)
- **Basal sweep/lean: 5-20° off vertical, S/pistol-butt** — "en büyük CGI tell düz eksen"
- Fork height 0.8-1.5m, üstte central leader YOK (scaffold'lara bölünür)
- Bark relief: scaly plates + dikey fissür (3-8mm) → **normal map işi, geometri değil**
- Healed branch scars 4-8 (dominant özellik), burls 1-3, canker 1-3

### Root crown (Kök biyoloğu)
- 6-7 major surface root (5-8 aralık)
- **D-shaped/flat-top cross-section** (width:height 2:1-3:1), submerge'e doğru yuvarlaklaşır
- Junction width 0.18-0.30m → submerge width 0.06-0.12m
- Surface travel 0.6-1.5m
- Profil: **flat shoulder (5-10°) → convex dip (25-35°)** — arch/knuckle DEĞİL
- Azimuth UNEVEN/clustered (2-3 dominant, eşit aralık değil)
- **KRİTİK: kök trunk flare derisinin devamı, aynı yüzey, dikiş yok**
- Kök trunk'tan smoother, üstü mossy
- 1-3 major kök yüzeyde bir kez çatallanır
- Root crown spread 2.5-4.0m

### AAA Teknik (Technical artist)
- Base ring 16-20 seg (lerp 18→8 yukarı)
- 2-octave radial displacement (oct1 0.06r @3cyc, oct2 0.025r @9cyc)
- **Vertical ridge phase: noise(angle*k + z*kz)** → ridge'ler yukarı çıkar, sıfır tri maliyeti
- Cross-section: low-freq açısal distortion (1-2 cycle, %8-12), z-rotating phase → ovalize + drift
- Root continuity: base ring = STAR, lob vertex cluster'larını radyal+aşağı çek, root taper'a bridge — paylaşılan vertex
- Vertex AO bake → root junction + base crevice koyulaştır (ucuz, büyük kazanç)
- Ground blend/skirt → "düzleme konmuş" hissini öldürür

## Öncelik Sırası (ROI)
3 ajan ortak öncelik:
1. **Lofted continuous roots + cross-section irregularity** (en büyük CGI-tell killer, ~0 tri, mevcut seam fix)
2. Bark albedo texture + cylindrical UV + normal map (en büyük perceived-realism, AMA asset gerekiyor → defer)
3. Vertex AO bake (ucuz multiplier)

## Implementation Plan (Round 33)

### Faz A — Trunk cross-section gerçekçiliği
1. `trunk_curve` radial_mod overhaul:
   - **Lobed star**: N_TRUNK_LOBES=4-5, sharp crests, fork'a kadar fade (base %100, fork %35)
   - **z-rotating phase**: loblar yukarı spiral (axial twist ~18°)
   - **2-octave noise**: low-freq lumps + high-freq sub-ridges
   - **Vertical ridge phase**: noise(angle*k + z*kz) → dikey ridge'ler
2. **Basal sweep**: trunk bezier'e pistol-butt S-curve (lean 12°, base offset)
3. Base radial segs 12→16

### Faz B — Lofted continuous surface roots (ANA İŞ)
1. Yeni `_build_lofted_roots()`:
   - 6 root, azimuth = trunk buttress lob azimuth'ları (lob→root hizalama)
   - Uneven azimuth (2-3 dominant cluster + jitter)
   - **D-section ring** (yeni `_d_section_ring`): width:height 2.5:1, flat top
   - Profil: shoulder (5-10° pitch, 0.3m) → dip (28° pitch, batış)
   - Junction width 0.24m → submerge 0.08m, gradual taper
   - İlk ring trunk lob crest'ine gömülü (overlap → seam gizle)
   - Son ring z<0 (toprağa dal)
   - 1-2 root yüzeyde çatallanır
2. Köklere tier=0 + wood_kind=1 (smoother vcolor, no crack, mossy base)

### Faz C — Vertex AO + ground contact
1. `_apply_bark_vcolor`'a AO pass:
   - z<0.3m → koyulaştır (ground contact occlusion)
   - root junction çevresi → koyu (crevice AO)
   - Procedural: base + valley darkening
2. Ground blend: kök tipleri z<0'a dalar (intersection gömülü)

### Faz D — Render + verify + commit
- trunk_base close-up + 6-view contact sheet
- Tri budget kontrol (~21-23k)
- GLB/FBX/LOD export

## Bark Texture (defer notu)
Normal map + albedo "en büyük perceived realism jump" ama **asset gerekiyor**. `pine_ultra_mobile/textures/bark/` pipeline'ı mevcut (kanıt: repo zaten PBR taşıyabiliyor). Kullanıcı `ASSETS_NEEDED.md` priority 2'deki bark dosyalarını verirse: cylindrical UV (U=angle/2π, V=cumulative arc) + normal map eklenir. Bu round geometri-only.

## Değişecek
`elma_agaci_generator.py`:
- `trunk_curve` (lobed + sweep + multi-octave + z-phase)
- Yeni `_d_section_ring`, `_build_lofted_roots`
- `_apply_bark_vcolor` (AO pass)
- Config: N_TRUNK_LOBES, TRUNK_TWIST_DEG, sweep params, D-section root params

## Riskler
- Lofted root seam: ilk ring trunk lob'a tam oturmazsa gap → overlap + embed ile mitigate
- Tri patlama: D-section root 4 ring × 6 seg × 6 root ≈ 800 tri, kontrollü
- Cross-section twist normal'leri bozabilir → normal_update sonda
