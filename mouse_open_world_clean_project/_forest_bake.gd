extends SceneTree

# SANDBOX BAKER (shipped DEGIL): N cam varyantini PROSEDUREL uretip
# her birini res://forest_data/pine_v<i>.scn olarak DISKE kaydeder
# (mesh verisi .scn dosyalarinda, ana sahneye GOMULMEZ). Sonra 100
# agaclik ormani kurup cokme + performans (tri / bellek / sure) olcer.

const VARIANTS := 8
const FOREST_COUNT := 100
const AREA := 60.0
const DATA_DIR := "res://forest_data"

func _set_owner_rec(n: Node, o: Node) -> void:
	for c in n.get_children():
		c.owner = o
		_set_owner_rec(c, o)

func _initialize() -> void:
	var t0 := Time.get_ticks_msec()
	DirAccess.make_dir_recursive_absolute(DATA_DIR)

	# --- 1) Varyantlari uret + DISKE .scn kaydet ---
	var holder := Node3D.new()
	root.add_child(holder)
	var variant_paths: Array[String] = []
	for v in range(VARIANTS):
		var pt: Node3D = PineTree.new()
		pt.name = "PineV%d" % v
		pt.set("seed", 1000 + v * 7)
		pt.set("texture_quality", 1)
		holder.add_child(pt)
		# _ready -> rebuild.call_deferred(); birkac kare bekle (senkron yapim)
		for i in range(8):
			await process_frame
		_set_owner_rec(pt, pt)
		var ps := PackedScene.new()
		var err := ps.pack(pt)
		var outp := "%s/pine_v%d.scn" % [DATA_DIR, v]
		if err == OK:
			var serr := ResourceSaver.save(ps, outp)
			print("VARIANT %d save=%d -> %s" % [v, serr, outp])
			if serr == OK:
				variant_paths.append(outp)
		else:
			print("VARIANT %d pack ERROR %d" % [v, err])
		pt.queue_free()
		await process_frame
	holder.queue_free()
	await process_frame
	print("BAKED_VARIANTS=%d in %dms" % [variant_paths.size(), Time.get_ticks_msec() - t0])

	# --- 2) DISKTEN yukle + 100 agaclik orman (cokme/perf testi) ---
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260517
	var packed_variants: Array[PackedScene] = []
	for p in variant_paths:
		var pv: PackedScene = load(p)
		if pv != null:
			packed_variants.append(pv)
	if packed_variants.is_empty():
		print("FATAL: hic varyant yuklenemedi"); quit(); return

	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -40, 0)
	sun.light_energy = 1.1
	root.add_child(sun)
	var we := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.55, 0.66, 0.78)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.62, 0.68, 0.74)
	env.ambient_light_energy = 0.9
	we.environment = env
	root.add_child(we)

	var forest := Node3D.new()
	forest.name = "Forest"
	root.add_child(forest)
	var t1 := Time.get_ticks_msec()
	var placed := 0
	for i in range(FOREST_COUNT):
		var pv: PackedScene = packed_variants[i % packed_variants.size()]
		var inst: Node3D = pv.instantiate()
		var ang := rng.randf() * TAU
		var rad := sqrt(rng.randf()) * AREA
		inst.position = Vector3(cos(ang) * rad, 0.0, sin(ang) * rad)
		inst.rotation.y = rng.randf() * TAU
		var s := rng.randf_range(0.8, 1.25)
		inst.scale = Vector3(s, s, s)
		forest.add_child(inst)
		placed += 1
	var build_ms := Time.get_ticks_msec() - t1
	for i in range(30):
		await process_frame
	await RenderingServer.frame_post_draw

	var tris := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
	var draws := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	var vram := RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED)
	var mem := OS.get_static_memory_usage()
	print("FOREST_PLACED=%d" % placed)
	print("FOREST_BUILD_MS=%d" % build_ms)
	print("FOREST_TRIS=%d" % tris)
	print("FOREST_DRAWCALLS=%d" % draws)
	print("FOREST_VRAM_MB=%.1f" % (float(vram) / 1048576.0))
	print("FOREST_STATICMEM_MB=%.1f" % (float(mem) / 1048576.0))
	print("FOREST_TOTAL_MS=%d" % (Time.get_ticks_msec() - t0))

	var cam := Camera3D.new()
	root.add_child(cam)
	cam.current = true
	cam.fov = 60.0
	cam.global_position = Vector3(0, 22, AREA * 0.95)
	cam.look_at(Vector3(0, 6, 0), Vector3.UP)
	for i in range(6):
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("/tmp/forest_wide.png")
	cam.global_position = Vector3(8, 3, 14)
	cam.look_at(Vector3(0, 5, 0), Vector3.UP)
	for i in range(6):
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("/tmp/forest_close.png")
	print("FOREST_OK_NO_CRASH")
	quit()
