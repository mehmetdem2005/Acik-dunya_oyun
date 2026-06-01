extends Node3D
class_name MouseSpawner

# Haritaya yoğun NPC fare yerleştirir. Yükleme tıkanmasını önlemek için
# spawn'lar birkaç kareye yayılır. swimmer_ratio kadarı nehri geçebilir.

@export var count: int = 50
@export var swimmer_ratio: float = 0.32
@export var npc_scale: float = 0.9

var terrain: Terrain

func build() -> void:
	if terrain == null or not terrain.built:
		return
	for i in count:
		var p := terrain.get_random_land_point(15.0)
		if p.y <= terrain.water_surface_y + 0.3:
			continue
		var npc := MouseNPC.new()
		npc.terrain = terrain
		add_child(npc)
		npc.global_position = p
		npc.setup(terrain, randf() < swimmer_ratio, npc_scale * randf_range(0.85, 1.12))
		if (i % 8) == 0:
			await get_tree().process_frame
	print("[Spawner] %d NPC fare yerleştirildi" % get_child_count())
