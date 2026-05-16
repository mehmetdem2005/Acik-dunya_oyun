extends Node3D

# Runtime-only chunk loader. @tool yok. Editörde çalışmaz, World sahnesini hafif tutar.

@export_group("Manifest")
@export var manifest_path: String = "res://terrains/generated_chunks/terrain_manifest.tres"

@export_group("Player")
@export var player_path: NodePath = NodePath("../Player")

@export_group("Chunk Loading")
@export_range(0, 6, 1) var load_radius_chunks: int = 2
@export_range(1, 8, 1) var unload_radius_chunks: int = 3
@export var update_interval: float = 0.35
@export var collision_enabled_runtime: bool = true
@export_flags_3d_physics var terrain_collision_layer: int = 1
@export_flags_3d_physics var terrain_collision_mask: int = 1

@export_group("Fog Runtime")
@export var enable_fog_runtime: bool = true
@export var create_world_environment_if_missing: bool = true
@export var world_environment_path: NodePath = NodePath("../WorldEnvironment")
@export var fog_color: Color = Color(0.58, 0.62, 0.66, 1.0)
@export_range(0.0, 1.0, 0.001) var fog_density: float = 0.025
@export_range(0.0, 1.0, 0.001) var fog_aerial_perspective: float = 0.20
@export var enable_volumetric_fog: bool = false
@export_range(0.0, 1.0, 0.001) var volumetric_fog_density: float = 0.015

var _manifest: TerrainChunkManifest
var _loaded_root: Node3D
var _player: Node3D
var _world_environment: WorldEnvironment
var _loaded_chunks: Dictionary = {}
var _update_timer: float = 0.0

func _ready() -> void:
	_ensure_loaded_root()
	_load_manifest()

	if enable_fog_runtime:
		_setup_fog_environment()

	await get_tree().process_frame
	_update_loaded_chunks(true)

func _process(delta: float) -> void:
	_update_timer -= delta
	if _update_timer <= 0.0:
		_update_timer = update_interval
		_update_loaded_chunks(false)

func _ensure_loaded_root() -> void:
	_loaded_root = get_node_or_null("LoadedChunks") as Node3D
	if _loaded_root == null:
		_loaded_root = Node3D.new()
		_loaded_root.name = "LoadedChunks"
		add_child(_loaded_root)

func _load_manifest() -> bool:
	if _manifest != null:
		return true
	if not ResourceLoader.exists(manifest_path):
		push_warning("Terrain manifest bulunamadı: " + manifest_path)
		return false
	_manifest = ResourceLoader.load(manifest_path, "", ResourceLoader.CACHE_MODE_REPLACE) as TerrainChunkManifest
	if _manifest == null:
		push_warning("Terrain manifest yüklenemedi.")
		return false
	return true

func _get_player() -> Node3D:
	if _player != null and is_instance_valid(_player):
		return _player
	_player = get_node_or_null(player_path) as Node3D
	return _player

func _update_loaded_chunks(force: bool) -> void:
	if not _load_manifest():
		return
	var player: Node3D = _get_player()
	if player == null:
		return
	var player_pos: Vector3 = player.global_position
	var wanted_ids: Dictionary = _calculate_wanted_chunks(player_pos)
	for chunk_id: String in wanted_ids.keys():
		if not _loaded_chunks.has(chunk_id):
			_load_chunk(wanted_ids[chunk_id])
	_unload_far_chunks(player_pos)
	if force:
		print("İlk terrain chunk runtime yüklemesi tamamlandı.")

func _calculate_wanted_chunks(player_pos: Vector3) -> Dictionary:
	var result: Dictionary = {}
	if _manifest == null:
		return result
	var best_data: Dictionary = _find_nearest_chunk(player_pos)
	if best_data.is_empty():
		return result
	var center_x: int = int(best_data.get("x", 0))
	var center_z: int = int(best_data.get("z", 0))
	for data: Dictionary in _manifest.chunks:
		var cx: int = int(data.get("x", 0))
		var cz: int = int(data.get("z", 0))
		var dx: int = abs(cx - center_x)
		var dz: int = abs(cz - center_z)
		if dx <= load_radius_chunks and dz <= load_radius_chunks:
			var chunk_id: String = String(data.get("id", ""))
			result[chunk_id] = data
	return result

func _find_nearest_chunk(world_pos: Vector3) -> Dictionary:
	var best: Dictionary = {}
	var best_dist_sq: float = INF
	if _manifest == null:
		return best
	for data: Dictionary in _manifest.chunks:
		var center: Vector3 = data.get("center", Vector3.ZERO)
		var dist_sq: float = Vector2(world_pos.x, world_pos.z).distance_squared_to(Vector2(center.x, center.z))
		if dist_sq < best_dist_sq:
			best_dist_sq = dist_sq
			best = data
	return best

func _load_chunk(data: Dictionary) -> void:
	_ensure_loaded_root()
	var chunk_id: String = String(data.get("id", ""))
	if chunk_id == "" or _loaded_chunks.has(chunk_id):
		return
	var mesh_path: String = String(data.get("mesh_path", ""))
	var collision_path: String = String(data.get("collision_path", ""))
	if not ResourceLoader.exists(mesh_path):
		push_warning("Chunk mesh yok: " + mesh_path)
		return
	var mesh: ArrayMesh = ResourceLoader.load(mesh_path, "", ResourceLoader.CACHE_MODE_REPLACE) as ArrayMesh
	if mesh == null:
		return

	var chunk_root: Node3D = Node3D.new()
	chunk_root.name = chunk_id
	chunk_root.position = data.get("center", Vector3.ZERO)
	_loaded_root.add_child(chunk_root)

	var mesh_instance: MeshInstance3D = MeshInstance3D.new()
	mesh_instance.name = "Mesh"
	mesh_instance.mesh = mesh
	chunk_root.add_child(mesh_instance)

	if _manifest != null and ResourceLoader.exists(_manifest.material_path):
		var mat: Material = ResourceLoader.load(_manifest.material_path, "", ResourceLoader.CACHE_MODE_REPLACE) as Material
		if mat != null:
			mesh_instance.material_override = mat

	if collision_enabled_runtime and ResourceLoader.exists(collision_path):
		var shape: HeightMapShape3D = ResourceLoader.load(collision_path, "", ResourceLoader.CACHE_MODE_REPLACE) as HeightMapShape3D
		if shape != null:
			var body: StaticBody3D = StaticBody3D.new()
			body.name = "Body"
			body.collision_layer = terrain_collision_layer
			body.collision_mask = terrain_collision_mask
			chunk_root.add_child(body)

			var collision: CollisionShape3D = CollisionShape3D.new()
			collision.name = "CollisionShape3D"
			collision.shape = shape
			collision.scale = Vector3(float(data.get("cell_size_x", 1.0)), 1.0, float(data.get("cell_size_z", 1.0)))
			body.add_child(collision)

	_loaded_chunks[chunk_id] = chunk_root

func _unload_far_chunks(player_pos: Vector3) -> void:
	if _manifest == null:
		return
	var nearest: Dictionary = _find_nearest_chunk(player_pos)
	if nearest.is_empty():
		return
	var center_x: int = int(nearest.get("x", 0))
	var center_z: int = int(nearest.get("z", 0))
	var to_remove: Array[String] = []
	for chunk_id: String in _loaded_chunks.keys():
		var data: Dictionary = _find_chunk_data_by_id(chunk_id)
		if data.is_empty():
			to_remove.append(chunk_id)
			continue
		var cx: int = int(data.get("x", 0))
		var cz: int = int(data.get("z", 0))
		if abs(cx - center_x) > unload_radius_chunks or abs(cz - center_z) > unload_radius_chunks:
			to_remove.append(chunk_id)
	for chunk_id: String in to_remove:
		_unload_chunk(chunk_id)

func _find_chunk_data_by_id(chunk_id: String) -> Dictionary:
	if _manifest == null:
		return {}
	for data: Dictionary in _manifest.chunks:
		if String(data.get("id", "")) == chunk_id:
			return data
	return {}

func _unload_chunk(chunk_id: String) -> void:
	if not _loaded_chunks.has(chunk_id):
		return
	var node: Node = _loaded_chunks[chunk_id]
	if node != null and is_instance_valid(node):
		node.queue_free()
	_loaded_chunks.erase(chunk_id)

func _setup_fog_environment() -> void:
	_world_environment = get_node_or_null(world_environment_path) as WorldEnvironment
	if _world_environment == null and create_world_environment_if_missing:
		var parent_node: Node = get_parent()
		if parent_node != null:
			_world_environment = WorldEnvironment.new()
			_world_environment.name = "WorldEnvironment"
			parent_node.add_child(_world_environment)
	if _world_environment == null:
		return
	if _world_environment.environment == null:
		_world_environment.environment = Environment.new()
	var env: Environment = _world_environment.environment
	env.set("fog_enabled", true)
	env.set("fog_light_color", fog_color)
	env.set("fog_density", fog_density)
	env.set("fog_aerial_perspective", fog_aerial_perspective)
	env.set("volumetric_fog_enabled", enable_volumetric_fog)
	env.set("volumetric_fog_density", volumetric_fog_density)
