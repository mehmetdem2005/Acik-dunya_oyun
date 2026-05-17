extends Node3D
class_name Forest

# Diske BAKE EDILMIS cam varyantlarini (res://forest_data/pine_v*.scn)
# yukleyip dagitir. Mesh verisi .scn dosyalarinda DISKTE durur; bu sahne
# yalniz REFERANS verir + transform uretir (sahneye gomulu mesh YOK).
# Varyantlar paylasilir -> 100 agac ~8 mesh bellegi (klon-instans).

@export var tree_count: int = 100
@export var area_radius: float = 60.0
@export var min_spacing: float = 2.5
@export var forest_seed: int = 20260517
@export var data_dir: String = "res://forest_data"

var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	_build()

func _build() -> void:
	for c in get_children():
		c.queue_free()
	_rng.seed = forest_seed

	var variants: Array[PackedScene] = []
	var i := 0
	while true:
		var p := "%s/pine_v%d.scn" % [data_dir, i]
		if not ResourceLoader.exists(p):
			break
		var ps: PackedScene = load(p)
		if ps != null:
			variants.append(ps)
		i += 1
	if variants.is_empty():
		push_warning("Forest: %s altinda bake edilmis varyant yok (_forest_bake.gd calistir)." % data_dir)
		return

	var placed: Array[Vector2] = []
	var made := 0
	var attempts := 0
	while made < tree_count and attempts < tree_count * 30:
		attempts += 1
		var ang := _rng.randf() * TAU
		var rad := sqrt(_rng.randf()) * area_radius
		var p2 := Vector2(cos(ang) * rad, sin(ang) * rad)
		var ok := true
		for q in placed:
			if p2.distance_to(q) < min_spacing:
				ok = false
				break
		if not ok:
			continue
		placed.append(p2)
		var inst: Node3D = variants[made % variants.size()].instantiate()
		inst.position = Vector3(p2.x, 0.0, p2.y)
		inst.rotation.y = _rng.randf() * TAU
		var s := _rng.randf_range(0.8, 1.25)
		inst.scale = Vector3(s, s, s)
		add_child(inst)
		made += 1
