extends SceneTree

# Sade cam agacini GLB'ye aktarir: res://scenes/world/pine_tree.glb
# GLB/glTF OZEL SHADER TASIMAZ -> materyaller StandardMaterial3D'ye
# cevrilir, igne UV'si atlas hucresine BAKE edilir (shader'siz dogru
# gorunsun). KAYBOLAN (shader-only): ruzgar animasyonu, kuru-uc
# gradyani, kabuk dunya-varyasyonu. Geometri + foto PBR doku KORUNUR.

const TEX := "res://assets/trees/pine_ultra_mobile/textures/"

func _bark_std() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_texture = load(TEX + "bark/pine_bark_albedo_2k.jpg")
	m.normal_enabled = true
	m.normal_texture = load(TEX + "bark/pine_bark_normal_2k.jpg")
	var ormc: Texture2D = load(TEX + "bark/pine_bark_ormc_2k.jpg")
	m.ao_enabled = true
	m.ao_texture = ormc
	m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	m.roughness_texture = ormc
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.uv1_scale = Vector3(2.5, 3.5, 1.0)
	m.metallic = 0.0
	return m

func _needle_std() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.albedo_texture = load(TEX + "needles/pine_needles_albedo_alpha_2k.png")
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.4
	m.normal_enabled = true
	m.normal_texture = load(TEX + "needles/pine_needles_normal_2k.png")
	m.roughness = 0.9
	m.metallic = 0.0
	return m

# Igne UV1'ini, UV2.y'deki 5x5 atlas hucresine gore yeniden esle
# (shader'daki auv formulunun mesh'e bake edilmis hali).
func _bake_needle_uv(mesh: Mesh) -> ArrayMesh:
	var out := ArrayMesh.new()
	for s in range(mesh.get_surface_count()):
		var arr: Array = mesh.surface_get_arrays(s)
		var uv: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV]
		var uv2: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV2]
		if uv.size() == uv2.size() and uv.size() > 0:
			for i in range(uv.size()):
				var cell: float = floor(uv2[i].y + 0.5)
				var cbx: float = fmod(cell, 5.0)
				var cby: float = floor(cell / 5.0)
				var lx: float = clampf(uv[i].x, 0.0, 1.0)
				var ly: float = clampf(uv[i].y, 0.0, 1.0)
				uv[i] = Vector2((lx * 0.92 + 0.04 + cbx) / 5.0,
								(ly * 0.92 + 0.04 + cby) / 5.0)
			arr[Mesh.ARRAY_TEX_UV] = uv
		arr[Mesh.ARRAY_TEX_UV2] = null
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	return out

func _initialize() -> void:
	var ps: PackedScene = load("res://scenes/world/pine_tree_scene.tscn")
	var tree: Node = ps.instantiate()
	root.add_child(tree)
	for i in range(10):
		await process_frame

	var bark_std := _bark_std()
	var needle_std := _needle_std()
	var n := 0
	for c in tree.get_children():
		if not (c is MeshInstance3D) or c.mesh == null:
			continue
		var mi := c as MeshInstance3D
		var nm := String(mi.name).to_lower()
		if nm.find("needle") != -1 or nm.find("leaf") != -1 or nm.find("yaprak") != -1:
			mi.mesh = _bake_needle_uv(mi.mesh)
			mi.material_override = null
			mi.mesh.surface_set_material(0, needle_std)
		else:
			mi.material_override = null
			for si in range(mi.mesh.get_surface_count()):
				mi.mesh.surface_set_material(si, bark_std)
		n += 1
	print("MESHES_REMATERIALIZED=%d" % n)

	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_scene(tree, state)
	print("APPEND_ERR=%d" % err)
	if err == OK:
		var outp := "res://scenes/world/pine_tree.glb"
		var werr := doc.write_to_filesystem(state, outp)
		print("WRITE_ERR=%d -> %s" % [werr, outp])
	print("GLB_EXPORT_DONE")
	quit()
