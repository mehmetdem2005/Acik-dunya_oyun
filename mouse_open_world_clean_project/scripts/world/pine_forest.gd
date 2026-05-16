@tool
extends Node3D
class_name PineForest

# Bir alana doğal dağılımlı çam ağaçları yerleştirir.
# Her ağaç boyut/dönüş/tohum varyasyonuyla benzersiz olur (klon hissi yok).
# Zemine RayCast ile oturtur; çarpışma gövdesi opsiyoneldir.

@export_group("Dağılım")
@export var tree_count: int = 40
@export var area_radius: float = 45.0
@export var min_spacing: float = 3.0
@export var forest_seed: int = 1337

@export_group("Ağaç Varyasyonu")
@export var height_min: float = 4.5
@export var height_max: float = 9.0
@export var ground_y: float = 0.0
@export var raycast_to_ground: bool = true
@export var ray_collision_mask: int = 1
@export var generate_collision: bool = true

@export_group("Yeniden Üret")
@export var rebuild_now: bool = false : set = _set_rebuild

var _rng := RandomNumberGenerator.new()
var _placed: Array[Vector2] = []

func _set_rebuild(v: bool) -> void:
	if v:
		rebuild()

func _ready() -> void:
	if Engine.is_editor_hint():
		rebuild()
		return
	if raycast_to_ground:
		# Terrain chunk'ları ilk karelerde yüklenir; zemine doğru otursun diye bekle.
		await get_tree().process_frame
		await get_tree().process_frame
		await get_tree().physics_frame
	rebuild()

func rebuild() -> void:
	for c in get_children():
		c.queue_free()
	_placed.clear()
	_rng.seed = forest_seed

	var pine_script := load("res://scripts/world/pine_tree.gd")
	if pine_script == null:
		push_error("pine_tree.gd bulunamadı.")
		return

	var attempts := 0
	var made := 0
	while made < tree_count and attempts < tree_count * 25:
		attempts += 1
		var pos2 := _sample_position()
		if not _is_far_enough(pos2):
			continue
		_placed.append(pos2)
		made += 1
		_spawn_tree(pine_script, pos2, made)

func _sample_position() -> Vector2:
	# Merkeze yakın seyrek, kenarlara doğru kümeli doğal görünüm.
	var ang := _rng.randf() * TAU
	var r := sqrt(_rng.randf()) * area_radius
	return Vector2(cos(ang) * r, sin(ang) * r)

func _is_far_enough(p: Vector2) -> bool:
	for q in _placed:
		if p.distance_to(q) < min_spacing:
			return false
	return true

func _spawn_tree(pine_script: Script, pos2: Vector2, idx: int) -> void:
	var tree := Node3D.new()
	tree.set_script(pine_script)
	tree.name = "Pine_%03d" % idx

	var h: float = _rng.randf_range(height_min, height_max)
	tree.set("total_height", h)
	tree.set("trunk_radius", h * _rng.randf_range(0.022, 0.030))
	tree.set("foliage_layers", _rng.randi_range(7, 11))
	tree.set("crown_max_radius", h * _rng.randf_range(0.28, 0.38))
	tree.set("seed", _rng.randi())
	tree.set("generate_collision", generate_collision)
	# İğne tonunda hafif tür/mevsim varyasyonu.
	var tint: float = _rng.randf_range(-0.03, 0.05)
	tree.set("needle_base", Color(0.06 + tint, 0.19 + tint, 0.09 + tint * 0.5))
	tree.set("needle_tip", Color(0.20 + tint, 0.39 + tint, 0.17 + tint * 0.5))

	var y := ground_y
	if raycast_to_ground and not Engine.is_editor_hint():
		y = _ground_height(pos2)

	tree.position = Vector3(pos2.x, y, pos2.y)
	tree.rotation.y = _rng.randf() * TAU
	var s: float = _rng.randf_range(0.95, 1.05)
	tree.scale = Vector3(s, s, s)
	add_child(tree)

func _ground_height(pos2: Vector2) -> float:
	var space := get_world_3d().direct_space_state
	if space == null:
		return ground_y
	var from := Vector3(pos2.x, 500.0, pos2.y)
	var to := Vector3(pos2.x, -500.0, pos2.y)
	var q := PhysicsRayQueryParameters3D.create(from, to)
	q.collision_mask = ray_collision_mask
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return ground_y
	return hit.position.y
