# Memory Directory

Bu klasör runtime'da skill tarafından doldurulur. İçerik:

- `run_log.jsonl` — her yaratık üretim run'ının özeti (self-critique için)
- `decisions.jsonl` — her kullanıcı kararı / cevabı log'u
- `cli_signature.json` — Claude CLI flag detection cache (vision_call.py kullanır)
- `runs/<timestamp>/` — her run'ın kendi klasörü:
  - `CreatureSpec.json` — anatomik araştırma + bütçe spec'i
  - `refs/` — referans görseller (web research + kullanıcı yüklemeleri)
  - `renders/iter_<n>/` — her iterasyonun eval render'ları
  - `vision_results/` — vision Claude çıktıları
  - `blender_scenes/` — ara .blend dosyaları (her büyük modül sonu)
  - `outputs/` — final teslimat (.glb, LOD'lar, materyal preview)

Silmek istersen tüm `memory/` klasörünü silebilirsin, skill sıfırdan başlar
(ama tüm öğrenmiş şeyler de kaybolur).
