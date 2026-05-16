AÇIK DÜNYA FARE SİMÜLASYONU - TEMİZ CHUNK PROJE

Bu proje eski world sahnesi gibi editörde dev terrain, player ve UI yükleyip telefonu çökertmesin diye ayrıldı.
World sahnesi hafiftir. Player, MobileUI ve terrain chunk'ları sadece oyun çalışınca yüklenir.

============================================================
1) SENİN EKLEMEN GEREKEN DOSYALAR
============================================================

A) Heightmap
Koyulacak klasör:
res://assets/terrain/heightmaps/

Önerilen dosya adı:
terrain_height.png
veya
heightmap.png

B) Zemin texture dosyaları
Koyulacak klasör:
res://assets/terrain/ground_textures/

Önerilen dosya adları:
forest_ground_diff_1k.jpg
forest_ground_nor_gl_1k.jpg
forest_ground_rough_1k.jpg
forest_ground_ao_1k.jpg

Not:
Godot için normal dosyan OpenGL normal olmalı. Dosyada nor_gl / normal_gl geçerse iyi.
DirectX normal kullanırsan ışık ters görünebilir. Çünkü normal mapler bile kavga ediyor, müthiş türümüz.

C) Fare modeli
Koyulacak klasör:
res://assets/animals/mouse/

Beklenen dosya adı:
mouse.glb

Farklı ad kullanırsan:
scenes/player/player.tscn aç → Player node'u seç → model_path değerini düzelt.

============================================================
2) TERRAIN ÜRETME
============================================================

1. Godot'ta şu sahneyi aç:
res://scenes/terrain/terrain_bake.tscn

2. TerrainBake node'unu seç.

3. Inspector'da en az şunu bağla:
Heightmap Texture = heightmap dosyan

4. Zemin texture'lar otomatik bulunmazsa elle bağla:
Diffuse Texture = diff/albedo dosyan
Normal Texture = nor_gl/normal_gl dosyan
Roughness Texture = roughness dosyan
AO Texture = ao dosyan

5. Güvenli mobil ayarlar:
Sample Step = 24
Chunk Quads Per Side = 32
Terrain Width = 420
Terrain Depth = 420
Max Height = 70
UV Tiling = 18

6. Tek tuşa bas:
TEK_TUS_CHUNK_TERRAIN_BAKE

Bu dosyalar oluşmalı:
res://terrains/generated_chunks/terrain_manifest.tres
res://terrains/generated_chunks/terrain_material.res
res://terrains/generated_chunks/chunks/chunk_x0_z0_mesh.res
res://terrains/generated_chunks/chunks/chunk_x0_z0_collision.res
...

============================================================
3) OYUNU ÇALIŞTIRMA
============================================================

Ana sahne hazır:
res://scenes/world/world.tscn

Bu sahnede bilinçli olarak şunlar editörde yoktur:
- Player
- MobileUI
- Chunk meshleri

Bunlar sadece Play tuşuna basınca RuntimeSpawner tarafından eklenir.
Bu normaldir. Editörü hayatta tutmak için yapıldı. Telefon zaten yeterince acı çekiyor.

============================================================
4) ÖNEMLİ UYARI
============================================================

Eski world.tscn dosyanı bu projeye koyma.
Eski bloated world, embedded terrain mesh/collision yüzünden tekrar çökertir.

World sahnesinin doğru yapısı:
World
├── TerrainRuntime
│   └── LoadedChunks
├── RuntimeSpawner
├── DirectionalLight3D
└── WorldEnvironment

Player ve MobileUI sadece runtime'da spawn olur.

============================================================
5) MOBİL EDITÖR ÇÖKMEYE DEVAM EDERSE
============================================================

Şunları kontrol et:
- terrain_bake.tscn açıkken PreviewChunks çok kalabalık olmasın.
- World sahnesinde Player veya MobileUI elle ekli olmasın.
- TerrainRuntime scriptinde @tool yoktur, bunu bozma.
- Eski mobile_ui_auto.gd kullanma.
- Eski terrain_root.gd / terrain_root0.gd bu projede kullanılmıyor.

============================================================
5.5) GERÇEKÇİ ÇAM AĞACI SAHNESİ
============================================================

Gösterim sahnesi (tek başına çalışır, oynak kamera + gökyüzü + sis):
res://scenes/world/pine_tree_scene.tscn
Bunu açıp Play (F6) deyince çam ormanını dönen kamerayla görürsün.

Tek ağaç (başka sahneye sürükle-bırak):
res://scenes/world/pine_tree.tscn

Ana oyun dünyasına da otomatik orman eklendi:
world.tscn -> PineForest node'u. Inspector'dan tree_count, area_radius,
forest_seed, height_min/max gibi değerleri değiştirip yeniden üretebilirsin.

Ağaçlar prosedürel üretilir (model dosyası gerekmez):
- Konik, hafif eğri gövde + kabuk rengi
- Aşağı sarkan, üst üste binen iğne yaprak katmanları
- Rüzgarda salınan yaprak shader'ı: res://shaders/pine_wind.gdshader
- Her ağaç farklı tohum/boy/dönüş -> klon görünmez
- Gövdede opsiyonel silindir çarpışma (generate_collision)

Mobil performans notu: tree_count ve foliage_layers düşük tut.
Telefonda 25-35 ağaç güvenli. PC'de 60+ rahat.

Zemine oturma: PineForest raycast_to_ground açıkken terrain chunk
collision'ına (layer 1) ışın atar. Terrain yoksa ground_y'ye düşer.

============================================================
6) DOSYA YAPISI
============================================================

scripts/terrain/terrain_chunk_manifest.gd
scripts/terrain/terrain_chunk_baker.gd
scripts/terrain/terrain_runtime_loader.gd
scripts/world/world_runtime_spawner.gd
scripts/world/pine_tree.gd
scripts/world/pine_forest.gd
scripts/world/showcase_camera.gd
scripts/player/player_controller.gd
scripts/ui/mobile_ui.gd

shaders/pine_wind.gdshader

scenes/terrain/terrain_bake.tscn
scenes/player/player.tscn
scenes/world/world.tscn
scenes/world/pine_tree.tscn
scenes/world/pine_tree_scene.tscn
