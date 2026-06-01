# Açık Dünya Fare Oyunu (Godot 4.6.3, Mobile)

Heightmap tabanlı bir yarımada üzerinde, rig'li bir fareyle gezdiğin açık dünya.
**Her şey kodla kurulur** — sahne dosyalarına veri gömülmez (`game.tscn` yalnızca
kök düğüm + script içerir).

## Çalıştırma
1. Godot **4.6.3** (veya 4.6.x) ile `project.godot`'u aç.
2. İlk açılışta Godot tüm asset'leri içe aktarır (EXR heightmap `Image`, fare
   GLB'leri `PackedScene` olarak). Birkaç saniye sürebilir.
3. **F5** ile çalıştır. Ana sahne: `scenes/world/game.tscn`.

## Kontroller
| Eylem | Mobil | Klavye / Gamepad |
|------|-------|------------------|
| Hareket | Sol yarı: sanal joystick | WASD / Ok tuşları / Sol analog |
| Kamera | Sağ yarı: sürükle | Fare (sol tık + sürükle) |
| Koşma | Joystick'i tam it | Shift / B |
| Zıpla | **ZIPLA** butonu | Space / A |
| Saldır | **SALDIR** butonu | J / X |

Ceviz 🌰 ve fıstık 🥜 üzerine yürüyünce toplanır (sol üst sayaç).

## Mimari (tamamı `scripts/` altında, hepsi prosedürel)
- `world/game.gd` — orkestratör: input map, ortam/ışık, arazi, serpme, oyuncu, NPC.
- `world/terrain.gd` — `yarimada_16bit.exr`'den:
  - görsel mesh (yükseklik+eğime göre vertex renkli kum/çim/kaya/kar),
  - `HeightMapShape3D` çarpışması,
  - **su tespiti**: flood-fill ile deniz / göl / nehir sınıflandırması,
  - su yüzeyi mesh'i (`shaders/water.gdshader`, mobil dostu dalgalar).
  - Sorgu API'si: `height_at`, `is_water`, `water_type_at`, `get_random_land_point`.
- `actors/mouse_visual.gd` — rig'li modeli yükler, skeletal animasyon durum makinesi.
- `actors/mouse_player.gd` — CharacterBody3D: hareket, zıplama, **yüzme** (suda
  kaldırma kuvveti + yüzme animasyonu), saldırı, takip kamerası.
- `actors/mouse_npc.gd` — NPC YZ: gezinme, su kaçınma ve **nehir geçişi**.
- `actors/spawner.gd` — yoğun NPC yerleştirme (kareye yayılır).
- `world/scatter.gd` — çam (PineTree) + elma ağacı + ceviz/fıstık serpme (MultiMesh).
- `ui/hud.gd` — dokunmatik joystick + ZIPLA/SALDIR + sayaçlar.

## NPC nehir geçişi kuralı
Yalnız **swimmer** işaretli (~%32) NPC'ler suya girebilir. Geçiş **mesafe
tabanlıdır**: karşı kıyı `MAX_CROSS_DIST` (38 m) içinde bulunamazsa geçmez →
**deniz çok geniş olduğu için asla geçilmez**, yalnız **dar nehir/koy kanalları**
geçilir. Ayrıca cooldown + rastgele istek → "her nehir kenarındaki fare geçmez".
Swimmer olmayanlar suya hiç girmez (kıyıda yön değiştirir).

## Fare rig'i (Blender 4.5 ile üretildi)
Verilen model (`housemouse.glb`) **iskeletsiz/animasyonsuz statik bir mesh**ti.
Blender'da Python ile:
- 15 kemikli quadruped armature (omurga + baş + kuyruk + 4 bacak),
- konuma dayalı özel skinning (içi dolu Tripo mesh'inde otomatik heat başarısız),
- 6 skeletal animasyon: `idle, walk, run, attack, swim, RESET`,
oluşturuldu ve iki sürüm dışa aktarıldı:
- `housemouse_rigged.glb` — yüksek poli (~72k tris), oyuncu.
- `housemouse_npc.glb` — decimate'li (~3.2k tris), NPC'ler (mobil performans).

## Ayarlanabilir (Inspector / export değişkenleri)
- `game.gd`: `world_size` (480 m), `height_scale` (60 m), `npc_count` (50),
  `player_scale`.
- `terrain.gd`: `water_level` (0.075 normalize), `grid_res` (192), `slope_limit_deg`.
- `scatter.gd`: ağaç/fındık sayıları.
- `spawner.gd`: `count`, `swimmer_ratio`.

Düşük donanımda: `npc_count`, `grid_res`, ağaç/fındık sayılarını düşür.
