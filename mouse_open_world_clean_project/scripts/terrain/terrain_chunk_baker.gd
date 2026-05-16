@tool
extends Node3D

# TerrainBake sahnesine bağlanır. Sadece bu sahnede kullan.
# World sahnesine bağlama. World hafif kalmalı, yoksa mobil editör yine ağlar.

@export_group("ONE CLICK")
@export var TEK_TUS_CHUNK_TERRAIN_BAKE: bool = false:
	set(value):
		TEK_TUS_CHUNK_TERRAIN_BAKE = false
		if value:
			call_deferred("_one_click_bake")

@export var PREVIEW_CHUNKLARI_TEMIZLE: bool = false:
	set(value):
		PREVIEW_CHUNKLARI_TEMIZLE = false
		if value:
			call_deferred("_clear_preview")

@export_group("Textures")
@export var heightmap_texture: Texture2D
@export var diffuse_texture: Texture2D
@export var normal_texture: Texture2D
@export var roughness_texture: Texture2D
@export var ao_texture: Texture2D

@export_group("Auto Texture Finder")
@export var auto_assign_missing_textures_on_bake: bool = true
@export_dir var terrain_texture_source_dir: String = "res://assets/terrain/ground_textures"
@export var search_only_terrain_texture_source_dir: bool = true
@export var allowed_texture_extensions: PackedStringArray = PackedStringArray(["png", "jpg", "jpeg", "webp", "exr", "hdr", "tga"])

@export_group("Terrain Settings")
@export_range(1, 128, 1) var sample_step: int = 24
@export_range(8, 128, 1) var chunk_quads_per_side: int = 32
@export var terrain_width: float = 420.0
@export var terrain_depth: float = 420.0
@export var max_height: float = 70.0
@export var height_offset: float = 0.0
@export var uv_tiling: float = 18.0

@export_group("Save Paths")
@export var generated_root: String = "res://terrains/generated_chunks"
@export var chunks_dir: String = "res://terrains/generated_chunks/chunks"
@export var manifest_path: String = "res://terrains/generated_chunks/terrain_manifest.tres"
@export var material_path: String = "res://terrains/generated_chunks/terrain_material.res"

@export_group("Preview")
@export var create_center_preview_after_bake: bool = true
@export_range(0, 3, 1) var preview_radius_chunks: int = 1
@export var preview_load_material: bool = true

func _one_click_bake() -> void:
	if not Engine.is_editor_hint():
		return

	print("========================================")
	print("CHUNK TERRAIN BAKE BAŞLADI")
	print("========================================")

	_clear_preview()
	_ensure_dirs()

	if auto_assign_missing_textures_on_bake:
		_auto_assign_textures()

	await get_tree().process_frame

	var manifest: TerrainChunkManifest = _bake_all_chunks()
	if manifest == null:
		push_error("Bake başarısız. Heightmap ve texture yollarını kontrol et.")
		return

	if create_center_preview_after_bake:
		_create_center_preview(manifest)

	print("========================================")
	print("CHUNK TERRAIN BAKE BİTTİ")
	print("Manifest: " + manifest_path)
	print("========================================")

func _ensure_dirs() -> void:
	_make_dir(generated_root)
	_make_dir(chunks_dir)

func _make_dir(path: String) -> void:
	var absolute_path: String = ProjectSettings.globalize_path(path)
	var err: Error = DirAccess.make_dir_recursive_absolute(absolute_path)
	if err != OK:
		push_error("Klasör oluşturulamadı: " + path)

func _auto_assign_textures() -> void:
	var roots: Array[String] = _get_texture_search_roots()

	if heightmap_texture == null:
		var height_path: String = _find_texture_with_keywords(roots, ["heightmap", "height", "displacement", "disp"], ["normal", "rough", "ao", "diffuse", "albedo", "basecolor"])
		heightmap_texture = _load_texture_or_null(height_path)
		if heightmap_texture != null:
			print("Heightmap bağlandı: " + height_path)

	if diffuse_texture == null:
		var diffuse_path: String = _find_texture_with_keywords(roots, ["diffuse", "diff", "albedo", "basecolor", "base_color"], ["normal", "rough", "height", "disp", "ao"])
		diffuse_texture = _load_texture_or_null(diffuse_path)
		if diffuse_texture != null:
			print("Diffuse bağlandı: " + diffuse_path)

	if normal_texture == null:
		var normal_path: String = _find_texture_with_keywords(roots, ["normal_gl", "normalgl", "normal_opengl", "nor_gl", "opengl", "normal"], ["rough", "height", "disp", "diffuse", "albedo", "ao", "dx", "directx"])
		normal_texture = _load_texture_or_null(normal_path)
		if normal_texture != null:
			print("NormalGL bağlandı: " + normal_path)

	if roughness_texture == null:
		var rough_path: String = _find_texture_with_keywords(roots, ["roughness", "rough"], ["normal", "height", "disp", "diffuse", "albedo", "ao"])
		roughness_texture = _load_texture_or_null(rough_path)
		if roughness_texture != null:
			print("Roughness bağlandı: " + rough_path)

	if ao_texture == null:
		var ao_path: String = _find_texture_with_keywords(roots, ["ambient_occlusion", "ambientocclusion", "occlusion", "_ao", "-ao"], ["normal", "height", "disp", "diffuse", "albedo", "rough"])
		ao_texture = _load_texture_or_null(ao_path)
		if ao_texture != null:
			print("AO bağlandı: " + ao_path)

func _get_texture_search_roots() -> Array[String]:
	var result: Array[String] = []
	if terrain_texture_source_dir.strip_edges() != "":
		result.append(terrain_texture_source_dir.strip_edges())
	if search_only_terrain_texture_source_dir:
		return result
	result.append("res://assets/terrain/ground_textures")
	result.append("res://assets/terrain")
	result.append("res://textures")
	return result

func _load_texture_or_null(path: String) -> Texture2D:
	if path == "" or not ResourceLoader.exists(path):
		return null
	var resource: Resource = ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE)
	if resource is Texture2D:
		return resource as Texture2D
	return null

func _find_texture_with_keywords(roots: Array[String], keywords: Array[String], reject_keywords: Array[String]) -> String:
	for root_path: String in roots:
		var absolute_root: String = ProjectSettings.globalize_path(root_path)
		if not DirAccess.dir_exists_absolute(absolute_root):
			continue
		var found: String = _search_texture_dir(root_path, 0, keywords, reject_keywords)
		if found != "":
			return found
	return ""

func _search_texture_dir(dir_path: String, depth: int, keywords: Array[String], reject_keywords: Array[String]) -> String:
	if depth > 6:
		return ""
	if _path_should_be_skipped(dir_path):
		return ""

	var dir: DirAccess = DirAccess.open(dir_path)
	if dir == null:
		return ""

	dir.list_dir_begin()
	var file_name: String = dir.get_next()
	while file_name != "":
		if file_name.begins_with("."):
			file_name = dir.get_next()
			continue
		var full_path: String = _join_path(dir_path, file_name)
		if dir.current_is_dir():
			if not _should_skip_search_dir(file_name):
				var found: String = _search_texture_dir(full_path, depth + 1, keywords, reject_keywords)
				if found != "":
					dir.list_dir_end()
					return found
		else:
			if _is_supported_texture_file(file_name) and _file_matches_keywords(file_name, keywords, reject_keywords):
				dir.list_dir_end()
				return full_path
		file_name = dir.get_next()
	dir.list_dir_end()
	return ""

func _path_should_be_skipped(path: String) -> bool:
	var lower_path: String = path.to_lower()
	return lower_path.contains("/animal") or lower_path.contains("/mouse") or lower_path.contains("/rat") or lower_path.contains("/player") or lower_path.contains("/character") or lower_path.contains("/model")

func _should_skip_search_dir(dir_name: String) -> bool:
	var lower_name: String = dir_name.to_lower()
	return lower_name == ".godot" or lower_name == "addons" or lower_name == "scripts" or lower_name == "scenes" or lower_name == "generated" or lower_name == "generated_chunks"

func _is_supported_texture_file(file_name: String) -> bool:
	return allowed_texture_extensions.has(file_name.to_lower().get_extension())

func _file_matches_keywords(file_name: String, keywords: Array[String], reject_keywords: Array[String]) -> bool:
	var lower_name: String = file_name.to_lower()
	for reject: String in reject_keywords:
		if reject != "" and lower_name.contains(reject):
			return false
	for keyword: String in keywords:
		if keyword != "" and lower_name.contains(keyword):
			return true
	return false

func _join_path(a: String, b: String) -> String:
	if a.ends_with("/"):
		return a + b
	return a + "/" + b

func _bake_all_chunks() -> TerrainChunkManifest:
	if heightmap_texture == null:
		push_error("Heightmap Texture atanmadı.")
		return null

	var source_image: Image = heightmap_texture.get_image()
	if source_image == null:
		push_error("Heightmap okunamadı.")
		return null

	source_image.convert(Image.FORMAT_RF)
	var sampled: Image = _downsample_heightmap(source_image, maxi(sample_step, 1))
	var grid_w: int = sampled.get_width()
	var grid_d: int = sampled.get_height()

	if grid_w < 2 or grid_d < 2:
		push_error("Heightmap çok küçük.")
		return null

	var cell_size_x: float = terrain_width / float(maxi(grid_w - 1, 1))
	var cell_size_z: float = terrain_depth / float(maxi(grid_d - 1, 1))

	var material: StandardMaterial3D = _build_material()
	ResourceSaver.save(material, material_path)

	var manifest: TerrainChunkManifest = TerrainChunkManifest.new()
	manifest.terrain_width = terrain_width
	manifest.terrain_depth = terrain_depth
	manifest.max_height = max_height
	manifest.height_offset = height_offset
	manifest.sample_step = sample_step
	manifest.chunk_quads_per_side = chunk_quads_per_side
	manifest.cell_size_x = cell_size_x
	manifest.cell_size_z = cell_size_z
	manifest.material_path = material_path
	manifest.clear_chunks()

	var total_quads_x: int = grid_w - 1
	var total_quads_z: int = grid_d - 1
	var chunk_index_z: int = 0
	var start_z: int = 0

	while start_z < total_quads_z:
		var end_z: int = mini(start_z + chunk_quads_per_side, total_quads_z)
		var chunk_index_x: int = 0
		var start_x: int = 0
		while start_x < total_quads_x:
			var end_x: int = mini(start_x + chunk_quads_per_side, total_quads_x)
			var data: Dictionary = _bake_one_chunk(sampled, start_x, end_x, start_z, end_z, chunk_index_x, chunk_index_z, cell_size_x, cell_size_z, grid_w, grid_d)
			if not data.is_empty():
				manifest.add_chunk(data)
			start_x += chunk_quads_per_side
			chunk_index_x += 1
		start_z += chunk_quads_per_side
		chunk_index_z += 1

	var manifest_err: Error = ResourceSaver.save(manifest, manifest_path)
	if manifest_err != OK:
		push_error("Manifest kaydedilemedi: " + manifest_path)
		return null
	print("Chunk sayısı: " + str(manifest.get_chunk_count()))
	return manifest

func _downsample_heightmap(source_image: Image, step: int) -> Image:
	var xs: Array[int] = []
	var zs: Array[int] = []
	var x: int = 0
	while x < source_image.get_width():
		xs.append(x)
		x += step
	if xs.size() == 0 or xs[xs.size() - 1] != source_image.get_width() - 1:
		xs.append(source_image.get_width() - 1)
	var z: int = 0
	while z < source_image.get_height():
		zs.append(z)
		z += step
	if zs.size() == 0 or zs[zs.size() - 1] != source_image.get_height() - 1:
		zs.append(source_image.get_height() - 1)
	var output: Image = Image.create_empty(xs.size(), zs.size(), false, Image.FORMAT_RF)
	for zi: int in range(zs.size()):
		for xi: int in range(xs.size()):
			var h: float = source_image.get_pixel(xs[xi], zs[zi]).r
			output.set_pixel(xi, zi, Color(h, h, h, 1.0))
	return output

func _bake_one_chunk(global_height_image: Image, start_x: int, end_x: int, start_z: int, end_z: int, chunk_x: int, chunk_z: int, cell_size_x: float, cell_size_z: float, global_grid_w: int, global_grid_d: int) -> Dictionary:
	var local_w: int = end_x - start_x + 1
	var local_d: int = end_z - start_z + 1
	if local_w < 2 or local_d < 2:
		return {}
	var chunk_image: Image = Image.create_empty(local_w, local_d, false, Image.FORMAT_RF)
	for z: int in range(local_d):
		for x: int in range(local_w):
			var h: float = global_height_image.get_pixel(start_x + x, start_z + z).r
			chunk_image.set_pixel(x, z, Color(h, h, h, 1.0))

	var chunk_id: String = "chunk_x" + str(chunk_x) + "_z" + str(chunk_z)
	var mesh: ArrayMesh = _build_chunk_mesh(chunk_image, cell_size_x, cell_size_z, start_x, start_z, global_grid_w, global_grid_d)
	var shape: HeightMapShape3D = HeightMapShape3D.new()
	shape.update_map_data_from_image(chunk_image, height_offset, height_offset + max_height)

	var mesh_path: String = chunks_dir + "/" + chunk_id + "_mesh.res"
	var collision_path: String = chunks_dir + "/" + chunk_id + "_collision.res"
	if ResourceSaver.save(mesh, mesh_path) != OK:
		return {}
	if ResourceSaver.save(shape, collision_path) != OK:
		return {}

	var center_x: float = -terrain_width * 0.5 + (float(start_x) + float(local_w - 1) * 0.5) * cell_size_x
	var center_z: float = -terrain_depth * 0.5 + (float(start_z) + float(local_d - 1) * 0.5) * cell_size_z
	return {
		"id": chunk_id,
		"x": chunk_x,
		"z": chunk_z,
		"center": Vector3(center_x, 0.0, center_z),
		"mesh_path": mesh_path,
		"collision_path": collision_path,
		"map_width": local_w,
		"map_depth": local_d,
		"cell_size_x": cell_size_x,
		"cell_size_z": cell_size_z,
		"size_x": float(local_w - 1) * cell_size_x,
		"size_z": float(local_d - 1) * cell_size_z
	}

func _build_chunk_mesh(chunk_image: Image, cell_size_x: float, cell_size_z: float, global_start_x: int, global_start_z: int, global_grid_w: int, global_grid_d: int) -> ArrayMesh:
	var width_count: int = chunk_image.get_width()
	var depth_count: int = chunk_image.get_height()
	var half_width: float = float(width_count - 1) * cell_size_x * 0.5
	var half_depth: float = float(depth_count - 1) * cell_size_z * 0.5
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for z: int in range(depth_count - 1):
		for x: int in range(width_count - 1):
			var p00: Vector3 = _point(chunk_image, x, z, cell_size_x, cell_size_z, half_width, half_depth)
			var p10: Vector3 = _point(chunk_image, x + 1, z, cell_size_x, cell_size_z, half_width, half_depth)
			var p01: Vector3 = _point(chunk_image, x, z + 1, cell_size_x, cell_size_z, half_width, half_depth)
			var p11: Vector3 = _point(chunk_image, x + 1, z + 1, cell_size_x, cell_size_z, half_width, half_depth)
			var gx0: float = float(global_start_x + x) / float(maxi(global_grid_w - 1, 1))
			var gx1: float = float(global_start_x + x + 1) / float(maxi(global_grid_w - 1, 1))
			var gz0: float = float(global_start_z + z) / float(maxi(global_grid_d - 1, 1))
			var gz1: float = float(global_start_z + z + 1) / float(maxi(global_grid_d - 1, 1))
			var uv00: Vector2 = Vector2(gx0, gz0) * uv_tiling
			var uv10: Vector2 = Vector2(gx1, gz0) * uv_tiling
			var uv01: Vector2 = Vector2(gx0, gz1) * uv_tiling
			var uv11: Vector2 = Vector2(gx1, gz1) * uv_tiling
			_add_vertex(st, p00, uv00)
			_add_vertex(st, p01, uv01)
			_add_vertex(st, p10, uv10)
			_add_vertex(st, p10, uv10)
			_add_vertex(st, p01, uv01)
			_add_vertex(st, p11, uv11)
	st.generate_normals()
	st.generate_tangents()
	return st.commit()

func _point(img: Image, x: int, z: int, cell_size_x: float, cell_size_z: float, half_width: float, half_depth: float) -> Vector3:
	var h: float = img.get_pixel(x, z).r
	return Vector3(float(x) * cell_size_x - half_width, height_offset + h * max_height, float(z) * cell_size_z - half_depth)

func _add_vertex(st: SurfaceTool, point: Vector3, uv: Vector2) -> void:
	st.set_uv(uv)
	st.add_vertex(point)

func _build_material() -> StandardMaterial3D:
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	if diffuse_texture != null:
		mat.albedo_texture = diffuse_texture
	if normal_texture != null:
		mat.normal_enabled = true
		mat.normal_texture = normal_texture
	if roughness_texture != null:
		mat.roughness_texture = roughness_texture
	if ao_texture != null:
		mat.set("ao_enabled", true)
		mat.set("ao_texture", ao_texture)
		mat.set("ao_light_affect", 0.65)
	mat.roughness = 1.0
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
	return mat

func _create_center_preview(manifest: TerrainChunkManifest) -> void:
	_clear_preview()
	var preview_root: Node3D = Node3D.new()
	preview_root.name = "PreviewChunks"
	add_child(preview_root)
	var edited_root: Node = get_tree().edited_scene_root
	if edited_root != null:
		preview_root.owner = edited_root
	for data: Dictionary in manifest.chunks:
		var cx: int = int(data.get("x", 0))
		var cz: int = int(data.get("z", 0))
		if cx > preview_radius_chunks or cz > preview_radius_chunks:
			continue
		_create_preview_chunk(preview_root, data, manifest)

func _create_preview_chunk(parent: Node3D, data: Dictionary, manifest: TerrainChunkManifest) -> void:
	var mesh_path: String = String(data.get("mesh_path", ""))
	if not ResourceLoader.exists(mesh_path):
		return
	var mesh: ArrayMesh = ResourceLoader.load(mesh_path, "", ResourceLoader.CACHE_MODE_REPLACE) as ArrayMesh
	if mesh == null:
		return
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = String(data.get("id", "chunk_preview"))
	mi.mesh = mesh
	mi.position = data.get("center", Vector3.ZERO)
	if preview_load_material and ResourceLoader.exists(manifest.material_path):
		var material: Material = ResourceLoader.load(manifest.material_path, "", ResourceLoader.CACHE_MODE_REPLACE) as Material
		if material != null:
			mi.material_override = material
	parent.add_child(mi)
	var edited_root: Node = get_tree().edited_scene_root
	if edited_root != null:
		mi.owner = edited_root

func _clear_preview() -> void:
	var old: Node = get_node_or_null("PreviewChunks")
	if old == null:
		return
	remove_child(old)
	old.free()
