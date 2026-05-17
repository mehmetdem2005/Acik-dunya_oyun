extends Node3D
class_name Forest

# Ayri orman sahnesi: tek GLB modelini (res://scenes/world/pine_tree.glb)
# N kez dagitir. Model dosyasi DISKTE; sahne yalniz referans + transform
# uretir (sahneye gomulu mesh YOK, gitignore'lu veriye bagimli degil).
# Ayni PackedScene tum instanslarda paylasilir -> dusuk bellek.

@export var tree_count: int = 100
@export var area_radius: float = 60.0
@export var min_spacing: float = 3.0
@export var forest_seed: int = 20260517
@export var model_path: String = "res://scenes/world/pine_tree.glb"

var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	_build()

func _build() -> void:
	for c in get_children():
		c.queue_free()
	if not ResourceLoader.exists(model_path):
		push_warning("Forest: model yok: " + model_path)
		return
	var model: PackedScene = load(model_path)
	if model == null:
		push_warning("Forest: model yuklenemedi: " + model_path)
		return
	_rng.seed = forest_seed
	var placed: Array[Vector2] = []
	var made := 0
	var attempts := 0
	while made < tree_count and attempts < tree_count * 30:
		attempts += 1
		var ang: float = _rng.randf() * TAU
		var rad: float = sqrt(_rng.randf()) * area_radius
		var p2 := Vector2(cos(ang) * rad, sin(ang) * rad)
		var ok := true
		for q in placed:
			if p2.distance_to(q) < min_spacing:
				ok = false
				break
		if not ok:
			continue
		placed.append(p2)
		var inst: Node3D = model.instantiate()
		inst.position = Vector3(p2.x, 0.0, p2.y)
		inst.rotation.y = _rng.randf() * TAU
		var s: float = _rng.randf_range(0.85, 1.25)
		inst.scale = Vector3(s, s, s)
		add_child(inst)
		made += 1
