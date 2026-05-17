extends SceneTree

# SAF ORMAN STRES TESTI (ayri dal: claude/forest-stress-test).
# Sadece: diskten 100 agac + TEK directional light. WorldEnvironment
# YOK, gokyuzu YOK, tonemap/efekt YOK -> saf agaclar. Amac yalnizca
# COKME + YAVASLAMA olcumu ve farkli acilardan goruntu.

const COUNT := 100
const AREA := 60.0
const DATA_DIR := "res://forest_data"

func _shot(cam: Camera3D, pos: Vector3, look: Vector3, path: String) -> void:
	cam.global_position = pos
	cam.look_at(look, Vector3.UP)
	for i in range(5):
		await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(path)

func _initialize() -> void:
	# Saf: yalniz gorunurluk icin tek isik (WorldEnvironment/sky YOK).
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-55, -35, 0)
	sun.light_energy = 1.2
	root.add_child(sun)

	var variants: Array[PackedScene] = []
	var vi := 0
	while true:
		var p := "%s/pine_v%d.scn" % [DATA_DIR, vi]
		if not ResourceLoader.exists(p):
			break
		var ps: PackedScene = load(p)
		if ps != null:
			variants.append(ps)
		vi += 1
	if variants.is_empty():
		print("FATAL: forest_data bos (_forest_bake.gd calistir)"); quit(); return
	print("VARIANTS_LOADED=%d" % variants.size())

	var rng := RandomNumberGenerator.new()
	rng.seed = 20260517
	var forest := Node3D.new()
	forest.name = "Forest"
	root.add_child(forest)

	var tb := Time.get_ticks_msec()
	var placed: Array[Vector2] = []
	var made := 0
	var att := 0
	while made < COUNT and att < COUNT * 30:
		att += 1
		var ang := rng.randf() * TAU
		var rad := sqrt(rng.randf()) * AREA
		var p2 := Vector2(cos(ang) * rad, sin(ang) * rad)
		var ok := true
		for q in placed:
			if p2.distance_to(q) < 2.5:
				ok = false
				break
		if not ok:
			continue
		placed.append(p2)
		var inst: Node3D = variants[made % variants.size()].instantiate()
		inst.position = Vector3(p2.x, 0.0, p2.y)
		inst.rotation.y = rng.randf() * TAU
		var sc := rng.randf_range(0.8, 1.25)
		inst.scale = Vector3(sc, sc, sc)
		forest.add_child(inst)
		made += 1
	var build_ms := Time.get_ticks_msec() - tb
	print("FOREST_PLACED=%d" % made)
	print("FOREST_BUILD_MS=%d" % build_ms)

	# --- YAVASLAMA OLCUMU: 150 kare, kare-suresi istatistigi ---
	for i in range(20):
		await process_frame
	var n := 150
	var tmin := 1e9
	var tmax := 0.0
	var tsum := 0.0
	for i in range(n):
		var a := Time.get_ticks_usec()
		await process_frame
		var d := float(Time.get_ticks_usec() - a) / 1000.0
		tsum += d
		tmin = minf(tmin, d)
		tmax = maxf(tmax, d)
	var avg := tsum / float(n)
	print("FRAME_MS_AVG=%.2f" % avg)
	print("FRAME_MS_MIN=%.2f" % tmin)
	print("FRAME_MS_MAX=%.2f" % tmax)
	print("APPROX_FPS=%.1f" % (1000.0 / maxf(avg, 0.001)))
	print("STATICMEM_MB=%.1f" % (float(OS.get_static_memory_usage()) / 1048576.0))

	# --- FARKLI ACILARDAN GORUNTU ---
	var cam := Camera3D.new()
	root.add_child(cam)
	cam.current = true
	cam.fov = 60.0
	cam.far = 400.0
	await _shot(cam, Vector3(0, 95, 1), Vector3(0, 0, 0), "/tmp/ft_top.png")
	await _shot(cam, Vector3(AREA * 1.05, 30, AREA * 1.05), Vector3(0, 6, 0), "/tmp/ft_persp.png")
	await _shot(cam, Vector3(AREA * 1.25, 8, 0), Vector3(0, 7, 0), "/tmp/ft_side.png")
	await _shot(cam, Vector3(6, 1.6, 20), Vector3(0, 6, -10), "/tmp/ft_ground.png")
	await _shot(cam, Vector3(20, 12, 20), Vector3(0, 5, 0), "/tmp/ft_mid.png")
	print("FOREST_STRESS_OK_NO_CRASH")
	quit()
