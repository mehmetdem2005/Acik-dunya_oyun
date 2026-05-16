extends Resource
class_name TerrainChunkManifest

@export var version: int = 1

@export var terrain_width: float = 420.0
@export var terrain_depth: float = 420.0
@export var max_height: float = 70.0
@export var height_offset: float = 0.0

@export var sample_step: int = 24
@export var chunk_quads_per_side: int = 32

@export var cell_size_x: float = 1.0
@export var cell_size_z: float = 1.0

@export var material_path: String = ""
@export var chunks: Array[Dictionary] = []

func clear_chunks() -> void:
	chunks.clear()

func add_chunk(data: Dictionary) -> void:
	chunks.append(data)

func get_chunk_count() -> int:
	return chunks.size()

func get_chunk(index: int) -> Dictionary:
	if index < 0 or index >= chunks.size():
		return {}
	return chunks[index]

func get_chunk_by_id(chunk_id: String) -> Dictionary:
	for i: int in range(chunks.size()):
		var data: Dictionary = chunks[i]
		if String(data.get("id", "")) == chunk_id:
			return data
	return {}
