@tool
extends Node3D
class_name PineTree

# AAA prosedürel iğne yapraklı ağaç (ladin/köknar tipi konifer).
# Sağlamlık: foliage StandardMaterial3D ile çizilir (custom shader beyaz
# fallback riski yok). Yeşil dokuya bakelidir, AO vertex renginden çarpılır.
# - Kök payandalı, plakalı kabuk dokulu, hafif eğimli gövde
# - Belirgin KATMANLI (whorl) dal tabakaları -> net kozalak silüeti
# - Her dal ekseni etrafında çok BIÇAKLI yoğun iğne spreyi (ince, sarkık)
# - Silüeti dolduran iç koni; AO için vertex rengi
# Dokular tüm ağaçlarda paylaşılır (static cache) -> orman ucuz kalır.

@export_group("Boyut")
@export var total_height: float = 7.0
@export var trunk_radius: float = 0.16
@export_range(0.03, 0.4, 0.01) var trunk_top_ratio: float = 0.06
@export_range(0.0, 0.3, 0.01) var trunk_bend: float = 0.05

@export_group("Taç / Dallar")
@export var crown_start_ratio: float = 0.13
@export_range(1.5, 6.0, 0.1) var crown_radius: float = 2.4
@export_range(20, 90, 1) var branch_count: int = 60
@export_range(0.15, 1.2, 0.02) var branch_droop: float = 0.55

@export_group("İğne Yaprak")
@export_range(3, 10, 1) var blades_per_branch: int = 6
@export_range(0.4, 2.0, 0.05) var frond_size: float = 1.0
@export var inner_fill: bool = true

@export_group("Detay / Performans")
@export_range(6, 14, 1) var trunk_sides: int = 10
@export var seed: int = 0
@export var generate_collision: bool = true
@export var enable_wind: bool = false  # önce doğru render; sonra açılabilir

@export_group("Renk")
@export var bark_color: Color = Color(0.34, 0.22, 0.15)
@export var needle_dark: Color = Color(0.05, 0.13, 0.06)
@export var needle_mid: Color = Color(0.13, 0.27, 0.11)
@export var needle_lite: Color = Color(0.34, 0.50, 0.22)

const GOLDEN_ANGLE := 2.399963229728653

static var _shared_needle_tex: Texture2D
static var _shared_bark_tex: Texture2D

var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	rebuild()

func rebuild() -> void:
	for c in get_children():
		c.queue_free()
	_rng.seed = seed if seed != 0 else hash(name)

	var bark := SurfaceTool.new()
	bark.begin(Mesh.PRIMITIVE_TRIANGLES)
	var leaf := SurfaceTool.new()
	leaf.begin(Mesh.PRIMITIVE_TRIANGLES)

	var phase := _rng.randf() * TAU
	_build_trunk(bark, phase)
	if inner_fill:
		_build_inner_cone(leaf, phase)
	_build_tiers(bark, leaf, phase)

	bark.generate_normals()
	bark.generate_tangents()
	var bark_mi := MeshInstance3D.new()
	bark_mi.name = "Bark"
	bark_mi.mesh = bark.commit()
	bark_mi.material_override = _bark_material()
	add_child(bark_mi)

	leaf.generate_normals()
	var leaf_mi := MeshInstance3D.new()
	leaf_mi.name = "Foliage"
	leaf_mi.mesh = leaf.commit()
	leaf_mi.material_override = _needle_material()
	add_child(leaf_mi)

	if generate_collision and not Engine.is_editor_hint():
		_build_collision()

# --- Gövde -------------------------------------------------------------

func _bend_offset(h01: float, phase: float) -> Vector3:
	var amt := trunk_bend * total_height
	return Vector3(sin(h01 * 1.4 + phase) * amt * h01 * h01, 0.0,
		cos(h01 * 1.1 + phase) * amt * 0.5 * h01 * h01)

func _trunk_point(h01: float, phase: float) -> Vector3:
	return Vector3(0.0, h01 * total_height, 0.0) + _bend_offset(h01, phase)

func _trunk_radius_at(t: float) -> float:
	var base: float = lerp(trunk_radius, trunk_radius * trunk_top_ratio, pow(t, 0.85))
	var buttress := trunk_radius * 1.4 * pow(maxf(1.0 - t * 6.0, 0.0), 2.0)
	return base + buttress

func _build_trunk(st: SurfaceTool, phase: float) -> void:
	var rings := 20
	var side_jit := PackedFloat32Array()
	for s in range(trunk_sides):
		side_jit.append(1.0 + _rng.randf_range(-0.06, 0.08))
	for ri in range(rings):
		var t0 := float(ri) / float(rings)
		var t1 := float(ri + 1) / float(rings)
		var c0 := _trunk_point(t0, phase)
		var c1 := _trunk_point(t1, phase)
		var rr0 := _trunk_radius_at(t0)
		var rr1 := _trunk_radius_at(t1)
		for si in range(trunk_sides):
			var a0 := TAU * float(si) / float(trunk_sides)
			var a1 := TAU * float(si + 1) / float(trunk_sides)
			var j0: float = side_jit[si]
			var j1: float = side_jit[(si + 1) % trunk_sides]
			var uA := float(si) / float(trunk_sides) * 2.0
			var uB := float(si + 1) / float(trunk_sides) * 2.0
			var v0 := t0 * 6.0
			var v1 := t1 * 6.0
			var p00 := c0 + Vector3(cos(a0) * rr0 * j0, 0, sin(a0) * rr0 * j0)
			var p10 := c0 + Vector3(cos(a1) * rr0 * j1, 0, sin(a1) * rr0 * j1)
			var p01 := c1 + Vector3(cos(a0) * rr1 * j0, 0, sin(a0) * rr1 * j0)
			var p11 := c1 + Vector3(cos(a1) * rr1 * j1, 0, sin(a1) * rr1 * j1)
			st.set_uv(Vector2(uA, v0)); st.add_vertex(p00)
			st.set_uv(Vector2(uA, v1)); st.add_vertex(p01)
			st.set_uv(Vector2(uB, v1)); st.add_vertex(p11)
			st.set_uv(Vector2(uA, v0)); st.add_vertex(p00)
			st.set_uv(Vector2(uB, v1)); st.add_vertex(p11)
			st.set_uv(Vector2(uB, v0)); st.add_vertex(p10)

# --- İç dolgu konisi (silüeti kapatır, derinlik) ----------------------

func _build_inner_cone(st: SurfaceTool, phase: float) -> void:
	var sides := 9
	var rings := 7
	var c_start := crown_start_ratio
	for ri in range(rings):
		var t0 := float(ri) / float(rings)
		var t1 := float(ri + 1) / float(rings)
		var h0: float = lerp(c_start, 0.96, t0)
		var h1: float = lerp(c_start, 0.96, t1)
		var c0 := _trunk_point(h0, phase)
		var c1 := _trunk_point(h1, phase)
		var rr0 := crown_radius * 0.5 * pow(1.0 - t0, 0.8)
		var rr1 := crown_radius * 0.5 * pow(1.0 - t1, 0.8)
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			var a1 := TAU * float(si + 1) / float(sides)
			var P0 := c0 + Vector3(cos(a0) * rr0, 0, sin(a0) * rr0)
			var P1 := c1 + Vector3(cos(a0) * rr1, 0, sin(a0) * rr1)
			var P2 := c1 + Vector3(cos(a1) * rr1, 0, sin(a1) * rr1)
			var P3 := c0 + Vector3(cos(a1) * rr0, 0, sin(a1) * rr0)
			_leaf_vert(st, P0, Vector2(0.15, t0 * 2.0), 0.32)
			_leaf_vert(st, P1, Vector2(0.15, t1 * 2.0), 0.40)
			_leaf_vert(st, P2, Vector2(0.85, t1 * 2.0), 0.40)
			_leaf_vert(st, P0, Vector2(0.15, t0 * 2.0), 0.32)
			_leaf_vert(st, P2, Vector2(0.85, t1 * 2.0), 0.40)
			_leaf_vert(st, P3, Vector2(0.85, t0 * 2.0), 0.32)

# --- Katmanlı dal tabakaları ------------------------------------------

func _build_tiers(bark: SurfaceTool, leaf: SurfaceTool, phase: float) -> void:
	var tier_count := clampi(int(round(total_height * 2.2)), 9, 20)
	var c_start := crown_start_ratio
	var tier_az := _rng.randf() * TAU
	for ti in range(tier_count):
		var tf := float(ti) / float(tier_count - 1)
		var h01: float = lerp(c_start, 0.955, tf)
		# Konifer profili: alt-ortada en uzun, tepede sıfıra sivrilir.
		var prof: float = pow(1.0 - tf, 0.80) * (0.45 + 0.55 * smoothstep(0.0, 0.18, tf))
		var tier_len := crown_radius * prof
		if tier_len < 0.16:
			continue
		var per_tier := int(round(lerp(float(branch_count) / float(tier_count) * 1.5, 3.0, tf)))
		per_tier = clampi(per_tier, 3, 10)
		tier_az += GOLDEN_ANGLE * 1.3
		for bi in range(per_tier):
			var az := tier_az + TAU * float(bi) / float(per_tier) + _rng.randf_range(-0.16, 0.16)
			var jitter_h := h01 + _rng.randf_range(-0.012, 0.012)
			var attach := _trunk_point(jitter_h, phase)
			var length := tier_len * _rng.randf_range(0.82, 1.14)
			var droop_amt := branch_droop * (0.4 + 0.6 * (1.0 - tf))
			_make_branch(bark, leaf, attach, az, length, droop_amt, tf)

func _make_branch(bark: SurfaceTool, leaf: SurfaceTool, attach: Vector3, az: float,
		length: float, droop_amt: float, tf: float) -> void:
	var dir := Vector3(cos(az), 0.0, sin(az))
	var up0: float = lerp(0.30, 0.05, tf)
	var segs := 6
	var pts: Array[Vector3] = [attach]
	var cur := attach
	var seg_dir := (dir + Vector3.UP * up0).normalized()
	for s in range(segs):
		var sl := length / float(segs)
		cur += seg_dir * sl
		pts.append(cur)
		var d := droop_amt * (0.10 + 0.5 * float(s) / float(segs))
		seg_dir = (seg_dir + Vector3.DOWN * d).normalized()
	_emit_branch_wood(bark, pts)
	# Ekseni saran çok bıçaklı yoğun iğne spreyi.
	var blades := clampi(blades_per_branch, 3, 10)
	for spi in range(blades):
		var roll := PI * float(spi) / float(blades) + _rng.randf_range(-0.15, 0.15)
		_emit_blade(leaf, pts, tf, roll)

func _emit_branch_wood(st: SurfaceTool, pts: Array[Vector3]) -> void:
	var sides := 4
	var n := pts.size()
	for k in range(n - 1):
		var r0: float = lerp(trunk_radius * 0.24, 0.004, float(k) / float(n - 1))
		var r1: float = lerp(trunk_radius * 0.24, 0.004, float(k + 1) / float(n - 1))
		var axis := (pts[k + 1] - pts[k]).normalized()
		var up := Vector3.UP if absf(axis.y) < 0.95 else Vector3.RIGHT
		var nx := axis.cross(up).normalized()
		var nz := axis.cross(nx).normalized()
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			var a1 := TAU * float(si + 1) / float(sides)
			var o0 := nx * cos(a0) + nz * sin(a0)
			var o1 := nx * cos(a1) + nz * sin(a1)
			var p00 := pts[k] + o0 * r0
			var p10 := pts[k] + o1 * r0
			var p01 := pts[k + 1] + o0 * r1
			var p11 := pts[k + 1] + o1 * r1
			st.set_uv(Vector2(0, 0)); st.add_vertex(p00)
			st.set_uv(Vector2(0, 1)); st.add_vertex(p01)
			st.set_uv(Vector2(1, 1)); st.add_vertex(p11)
			st.set_uv(Vector2(0, 0)); st.add_vertex(p00)
			st.set_uv(Vector2(1, 1)); st.add_vertex(p11)
			st.set_uv(Vector2(1, 0)); st.add_vertex(p10)

func _emit_blade(st: SurfaceTool, pts: Array[Vector3], tf: float, roll: float) -> void:
	# Dalı izleyen ince düz iğne bıçağı; doku V'de tilelenir, alpha keser.
	var n := pts.size()
	var axis0 := (pts[1] - pts[0]).normalized()
	var up := Vector3.UP if absf(axis0.y) < 0.95 else Vector3.FORWARD
	var ref := axis0.cross(up).normalized()
	var width := frond_size * (0.16 + 0.10 * (1.0 - tf))
	var acc := 0.0
	for k in range(n - 1):
		var seg := pts[k + 1] - pts[k]
		var seg_len := seg.length()
		var axis := seg.normalized()
		var bn := axis.cross(ref).normalized()
		var flat := (ref * cos(roll) + bn * sin(roll)).normalized()
		var kf0 := float(k) / float(n - 1)
		var kf1 := float(k + 1) / float(n - 1)
		var w0 := width * _spray_w(kf0)
		var w1 := width * _spray_w(kf1)
		# İğneler hafif aşağı sarkar (yerçekimi).
		var sag0 := Vector3.DOWN * w0 * 0.45
		var sag1 := Vector3.DOWN * w1 * 0.45
		var L0 := pts[k] - flat * w0 + sag0
		var R0 := pts[k] + flat * w0 + sag0
		var L1 := pts[k + 1] - flat * w1 + sag1
		var R1 := pts[k + 1] + flat * w1 + sag1
		var v0 := acc
		acc += seg_len / maxf(frond_size * 0.42, 0.08)
		var v1 := acc
		# AO: gövdeye yakın koyu, uca doğru aydınlık.
		var ao0: float = lerp(0.42, 1.0, kf0)
		var ao1: float = lerp(0.42, 1.0, kf1)
		_leaf_vert(st, L0, Vector2(0, v0), ao0)
		_leaf_vert(st, L1, Vector2(0, v1), ao1)
		_leaf_vert(st, R1, Vector2(1, v1), ao1)
		_leaf_vert(st, L0, Vector2(0, v0), ao0)
		_leaf_vert(st, R1, Vector2(1, v1), ao1)
		_leaf_vert(st, R0, Vector2(1, v0), ao0)

func _spray_w(k: float) -> float:
	return sin(clampf(k, 0.0, 1.0) * PI) * 0.65 + (1.0 - k) * 0.45 + 0.15

func _leaf_vert(st: SurfaceTool, p: Vector3, uv: Vector2, ao: float) -> void:
	# AO grisi -> vertex_color_use_as_albedo ile yeşil dokuyu koyulaştırır.
	var a := clampf(ao, 0.0, 1.0)
	st.set_color(Color(a, a, a, 1.0))
	st.set_uv(uv)
	st.add_vertex(p)

# --- Materyaller / dokular --------------------------------------------

func _bark_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = bark_color
	m.albedo_texture = _bark_texture()
	m.roughness = 0.92
	m.metallic = 0.0
	m.specular = 0.12
	return m

func _needle_material() -> Material:
	var tex := _needle_texture()
	if enable_wind and ResourceLoader.exists("res://shaders/pine_wind.gdshader"):
		var sh := ResourceLoader.load("res://shaders/pine_wind.gdshader") as Shader
		if sh != null:
			var sm := ShaderMaterial.new()
			sm.shader = sh
			sm.set_shader_parameter("needle_tex", tex)
			sm.set_shader_parameter("tree_height", total_height)
			sm.set_shader_parameter("tip_color", needle_lite)
			return sm
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.albedo_color = Color(1, 1, 1, 1)
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.5
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 0.86
	m.specular = 0.16
	# Hafif iç ışıma -> iğnelerde alt-yüzey geçirgenlik hissi.
	m.emission_enabled = true
	m.emission = needle_mid
	m.emission_energy_multiplier = 0.05
	return m

func _needle_texture() -> Texture2D:
	if _shared_needle_tex != null:
		return _shared_needle_tex
	# Dikeyde tilelenebilir yoğun iğne dalcığı: orta sap + iki yana ince
	# iğneler. Yeşil dokuya bakelidir (materyalden bağımsız doğru renk).
	var w := 512
	var h := 512
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7331
	var cx := float(w) * 0.5
	var signs: Array[float] = [-1.0, 1.0]
	var rows := 150
	for r in range(rows):
		var y := float(r) / float(rows) * float(h)
		var stem_x := cx + sin(y * 0.045) * 14.0
		for sgn in signs:
			var per := 2
			for c in range(per):
				var jy := y + rng.randf_range(-3.0, 3.0)
				var nl := rng.randf_range(70.0, 150.0)
				var ang: float = deg_to_rad(rng.randf_range(38.0, 64.0)) * sgn
				var p0 := Vector2(stem_x + sgn * 3.0, jy)
				var p1 := p0 + Vector2(sin(ang), -cos(ang)) * nl
				var shade := rng.randf()
				var c0: Color
				if shade < 0.4:
					c0 = needle_dark
				elif shade < 0.8:
					c0 = needle_mid
				else:
					c0 = needle_lite
				_draw_needle(img, p0, p1, rng.randf_range(1.4, 2.4), c0, needle_lite)
	# Orta sap (koyu ince çizgi).
	for r2 in range(h):
		var sx := int(round(cx + sin(float(r2) * 0.045) * 14.0))
		for ox in range(-2, 3):
			var px := sx + ox
			if px >= 0 and px < w:
				img.set_pixel(px, r2, Color(needle_dark.r, needle_dark.g, needle_dark.b, 1.0))
	_shared_needle_tex = ImageTexture.create_from_image(img)
	return _shared_needle_tex

func _draw_needle(img: Image, p0: Vector2, p1: Vector2, w: float, c0: Color, c1: Color) -> void:
	var steps := int(ceil(p0.distance_to(p1)))
	var H := img.get_height()
	var W := img.get_width()
	for s in range(steps + 1):
		var t := float(s) / float(maxi(steps, 1))
		var p := p0.lerp(p1, t)
		var col := c0.lerp(c1, t * 0.6)
		col.a = lerp(1.0, 0.5, t)
		var rad := maxf(w * (1.0 - 0.55 * t), 0.6)
		var ri := int(ceil(rad))
		for oy in range(-ri, ri + 1):
			for ox in range(-ri, ri + 1):
				if Vector2(ox, oy).length() > rad:
					continue
				var px := int(round(p.x)) + ox
				var py := ((int(round(p.y)) + oy) % H + H) % H
				if px < 0 or px >= W:
					continue
				var ex := img.get_pixel(px, py)
				if col.a > ex.a:
					img.set_pixel(px, py, col)

func _bark_texture() -> Texture2D:
	if _shared_bark_tex != null:
		return _shared_bark_tex
	var w := 128
	var h := 256
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var n := FastNoiseLite.new()
	n.noise_type = FastNoiseLite.TYPE_SIMPLEX
	n.frequency = 0.05
	var plate := FastNoiseLite.new()
	plate.noise_type = FastNoiseLite.TYPE_CELLULAR
	plate.frequency = 0.018
	plate.cellular_return_type = FastNoiseLite.RETURN_DISTANCE2_SUB
	for y in range(h):
		for x in range(w):
			var fib := n.get_noise_2d(float(x) * 3.0, float(y) * 0.55)
			var pl := plate.get_noise_2d(float(x) * 1.6, float(y) * 1.0)
			var v: float = 0.62 + 0.30 * fib
			if pl > 0.32:
				v *= 0.38
			elif pl > 0.18:
				v *= 0.70
			v = clampf(v, 0.12, 1.05)
			var warm := Color(0.42, 0.27, 0.17) * v + Color(0.05, 0.03, 0.02)
			img.set_pixel(x, y, Color(warm.r, warm.g, warm.b, 1.0))
	_shared_bark_tex = ImageTexture.create_from_image(img)
	return _shared_bark_tex

func _build_collision() -> void:
	var body := StaticBody3D.new()
	body.name = "TrunkBody"
	add_child(body)
	var col := CollisionShape3D.new()
	var shape := CylinderShape3D.new()
	shape.radius = maxf(trunk_radius * 1.4, 0.18)
	shape.height = total_height
	col.shape = shape
	col.position = Vector3(0.0, total_height * 0.5, 0.0)
	body.add_child(col)
