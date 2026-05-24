# GPU OTURUMU RUNBOOK — Foto-real kurt (TripoSG) + tam oyun pipeline

> Bu dosya, **GPU'lu (CUDA, >=8GB VRAM) bir ortamda** kurt pipeline'ina kaldigi
> yerden devam etmek icindir. CPU'lu ortamda TripoSG CALISMAZ (diso CUDA ister).
> Repo temiz klonlanir; referans fotolar `refs/` altinda commit'li.

## Durum (CPU oturumunda yapilanlar)
- Referanslar: `refs/wolf_side.png` (yan, en iyi), `wolf_front.png`, `wolf_back.png`
- CPU'da TripoSR denendi → lumpy/web'li (model zayif). TripoSG GPU ister → burada calismadi.
- Rig (60 kemik), skinning (proximity), 4 animasyon (walk/run/crawl/attack + kuyruk),
  export script'leri HAZIR ve test edildi (asagida).

## ADIM 0 — Kurulum
```bash
bash agent_io/gpu_setup.sh      # CUDA torch + TripoSG + diso + Blender + GL libs
```

## ADIM 1 — TripoSG ile foto-real mesh (GPU)
```bash
bash agent_io/gpu_run.sh        # refs/wolf_side.png -> blender_scenes/triposg_wolf.glb + onizleme
```
- Tris'i Tripo belirler (--faces verilmedi). Daha sik istersen gpu_run.sh icine --faces 80000.
- NOT: TripoSG sadece SEKIL uretir (texture yok). Texture icin: (a) referans fotoyu
  projeksiyonla bake et, ya da (b) Tripo texture modeli. Vertex-renk degil, UV+texture hedefle.
- NOT: `ai_import_textured.py` .obj bekler; TripoSG .glb verir → import'u
  `bpy.ops.import_scene.gltf` ile yap (gltf), auto-orient bloklari ayni kalsin.

## ADIM 2 — Rig (iskeleti mesh'e oturt + skin)
- Iskelet blueprint: `SkeletonBlueprint.json` (60 kemik, IK, twist). Uret/duzelt:
  `python3 agent_io/gen_skeleton_blueprint.py SkeletonBlueprint.json`
  - ÖNEMLI DUZELTME: on bacak dirsegi ARKAYA bakmali (gercek kurt). `leg()` icinde
    upper_arm tail y'sini omuzdan KUCUK yap (orn 0.255), forearm ileri. IK pole'lari
    kaldir (pole=None) — bend-plane'e guven.
- Iskeleti TripoSG mesh'ine olcek/konumla (mesh body_length'e gore skeleton scale).
- Skin: `blender --background <mesh+arm>.blend --python agent_io/skin_proximity.py -- <out>.blend 0.06`
  (heat-weight degil; mesafe-tabanli, orphan=0, robust).

## ADIM 3 — Animasyon (kuyruk dahil)
```bash
blender --background skinned.blend --python agent_io/wolf_animate.py -- animated.blend 30
```
Klipler: walk / run / crawl / attack (cromel→arka-it→sicra→on-pati-vur→toparla) + kuyruk dalgasi.
- Jaw/head yon DUZELTMESI: jaw acmak NEGATIF X; head/neck asagi NEGATIF X (wolf_animate'te kontrol et).

## ADIM 4 — Export (.glb + LOD + Godot .tres)
```bash
blender --background animated.blend --python ../../scripts/production/build_export.py -- \
  --budget BudgetSpec.json --anim-manifest animated.animation_manifest.json \
  --output-dir final --creature-id kurt_001
```

## ADIM 5 — Dogrulama + teslim
- `final/kurt_001.glb` (skin+anim+texture) + LOD1/LOD2 + ExportManifest.json
- Kullaniciya SendUserFile ile gonder; mouse_open_world Godot projesine entegre et.

## Hizli baslangic (GPU oturumunda tek cumle)
"kurt pipeline'ina GPU'da devam et: gpu_setup.sh + gpu_run.sh calistir, sonra runbook ADIM 2-5"
